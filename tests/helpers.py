from reuse_router.models import Answers, ChoiceAnswer, NoulAnswer, ScoreAnswer
from reuse_router.policy import Policy

POLICY = Policy(
    match_min_confidence=0.55,
    reuse_min_fit=2.5,
    extend_min_fit=1.5,
    review_min_p=0.5,
    ready_min_score=2.0,
    element_min_p=0.5,
)


def choice(label: str, confidence: float) -> ChoiceAnswer:
    return ChoiceAnswer(label=label, confidence=confidence, probabilities={label: confidence})


def score(value: float) -> ScoreAnswer:
    return ScoreAnswer(score=value, confidence=0.8, probabilities={round(value): 0.8})


def make_answers(**overrides) -> Answers:
    """A complete, low-risk, fully specified BUILD request; override single answers per test."""
    answers: Answers = {
        "catalog_match": choice("none", 0.9),
        "reuse_fit": score(0.2),
        "data_class": choice("internal", 0.9),
        "client_data": NoulAnswer(0.05),
        "model_risk": NoulAnswer(0.05),
        "external_transfer": NoulAnswer(0.05),
        "spec_readiness": score(2.8),
        "has_inputs": NoulAnswer(0.9),
        "has_outputs": NoulAnswer(0.9),
        "has_users": NoulAnswer(0.9),
        "has_acceptance": NoulAnswer(0.9),
    }
    answers.update(overrides)
    return answers
