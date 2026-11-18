// Only read public GitHub Issue data. The workflow commits validated encrypted records under schedules/channels/.
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expiry } from './cleanup.mjs';

const kind = 'hunt-shared-schedule-v1';
const source = 'https://api.github.com/repos/tyuio7777/hunt-briefing-guestbook/issues';
const hex = (v,n) => typeof v==='string' && v.length===n && /^[0-9a-f]+$/.test(v);
const b64 = (v,n) => typeof v==='string' && v.length>0 && v.length<=40000 &&
  /^[A-Za-z0-9+/]+={0,2}$/.test(v) && Buffer.from(v,'base64').toString('base64')===v &&
  (!n || Buffer.from(v,'base64').length===n);

export function parseIssue(issue,now=Date.now()){
  if (issue.pull_request || !/^Hunt 공유 일정 · [0-9a-f]{32}$/.test(issue.title) ||
      !Number.isSafeInteger(issue.number) || issue.number<1 || issue.user?.type!=='User' ||
      !Number.isSafeInteger(issue.user.id) || issue.user.id<1 || typeof issue.body!=='string' || issue.body.length>56000) return;
  let value;
  try { value=JSON.parse(issue.body); } catch {return;}
  const e=value?.item;
  if(value?.kind!==kind || !hex(value.channelKey,64) || !hex(value.operationId,32) || !e ||
     !hex(e.id,32) || issue.title!=='Hunt 공유 일정 · '+e.id || !Number.isSafeInteger(e.version) ||
     e.version<1 || e.version>2147483647 || typeof e.deleted!=='boolean')return;
  const opened=Date.parse(issue.created_at),requested=Date.parse(e.createdAt);
  if(!Number.isFinite(opened)||!Number.isFinite(requested)||requested>opened+300000)return;
  const createdAt=new Date(Math.min(opened,requested)).toISOString();
  if(expiry(createdAt)<=now)return;
  const deleted=issue.state==='closed'||e.deleted;
  if(!deleted && (!b64(e.nonce,12)||!b64(e.tag,16)||!b64(e.ciphertext)))return;
  return {key:value.channelKey,record:{id:e.id,version:e.version,createdAt,expiresAt:new Date(expiry(createdAt)).toISOString(),
    deleted,nonce:deleted?'':e.nonce,ciphertext:deleted?'':e.ciphertext,tag:deleted?'':e.tag,
    githubIssue:issue.number,githubAuthorId:issue.user.id,operationId:value.operationId}};
}

export async function publish(issues,directory,now=Date.now()){
  const channels=new Map(),origins=new Map(),changed=new Set();
  for(const name of await readdir(directory)){
    if(!/^[0-9a-f]{64}\.json$/.test(name))continue;
    const doc=JSON.parse(await readFile(join(directory,name),'utf8'));
    if(doc.schemaVersion!==1||!Array.isArray(doc.events))throw Error('Unreadable channel document');
    const key=name.slice(0,-5);channels.set(key,doc);
    for(const e of doc.events)if(e.githubIssue)origins.set(e.githubIssue,[key,e.id]);
  }
  for(const issue of [...issues].sort((a,b)=>a.number-b.number)){
    const parsed=parseIssue(issue,now);if(!parsed)continue;
    const {key,record}=parsed;
    const origin=origins.get(record.githubIssue);
    if(origin&&(origin[0]!==key||origin[1]!==record.id))continue;
    const doc=channels.get(key)??{schemaVersion:1,events:[]};
    const old=doc.events.find(e=>e.id===record.id);
    if(old){
      if(old.githubIssue!==record.githubIssue || old.githubAuthorId!==record.githubAuthorId || old.deleted ||
         record.version<old.version || (record.version===old.version && !record.deleted))continue;
      record.createdAt=old.createdAt;record.expiresAt=old.expiresAt;
    }else if(record.deleted || doc.events.length>=500)continue;
    const next={schemaVersion:1,events:doc.events.filter(e=>e.id!==record.id).concat(record)};
    if(Buffer.byteLength(JSON.stringify(next))>750000)continue;
    channels.set(key,next);origins.set(record.githubIssue,[key,record.id]);changed.add(key);
  }
  for(const key of changed)await writeFile(join(directory,key+'.json'),JSON.stringify(channels.get(key))+'\n');
  return changed.size;
}

async function readIssues(){
  const since=encodeURIComponent(new Date(Date.now()-190*86400000).toISOString());
  const issues=[];
  for(let page=1;;page++){
    const result=await fetch(source+`?state=all&since=${since}&sort=created&direction=asc&per_page=100&page=${page}`,
      {headers:{'User-Agent':'Hunt-Schedule-Publisher',Accept:'application/vnd.github+json'},redirect:'error',signal:AbortSignal.timeout(30000)});
    if(!result.ok)throw Error('Issue inbox unavailable ('+result.status+')');
    const batch=await result.json();if(!Array.isArray(batch))throw Error('Unexpected inbox data');
    issues.push(...batch.filter(i=>i.title?.startsWith('Hunt 공유 일정 · ')));if(batch.length<100)return issues;
  }
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))
  console.log('Updated channels:',await publish(await readIssues(),resolve('schedules/channels')));
