'use client';

import { useEffect } from 'react';

export default function PwaClient() {
  useEffect(() => {
    if ('serviceWorker' in navigator && window.location.protocol === 'https:') {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }

    const standalone =
      window.matchMedia?.('(display-mode: standalone)').matches ||
      (window.navigator as any).standalone === true;

    if (standalone) {
      document.body.classList.add('pwa-standalone');
    }
  }, []);

  return null;
}
