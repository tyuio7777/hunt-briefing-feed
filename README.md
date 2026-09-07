# Hunt Briefing Feed

Hunt: Showdown 주간 브리핑 앱이 읽는 공개 데이터 저장소입니다.

## 역할

- 토요일 정규 브리핑의 JSON/HTML 배포
- 최신 발행본과 과거 발행 목록 제공
- C# .NET MAUI Android 앱의 읽기 전용 데이터 소스

이 저장소에는 완성된 공개 브리핑만 저장합니다. 이메일 주소, API 키, 토큰, 내부 프롬프트와 생성 중간 자료는 저장하지 않습니다.

## 공개 엔드포인트

- 최신 발행 정보: `feed/latest.json`
- 발행 목록: `feed/index.json`
- JSON 스키마: `schema/briefing-v1.schema.json`
- 개발용 예시: `samples/briefing-v1.example.json`

Raw URL 기본 주소:

```text
https://raw.githubusercontent.com/tyuio7777/hunt-briefing-feed/main/
```

## 디렉터리

```text
feed/
├─ latest.json
├─ index.json
└─ YYYY/MM/
   ├─ YYYY-MM-DD.json
   └─ YYYY-MM-DD.html

schema/
└─ briefing-v1.schema.json

samples/
└─ briefing-v1.example.json
```

## 상태 규칙

초기 상태에서는 `latest.json`의 `status`가 `empty`입니다. 첫 정규 발행이 완료되면 `ready`로 변경하고 해당 발행본 경로를 기록합니다.
