# 브리핑 채널 — 공식 녹화 영상 등록

2026-11-04 사용자가 지정한 다음 3개 공개 녹화 영상을 등록했습니다.

| 원본 | 제목 | 확인한 길이 |
| --- | --- | --- |
| https://www.youtube.com/watch?v=Mz8ungOdl8M | Blood Testament Chapter 2 · Developer Livestream | 01:05:19 |
| https://www.youtube.com/watch?v=qUPhr8ZVyKY | Blood Testament · Developer Livestream | 00:39:21 |
| https://www.youtube.com/watch?v=wumQYLcvdes | Blood Testament · Developer Livestream | 00:35:16 |

두 Blood Testament 영상은 제목이 같지만 서로 다른 video ID와 방송 구간을 가진 원본입니다. 카탈로그에는 원래 제목을 그대로 저장합니다.

- 공식 채널 ID: UCd-9pZ4Vcmsjw5TsPKWrigw (@HuntShowdown).
- 공식 공개 watch 페이지와 YouTube oEmbed로 소속·제목·공개·방송 종료·길이·임베드 허용 상태를 확인했습니다. 인증 YouTube Data API를 호출한 결과는 아닙니다.
- 현재 패키지는 원본 재생 연결용입니다. 번역·요약·타임라인·발언 발췌는 아직 없으며, 영상 내용 분석이나 구간 시간 정합성 검수를 완료한 것으로 표시하지 않습니다.
- 원본 영상·오디오·자막 파일을 다운로드하거나 저장소에 재업로드하지 않았습니다. 앱은 공식 YouTube 플레이어로 원본을 재생합니다.
- 실제 Android 기기의 재생 여부는 별도 검증 대상입니다. 임베드 허용 메타데이터만으로 모든 기기의 재생 성공을 보장하지 않습니다.

## 갱신과 검토

앱의 브리핑 채널에서 새로고침한 뒤 공식 영상 선택 목록을 확인합니다. 이번 변경은 공통 JSON 자료만 갱신하므로 해당 자료 경로를 사용하는 앱에는 APK 재설치가 필요하지 않습니다.

`catalog.json`은 영상별 `packages/<sha256>.json`을 가리킵니다. 패키지를 검증·업로드하고 실제 파일을 확인한 뒤 카탈로그를 갱신합니다. 기존 feed/latest.json과 다른 운영 데이터는 변경하지 않습니다.

영상 메타데이터는 30일 이내 재확인·갱신하거나 목록에서 제거해야 합니다. 이 변경으로 GitHub Actions 또는 서버 예약을 추가하지 않았습니다.

번역·요약·타임라인은 운영 API 연결과 실제 무료 프로젝트·모델 사용 조건을 확인한 뒤, 허용 원자료 기반 제작·내용 대조·공개 범위 검토를 거쳐 새 revision으로 발행합니다. 영상 제목·설명만으로 번역이나 시간 구간을 만들지 않습니다. 운영 인증 정보는 공개 파일에 포함하지 않습니다.
