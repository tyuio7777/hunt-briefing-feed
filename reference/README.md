# Hunt Briefing Reference Data

기존 `hunt-briefing-feed`의 **`reference/` 전용 영역**입니다. 기존 조사·생성·검증·게시, 피드 JSON, 푸시, 아카이브와 연결하지 않습니다.

## 현재 상태 — 2026-11-13

Bayou Index 2.9.1의 공개 상세 페이지 294개와 공개 장비 데이터 모듈을 조사해 **실제 데이터 보강본**을 저장했습니다. 기존 이름 목록만 있던 상태에서 가격·무기 수치·탄약 조합·효과 설명·특성 포인트·스킨 관계를 추가했습니다.

- [검토용 데이터](staging/bayou-2026-11-13/catalog.json): 무기 목록 161, 무기별 탄약 조합 516, 장비 68, 특성 65, 스킨 816.
- [상세 수치와 보조 정보](staging/bayou-2026-11-13/details.json): 카드 수치와 계산 수치, 탄약 변경값, 보조 총열, 습득 경로, 관련 특성, 스킨 가격.
- [이미지 후보](staging/bayou-2026-11-13/image-candidates.json): 출처 URL 1,626개. 사용권 미확인, 파일 다운로드·배포·자동 로딩 0개.
- [필드 충족 현황](staging/bayou-2026-11-13/coverage.json), [충돌·수치 기준 차이](staging/bayou-2026-11-13/review-issues.json), [필드별 증거](staging/bayou-2026-11-13/evidence.json).

**운영 연동 OFF**입니다. `catalog/v1/active.json`을 만들지 않았고 서명 배포·자동 수집·뉴스 카드 생성도 하지 않습니다. `published:false`는 앱 운영 배포가 아니라는 뜻입니다. 검토용 사실 스냅샷은 이 공개 Git 폴더에서 개발자가 확인할 수 있습니다.

`verified`는 **해당 출처에서 확인한 값**이라는 기존 스키마 상태입니다. 모든 항목을 게임에서 독립 검증했다는 뜻이 아닙니다. 원문 안의 충돌, 사용권, 게임 내 교차검증은 별도 검수 대상입니다. 미확인 값은 `null`이며 무료·효과 없음·호환 불가로 바꾸지 않습니다.

## 재현과 검증

```sh
python -m pip install -r requirements-research.txt
python scripts/fetch_bayou.py --fetch --cache /tmp/hunt-bayou-2026-11-13
python scripts/enrich_bayou.py --cache /tmp/hunt-bayou-2026-11-13 --output staging/bayou-2026-11-13
python -m unittest discover -s tests -p 'test_*.py' -v
```

수집은 명시적인 `--fetch` 없이는 실행되지 않습니다. 현재 목록만 읽으며, 공개 모듈 경로가 바뀌면 중단하고 검토를 요구합니다. 원본 HTML·JS와 이미지 바이트는 Git에 넣지 않습니다. 파서는 원문 JavaScript를 실행하지 않습니다. 숫자와 한국어 기능 요약만 선별하며 스킨 서사 원문을 복제하지 않습니다.

기존 `.NET` 검증은 SDK가 있는 환경에서 `python scripts/check_all.py`로 실행합니다. 운영 배포는 기존 권한·필드 검수·해시 승인·서명 절차를 모두 통과해야 하며 현재 `release.py check`는 차단됩니다.

## 경계와 후속

- 기존 `latest.json`, `index.json`, 워크플로, 브리핑 화면은 변경하지 않습니다.
- `staging/`을 앱이나 피드의 자동 탐색 경로로 등록하지 않습니다.
- `research/`에는 원본 연구자료를 보관하며 공개 내보내기에서 제외합니다. `staging/`은 해시 검증한 사실 보강본만 별도로 선별합니다.
- 무기 인덱스의 도구 11종은 기존 ID를 보존하되 `details.inventoryDomain=gear`와 정식 장비 ID로 구분했습니다.
- 원본 데이터에서 얻은 `unlockRank`는 참고값으로만 보관하며 현재 게임의 해금 조건으로 확정하지 않습니다.

[데이터 검수](docs/DATA_REVIEW_KO.md) · [로드아웃 페이지 후속 항목](docs/LOADOUT_DATA_FOLLOWUP_KO.md) · [배포](docs/DEPLOYMENT_KO.md) · [연동](docs/INTEGRATION_KO.md) · [검증](docs/VALIDATION_KO.md)
