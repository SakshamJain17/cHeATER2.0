import logging
import threading
from types import SimpleNamespace

from codekey.app import CodeKeyApp
from codekey.classifier import TaskType
from codekey.config import load_config


def test_programming_answer_is_typed_without_replacing_clipboard(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    writes = []
    typed = []
    typed_event = threading.Event()
    app.clipboard.read_text = lambda: "WAP to print hello"
    app.clipboard.write_text = writes.append
    app.solver.solve = lambda question: SimpleNamespace(
        code='print("hello")',
        classification=SimpleNamespace(task_type=TaskType.CODING_PROBLEM),
    )
    monkeypatch.setattr(
        "codekey.app.type_into_focused_application",
        lambda text, delay, cancel_event, preserve_indentation: typed.append((text, preserve_indentation)) or typed_event.set() or True,
    )

    app.solve_clipboard()
    assert typed == []
    assert writes == []

    app.request_typing()
    assert typed_event.wait(1)

    assert typed == [('print("hello")', True)]
    assert writes == []


def test_typing_request_during_generation_waits_for_answer(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    generation_started = threading.Event()
    finish_generation = threading.Event()
    typed = threading.Event()
    app.clipboard.read_text = lambda: "WAP to print hello"

    def solve(question):
        generation_started.set()
        assert finish_generation.wait(1)
        return SimpleNamespace(
            code='print("hello")',
            classification=SimpleNamespace(task_type=TaskType.CODING_PROBLEM),
        )

    app.solver.solve = solve
    monkeypatch.setattr(
        "codekey.app.type_into_focused_application",
        lambda text, delay, cancel_event, preserve_indentation: typed.set() or True,
    )
    worker = threading.Thread(target=app.solve_clipboard)
    worker.start()
    assert generation_started.wait(1)
    app.request_typing()
    assert not typed.is_set()
    finish_generation.set()
    worker.join(1)
    assert typed.wait(1)


def test_cancel_discards_prepared_answer(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    app.clipboard.read_text = lambda: "WAP to print hello"
    app.solver.solve = lambda question: SimpleNamespace(
        code='print("hello")',
        classification=SimpleNamespace(task_type=TaskType.CODING_PROBLEM),
    )
    typed = []
    monkeypatch.setattr("codekey.app.type_into_focused_application", lambda *args, **kwargs: typed.append((args, kwargs)))
    app.solve_clipboard()
    app.cancel_current()
    app.request_typing()
    assert typed == []


def test_mcq_moves_cursor_on_prepare_hotkey(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    app.clipboard.read_text = lambda: "Question?\nA. Up\nB. Right\nC. Left\nD. Down"
    app.solver.solve = lambda question: SimpleNamespace(
        code="C", classification=SimpleNamespace(task_type=TaskType.MCQ)
    )
    copied = []
    moved = []
    done = threading.Event()
    app.clipboard.write_text = copied.append
    monkeypatch.setattr("codekey.app.move_to_mcq_answer", lambda answer: moved.append(answer) or done.set())
    app.solve_clipboard()
    assert done.wait(1)
    assert copied == ["C"]
    assert moved == ["C"]


def test_true_false_options_move_left_or_right(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    app.clipboard.read_text = lambda: "Python is compiled only.\nA. True\nB. False"

    class Client:
        def ensure_ready(self):
            pass

        def generate(self, system_prompt, prompt, temperature):
            return "False"

    app.solver.client = Client()
    app.clipboard.write_text = lambda text: None
    moved = []
    done = threading.Event()

    def move(answer, horizontal=False):
        moved.append((answer, horizontal))
        done.set()

    monkeypatch.setattr("codekey.app.move_to_mcq_answer", move)
    app.solve_clipboard()
    assert done.wait(1)
    assert moved == [("B", True)]


def test_unlabelled_true_false_moves_without_typing(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    app.clipboard.read_text = lambda: "True or false: Python supports functions?"
    app.solver.solve = lambda question: SimpleNamespace(
        code="True", classification=SimpleNamespace(task_type=TaskType.TRUE_FALSE)
    )
    copied = []
    moved = []
    done = threading.Event()
    app.clipboard.write_text = copied.append
    monkeypatch.setattr(
        "codekey.app.move_to_true_false_answer",
        lambda answer: moved.append(answer) or done.set() or (1, 2),
    )
    monkeypatch.setattr(
        "codekey.app.type_into_focused_application",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("typed instead of moved")),
    )
    app.solve_clipboard()
    assert done.wait(1)
    assert copied == ["True"]
    assert moved == ["True"]


def test_screen_capture_is_sent_to_solver(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    seen = []
    monkeypatch.setattr("codekey.app.read_screen_text", lambda limit: "What is visible?\nA. One\nB. Two")
    app.solver.solve = lambda question: seen.append(question) or SimpleNamespace(
        code="Short answer", classification=SimpleNamespace(task_type=TaskType.GENERAL)
    )
    app.solve_screen()
    assert seen == ["What is visible?\nA. One\nB. Two"]


def test_copied_html_escaped_mcq_moves_cursor_without_typing(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    app.clipboard.read_text = lambda: (
        "**. Which keyword is used to define a function in Python?**\n"
        "A. function\\\n&#x20;B. def\\\n&#x20;C. fun\\\n&#x20;D. define\\\n&#x20;"
    )
    class Client:
        def ensure_ready(self):
            pass
        def generate(self, system_prompt, prompt, temperature):
            assert "&#x20;" not in prompt
            assert "B. def" in prompt
            return "B"
    app.solver.client = Client()
    copied = []
    moved = []
    done = threading.Event()
    app.clipboard.write_text = copied.append
    monkeypatch.setattr("codekey.app.move_to_mcq_answer", lambda answer: moved.append(answer) or done.set())
    monkeypatch.setattr("codekey.app.type_into_focused_application", lambda *args: (_ for _ in ()).throw(AssertionError("typed instead of moved")))
    app.solve_clipboard()
    assert done.wait(1)
    assert copied == ["B"]
    assert moved == ["B"]


def test_copied_image_uses_ocr_when_clipboard_has_no_text(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    app.clipboard.read_text = lambda: ""
    monkeypatch.setattr("codekey.app.read_clipboard_image_text", lambda limit: "What is 2 + 2?")
    seen = []
    app.solver.solve = lambda question: seen.append(question) or SimpleNamespace(
        code="4", classification=SimpleNamespace(task_type=TaskType.GENERAL)
    )
    app.solve_clipboard()
    assert seen == ["What is 2 + 2?"]


def test_multiple_mcqs_move_cursor_repeatedly(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    questions = [
        "What is 2 + 2?\nC. 5\nD. 6\nA. 3\nB. 4",
        "Which keyword defines a function?\nD. define\nC. fun\nB. def\nA. function",
        "What is 3 + 3?\nB. 5\nC. 6\nD. 7\nA. 4",
    ]
    app.clipboard.read_text = lambda: questions.pop(0)
    answers = iter("BBC")
    class Client:
        def ensure_ready(self):
            pass
        def generate(self, system_prompt, prompt, temperature):
            return next(answers)
    app.solver.client = Client()
    app.clipboard.write_text = lambda text: None
    moved = []
    monkeypatch.setattr("codekey.app.move_to_mcq_answer", moved.append)
    for count in range(1, 4):
        app.solve_clipboard()
        import time
        deadline = time.monotonic() + 1
        while len(moved) < count and time.monotonic() < deadline:
            time.sleep(0.001)
        assert len(moved) == count
    assert moved == ["B", "B", "C"]


def test_image_with_question_and_options_moves_to_written_letter(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    monkeypatch.setattr("codekey.app.read_clipboard_image_text", lambda limit: (
        "What is the capital of France?\nC. Paris\nB. London\nD. Rome\nA. Berlin"
    ))
    app.clipboard.read_text = lambda: "image alt text"
    class Client:
        def ensure_ready(self):
            pass
        def generate(self, system_prompt, prompt, temperature):
            return "Paris"
    app.solver.client = Client()
    app.clipboard.write_text = lambda text: None
    moved = []
    done = threading.Event()
    monkeypatch.setattr("codekey.app.move_to_mcq_answer", lambda letter: moved.append(letter) or done.set())
    app.solve_clipboard()
    assert done.wait(1)
    assert moved == ["C"]


def test_screen_python_output_mcq_moves_cursor_to_b(monkeypatch):
    app = CodeKeyApp(load_config("config.yaml"), logging.getLogger("test-codekey"))
    question = (
        "What is the output of the following Python code?\n"
        "1 x = [1, 2, 3]\n2 y = x\n3 y.append(4)\n4 x.append(5)\n5 print(y)\n"
        "A [1, 2, 3, 4]\nB [1, 2, 3, 4, 5]\nC [1, 2, 3, 5]\nD Error"
    )
    monkeypatch.setattr("codekey.app.read_screen_text", lambda limit: question)
    class Client:
        def ensure_ready(self):
            pass
        def generate(self, system_prompt, prompt, temperature):
            return "[1, 2, 3, 4, 5]"
    app.solver.client = Client()
    app.clipboard.write_text = lambda text: None
    moved = []
    done = threading.Event()
    monkeypatch.setattr("codekey.app.move_to_mcq_answer", lambda letter: moved.append(letter) or done.set())
    app.solve_screen()
    assert done.wait(1)
    assert moved == ["B"]
