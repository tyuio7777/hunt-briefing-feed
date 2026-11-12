import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fixtures_factory import fixture,envelope
from reference_tools.catalog import *
from reference_tools.release import *
from reference_tools.changes import compare
from scripts.monitor_sources import probe
from unittest.mock import patch
from scripts.export_public import export,collect

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.cat,self.review,self.sources,self.evidence=fixture();self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        write(self.root/'config/repository.json',{'repository':'tyuio7777/hunt-briefing-feed','managedPrefix':'reference/'})
        write(self.root/'config/sources.json',self.sources);write(self.root/'research/evidence.json',self.evidence)
        self.key=ec.generate_private_key(ec.SECP256R1())
    def tearDown(self):self.temp.cleanup()
    def validate(self):return validate(self.cat,True,self.sources,self.evidence)
    def publish(self):return publish(self.root,self.cat,self.review,self.sources,self.evidence,self.key)
    def test_good_signed_snapshot(self):
        self.publish();m=verify((self.root/'catalog/v1/active.json').read_bytes(),self.key.public_key());self.assertEqual(m['contentSha256'],digest(encode(self.cat)))
    def test_missing_price_is_not_zero(self):
        item=self.cat['weapons'][0];item['values']['priceHuntDollars']=None;item['fieldReviews']['priceHuntDollars']['status']='missing'
        with self.assertRaises(ValidationError):self.validate()
        self.assertIsNone(item['values']['priceHuntDollars'])
    def test_duplicate_keys_rejected(self):
        with self.assertRaises(ValidationError):loads('{"x":0,"x":1}')
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValidationError):loads('{"x":NaN}')
    def test_duplicate_ids_rejected(self):
        self.cat['gear'][0]['id']=self.cat['weapons'][0]['id']
        with self.assertRaises(ValidationError):self.validate()
    def test_wrong_relation_rejected(self):
        self.cat['weapons'][0]['values']['variantOfId']=self.cat['traits'][0]['id']
        with self.assertRaises(ValidationError):self.validate()
    def test_evidence_value_bound(self):
        self.cat['weapons'][0]['values']['damage']=999
        with self.assertRaisesRegex(ValidationError,'evidence'):self.validate()
    def test_evidence_source_bound(self):
        self.evidence['test-proof']['sourceId']='unrelated'
        with self.assertRaisesRegex(ValidationError,'evidence'):self.validate()
    def test_rights_gate(self):
        self.sources['test-source']['dataRedistributionApproved']=False
        with self.assertRaises(ValidationError):self.publish()
        self.assertFalse((self.root/'catalog').exists())
    def test_review_bound_to_hash(self):
        self.cat['dataVersion']='1.0.1'
        with self.assertRaises(ValidationError):self.publish()
    def test_research_never_published(self):
        self.cat.update(researchOnly=True,published=False);self.review['catalogSha256']=digest(encode(self.cat))
        with self.assertRaises(ValidationError):self.publish()
    def test_bad_update_preserves_active(self):
        self.publish();p=self.root/'catalog/v1/active.json';before=p.read_bytes();self.cat['weapons']=[]
        with self.assertRaises(ValidationError):self.publish()
        self.assertEqual(before,p.read_bytes())
    def test_partial_write_keeps_active(self):
        self.publish();p=self.root/'catalog/v1/active.json';before=p.read_bytes();self.cat['dataVersion']='1.0.1';self.review['catalogSha256']=digest(encode(self.cat))
        with patch('reference_tools.release.atomic',side_effect=OSError('test disk full')):
            with self.assertRaises(OSError):self.publish()
        self.assertEqual(before,p.read_bytes())
    def test_verified_rollback(self):
        self.publish();before=(self.root/'catalog/v1/active.json').read_bytes();self.cat['dataVersion']='1.0.1';self.review['catalogSha256']=digest(encode(self.cat));self.publish()
        rollback(self.root,'1.0.0',self.key.public_key());self.assertEqual(before,(self.root/'catalog/v1/active.json').read_bytes())
    def test_version_immutable(self):
        self.publish();self.cat['generatedAt']='2026-11-14';self.review['catalogSha256']=digest(encode(self.cat))
        with self.assertRaisesRegex(ValidationError,'version'):self.publish()
    def test_signature_tampering(self):
        e=loads(envelope(self.cat,self.key));e['payload']=base64.b64encode(b'{}').decode()
        with self.assertRaises(Exception):verify(encode(e),self.key.public_key())
    def test_nested_symlink_rejected(self):
        target=self.root/'catalog/v1';target.mkdir(parents=True);(target/'snapshots').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValidationError):self.publish()
    def test_lock_prevents_concurrent_publication(self):
        with release_lock(self.root):
            with self.assertRaises(FileExistsError):self.publish()
    def test_unapproved_image_blocked(self):
        image={'id':'image-test','values':{f:None for f in FIELDS['images']},'fieldReviews':{f:{'status':'missing','sourceId':None,'sourceUrl':None,'observedAt':None,'sourcePatch':None,'evidenceId':None} for f in FIELDS['images']}}
        image['values'].update(nameEn='TEST ONLY',licenseStatus='unverified',redistributionApproved=False,localFile='assets/'+'a'*64+'.webp')
        self.cat['images']=[image]
        with self.assertRaises(ValidationError):self.validate()
    def test_monitor_off_makes_no_calls(self):
        class Never:
            def open(*a,**k):raise AssertionError('network forbidden')
        source={'bayou-index':{'indexUrl':'https://bayouindex.com/','monitoringApproved':True,'permissionEvidenceUrl':'TEST'}}
        self.assertEqual(probe(source,False,Never())['newsItems'],[])
        source['bayou-index']['monitoringApproved']=False
        self.assertEqual(probe(source,True,Never())['status'],'disabled_or_permission_unconfirmed')
    def test_monitor_failure_isolated(self):
        class Broken:
            def open(*a,**k):raise TimeoutError('TEST ONLY')
        result=probe({'bayou-index':{'indexUrl':'https://bayouindex.com/','monitoringApproved':True,'permissionEvidenceUrl':'TEST'}},True,Broken())
        self.assertEqual(result['status'],'reference_unavailable');self.assertEqual(result['newsItems'],[])
    def test_change_history(self):
        before=copy.deepcopy(self.cat);before.update(researchOnly=True,published=False);after=copy.deepcopy(before);after['sourcePatch']='test-next';after['weapons'][0]['values']['damage']=4.5
        out=compare(before,after,'2026-11-13');self.assertFalse(out['published']);self.assertEqual(len(out['changes']),1);c=out['changes'][0]
        self.assertEqual((c['previousValue'],c['candidateValue'],c['sourcePatch']),(2.5,4.5,'test-next'));self.assertEqual(c['sourceUrl'],'https://example.invalid/test-only')
    def test_export_omits_private_research(self):
        write(self.root/'research/private.json',{'secret':'TEST ONLY MUST NOT SHIP'})
        write(self.root/'catalog/v1/status.json',{'published':False})
        files=collect(self.root)
        self.assertTrue(files);self.assertFalse(any('research' in str(x.relative_to(self.root)) for x in files))
    def test_export_rejects_unsigned_active(self):
        write(self.root/'catalog/v1/active.json',{'published':True})
        with self.assertRaises((OSError,ValueError)):collect(self.root)
    def test_export_rejects_symlink(self):
        (self.root/'README.md').symlink_to(self.root/'research/evidence.json')
        with self.assertRaises(ValidationError):collect(self.root)
    @unittest.skipUnless((ROOT/'research/catalog/catalog.json').exists(),'private research bundle not present')
    def test_private_seed_counts_and_null_ammo(self):
        cat=read(ROOT/'research/catalog/catalog.json');validate(cat,evidence=read(ROOT/'research/evidence.json'))
        self.assertEqual([len(cat[d]) for d in ('weapons','gear','traits')],[161,68,65]);self.assertTrue(all(x['values']['priceHuntDollars'] is None for x in cat['ammo']))
if __name__=='__main__':unittest.main()
