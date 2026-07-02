# Alpha Radar Engine 클라우드 이전 가이드

목표는 Windows PC를 꺼도 알파레이더 데이터가 계속 갱신되게 만드는 것입니다.

## 현재 구조

```text
Windows PC
 └─ engine/alpha_radar_engine_v1.py
    └─ 종목 스캔 / 가격 업데이트 / 핫뉴스 수집 / Supabase 업로드

Vercel 또는 로컬 웹
 └─ 알파레이더 화면 표시

Supabase
 └─ rankings / alerts / hot_news / paper trading 저장
```

## 1차 추천: GitHub Actions 스케줄

비용을 거의 안 쓰고 시작하려면 GitHub Actions가 좋습니다.

동작 방식:

```text
10분마다 GitHub가 엔진을 한 번 실행
→ Supabase에 최신 데이터 업로드
→ Vercel/PWA 화면은 Supabase에서 최신 데이터 표시
```

장점:

- Windows PC를 계속 켜둘 필요가 줄어듦
- 무료로 시작 가능
- 설정이 비교적 단순함

주의:

- GitHub 스케줄은 정확히 10분 정각에 실행된다는 보장은 없습니다.
- 무료 Finnhub API 호출 제한에 걸릴 수 있습니다.
- 실시간 초단위 가격 업데이트용은 아닙니다.

## GitHub Secrets에 넣을 값

GitHub 저장소에서:

```text
Settings > Secrets and variables > Actions > New repository secret
```

아래 값을 추가하세요.

필수:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
FINNHUB_API_KEY
```

선택:

```text
KRX_ID
KRX_PW
```

## GitHub Actions 파일

이미 생성됨:

```text
.github/workflows/alpha-radar-engine.yml
```

이 파일은:

- 10분마다 자동 실행
- 수동 실행 가능
- Python 3.11 설치
- `engine/requirements.txt` 설치
- `engine/config.cloud.json`을 `config.json`으로 복사
- 엔진을 한 번 실행 후 종료

## 수동 실행 방법

GitHub 저장소 페이지에서:

```text
Actions > Alpha Radar Engine > Run workflow
```

## Vercel 화면과 연결

Vercel 화면은 Supabase만 바라봅니다.

즉 GitHub Actions가 Supabase에 데이터를 업로드하면 Vercel/PWA 화면도 자동으로 최신 데이터가 보입니다.

## 2차 선택: Railway/Render/VPS

더 빠르고 지속적인 업데이트가 필요하면 GitHub Actions보다 Railway/Render/VPS가 낫습니다.

이미 추가한 파일:

```text
railway.json
Procfile
runtime.txt
requirements.txt
```

Railway에서는 환경변수만 넣고 배포하면 아래 명령으로 계속 실행됩니다.

```bash
cd engine && ALPHA_RADAR_LOOP=true python alpha_radar_engine_v1.py
```

## 보안 주의

절대 GitHub에 올리면 안 되는 파일:

```text
engine/.env
webapp_update/.env.local
```

이미 `.gitignore`에 제외 처리해두었습니다.

## 추천 진행 순서

1. GitHub에 저장소 만들기
2. 이 프로젝트 업로드
3. GitHub Secrets 입력
4. Actions에서 수동 실행 테스트
5. Vercel PWA 화면에서 데이터 갱신 확인
6. 문제 없으면 10분 자동 실행 유지
7. 더 빠른 실시간성이 필요하면 Railway/VPS로 이전

