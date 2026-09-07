from datetime import datetime, timedelta
import os
from typing import Optional
import re, json, io, zipfile, csv
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, String, Integer, Boolean, Text, ForeignKey, DateTime, Index, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session
from pathlib import Path
from fastapi.responses import FileResponse, Response
import urllib.request
import urllib.error

DB_PATH = Path(os.getenv('FIREFLIES_DB_PATH', str(Path.cwd() / 'fireflies.db')))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
RECORDINGS_DIR = Path(os.getenv('FIREFLIES_RECORDINGS_DIR', str(DB_PATH.parent / 'recordings')))
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = DB_PATH.parent / 'settings.json'
engine=create_engine(f'sqlite:///{DB_PATH.as_posix()}',connect_args={'check_same_thread':False})
@event.listens_for(engine, 'connect')
def _sqlite_fk(dbapi_connection, _connection_record):
    cur=dbapi_connection.cursor(); cur.execute('PRAGMA foreign_keys=ON'); cur.close()
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
class Base(DeclarativeBase): pass

class Meeting(Base):
    __tablename__ = 'meetings'
    __table_args__ = (Index('ix_meetings_date', 'date'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    duration: Mapped[int] = mapped_column(Integer, default=0)
    participants: Mapped[str] = mapped_column(Text, default='')
    summary: Mapped[str] = mapped_column(Text, default='')
    topics: Mapped[str] = mapped_column(Text, default='')
    decisions: Mapped[str] = mapped_column(Text, default='')
    tags: Mapped[str] = mapped_column(Text, default='')
    notes: Mapped[str] = mapped_column(Text, default='')
    recording: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, default=None)

    transcript: Mapped[list['TranscriptLine']] = relationship(
        back_populates='meeting', cascade='all, delete-orphan', order_by='TranscriptLine.seconds'
    )
    tasks: Mapped[list['Task']] = relationship(back_populates='meeting', cascade='all, delete-orphan')
    bookmarks: Mapped[list['Bookmark']] = relationship(back_populates='meeting', cascade='all, delete-orphan')
    comments: Mapped[list['Comment']] = relationship(back_populates='meeting', cascade='all, delete-orphan')
    soundbites: Mapped[list['Soundbite']] = relationship(back_populates='meeting', cascade='all, delete-orphan')


class Note(Base):
    __tablename__ = 'notes'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default='Untitled note')
    content: Mapped[str] = mapped_column(Text, default='')
    summary: Mapped[str] = mapped_column(Text, default='')
    created: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TranscriptLine(Base):
    __tablename__ = 'transcript_lines'
    __table_args__ = (Index('ix_transcript_meeting_seconds', 'meeting_id', 'seconds'),)

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), index=True)
    speaker: Mapped[str] = mapped_column(String(100))
    seconds: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    meeting: Mapped['Meeting'] = relationship(back_populates='transcript')


class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), index=True)
    text: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(100), default='Unassigned')
    due: Mapped[str] = mapped_column(String(100), default='No due date')
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    meeting: Mapped['Meeting'] = relationship(back_populates='tasks')


class Bookmark(Base):
    __tablename__ = 'bookmarks'
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), index=True)
    line_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(40), default='Important')
    note: Mapped[str] = mapped_column(Text, default='')
    seconds: Mapped[int] = mapped_column(Integer)
    meeting: Mapped['Meeting'] = relationship(back_populates='bookmarks')


class Comment(Base):
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), index=True)
    line_id: Mapped[int] = mapped_column(Integer, index=True)
    author: Mapped[str] = mapped_column(String(100), default='Harsh')
    text: Mapped[str] = mapped_column(Text)
    created: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    meeting: Mapped['Meeting'] = relationship(back_populates='comments')


