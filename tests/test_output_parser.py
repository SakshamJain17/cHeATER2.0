import pytest

from codekey.exceptions import OutputValidationError
from codekey.output_parser import clean_model_output


def test_strips_markdown_fence_and_introductory_line():
    output = "Here is the solution:\n```python\nprint('hello')\n```"
    assert clean_model_output(output) == "print('hello')"


def test_accepts_plain_code_and_validates_python_syntax():
    assert clean_model_output("for value in range(3):\n    print(value)").startswith("for")
    with pytest.raises(OutputValidationError, match="syntax error"):
        clean_model_output("if True print('no')")


def test_rejects_empty_response():
    with pytest.raises(OutputValidationError, match="empty"):
        clean_model_output("  ")
