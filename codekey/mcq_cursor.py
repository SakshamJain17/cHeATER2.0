import sys

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


def move_to_mcq_answer(answer: str) -> tuple[int, int]:
    if answer not in _POSITIONS:
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
        x_fraction, y_fraction = _POSITIONS[answer]
        x = left + width * x_fraction
        y = top + height * y_fraction
        target = (int(x), int(y))
        mouse = Controller()
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
