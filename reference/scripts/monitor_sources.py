"""Explicitly gated metadata probe; no images or detailed-page crawler."""
import sys,os,re,urllib.request,urllib.error
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_tools.catalog import *
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)
def probe(sources,enabled,opener=None):
    result={'schemaVersion':SCHEMA,'observedAt':datetime.now(timezone.utc).isoformat(),'role':'reference_only','newsItems':[],'observations':[]}
    source=sources['bayou-index']
    if not enabled or not source.get('monitoringApproved') or not source.get('permissionEvidenceUrl'):
        result['status']='disabled_or_permission_unconfirmed';return result
    url=source['indexUrl']
    if url!='https://bayouindex.com/':raise ValidationError('probe URL must be the registered homepage')
    try:
        opener=opener or urllib.request.build_opener(NoRedirect())
        request=urllib.request.Request(url,headers={'User-Agent':'HuntReferenceResearch/0.3 (metadata-only)'})
        with opener.open(request,timeout=4) as r:
            if r.geturl()!=url or 'text/html' not in r.headers.get('Content-Type',''):raise ValidationError('unexpected source response')
            data=r.read(524289)
            if len(data)>524288:raise ValidationError('source too large')
        parser=Text();parser.feed(data.decode('utf8'));text=' '.join(parser.parts)
        patch=re.search(r'Latest patch\s+([0-9]+(?:\.[0-9]+){1,3})',text,re.I)
        result.update(status='candidate_only',observations=[{'sourceUrl':url,'htmlSha256':digest(data),'patchCandidate':patch.group(1) if patch else None,'verificationStatus':'pending_review'}])
    except Exception as e:result.update(status='reference_unavailable',errorType=type(e).__name__)
    return result
if __name__=='__main__':
    result=probe(read(ROOT/'config/sources.json'),os.environ.get('REFERENCE_MONITOR_ENABLED')=='true')
    write(ROOT/'reports/source_probe.json',result);print(result['status'])
