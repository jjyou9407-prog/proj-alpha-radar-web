# Alpha Radar AI iOS 앱 포장 안내

이 폴더는 기존 Next.js 알파레이더 웹앱을 Capacitor 기반 iOS 앱으로 감싸기 위한 설정을 포함합니다.

## 현재 방식

- 앱 이름: `Alpha Radar AI`
- iOS Bundle ID: `com.yhj.alpharadar`
- 기본 개발 주소: `http://172.30.1.67:3000`
- 앱은 iOS WebView 안에서 알파레이더 웹 화면을 로드합니다.

## Windows에서 가능한 것

Windows에서는 아래 작업까지 가능합니다.

```bat
npm install
npm run build
npm run ios:doctor
```

단, 실제 iOS 프로젝트 생성/빌드/실기기 실행/App Store 업로드는 macOS + Xcode가 필요합니다.

## Mac에서 iOS 프로젝트 생성

Mac으로 이 `webapp_update` 폴더를 옮긴 뒤 터미널에서 실행합니다.

```bash
npm install
npm run cap:add:ios
npm run cap:sync
npm run cap:open:ios
```

그러면 Xcode가 열리고, iPhone 실기기 또는 시뮬레이터로 실행할 수 있습니다.

## 실제 배포용 URL로 바꾸기

현재 `capacitor.config.ts`는 기본으로 PC 내부 주소를 사용합니다.

```ts
const appUrl = process.env.CAPACITOR_SERVER_URL || 'http://172.30.1.67:3000';
```

App Store/TestFlight 배포용으로는 Vercel 또는 개인 도메인 주소를 사용하는 것을 추천합니다.

Mac에서 예:

```bash
export CAPACITOR_SERVER_URL=https://your-alpha-radar-domain.com
npm run cap:sync
npm run cap:open:ios
```

## 주의

- `http://172.30.1.67:3000`은 같은 와이파이/내부망에서만 동작합니다.
- 외부 사용자에게 배포하려면 반드시 HTTPS 도메인이 필요합니다.
- 푸시 알림까지 넣으려면 Apple Developer 계정과 푸시 인증 설정이 추가로 필요합니다.
