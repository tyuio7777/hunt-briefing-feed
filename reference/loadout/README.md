# 로드아웃 자료 배포

`loadout/v1/active.json`은 로드아웃 전용 읽기 경로입니다. 브리핑 `latest.json`, `index.json`, 생성·검증·게시·알림·아카이브는 이 경로를 참조하지 않습니다. 기존 서명 방식의 `catalog/v1` 시험 계약은 그대로 유지합니다.

앱은 페이지 진입 및 본문 당겨서 새로고침 때만 자료를 요청합니다. 로드아웃 내용, 보유 항목, 개인 API 키는 서버로 보내지 않습니다. 사용자 로드아웃을 AI에 보내는 분석 기능은 없습니다. 자동 유지보수는 저장소 자료 갱신만 담당합니다.

## 내부 AI 유지보수

1. 기존 브리핑 작업과 별개로 신규 브리핑의 공식 출처를 변경 후보 탐색에 사용합니다. 브리핑 요약만으로 수치를 확정하지 않습니다.
2. 공식 패치 노트/장비 문서를 우선 확인하고 공개 Bayou Index 원자료로 보완합니다. 유료·비공개 자료에 접근하지 않습니다.
3. 현재 active가 가리키는 스냅샷을 기반으로 변경 필드만 수정합니다. `fieldReviews`에 URL, 관찰 날짜, 증거 ID를 함께 남기고 `reference/loadout/reviews/`에 이전값/새값/근거를 기록합니다. 불확실한 값은 null로 유지합니다. 과거 staging 파일 전체를 다시 적용해 최신 값을 되돌리지 않습니다.
4. 카드 피해량, 투사체 기본 피해량, 부위별 시뮬레이션 피해량을 혼합하지 않습니다. 활은 가변 카드 수치임을 표시합니다. 보조 총열은 별도 stock delta와 선택 delta를 적용합니다. 혼합 탄종의 보급 분할은 검증 전 추정하지 않습니다.
5. `reference/scripts/publish_loadout.py`로 검증합니다. 가격 음수, 중복 ID, 잘못된 탄약 관계, 출처 없는 비어 있지 않은 값, 지원하지 않는 규칙 구조는 배포하지 않습니다.
6. 기존 sequence보다 큰 번호로 스냅샷을 만들고 **스냅샷·리뷰·active를 단일 Git 커밋으로** 게시합니다. 최신 HEAD를 부모로 삼고 낙관적 잠금으로 main을 갱신합니다. 변경 경로는 `reference/`로 한정합니다. 실패하면 active를 유지하고 다음 회차에 재시도합니다. 기존 예약 작업은 수정하지 않습니다.
7. 새로운 사실이 없으면 커밋하거나 사용자에게 알리지 않습니다. 이미지 파일 재배포/가공은 별도 사용권 근거 없이는 하지 않습니다. 현재 앱의 외부 이미지 참조 규칙을 유지합니다.

## 검증·배포

```sh
python reference/scripts/publish_loadout.py --catalog /tmp/reviewed-catalog.json --rules /tmp/reviewed-rules.json --sequence NEXT
```

`NEXT`는 현재 sequence+1입니다. 스냅샷은 UTF-8 JSON이며 SHA-256으로 파일명/manifest가 연결됩니다. HTTPS와 지정 저장소를 신뢰 경계로 사용하며, 이 해시는 전자서명이 아닙니다. 앱은 해시·형식·관계·시퀀스를 검증한 뒤 캐시 파일 하나를 원자적으로 교체합니다. 실패 시 마지막 정상 캐시, 캐시도 없으면 앱 내 자료를 사용합니다.

`fieldReviews.status=verified`는 해당 출처에서 확인한 값이라는 뜻이며 게임 전체의 독립 검증 완료를 의미하지 않습니다. 이 구분과 출처 메타데이터를 유지합니다.

## Range guidance adapter (2026-11-15)

The loadout catalog now carries `falloffCurve` for reviewed source observations and
`weaponType` for weapon-specific explanatory caveats. These are from the existing
2026-11-13 observation set; this release does not claim a new in-game measurement.
The publisher rejects nonmonotone, non-finite and out-of-bounds curves. Missing
secondary-barrel curves remain null; never substitute the primary barrel curve.

The app's editorial range labels interpolate the observed projectile curve at
75% (effective guidance) and 50% (limited guidance) of original damage. These are
not official effective-range or guaranteed-kill claims. Bullet-drop start is
never used as damage falloff. Explosion, status damage, pellet hit count and
body-zone multipliers are not included in this guidance.

For every future changed source snapshot, assign a new catalog dataVersion and
publish a strictly increasing sequence. Keep these fields when rebuilding with
`build_loadout.py`; do not retain old curves when a source observation changes.
A future rules bundle may specify integer `minimumEditorVersion` > 1 to make the
current editor read-only; ordinary patch/version changes must remain editable.
