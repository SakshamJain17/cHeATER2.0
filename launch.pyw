"""Start CodeKey without a console and record early startup failures."""

import sys
import traceback
import os
from pathlib import Path


project = Path(__file__).resolve().parent
try:
    output = (project / "codekey.log").open("a", encoding="utf-8", buffering=1)
except OSError:
    output = open(os.devnull, "w", encoding="utf-8")
with output as log:
    sys.stdout = log
    sys.stderr = log
    try:
        from codekey.app import main

        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc(file=log)
        raise SystemExit(1)
