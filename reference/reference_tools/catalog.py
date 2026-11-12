"""Offline catalog normalization and validation; never imports the briefing system."""
from __future__ import annotations
import csv, hashlib, json, re, unicodedata
from collections import Counter
from pathlib import Path
from jsonschema import Draft202012Validator
ROOT=Path(__file__).resolve().parents[1]
DOMAINS=('weapons','ammo','gear','traits','skins','images')
SCHEMA='1.0.0'
# Every value has its own provenance. null is unknown, never zero/free/unsupported.
FIELDS={
 'weapons':{'nameEn':'text','nameKo':'text','variantOfId':'id','ammoClass':'text','priceHuntDollars':'int','damage':'number','velocityMps':'number','dropMeters':'number','cycleSeconds':'number','slots':'int','capacity':'int','reserveAmmo':'int','reloadSeconds':'number','customAmmoIds':'ids','customAmmoCoverage':'text','unlockCondition':'text','imageAssetId':'id'},
 'ammo':{'nameEn':'text','weaponId':'id','priceHuntDollars':'int','slots':'int','damage':'number','velocityMps':'number','dropMeters':'number','effects':'text','imageAssetId':'id'},
 'gear':{'nameEn':'text','nameKo':'text','kind':'text','priceHuntDollars':'int','packCount':'int','effect':'text','durationSeconds':'number','damage':'number','rangeMeters':'number','unlockCondition':'text','lightStamina':'number','heavyStamina':'number','lightDamage':'number','heavyDamage':'number','reachMeters':'number','imageAssetId':'id'},
 'traits':{'nameEn':'text','nameKo':'text','category':'text','costPoints':'int','acquisition':'texts','flags':'texts','effectKo':'text','effectStructured':'object','conditions':'text','equipmentIds':'ids','imageAssetId':'id'},
 'skins':{'nameEn':'text','nameKo':'text','kind':'text','baseItemId':'id','baseItemName':'text','releaseDate':'text','acquisition':'text','availability':'text','eventOrDlc':'text','imageAssetId':'id'},
 'images':{'nameEn':'text','relatedId':'id','candidateUrl':'url','licenseStatus':'text','redistributionApproved':'bool','localFile':'text','sha256':'text','licenseEvidenceUrl':'url','attribution':'text'}
}
# Optional/non-applicable fields remain listed in the full gap report but not mandatory to ship.
REQUIRED_DETAILS={
 'weapons':['nameEn','ammoClass','priceHuntDollars','damage','velocityMps','dropMeters','cycleSeconds','slots','customAmmoCoverage'],
 'ammo':['nameEn','weaponId','priceHuntDollars','slots','damage','velocityMps','dropMeters','effects'],
 'gear':['nameEn','kind','priceHuntDollars','packCount','effect','unlockCondition'],
 'traits':['nameEn','category','costPoints','acquisition','flags','effectKo','conditions'],
 'skins':['nameEn','kind','baseItemName','releaseDate','acquisition','availability','eventOrDlc'],
 'images':['nameEn','relatedId','licenseStatus','redistributionApproved','localFile','sha256','licenseEvidenceUrl','attribution']
}
class ValidationError(ValueError):pass

def encode(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def digest(data):return hashlib.sha256(data).hexdigest()
def no_duplicates(pairs):
    out={}
    for key,value in pairs:
        if key in out:raise ValidationError('duplicate JSON property: '+key)
        out[key]=value
    return out
def loads(data):return json.loads(data,object_pairs_hook=no_duplicates,parse_constant=lambda x:(_ for _ in ()).throw(ValidationError('nonfinite JSON')))
def read(path):return loads(Path(path).read_bytes())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encode(value))
def stable_id(domain,name):
    slug=re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode().lower()).strip('-')
    return domain.rstrip('s')+'-'+slug

