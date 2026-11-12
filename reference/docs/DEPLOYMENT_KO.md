# 폴더 격리 배포

## 실제 배치

- 저장소: `tyuio7777/hunt-briefing-feed` (기존 공개 저장소)
- 이번 변경 허용 범위: `reference/` 하위 신규 파일만. 루트 README, `.github/`, `feed/`, 기존 HTML 등은 변경하지 않음.
- 원본 연구자료는 공개하지 않음. 공개 브랜치나 공개 PR 초안에도 넣지 않음.
- 현재 `reference/catalog/v1/status.json`은 미승인/연동 OFF를 명시. 운영용 `active.json`과 이미지 바이너리는 생성하지 않음.

## 검증 데이터 출시 절차

1. 비공개 로컬 작업 공간에서 필드별 값·원출처·조회일·패치·증거를 검수한다. 숫자 누락은 `null`; 무료/미지원으로 추정하지 않는다.
2. `config/sources.json`에 실제 수집·재배포 허가 증거를 기록한다. 데이터 권리와 이미지 권리를 각각 승인한다. 권한 값만 임의로 true로 바꾸지 않는다.
3. `research/evidence.json`은 엔터티/필드/값 SHA-256에 묶는다. 출처가 달라지거나 값이 바뀌면 다시 검수한다.
4. 로컬 후보 `research/catalog/release-candidate.json`에 정확한 버전, `researchOnly=false`, `published=true`를 설정한다. 모든 필수값 및 존재하는 선택값이 검수되어야 한다. 실제 해당 없음만 증거와 함께 `not_applicable` + null로 표현한다.
5. 커스텀 탄약 호환 전수 조사를 마치고 무기별 `customAmmoCoverage=complete` 또는 검증된 `none`을 기록한다. 일부 후보뿐이면 공개 게이트가 차단한다.
6. 후보 파일의 정규화 바이트 SHA-256을 `config/publication-review.json`에 기록하고 검수자·검수일·범위·권한을 승인한다. 이미지가 있으면 `allowedImages`에 개별 ID를 추가한다.
7. 승인된 WebP만 `research/approved-assets/assets/<SHA-256>.webp`에 두고 출처 권한·파일 해시·파일 형식을 검사한다. 현재 승인된 이미지 0개이며 다운로드/핫링크 코드는 없다.
8. 안전한 로컬 키 저장소에서 ECDSA P-256 키를 준비한다. **개인키를 Git/ZIP/로그에 넣지 않는다.** 공개키를 별도 앱 설정에 고정한다. 테스트는 매 실행 임시 키를 만들고 폐기한다.

```sh
python scripts/release.py check --catalog research/catalog/release-candidate.json
python scripts/release.py publish --catalog research/catalog/release-candidate.json --key /secure/path/reference-signing-key.pem
```

게시 도구는 `catalog/v1/snapshots/<hash>.json`, `manifests/<version>.json`을 먼저 만들고 마지막에 `active.json`을 원자 교체한다. 프로세스 동시 게시를 잠금으로 막으며 기존 버전 내용 변경은 거부한다. 서명은 P-256/SHA-256/DER, 내용 검증은 SHA-256이다. 잠금 파일이 비정상 종료로 남으면 **게시 프로세스가 종료되었는지 확인한 뒤** 해당 잠금만 제거한다.

`status.json`은 검수 승인 후 배포 담당자가 실제 상태로 함께 갱신한다. 자동 수집이 공개 승인을 수행하지 않는다.

## Git 게시 경계

```sh
python scripts/export_public.py /tmp/hunt-reference-public
```

내보낸 파일만 저장소의 `reference/`로 복사한다. 공개 대상은 명시된 코드/문서/설정과 서명 검증된 운영 스냅샷이다. 현재 내보내기는 미승인 연구 데이터가 없고 운영 스냅샷도 없다. 전체 로컬 폴더를 `git add .` 하지 않는다. 커밋 직전 `git diff --name-only`가 모두 `reference/`로 시작하는지 확인한다. 기존 파일의 Git blob SHA를 비교하고 다른 파일이 변하면 중단한다. 푸시는 최신 HEAD를 기준으로 fast-forward만 사용한다.

출시 스냅샷을 내보낼 때에는 `config/trusted-public-key.pem`을 먼저 제공하고 `export_public.py`가 서명/해시/이미지 참조를 재검사하게 한다. 이 키는 공개키이며 개인키는 허용하지 않는다.

## 원복

```sh
python scripts/release.py rollback --version 1.0.0 --key config/trusted-public-key.pem
```

서명·해시와 현재 출처 권한/증거가 유효한 과거 버전만 활성 포인터로 복원한다. 권한 취소 자료는 원복할 수 없다. 앱에서 장애가 생기면 **레퍼런스 플래그만 OFF**로 되돌린다. 브리핑 피드나 발행 파이프라인을 원복 대상으로 삼지 않는다.

## 자동화

템플릿은 자동 실행 경로 밖에 두었다. 검증된 뒤 독립 스케줄러에 설치할 수 있으나 현재 기존 오전 조사·게시 예약/재시도/알림 설정은 바꾸지 않는다. 배포 작업은 이 저장소의 `reference/` 경로만 허용하고 동시 실행을 직렬화한다. 수집 작업은 후보만 만들며 배포·승인 작업과 분리한다.
