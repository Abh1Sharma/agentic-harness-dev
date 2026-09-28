import pytest

from reuse_router.models import NoulAnswer
from reuse_router.policy import Policy, evaluate
from tests.helpers import POLICY, choice, make_answers, score


def test_complete_low_risk_new_tool_is_ready_for_factory():
    verdict = evaluate(make_answers(), POLICY)
    assert (verdict.route, verdict.status, verdict.reviews) == ("BUILD", "READY_FOR_FACTORY", [])


@pytest.mark.parametrize(("fit", "route"), [(2.5, "REUSE"), (2.49, "EXTEND"), (1.5, "EXTEND"), (1.49, "BUILD")])
def test_route_boundaries_are_inclusive(fit, route):
    answers = make_answers(catalog_match=choice("emma", 0.9), reuse_fit=score(fit))
    assert evaluate(answers, POLICY).route == route


def test_reuse_wins_over_everything_else():
    answers = make_answers(catalog_match=choice("emma", 0.9), reuse_fit=score(2.9), has_acceptance=NoulAnswer(0.1))
    assert evaluate(answers, POLICY).status == "REUSE_EXISTING"


def test_uncertain_match_builds_and_warns():
    verdict = evaluate(make_answers(catalog_match=choice("emma", 0.4), reuse_fit=score(2.9)), POLICY)
    assert verdict.route == "BUILD"
    assert verdict.matched_tool == "emma"
    assert any("architect" in warning for warning in verdict.warnings)


def test_model_risk_blocks_handoff():
    verdict = evaluate(make_answers(model_risk=NoulAnswer(0.8)), POLICY)
    assert verdict.status == "NEEDS_REVIEW"
    assert verdict.blocking_reviews == ["model_risk"]


def test_privacy_review_does_not_block():
    verdict = evaluate(make_answers(client_data=NoulAnswer(0.9)), POLICY)
    assert verdict.reviews == ["privacy"]
    assert verdict.status == "READY_FOR_FACTORY"


def test_sensitive_data_class_alone_triggers_privacy():
    verdict = evaluate(make_answers(data_class=choice("confidential", 0.8)), POLICY)
    assert "privacy" in verdict.reviews


def test_extending_a_tool_beyond_its_data_approval_triggers_privacy():
    # Emma is approved up to confidential; restricted data exceeds that. client_data stays low
    # so only the approval check can trigger the review.
    answers = make_answers(
        catalog_match=choice("emma", 0.9), reuse_fit=score(2.0), data_class=choice("restricted", 0.6)
    )
    policy = Policy(**{**POLICY.to_dict(), "sensitive_classes": ()})
    verdict = evaluate(answers, policy)
    assert "privacy" in verdict.reviews
    assert any("approved up to confidential" in warning for warning in verdict.warnings)


def test_missing_elements_need_clarification_in_contract_order():
    verdict = evaluate(make_answers(has_users=NoulAnswer(0.2), has_inputs=NoulAnswer(0.3)), POLICY)
    assert verdict.status == "NEEDS_CLARIFICATION"
    assert verdict.missing_elements == ["has_inputs", "has_users"]


def test_trace_shows_the_numbers_behind_each_rule():
    verdict = evaluate(make_answers(client_data=NoulAnswer(0.91)), POLICY)
    privacy = next(step for step in verdict.trace if step.step == "Privacy review")
    assert "client_data 0.91 ≥ 0.50" in privacy.because
    assert [step.step for step in verdict.trace][-1] == "Status"


def test_lowering_a_cutoff_changes_the_verdict_without_new_answers():
    answers = make_answers(model_risk=NoulAnswer(0.4))
    assert evaluate(answers, POLICY).status == "READY_FOR_FACTORY"
    assert evaluate(answers, POLICY.with_overrides({"review_min_p": 0.3})).status == "NEEDS_REVIEW"


def test_overrides_reject_unknown_cutoffs():
    with pytest.raises(ValueError, match="bogus"):
        POLICY.with_overrides({"bogus": 1})


def test_policy_loads_from_config_and_version_tracks_cutoffs():
    policy = Policy.load()
    assert policy.review_min_p == 0.5
    assert policy.version() != policy.with_overrides({"review_min_p": 0.4}).version()
