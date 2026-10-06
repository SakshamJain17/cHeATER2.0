"""Read image questions with local macOS Vision text recognition."""

import subprocess
import sys
import tempfile
import re
from urllib.parse import unquote, urlparse
from pathlib import Path

from codekey.exceptions import CodeKeyError


def _observations_to_text(observations) -> str:
    """Keep OCR fragments on a row together, but separate distant columns."""
    fragments = []
    for item in observations:
        candidates = item.topCandidates_(1)
        if not candidates:
            continue
        box = item.boundingBox()
        value = str(candidates[0].string()).strip()
        if value:
            fragments.append((box.origin.y + box.size.height / 2, box.origin.x,
                              box.size.width, box.size.height, value))
    fragments.sort(key=lambda fragment: (-fragment[0], fragment[1]))
    rows = []
    for fragment in fragments:
        if rows and abs(rows[-1][0][0] - fragment[0]) <= max(rows[-1][0][3], fragment[3], 0.015) * 0.55:
            rows[-1].append(fragment)
        else:
            rows.append([fragment])
    lines = []
    for row in rows:
        row.sort(key=lambda fragment: fragment[1])
        current = ""
        right = 0.0
        for _, x, width, _, value in row:
            if current and not re.fullmatch(r"[A-DⒶⒷⒸⒹ]", current) and (
                x - right > 0.13 or re.fullmatch(r"[A-DⒶⒷⒸⒹ]", value)
            ):
                lines.append(current)
                current = value
            else:
                current = f"{current} {value}".strip()
            right = x + width
        if current:
            lines.append(current)
    text = "\n".join(lines)
    # Vision sometimes puts two options in one text observation or one OCR row.
    text = re.sub(r"(?<=\S)[ \t]+(?=(?:\(?[A-D]\)|[A-D][.)])[ \t]+\S)", "\n", text)
    return text.strip()


def _recover_spatial_choices(observations) -> dict[str, str]:
    """Pair isolated OCR option letters with nearby text when row grouping misses them."""
    labels = []
    words = []
    circled = str.maketrans("ⒶⒷⒸⒹⓐⓑⓒⓓ", "ABCDabcd")
    for item in observations:
        box = item.boundingBox()
        candidates = [str(candidate.string()).strip().translate(circled)
                      for candidate in item.topCandidates_(5)]
        if not candidates:
            continue
        recognized = None
        for candidate in candidates:
            match = re.fullmatch(r"\(?([A-Da-d])\)?[.):]?", candidate)
            if match:
                recognized = match.group(1).upper()
                break
        center_y = box.origin.y + box.size.height / 2
        if recognized and box.size.width < 0.10:
            labels.append((recognized, box.origin.x + box.size.width, center_y, box.size.height))
        else:
            words.append((box.origin.x, center_y, box.size.width, box.size.height, candidates[0]))
    choices = {}
    for label, right, center_y, height in labels:
        nearby = [word for word in words if word[0] >= right - 0.01
                  and word[0] - right < 0.50
                  and abs(word[1] - center_y) < max(height, word[3], 0.05)]
        other_labels = [other[1] for other in labels if other[1] > right
                        and abs(other[2] - center_y) < max(height, other[3], 0.05)]
        if other_labels:
            nearby = [word for word in nearby if word[0] < min(other_labels)]
        if nearby:
            nearby.sort(key=lambda word: word[0])
            choices[label] = " ".join(word[4] for word in nearby).strip()
    return choices