def schema():
    types={'text':{'type':['string','null'],'minLength':1},'id':{'type':['string','null'],'pattern':r'^[a-z][a-z0-9-]+$'},'url':{'type':['string','null'],'pattern':r'^https://[^\s]+$'},'int':{'type':['integer','null'],'minimum':0},'number':{'type':['number','null'],'minimum':0},'bool':{'type':['boolean','null']},'ids':{'type':['array','null'],'items':{'type':'string','pattern':r'^[a-z][a-z0-9-]+$'},'uniqueItems':True},'texts':{'type':['array','null'],'items':{'type':'string'},'uniqueItems':True},'object':{'type':['object','null']}}
    review={'type':'object','additionalProperties':False,'required':['status','sourceId','sourceUrl','observedAt','sourcePatch','evidenceId'], 'properties':{'status':{'enum':['missing','unverified','verified','not_applicable']},**{k:{'type':['string','null']} for k in ['sourceId','sourceUrl','observedAt','sourcePatch','evidenceId']}}}
    props={'schemaVersion':{'const':SCHEMA},'snapshotId':{'type':'string','pattern':r'^[a-z0-9][a-z0-9.-]+$'},'dataVersion':{'type':'string'},'sourcePatch':{'type':['string','null']},'generatedAt':{'type':'string'},'researchOnly':{'type':'boolean'},'published':{'type':'boolean'}}
    for domain in DOMAINS:
        values={k:types[t] for k,t in FIELDS[domain].items()}
        item={'type':'object','additionalProperties':False,'required':['id','values','fieldReviews'],'properties':{'id':{'type':'string','pattern':r'^[a-z][a-z0-9-]+$'},'values':{'type':'object','additionalProperties':False,'required':list(values),'properties':values},'fieldReviews':{'type':'object','additionalProperties':False,'required':list(values),'properties':{k:review for k in values}}}}
        props[domain]={'type':'array','items':item,'maxItems':20000,'minItems':1 if domain in ('weapons','gear','traits') else 0}
    return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:hunt-reference:catalog:1.0.0','type':'object','additionalProperties':False,'required':list(props),'properties':props}

def normalize():
    original=read(ROOT/'research/imports/v0.2_catalog.json');images=read(ROOT/'research/imports/v0.2_images.json')
    cat={k:[] for k in DOMAINS};cat.update(schemaVersion=SCHEMA,snapshotId='research-20261112-v0.3.0',dataVersion='0.3.0',sourcePatch=original['sourcePatch'],generatedAt='2026-11-12T23:00:00+09:00',researchOnly=True,published=False)
    ids={d:{e['nameEn']:stable_id(d,e['nameEn']) for e in original[d]} for d in ('weapons','gear','traits','skins')}
    def record(domain,ident,values,url,source='bayou-index'):
        vals={k:values.get(k) for k in FIELDS[domain]}
        reviews={k:{'status':'missing' if v is None else 'unverified','sourceId':source,'sourceUrl':url,'observedAt':original['snapshotDate'],'sourcePatch':original['sourcePatch'] if source=='bayou-index' else None,'evidenceId':None} for k,v in vals.items()}
        return {'id':ident,'values':vals,'fieldReviews':reviews}
    for domain in ('weapons','gear','traits','skins'):
        for e in original[domain]:
            vals=dict(e)
            if domain=='weapons':
                vals['customAmmoIds']=None;vals['customAmmoCoverage']=None
                if e['customAmmo']:
                    vals['customAmmoIds']=[]
                    for a in e['customAmmo']:
                        aid=stable_id('ammo',e['nameEn']+'-'+a['ammoNameEn']);vals['customAmmoIds'].append(aid)
                        cat['ammo'].append(record('ammo',aid,{'nameEn':a['ammoNameEn'],'weaponId':ids[domain][e['nameEn']],'priceHuntDollars':a['priceHuntDollars']},e['sourceUrl']))
                    vals['customAmmoCoverage']='partial'
            if domain=='gear':vals.update(e.get('verifiedDetails',{}))
            if domain=='skins':vals['baseItemId']=ids['weapons'].get(e['baseItemName'])
            cat[domain].append(record(domain,ids[domain][e['nameEn']],vals,e['sourceUrl'],'steam-crytek' if domain=='skins' else 'bayou-index'))
    for e in images:
        related=next((ids[d][e['relatedName']] for d in ids if e['relatedName'] in ids[d]),None)
        cat['images'].append(record('images','image-'+e['assetId'],{'nameEn':e['relatedName'],'relatedId':related,'candidateUrl':e['candidateUrl'],'licenseStatus':'unverified','redistributionApproved':False},e['candidateUrl']))
    # Only primary-source corroboration; not a public redistribution approval.
    evidence=read(ROOT/'research/evidence.json')
    for skin in cat['skins']:
        values=skin['values'];old_name=values['nameEn']
        values.update(nameEn='Skin Deep' if old_name.startswith('Skin Deep') else old_name,releaseDate='2026-10-07',acquisition='DLC',eventOrDlc='Bound by Blood')
        for field in ('nameEn','kind','baseItemName','releaseDate','acquisition','eventOrDlc'):
            skin['fieldReviews'][field].update(status='verified',sourcePatch=None,evidenceId='steam-bound-by-blood-20261112')
    validate(cat)
    write(ROOT/'schema/catalog-v1.schema.json',schema());write(ROOT/'research/catalog/catalog.json',cat)
    write(ROOT/'research/catalog/draft_manifest.json',{'schemaVersion':SCHEMA,'researchOnly':True,'published':False,'contentSha256':digest(encode(cat)),'appIntegrationEnabled':False,'counts':{k:len(cat[k]) for k in DOMAINS}})
    return cat

