# Fireflies Clone 2.4.2 — Final Source Package

This project is an original Fireflies-inspired local desktop meeting workspace. It recreates the product's core meeting-memory workflow without copying proprietary code or assets. The assignment supplied with the project permits seeded/mock/LLM-generated transcripts and summaries rather than requiring cloud speech-to-text.

## Included experience

- Animated Fireflies-style startup splash and first-run signup/profile flow.
- Polished light/dark themes with persistent preference.
- Collapsible navigation sidebar with a compact profile menu and dedicated Settings page.
- Capture menu with live meeting, scheduling, upload, and Take Notes actions.
- Take Notes opens a notes-only surface and never silently creates a meeting.
- Meetings library with title/participant search, sorting, direct transcript opening, direct deletion, and persistent SQLite data.
- Meeting CRUD for titles, participants, notes, recordings, transcripts, summaries, and action items.
- Audio playback with native seek bar, recording controls, pause/resume while recording, and download.
- Interactive transcript with speaker labels, timestamps, click-to-seek, active-line highlighting, and search-term highlighting.
- Multilingual transcription with Auto detect plus English, Hindi, Spanish, French, German, Italian, Portuguese, Japanese, Korean, Chinese, Arabic, and Russian selections.
- Automatic local Whisper transcription for saved microphone recordings and uploaded audio/video.
- AskFred uses grounded meeting-memory retrieval by default and OpenAI when an API key is configured in Settings. Chat no longer falls back to the low-quality tiny browser generator.
- AI-generated meeting summary, topics, decisions, and action items.
- Live Assist layout with live captions, saved recording, Whisper transcript generation, pause/resume, and meeting-aware AskFred.
- Tasks page with global action-item completion and source-meeting navigation.
- Analytics page with meeting, minutes, participant, average-duration, and recent-duration views.
- Standalone persistent Notes workspace with AI summarization, notifications with Clear, profile menu, modals, toasts, and responsive layouts.

## Local AI behavior

For chat, AskFred is deliberately grounded in stored meeting data. When an OpenAI API key is saved under Settings → Meeting AI, OpenAI is used first for stronger answers and analysis. Without a key, chat uses deterministic meeting-memory retrieval so it does not invent facts. The local browser models remain available for supported offline analysis/transcription tasks.

## Build on Windows

1. Install Node.js 22+ and Python 3.11.
2. Run `build-windows.bat`.
3. The script builds the Next.js static frontend, bundles the FastAPI backend with PyInstaller, and packages a portable EXE plus NSIS installer.
4. The packaged app stores its SQLite database and recordings under Electron's per-user application data directory.

## Architecture

- Frontend: Next.js 14 + TypeScript + React + Tailwind CSS + lucide-react.
- Backend: FastAPI + SQLAlchemy + SQLite.
- Desktop shell: Electron.
- Local AI: Transformers.js + ONNX models for Qwen2.5-0.5B-Instruct and multilingual Whisper Tiny.
- Persistence: SQLite meetings, transcript lines, tasks, notes, and optional bookmark/comment/soundbite tables.

## Verification

The source package was syntax-checked for the updated TypeScript files, Python syntax-checked, and the included FastAPI lifecycle suite passes. Native Windows packaging remains a target-machine step because this preparation environment cannot create a Windows-native executable.

## 2.4.2 final touches
- Added a persistent Notes workspace with create/edit/delete and AI summarization.
- Take Notes now saves directly into the Notes workspace instead of only browser scratch storage.
- Removed the redundant Control Center UI. Settings remains the single configuration destination.
- Added a profile dropdown with name, email, and Settings access.
- Added Clear notifications and persistent cleared state.
- Added a one-click Transcript action in the Meetings library that opens the meeting's full transcript tab.
- Expanded starter data to 20 fully populated sample meetings with transcripts, summaries, decisions, and tasks.
- Tightened AskFred grounding so questions without evidence return a clear not-found response instead of a guessed answer.
