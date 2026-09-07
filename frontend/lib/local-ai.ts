/* Credential-free on-device meeting AI.
 * Transformers.js is loaded from a public ESM CDN on first use. The models are
 * downloaded once and cached by the Chromium profile, then inference runs locally.
 */

type ModuleLike = {
  pipeline: (task: string, model: string, options?: any) => Promise<any>;
};

declare global {
  interface Window {
    __ffTransformers?: ModuleLike;
    __ffTransformersPromise?: Promise<ModuleLike>;
  }
}

const CDN = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.2.0';
const TEXT_MODEL = 'onnx-community/Qwen2.5-0.5B-Instruct';
const ASR_MODEL = 'Xenova/whisper-tiny';
const BACKEND_API = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || 'http://localhost:8000/api';

export type LocalMeetingContext = {
  title: string;
  summary?: string;
  notes?: string;
  topics?: string[];
  decisions?: string[];
  transcript?: { speaker: string; seconds: number; text: string }[];
  tasks?: { text: string; owner: string; due: string; completed: boolean }[];
};

export type ProgressHandler = (value: number, message?: string) => void;

export async function loadTransformers(): Promise<ModuleLike> {
  if (typeof window === 'undefined') throw new Error('Local AI is only available in the app window.');
  if (window.__ffTransformers?.pipeline) return window.__ffTransformers;
  if (window.__ffTransformersPromise) return window.__ffTransformersPromise;

  window.__ffTransformersPromise = new Promise<ModuleLike>((resolve, reject) => {
    let settled = false;
    const finish = (fn: (v: any) => void, value: any) => {
      if (settled) return;
      settled = true;
      window.removeEventListener('ff:transformers-ready', ready as EventListener);
      fn(value);
    };
    const ready = () => {
      if (window.__ffTransformers?.pipeline) finish(resolve, window.__ffTransformers);
      else finish(reject, new Error('Transformers.js loaded without a pipeline export.'));
    };
    window.addEventListener('ff:transformers-ready', ready as EventListener, { once: true });

    const script = document.createElement('script');
    script.type = 'module';
    script.textContent = `import * as mod from ${JSON.stringify(CDN)}; window.__ffTransformers = mod; window.dispatchEvent(new Event('ff:transformers-ready'));`;
    script.onerror = () => finish(reject, new Error('Could not load the local AI runtime. Internet access is required on first use.'));
    document.head.appendChild(script);
  });

  return window.__ffTransformersPromise;
}

function pickDevice() {
  return typeof navigator !== 'undefined' && (navigator as any).gpu ? 'webgpu' : 'wasm';
}

let llmPromise: Promise<any> | null = null;
let asrPromise: Promise<any> | null = null;

export async function getMeetingLLM(onProgress?: ProgressHandler) {
  if (!llmPromise) {
    llmPromise = (async () => {
      const { pipeline } = await loadTransformers();
      const device = pickDevice();
      const progress_callback = (p: any) => {
        const fraction = typeof p?.progress === 'number' ? Math.max(0, Math.min(100, p.progress)) / 100 : 0;
        onProgress?.(fraction, p?.file || p?.status || 'Loading meeting AI…');
      };
      if (device === 'webgpu') {
        try {
          return await pipeline('text-generation', TEXT_MODEL, { device: 'webgpu', dtype: 'q4f16', progress_callback });
        } catch {}
      }
      try {
        return await pipeline('text-generation', TEXT_MODEL, { device: 'wasm', dtype: 'q8', progress_callback });
      } catch {
        return await pipeline('text-generation', TEXT_MODEL, { device: 'wasm', dtype: 'q4f16', progress_callback });
      }
    })();
  }
  return llmPromise;
}

export function contextText(contexts: LocalMeetingContext[], extra?: string) {
  const selected = contexts.slice(0, 8);
  const blocks = selected.map((m) => {
    const transcript = (m.transcript || [])
      .slice()
      .sort((a, b) => a.seconds - b.seconds)
      .map((l) => `[${formatSeconds(l.seconds)}] ${l.speaker}: ${l.text}`)
      .join('\n');
    const tasks = (m.tasks || []).map((t) => `- ${t.text} — ${t.owner} (${t.due})${t.completed ? ' [done]' : ''}`).join('\n');
    return `MEETING: ${m.title}\nSUMMARY: ${m.summary || '(none)'}\nTOPICS: ${(m.topics || []).join(', ')}\nDECISIONS: ${(m.decisions || []).join(', ')}\nTASKS:\n${tasks || '(none)'}\nNOTES: ${m.notes || '(none)'}\nTRANSCRIPT:\n${transcript || '(none)'}`;
  });
  return `${blocks.join('\n\n').slice(0, 26000)}${extra ? `\n\nCURRENT MEETING CONTEXT:\n${extra.slice(0, 9000)}` : ''}`;
}

