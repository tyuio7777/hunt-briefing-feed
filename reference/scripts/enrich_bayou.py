"""Build an unpublished, source-observed factual catalog from an offline cache.

No network, signing, active manifest, app configuration or briefing writes.
Raw HTML, JS, translated lore and image bytes are NOT exported.
"""
import argparse, json, re, sys
from pathlib import Path
from lxml import html
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference_tools.catalog import DOMAINS, FIELDS, encode, digest, stable_id, validate, write
from reference_tools.source_literal import Reader, hydration
from scripts.fetch_bayou import ORIGIN, cache_name, roster_links

DATE='2026-11-13'
PATCH='2.9.1'
VERSION='0.4.0-research.20261113'
ROOT=Path(__file__).resolve().parents[1]

def build(cache, output):
    summaries=json.loads((ROOT/'config/bayou-summaries-ko.json').read_text())
    aliases=json.loads((ROOT/'config/bayou-id-aliases.json').read_text())
    def ident(domain,name): return aliases.get(domain,{}).get(name,stable_id(domain,name))
    catalog={d:[] for d in DOMAINS}
    catalog.update(schemaVersion='1.0.0',snapshotId='bayou-20261113-0.4.0',dataVersion=VERSION,
                   sourcePatch=PATCH,generatedAt=DATE+'T00:00:00Z',researchOnly=True,published=False)
    evidence={};details={};images=[];issues=[]
    def proof(path):
        key='bayou-'+path.strip('/').replace('/','-')+'-20261113'
        raw=(cache/cache_name(path)).read_bytes()
        evidence.setdefault(key,{'sourceId':'bayou-index','url':ORIGIN+path,'observedAt':DATE,
            'sourcePatch':PATCH,'sourceSha256':digest(raw),'verification':'source_observed_not_independently_game_verified','claims':[]})
        return key
    def record(domain,id,vals,path,derived=()):
        key=proof(path);reviews={};values={f:vals.get(f) for f in FIELDS[domain]}
        for field,value in values.items():
            reviews[field]={'status':'missing' if value is None else 'verified','sourceId':'bayou-index',
                'sourceUrl':ORIGIN+path,'observedAt':DATE,'sourcePatch':PATCH,'evidenceId':key if value is not None else None}
            if value is not None:
                evidence[key]['claims'].append({'entityId':id,'field':field,'valueSha256':digest(encode(value)),
                    'method':'mapped_or_summarized_source_fact' if field in derived else 'source_observation'})
        item={'id':id,'values':values,'fieldReviews':reviews};catalog[domain].append(item);return item
    def image_candidate(id,name,url,path):
        if url:
            images.append({'relatedId':id,'nameEn':name,'candidateUrl':ORIGIN+url if url.startswith('/') else url,
                'sourceUrl':ORIGIN+path,'observedAt':DATE,'licenseStatus':'unverified','redistributionApproved':False,
                'localFile':None,'sha256':None,'attribution':'Game artwork and trademarks: Crytek; reference: Bayou Index.'})
    source={};pages={}
    gear_text=(cache/'gear-data.js').read_text()
    match=re.search(r'\bvar\s+\w+=\{buildId:',gear_text)
    if not match: raise ValueError('Gear bundle data declaration changed')
    gear_snapshot=Reader(gear_text,gear_text.index('{',match.start())).value()
    bundle_policy=json.loads((ROOT/'config/bayou-source-snapshot.json').read_text())
    gear_by_name={x['names']['en']:x for x in gear_snapshot['items']}
    for domain in ('weapons','gear','traits'):
        source[domain]=[]
        for path in roster_links((cache/(domain+'.html')).read_bytes(),domain):
            document=(cache/cache_name(path)).read_text();data=hydration(document)[-1]
            if domain=='gear':
                name=html.fromstring(document).xpath('//h1')[0].text_content().strip()
                obj=gear_by_name[name]
            else:obj=data['weapon' if domain=='weapons' else 'trait'];name=obj['names']['en']
            id=ident(domain,name);source[domain].append((id,name,obj,path,data));pages[id]=path
    source_ids={domain:{o['id']:id for id,name,o,path,data in rows} for domain,rows in source.items()}
    name_ids={domain:{name:id for id,name,o,path,data in rows} for domain,rows in source.items()}
    def skins(base,base_name,domain,obj,path,page):
        # Sidearms/melee tools appear in both source indexes. The inventory item owns its skins once.
        if domain=='weapons' and base_name in name_ids['gear']: return
        for skin in obj.get('legendaries') or []:
            # Unreleased/withdrawn entries in a downloaded bundle are not active catalog items.
            start=(page.get('skinStarts') or {}).get(skin['id'])
            if skin.get('withdrawn') or (skin.get('hiddenBy') and not (start and start[:10]<=DATE)):continue
            name=skin['names']['en'];id=aliases.get('skins',{}).get(base+'|'+name,'skin-'+skin['id'].lower());route=skin.get('route') or {}
            title=route.get('title') or {};event=title.get('en') if isinstance(title,dict) else title
            dlc=skin.get('dlc');dlc=dlc.get('en') if isinstance(dlc,dict) else dlc
            record('skins',id,{'nameEn':name,'kind':domain[:-1] if domain.endswith('s') else domain,
                'baseItemId':base,'baseItemName':base_name,'acquisition':route.get('kind') or ('DLC' if skin.get('dlc') else None),
                'releaseDate':start[:10] if start else None,
                'eventOrDlc':dlc or event},path,('kind','baseItemId'))
            details[id]={'sourceUrl':ORIGIN+path,'sourceId':skin['id'],'releasePack':skin.get('releasePack'),
                'priceBloodBonds':skin.get('priceBloodBonds'),'onSale':skin.get('onSale'),
                'acquisitionFlags':skin.get('acquisition'),'rarity':skin.get('rarity'),'dlcSteamId':skin.get('dlcSteamId'),
                'availability':'requires_current_store_or_event_verification'}
            image_candidate(id,name,skin.get('icon'),path)
    for id,name,w,path,page in source['weapons']:
        card=w.get('cardStats') or {};ammo_ids=[]
        for chamber,options in (('primary',w.get('ammoOverrides')),('secondary',w.get('ammoOverrides2'))):
            for n,a in enumerate(options or []):
                if n==0:continue # stock ammunition is in details, not a paid custom-ammo choice
                an=a['names']['en'];an_display=an if chamber=='primary' else an+' (secondary)'
                aid=stable_id('ammo',name+'-'+an_display);ammo_ids.append(aid)
                delta=a.get('stats') or {};ballistics=a.get('ballistics') or {}
                # Only card-to-card deltas are added. Display damage is a different model.
                base_card=card if chamber=='primary' else {}
                def card_value(k):
                    return base_card[k]+delta.get(k,0) if isinstance(base_card.get(k),(float,int)) else None
                effect=summaries['ammo'].get(an)
                if an=='Dragon Breath' and 'Coins replace' in a['description']['en']:
                    effect=None
                    issues.append({'id':aid,'field':'effects','kind':'name_description_conflict','resolution':'kept_null','sourceUrl':ORIGIN+path})
                record('ammo',aid,{'nameEn':an_display,'weaponId':id,'priceHuntDollars':a.get('priceDollars'),
                    'damage':card_value('Damage'),'velocityMps':ballistics.get('muzzleVelocity',card_value('Muzzle Velocity')),
                    'dropMeters':card_value('Drop Range'),'effects':effect},path,
                    ('weaponId','damage','velocityMps','dropMeters','effects','nameEn'))
                details[aid]={'sourceUrl':ORIGIN+path,'sourceId':a['id'],'chamber':chamber,'sourceNameEn':an,
                    'acquisitionFlags':a.get('acquisition'),
                    'damageBasis':'in_game_card_base_plus_source_delta','cardStatDeltas':delta,
                    'ballisticOverrides':ballistics,'damageSource':a.get('damageSource'),'damageFalloffMeters':a.get('damageFalloff'),
                    'falloffCurve':a.get('falloffCurve'),'penetrationAmmo':a.get('penetrationAmmo'),
                    'impactBurst':a.get('impactBurst'),'availableWeaponAmmoSlots':w.get('customAmmoSlots'),
                    'calculationNote':'Secondary barrel card base and per-selection slot consumption remain unknown; do not use primary barrel values.'}
                image_candidate(aid,an,a.get('icon'),path)
        vals={'nameEn':name,'ammoClass':w.get('ammo'),'priceHuntDollars':w.get('priceDollars'),
            'damage':card.get('Damage'),'velocityMps':w.get('muzzleVelocity'),'dropMeters':card.get('Drop Range'),
            'cycleSeconds':card.get('Cycle Time'),'slots':w.get('slots'),'capacity':w.get('ammoLoaded'),
            'reserveAmmo':w.get('ammoReserve'),'reloadSeconds':w.get('reloadTime'),
            'customAmmoIds':ammo_ids,'customAmmoCoverage':'complete' if w.get('ammoOverrides') is not None or w.get('ammoOverrides2') is not None else ('none' if not w.get('customAmmoSlots') else 'partial')}
        # Internal zero/default prices on scarce items are not buyable prices.
        if w.get('unobtainable') or 'isScarce' in (w.get('acquisition') or []):vals['priceHuntDollars']=None
        record('weapons',id,vals,path,('customAmmoIds','customAmmoCoverage'))
        details[id]={'sourceUrl':ORIGIN+path,'sourceId':w['id'],'familyId':w.get('familyId'),
            'inventoryDomain':'gear' if name in name_ids['gear'] else 'weapons',
            'canonicalInventoryId':name_ids['gear'].get(name,id),
            'familyName':w.get('familyName'),'weaponType':w.get('weaponType'),'actionType':w.get('actionType'),
            'damageBasis':'in_game_card','inGameCardStats':card,'bayouDisplayDamage':w.get('displayDamage'),
            'baseProjectileDamage':w.get('perHitDamage'),'pellets':w.get('pellets'),
            'damageFalloffMeters':w.get('damageFalloff'),'falloffCurve':w.get('falloffCurve'),
            'customAmmoSlots':w.get('customAmmoSlots'),'reportedUnlockRank':w.get('unlockRank'),
            'acquisitionFlags':w.get('acquisition'),'sourceUnobtainable':w.get('unobtainable'),
            'internalPriceHuntDollars':w.get('priceDollars'),'alternateBarrel':w.get('alternate'),
            'recommendedTraitIds':[name_ids['traits'][p['names']['en']] for p in w.get('recommendedTraits') or [] if p['names']['en'] in name_ids['traits']],
            'traitEffects':w.get('traitEffects'),'dualWield':w.get('dualWield')}
        category={'Shotgun':'산탄총','Pistol':'권총','Rifle':'소총','Melee':'근접 무기','Bow':'활','Crossbow':'석궁'}.get(w.get('weaponType'),w.get('weaponType') or '무기')
        action={'pump':'펌프액션','bolt':'볼트액션','lever':'레버액션','single':'단발식','double':'더블액션','semi':'반자동'}.get(w.get('actionType'),w.get('actionType'))
        details[id]['descriptionKo']=((action+' 방식의 ') if action else '')+category+'.'+(f" 기본 장전 {w['ammoLoaded']}발, 예비탄 {w['ammoReserve']}발." if w.get('ammoLoaded') is not None and w.get('ammoReserve') is not None else '')
        if card.get('Damage') is not None and card.get('Damage')!=w.get('displayDamage'):
            issues.append({'id':id,'field':'damage','kind':'different_measurement_basis','inGameCard':card['Damage'],'bayouDisplay':w.get('displayDamage'),'sourceUrl':ORIGIN+path})
        image_candidate(id,name,w.get('icon'),path);skins(id,name,'weapons',w,path,page)
    for id,name,g,path,page in source['gear']:
        stats=g.get('cardStats') or {};melee=g.get('melee') or {}
        duration=stats.get('Duration',stats.get('Duration Beetle'))
        if name=='The High Priestess':
            issues.append({'id':id,'field':'durationSeconds','kind':'source_conflict','descriptionSeconds':30,'cardSeconds':15,'resolution':'kept_null','sourceUrl':ORIGIN+path});duration=None
        record('gear',id,{'nameEn':name,'kind':g.get('family'),
            'priceHuntDollars':g.get('priceDollars') if g.get('acquisition')=='store' else None,
            'packCount':g.get('carryQuantity'),'effect':summaries['gear'][name],
            'durationSeconds':duration,'damage':stats.get('Damage',stats.get('Damage (Throwables)')),
            'rangeMeters':stats.get('Throw Range'),'lightStamina':melee.get('lightStamina'),
            'heavyStamina':melee.get('heavyStamina'),'lightDamage':melee.get('light'),'heavyDamage':melee.get('heavy')},path,('effect','kind'))
        details[id]={'sourceUrl':ORIGIN+path,'sourceId':g['id'],'gearKind':g.get('kind'),'acquisition':g.get('acquisition'),
            'reportedUnlockRank':g.get('unlockRank'),'internalPriceHuntDollars':g.get('priceDollars'),
            'inGameCardStats':stats,'damagePerSecond':stats.get('Damage per Second'),'radiusMeters':stats.get('Radius'),
            'fuseSeconds':stats.get('Fuse Timer'),'controlRangeMeters':stats.get('Control Range'),
            'characteristics':g.get('characteristics'),'traitEffects':g.get('traitEffects'),
            'rangeMeaning':'throw_distance_only','packCountMeaning':'uses_per_item_if_explicit_not_inventory_slot_count'}
        evidence[proof(path)]['auxiliarySources']=[{'url':bundle_policy['gearDataUrl'],'sha256':digest((cache/'gear-data.js').read_bytes())}]
        image_candidate(id,name,g.get('icon'),path);skins(id,name,'gear',g,path,page)
    for id,name,t,path,page in source['traits']:
        routes=t.get('routes') or [];flags=[k for k in ('burnOnUse','missionOnly','multipleAllowed') if t.get(k)]
        if routes and 'shop' not in routes:flags.append('not_shop_purchasable')
        related=[source_ids[d][x['id']] for d in ('weapons','gear') for x in page.get(d,[]) if x['id'] in source_ids[d]]
        record('traits',id,{'nameEn':name,'category':t.get('category'),'costPoints':t.get('cost') if 'shop' in routes else None,
            'acquisition':routes or None,'flags':flags,'effectKo':summaries['traits'][name],
            'equipmentIds':sorted(set(related)) if related else None},path,('flags','effectKo','equipmentIds'))
        details[id]={'sourceUrl':ORIGIN+path,'sourceId':t['id'],'internalCostPoints':t.get('cost'),
            'purchasable':('shop' in routes) if routes else None,'reportedUnlockRank':t.get('unlockRank'),
            'burnOnUse':t.get('burnOnUse'),'missionOnly':t.get('missionOnly'),'multipleAllowed':t.get('multipleAllowed'),
            'magnitudes':t.get('magnitudes'),'bonuses':t.get('bonuses'),'burnReduction':t.get('burnReduction'),
            'bodyDamage':t.get('bodyDamage'),'metaEffect':t.get('metaEffect'),
            'equipmentRelationMeaning':'source_lists_affected_equipment; absence is not proof of no effect'}
        image_candidate(id,name,t.get('icon'),path)
    # Retain primary-source facts already verified in the seed; corroborated again.
    official_url='https://store.steampowered.com/app/4733620/Hunt_Showdown_1896_Bound_by_Blood/'
    official_key='steam-bound-by-blood-20261113'
    official_targets={('weapon-mosin-nagant','The Primrose'),('weapon-sparks-pistol','Skin Deep'),
        ('weapon-sparks-pistol-silencer','Skin Deep: Silencer'),('gear-ammo-box','The White Fox')}
    for item in catalog['skins']:
        if (item['values']['baseItemId'],item['values']['nameEn']) not in official_targets:continue
        evidence.setdefault(official_key,{'sourceId':'steam-crytek','url':official_url,'observedAt':DATE,
            'sourcePatch':None,'verification':'primary_publisher_store_page','claims':[]})
        for field,value in {'releaseDate':'2026-10-07','acquisition':'DLC','eventOrDlc':'Bound by Blood'}.items():
            item['values'][field]=value
            item['fieldReviews'][field]={'status':'verified','sourceId':'steam-crytek','sourceUrl':official_url,
                'observedAt':DATE,'sourcePatch':None,'evidenceId':official_key}
            evidence[official_key]['claims'].append({'entityId':item['id'],'field':field,'valueSha256':digest(encode(value)),'method':'primary_source_observation'})
    for d in DOMAINS:catalog[d].sort(key=lambda x:x['id'])
    validate(catalog,evidence=evidence)
    output.mkdir(parents=True,exist_ok=True)
    write(output/'catalog.json',catalog);write(output/'evidence.json',evidence)
    write(output/'details.json',{'schemaVersion':'bayou-details-1','dataVersion':VERSION,'sourcePatch':PATCH,'items':details})
    write(output/'image-candidates.json',{'images':images,'downloadedImages':0,'approvedImages':0,'defaultLoadEnabled':False})
    write(output/'review-issues.json',issues)
    coverage={d:{'records':len(catalog[d]),'fields':{f:sum(x['values'][f] is not None for x in catalog[d]) for f in FIELDS[d]}} for d in DOMAINS}
    write(output/'coverage.json',coverage)
    write(output/'manifest.json',{'schemaVersion':'reference-staging-1','dataVersion':VERSION,'sourcePatch':PATCH,
        'researchOnly':True,'published':False,'appIntegrationEnabled':False,'observedAt':DATE,
        'verification':'source_observed_not_independently_game_verified','catalogSha256':digest(encode(catalog)),
        'counts':{d:len(catalog[d]) for d in DOMAINS},'imageCandidates':len(images),'sourcePages':sum(len(x) for x in source.values()),
        'gearBundleSha256':digest((cache/'gear-data.js').read_bytes()),'gearBundleGeneratedAt':gear_snapshot['generatedAt'],
        'files':{p.name:digest(p.read_bytes()) for p in sorted(output.glob('*.json')) if p.name!='manifest.json'}})
    print(json.dumps({'counts':{d:len(catalog[d]) for d in DOMAINS},'imageCandidates':len(images),'issues':len(issues),'bytes':(output/'catalog.json').stat().st_size}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();build(args.cache,args.output)
