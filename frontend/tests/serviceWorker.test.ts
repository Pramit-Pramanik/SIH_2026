import test, { describe } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { registerServiceWorker } from '../src/services/serviceWorkerRegistration.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

describe('Service Worker & PWA Integration Tests', () => {
  const publicDir = path.resolve(__dirname, '../public');
  const swPath = path.join(publicDir, 'sw.js');
  const manifestPath = path.join(publicDir, 'manifest.json');
  const iconPath = path.join(publicDir, 'vite.svg');

  test('1. Service worker source file sw.js exists in public directory', () => {
    assert.equal(fs.existsSync(swPath), true, 'public/sw.js must exist');
    const content = fs.readFileSync(swPath, 'utf-8');
    assert.ok(content.length > 100, 'sw.js must contain implementation code');
  });

  test('2. Manifest.json is valid and configured for standalone PWA', () => {
    assert.equal(fs.existsSync(manifestPath), true, 'public/manifest.json must exist');
    const raw = fs.readFileSync(manifestPath, 'utf-8');
    const manifest = JSON.parse(raw);

    assert.equal(manifest.display, 'standalone');
    assert.equal(manifest.start_url, '/');
    assert.ok(Array.isArray(manifest.icons) && manifest.icons.length > 0, 'Must define icons');
    assert.equal(manifest.icons[0].src, '/vite.svg');
    assert.equal(fs.existsSync(iconPath), true, 'Icon asset /vite.svg must exist');
  });

  test('3. Precache list includes application shell files', () => {
    const swContent = fs.readFileSync(swPath, 'utf-8');
    assert.match(swContent, /'\/index\.html'/, 'Must precache /index.html');
    assert.match(swContent, /'\/manifest\.json'/, 'Must precache /manifest.json');
    assert.match(swContent, /'\/vite\.svg'/, 'Must precache /vite.svg');
  });

  test('4. Sensitive /api/ requests are strictly excluded from service worker caching', () => {
    const swContent = fs.readFileSync(swPath, 'utf-8');
    // Must contain explicit bypass for /api/
    assert.match(
      swContent,
      /url\.pathname\.startsWith\(['"]\/api\/['"]\)/,
      'Must check and bypass url.pathname.startsWith("/api/")'
    );
  });

  test('5. Non-GET requests (POST/PUT/DELETE) bypass cache storage', () => {
    const swContent = fs.readFileSync(swPath, 'utf-8');
    assert.match(
      swContent,
      /request\.method\s*!==\s*['"]GET['"]/,
      'Must bypass all non-GET requests'
    );
  });

  test('6. HTML Navigation requests implement offline fallback to /index.html', () => {
    const swContent = fs.readFileSync(swPath, 'utf-8');
    assert.match(swContent, /request\.mode\s*===\s*['"]navigate['"]/, 'Must handle navigate requests');
    assert.match(swContent, /caches\.match\(['"]\/index\.html['"]\)/, 'Must fallback to cached index.html');
  });

  test('7. Service worker registration logic executes safely in browser environment', () => {
    // Mock navigator.serviceWorker and window in test environment
    const registered: Array<{ scriptUrl: string; options?: unknown }> = [];
    // @ts-expect-error - mock navigator for test
    globalThis.navigator.serviceWorker = {
      register: async (url: string, opts?: unknown) => {
        registered.push({ scriptUrl: url, options: opts });
        return { scope: '/' } as ServiceWorkerRegistration;
      }
    };

    // @ts-expect-error - mock window location
    globalThis.window = {
      location: { protocol: 'http:' },
      addEventListener: (event: string, callback: () => void) => {
        if (event === 'load') callback();
      }
    };

    registerServiceWorker();
    assert.equal(registered.length, 1);
    assert.equal(registered[0].scriptUrl, '/sw.js');
  });
});
