import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_tools.catalog import *
if __name__=='__main__':
    cat=normalize() if '--build' in sys.argv else read(ROOT/'research/catalog/catalog.json')
    validate(cat,evidence=read(ROOT/'research/evidence.json'))
    print(json.dumps(report(cat),ensure_ascii=False,indent=2))
