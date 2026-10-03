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

_UNLABELLED_CHOICE_CUE = re.compile(
    r"\b(?:which\s+of\s+the\s+following|which\s+(?:option|answer|choice)\s+is|"
    r"choose\s+(?:the|a|an|one)|"
    r"select\s+(?:the|a|an|one)|pick\s+(?:the|a|an|one)|"
    r"what\s+is\s+the\s+(?:correct|output|result|value))\b",
    re.IGNORECASE,
)


def _strip_unlabelled_marker(line: str) -> str:
    return re.sub(r"^[ \t]*(?:[-*•◦○◯◉●▪▫□☐]\s*)", "", line).strip()


def _option_after_question(line: str) -> str:
    """Return an option OCR/copying placed after the question on one line."""
    if "?" not in line:
        return ""
    suffix = line.rsplit("?", 1)[1].strip()
    # A Markdown question often closes bold text immediately after the `?`.
    suffix = re.sub(r"^(?:\*\*|__)[ \t]*", "", suffix).strip()
    return _strip_unlabelled_marker(suffix)


def _parse_unlabelled_choice_options(text: str) -> dict[str, str]:
    lines = [line.strip() for line in normalize_choice_text(text).splitlines() if line.strip()]
    if len(lines) < 3:
        return {}
    cue_index = next(
        (index for index, line in enumerate(lines) if _UNLABELLED_CHOICE_CUE.search(line)),
        None,
    )
    if cue_index is None:
        if len(lines) >= 3 and {
            _strip_unlabelled_marker(value).strip(" .:;()[]").casefold()
            for value in lines[-2:]
        } == {"true", "false"}:
            candidates = lines[-2:]
        else:
            return {}
    else:
        candidates = lines[cue_index + 1:]
        first_option = _option_after_question(lines[cue_index])
        if first_option:
            candidates.insert(0, first_option)
    cleaned = [_strip_unlabelled_marker(line) for line in candidates]
    if any(not option for option in cleaned):
        return {}
    normalized_values = {option.strip(" .:;()[]").casefold() for option in cleaned}
    # Ordered exam questions use four choices. Requiring all four prevents a
    # missed OCR row from shifting the remaining choices to the wrong letter.
    if len(cleaned) != 4 and not (len(cleaned) == 2 and normalized_values == {"true", "false"}):
        return {}
    return dict(zip("ABCD", cleaned))


def parse_choice_options(text: str) -> dict[str, str]:
    options = {}
    for parenthesized, punctuated, answer in _CHOICE_LINE.findall(normalize_choice_text(text)):
        label = (parenthesized or punctuated).upper()
        options[label] = answer.strip().rstrip("\\").strip()
    return options or _parse_unlabelled_choice_options(text)


def classify_question(text: str) -> Classification:
    normalized = text.strip()
    lowered = normalized.lower()
    if not normalized:
        return Classification(TaskType.UNKNOWN)

    if len(parse_choice_options(normalized)) >= 2:
        task_type = TaskType.MCQ
    elif re.search(r"\b(?:true\s*(?:or|/)\s*false|true\s+false|t\s*/\s*f)\b", lowered):
        task_type = TaskType.TRUE_FALSE
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
