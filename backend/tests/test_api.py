"""Fast API smoke tests for the core evaluator workflow."""
import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def test_core_meeting_lifecycle():
    root = Path(tempfile.mkdtemp())
    os.environ['FIREFLIES_DB_PATH'] = str(root / 'test.db')
    os.environ['FIREFLIES_RECORDINGS_DIR'] = str(root / 'recordings')

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    assert client.get('/api/health').status_code == 200
    meetings = client.get('/api/meetings').json()
    assert len(meetings) >= 20

    meeting = client.post('/api/meetings', json={
        'title': 'Evaluation Meeting', 'participants': ['Harsh'],
        'notes': 'Discuss dashboard delivery.', 'duration': 0,
    }).json()
    mid = meeting['id']

    assert client.get(f'/api/meetings/{mid}').json()['transcript'] == []
    note = client.post('/api/notes', json={'title':'Test note','content':'Capture the launch decision.'}).json()
    assert note['title'] == 'Test note'
    assert client.patch(f'/api/notes/{note["id"]}', json={'content':'Updated launch decision.'}).json()['content'] == 'Updated launch decision.'
    assert client.get('/api/notes').status_code == 200
    assert client.delete(f'/api/notes/{note["id"]}').status_code == 200
    line = client.post(f'/api/meetings/{mid}/transcript', json={
        'speaker': 'Harsh', 'seconds': 5, 'text': 'Ship dashboard next week.'
    }).json()
    task = client.post(f'/api/meetings/{mid}/tasks', json={
        'text': 'Ship dashboard', 'owner': 'Harsh'
    }).json()
    assert task['completed'] is False

    summary = client.post(f'/api/meetings/{mid}/summary').json()
    assert summary['summary']
    assert client.post(f'/api/meetings/{mid}/bookmarks', json={'line_id': line['id']}).status_code == 200
    assert client.post(f'/api/meetings/{mid}/comments', json={'line_id': line['id'], 'text': 'Important'}).status_code == 200
    assert client.post(f'/api/meetings/{mid}/soundbites', json={'title': 'Highlight', 'start': 5, 'end': 15}).status_code == 200
    assert client.post(f'/api/meetings/{mid}/recording', data=b'fake-audio', headers={'Content-Type': 'audio/webm', 'X-Filename': 'test.webm'}).status_code == 200
    assert client.get(f'/api/meetings/{mid}/recording').status_code == 200
    assert client.patch(f'/api/tasks/{task["id"]}', json={'text':'Ship dashboard fast'}).json()['text'] == 'Ship dashboard fast'
    assert client.patch(f'/api/transcript/{line["id"]}', json={'text':'Ship dashboard fast next week.'}).json()['text'] == 'Ship dashboard fast next week.'
    detail = client.get(f'/api/meetings/{mid}').json()
    assert len(detail['transcript']) == 1
    assert len(detail['tasks']) == 1
    assert detail['summary']
    assert client.delete(f'/api/tasks/{task["id"]}').status_code == 200
    assert len(client.get(f'/api/meetings/{mid}').json()['tasks']) == 0

    assert client.delete(f'/api/meetings/{mid}').status_code == 200
    assert client.get(f'/api/meetings/{mid}').status_code == 404
