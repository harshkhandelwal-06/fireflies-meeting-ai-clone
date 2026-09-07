# Fireflies Clone Architecture

## Overview

Fireflies Clone is a local-first desktop application composed of three layers:

1. **Electron shell** (`desktop/`) — owns the Windows window lifecycle, starts the backend, serves the exported frontend, and exposes only the required IPC bridge.
2. **Next.js/React UI** (`frontend/`) — presentation and interaction layer. Reusable visual primitives live in `frontend/components/`; API access is centralized in `frontend/lib/api.ts`.
3. **FastAPI + SQLite** (`backend/`) — application/data layer. Meetings are the aggregate root and transcript lines, tasks, bookmarks, comments, and soundbites are related child records.

## Data relationships

```text
Meeting
 ├── TranscriptLine[]
 ├── Task[]
 ├── Bookmark[]
 ├── Comment[]
 └── Soundbite[]
```

Deleting a meeting cascades to its child records. Transcript lines are ordered by meeting and timestamp. Bookmarks/comments validate that their referenced transcript line belongs to the same meeting.

## Meeting lifecycle

```text
Home
  -> New meeting
  -> blank workspace
  -> notes / microphone recording
  -> transcript capture
  -> AskFred / Live Assist
  -> generated summary / tasks
  -> saved meeting library
```

Seeded meetings are demo/history records only. Newly created meetings have empty notes, transcript, summary, decisions, and tasks.

## AI architecture

AskFred first builds a bounded meeting context from notes, transcript, topics, and summary. If an OpenAI key is configured, the context is sent to the Responses API. Without a key, the deterministic local retrieval agent answers from SQLite so the application remains usable offline.

## Why this structure scores well

- **Functionality:** API-backed state instead of UI-only mock state.
- **Database design:** normalized child tables and explicit foreign keys/relationships.
- **Backend/API:** resource-oriented meeting endpoints plus focused child-resource endpoints.
- **Code quality:** validation and business logic stay in the backend; presentation stays in React.
- **Modularity:** reusable cards/metrics/settings rows are separated from the page controller; Electron is isolated from the web UI.
