import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_tools.changes import *
p=argparse.ArgumentParser();p.add_argument('before');p.add_argument('after');p.add_argument('--observed-at',required=True);a=p.parse_args()
write(ROOT/'research/reference_change_candidates.json',compare(read(a.before),read(a.after),a.observed_at))
