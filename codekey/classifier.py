import html
import re
from dataclasses import dataclass
from enum import Enum


class TaskType(str, Enum):
    CODING_PROBLEM = "CODING_PROBLEM"
    MCQ = "MCQ"
    TRUE_FALSE = "TRUE_FALSE"
    DEBUG = "DEBUG"
    EXPLAIN_CODE = "EXPLAIN_CODE"
    OPTIMIZE_CODE = "OPTIMIZE_CODE"
    UNKNOWN = "UNKNOWN"
    GENERAL = "GENERAL"


@dataclass(frozen=True)
class Classification:
    task_type: TaskType


def normalize_choice_text(text: str) -> str:
    normalized = html.unescape(text.strip()).replace("\\\n", "\n")
    normalized = normalized.translate(str.maketrans("ⒶⒷⒸⒹⓐⓑⓒⓓ", "A B C D a b c d".replace(" ", "")))
    normalized = re.sub(r"\\[ \t]*(?=[A-D][.)])", "\n", normalized)
    normalized = re.sub(r"\\[ \t]*(?=\n|$)", "", normalized)
    # OCR may put a circled option letter on a separate line from its answer.
    normalized = re.sub(r"(?m)^[ \t]*([A-D])[ \t]*\n(?=[ \t]*\S)", r"\1. ", normalized)
    return normalized


_CHOICE_LINE = re.compile(
    r"(?m)^[ \t]*(?:[-*][ \t]*)?(?:\(([A-D])\)|([A-D])[.):]?)[ \t]+(.+?)[ \t]*$",
    re.IGNORECASE,
)


def parse_choice_options(text: str) -> dict[str, str]:
    options = {}
    for parenthesized, punctuated, answer in _CHOICE_LINE.findall(normalize_choice_text(text)):
        label = (parenthesized or punctuated).upper()
        options[label] = answer.strip().rstrip("\\").strip()
    return options


def classify_question(text: str) -> Classification:
    normalized = text.strip()
    lowered = normalized.lower()
    if not normalized:
        return Classification(TaskType.UNKNOWN)

    if re.search(r"\b(?:true\s*(?:or|/)\s*false|true\s+false|t\s*/\s*f)\b", lowered):
        task_type = TaskType.TRUE_FALSE
    elif len(parse_choice_options(normalized)) >= 2:
        task_type = TaskType.MCQ
    elif re.search(r"\b(?:indexerror|traceback|exception|error|bug|not working|wrong output|fix this)\b", lowered):
        task_type = TaskType.DEBUG
    elif re.search(r"\b(?:explain|what does|how does)\b", lowered) and re.search(
        r"\b(?:code|program|function|snippet)\b", lowered
    ):
        task_type = TaskType.EXPLAIN_CODE
    elif re.search(r"\b(?:optimize|improve the performance|make .* faster|time complexity)\b", lowered):
        task_type = TaskType.OPTIMIZE_CODE
    elif (
        re.search(r"\b(?:wap|write a program|write code|write a function|create a program|implement a function|implement an algorithm)\b", lowered)
        or re.search(r"\b(?:write|create|implement|build|develop)\b.{0,35}\b(?:code|program|script|function|algorithm)\b", lowered)
        or re.search(r"\b(?:write|create|implement|build|develop)\b.{0,35}\b(?:python|java|javascript|typescript|ruby|rust|kotlin|swift)\b", lowered)
        or re.search(r"\b(?:print|reverse|sort)\b.{0,35}\b(?:number|array|list|string|pattern)\b", lowered)
        or "```" in normalized
    ):
        task_type = TaskType.CODING_PROBLEM
    else:
        task_type = TaskType.GENERAL
    return Classification(task_type)