class Soundbite(Base):
    __tablename__ = 'soundbites'
    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey('meetings.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default='')
    access: Mapped[str] = mapped_column(String(40), default='Private')
    meeting: Mapped['Meeting'] = relationship(back_populates='soundbites')

Base.metadata.create_all(engine)
# Lightweight migration for databases created by older builds.
from sqlalchemy import inspect, text as sql_text
with engine.begin() as conn:
    cols = {c['name'] for c in inspect(engine).get_columns('meetings')}
    if 'notes' not in cols: conn.execute(sql_text("ALTER TABLE meetings ADD COLUMN notes TEXT DEFAULT ''"))
    if 'recording' not in cols: conn.execute(sql_text("ALTER TABLE meetings ADD COLUMN recording VARCHAR(500)"))

def db():
    s=SessionLocal();
    try: yield s
    finally: s.close()

def seed(s:Session):
    """Ensure a useful 20-meeting starter library without duplicating existing titles."""
    samples=[
        ('Q3 Product Strategy Review',1,52,['Harsh','Priya','Alex','Daniel'],'The team reviewed Q3 product priorities, customer feedback and launch sequencing. The group aligned on shipping the analytics workspace first and moving the mobile refresh into the following sprint.',['Q3 priorities','Analytics workspace','Customer feedback','Launch sequencing'],['Ship analytics workspace first','Mobile refresh moves to next sprint'],['product','strategy','q3']),
        ('Design System Sync',3,38,['Harsh','Maya','Leo'],'Design and engineering aligned on the new component library, naming conventions and accessibility requirements. A phased rollout was agreed for the next release.',['Component library','Accessibility','Rollout'],['Use semantic component names','Audit keyboard navigation before release'],['design','accessibility']),
        ('Customer Discovery — Acme',5,61,['Harsh','Nina','Jordan','Sam'],'Acme described onboarding friction and requested stronger reporting, exports and role-based controls. The team agreed to validate the workflow with two more customer interviews.',['Onboarding','Reporting','Exports','Permissions'],['Run two follow-up interviews','Prototype reporting dashboard'],['customer','research','acme']),
        ('Engineering Weekly',7,44,['Harsh','Arjun','Meera','Chris'],'Engineering reviewed delivery status, API reliability and upcoming infrastructure work. No major blockers remain, but API latency needs monitoring.',['Delivery','API reliability','Infrastructure'],['Monitor p95 API latency','Publish next sprint capacity'],['engineering','api']),
        ('Hiring Panel — ML Engineer',9,49,['Harsh','Riya','Kabir'],'The panel discussed system design depth, experimentation practices and communication. Candidate should receive a technical follow-up focused on evaluation design.',['System design','Experimentation','Communication'],['Schedule technical follow-up','Share evaluation rubric'],['hiring','ml']),
        ('Marketing Campaign Planning',11,35,['Harsh','Aisha','Vikram'],'Marketing aligned on the launch campaign, channel mix and creative production schedule for the next release.',['Campaign','Channels','Creative'],['Finalize channel plan','Approve creative brief'],['marketing','launch']),
        ('Sprint Planning — Platform',13,47,['Harsh','Dev','Ishita','Noah'],'The team prioritized platform reliability work, technical debt and developer tooling for the upcoming sprint.',['Sprint planning','Reliability','Developer tooling'],['Prioritize reliability fixes','Create developer tooling backlog'],['engineering','sprint']),
        ('Sales Pipeline Review',16,41,['Harsh','Neha','Omar'],'Sales reviewed pipeline health, top opportunities and follow-up timing. Several accounts require executive outreach before month end.',['Pipeline','Opportunities','Follow-up'],['Escalate top three deals','Schedule executive outreach'],['sales','pipeline']),
        ('Customer Success Weekly',18,33,['Harsh','Tanya','Luis'],'Customer success reviewed renewals, onboarding health and accounts needing intervention.',['Renewals','Onboarding health','Risk accounts'],['Contact at-risk renewals','Refresh onboarding checklist'],['customer-success','renewals']),
        ('Data Science Review',20,56,['Harsh','Aman','Sara'],'Data science reviewed experiment results, feature quality and evaluation metrics for the recommendation model.',['Experiments','Feature quality','Evaluation'],['Re-run the ablation study','Document evaluation metrics'],['data-science','ml']),
        ('UX Research Readout',23,39,['Harsh','Pooja','Ethan'],'Research findings highlighted navigation confusion and opportunities to improve first-time user guidance.',['UX research','Navigation','Onboarding'],['Prototype a simplified navigation','Test onboarding with five users'],['ux','research']),
        ('Security Review',26,51,['Harsh','Rahul','Grace'],'The team reviewed authentication flows, dependency updates and audit logging requirements.',['Security','Authentication','Audit logs'],['Complete dependency audit','Verify audit logging coverage'],['security','compliance']),
        ('Finance & Budget Check-in',29,31,['Harsh','Meera','Ryan'],'Finance reviewed monthly spend, cloud costs and the budget for planned product initiatives.',['Budget','Cloud costs','Planning'],['Review cloud cost anomalies','Lock next quarter budget'],['finance','budget']),
        ('Website Redesign Kickoff',32,45,['Harsh','Zoya','Karan'],'The redesign kickoff covered information architecture, visual direction and content migration sequencing.',['Redesign','Information architecture','Content'],['Approve sitemap','Create migration checklist'],['website','design']),
        ('Mobile App Retrospective',35,42,['Harsh','Ankit','Mia'],'The retrospective covered crash rates, release cadence and the quality of the mobile QA process.',['Mobile','Crash rate','QA'],['Improve crash monitoring','Add release QA checklist'],['mobile','retrospective']),
        ('Leadership Weekly Sync',38,48,['Harsh','Priyanka','Daniel'],'Leadership reviewed company priorities, cross-functional dependencies and risks for the next two weeks.',['Leadership','Priorities','Risks'],['Confirm cross-team owners','Review top delivery risks'],['leadership','planning']),
        ('Partner Integration Review',41,53,['Harsh','Rohan','Elena'],'The integration review focused on API contracts, authentication and the rollout plan for a new partner.',['Integration','API contracts','Authentication'],['Finalize API contract','Schedule integration test'],['partnerships','api']),
        ('Content Strategy Workshop',44,36,['Harsh','Simran','Jake'],'The workshop covered content themes, editorial cadence and distribution across product education channels.',['Content strategy','Editorial cadence','Distribution'],['Approve editorial calendar','Draft the first two guides'],['content','education']),
        ('Performance Tuning Session',47,58,['Harsh','Aditya','Chloe'],'The team analyzed response times, database queries and front-end rendering bottlenecks.',['Performance','Database','Frontend'],['Profile slow queries','Reduce initial bundle size'],['performance','database']),
        ('Quarterly Roadmap Alignment',50,63,['Harsh','Nikhil','Anaya','Tom'],'The group aligned roadmap themes, capacity assumptions and dependencies across the next quarter.',['Roadmap','Capacity','Dependencies'],['Freeze roadmap themes','Publish dependency map'],['roadmap','planning']),
    ]
    existing={m.title for m in s.query(Meeting).all()}
    now=datetime.now()
    for title,days,dur,people,summary,topics,decisions,tags in samples:
        if title in existing: continue
        m=Meeting(title=title,date=now-timedelta(days=days),duration=dur,participants=','.join(people),summary=summary,topics='|'.join(topics),decisions='|'.join(decisions),tags=','.join(tags))
        s.add(m); s.flush()
        lines=[
            ('Harsh',0,f'Welcome everyone. Today I want to focus on {topics[0].lower()} and what we need to decide.'),
            (people[1],max(8,round(dur*.22)),f'I think the biggest opportunity is {topics[1].lower()}. We have enough evidence from the last cycle.'),
            (people[2] if len(people)>2 else people[1],max(14,round(dur*.43)),'I agree. We should also make sure the implementation is measurable and easy to roll out.'),
            ('Harsh',max(18,round(dur*.60)),f'Good point. Let’s capture that as a follow-up and keep the plan focused on {topics[-1].lower()}.'),
            (people[1],max(22,round(dur*.70)),'What would you consider the most important dependency before we commit?'),
            ('Harsh',max(26,round(dur*.78)),'The dependency is readiness. If that is green, we can move ahead with the agreed sequencing.'),
            (people[-1],max(30,round(dur*.86)),'I can take the follow-up and bring a concrete proposal to the next sync.'),
            ('Harsh',max(34,round(dur*.94)),'Perfect. Let’s close with owners and next steps.'),
        ]
        for sp,sec,text in lines: s.add(TranscriptLine(meeting_id=m.id,speaker=sp,seconds=sec,text=text))
        for i,t in enumerate(decisions): s.add(Task(meeting_id=m.id,text=t,owner=people[(i+1)%len(people)],due='This week'))
    s.commit()

with SessionLocal() as s: seed(s)

app=FastAPI(title='Fireflies Clone API'); app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=False,allow_methods=['*'],allow_headers=['*'])

