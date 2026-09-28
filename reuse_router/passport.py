"""SafeAI Passport: a signed, tamper-evident certificate for each marketplace asset (SPEC §12).

No AI here, deliberately: proof should be plain cryptography a risk team can reason about.

- Ed25519 signatures: only the marketplace holds the private key; anyone holding the public
  key can verify a passport without calling the marketplace.
- Canonical JSON: the same content always serializes to the same bytes, so changing any
  field, even one character, breaks the signature.
- Deterministic: Ed25519 signs the same bytes the same way, so passports are recomputed from
  the catalog on demand and the POC needs no database.

    uv run python -m reuse_router.passport keygen    # a key for PASSPORT_SIGNING_KEY
"""

import base64
import binascii
import hashlib
import json
import os
import sys
from datetime import date, timedelta

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from reuse_router.catalog import Tool

SCHEMA = "safeai-passport/v0"
VALIDITY_DAYS = 365
KEY_ENV = "PASSPORT_SIGNING_KEY"
# Used only when no key is configured. Public by design: fine for demonstrating tamper
# detection, worthless as real trust. The UI labels passports signed with it.
DEMO_SEED = hashlib.sha256(b"safeai-passport-demo-key").digest()

CHECK_NAMES = {
    "licence": "Licence compliance",
    "secrets": "Secrets scan",
    "dependencies": "Dependency vulnerabilities",
    "tests": "Unit and integration tests",
    "eval_evidence": "Evaluation evidence",
    "prompt_injection": "Prompt-injection suite",
    "pii_leakage": "Personal-data leakage suite",
}


def _seed() -> tuple[bytes, bool]:
    raw = os.environ.get(KEY_ENV, "").strip()
    if not raw:
        return DEMO_SEED, True
    try:
        seed = base64.b64decode(raw, validate=True)
    except binascii.Error as error:
        raise ValueError(f"{KEY_ENV} is not valid base64") from error
    if len(seed) != 32:
        raise ValueError(f"{KEY_ENV} must decode to 32 bytes; generate one with `python -m reuse_router.passport keygen`")
    return seed, False


def _private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_seed()[0])


def _raw_public(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)


def _key_id(key: Ed25519PublicKey) -> str:
    return hashlib.sha256(_raw_public(key)).hexdigest()[:16]


def public_key_info() -> dict:
    public = _private_key().public_key()
    return {
        "algorithm": "Ed25519",
        "key_id": _key_id(public),
        "public_key": base64.b64encode(_raw_public(public)).decode(),
        "demo_key": _seed()[1],
    }


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def payload_for(tool: Tool) -> dict:
    issued = date.fromisoformat(tool.certified_on)
    return {
        "schema": SCHEMA,
        "passport_id": f"sap-{tool.id}-{tool.version}",
        "asset": {
            "id": tool.id,
            "name": tool.name,
            "version": tool.version,
            "owner": tool.owner,
            "repo": tool.repo,
            "commit": tool.commit,
        },
        "risk_tier": tool.risk_tier,
        "approved_data_up_to": tool.approved_up_to,
        "checks": [
            {
                "id": check,
                "name": CHECK_NAMES[check],
                "suite": f"pantheon-mock/{check}@1.0",
                "result": "pass",
                # Stands in for a hash of the check's report, so evidence can't be swapped later.
                "evidence_sha256": hashlib.sha256(f"{tool.id}:{tool.commit}:{check}".encode()).hexdigest(),
            }
            for check in tool.checks
        ],
        "evaluated_by": "Pantheon (mock)",
        "approved_by": "AI Risk Office (mock)",
        "issued_on": issued.isoformat(),
        "expires_on": (issued + timedelta(days=VALIDITY_DAYS)).isoformat(),
    }


def issue(tool: Tool) -> dict:
    key = _private_key()
    payload = payload_for(tool)
    return {
        "payload": payload,
        "signature": {
            "algorithm": "Ed25519",
            "key_id": _key_id(key.public_key()),
            "value": base64.b64encode(key.sign(canonical(payload))).decode(),
        },
    }


def _step(name: str, ok: bool | None, detail: str) -> dict:
    return {"name": name, "ok": ok, "detail": detail}


def verify(passport: dict, current_commit: str | None = None, today: date | None = None) -> dict:
    """Check signature, then expiry, then that the code still matches what was certified.

    `current_commit` is the repo head the marketplace sees now; None skips that check.
    """
    today = today or date.today()
    public = _private_key().public_key()
    try:
        payload = passport["payload"]
        signature = base64.b64decode(passport["signature"]["value"], validate=True)
        public.verify(signature, canonical(payload))
    except (KeyError, TypeError, ValueError, binascii.Error, InvalidSignature):
        signature_block = passport.get("signature") if isinstance(passport, dict) else None
        claimed = signature_block.get("key_id") if isinstance(signature_block, dict) else None
        reason = (f"signed with a different key ({claimed})" if claimed and claimed != _key_id(public)
                  else "the content no longer matches its signature")
        return {
            "status": "TAMPERED",
            "summary": "Tampered: do not trust any field in this passport.",
            "steps": [
                _step("Signature", False, f"Invalid: {reason}."),
                _step("In date", None, "Not checked: the content can't be trusted."),
                _step("Code unchanged", None, "Not checked: the content can't be trusted."),
            ],
        }

    steps = [_step("Signature", True, f"Valid Ed25519 signature from key {_key_id(public)}.")]
    expires = date.fromisoformat(payload["expires_on"])
    in_date = today <= expires
    steps.append(_step("In date", in_date, f"{'Expires' if in_date else 'Expired'} on {expires.isoformat()}."))

    certified = payload["asset"]["commit"]
    if current_commit is None:
        unchanged = True
        steps.append(_step("Code unchanged", None, "Not checked: no current commit given."))
    else:
        unchanged = current_commit == certified
        detail = (f"Repo is still at the certified commit {certified[:7]}." if unchanged
                  else f"Repo moved from certified {certified[:7]} to {current_commit[:7]}.")
        steps.append(_step("Code unchanged", unchanged, detail))

    if not in_date:
        status, summary = "EXPIRED", f"Expired on {expires.isoformat()}: re-certification required."
    elif not unchanged:
        status, summary = "SUSPENDED", "Suspended: the code changed after certification. Re-certify before reuse."
    else:
        status, summary = "VALID", "Valid: issued by this marketplace, unaltered, in date, and matching the certified code."
    return {"status": status, "summary": summary, "steps": steps}


def main() -> None:
    if sys.argv[1:] != ["keygen"]:
        sys.exit("usage: python -m reuse_router.passport keygen")
    seed = os.urandom(32)
    public = Ed25519PrivateKey.from_private_bytes(seed).public_key()
    print(f"{KEY_ENV}={base64.b64encode(seed).decode()}")
    print(f"# public key id: {_key_id(public)}  (keep the value above secret)")


if __name__ == "__main__":
    main()
