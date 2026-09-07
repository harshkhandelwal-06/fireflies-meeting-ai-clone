# Evaluation Checklist

## Functionality
- [ ] Launches to Home, not a meeting.
- [ ] New meeting opens a blank workspace.
- [ ] Notes can be edited and persisted.
- [ ] Microphone recording starts/stops and saves locally.
- [ ] Transcript can be searched, timestamped, and extended.
- [ ] Summary can be generated from captured content.
- [ ] Tasks can be created and completed.
- [ ] Bookmarks/comments/soundbites persist.
- [ ] AskFred answers with meeting context.
- [ ] Live Assist opens in its own desktop window.
- [ ] Home actions navigate to their intended workflows.

## UI/UX
- [ ] Home mirrors the supplied Fireflies reference layout.
- [ ] Meeting workspace uses Notes + AskFred/Transcript two-panel hierarchy.
- [ ] Dark theme uses distinct workspace, card, control, and border tones.
- [ ] Desktop title bars and controls behave as native Windows windows.

## Database
- [ ] Meeting is the parent aggregate.
- [ ] Child records use foreign keys and cascade on meeting deletion.
- [ ] Transcript ordering is timestamp-based.
- [ ] Cross-meeting transcript references are rejected.

## Backend/API
- [ ] Health endpoint is available for Electron startup checks.
- [ ] CRUD endpoints return consistent JSON.
- [ ] Child resources validate their parent meeting.
- [ ] Binary recordings are stored outside the SQLite file.

## Code quality/modularity
- [ ] API access is centralized in `frontend/lib/api.ts`.
- [ ] Shared UI primitives are in `frontend/components/common.tsx`.
- [ ] Electron lifecycle is isolated in `desktop/main.cjs`.
- [ ] Backend models/routes/AI helpers have clear responsibilities.
- [ ] Architecture can be explained using `docs/ARCHITECTURE.md`.
