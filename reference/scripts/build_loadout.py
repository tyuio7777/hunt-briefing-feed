"""Build the offline loadout snapshot. No downloads or feed writes.

python tools/Loadout/build_enriched.py REFERENCE_STAGING_DIR [OUTPUT_DIR]
Source observations are not a signed/published reference release. All source
prices are already per ammo selection: do not divide a two-pool price again.
"""
import copy
import hashlib
import json
import sys
from pathlib import Path

src = Path(sys.argv[1])
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / 'loadout/staging'
raw = json.loads((src / 'catalog.json').read_text())
details = json.loads((src / 'details.json').read_text())['items']
catalog = {k: copy.deepcopy(raw[k]) for k in ['weapons', 'ammo', 'gear', 'traits', 'skins']}
catalog.update(schemaVersion='1.0.0', dataVersion='loadout-20261114-r2', sourcePatch=raw['sourcePatch'], researchOnly=True, published=False, images=[])
catalog['weapons'] = [i for i in catalog['weapons'] if details[i['id']]['inventoryDomain'] == 'weapons']
# Skins are not part of this calculation patch; retain the three original IDs.
catalog['skins'] = [i for i in catalog['skins'] if i['id'] in {'skin-the-primrose', 'skin-skin-deep', 'skin-skin-deep-silencer'}]
all_items = {i['id']: i for g in ['weapons','ammo','gear','traits','skins'] for i in catalog[g]}

def put(item, key, value, source=None):
    item['values'][key] = value
    item['fieldReviews'][key] = {'status': 'verified' if value is not None else 'missing', 'sourceUrl': source or details[item['id']]['sourceUrl'], 'observedAt': '2026-11-13', 'sourcePatch': raw['sourcePatch'], 'sourceId': 'bayou-index', 'evidenceId': 'offline-adapter-source-observation'}

def effect(item, effects):
    put(item, 'effectStructured', {'effects': effects})

# Internal-only duplicate weapon entries are mapped to their canonical tool IDs
# for trait targeting, without silently changing any saved user selections.
aliases = {k: v['canonicalInventoryId'] for k,v in details.items() if k.startswith('weapon-') and v.get('inventoryDomain') == 'gear'}
for w in catalog['weapons']:
    d = details[w['id']]
    n = d['customAmmoSlots']
    put(w, 'ammoSlotCount', n)
    put(w, 'ammoLayout', 'barrels' if d['alternateBarrel'] else 'pools')
    put(w, 'descriptionKo', d['descriptionKo'])
    put(w, 'role', 'melee' if d['weaponType']=='Melee' else 'ranged')
    put(w, 'damageBasis', 'variable_card' if d.get('damageCardKey')=='Variable Damage' else 'card')
    flags = d['acquisitionFlags'] or []
    put(w, 'purchaseStatus', 'unavailable' if d['sourceUnobtainable'] else 'scarce' if 'isScarce' in flags else 'shop' if w['values']['priceHuntDollars'] is not None else 'unknown')
    if d['alternateBarrel']:
        a = d['alternateBarrel']
        # Stock secondary has its own explicit delta from the source primary card.
        card=d['inGameCardStats']; delta=d.get('stockSecondaryCardDeltas')
        def secondary(key):
            return round(card[key]+delta.get(key,0),6) if isinstance(delta,dict) and isinstance(card.get(key),(int,float)) else None
        put(w, 'secondaryStats', {'damage':secondary('Damage'),'dropMeters':secondary('Drop Range'),'velocityMps':a.get('muzzleVelocity'),'reloadSeconds':a.get('reloadTime'),'capacity':a.get('ammoLoaded'),'reserveAmmo':a.get('ammoReserve')})
for a in catalog['ammo']:
    d = details[a['id']]
    put(a, 'ammoChamber', d['chamber'])
    put(a, 'capacity', d.get('ammoCounts',{}).get('ammoLoaded'))
    put(a, 'reserveAmmo', d.get('ammoCounts',{}).get('ammoReserve'))
    put(a, 'damageBasis', 'variable_card' if d.get('damageCardKey')=='Variable Damage' else 'card')
    flags = d['acquisitionFlags'] or []
    status = 'worldOnly' if 'worldOnly' in flags else 'scarce' if 'isScarce' in flags else 'shop' if 'availableOnStore' in flags else 'unknown'
    put(a, 'purchaseStatus', status)
    put(a, 'priceBasis', 'perSelection')
