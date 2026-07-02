# Alpha Radar AI - Windows에서 iPhone 앱처럼 쓰기

Mac 없이 갈 수 있는 최선의 방식은 **Vercel 배포 + PWA 홈화면 추가**입니다.

## 결과물

- App Store 없이 아이폰 홈화면에 앱 아이콘 생성
- Safari 주소창 없이 앱처럼 실행
- 검색/상세/모의투자/뉴스 탭 사용
- Vercel 배포 시 PC CMD가 꺼져 있어도 화면 접속 가능

## 1. 로컬 테스트

Windows에서:

```bat
cd /d "C:\Users\user\Desktop\alpha_radar_ai_engine_v1_package\alpha_radar_ai_engine_v1\webapp_update"
npm run dev -- -H 0.0.0.0 -p 3000
```

아이폰 Safari:

```text
http://172.30.1.67:3000/?v=pwa
```

## 2. Vercel 로그인

처음 한 번만:

```bat
npx vercel login
```

## 3. Vercel 배포

프리뷰:

```bat
npx vercel
```

정식 배포:

```bat
npx vercel --prod
```

또는 `deploy_to_vercel.bat`를 실행해서 빌드 확인 후 안내대로 진행하세요.

## 4. Vercel 환경변수

Vercel 프로젝트 설정에서 아래 환경변수를 넣어야 합니다.

```text
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
```

값은 로컬 `.env.local`에 있는 값과 동일하게 넣으면 됩니다.

## 5. 아이폰 홈화면 추가

아이폰 Safari에서 Vercel 주소 접속:

```text
https://배포된주소.vercel.app
```

그 다음:

1. 하단 공유 버튼
2. 홈 화면에 추가
3. 이름 `Alpha Radar`
4. 추가

## 6. 캐시 때문에 옛 화면이 보일 때

주소 뒤에 버전 파라미터를 붙입니다.

```text
https://배포된주소.vercel.app/?v=20260702
```

그래도 안 되면 홈화면 앱 삭제 후 다시 추가하세요.

## 7. 데이터 갱신 주의

Vercel은 화면만 배포합니다.

종목 스캔/핫뉴스 수집/Supabase 업로드는 여전히 알파레이더 엔진이 담당합니다.

즉 Windows PC에서 아래 엔진 CMD가 켜져 있어야 새 데이터가 계속 들어갑니다.

```bat
cd /d "C:\Users\user\Desktop\alpha_radar_ai_engine_v1_package\alpha_radar_ai_engine_v1\engine"
set ALPHA_RADAR_LOOP=true
python alpha_radar_engine_v1.py
```

나중에 엔진까지 클라우드 서버로 옮기면 PC를 켜두지 않아도 됩니다.

