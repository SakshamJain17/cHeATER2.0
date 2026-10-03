import ast
import re
from dataclasses import dataclass

from codekey.classifier import Classification, TaskType, classify_question, normalize_choice_text, parse_choice_options
from codekey.config import GenerationConfig
from codekey.exceptions import CodeKeyError, OutputValidationError
from codekey.local_model import LocalModelClient
from codekey.output_parser import clean_model_output


SYSTEM_PROMPT = """You are a careful question-answering assistant. Answer the actual question directly and accurately.
For programming tasks, use the language requested by the user. If none is requested, use Python.
For basic or intermediate Python program questions, write a complete runnable script using straightforward statements, input(), loops, and print() as needed. Do not wrap the whole answer in def or class unless the question asks for a function or class. If you use a function for a program, call it from top-level code.
For programming tasks in code-only mode, return only the requested code, without Markdown fences or commentary.
For multiple choice questions, return only one option label (A, B, C, or D).
For questions that allow multiple correct choices, return every correct option label in alphabetical order, separated by commas.
For true/false questions, return only True or False.
For non-programming questions, answer in plain natural language, never as print(...) or code. If a word, name, number, or short phrase fully answers the question, output only that value on one line. Otherwise use the shortest sufficient answer, unless the user explicitly asks for detail. Use the user's language.
Do not invent facts or claim certainty when the question is subjective or ambiguous."""


_LANGUAGE_PATTERNS = (
    ("c++", r"(?<!\w)c\+\+(?!\w)|\bcpp\b"),
    ("c#", r"(?<!\w)c#(?!\w)"),
    ("javascript", r"\bjavascript\b|\bjs\b"),
    ("typescript", r"\btypescript\b"),
    ("java", r"\bjava\b"),
    ("python", r"\bpython\b"),
    ("c", r"\bc\b"),
    ("rust", r"\brust\b"),
    ("go", r"\bgolang\b|\bgo\b"),
    ("ruby", r"\bruby\b"),
    ("php", r"\bphp\b"),
    ("swift", r"\bswift\b"),
    ("kotlin", r"\bkotlin\b"),
)


def requested_language(question: str) -> str:
    for language, pattern in _LANGUAGE_PATTERNS:
        if re.search(r"\b(?:in|using|with)\s+" + pattern, question, re.IGNORECASE):
            return language
        if re.search(pattern + r"\s+(?:program|code|solution|function)", question, re.IGNORECASE):
            return language
    return "python"


def _needs_runnable_script(question: str, language: str) -> bool:
    if language != "python":
        return False
    if not re.search(r"\b(?:program|wap|script)\b", question, re.IGNORECASE):
        return False
    return not re.search(r"\b(?:write|define|implement|create)\s+(?:a |an )?(?:function|class)\b", question, re.IGNORECASE)


def _is_function_only(code: str) -> bool:
    tree = ast.parse(code)
    declarations = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for node in tree.body) and all(
        isinstance(node, declarations) for node in tree.body
    )


def _plain_text_answer(raw: str, question: str) -> str:
    answer = raw.strip()
    match = re.fullmatch(r"(?:```(?:python)?\s*)?(print\s*\(.*\))(?:\s*```)?", answer, re.DOTALL | re.IGNORECASE)
    if match:
        try:
            expression = ast.parse(match.group(1), mode="eval").body
            if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name) and expression.func.id == "print" and not expression.keywords:
                values = [ast.literal_eval(arg) for arg in expression.args]
                answer = " ".join(str(value) for value in values).strip()
        except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError):
            pass
    if re.match(r"^(?:```|print\s*\(|def\s+|class\s+|import\s+|from\s+)", answer):
        raise OutputValidationError("Expected a plain text answer, not code.")
    if not answer:
        raise OutputValidationError("The model returned an empty answer.")
    if not re.search(r"\b(?:long|detailed|in detail|thoroughly)\b", question, re.IGNORECASE):
        answer = " ".join(answer.split())
    answer = re.sub(r"^(?:the\s+)?answer\s*(?:is|:)\s*", "", answer, flags=re.IGNORECASE).strip()
    if re.search(r"\b(?:one[- ]word|single[- ]word)\b", question, re.IGNORECASE):
        word = re.search(r"[^\W_]+(?:[-'][^\W_]+)*", answer, re.UNICODE)
        if word:
            return word.group()
    return answer


