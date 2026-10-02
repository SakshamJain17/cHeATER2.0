#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Run setup_mac.command first."
  exit 1
fi
.venv/bin/python main.py
result=$?
if [ "$result" -ne 0 ]; then
  echo "Press Return to close this window."
  read -r answer
fi
exit "$result"
