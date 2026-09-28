"""Decision engines: the only module that talks to the TypeSafe SDK (SPEC §4.5, §8).

Every engine exposes `decide(state, questions) -> EngineResult`, so the pipeline never
knows which one it is using:

- LiveEngine    calls Jev and saves each response to data/recordings/.
- ReplayEngine  serves saved responses; fails loudly on a request it has not seen.
- SimEngine     keyword rules for offline tests (see sim.py). Not a model.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from reuse_router.models import (
    Answers,
    ChoiceAnswer,
    EngineResult,
    NoulAnswer,
    ScoreAnswer,
    answers_from_dict,
    answers_to_dict,
)
from reuse_router.paths import DATA_DIR, runtime_dir

# Replay reads committed recordings; live mode writes wherever runtime files may go.
RECORDINGS_DIR = DATA_DIR / "recordings"
LIVE_RECORDINGS_DIR = runtime_dir() / "recordings"
DEFAULT_MODEL = "jev-latest"


class EngineError(RuntimeError):
    """A failure the UI can show as-is: the message says what to do next."""


class Engine(Protocol):
    mode: str

    def decide(self, state: dict, questions: dict[str, dict]) -> EngineResult: ...


def requested_model() -> str:
    return os.environ.get("TYPESAFE_DEFAULT_MODEL", "").strip() or DEFAULT_MODEL


def recording_key(state: dict, questions: dict[str, dict], model: str) -> str:
    """Stable hash of exactly what was asked, so a replay matches only an identical request."""
    canonical = json.dumps({"state": state, "questions": questions, "model": model}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _check_complete(answers: Answers, questions: dict[str, dict]) -> None:
    missing = set(questions) - set(answers)
    if missing:
        raise EngineError(f"Jev returned no answer for: {', '.join(sorted(missing))}")


class LiveEngine:
    mode = "live"

    def __init__(self, recordings_dir: Path = LIVE_RECORDINGS_DIR, client=None):
        # Imported here so sim and replay modes work even if the SDK is broken or absent.
        from typesafe_sdk import TypeSafeClient, TypeSafeError

        self._error_type = TypeSafeError
        self._model = requested_model()
        try:
            self._client = client or TypeSafeClient(model=self._model)
        except TypeSafeError as error:
            raise EngineError(f"{error} Set TYPESAFE_API_KEY, or run with JEV_MODE=sim.") from error
        self._recordings_dir = recordings_dir

    def decide(self, state: dict, questions: dict[str, dict]) -> EngineResult:
        start = time.perf_counter()
        try:
            response = self._client.system_one(state=state, questions=questions)
        except self._error_type as error:
            raise EngineError(
                f"Jev call failed: {error}. If api.typesafe.ai is blocked on this network, "
                "record on another network and run with JEV_MODE=replay."
            ) from error
        latency_ms = (time.perf_counter() - start) * 1000

        result = EngineResult(
            answers=self._convert(response.answers),
            mode=self.mode,
            model=response.model,
            latency_ms=round(latency_ms, 1),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        _check_complete(result.answers, questions)
        self._record(state, questions, result)
        return result

    @staticmethod
    def _convert(sdk_answers: dict) -> Answers:
        from typesafe_sdk import ChoiceAnswer as SdkChoice
        from typesafe_sdk import NoulAnswer as SdkNoul
        from typesafe_sdk import ScoreAnswer as SdkScore

        answers: Answers = {}
        for name, answer in sdk_answers.items():
            if isinstance(answer, SdkNoul):
                answers[name] = NoulAnswer(p=answer.noul)
            elif isinstance(answer, SdkChoice):
                answers[name] = ChoiceAnswer(answer.choice, answer.confidence, dict(answer.probabilities))
            elif isinstance(answer, SdkScore):
                answers[name] = ScoreAnswer(answer.score, answer.confidence, dict(answer.probabilities))
        return answers

    def _record(self, state: dict, questions: dict[str, dict], result: EngineResult) -> None:
        self._recordings_dir.mkdir(parents=True, exist_ok=True)
        key = recording_key(state, questions, self._model)
        recording = {
            "key": key,
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "requested_model": self._model,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "state": state,
            "questions": questions,
            "answers": answers_to_dict(result.answers),
        }
        (self._recordings_dir / f"{key}.json").write_text(json.dumps(recording, indent=2))


class ReplayEngine:
    mode = "replay"

    def __init__(self, recordings_dir: Path = RECORDINGS_DIR):
        self._recordings_dir = recordings_dir
        self._model = requested_model()

    def decide(self, state: dict, questions: dict[str, dict]) -> EngineResult:
        key = recording_key(state, questions, self._model)
        path = self._recordings_dir / f"{key}.json"
        if not path.exists():
            raise EngineError(
                "No recording for this exact request. Replay mode only serves requests "
                "previously run in live mode, with identical text, catalog and questions."
            )
        recording = json.loads(path.read_text())
        # Latency is the original live latency; the replay itself takes no time.
        return EngineResult(
            answers=answers_from_dict(recording["answers"]),
            mode=self.mode,
            model=recording["model"],
            latency_ms=recording["latency_ms"],
            input_tokens=recording["input_tokens"],
            output_tokens=recording["output_tokens"],
        )


def resolve_mode(mode: str | None = None) -> str:
    mode = (mode or os.environ.get("JEV_MODE", "")).strip().lower()
    if not mode:
        mode = "live" if os.environ.get("TYPESAFE_API_KEY", "").strip() else "sim"
    if mode not in {"live", "replay", "sim"}:
        raise EngineError(f"Unknown JEV_MODE {mode!r}: use live, replay or sim.")
    return mode


def make_engine(mode: str | None = None) -> Engine:
    match resolve_mode(mode):
        case "live":
            return LiveEngine()
        case "replay":
            return ReplayEngine()
        case _:
            from reuse_router.sim import SimEngine

            return SimEngine()
