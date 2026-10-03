import sys
import time

from codekey.exceptions import CodeKeyError


# Screen positions for answers arranged at the top, right, left, and bottom.
_POSITIONS = {
    "A": (0.50, 0.07),
    "B": (0.96, 0.50),
    "C": (0.04, 0.50),
    "D": (0.50, 0.93),
    "a": (0.50, 0.07),
    "b": (0.96, 0.50),
    "c": (0.04, 0.50),
    "d": (0.50, 0.93),
}

_HORIZONTAL_POSITIONS = {
    "A": (0.50, 0.07),
    "B": (0.50, 0.93),
    "a": (0.50, 0.07),
    "b": (0.50, 0.93),
    "true": (0.50, 0.07),
    "false": (0.50, 0.93),
}


def is_true_false_choice_pair(options: dict[str, str] | None) -> bool:
    if not options or set(options) != {"A", "B"}:
        return False
    values = {value.strip(" .:;()[]").casefold() for value in options.values()}
    return values == {"true", "false"}


def move_to_true_false_answer(answer: str) -> tuple[int, int]:
    labels = {"true": "A", "false": "B"}
    label = labels.get(answer.strip().casefold())
    if label is None:
        raise CodeKeyError("Cannot move the cursor: answer must be True or False.")
    return move_to_mcq_answer(label, horizontal=True)


def move_to_mcq_answer(
    answer: str,
    horizontal: bool = False,
    duration_seconds: float = 0.0,
) -> tuple[int, int]:
    positions = _HORIZONTAL_POSITIONS if horizontal else _POSITIONS
    if answer not in positions:
        raise CodeKeyError("Cannot move the cursor: MCQ answer must be A, B, C, or D.")
    try:
        from pynput.mouse import Controller

        if sys.platform == "darwin":
            from Quartz import CGDisplayBounds, CGMainDisplayID

            bounds = CGDisplayBounds(CGMainDisplayID())
            left, top = bounds.origin.x, bounds.origin.y
            width, height = bounds.size.width, bounds.size.height
        elif sys.platform == "win32":
            import ctypes

            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            left, top = 0, 0
            width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        else:
            raise CodeKeyError("MCQ cursor movement requires macOS or Windows.")
        x_fraction, y_fraction = positions[answer]
        x = left + width * x_fraction
        y = top + height * y_fraction
        target = (int(x), int(y))
        mouse = Controller()
        if duration_seconds > 0:
            start_x, start_y = mouse.position
            steps = max(2, int(duration_seconds / 0.012))
            for step in range(1, steps + 1):
                progress = step / steps
                # Smoothstep eases in and out instead of changing speed abruptly.
                eased = progress * progress * (3 - 2 * progress)
                mouse.position = (
                    int(start_x + (target[0] - start_x) * eased),
                    int(start_y + (target[1] - start_y) * eased),
                )
                time.sleep(duration_seconds / steps)
        else:
            mouse.position = target
        actual = mouse.position
        if abs(actual[0] - target[0]) > 10 or abs(actual[1] - target[1]) > 10:
            if sys.platform == "darwin":
                from Quartz import CGWarpMouseCursorPosition
                CGWarpMouseCursorPosition(target)
                actual = mouse.position
            if abs(actual[0] - target[0]) > 10 or abs(actual[1] - target[1]) > 10:
                raise CodeKeyError("Cursor did not reach the MCQ target. Check Accessibility permission.")
        return target
    except CodeKeyError:
        raise
    except Exception as error:
        raise CodeKeyError(
            "Could not move the mouse. Check system input permissions."
        ) from error


def move_to_mcq_answers(
    answers: str,
    pause_seconds: float = 0.3,
    travel_seconds: float = 0.45,
) -> list[tuple[int, int]]:
    """Show selected letters with smooth, ordered cursor movements."""
    labels = [label.strip().upper() for label in answers.split(",") if label.strip()]
    if not labels or any(label not in "ABCD" for label in labels):
        raise CodeKeyError("Cannot move the cursor: selections must contain A, B, C, or D.")
    targets = []
    for index, label in enumerate(labels):
        targets.append(move_to_mcq_answer(label, duration_seconds=travel_seconds))
        if index + 1 < len(labels):
            time.sleep(pause_seconds)
    return targets
