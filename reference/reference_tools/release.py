"""Immutable signed snapshots and one atomic active pointer, confined to this repo."""
import base64, os, re, tempfile
from contextlib import contextmanager
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from .catalog import *

def atomic(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.reference-')
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def sign(payload,private_key):
    if not isinstance(private_key,ec.EllipticCurvePrivateKey) or not isinstance(private_key.curve,ec.SECP256R1):raise ValidationError('ECDSA P-256 key required')
    raw=encode(payload)
    return encode({'algorithm':'ECDSA-P256-SHA256-DER','payload':base64.b64encode(raw).decode(),'signature':base64.b64encode(private_key.sign(raw,ec.ECDSA(hashes.SHA256()))).decode()})

def verify(envelope,public_key):
    if len(envelope)>65536:raise ValidationError('oversized envelope')
    e=loads(envelope)
    if set(e)!= {'algorithm','payload','signature'} or e['algorithm']!='ECDSA-P256-SHA256-DER':raise ValidationError('bad envelope')
    if not isinstance(public_key,ec.EllipticCurvePublicKey) or not isinstance(public_key.curve,ec.SECP256R1):raise ValidationError('P-256 public key required')
    raw=base64.b64decode(e['payload'],validate=True);signature=base64.b64decode(e['signature'],validate=True)
    public_key.verify(signature,raw,ec.ECDSA(hashes.SHA256()));m=loads(raw)
    if set(m)!={'schemaVersion','version','snapshotId','published','researchOnly','contentSha256','catalogRelativePath','counts'}:raise ValidationError('manifest keys mismatch')
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',m['version']) or set(m['counts'])!=set(DOMAINS) or any(type(v) is not int or v<0 for v in m['counts'].values()):raise ValidationError('manifest version/counts invalid')
    if m.get('schemaVersion')!=SCHEMA or m.get('published') is not True or m.get('researchOnly') is not False:raise ValidationError('not a public manifest')
    if not re.fullmatch(r'snapshots/[a-f0-9]{64}\.json',m.get('catalogRelativePath','')):raise ValidationError('unsafe catalog path')
    if m['catalogRelativePath']!='snapshots/'+m.get('contentSha256','')+'.json':raise ValidationError('path/hash mismatch')
    return m

def public_gate(cat,review,sources,evidence):
    expected=digest(encode(cat))
    if review.get('approved') is not True or review.get('catalogSha256')!=expected or not all(review.get(x) for x in ('reviewer','reviewedAt','coverageApproved','rightsApproved')):raise ValidationError('release review missing or for a different snapshot')
    validate(cat,public=True,sources=sources,evidence=evidence)
    if any(w['values']['customAmmoCoverage'] not in ('complete','none') for w in cat['weapons']):raise ValidationError('ammo compatibility survey incomplete')
    return expected

def destination(root):
    root=Path(root).resolve()
    marker=read(root/'config/repository.json')
    if marker.get('repository')!='tyuio7777/hunt-briefing-feed' or marker.get('managedPrefix')!='reference/':raise ValidationError('wrong repository marker')
    target=root/'catalog/v1'
    if target.resolve()!=target or any(p.is_symlink() for p in (root/'catalog',target)):raise ValidationError('symlink destination forbidden')
    if target.exists() and any(p.is_symlink() for p in target.rglob('*')):raise ValidationError('symlink below destination forbidden')
    return target

def _publish(root,cat,review,sources,evidence,key):
    # No filesystem mutation occurs before all content/rights gates pass.
    sha=public_gate(cat,review,sources,evidence);target=destination(root)
    assets=approved_assets(root,cat,review)
    version=cat['dataVersion']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version):raise ValidationError('release version must be semver')
    payload={'schemaVersion':SCHEMA,'version':version,'snapshotId':cat['snapshotId'],'published':True,'researchOnly':False,'contentSha256':sha,'catalogRelativePath':f'snapshots/{sha}.json','counts':{d:len(cat[d]) for d in DOMAINS}}
    envelope=sign(payload,key);verify(envelope,key.public_key())
    snapshot=target/payload['catalogRelativePath'];manifest=target/'manifests'/f'{version}.json'
    if manifest.exists() and verify(manifest.read_bytes(),key.public_key())['contentSha256']!=sha:raise ValidationError('version already used')
    # Reuse an existing immutable signature rather than changing a released envelope.
    if manifest.exists():envelope=manifest.read_bytes()
    if snapshot.exists() and snapshot.read_bytes()!=encode(cat):raise ValidationError('immutable snapshot conflict')
    for relative,data in assets:atomic(target/relative,data)
    atomic(snapshot,encode(cat));atomic(manifest,envelope)
    active=target/'active.json'
    if active.exists():atomic(target/'previous.json',active.read_bytes())
    atomic(active,envelope)
    return payload

def _rollback(root,version,public_key):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version):raise ValidationError('bad version')
    target=destination(root);raw=(target/'manifests'/f'{version}.json').read_bytes();m=verify(raw,public_key)
    data=(target/m['catalogRelativePath']).read_bytes()
    if digest(data)!=m['contentSha256']:raise ValidationError('rollback checksum mismatch')
    # Previously approved signature is the authority; do not bypass with an unsigned draft.
    cat=loads(data);validate(cat,public=True,sources=read(Path(root)/'config/sources.json'),evidence=read(Path(root)/'research/evidence.json'))
    atomic(target/'active.json',raw)
    return m


def approved_assets(root,cat,review):
    assets=[];allowed=set(review.get('allowedImages',[]))
    for item in cat['images']:
        v=item['values'];relative=v['localFile']
        if item['id'] not in allowed or not isinstance(v['sha256'],str) or relative!='assets/'+v['sha256']+'.webp':raise ValidationError('image not specifically approved')
        source=Path(root)/'research/approved-assets'/relative
        base=(Path(root)/'research/approved-assets').resolve()
        if source.resolve()!=source or not source.resolve().is_relative_to(base):raise ValidationError('unsafe source asset')
        data=source.read_bytes()
        if len(data)>4_000_000 or digest(data)!=v['sha256'] or data[:4]!=b'RIFF' or data[8:12]!=b'WEBP':raise ValidationError('asset checksum/type/size mismatch')
        assets.append((relative,data))
    return assets

@contextmanager
def release_lock(root):
    target=destination(root);target.mkdir(parents=True,exist_ok=True)
    lock=target/'.release.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:yield
    finally:os.close(fd);lock.unlink()

def publish(root,cat,review,sources,evidence,key):
    # Fail before even creating a lock for unapproved research.
    public_gate(cat,review,sources,evidence)
    with release_lock(root):return _publish(root,cat,review,sources,evidence,key)

def rollback(root,version,public_key):
    with release_lock(root):return _rollback(root,version,public_key)
