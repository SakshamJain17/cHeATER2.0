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


def test_true_false_a_b_targets_left_and_right(monkeypatch):
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
    assert positions == [(40, 400), (960, 400)]