for g in catalog['gear']:
    d = details[g['id']]
    put(g, 'purchaseStatus', 'shop' if d['acquisition'] == 'store' else 'craft' if d['acquisition'] == 'craft' else 'unknown')
    if d['gearKind'] == 'healing' or g['id'].startswith(('gear-vitality-shot', 'gear-regeneration-shot')):
        put(g, 'role', 'healing')
    elif d['gearKind'] == 'trap': put(g, 'role', 'trap')
    elif d['gearKind'] == 'melee': put(g, 'role', 'melee')
    elif g['id'] in ['gear-choke-bombs','gear-choke-beetle']: put(g, 'role', 'choke')
    put(g, 'instantHealing', g['id'] in ['gear-vitality-shot','gear-vitality-shot-weak'])
    if g['values']['kind'] == 'consumable':
        category = {'throwable':'throwable', 'drone':'throwable', 'boost':'shot', 'tarot':'tarot', 'restock':'placeable', 'healing':'placeable'}.get(d['gearKind'])
        if category: put(g, 'consumableCategory', category)

conditions = {'trait-ambidextrous':'dualWield', 'trait-hundred-hands':'fullDraw', 'trait-fanning':'hipFire', 'trait-levering':'hipFire', 'trait-iron-eye':'aiming', 'trait-scopesmith':'aiming', 'trait-steady-aim':'aiming', 'trait-bulletgrubber':'partialReload'}
for t in catalog['traits']:
    d = details[t['id']]
    if d['purchasable'] is False: put(t, 'unlockCondition', 'matchOnly')
    targets = list(dict.fromkeys(aliases.get(x,x) for x in t['values'].get('equipmentIds') or [] if aliases.get(x,x) in all_items))
    e = {'type':'ability', 'label':t['values']['effectKo'] or '효과 확인 중', 'targetIds': targets}
    if t['id'] in conditions: e['condition'] = conditions[t['id']]
    elif not targets: e['condition'] = 'gameplay'
    if t['id'] == 'trait-crack-shot': e.update(type='pending', label='대상 목록과 제외 설명이 달라 적용 범위를 확인 중')
    effect(t, [e])

effect(all_items['trait-quartermaster'], [{'type':'capacity', 'label':'무기 용량 +1', 'value':1}])
for tid, source_stat, stat, label in [('trait-doctor','firstAidHeal','healing','응급 도구 회복량 증가'), ('trait-physician','firstAidTime','useSeconds','응급 도구 사용 시간 단축')]:
    t = all_items[tid]
    magnitude = next(x for x in details[tid]['magnitudes'] if x['stat'] == source_stat)
    put(all_items['gear-first-aid-kit'], stat, magnitude['without'], details[tid]['sourceUrl'])
    effect(t, [{'type':'modifier', 'label':label, 'targetIds':['gear-first-aid-kit'], 'stat':stat, 'operation':'set', 'value':magnitude['with']}])
frontier_targets = [g['id'] for g in catalog['gear'] if any(x.get('trait') == 'Frontiersman' and x.get('stat') == 'carryQuantity' for x in details[g['id']].get('traitEffects') or [])]
effect(all_items['trait-frontiersman'], [{'type':'toolCharges', 'label':'도구 사용 횟수 +1', 'targetIds':frontier_targets, 'value':1, 'overrides':[{'requiresTraitIds':['trait-catalyst'], 'solo':True, 'value':2, 'label':'도구 사용 횟수 +2 · 솔로 Catalyst'}]}])
effect(all_items['trait-catalyst'], [{'type':'traitSynergy', 'label':'함께 선택한 특성의 추가 효과 · 개별 조건 확인', 'traitIds':['trait-beastface','trait-kiteskin','trait-vigilant','trait-pain-sense','trait-frontiersman'], 'condition':'gameplay'}])
# No invented reload multipliers, damage boosts, throw-distance multipliers, or
# automatic activation of situational effects. Numeric facts stay typed.
catalog['observation'] = {'source':'The Bayou Index', 'observedAt':'2026-11-13', 'patch':raw['sourcePatch'], 'status':'source_observed_not_game_verified', 'priceBasis':'per_selected_item_and_ammo_compartment', 'sourceUrl':'https://bayouindex.com/', 'inputSha256':{n:hashlib.sha256((src/n).read_bytes()).hexdigest() for n in ['catalog.json','details.json']}}
# Retain only usable values: null never becomes zero or an unchanged stat.
for group in ['weapons','ammo','gear','traits','skins']:
    for i in catalog[group]:
        for k,v in list(i['values'].items()):
            if i['fieldReviews'].get(k,{}).get('status') != 'verified' and k not in ['nameEn','nameKo']:
                i['values'][k] = None
out.mkdir(parents=True,exist_ok=True)
(out/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+'\n')
print({k:len(catalog[k]) for k in ['weapons','ammo','gear','traits','skins','images']})
