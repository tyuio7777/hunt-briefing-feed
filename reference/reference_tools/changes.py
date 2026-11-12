"""Propose changes without modifying reviewed catalogs or briefing files."""
from .catalog import *

def compare(before,after,observed_at):
    validate(before);validate(after)
    changes=[]
    for domain in DOMAINS:
        old={x['id']:x for x in before[domain]};new={x['id']:x for x in after[domain]}
        for ident in sorted(old.keys()|new.keys()):
            for field in FIELDS[domain]:
                a=old.get(ident,{}).get('values',{}).get(field);b=new.get(ident,{}).get('values',{}).get(field)
                if a==b and ident in old and ident in new:continue
                r=(new.get(ident) or old[ident])['fieldReviews'][field]
                changes.append({'domain':domain,'entityId':ident,'field':field,'change':'added' if ident not in old else 'removed' if ident not in new else 'modified','previousValue':a,'candidateValue':b,'sourceUrl':r['sourceUrl'],'previousSourcePatch':before['sourcePatch'],'sourcePatch':after['sourcePatch'],'observedAt':observed_at,'verificationStatus':'pending_review'})
    return {'schemaVersion':SCHEMA,'previousSha256':digest(encode(before)),'candidateSha256':digest(encode(after)),'changes':changes,'published':False}
