"""Create an allowlisted public tree; never include research, keys or feed files."""
import shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_tools.catalog import *
from reference_tools.release import verify
from cryptography.hazmat.primitives import serialization

def collect(root):
    root=Path(root).resolve();selected=set()
    for pattern in ['README.md','.gitignore','requirements*.txt','global.json','config/*.json','schema/*.json','reference_tools/*.py','scripts/*.py','src/Hunt.ReferenceData/*.cs','src/Hunt.ReferenceData/*.csproj','tests/*.py','tests/Hunt.ReferenceData.Tests/*.cs','tests/Hunt.ReferenceData.Tests/*.csproj','docs/*_KO.md','workflow-templates/*.yml','reports/completeness.json','catalog/v1/status.json']:
        selected.update(root.glob(pattern))
    selected.discard(root/'docs/ORIGINAL_REQUEST_KO.md')
    # Curated numeric facts and original summaries are separate from private raw
    # research and signed runtime releases. Unknown image rights never ship bytes.
    allowed={'catalog.json','details.json','evidence.json','coverage.json','image-candidates.json','review-issues.json'}
    for file in (root/'staging').glob('*/manifest.json'):
        m=read(file)
        if m.get('researchOnly') is not True or m.get('published') is not False or m.get('appIntegrationEnabled') is not False:
            raise ValidationError('staging cannot activate runtime')
        if set(m.get('files',{}))!=allowed: raise ValidationError('unexpected staging file set')
        for name,sha in m['files'].items():
            p=file.parent/name
            if digest(p.read_bytes())!=sha: raise ValidationError('staging checksum mismatch')
            selected.add(p)
        cat=read(file.parent/'catalog.json');validate(cat,evidence=read(file.parent/'evidence.json'))
        if cat['images']: raise ValidationError('staging image binaries are not approved')
        for candidate in read(file.parent/'image-candidates.json')['images']:
            if candidate.get('redistributionApproved') or candidate.get('localFile') or candidate.get('sha256'):
                raise ValidationError('unapproved staging image')
        selected.add(file)
    base=root/'catalog/v1';active=base/'active.json'
    if active.exists():
        keypath=root/'config/trusted-public-key.pem';key=serialization.load_pem_public_key(keypath.read_bytes());selected.add(keypath)
        active_manifest=verify(active.read_bytes(),key)
        files=list((base/'manifests').glob('*.json'))+[active]
        if (base/'previous.json').exists():files.append(base/'previous.json')
        seen=set()
        for file in files:
            m=verify(file.read_bytes(),key);snapshot=base/m['catalogRelativePath'];data=snapshot.read_bytes()
            if digest(data)!=m['contentSha256']:raise ValidationError('export checksum mismatch')
            cat=loads(data);validate(cat,True,read(root/'config/sources.json'),read(root/'research/evidence.json'))
            if cat['dataVersion']!=m['version'] or cat['snapshotId']!=m['snapshotId'] or {d:len(cat[d]) for d in DOMAINS}!=m['counts']:raise ValidationError('manifest metadata mismatch')
            for item in cat['images']:
                v=item['values'];asset=base/v['localFile']
                if digest(asset.read_bytes())!=v['sha256']:raise ValidationError('export asset checksum mismatch')
                selected.add(asset)
            selected.update([file,snapshot]);seen.add(m['version'])
        if active_manifest['version'] not in seen:raise ValidationError('active manifest missing')
    for file in selected:
        if file.resolve()!=file or not file.is_file() or not file.is_relative_to(root):raise ValidationError('unsafe export path')
        if file.suffix=='.pem' and b'PRIVATE KEY' in file.read_bytes():raise ValidationError('private key export forbidden')
    return sorted(selected)

def export(root,destination):
    root=Path(root).resolve();destination=Path(destination).resolve();files=collect(root)
    if destination.exists() and any(destination.iterdir()):raise ValidationError('export destination must be empty')
    if destination==root or destination.is_relative_to(root):raise ValidationError('export outside the research checkout')
    for file in files:
        output=destination/file.relative_to(root);output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,output)
    return [str(file.relative_to(root)) for file in files]
if __name__=='__main__':
    files=export(ROOT,sys.argv[1]);print(json.dumps({'files':files,'count':len(files),'containsResearch':False},ensure_ascii=False,indent=2))

