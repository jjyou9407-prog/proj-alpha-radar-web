import type { CapacitorConfig } from '@capacitor/cli';

const appUrl = process.env.CAPACITOR_SERVER_URL || 'http://172.30.1.67:3000';

const config: CapacitorConfig = {
  appId: 'com.yhj.alpharadar',
  appName: 'Alpha Radar AI',
  webDir: '.next',
  server: {
    url: appUrl,
    cleartext: appUrl.startsWith('http://'),
  },
  ios: {
    contentInset: 'automatic',
  },
  plugins: {
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#03070d',
    },
    SplashScreen: {
      launchShowDuration: 1200,
      backgroundColor: '#03070d',
      showSpinner: false,
    },
  },
};

export default config;
