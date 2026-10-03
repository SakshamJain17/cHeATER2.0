import sys
from types import ModuleType, SimpleNamespace

from codekey import mcq_cursor


def test_mcq_cursor_targets_screen_edges(monkeypatch):
    positions = []
    class Mouse:
        @property
        def position(self):
            return positions[-1]
        @position.setter
        def position(self, value):
            positions.append(value)
    monkeypatch.setattr("pynput.mouse.Controller", Mouse)
    monkeypatch.setattr(mcq_cursor.sys, "platform", "darwin")
    quartz = ModuleType("Quartz")
    monkeypatch.setitem(sys.modules, "Quartz", quartz)
    quartz.CGMainDisplayID = lambda: 1
    quartz.CGDisplayBounds = lambda display: SimpleNamespace(
        origin=SimpleNamespace(x=0, y=0), size=SimpleNamespace(width=1000, height=800)
    )
    for choice in "ABCD":
        mcq_cursor.move_to_mcq_answer(choice)
    assert positions == [(500, 56), (960, 400), (40, 400), (500, 744)]


def test_true_false_a_b_uses_configured_pair_positions(monkeypatch):
    positions = []

    class Mouse:
        @property
        def position(self):
            return positions[-1]

        @position.setter
        def position(self, value):
            positions.append(value)

    monkeypatch.setattr("pynput.mouse.Controller", Mouse)
    monkeypatch.setattr(mcq_cursor.sys, "platform", "darwin")
    quartz = ModuleType("Quartz")
    monkeypatch.setitem(sys.modules, "Quartz", quartz)
    quartz.CGMainDisplayID = lambda: 1
    quartz.CGDisplayBounds = lambda display: SimpleNamespace(
        origin=SimpleNamespace(x=0, y=0), size=SimpleNamespace(width=1000, height=800)
    )
    mcq_cursor.move_to_mcq_answer("A", horizontal=True)
    mcq_cursor.move_to_mcq_answer("B", horizontal=True)
    assert positions == [
        (int(1000 * mcq_cursor._HORIZONTAL_POSITIONS["A"][0]),
         int(800 * mcq_cursor._HORIZONTAL_POSITIONS["A"][1])),
        (int(1000 * mcq_cursor._HORIZONTAL_POSITIONS["B"][0]),
         int(800 * mcq_cursor._HORIZONTAL_POSITIONS["B"][1])),
    ]


def test_unlabelled_true_false_targets_left_and_right(monkeypatch):
    moved = []
    monkeypatch.setattr(
        mcq_cursor,
        "move_to_mcq_answer",
        lambda answer, horizontal=False: moved.append((answer, horizontal)) or (1, 2),
    )
    assert mcq_cursor.move_to_true_false_answer("True") == (1, 2)
    assert mcq_cursor.move_to_true_false_answer("false") == (1, 2)
    assert moved == [("A", True), ("B", True)]


def test_multiple_answers_move_in_their_written_order(monkeypatch):
    moved = []
    paused = []
    monkeypatch.setattr(mcq_cursor, "move_to_mcq_answer", lambda answer: moved.append(answer) or (1, 2))
    monkeypatch.setattr(mcq_cursor.time, "sleep", paused.append)
    assert mcq_cursor.move_to_mcq_answers("B,D") == [(1, 2), (1, 2)]
    assert moved == ["B", "D"]
    assert paused == [0.7]
