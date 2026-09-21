/**
 * MandiQ Progressive Web App (PWA) Service Worker
 * 
 * Provides:
 * 1. Application shell precaching ('/', '/index.html', '/manifest.json')
 * 2. Offline application reload support via CacheStorage
 * 3. Strict network-only bypass for all '/api/...' requests (no sensitive API caching)
 * 4. Cache-first / stale-while-revalidate for static scripts, styles, and assets
 */

const CACHE_VERSION = 'v1';
const CACHE_SHELL = `mandiq-shell-${CACHE_VERSION}`;
const CACHE_RUNTIME = `mandiq-runtime-${CACHE_VERSION}`;

const PRECACHE_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/vite.svg'
];

// 1. Install: Precache application shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_SHELL).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => {
      return self.skipWaiting();
    })
  );
});

// 2. Activate: Clean up outdated caches
self.addEventListener('activate', (event) => {
  const currentCaches = [CACHE_SHELL, CACHE_RUNTIME];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (!currentCaches.includes(name)) {
            return caches.delete(name);
          }
        })
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// 3. Fetch: Route requests according to offline-first policy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Policy: Only intercept HTTP/HTTPS GET requests
  if (request.method !== 'GET') {
    return;
  }

  // CRITICAL CONSTRAINT: Strictly bypass all /api/ requests.
  // Sensitive authenticated API responses must NEVER be cached by the service worker.
  // Offline data is authoritative in IndexedDB WAL, not CacheStorage.
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Navigation requests (HTML document): Network-first with Cache fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_SHELL).then((cache) => {
              cache.put('/index.html', responseClone);
            });
          }
          return networkResponse;
        })
        .catch(() => {
          // Network failure: return cached application shell
          return caches.match('/index.html').then((cached) => {
            return cached || caches.match('/');
          });
        })
    );
    return;
  }

  // Static assets (JS, CSS, fonts, images, icons): Cache-first with Network update
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        // Fetch background update for freshness if online
        fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(CACHE_RUNTIME).then((cache) => {
              cache.put(request, networkResponse);
            });
          }
        }).catch(() => {
          // Expected when offline
        });
        return cachedResponse;
      }

      // Not in cache: fetch from network and store in runtime cache
      return fetch(request).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type === 'opaque') {
          return networkResponse;
        }
        const responseClone = networkResponse.clone();
        caches.open(CACHE_RUNTIME).then((cache) => {
          cache.put(request, responseClone);
        });
        return networkResponse;
      });
    })
  );
});