def _parse_mcq_answer(raw: str, options: dict[str, str]) -> str:
    answer = raw.strip().strip("`* ").strip()
    exact = re.fullmatch(r"(?:option|choice)?\s*\(?([A-D])\)?[.):]?", answer, re.IGNORECASE)
    if exact and exact.group(1).upper() in options:
        return exact.group(1).upper()
    declared = re.findall(
        r"\b(?:correct\s+)?(?:answer|option|choice)\s*(?:is|:|=|-)?\s*\(?([A-D])\)?\b",
        answer, re.IGNORECASE,
    )
    declared = {label.upper() for label in declared if label.upper() in options}
    if len(declared) == 1:
        return declared.pop()
    leading = re.match(r"^\(?([A-D])\)?[.):]\s+", answer, re.IGNORECASE)
    if leading and leading.group(1).upper() in options:
        return leading.group(1).upper()
    normalized_answer = re.sub(r"^[\s\W]*(?:the\s+)?(?:correct\s+)?(?:answer|option|choice)\s*(?:is|:)?\s*", "", answer, flags=re.IGNORECASE)
    normalized_answer = normalized_answer.strip(" .:;\"'`*\n\t").casefold()
    matches = {label for label, value in options.items() if normalized_answer == value.strip(" .:;\"'`*\n\t").casefold()}
    if len(matches) == 1:
        return matches.pop()
    # A short explanation can name the option text instead of its label.
    if len(answer) <= 200:
        mentioned = {
            label for label, value in options.items()
            if len(value.strip()) >= 3 and re.search(r"(?<!\w)" + re.escape(value.strip()) + r"(?!\w)", answer, re.IGNORECASE)
        }
        if len(mentioned) == 1:
            return mentioned.pop()
    raise CodeKeyError("The model did not identify one MCQ option clearly.")


def _parse_multi_select_answer(raw: str, options: dict[str, str]) -> str:
    answer = raw.strip().strip("`* ").strip()
    stripped = re.sub(
        r"^(?:the\s+)?(?:correct\s+)?(?:answers?|options?|choices?)\s*(?:are|is|:|=|-)*\s*",
        "",
        answer,
        flags=re.IGNORECASE,
    ).strip().rstrip(".")
    stripped = re.sub(r"\b(?:and|or)\b", ",", stripped, flags=re.IGNORECASE)
    if not re.fullmatch(r"[()A-Da-d,;&/+\s]+", stripped):
        raise CodeKeyError("The model did not identify multiple choices clearly.")
    labels = {label.upper() for label in re.findall(r"(?<![A-Za-z])([A-Da-d])(?![A-Za-z])", stripped)}
    if not labels:
        compact = re.sub(r"[^A-Da-d]", "", stripped).upper()
        labels = set(compact) if compact and len(compact) <= len(options) else set()
    if not labels or not labels.issubset(options):
        raise CodeKeyError("The model did not identify multiple choices clearly.")
    return ",".join(sorted(labels))


@dataclass(frozen=True)
class SolveResult:
    code: str
    classification: Classification
    language: str
    choice_options: dict[str, str] | None = None


