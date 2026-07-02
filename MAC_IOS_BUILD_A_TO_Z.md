# Alpha Radar AI - Mac으로 iOS 앱 빌드 A to Z

이 문서는 Windows에서 준비한 알파레이더 iOS 앱 프로젝트를 Mac으로 옮겨서 아이폰 앱처럼 실행/TestFlight/App Store 배포까지 가는 전체 흐름입니다.

## 0. 전체 구조 이해

알파레이더는 크게 2개가 필요합니다.

1. 알파레이더 엔진
   - 종목 스캔
   - 가격 업데이트
   - 핫뉴스 수집
   - Supabase 업로드

2. 알파레이더 화면/iOS 앱
   - 사용자가 보는 화면
   - 검색/상세/모의투자/뉴스 사이드바
   - Capacitor iOS 앱 껍데기로 감싼 화면

iOS 앱은 화면을 앱처럼 보여주는 역할이고, 데이터 갱신은 엔진이 계속 돌고 있어야 합니다.

## 1. Mac에 필요한 것

Mac에 아래 프로그램이 필요합니다.

- Xcode
- Node.js LTS
- Git
- Apple ID
- 아이폰 실기기 테스트 시 USB-C/Lightning 케이블
- App Store/TestFlight 배포 시 Apple Developer Program 계정

## 2. Mac 초기 세팅

### 2-1. Xcode 설치

Mac App Store에서 Xcode 설치.

설치 후 한 번 실행해서 약관 동의와 추가 컴포넌트 설치를 끝내세요.

### 2-2. Xcode Command Line Tools 확인

터미널에서:

```bash
xcode-select --install
```

이미 설치되어 있으면 설치되어 있다고 나옵니다.

### 2-3. Node.js 설치

추천은 Node.js LTS입니다.

설치 확인:

```bash
node -v
npm -v
```

## 3. Windows에서 Mac으로 옮길 폴더

Windows에서 아래 폴더를 Mac으로 옮깁니다.

```text
C:\Users\user\Desktop\alpha_radar_ai_engine_v1_package\alpha_radar_ai_engine_v1\webapp_update
```

용량을 줄이려면 아래 폴더는 제외해도 됩니다.

- node_modules
- .next
- .vercel
- .git

Mac에서 `npm install`과 `npm run build`를 다시 하면 됩니다.

## 4. Mac에서 프로젝트 열기

터미널에서 옮긴 폴더로 이동:

```bash
cd /path/to/webapp_update
```

예:

```bash
cd ~/Desktop/webapp_update
```

## 5. 의존성 설치

```bash
npm install
```

## 6. 알파레이더 웹 빌드

```bash
npm run build
```

## 7. Capacitor iOS 동기화

```bash
npm run cap:sync
```

만약 iOS 폴더가 없다고 나오면:

```bash
npm run cap:add:ios
npm run cap:sync
```

## 8. Xcode 열기

```bash
npm run cap:open:ios
```

또는 직접 열기:

```text
webapp_update/ios/App/App.xcodeproj
```

## 9. Xcode에서 꼭 확인할 것

Xcode가 열리면 왼쪽에서 `App` 프로젝트를 선택합니다.

확인할 항목:

- Bundle Identifier: `com.yhj.alpharadar`
- Display Name: `Alpha Radar AI`
- Signing & Capabilities
  - Team: 본인 Apple ID 또는 개발자 팀 선택
  - Automatically manage signing 체크

## 10. 아이폰 실기기 실행

1. 아이폰을 Mac에 연결
2. 아이폰에서 “이 컴퓨터를 신뢰” 선택
3. Xcode 상단 실행 대상에서 내 아이폰 선택
4. ▶ Run 클릭

처음 실행할 때 개발자 신뢰 오류가 나면:

아이폰에서:

```text
설정 > 일반 > VPN 및 기기 관리 > 개발자 앱 신뢰
```

## 11. 현재 개발 주소 주의

