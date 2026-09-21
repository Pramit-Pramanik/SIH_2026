/**
 * MandiQ Service Worker Registration Handler
 * Registers /sw.js in compatible browser environments to support offline PWA reload.
 */

export function registerServiceWorker(): void {
  if (typeof window === 'undefined') return;

  if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .then((registration) => {
          if (typeof import.meta !== 'undefined' && (import.meta as any).env?.DEV) {
            console.log('[MandiQ PWA] Service Worker registered with scope:', registration.scope);
          }
        })
        .catch((error) => {
          console.warn('[MandiQ PWA] Service Worker registration failed:', error);
        });
    });
  }
}

export function unregisterServiceWorker(): void {
  if (typeof window === 'undefined') return;

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready
      .then((registration) => {
        registration.unregister();
      })
      .catch((error) => {
        console.warn('[MandiQ PWA] Service Worker unregister error:', error);
      });
  }
}