def validate(cat,public=False,sources=None,evidence=None):
    errors=sorted(Draft202012Validator(schema()).iter_errors(cat),key=lambda e:str(list(e.path)))
    if errors:raise ValidationError(str(errors[0]))
    all_ids=[x['id'] for d in DOMAINS for x in cat[d]]
    if len(all_ids)!=len(set(all_ids)):raise ValidationError('duplicate stable ID')
    by_id={x['id']:d for d in DOMAINS for x in cat[d]}
    for domain in DOMAINS:
        names=set()
        for item in cat[domain]:
            v=item['values'];key=(str(v['nameEn']).casefold(),v.get('baseItemId'),v.get('weaponId'))
            if key in names:raise ValidationError('duplicate name within domain/base item')
            names.add(key)
            for f,value in v.items():
                review=item['fieldReviews'][f];status=review['status']
                if status in ('missing','not_applicable') and value is not None:raise ValidationError('missing value must be null')
                if value is None and status not in ('missing','not_applicable'):raise ValidationError('null cannot be a verified fact')
                if status in ('verified','not_applicable'):
                    if not all(review.get(k) for k in ('sourceId','sourceUrl','observedAt','evidenceId')):raise ValidationError('verified field requires evidence')
                    if evidence is not None:
                        e=evidence.get(review['evidenceId'])
                        if not e or e.get('sourceId')!=review['sourceId'] or e.get('url')!=review['sourceUrl'] or not any(c['entityId']==item['id'] and c['field']==f and c['valueSha256']==digest(encode(value)) for c in e.get('claims',[])):raise ValidationError('evidence does not attest this value')
                if public and (value is not None or f in REQUIRED_DETAILS[domain]) and status not in ('verified','not_applicable'):raise ValidationError('unreviewed field: '+item['id']+'/'+f)
                if public and status in ('verified','not_applicable'):
                    source=(sources or {}).get(review['sourceId'],{})
                    if not source.get('dataRedistributionApproved') or not source.get('permissionEvidenceUrl'):raise ValidationError('source rights not approved')
            for field,target in [('variantOfId','weapons'),('weaponId','weapons'),('imageAssetId','images'),('relatedId',None),('baseItemId',None)]:
                value=v.get(field)
                if value and (value not in by_id or target and by_id[value]!=target):raise ValidationError('dangling/wrong-domain relation '+field)
            for field,target in [('customAmmoIds','ammo'),('equipmentIds',None)]:
                for ident in v.get(field) or []:
                    if ident not in by_id or target and by_id[ident]!=target:raise ValidationError('dangling array relation')
            if domain=='images':
                approved=v['redistributionApproved'] is True and v['licenseStatus']=='approved' and v['licenseEvidenceUrl'] is not None
                if not approved and (v['localFile'] is not None or v['sha256'] is not None):raise ValidationError('unapproved image binary')
                if public and not approved:raise ValidationError('unapproved image in public catalog')
                if public and not (sources or {}).get(item['fieldReviews']['licenseStatus']['sourceId'],{}).get('imageRedistributionApproved'):raise ValidationError('image source rights not approved')
                if v['localFile'] is not None and not re.fullmatch(r'assets/[a-f0-9]{64}\.webp',v['localFile']):raise ValidationError('unsafe asset path')
    weapons={x['id']:x for x in cat['weapons']}
    for ammo in cat['ammo']:
        weapon=weapons.get(ammo['values']['weaponId'])
        if weapon and ammo['id'] not in (weapon['values']['customAmmoIds'] or []):raise ValidationError('ammo relation not reciprocal')
    if public and (cat['researchOnly'] or not cat['published']):raise ValidationError('research snapshot cannot be published')
    if not public and (not cat['researchOnly'] or cat['published']):raise ValidationError('research input must remain unpublished')
    return True

def report(cat):
    summary={};rows=[]
    for domain in DOMAINS:
        counters=Counter();required=verified=0
        for item in cat[domain]:
            for field,value in item['values'].items():
                status=item['fieldReviews'][field]['status'];counters[status]+=1
                required+=field in REQUIRED_DETAILS[domain]
                verified+=field in REQUIRED_DETAILS[domain] and status in ('verified','not_applicable')
                if status not in ('verified','not_applicable'):rows.append({'domain':domain,'id':item['id'],'name':item['values']['nameEn'],'field':field,'status':status,'value':json.dumps(value,ensure_ascii=False),'sourceUrl':item['fieldReviews'][field]['sourceUrl']})
        summary[domain]={'records':len(cat[domain]),'fields':dict(counters),'requiredFields':required,'reviewedRequiredFields':verified,'reviewedRequiredPercent':round(100*verified/required,2) if required else None}
    write(ROOT/'reports/completeness.json',summary)
    with (ROOT/'reports/detail_gaps.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['domain','id','name','field','status','value','sourceUrl']);w.writeheader();w.writerows(rows)
    return summary
