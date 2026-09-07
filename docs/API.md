# API Contract

Base URL: `http://127.0.0.1:8000/api`

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Electron startup health check |
| GET | `/meetings` | List/search meetings |
| GET | `/meetings/{id}` | Full meeting aggregate |
| POST | `/meetings` | Create blank/upload-backed meeting |
| PATCH | `/meetings/{id}` | Update title, participants, tags, notes |
| DELETE | `/meetings/{id}` | Delete meeting and related child rows |
| POST | `/meetings/{id}/transcript` | Append transcript line |
| POST | `/meetings/{id}/summary` | Generate summary from captured content; uses OpenAI when configured, otherwise local fallback |
| POST | `/meetings/{id}/tasks` | Create action item |
| PATCH | `/tasks/{id}` | Complete/edit action item |
| POST/DELETE | `/meetings/{id}/bookmarks`, `/bookmarks/{id}` | Timestamp bookmarks |
| POST/DELETE | `/meetings/{id}/comments`, `/comments/{id}` | Transcript comments |
| POST/PATCH/DELETE | `/meetings/{id}/soundbites`, `/soundbites/{id}` | Soundbite lifecycle |
| POST | `/meetings/{id}/recording` | Persist recorded media |
| GET | `/ai/status` | Report AI provider/model configuration without exposing the key |
| POST | `/settings/llm-key` | Save or clear the optional local OpenAI API key |
| POST | `/ask` | AskFred meeting-memory query; uses OpenAI when configured, otherwise local/Ollama/fallback AI |
| POST | `/ai/summarize-notes` | Summarize scratch Take Notes content with the configured AI provider/fallback |
| GET | `/meetings/{id}/export` | Download a ZIP containing meeting metadata, transcript, summary, tasks, and recording when available |


### Recording & transcription additions

- `GET /api/meetings/{mid}/recording` streams a saved local recording for the meeting player.
- `POST /api/meetings/{mid}/transcribe` accepts recorded audio and uses the saved OpenAI key for server-side transcription when configured; without a key it returns existing browser/live transcript data when available.
- `DELETE /api/tasks/{tid}` permanently removes a task.


### Notes
- `GET /api/notes`
- `POST /api/notes`
- `PATCH /api/notes/{id}`
- `DELETE /api/notes/{id}`

Standalone notes persist in SQLite and can be summarized through the existing AI notes endpoint.
