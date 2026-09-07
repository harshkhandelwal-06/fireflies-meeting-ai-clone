# Run / Build on Windows

## Development
1. Install Node.js 22+ and Python 3.11.
2. Run `build-windows.bat` to build the desktop application.
3. The app stores SQLite data and recordings in the Windows Electron user-data directory.

## AI
Open Settings → AI provider and enter an OpenAI API key. The key is stored in the local application settings and is never hard-coded into the project.

The application uses the OpenAI Responses API for AskFred/meeting analysis and the OpenAI transcription endpoint for uploaded/recorded audio. Without a key, the app retains deterministic local summary/meeting-memory fallbacks.

## Verification
Run:

`python -m pytest -q backend/tests`

The repository also contains `docs/VERIFICATION.md` with the verified capability matrix.
