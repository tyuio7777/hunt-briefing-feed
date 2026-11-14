"""Validate and stage an atomic loadout release; never writes outside reference/loadout.
Usage: python reference/scripts/publish_loadout.py --catalog path --rules path --sequence N [--output reference/loadout/v1]
Commit ALL staged snapshot/manifest files in one Git commit. Keep the previous snapshots.
"""
import argparse,hashlib,json,datetime,re
from pathlib import Path
from urllib.parse import urlparse
DOMAINS=('weapons','ammo','gear','traits','skins','images')
def encode(x):return (json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def validate(c,r):
 assert c['schemaVersion']=='1.0.0' and c['dataVersion']
 assert r['schemaVersion']==1 and r['weaponPositions']==2 and r['equipmentSlots']==8 and 1<=r['baseWeaponCapacity']<=10
 ids={}
 for domain in DOMAINS:
  assert isinstance(c[domain],list) and len(c[domain])<=5000
  if domain in ('weapons','gear','traits'):assert len(c[domain])>0
  for i in c[domain]:
   assert re.fullmatch('[a-z][a-z0-9-]{0,119}',i['id']) and i['id'] not in ids
   ids[i['id']]=(domain,i);assert i['values']['nameEn']
   for k,v in i['values'].items():
    if type(v) in (int,float):assert v>=0 and abs(v)<1e12
    if v is not None and k not in ('nameEn','nameKo'):
     review=i['fieldReviews'][k];assert review['status']=='verified' and review.get('evidenceId')
     u=urlparse(review['sourceUrl']);assert u.scheme=='https' and not u.username and u.hostname in ('bayouindex.com','www.huntshowdown.com','huntshowdown.com','store.steampowered.com','steamcommunity.com','github.com')
 for a in c['ammo']:
  assert a['values']['weaponId'] in ids and ids[a['values']['weaponId']][0]=='weapons'
 for w in c['weapons']:
  for aid in w['values'].get('customAmmoIds') or []:assert ids[aid][0]=='ammo' and ids[aid][1]['values']['weaponId']==w['id']
 return True
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True);p.add_argument('--rules',type=Path,required=True);p.add_argument('--sequence',type=int,required=True);p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'loadout/v1');a=p.parse_args()
 c=json.loads(a.catalog.read_text());r=json.loads(a.rules.read_text());validate(c,r)
 assert a.sequence>0
 active=a.output/'active.json'
 if active.exists():assert a.sequence>json.loads(active.read_text())['sequence'],'Sequence must increase'
 published=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
 bundle={'schemaVersion':1,'sequence':a.sequence,'publishedAt':published,'catalog':c,'rules':r}
 data=encode(bundle);sha=hashlib.sha256(data).hexdigest();relative='snapshots/'+sha+'.json'
 dest=a.output/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 manifest={'schemaVersion':1,'sequence':a.sequence,'publishedAt':published,'path':relative,'sha256':sha}
 active.write_bytes(encode(manifest));print(json.dumps({'sha256':sha,'bytes':len(data),'sequence':a.sequence}))
