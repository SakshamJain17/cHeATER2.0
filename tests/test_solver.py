from codekey.classifier import TaskType
from codekey.config import GenerationConfig
from codekey.solver import Solver


class FakeClient:
    def __init__(self, response: str):
        self.response = response
        self.ready = False

    def ensure_ready(self):
        self.ready = True

    def generate(self, system_prompt: str, prompt: str, temperature: float) -> str:
        assert "Programming language:" in prompt
        assert "language requested by the user" in system_prompt
        assert temperature == 0.1
        return self.response


def test_solver_checks_model_and_returns_clean_code():
    client = FakeClient("```python\nn = int(input())\nprint(n * 2)\n```")
    solver = Solver(client, GenerationConfig(0.1, "code_only"), 1000)
    result = solver.solve("WAP in Python to double a number")
    assert client.ready
    assert result.classification.task_type is TaskType.CODING_PROBLEM
    assert result.code == "n = int(input())\nprint(n * 2)"


def test_solver_returns_mcq_answer():
    client = FakeClient("B")
    solver = Solver(client, GenerationConfig(0.1, "code_only"), 1000)
    result = solver.solve("Which of the following is correct?\nA. One\nB. Two")
    assert result.classification.task_type is TaskType.MCQ
    assert result.code == "B"


def test_solver_returns_true_false_answer():
    client = FakeClient("True")
    solver = Solver(client, GenerationConfig(0.1, "code_only"), 1000)
    result = solver.solve("True or false: Python supports functions?")
    assert result.classification.task_type is TaskType.TRUE_FALSE
    assert result.code == "True"


def test_explicit_cpp_request_produces_cpp():
    client = FakeClient("```cpp\n#include <iostream>\nint main() { std::cout << 1; }\n```")
    solver = Solver(client, GenerationConfig(0.1, "code_only"), 1000)
    result = solver.solve("Write a C++ program to sort an array")
    assert result.language == "c++"
    assert result.code.startswith("#include <iostream>")


def test_general_question_returns_plain_text():
    client = FakeClient("Shah Rukh Khan is an actor. Whether he is the best is subjective.")
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve(
        "Shahrukhkhan kaisa banda hai? And why is he the best actor."
    )
    assert result.classification.task_type is TaskType.GENERAL
    assert result.code.startswith("Shah Rukh Khan")


def test_python_program_repairs_uncalled_function():
    class SequenceClient(FakeClient):
        def __init__(self):
            self.responses = [
                "def double():\n    print(int(input()) * 2)",
                "n = int(input())\nprint(n * 2)",
            ]
            self.prompts = []

        def generate(self, system_prompt, prompt, temperature):
            self.prompts.append(prompt)
            return self.responses.pop(0)

    client = SequenceClient()
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve(
        "Write a Python program to double a number"
    )
    assert result.code == "n = int(input())\nprint(n * 2)"
    assert len(client.prompts) == 2


def test_explicit_function_request_keeps_definition():
    client = FakeClient("def double(n):\n    return n * 2")
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve(
        "Write a Python function to double a number"
    )
    assert result.code.startswith("def double")


def test_general_print_wrapper_is_unwrapped_to_plain_text():
    client = FakeClient('print("Shah Rukh Khan is a Bollywood actor.")')
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve(
        "Who is Shah Rukh Khan?"
    )
    assert result.classification.task_type is TaskType.GENERAL
    assert result.code == "Shah Rukh Khan is a Bollywood actor."


def test_general_code_answer_gets_repaired():
    class SequenceClient(FakeClient):
        def __init__(self):
            self.responses = ["```python\\nprint(2 + 2)\\n```", "4"]
            self.prompts = []

        def generate(self, system_prompt, prompt, temperature):
            self.prompts.append(prompt)
            return self.responses.pop(0)

    client = SequenceClient()
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve("Calculate 2 + 2.")
    assert result.code == "4"
    assert len(client.prompts) == 2


def test_mcq_maps_option_text_to_letter_in_shuffled_list():
    client = FakeClient("The correct answer is def.")
    question = "Which keyword defines a function?\nC. fun\nD. define\nA. function\nB. def"
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve(question)
    assert result.classification.task_type is TaskType.MCQ
    assert result.code == "B"


def test_mcq_retries_ambiguous_reply_once():
    class SequenceClient(FakeClient):
        def __init__(self):
            self.responses = ["I am uncertain.", "Option B"]
            self.prompts = []
        def generate(self, system_prompt, prompt, temperature):
            self.prompts.append(prompt)
            return self.responses.pop(0)
    client = SequenceClient()
    question = "Which keyword defines a function?\nC. fun\nD. define\nA. function\nB. def"
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve(question)
    assert result.code == "B"
    assert "A. function" in client.prompts[1]
    assert "B. def" in client.prompts[1]
    assert len(client.prompts) == 2


def test_one_word_question_has_no_extra_lines():
    client = FakeClient("Answer: Paris\n")
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve(
        "In one word, what is the capital of France?"
    )
    assert result.code == "Paris"


def test_short_answer_collapses_unrequested_line_breaks():
    client = FakeClient("A list is mutable.\nIt can grow after creation.")
    result = Solver(client, GenerationConfig(0.1, "code_only"), 1000).solve(
        "What is a Python list?"
    )
    assert result.code == "A list is mutable. It can grow after creation."
