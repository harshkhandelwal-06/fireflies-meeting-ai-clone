export const API=process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000/api';
export async function getMeetings(q=''){const r=await fetch(`${API}/meetings${q?`?q=${encodeURIComponent(q)}`:''}`,{cache:'no-store'});return r.json()}
export async function getMeeting(id:number){const r=await fetch(`${API}/meetings/${id}`,{cache:'no-store'});if(!r.ok)throw Error('Not found');return r.json()}
export async function uploadBinary(path:string,body:BodyInit,contentType:string,filename:string){const r=await fetch(API+path,{method:'POST',headers:{'Content-Type':contentType,'X-Filename':filename},body});if(!r.ok)throw Error(await r.text());return r.json()}
export async function api(path:string,init?:RequestInit){const r=await fetch(API+path,{...init,headers:{'Content-Type':'application/json',...(init?.headers||{})}});if(!r.ok)throw Error(await r.text());return r.json()}
