import {readdir,readFile,writeFile,unlink} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
export function expiry(createdAt){
 const d=new Date(Date.parse(createdAt)+9*3600000);if(!Number.isFinite(d.getTime()))throw Error('Invalid creation time');
 const day=d.getUTCDate();d.setUTCDate(1);d.setUTCMonth(d.getUTCMonth()+6);
 d.setUTCDate(Math.min(day,new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,0)).getUTCDate()));return d.getTime()-9*3600000;
}
export function prune(document,now=Date.now()){
 if(document.schemaVersion!==1||!Array.isArray(document.events))throw Error('Invalid schedule document');
 // Registration date is authoritative. Editing expiresAt cannot extend retention.
 return {schemaVersion:1,events:document.events.filter(e=>expiry(e.createdAt)>now)};
}
export async function cleanup(directory,now=Date.now()){
 let removed=0;
 for(const name of await readdir(directory)){
  if(!/^[a-f0-9]{64}\.json$/.test(name))continue;
  const file=join(directory,name),doc=JSON.parse(await readFile(file,'utf8')),next=prune(doc,now);
  if(next.events.length===doc.events.length)continue;
  if(!next.events.length)await unlink(file);else await writeFile(file,JSON.stringify(next)+'\n');
  removed+=doc.events.length-next.events.length;
 }
 return removed;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 console.log('Expired encrypted records removed:',await cleanup(resolve('schedules/channels')));
}
