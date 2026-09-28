"""Domain types shared by the engine, policy, template and server.

These are our own types, not the TypeSafe SDK's. The engine converts SDK responses
into them, so nothing outside engine.py depends on the vendor library (SPEC §4.5).
"""

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class Request:
    description: str
    title: str = ""
    team: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class NoulAnswer:
    """Yes/no: `p` is the probability of yes."""

    p: float
    type: Literal["noul"] = "noul"


@dataclass(frozen=True)
class ChoiceAnswer:
    label: str
    confidence: float
    probabilities: dict[str, float]
    type: Literal["choice"] = "choice"


@dataclass(frozen=True)
class ScoreAnswer:
    """`score` is the probability-weighted level, so it can fall between integers."""

    score: float
    confidence: float
    probabilities: dict[int, float]
    type: Literal["score"] = "score"


Answer = NoulAnswer | ChoiceAnswer | ScoreAnswer
Answers = dict[str, Answer]


def answer_to_dict(answer: Answer) -> dict:
    return asdict(answer)


def answer_from_dict(data: dict) -> Answer:
    match data["type"]:
        case "noul":
            return NoulAnswer(p=float(data["p"]))
        case "choice":
            return ChoiceAnswer(
                label=data["label"],
                confidence=float(data["confidence"]),
                probabilities={k: float(v) for k, v in data["probabilities"].items()},
            )
        case "score":
            return ScoreAnswer(
                score=float(data["score"]),
                confidence=float(data["confidence"]),
                # JSON object keys are strings; score levels are integers.
                probabilities={int(k): float(v) for k, v in data["probabilities"].items()},
            )
    raise ValueError(f"Unknown answer type: {data['type']!r}")


def answers_to_dict(answers: Answers) -> dict:
    return {name: answer_to_dict(answer) for name, answer in answers.items()}


def answers_from_dict(data: dict) -> Answers:
    return {name: answer_from_dict(raw) for name, raw in data.items()}


@dataclass(frozen=True)
class EngineResult:
    answers: Answers
    mode: str
    model: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
