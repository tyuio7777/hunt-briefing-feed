import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference_tools.catalog import ROOT,DOMAINS,read,validate,digest,ValidationError
from reference_tools.source_literal import Reader,LiteralError

class LiteralTests(unittest.TestCase):
    def test_devalue_shared_record_without_execution(self):
        value=Reader('(function(a){a.en="Packmule";return {name:a,cost:4}}({}))').value()
        self.assertEqual(value,{'name':{'en':'Packmule'},'cost':4})
    def test_data_syntax(self):
        self.assertEqual(Reader('{x:.25,n:void 0,y:!0,z:`a\\nline`}').value(),{'x':.25,'n':None,'y':True,'z':'a\nline'})
    def test_executable_source_is_rejected(self):
        for s in ['alert("bad")','(function(){alert("bad");return 2}())','`${fetch("bad")}`','{a:1,a:2}']:
            with self.subTest(s=s),self.assertRaises(LiteralError):Reader(s).value()

STAGE=ROOT/'staging/bayou-2026-11-13'
@unittest.skipUnless(STAGE.exists(),'staging snapshot not present')
class EnrichmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat=read(STAGE/'catalog.json');cls.detail=read(STAGE/'details.json')['items']
        cls.byid={i['id']:i for d in DOMAINS for i in cls.cat[d]}
    def value(self,id):return self.byid[id]['values']
    def test_schema_relations_and_value_bound_provenance(self):
        validate(self.cat,evidence=read(STAGE/'evidence.json'))
    def test_current_roster_and_stable_identifiers(self):
        aliases=read(ROOT/'config/bayou-id-aliases.json')
        for domain,count in [('weapons',161),('gear',68),('traits',65)]:
            self.assertEqual(len(self.cat[domain]),count)
            self.assertEqual({i['id'] for i in self.cat[domain]},set(aliases[domain].values()))
        self.assertTrue('skin-skin-deep-silencer' in self.byid)
        self.assertEqual(len(self.cat['ammo']),516)
    def test_source_conflicts_are_not_guessed(self):
        self.assertIsNone(self.value('gear-the-high-priestess')['durationSeconds'])
        self.assertIsNone(self.value('ammo-drilling-dragon-breath-secondary')['effects'])
        self.assertIsNone(self.value('ammo-drilling-slug-secondary')['damage'])
    def test_world_only_is_not_free(self):
        self.assertIsNone(self.value('weapon-shredder')['priceHuntDollars'])
        self.assertIsNone(self.value('gear-the-temperance')['priceHuntDollars'])
        self.assertIsNone(self.value('trait-berserker')['costPoints'])
        self.assertIsNone(self.value('ammo-drilling-subsonic-ammo')['priceHuntDollars'])
        self.assertEqual(self.value('trait-quartermaster')['costPoints'],8)
    def test_card_and_model_damage_not_mixed(self):
        self.assertEqual(self.value('weapon-burgess')['damage'],207)
        self.assertEqual(self.detail['weapon-burgess']['bayouDisplayDamage'],240)
        self.assertEqual(self.value('ammo-burgess-slug')['damage'],163)
    def test_tools_are_identified_separately_from_weapon_index(self):
        tools=[x for x in self.cat['weapons'] if self.detail[x['id']]['inventoryDomain']=='gear']
        self.assertEqual(len(tools),11)
        for item in tools:self.assertTrue(self.detail[item['id']]['canonicalInventoryId'].startswith('gear-'))
    def test_images_have_no_implied_license_or_bytes(self):
        self.assertEqual(self.cat['images'],[])
        candidates=read(STAGE/'image-candidates.json')
        self.assertEqual(len(candidates['images']),1626)
        for item in candidates['images']:
            self.assertTrue(item['relatedId'] in self.byid)
            self.assertFalse(item['redistributionApproved']);self.assertIsNone(item['localFile']);self.assertIsNone(item['sha256'])
    def test_staging_hashes_and_disabled_runtime(self):
        m=read(STAGE/'manifest.json')
        for name,sha in m['files'].items():self.assertEqual(digest((STAGE/name).read_bytes()),sha)
        self.assertEqual(digest((STAGE/'catalog.json').read_bytes()),m['catalogSha256'])
        self.assertFalse(m['published']);self.assertFalse(m['appIntegrationEnabled'])
        self.assertFalse((ROOT/'catalog/v1/active.json').exists())
        self.assertEqual(read(ROOT/'config/features.json')['mode'],'disabled')
        with self.assertRaises(ValidationError):validate(self.cat,public=True,sources=read(ROOT/'config/sources.json'),evidence=read(STAGE/'evidence.json'))

if __name__=='__main__':unittest.main()
