#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3.12 -m venv .venv || exit 1
.venv/bin/python -m pip install -r requirements.txt || exit 1
.venv/bin/python download_model.py || exit 1
.venv/bin/python main.py --check || {
  echo "Install llama.cpp or place a prebuilt llama-cli under vendor/llama-*/."
  exit 1
}
echo "Setup complete. Double-click launch_mac.command to start CodeKey."