export async function askMeetingAI(question: string, contexts: LocalMeetingContext[], onProgress?: ProgressHandler, meetingId?: number) {
  onProgress?.(0, 'Checking meeting AI…');
  try {
    const response = await fetch(`${BACKEND_API}/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, meeting_id: meetingId }) });
    if (response.ok) { const data = await response.json(); if (data?.answer) { onProgress?.(1, data.mode === 'openai' ? 'OpenAI ready' : 'Safe meeting retrieval ready'); return String(data.answer); } }
  } catch {}
  return groundedBrowserAnswer(question, contexts);
}

function groundedBrowserAnswer(question: string, contexts: LocalMeetingContext[]) {
  const q = question.toLowerCase().trim();
  const words = (q.match(/[a-z0-9]+/g) || []).filter(w => w.length > 3 && !new Set(['what','when','where','which','about','meeting','meetings','tell','give','from','this','that','with','have','your','last','open','please','could','would','does','did','are','the','for','show','find','can','you','me','my']).has(w));
  if (!contexts.length) return 'I could not find any meetings in your saved meeting memory.';
  if (/summar|recap|brief/.test(q)) return contexts.slice(0,5).map(m => `• ${m.title}: ${m.summary || 'No saved summary.'}`).join('\n');
  if (/action|task|follow up|follow-up/.test(q)) { const rows=contexts.flatMap(m => (m.tasks||[]).map(t=>`• ${t.text} — ${t.owner} (${t.due}) · ${m.title}`)); return rows.length ? rows.slice(0,15).join('\n') : 'There are no stored action items yet.'; }
  if (/decision/.test(q)) { const rows=contexts.flatMap(m=>(m.decisions||[]).map(d=>`• ${m.title}: ${d}`)); return rows.length ? rows.slice(0,15).join('\n') : 'No explicit decisions are stored yet.'; }
  const hits:string[]=[];
  for (const m of contexts) {
    const fields=[m.title,m.summary||'',m.notes||'',...(m.topics||[]),...(m.decisions||[])].join(' ').toLowerCase();
    const score=words.filter(w=>fields.includes(w)).length;
    if(score>0) hits.push(`• ${m.title}: ${m.summary || m.notes || (m.transcript||[]).slice(0,2).map(l=>l.text).join(' ') || 'Relevant meeting context found.'}`);
    for(const l of m.transcript||[]) { const line=l.text.toLowerCase(); if(words.some(w=>line.includes(w))) hits.push(`• ${m.title} · ${l.speaker} · ${formatSeconds(l.seconds)} — ${l.text}`); }
  }
  if(!words.length || !hits.length) return 'I could not find that in the saved meeting memory. Configure an OpenAI API key in Settings → Meeting AI for full LLM answers.';
  return hits.slice(0,10).join('\n');
}

export async function askLocalMeetingAI(question: string, contexts: LocalMeetingContext[], onProgress?: ProgressHandler) {
  const llm = await getMeetingLLM(onProgress);
  const context = contextText(contexts);
  const messages = [
    {
      role: 'system',
      content:
        'You are AskFred, a precise meeting copilot. Answer only from the supplied meeting memory. Never invent facts. Use concise, useful bullets when appropriate. When the answer is not in the context, say that clearly. You can summarize, compare meetings, find decisions, identify owners, extract action items, draft follow-up messages, and prepare the user for meetings.',
    },
    {
      role: 'user',
      content: `Question: ${question}\n\nMeeting memory:\n${context}`,
    },
  ];

  onProgress?.(0, 'Thinking…');
  const output = await llm(messages, { max_new_tokens: 260, temperature: 0.2, do_sample: true });
  const raw = output?.[0]?.generated_text;
  let text = '';
  if (typeof raw === 'string') text = raw;
  else if (Array.isArray(raw)) text = String(raw[raw.length - 1]?.content || '');
  else text = String(raw?.content || output?.[0]?.text || '');
  onProgress?.(1, 'Ready');
  return text.replace(/^\s*assistant\s*/i, '').trim();
}

function audioLanguage(code: string) {
  const map: Record<string, string> = {
    'en-US': 'english', 'en-IN': 'english', 'hi-IN': 'hindi', 'es-ES': 'spanish', 'fr-FR': 'french',
    'de-DE': 'german', 'it-IT': 'italian', 'pt-BR': 'portuguese', 'ja-JP': 'japanese', 'ko-KR': 'korean',
    'zh-CN': 'chinese', 'ar-SA': 'arabic', 'ru-RU': 'russian', 'auto': undefined as any,
  };
  return map[code] || undefined;
}

export async function transcribeAudio(blob: Blob, languageCode = 'auto', onProgress?: ProgressHandler) {
  if (!asrPromise) {
    asrPromise = (async () => {
      const { pipeline } = await loadTransformers();
      const device = pickDevice();
      const progress_callback = (p: any) => {
        const fraction = typeof p?.progress === 'number' ? Math.max(0, Math.min(100, p.progress)) / 100 : 0;
        onProgress?.(fraction, p?.file || p?.status || 'Loading speech model…');
      };
      try {
        return await pipeline('automatic-speech-recognition', ASR_MODEL, { device, progress_callback });
      } catch {
        return await pipeline('automatic-speech-recognition', ASR_MODEL, { device: 'wasm', progress_callback });
      }
    })();
  }
  const transcriber = await asrPromise;
  const url = URL.createObjectURL(blob);
  try {
    const options: any = {
      task: 'transcribe',
      return_timestamps: true,
      chunk_length_s: 30,
      stride_length_s: 5,
    };
    const language = audioLanguage(languageCode);
    if (language) options.language = language;
    const result = await transcriber(url, options);
    const chunks = Array.isArray(result?.chunks) ? result.chunks : [];
    if (chunks.length) {
      return chunks
        .map((chunk: any, i: number) => ({
          seconds: Array.isArray(chunk.timestamp) && Number.isFinite(chunk.timestamp[0]) ? Math.max(0, Math.floor(chunk.timestamp[0])) : i * 8,
          text: String(chunk.text || '').trim(),
        }))
        .filter((x: any) => x.text);
    }
    return result?.text ? [{ seconds: 0, text: String(result.text).trim() }] : [];
  } finally {
    URL.revokeObjectURL(url);
  }
}


export type LocalMeetingAnalysis = {
  summary: string;
  topics: string[];
  decisions: string[];
  action_items: { text: string; owner: string; due: string }[];
};

function extractJson(raw: string) {
  const cleaned = raw.replace(/^\s*```(?:json)?\s*/i, '').replace(/\s*```\s*$/i, '').trim();
  try { return JSON.parse(cleaned); } catch {}
  const start = cleaned.indexOf('{');
  const end = cleaned.lastIndexOf('}');
  if (start >= 0 && end > start) {
    try { return JSON.parse(cleaned.slice(start, end + 1)); } catch {}
  }
  return null;
}

export async function analyzeMeetingLocally(context: LocalMeetingContext, onProgress?: ProgressHandler): Promise<LocalMeetingAnalysis> {
  // Safe browser fallback: do not run a tiny generative model for meeting analysis.
  // Full LLM analysis is handled by the backend when an OpenAI key is configured.
  onProgress?.(0, 'Preparing grounded meeting analysis…');
  const transcriptText = (context.transcript || []).slice().sort((a,b)=>a.seconds-b.seconds).map(x=>x.text.trim()).filter(Boolean);
  const source = [context.notes || '', context.summary || '', ...transcriptText].join(' ').trim();
  const sentences = (source.match(/[^.!?\n]+[.!?]?/g) || []).map(x=>x.trim()).filter(Boolean);
  const summary = context.summary?.trim() || sentences.slice(0,4).join(' ') || 'No summary generated yet.';
  const topicWords:string[]=[];
  for(const w of (source.match(/[A-Za-z][A-Za-z0-9-]{5,}/g)||[])) {
    const low=w.toLowerCase();
    if(!['meeting','today','there','about','because','should','could','would'].includes(low) && !topicWords.includes(low)) topicWords.push(low);
  }
  const decisions = (context.decisions||[]).slice(0,12);
  const action_items = (context.tasks||[]).filter(t=>!t.completed).slice(0,12).map(t=>({text:t.text,owner:t.owner||'Unassigned',due:t.due||'No due date'}));
  onProgress?.(1, 'Grounded meeting analysis ready');
  return {summary,topics:(context.topics||[]).length?(context.topics||[]).slice(0,12):topicWords.slice(0,8),decisions,action_items};
}

export async function summarizeNotesWithAI(title: string, notes: string, onProgress?: ProgressHandler): Promise<LocalMeetingAnalysis> {
  onProgress?.(0, 'Summarizing notes with AI…');
  try {
    const response = await fetch(`${BACKEND_API}/ai/summarize-notes`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,notes})});
    if (response.ok) { const data=await response.json(); onProgress?.(1,data.mode==='openai'?'OpenAI summary ready':'Summary ready'); return {summary:String(data.summary||''),topics:Array.isArray(data.topics)?data.topics.map(String):[],decisions:Array.isArray(data.decisions)?data.decisions.map(String):[],action_items:Array.isArray(data.action_items)?data.action_items.map((x:any)=>({text:String(x?.text||''),owner:String(x?.owner||'Unassigned'),due:String(x?.due||'No due date')})).filter((x:any)=>x.text):[]}; }
  } catch {}
  return analyzeMeetingLocally({title,notes,transcript:[]},onProgress);
}

export function formatSeconds(total: number) {
  const s = Math.max(0, Math.floor(total || 0));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}