현재 Capacitor 설정은 기본으로 아래 주소를 봅니다.

```text
http://172.30.1.67:3000
```

이건 Windows PC의 내부 IP입니다.

즉, Mac/아이폰이 같은 네트워크에 있고 Windows PC에서 알파레이더 웹 CMD가 켜져 있어야 앱 화면이 보입니다.

Windows에서 실행:

```bat
cd /d "C:\Users\user\Desktop\alpha_radar_ai_engine_v1_package\alpha_radar_ai_engine_v1\webapp_update"
npm run dev -- -H 0.0.0.0 -p 3000
```

## 12. 배포용으로 바꾸려면

진짜 앱처럼 외부에서도 쓰려면 내부 IP가 아니라 HTTPS 주소가 필요합니다.

추천:

- Vercel
- Netlify
- 개인 서버
- 개인 도메인 + HTTPS

예:

```text
https://alpha-radar.yourdomain.com
```

Mac에서 임시로 앱 주소 바꿔서 sync:

```bash
export CAPACITOR_SERVER_URL=https://alpha-radar.yourdomain.com
npm run cap:sync
npm run cap:open:ios
```

## 13. TestFlight 배포 흐름

App Store Connect에서 앱 생성 후:

1. Xcode에서 Signing Team 설정
2. Product > Archive
3. Distribute App
4. App Store Connect 업로드
5. TestFlight에서 내부 테스터 추가
6. 아이폰 TestFlight 앱으로 설치

## 14. App Store 배포 흐름

필요한 것:

- 앱 이름
- 아이콘
- 스크린샷
- 개인정보 처리방침 URL
- 앱 설명
- 카테고리
- 심사 제출

금융/투자 관련 앱은 심사에서 설명을 잘 써야 합니다.

추천 문구:

```text
Alpha Radar AI는 시장 데이터를 기반으로 종목 정보를 정리해 보여주는 참고용 리서치 도구입니다.
본 앱은 투자 수익을 보장하지 않으며, 매수/매도 권유가 아닙니다.
```

## 15. 꼭 넣어야 하는 고지

앱 안 또는 설명에 아래 문구를 넣는 것을 추천합니다.

```text
본 서비스는 투자 참고용 정보 제공 도구이며, 투자 판단과 책임은 사용자 본인에게 있습니다.
제공되는 점수, 뉴스, 가격 정보는 지연되거나 부정확할 수 있으며 수익을 보장하지 않습니다.
```

## 16. 푸시 알림까지 넣고 싶다면

추가로 필요한 것:

- Apple Developer 계정
- APNs 설정
- Supabase Edge Function 또는 별도 서버
- Capacitor Push Notifications 플러그인

1차 앱 포장 후 2차 업그레이드로 진행하는 것을 추천합니다.

## 17. 흔한 오류

### Xcode에서 Signing 오류

- Apple ID 로그인 확인
- Team 선택
- Bundle ID 중복 여부 확인

### 앱은 켜지는데 화면이 안 뜸

- Windows 알파레이더 웹 CMD가 켜져 있는지 확인
- 아이폰/Mac/Windows가 같은 네트워크인지 확인
- `http://172.30.1.67:3000` 접속 가능한지 Safari에서 확인

### 뉴스 탭이 안 뜸

- 옛날 PWA 캐시일 수 있음
- Safari 새로고침
- 홈화면 앱 삭제 후 다시 추가
- `?v=hotnews` 붙여서 접속

## 18. 추천 진행 순서

1. Windows에서 알파레이더 엔진/웹 정상 실행
2. Mac으로 `webapp_update` 이동
3. Mac에서 `npm install`
4. `npm run build`
5. `npm run cap:sync`
6. `npm run cap:open:ios`
7. 아이폰 실기기 실행
8. HTTPS 도메인 연결
9. TestFlight 배포
10. 푸시 알림 추가
11. App Store 심사 제출

