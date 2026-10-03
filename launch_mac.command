#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  printf '%s\n' 'CodeKey setup is missing. Run setup_mac.command first.' >> codekey.log
  exit 1
fi
.venv/bin/python main.py >> codekey.log 2>&1
