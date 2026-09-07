# Fireflies Clone 2.4.0

A Windows desktop meeting workspace inspired by the Fireflies experience.

## Included
- Home dashboard + persistent meeting library
- First-run profile setup
- Polished light/dark mode with dedicated Settings
- Startup splash animation
- Live microphone recording with playback after saving
- Browser live speech recognition where Chromium supports it
- Multilingual AI transcription fallback through OpenAI transcription models
- Interactive speaker/timestamp transcript
- Transcript search with highlighted matches
- Click transcript line to seek audio
- Audio player with native seek controls
- Grounded AskFred meeting-aware AI assistant with optional OpenAI enhancement
- AI meeting summary, topics, decisions and action-item extraction
- Meeting CRUD, notes CRUD and task completion/deletion
- Upload audio/video or paste a timestamped transcript
- Persistent SQLite database, recordings, and standalone Notes in the Windows user-data directory

## AI setup
Open **Settings** to choose appearance and transcription language. An OpenAI API key is optional and can be added in Settings → Meeting AI for stronger AI answers and analysis.

The application uses the OpenAI Responses API for AskFred/analysis and OpenAI transcription models for uploaded recordings. Without a key, AskFred uses grounded deterministic meeting-memory retrieval instead of a free-form local chat model, reducing hallucinations. OpenAI is used when the saved key is available.

## Windows build
Run:

```bat
build-windows.bat
```

The build creates the Next.js static frontend, packages the Python backend, and produces the Electron Windows artifacts in `release/`.
