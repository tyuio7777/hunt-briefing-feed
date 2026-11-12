"""Synthetic TEST ONLY records; no real game claims or reusable signing key."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_tools.catalog import *
from reference_tools.release import sign
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

def fixture():
    cat={k:[] for k in DOMAINS};cat.update(schemaVersion=SCHEMA,snapshotId='test-only-v1',dataVersion='1.0.0',sourcePatch='test-only',generatedAt='2026-11-13T00:00:00+09:00',researchOnly=False,published=True)
    claims=[];url='https://example.invalid/test-only';evidence={'test-proof':{'sourceId':'test-source','url':url,'claims':claims}}
    for d in ('weapons','gear','traits'):
        v={k:None for k in FIELDS[d]};r={k:{'status':'missing','sourceId':None,'sourceUrl':None,'sourcePatch':None,'observedAt':None,'evidenceId':None} for k in v};ident=d+'-test-only'
        for field in REQUIRED_DETAILS[d]:
            typ=FIELDS[d][field];value={'int':7,'number':2.5,'texts':[],'text':'TEST ONLY'}.get(typ)
            if field=='nameEn':value='TEST ONLY '+d
            if field=='customAmmoCoverage':value='none'
            v[field]=value;r[field]={'status':'verified','sourceId':'test-source','sourceUrl':url,'sourcePatch':'test-only','observedAt':'2026-11-13','evidenceId':'test-proof'}
            claims.append({'entityId':ident,'field':field,'valueSha256':digest(encode(value))})
        cat[d].append({'id':ident,'values':v,'fieldReviews':r})
    sources={'test-source':{'dataRedistributionApproved':True,'imageRedistributionApproved':False,'permissionEvidenceUrl':url}}
    review={'approved':True,'catalogSha256':digest(encode(cat)),'reviewer':'TEST ONLY','reviewedAt':'2026-11-13','coverageApproved':True,'rightsApproved':True,'allowedImages':[]}
    return cat,review,sources,evidence

def envelope(cat,key,**overrides):
    raw=encode(cat);sha=digest(raw)
    m={'schemaVersion':SCHEMA,'version':cat['dataVersion'],'snapshotId':cat['snapshotId'],'published':True,'researchOnly':False,'contentSha256':sha,'catalogRelativePath':'snapshots/'+sha+'.json','counts':{d:len(cat[d]) for d in DOMAINS}}
    m.update(overrides);return sign(m,key)

def export(directory):
    import copy
    p=Path(directory);p.mkdir(parents=True,exist_ok=True);cat,*_=fixture();key=ec.generate_private_key(ec.SECP256R1())
    (p/'public.pem').write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    (p/'valid.json').write_bytes(encode(cat));(p/'valid.manifest.json').write_bytes(envelope(cat,key))
    variants={}
    bad=copy.deepcopy(cat);del bad['weapons'][0]['values']['damage'];variants['missing']=bad
    bad=copy.deepcopy(cat);bad['traits'][0]['fieldReviews']['costPoints']['status']='unverified';variants['unverified']=bad
    bad=copy.deepcopy(cat);bad['published']=False;bad['researchOnly']=True;variants['draft']=bad
    bad=copy.deepcopy(cat);bad['weapons'][0]['values']['variantOfId']='traits-test-only';bad['weapons'][0]['fieldReviews']['variantOfId']=bad['weapons'][0]['fieldReviews']['nameEn'].copy();variants['wrongrelation']=bad
    for name,bad in variants.items():
        (p/(name+'.json')).write_bytes(encode(bad));(p/(name+'.manifest.json')).write_bytes(envelope(bad,key))
    (p/'path.manifest.json').write_bytes(envelope(cat,key,catalogRelativePath='https://other.invalid/steal.json'))
    # Key deliberately never serialized; each test run creates a fresh pair.
if __name__=='__main__':export(sys.argv[1])
