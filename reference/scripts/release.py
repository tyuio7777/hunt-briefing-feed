import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_tools.release import *
p=argparse.ArgumentParser();p.add_argument('action',choices=['check','publish','rollback']);p.add_argument('--catalog',type=Path,default=ROOT/'research/catalog/catalog.json');p.add_argument('--key',type=Path);p.add_argument('--version');a=p.parse_args()
try:
    if a.action=='rollback':
        if not a.key:raise ValidationError('public key required')
        print(rollback(ROOT,a.version,serialization.load_pem_public_key(a.key.read_bytes())))
    else:
        args=[read(a.catalog),read(ROOT/'config/publication-review.json'),read(ROOT/'config/sources.json'),read(ROOT/'research/evidence.json')]
        if a.action=='check':print(public_gate(*args))
        else:
            if not a.key:raise ValidationError('private signing key required')
            print(publish(ROOT,*args,serialization.load_pem_private_key(a.key.read_bytes(),password=None)))
except (ValueError,OSError) as e:print('BLOCKED:',e,file=sys.stderr);sys.exit(2)
