# Hunt Briefing Reference Data

기존 `tyuio7777/hunt-briefing-feed` 저장소의 **`reference/` 전용 영역**입니다. 2026-11-13 사용자 지시에 따라 별도 저장소 대신 이 폴더에 구축했습니다. 기존 브리핑 조사·생성·검증·게시 코드와 `feed/latest.json`, `feed/index.json`은 수정하지 않습니다.

현재 상태는 **기반 구축 완료 / 상세 데이터 및 권한 검수 대기 / 앱 연동 OFF**입니다. `catalog/v1/status.json`만 제공하며 운영용 `active.json`은 없습니다. 빈 카탈로그를 완성된 데이터처럼 배포하지 않습니다.

## 구성

| 경로 (`reference/` 기준) | 용도 |
|---|---|
| `catalog/v1/status.json` | 비활성 배포 상태. 게임 데이터 없음 |
| `schema/catalog-v1.schema.json` | 무기·탄약·도구/소모품·특성·스킨·이미지 스키마 |
| `config/` | 기능 OFF, 출처 정책, 공개 검수 게이트 |
| `reference_tools/`, `scripts/` | 정규화·검증·변경 비교·서명 배포·롤백·공개 파일 선별 |
| `src/Hunt.ReferenceData/` | .NET 8 읽기 전용 클라이언트. MAUI 앱에는 아직 연결하지 않음 |
| `tests/` | 합성 데이터 기반 테스트. 실제 게임 수치와 운영 서명키 없음 |
| `docs/` | 배포·데이터 보강·검증·연동 지침 |
| `workflow-templates/` | 향후 별도 검증용 템플릿. 자동 실행되는 `.github/workflows`에는 설치하지 않음 |

`research/`의 원본·정규화 초안·이미지 후보와 필드별 누락표는 공개 Git에 넣지 않습니다. 공개 브랜치에 올린 후 삭제해도 이력에 남으므로 **공개 전 파일 선별**을 적용합니다. 원본 연구자료는 별도 전달 파일에서 로컬 `reference/research/`에 복원하여 사용합니다.

## 검증 실행

저장소를 받은 뒤 `reference/` 디렉터리에서 실행합니다. Python 3.11+ / .NET 8 SDK가 필요합니다.

```sh
python -m pip install -r requirements.txt
python scripts/check_all.py
```

실제 연구자료가 로컬에 있을 때만 다음을 실행합니다. 없으면 기본 테스트에서 연구자료 전용 검사 1건만 건너뜁니다.

```sh
python scripts/catalog.py --build
python scripts/release.py check
```

현재 공개 승인 검사 `release.py check`는 **차단되는 것이 정상**입니다. 출처별 허가, 상세값·호환관계 검수, 정확한 스냅샷 해시 승인, 운영 서명키가 준비되기 전에는 게시할 수 없습니다.

## 기존 시스템과의 경계

- 이 폴더를 기존 피드 스캔/수집 경로에 추가하지 않습니다.
- Bayou Index 등록은 `reference_only`. 뉴스 항목·카드·섹션 생성은 없습니다.
- 기본 설정 `mode=disabled`, AI 컨텍스트·UI·이미지·자동 수집·자동 공개 모두 OFF.
- Disabled는 네트워크와 디스크 캐시도 읽지 않습니다. Shadow는 검증 상태만 반환하고 데이터 검색 결과를 노출하지 않습니다.
- 활성화 시에도 별도 프로세스/작업에서 실행하며 기존 발행 성공 여부와 결합하지 않습니다.
- 기존 서버리스·푸시·아카이브 실서비스 회귀 테스트는 별도 환경에서 필요합니다. 로컬 장애 테스트를 실서비스 회귀 성공으로 간주하지 않습니다.

자세한 내용: [배포](docs/DEPLOYMENT_KO.md), [연동](docs/INTEGRATION_KO.md), [상세 보강/권한](docs/DATA_REVIEW_KO.md), [테스트 결과](docs/VALIDATION_KO.md).