@app.get('/api/health')
def health(): return {'ok': True, 'app': 'Fireflies Clone'}
@app.get('/api/ai/status')
def ai_status():
    probe=False
    return {'mode':'openai' if configured_key() else 'grounded-retrieval','backend_ollama_available':bool(probe),'openai_configured':bool(configured_key()),'model':os.getenv('OPENAI_MODEL','gpt-5.6-luna'),'local_model':'grounded retrieval fallback','speech_model':'Xenova/whisper-tiny','api_key_required':False}
class MeetingCreate(BaseModel): title:str; participants:list[str]=[]; transcript:str=''; summary:str=''; notes:str=''; duration:int=30; tags:list[str]=[]; date:Optional[datetime]=None
class MeetingUpdate(BaseModel): title:Optional[str]=None; participants:Optional[list[str]]=None; tags:Optional[list[str]]=None; notes:Optional[str]=None; duration:Optional[int]=None; date:Optional[datetime]=None; summary:Optional[str]=None; topics:Optional[list[str]]=None; decisions:Optional[list[str]]=None
class TaskUpdate(BaseModel): completed:Optional[bool]=None; text:Optional[str]=None; owner:Optional[str]=None; due:Optional[str]=None
class TaskCreate(BaseModel): text:str; owner:str='Unassigned'; due:str='No due date'
class BookmarkCreate(BaseModel): line_id:int; kind:str='Important'; note:str=''
class CommentCreate(BaseModel): line_id:int; text:str; author:str='Harsh'
class SoundbiteCreate(BaseModel): title:str; start:int; end:int; text:str=''; access:str='Private'
class Ask(BaseModel): question:str; meeting_id:Optional[int]=None
class TranscriptCreate(BaseModel): speaker:str='Harsh'; seconds:int=0; text:str


def arr(x,sep='|'): return x.split(sep) if x else []
def mjson(m): return {'id':m.id,'title':m.title,'date':m.date.isoformat(),'duration':m.duration,'participants':arr(m.participants,','),'summary':m.summary,'notes':m.notes or '','recording':m.recording,'topics':arr(m.topics),'decisions':arr(m.decisions),'tags':arr(m.tags,',')}
def djson(m):
    d=mjson(m); d['transcript']=[{'id':x.id,'speaker':x.speaker,'seconds':x.seconds,'text':x.text} for x in sorted(m.transcript,key=lambda x:x.seconds)]; d['tasks']=[{'id':x.id,'text':x.text,'owner':x.owner,'due':x.due,'completed':x.completed} for x in m.tasks]; d['bookmarks']=[{'id':x.id,'line_id':x.line_id,'kind':x.kind,'note':x.note,'seconds':x.seconds} for x in m.bookmarks]; d['comments']=[{'id':x.id,'line_id':x.line_id,'author':x.author,'text':x.text,'created':x.created.isoformat()} for x in m.comments]; d['soundbites']=[{'id':x.id,'title':x.title,'start':x.start,'end':x.end,'text':x.text,'access':x.access} for x in m.soundbites]; return d

@app.get('/api/meetings')
def meetings(q:str='',tag:str='',db:Session=Depends(db)):
    ms=db.query(Meeting).order_by(Meeting.date.desc()).all(); ql=q.lower().strip()
    if ql: ms=[m for m in ms if ql in (m.title+' '+m.participants+' '+m.summary+' '+m.tags).lower() or any(ql in x.text.lower() or ql in x.speaker.lower() for x in m.transcript)]
    if tag: ms=[m for m in ms if tag.lower() in m.tags.lower().split(',')]
    return [mjson(m) for m in ms]
