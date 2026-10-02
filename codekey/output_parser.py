import re

from codekey.exceptions import OutputValidationError


_FENCE = re.compile(r"```(?:[\w+#.-]+)?\s*\n?(.*?)```", re.DOTALL)
_INTRO = re.compile(
    r"^(?:here(?:'s| is) (?:the )?(?:code|solution)|certainly[,!]?)\s*:?\s*$",
    re.IGNORECASE,
)


def clean_model_output(raw_output: str, language: str = "python") -> str:
    if not isinstance(raw_output, str) or not raw_output.strip():
        raise OutputValidationError("The model returned an empty response.")

    fenced_blocks = _FENCE.findall(raw_output)
    if fenced_blocks:
        cleaned = max(fenced_blocks, key=len).strip()
    else:
        cleaned = re.sub(r"^\s*```(?:[\w+#.-]+)?\s*", "", raw_output.strip())
        cleaned = re.sub(r"\s*```\s*$", "", cleaned).strip()

    lines = cleaned.splitlines()
    while lines and (not lines[0].strip() or _INTRO.match(lines[0].strip())):
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    cleaned = "\n".join(lines).strip()
    if not cleaned:
        raise OutputValidationError("The model response did not contain usable code.")

    if language == "python":
        try:
            compile(cleaned, "<codekey-output>", "exec")
        except SyntaxError as error:
            raise OutputValidationError(
                f"The generated Python has a syntax error on line {error.lineno}."
            ) from error
    return cleaned