class Solver:
    def __init__(self, client: LocalModelClient, generation: GenerationConfig, max_output_chars: int):
        self.client = client
        self.generation = generation
        self.max_output_chars = max_output_chars

    def solve(self, question: str) -> SolveResult:
        classification = classify_question(question)
        if classification.task_type is TaskType.UNKNOWN:
            raise CodeKeyError("Question is empty.")
        programming = classification.task_type in {
            TaskType.CODING_PROBLEM, TaskType.DEBUG, TaskType.OPTIMIZE_CODE,
        }
        language = requested_language(question) if programming else ""
        self.client.ensure_ready()
        model_question = normalize_choice_text(question) if classification.task_type in {
            TaskType.MCQ, TaskType.MULTI_SELECT,
        } else question.strip()
        prompt = (
            f"Task type: {classification.task_type.value}\n"
            f"Programming language: {language or 'not applicable'}\n"
            f"Output mode: {self.generation.output_mode}\n"
            f"Answer style: {'code' if programming else 'one line; one word if sufficient, unless a long answer is requested'}\n\n"
            f"User request:\n{model_question}"
        )
        raw = self.client.generate(SYSTEM_PROMPT, prompt, self.generation.temperature)
        choice_options = None
        if len(raw) > self.max_output_chars:
            raise CodeKeyError("Generated output exceeds the configured size limit.")
        if programming and self.generation.output_mode == "code_only":
            try:
                answer = clean_model_output(raw, language)
                if _needs_runnable_script(question, language) and _is_function_only(answer):
                    raise OutputValidationError("Program needs a top-level call or statements.")
            except OutputValidationError:
                repair_prompt = (
                    f"Rewrite this as a complete runnable {language} solution with correct indentation and no Markdown. "
                    "For a Python program, prefer simple top-level statements and print the result. "
                    "Do not return only an uncalled def or class.\n\n"
                    f"Task:\n{question.strip()}\n\nDraft:\n{raw}"
                )
                repaired = self.client.generate(SYSTEM_PROMPT, repair_prompt, self.generation.temperature)
                if len(repaired) > self.max_output_chars:
                    raise CodeKeyError("Generated output exceeds the configured size limit.")
                answer = clean_model_output(repaired, language)
                if _needs_runnable_script(question, language) and _is_function_only(answer):
                    raise OutputValidationError("The model returned only an uncalled function or class.")
        elif classification.task_type is TaskType.MCQ:
            options = parse_choice_options(question)
            choice_options = options
            try:
                answer = _parse_mcq_answer(raw, options)
            except CodeKeyError:
                choices = "\n".join(f"{label}. {options[label]}" for label in sorted(options))
                retry_prompt = (
                    "Choose the correct option by its written letter, regardless of display order. "
                    "Reply with exactly one letter: A, B, C, or D.\n\n"
                    f"Question:\n{model_question}\n\nChoices:\n{choices}"
                )
                retried = self.client.generate(SYSTEM_PROMPT, retry_prompt, self.generation.temperature)
                if len(retried) > self.max_output_chars:
                    raise CodeKeyError("Generated output exceeds the configured size limit.")
                answer = _parse_mcq_answer(retried, options)
        elif classification.task_type is TaskType.MULTI_SELECT:
            options = parse_choice_options(question)
            choice_options = options
            try:
                answer = _parse_multi_select_answer(raw, options)
            except CodeKeyError:
                choices = "\n".join(f"{label}. {options[label]}" for label in sorted(options))
                retry_prompt = (
                    "Select every correct choice. Reply with only the written option letters in alphabetical "
                    "order, separated by commas, such as A,C.\n\n"
                    f"Question:\n{model_question}\n\nChoices:\n{choices}"
                )
                retried = self.client.generate(SYSTEM_PROMPT, retry_prompt, self.generation.temperature)
                if len(retried) > self.max_output_chars:
                    raise CodeKeyError("Generated output exceeds the configured size limit.")
                answer = _parse_multi_select_answer(retried, options)
        elif classification.task_type is TaskType.TRUE_FALSE:
            answer = raw.strip().rstrip(".").lower()
            if answer not in {"true", "false"}:
                raise CodeKeyError("The model did not return True or False.")
            answer = answer.capitalize()
        else:
            try:
                answer = _plain_text_answer(raw, question)
            except OutputValidationError:
                repair_prompt = (
                    "Answer this question in plain natural language, with no Python, print(), or code fences. "
                    "Use one or two short sentences unless a detailed answer was requested.\n\n"
                    f"Question:\n{question.strip()}\n\nDraft:\n{raw}"
                )
                repaired = self.client.generate(SYSTEM_PROMPT, repair_prompt, self.generation.temperature)
                if len(repaired) > self.max_output_chars:
                    raise CodeKeyError("Generated output exceeds the configured size limit.")
                answer = _plain_text_answer(repaired, question)
        return SolveResult(answer, classification, language, choice_options)