@app.get('/api/meetings/{mid}')
def meeting(mid:int,db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m: raise HTTPException(404,'Meeting not found')
    return djson(m)


class NoteCreate(BaseModel):
    title:str='Untitled note'
    content:str=''
    summary:str=''

class NoteUpdate(BaseModel):
    title:Optional[str]=None
    content:Optional[str]=None
    summary:Optional[str]=None

def njson(n:Note):
    return {'id':n.id,'title':n.title,'content':n.content,'summary':n.summary,'created':n.created.isoformat(),'updated':n.updated.isoformat()}

@app.get('/api/notes')
def notes(db:Session=Depends(db)):
    return [njson(n) for n in db.query(Note).order_by(Note.updated.desc()).all()]

@app.post('/api/notes')
def create_note(p:NoteCreate,db:Session=Depends(db)):
    n=Note(title=p.title.strip() or 'Untitled note',content=p.content,summary=p.summary,created=datetime.now(),updated=datetime.now())
    db.add(n);db.commit();db.refresh(n);return njson(n)

@app.patch('/api/notes/{nid}')
def update_note(nid:int,p:NoteUpdate,db:Session=Depends(db)):
    n=db.get(Note,nid)
    if not n: raise HTTPException(404,'Note not found')
    if p.title is not None: n.title=p.title.strip() or 'Untitled note'
    if p.content is not None: n.content=p.content
    if p.summary is not None: n.summary=p.summary
    n.updated=datetime.now();db.commit();db.refresh(n);return njson(n)

@app.delete('/api/notes/{nid}')
def delete_note(nid:int,db:Session=Depends(db)):
    n=db.get(Note,nid)
    if not n: raise HTTPException(404,'Note not found')
    db.delete(n);db.commit();return {'ok':True}
@app.post('/api/meetings')
def create_meeting(p:MeetingCreate,db:Session=Depends(db)):
    m=Meeting(title=p.title,participants=','.join(p.participants),summary=p.summary,notes=p.notes,duration=p.duration,tags=','.join(p.tags),topics='',decisions='',date=p.date or datetime.now());db.add(m);db.flush()
    for i,line in enumerate(p.transcript.splitlines()):
        if not line.strip():continue
        mt=re.match(r'\[(\d+):(\d+)\]\s*([^:]+):\s*(.*)',line); sec=int(mt.group(1))*60+int(mt.group(2)) if mt else i*30; sp=mt.group(3).strip() if mt else 'Speaker'; text=mt.group(4).strip() if mt else line.strip();db.add(TranscriptLine(meeting_id=m.id,speaker=sp,seconds=sec,text=text))
    db.commit();db.refresh(m);return mjson(m)
@app.patch('/api/meetings/{mid}')
def update_meeting(mid:int,p:MeetingUpdate,db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m:raise HTTPException(404,'Meeting not found')
    if p.title is not None:m.title=p.title
    if p.participants is not None:m.participants=','.join(p.participants)
    if p.tags is not None:m.tags=','.join(p.tags)
    if p.notes is not None:m.notes=p.notes
    if p.duration is not None:m.duration=max(0,p.duration)
    if p.date is not None:m.date=p.date
    if p.summary is not None:m.summary=p.summary
    if p.topics is not None:m.topics='|'.join(p.topics)
    if p.decisions is not None:m.decisions='|'.join(p.decisions)
    db.commit();return mjson(m)
@app.delete('/api/meetings/{mid}')
def delete_meeting(mid:int,db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m:raise HTTPException(404,'Meeting not found')
    rec=Path(m.recording) if m.recording else None
    db.delete(m);db.commit()
    if rec and rec.exists():
        try: rec.unlink()
        except OSError: pass
    return {'ok':True}
@app.patch('/api/tasks/{tid}')
def update_task(tid:int,p:TaskUpdate,db:Session=Depends(db)):
    t=db.get(Task,tid)
    if not t:raise HTTPException(404,'Task not found')
    if p.completed is not None:t.completed=p.completed
    if p.text is not None:t.text=p.text
    if p.owner is not None:t.owner=p.owner
    if p.due is not None:t.due=p.due
    db.commit();return {'ok':True,'id':t.id,'text':t.text,'owner':t.owner,'due':t.due,'completed':t.completed}
@app.delete('/api/tasks/{tid}')
def delete_task(tid:int,db:Session=Depends(db)):
    t=db.get(Task,tid)
    if not t:raise HTTPException(404,'Task not found')
    db.delete(t);db.commit();return {'ok':True}
@app.post('/api/meetings/{mid}/tasks')
def create_task(mid:int,p:TaskCreate,db:Session=Depends(db)):
    if not db.get(Meeting,mid):raise HTTPException(404,'Meeting not found')
    t=Task(meeting_id=mid,text=p.text,owner=p.owner,due=p.due);db.add(t);db.commit();db.refresh(t);return {'id':t.id,'text':t.text,'owner':t.owner,'due':t.due,'completed':t.completed}

@app.post('/api/meetings/{mid}/transcript')
def add_transcript(mid:int,p:TranscriptCreate,db:Session=Depends(db)):
    if not db.get(Meeting,mid): raise HTTPException(404,'Meeting not found')
    text=p.text.strip()
    if not text: raise HTTPException(400,'Transcript text cannot be empty')
    line=TranscriptLine(meeting_id=mid,speaker=p.speaker.strip() or 'Speaker',seconds=max(0,p.seconds),text=text)
    db.add(line); db.commit(); db.refresh(line)
    return {'id':line.id,'speaker':line.speaker,'seconds':line.seconds,'text':line.text}

class TranscriptUpdate(BaseModel): speaker:Optional[str]=None; seconds:Optional[int]=None; text:Optional[str]=None

class TranscriptImport(BaseModel): text:str

@app.post('/api/meetings/{mid}/transcript/import')
def import_transcript(mid:int,p:TranscriptImport,db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m: raise HTTPException(404,'Meeting not found')
    for old in list(m.transcript): db.delete(old)
    for i,line in enumerate(p.text.splitlines()):
        line=line.strip()
        if not line or line.upper().startswith('WEBVTT'): continue
        mt=re.match(r'\[?(\d+):(\d+)(?::(\d+))?\]?\s*(?:[-–]\s*)?([^:]+):\s*(.*)',line)
        if mt:
            h=int(mt.group(1)); mm=int(mt.group(2)); ss=int(mt.group(3) or 0); speaker=mt.group(4).strip(); text=mt.group(5).strip(); seconds=h*60+mm if not mt.group(3) else h*3600+mm*60+ss
        else:
            seconds=i*8; speaker='Speaker'; text=line
        if text: db.add(TranscriptLine(meeting_id=mid,speaker=speaker,seconds=seconds,text=text))
    db.commit()
    return {'ok':True,'lines':db.query(TranscriptLine).filter(TranscriptLine.meeting_id==mid).count()}

@app.patch('/api/transcript/{line_id}')
def edit_transcript(line_id:int,p:TranscriptUpdate,db:Session=Depends(db)):
    line=db.get(TranscriptLine,line_id)
    if not line: raise HTTPException(404,'Transcript line not found')
    if p.speaker is not None: line.speaker=p.speaker.strip() or 'Speaker'
    if p.seconds is not None: line.seconds=max(0,p.seconds)
    if p.text is not None:
        if not p.text.strip(): raise HTTPException(400,'Transcript text cannot be empty')
        line.text=p.text.strip()
    db.commit();db.refresh(line)
    return {'id':line.id,'meeting_id':line.meeting_id,'speaker':line.speaker,'seconds':line.seconds,'text':line.text}

@app.delete('/api/transcript/{line_id}')
def delete_transcript(line_id:int,db:Session=Depends(db)):
    line=db.get(TranscriptLine,line_id)
    if not line: raise HTTPException(404,'Transcript line not found')
    db.delete(line);db.commit();return {'ok':True}

@app.post('/api/meetings/{mid}/recording')
async def upload_recording(mid:int, request:Request, db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m: raise HTTPException(404,'Meeting not found')
    data=await request.body()
    if not data: raise HTTPException(400,'Empty recording')
    safe=re.sub(r'[^a-zA-Z0-9._-]','_',request.headers.get('x-filename') or f'meeting-{mid}.webm')
    folder=RECORDINGS_DIR / str(mid); folder.mkdir(parents=True,exist_ok=True)
    target=folder / safe
    target.write_bytes(data)
    m.recording=str(target)
    db.commit()
    return {'ok':True,'filename':safe,'size':len(data)}

@app.get('/api/meetings/{mid}/recording')
def get_recording(mid:int,db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m or not m.recording: raise HTTPException(404,'Recording not found')
    path=Path(m.recording)
    if not path.exists(): raise HTTPException(404,'Recording file not found')
    media_by_ext={'.webm':'audio/webm','.mp3':'audio/mpeg','.wav':'audio/wav','.m4a':'audio/mp4','.mp4':'video/mp4','.mpeg':'video/mpeg','.mpga':'audio/mpeg','.ogg':'audio/ogg'}
    media=media_by_ext.get(path.suffix.lower(),'application/octet-stream')
    return FileResponse(path,media_type=media,filename=path.name)

@app.get('/api/meetings/{mid}/export')
def export_meeting(mid:int,db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m: raise HTTPException(404,'Meeting not found')
    safe=re.sub(r'[^a-zA-Z0-9._-]+','_',m.title).strip('._') or f'meeting-{mid}'
    transcript='\n'.join(f'[{l.seconds//60:02d}:{l.seconds%60:02d}] {l.speaker}: {l.text}' for l in sorted(m.transcript,key=lambda x:x.seconds))
    tasks=[{'id':t.id,'text':t.text,'owner':t.owner,'due':t.due,'completed':t.completed} for t in m.tasks]
    payload={'id':m.id,'title':m.title,'date':m.date.isoformat(),'duration':m.duration,'participants':arr(m.participants,','),'summary':m.summary,'notes':m.notes or '','topics':arr(m.topics),'decisions':arr(m.decisions),'tags':arr(m.tags,','),'recording_available':bool(m.recording and Path(m.recording).exists()),'tasks':tasks,'transcript':[{'id':l.id,'speaker':l.speaker,'seconds':l.seconds,'text':l.text} for l in sorted(m.transcript,key=lambda x:x.seconds)]}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr(f'{safe}/meeting.json',json.dumps(payload,indent=2,ensure_ascii=False))
        z.writestr(f'{safe}/transcript.txt',transcript or 'No transcript available.')
        z.writestr(f'{safe}/summary.md','# '+m.title+'\n\n'+(m.summary or 'No summary available.'))
        task_buf=io.StringIO(); writer=csv.DictWriter(task_buf,fieldnames=['id','text','owner','due','completed']); writer.writeheader(); writer.writerows(tasks); z.writestr(f'{safe}/tasks.csv',task_buf.getvalue())
        if m.recording and Path(m.recording).exists(): z.write(Path(m.recording),arcname=f'{safe}/recording{Path(m.recording).suffix.lower()}')
    return Response(content=buf.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="{safe}-meeting-data.zip"'})

@app.post('/api/meetings/{mid}/bookmarks')
def bookmark(mid:int,p:BookmarkCreate,db:Session=Depends(db)):
    m=db.get(Meeting,mid);line=db.get(TranscriptLine,p.line_id)
    if not m or not line or line.meeting_id != mid:raise HTTPException(404,'Transcript line not found for this meeting')
    b=Bookmark(meeting_id=mid,line_id=line.id,kind=p.kind,note=p.note,seconds=line.seconds);db.add(b);db.commit();db.refresh(b);return {'id':b.id,'line_id':b.line_id,'kind':b.kind,'note':b.note,'seconds':b.seconds}
@app.delete('/api/bookmarks/{bid}')
def del_bookmark(bid:int,db:Session=Depends(db)):
    b=db.get(Bookmark,bid)
    if not b:raise HTTPException(404,'Bookmark not found')
    db.delete(b);db.commit();return {'ok':True}
@app.post('/api/meetings/{mid}/comments')
def comment(mid:int,p:CommentCreate,db:Session=Depends(db)):
    m=db.get(Meeting,mid); line=db.get(TranscriptLine,p.line_id)
    if not m or not line or line.meeting_id != mid: raise HTTPException(404,'Transcript line not found for this meeting')
    c=Comment(meeting_id=mid,line_id=p.line_id,text=p.text.strip(),author=p.author.strip() or 'User');db.add(c);db.commit();db.refresh(c);return {'id':c.id,'line_id':c.line_id,'text':c.text,'author':c.author,'created':c.created.isoformat()}
@app.delete('/api/comments/{cid}')
def del_comment(cid:int,db:Session=Depends(db)):
    c=db.get(Comment,cid)
    if not c:raise HTTPException(404,'Comment not found')
    db.delete(c);db.commit();return {'ok':True}
@app.post('/api/meetings/{mid}/soundbites')
def soundbite(mid:int,p:SoundbiteCreate,db:Session=Depends(db)):
    if not db.get(Meeting,mid):raise HTTPException(404,'Meeting not found')
    s=Soundbite(meeting_id=mid,title=p.title,start=p.start,end=p.end,text=p.text,access=p.access);db.add(s);db.commit();db.refresh(s);return {'id':s.id,'title':s.title,'start':s.start,'end':s.end,'text':s.text,'access':s.access}
@app.patch('/api/soundbites/{sid}')
def edit_soundbite(sid:int,p:SoundbiteCreate,db:Session=Depends(db)):
    s=db.get(Soundbite,sid)
    if not s:raise HTTPException(404,'Soundbite not found')
    s.title=p.title;s.start=p.start;s.end=p.end;s.text=p.text;s.access=p.access;db.commit();return {'ok':True}
@app.delete('/api/soundbites/{sid}')
def del_soundbite(sid:int,db:Session=Depends(db)):
    s=db.get(Soundbite,sid)
    if not s:raise HTTPException(404,'Soundbite not found')
    db.delete(s);db.commit();return {'ok':True}
@app.post('/api/settings/llm-key')
def set_llm_key(payload:dict):
    key=str(payload.get('key') or '').strip()
    cfg={}
    if CONFIG_PATH.exists():
        try: cfg=json.loads(CONFIG_PATH.read_text())
        except Exception: cfg={}
    cfg['openai_api_key']=key
    CONFIG_PATH.write_text(json.dumps(cfg))
    return {'ok':True,'configured':bool(key)}

class NotesAIRequest(BaseModel):
    title:str='Meeting notes'
    notes:str

@app.post('/api/ai/summarize-notes')
def summarize_notes_ai(p: NotesAIRequest):
    notes=p.notes.strip()
    if not notes: raise HTTPException(400,'Notes cannot be empty')
    sentences=[x.strip() for x in re.split(r'(?<=[.!?])\s+',notes) if x.strip()]
    fallback_summary=' '.join(sentences[:5]) or notes[:500]
    topics=[]
    for token in re.findall(r'[A-Za-z][A-Za-z0-9-]{4,}',notes):
        low=token.lower()
        if low not in topics: topics.append(low)
    result=local_llm_json('Summarize these notes. Return JSON with summary, topics, decisions and action_items. Use only facts from the notes. For unknown owner or due date, use Unassigned and No due date.\n\nTITLE: '+p.title+'\nNOTES:\n'+notes, {'summary':fallback_summary,'topics':topics[:8],'decisions':[],'action_items':[]})
    return {'summary':str(result.get('summary') or fallback_summary),'topics':[str(x) for x in result.get('topics',[])[:8]],'decisions':[str(x) for x in result.get('decisions',[])[:8]],'action_items':result.get('action_items',[])[:8],'mode':result.get('_mode','offline-ai')}

def transcribe_with_openai(data: bytes, filename: str, content_type: str, language: str=''):
    key=configured_key()
    if not key: raise HTTPException(503,'No OpenAI key configured for server transcription')
    boundary='----FirefliesBoundary7MA4YWxkTrZu0gW'
    def field(name,value):
        return (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode()
    model=os.getenv('OPENAI_TRANSCRIBE_MODEL','gpt-4o-transcribe-diarize')
    body=field('model',model)
    if 'transcribe-diarize' in model:
        body+=field('response_format','diarized_json')
        body+=field('chunking_strategy','auto')
    else:
        body+=field('response_format','json')
    if language and language != 'auto' and 'transcribe-diarize' not in model: body+=field('language',language.split('-')[0])
    body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {content_type or "audio/webm"}\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
    req=urllib.request.Request('https://api.openai.com/v1/audio/transcriptions',data=body,headers={'Authorization':f'Bearer {key}','Content-Type':f'multipart/form-data; boundary={boundary}'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=180) as r: result=json.loads(r.read().decode())
        return result
    except urllib.error.HTTPError as e:
        detail=e.read().decode(errors='ignore')
        raise HTTPException(502,f'Transcription service error: {detail[:500]}')
    except Exception as e:
        raise HTTPException(502,f'Transcription service unavailable: {e}')

@app.post('/api/meetings/{mid}/transcribe')
async def transcribe_meeting(mid:int,request:Request,db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m: raise HTTPException(404,'Meeting not found')
    language=request.headers.get('x-language','')
    data=await request.body()
    filename=request.headers.get('x-filename') or ''
    content_type=request.headers.get('content-type','audio/webm')
    if not data or content_type.startswith('application/json'):
        if not m.recording: raise HTTPException(400,'No recording available')
        path=Path(m.recording)
        if not path.exists(): raise HTTPException(404,'Recording file not found')
        data=path.read_bytes(); filename=path.name; content_type='audio/webm' if path.suffix.lower()=='.webm' else 'audio/mpeg'
    key=configured_key()
    if not key:
        existing=sorted(m.transcript,key=lambda x:x.seconds)
        if existing:
            return {'ok':True,'text':' '.join(x.text for x in existing),'lines':len(existing),'mode':'browser-live-transcript'}
        note=(m.notes or '').strip()
        if note:
            for old in list(m.transcript): db.delete(old)
            db.add(TranscriptLine(meeting_id=mid,speaker='Meeting Notes',seconds=0,text=note))
            db.commit()
            return {'ok':True,'text':note,'lines':1,'mode':'offline-notes-transcript'}
        raise HTTPException(503,'Offline transcription is not available for uploaded audio. Use Live Capture for browser speech recognition or paste a transcript file.')
    result=transcribe_with_openai(data,filename or f'meeting-{mid}.webm',content_type,language)
    # Replace transcript with timestamped segments when the provider returns them.
    for old in list(m.transcript): db.delete(old)
    segments=result.get('segments') or result.get('speaker_segments') or []
    if segments:
        for seg in segments:
            text=str(seg.get('text') or '').strip()
            if text:
                speaker=str(seg.get('speaker') or 'Speaker')
                db.add(TranscriptLine(meeting_id=mid,speaker=speaker,seconds=max(0,int(float(seg.get('start') or 0))),text=text))
    else:
        text=str(result.get('text') or '').strip()
        if text:
            # Keep usable timestamp structure even when the model only returns plain text.
            chunks=[x.strip() for x in re.split(r'(?<=[.!?])\s+',text) if x.strip()]
            for i,x in enumerate(chunks): db.add(TranscriptLine(meeting_id=mid,speaker='Speaker',seconds=i*8,text=x))
    db.commit()
    line_count=db.query(TranscriptLine).filter(TranscriptLine.meeting_id==mid).count()
    return {'ok':True,'text':result.get('text',''),'lines':line_count,'mode':'openai-diarized' if 'transcribe-diarize' in os.getenv('OPENAI_TRANSCRIBE_MODEL','gpt-4o-transcribe-diarize') else 'openai-transcribe'}


def build_local_summary(m: Meeting) -> dict:
    """Create a deterministic summary from captured notes/transcript for offline use."""
    lines = sorted(m.transcript, key=lambda x: x.seconds)
    source = (m.notes or '').strip()
    if lines:
        transcript_text = ' '.join(x.text.strip() for x in lines if x.text.strip())
        source = (source + ' ' + transcript_text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', source) if source else []
    sentences = [x.strip() for x in sentences if x.strip()]
    summary = ' '.join(sentences[:4])
    if not summary:
        summary = 'No notes or transcript have been captured yet.'
    topic_words = []
    for token in re.findall(r'[A-Za-z][A-Za-z0-9-]{4,}', source):
        low = token.lower()
        if low not in {'about','there','which','their','would','could','should','meeting','today','hello'} and low not in topic_words:
            topic_words.append(low)
    topics = topic_words[:5]
    decisions = [t.text for t in m.tasks[:5]]
    action_candidates=[]
    for sentence in sentences:
        low=sentence.lower()
        if any(k in low for k in ('we should','need to','action item','follow up','follow-up','will ','let us','let’s','schedule ','send ','prepare ','review ')):
            action_candidates.append(sentence)
    return {'summary': summary, 'topics': topics, 'decisions': decisions, 'actions': action_candidates[:6]}


@app.post('/api/meetings/{mid}/summary')
def generate_summary(mid: int, db: Session = Depends(db)):
    m=db.get(Meeting,mid)
    if not m: raise HTTPException(404,'Meeting not found')
    source='\n'.join(f'[{l.seconds//60:02d}:{l.seconds%60:02d}] {l.speaker}: {l.text}' for l in sorted(m.transcript,key=lambda x:x.seconds))
    source=(m.notes+'\n'+source).strip()
    if not source: raise HTTPException(400,'Add notes or a transcript before generating a summary')
    fallback=build_local_summary(m)
    result=local_llm_json(
        'Summarize this meeting and return JSON with summary (string), topics (array), decisions (array), and action_items (array of objects with text, owner, due). Only use facts present in the meeting.\n\nMEETING: '+m.title+'\n'+source,
        {'summary':fallback['summary'],'topics':fallback['topics'],'decisions':fallback['decisions'],'action_items':[{'text':x,'owner':'Unassigned','due':'No due date'} for x in fallback.get('actions',[])]}
    )
    m.summary=str(result.get('summary') or fallback['summary'])
    m.topics='|'.join(str(x) for x in result.get('topics',[])[:12])
    m.decisions='|'.join(str(x) for x in result.get('decisions',[])[:12])
    db.commit(); db.refresh(m)
    for item in result.get('action_items',[]):
        text=str(item.get('text') or '').strip()
        if text and not any(t.text.lower()==text.lower() for t in m.tasks):
            db.add(Task(meeting_id=m.id,text=text,owner=str(item.get('owner') or 'Unassigned'),due=str(item.get('due') or 'No due date')))
    db.commit()
    return {'summary':m.summary,'topics':arr(m.topics),'decisions':arr(m.decisions),'tasks':[{'id':t.id,'text':t.text,'owner':t.owner,'due':t.due,'completed':t.completed} for t in m.tasks],'mode':result.get('_mode','offline-ai')}

def openai_json(prompt:str,key:str):
    payload=json.dumps({'model':os.getenv('OPENAI_MODEL','gpt-5.6-luna'),'instructions':'Return valid JSON only. You are a meeting intelligence analyst.','input':prompt}).encode()
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=payload,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=60) as r: data=json.loads(r.read().decode())
        text=data.get('output_text','')
        if not text:
            for item in data.get('output',[]):
                for c in item.get('content',[]):
                    if c.get('type')=='output_text': text+=c.get('text','')
        text=text.strip()
        if text.startswith('```'): text=re.sub(r'^```(?:json)?\s*|\s*```$','',text,flags=re.I|re.S)
        return json.loads(text)
    except Exception as e:
        raise HTTPException(502,f'AI analysis failed: {e}')

@app.post('/api/meetings/{mid}/analyze')
def analyze_meeting(mid:int,db:Session=Depends(db)):
    m=db.get(Meeting,mid)
    if not m: raise HTTPException(404,'Meeting not found')
    source='\n'.join(f'[{l.seconds//60:02d}:{l.seconds%60:02d}] {l.speaker}: {l.text}' for l in sorted(m.transcript,key=lambda x:x.seconds))
    source=(m.notes+'\n'+source).strip()
    if not source: raise HTTPException(400,'Add a transcript or notes before analysis')
    result=local_llm_json(
        'Analyze this meeting and return JSON with summary, topics, decisions and action_items (text, owner, due).\n\nMEETING: '+m.title+'\n'+source,
        fallback=build_local_summary(m)
    )
    m.summary=str(result.get('summary') or '')
    m.topics='|'.join(str(x) for x in result.get('topics',[])[:12])
    m.decisions='|'.join(str(x) for x in result.get('decisions',[])[:12])
    for item in result.get('action_items',[])[:12]:
        text=str(item.get('text') or '').strip()
        if text and not any(t.text.lower()==text.lower() for t in m.tasks):
            db.add(Task(meeting_id=m.id,text=text,owner=str(item.get('owner') or 'Unassigned'),due=str(item.get('due') or 'No due date')))
    db.commit()
    return {'summary':m.summary,'topics':arr(m.topics),'decisions':arr(m.decisions),'tasks':len(m.tasks),'mode':result.get('_mode','local')}


def ollama_generate(prompt:str, timeout:float=45):
    """Use a locally installed Ollama model when available; never requires an API key."""
    try:
        payload=json.dumps({'model':os.getenv('FIREFLIES_LOCAL_MODEL','qwen2.5:3b'),'prompt':prompt,'stream':False,'options':{'temperature':0.2}}).encode()
        req=urllib.request.Request('http://127.0.0.1:11434/api/generate',data=payload,headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=timeout) as r:
            data=json.loads(r.read().decode())
        return str(data.get('response') or '').strip() or None
    except Exception:
        return None

def local_llm_json(prompt:str,fallback:dict):
    """Use OpenAI when configured; otherwise use deterministic grounded data."""
    key=configured_key()
    if key:
        try:
            data=openai_json(prompt,key)
            data['_mode']='openai'
            return data
        except HTTPException:
            pass
    data=dict(fallback); data['_mode']='grounded-fallback'; return data

def local_agent_enhanced(question:str, ms:list[Meeting]):
    """Disabled for chat: tiny local generators may hallucinate. Use grounded retrieval unless OpenAI is configured."""
    return None

def configured_key():
    if os.getenv('OPENAI_API_KEY'): return os.getenv('OPENAI_API_KEY')
    if CONFIG_PATH.exists():
        try: return json.loads(CONFIG_PATH.read_text()).get('openai_api_key','')
        except Exception: return ''
    return ''

def local_agent(question:str, ms:list[Meeting]):
    q=question.lower().strip()
    if not ms: return 'I could not find any meetings in your local meeting memory.'
    if any(k in q for k in ('action','task','follow up','follow-up')):
        rows=[]
        for m in ms:
            for t in m.tasks: rows.append(f'• {t.text} — {t.owner} ({t.due}) · {m.title}')
        return 'Here are the action items I found:\n'+'\n'.join(rows[:15]) if rows else 'There are no stored action items yet.'
    if any(k in q for k in ('summar','recap','brief')):
        blocks=[]
        for m in ms[:5]: blocks.append(f'• {m.title}: {m.summary or build_local_summary(m)["summary"]}')
        return 'Meeting summary:\n'+'\n'.join(blocks)
    if 'decision' in q:
        rows=[]
        decision_texts=set()
        for m in ms:
            for d in arr(m.decisions):
                d=str(d).strip()
                if d and d.lower() not in decision_texts:
                    decision_texts.add(d.lower()); rows.append(f'• {m.title}: {d}')
            for t in m.tasks:
                if t.text.strip().lower() not in decision_texts:
                    rows.append(f'• {m.title}: {t.text}')
        return 'Key decisions and commitments:\n'+'\n'.join(rows[:15]) if rows else 'No explicit decisions are stored yet.'
    if 'last 1 min' in q or 'latest context' in q or 'catch up' in q:
        blocks=[]
        for m in ms[:3]:
            lines=sorted(m.transcript,key=lambda x:x.seconds)
            if lines:
                cutoff=max(x.seconds for x in lines)-60
                recent=[x for x in lines if x.seconds>=cutoff]
                blocks.append(f'{m.title}: '+' '.join(f'{x.speaker}: {x.text}' for x in recent))
        return 'Latest meeting context:\n'+'\n'.join(blocks) if blocks else 'There is not enough recent transcript context yet.'
    if 'who said' in q or 'said what' in q or 'participant' in q:
        rows=[]
        for m in ms:
            for l in m.transcript[:20]: rows.append(f'• {m.title} — {l.speaker} at {l.seconds//60:02d}:{l.seconds%60:02d}: {l.text}')
        return 'Speaker moments from the meeting:\n'+'\n'.join(rows[:15]) if rows else 'No transcript speaker lines are available yet.'
    words=[w for w in re.findall(r'[a-z0-9]+',q) if len(w)>3 and w not in {'what','when','where','which','about','meeting','meetings','tell','give','from','this','that','with','have','your','last','open','please','could','would','does','did','are','the','for','show','find','can','you','me','my'}]
    if not words:
        return 'I could not find that in the saved meeting memory. Try asking about a specific meeting, transcript phrase, decision, task, participant, or summary.'
    all_hay=' '.join((m.title+' '+m.summary+' '+m.notes+' '+' '.join(m.topics)+' '+' '.join(m.decisions)+' '+' '.join(l.text for l in m.transcript)).lower() for m in ms)
    matched_terms=sum(1 for w in words if w in all_hay)
    if matched_terms / len(words) < 0.51:
        return 'I could not find that in the saved meeting memory. Try asking about a specific meeting, transcript phrase, decision, task, participant, or summary.'
    hits=[]
    for m in ms:
        hay=(m.title+' '+m.summary+' '+m.notes+' '+' '.join(m.topics)+' '+' '.join(m.decisions)).lower()
        score=sum(1 for w in words if w in hay)
        if score: hits.append((score,m,None))
        for l in m.transcript:
            score=sum(1 for w in words if w in l.text.lower())
            if score: hits.append((score,m,l))
    hits.sort(key=lambda x:x[0],reverse=True)
    if hits:
        out=[]
        for _,m,l in hits[:7]:
            if l: out.append(f'• {m.title} · {l.speaker} · {l.seconds//60:02d}:{l.seconds%60:02d} — {l.text}')
            else: out.append(f'• {m.title}: {m.summary or ", ".join(arr(m.topics)) or "No additional context."}')
        return 'I found these relevant moments:\n'+'\n'.join(out)
    return 'I could not find that in the saved meeting memory. Try asking about a specific meeting, transcript phrase, decision, task, participant, or summary.'

def openai_agent(question:str, context:str, key:str):
    payload=json.dumps({'model':os.getenv('OPENAI_MODEL','gpt-5.6-luna'),'instructions':'You are AskFred, a precise meeting assistant. Use only facts contained in the supplied meeting context. Never invent names, dates, decisions, tasks, quotes, or events. If the answer is not supported by the context, say: I could not find that in the saved meeting memory. Keep answers concise and directly answer the question. Mention the meeting title when useful.','input':f'Question: {question}\n\nMeeting context:\n{context}'}).encode()
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=payload,headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=30) as r: data=json.loads(r.read().decode())
        if data.get('output_text'): return data['output_text']
        parts=[]
        for item in data.get('output',[]):
            for c in item.get('content',[]):
                if c.get('type')=='output_text': parts.append(c.get('text',''))
        return '\n'.join(parts).strip() or None
    except Exception:
        return None

@app.post('/api/ask')
def ask(p:Ask,db:Session=Depends(db)):
    ms=[db.get(Meeting,p.meeting_id)] if p.meeting_id else db.query(Meeting).order_by(Meeting.date.desc()).all()
    ms=[m for m in ms if m]
    if not p.meeting_id and ms:
        stop={'what','when','where','which','about','meeting','meetings','tell','give','from','this','that','with','have','your','last','open','please','could','would','does','did','are','the','for','show','find','can','you','me','my'}
        words=[w for w in re.findall(r'[a-z0-9]+',p.question.lower()) if len(w)>3 and w not in stop]
        if words and not any(k in p.question.lower() for k in ('summar','recap','brief','latest','all meetings','action','task','follow up','decision')):
            scored=[]
            for m in ms:
                hay=(m.title+' '+m.summary+' '+m.notes+' '+' '.join(arr(m.topics))+' '+' '.join(arr(m.decisions))+' '+' '.join(l.text for l in m.transcript)).lower()
                score=sum(1 for w in words if w in hay)
                if score: scored.append((score,m))
            if scored:
                scored.sort(key=lambda x:(x[0],x[1].date.timestamp()),reverse=True)
                ms=[m for _,m in scored[:5]]
            elif words:
                return {'answer':'I could not find that in the saved meeting memory. Try a meeting title, participant, transcript phrase, decision, task, or summary.', 'mode':'grounded-retrieval','sources':[]}
    context='\n\n'.join([
        f'MEETING: {m.title}\nSUMMARY: {m.summary}\nNOTES: {m.notes}\nTOPICS: {", ".join(arr(m.topics))}\nDECISIONS: {", ".join(arr(m.decisions))}\nTASKS: '+
        ' | '.join(f'{t.text} ({t.owner}, {t.due})' for t in m.tasks)+'\nTRANSCRIPT: '+
        ' | '.join(f'{l.speaker} [{l.seconds//60:02d}:{l.seconds%60:02d}] {l.text}' for l in sorted(m.transcript,key=lambda x:x.seconds))
        for m in ms[:8]
    ])
    key=configured_key()
    if key:
        answer=openai_agent(p.question,context,key)
        if answer:
            return {'answer':answer,'mode':'openai','sources':[m.title for m in ms[:5]]}
    answer=local_agent_enhanced(p.question,ms)
    if answer: return {'answer':answer,'mode':'local-llm','sources':[m.title for m in ms[:5]]}
    return {'answer':local_agent(p.question,ms),'mode':'grounded-retrieval','sources':[m.title for m in ms[:5]]}