def _recognize_image(image_path: Path, max_chars: int, diagnostics: bool = False) -> str:
    import objc
    from Foundation import NSURL

    objc.loadBundle("Vision", globals(), bundle_path="/System/Library/Frameworks/Vision.framework")
    request_type = objc.lookUpClass("VNRecognizeTextRequest")
    handler_type = objc.lookUpClass("VNImageRequestHandler")
    request = request_type.alloc().init()
    request.setRecognitionLevel_(1)
    handler = handler_type.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(image_path)), {})
    if not handler.performRequests_error_([request], None):
        raise CodeKeyError("Image text recognition failed.")
    observations = request.results() or []
    text = _observations_to_text(observations)
    from codekey.classifier import parse_choice_options
    if len(parse_choice_options(text)) < 2:
        recovered = _recover_spatial_choices(observations)
        if len(recovered) >= 2:
            text += "\n" + "\n".join(f"{label}. {answer}" for label, answer in sorted(recovered.items()))
    if not text:
        raise CodeKeyError("No readable text was found in the image.")
    if len(text) > max_chars:
        raise CodeKeyError(f"Image text exceeds the {max_chars}-character limit.")
    if diagnostics:
        details = []
        for item in observations:
            box = item.boundingBox()
            candidates = [str(candidate.string()) for candidate in item.topCandidates_(5)]
            if candidates:
                details.append(f"x={box.origin.x:.2f} y={box.origin.y:.2f}: " + " | ".join(candidates))
        return text + "\n\n--- OCR fragments (position: candidates) ---\n" + "\n".join(details)
    return text


def recognize_image_text(image_path: str | Path, max_chars: int, diagnostics: bool = False) -> str:
    """OCR an existing image locally with macOS Vision."""
    path = Path(image_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise CodeKeyError("The captured screen image is missing or empty.")
    return _recognize_image(path, max_chars, diagnostics)


def _require_screen_capture_access() -> None:
    if sys.platform != "darwin":
        raise CodeKeyError("Screen question capture currently requires macOS.")
    from Quartz import CGPreflightScreenCaptureAccess, CGRequestScreenCaptureAccess

    if not CGPreflightScreenCaptureAccess() and not CGRequestScreenCaptureAccess():
        raise CodeKeyError(
            "Screen Recording permission is required. Enable CodeKey Launcher "
            "(or Terminal, if launched there) in System Settings > Privacy & Security "
            "> Screen & System Audio Recording, then restart CodeKey."
        )


def capture_screen_image(destination: str | Path) -> Path:
    """Capture the primary display to a caller-owned local PNG."""
    _require_screen_capture_access()
    image_path = Path(destination)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["/usr/sbin/screencapture", "-x", "-D", "1", str(image_path)],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0 or not image_path.is_file() or image_path.stat().st_size == 0:
            raise CodeKeyError("Screen capture failed. Check Screen Recording permission and restart CodeKey.")
        return image_path
    except CodeKeyError:
        raise
    except Exception as error:
        raise CodeKeyError("Could not capture the screen image.") from error


def read_screen_text(max_chars: int, diagnostics: bool = False) -> str:
    with tempfile.TemporaryDirectory(prefix="codekey-screen-") as directory:
        image_path = capture_screen_image(Path(directory) / "screen.png")
        return recognize_image_text(image_path, max_chars, diagnostics)


def read_clipboard_image_text(max_chars: int) -> str | None:
    """Return OCR text when the macOS clipboard contains an image, else None."""
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSPasteboard

        board = NSPasteboard.generalPasteboard()
        image_data = None
        suffix = ".png"
        for kind, extension in (
            ("public.png", ".png"), ("image/png", ".png"),
            ("public.tiff", ".tiff"), ("com.apple.tiff", ".tiff"),
            ("public.jpeg", ".jpg"), ("image/jpeg", ".jpg"),
            ("public.heic", ".heic"),
        ):
            image_data = board.dataForType_(kind)
            if image_data is not None:
                suffix = extension
                break
        if image_data is None:
            file_url = board.stringForType_("public.file-url")
            if file_url:
                parsed = urlparse(str(file_url))
                file_path = Path(unquote(parsed.path))
                if parsed.scheme == "file" and file_path.is_file() and file_path.suffix.lower() in {
                    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic",
                }:
                    return _recognize_image(file_path, max_chars)
            return None
        with tempfile.TemporaryDirectory(prefix="codekey-image-") as directory:
            image_path = Path(directory) / ("clipboard" + suffix)
            image_path.write_bytes(bytes(image_data))
            return _recognize_image(image_path, max_chars)
    except CodeKeyError:
        raise
    except Exception as error:
        raise CodeKeyError("Could not read the copied image.") from error
