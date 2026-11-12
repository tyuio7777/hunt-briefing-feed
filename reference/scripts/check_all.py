"""Run isolated tests, using temporary synthetic keys/data, never production feed."""
import os,subprocess,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def run(*args):subprocess.run(args,cwd=root,check=True)
run(sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py','-v')
with tempfile.TemporaryDirectory(prefix='hunt-reference-fixtures-') as directory:
    run(sys.executable,'tests/fixtures_factory.py',directory)
    run(os.environ.get('REFERENCE_DOTNET','dotnet'),'run','--project','tests/Hunt.ReferenceData.Tests','--',directory)
