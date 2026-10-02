# CodeKey

CodeKey answers copied questions with a model running **on your computer**. Nonprogramming questions get short plain text answers unless a longer answer is requested. It supports write-a-program questions, debugging, code explanations, MCQs, true/false, and general questions. Programming answers follow the requested language; Python is the default. It works on Windows and macOS without VS Code, Ollama, an API key, or per-question charges. Once the model and software are installed, answering questions needs no internet connection.

The default model is [Qwen2.5-Coder-1.5B-Instruct GGUF](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF), an Apache 2.0 model of about 1.12 GB. It is small enough to transfer between computers, though a larger model may answer difficult questions better. CodeKey runs it through [llama.cpp](https://github.com/ggml-org/llama.cpp). The model and runner must be installed once on **each** computer, or copied there before going offline.

## Set up on Windows

1. Install [Python 3.12 or newer](https://www.python.org/downloads/windows/) and enable the Python launcher.
2. Install llama.cpp with `winget install llama.cpp` in a Command Prompt. Reopen Command Prompt after installation so the command is on `PATH`. You can also use a [prebuilt llama.cpp release](https://github.com/ggml-org/llama.cpp/releases) and set `model.binary` in `config.yaml` to its `llama-cli.exe` path.
3. Double-click `setup_windows.bat` in the CodeKey folder. It installs Python dependencies, downloads and verifies the model, then checks the runner.
4. Double-click `launch_windows.bat` whenever you want CodeKey running. Keep its terminal window open while using the hotkey.

If the computer cannot download the model, copy `models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` from a computer where setup completed. The Windows computer still needs Python dependencies and llama.cpp installed. Setup requires network access once for downloads; normal question answering does not use a network connection.

## Set up on macOS

Install [Python 3.12 or newer](https://www.python.org/downloads/macos/) and llama.cpp before setup. If you use Homebrew, run `brew install llama.cpp`. You can also use a [prebuilt llama.cpp release](https://github.com/ggml-org/llama.cpp/releases) and set `model.binary` in `config.yaml` to its `llama-cli` path.

1. Run `setup_mac.command` once, then double-click `launch_mac.command` to start CodeKey. Keep its Terminal window open. Setup downloads the model; the model and llama.cpp runner are not stored in this repository.
2. If CodeKey reports a permission error, open System Settings > Privacy & Security > Accessibility and enable Terminal (or Python), then launch CodeKey again. macOS may also request Input Monitoring permission for global hotkeys.

If macOS blocks a downloaded `.command` file, open Terminal in the CodeKey folder and run `sh setup_mac.command` or `sh launch_mac.command`.

## Use

Copy a question from Notes, a browser, or another app, then press **Option + /** on macOS or **Alt + /** on Windows to prepare the answer. On macOS, press **Control + Shift + I** to read a question visible on the main screen using local OCR. Enable Screen Recording for Terminal in System Settings > Privacy & Security > Screen & System Audio Recording, then restart CodeKey. The clipboard hotkey reads copied text or OCR text from a copied image when pressed. If the copied image contains both a question and labeled options, it uses the letters before the options even when they appear in a different order. The screen hotkey captures the main display only when pressed. Put the text cursor where you want the answer and press **Control + Shift + T** to start typing. You can press the typing hotkey while CodeKey is still generating; it will wait until the answer is ready. It types answers gradually. For programming questions, it adjusts for editor auto indentation after each new line. It does not replace the clipboard while typing. Keep that app focused until typing finishes. It does not execute generated code.

Press **Control + Shift + X** to cancel a prepared or currently typing answer while keeping CodeKey running. Press **Control + Shift + Q** to stop CodeKey completely; start it again with the launcher. The shortcuts can be changed in `config.yaml`.

For an MCQ with options A–D, the prepare hotkey immediately copies the chosen letter and moves the mouse on the main display. Options may appear in any order and may use a bare or circled letter; CodeKey uses the letter written before each option. A maps near the top edge (50% across, 7% down), B near the right edge (96% across, 50% down), C near the left edge (4% across, 50% down), and D near the bottom edge (50% across, 93% down). The small margin keeps the pointer visible outside the menu bar and Dock. It **does not click**. These positions indicate the answer letter; they are independent of where the option appears on the webpage.

Run `python main.py --check` to check that the local runner and model files exist without starting the hotkey listener. This does not perform a model inference. The setup scripts run this check automatically. Configuration is in `config.yaml`; `model.path` can point to any local GGUF model and `model.binary` can point to a local `llama-cli` executable.

Image input uses OCR to read text. It cannot reason from diagrams or other visual content that has no readable text. The default model may take time to load for each question and can make mistakes. Review code and answers before using them. No question or answer text is logged.

## Tests

After setup, run `.venv\Scripts\python.exe -m pip install pytest` and `.venv\Scripts\python.exe -m pytest` on Windows. On macOS, use `.venv/bin/python -m pip install pytest` and `.venv/bin/python -m pytest`.

## License

CodeKey is MIT licensed; see [LICENSE](LICENSE). The model and llama.cpp have their own licenses at the links above.
