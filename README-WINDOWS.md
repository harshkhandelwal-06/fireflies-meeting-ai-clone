# Windows notes — Fireflies Clone 2.4.2

1. Install Node.js 22+ and Python 3.11+.
2. Run `build-windows.bat` from the project root.
3. Launch `release\Fireflies-Clone-Portable-2.4.2.exe` or install `release\Fireflies-Clone-2.4.2-x64.exe`.
4. On first launch, complete signup/profile setup.
5. No API key is required.
6. On the first AskFred/Whisper use, allow internet access so the app can download its local ONNX models. After the first download, model inference runs inside the app and the model files are cached.
7. Microphone access is requested when recording starts.

Recordings and SQLite data are persisted under Electron's per-user application data directory rather than inside the project folder.


## Meeting AI
AskFred and meeting analysis use the configured OpenAI API key for full LLM responses. Add or replace the key from Profile → Settings → Meeting AI. Without a key, chat uses grounded retrieval only and never invokes a small generative chat model. The default model is `gpt-5.6-luna`.
