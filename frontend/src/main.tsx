import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import { registerServiceWorker } from './services/serviceWorkerRegistration.ts';

// Dynamic API base URL resolution from environment (AC-VITE / Section 6)
const isLocalhost =
  typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    window.location.hostname === '[::1]' ||
    window.location.hostname.endsWith('.local'));

const envApiBase =
  typeof import.meta !== 'undefined' &&
  import.meta.env &&
  import.meta.env.VITE_API_BASE_URL !== undefined &&
  import.meta.env.VITE_API_BASE_URL !== ''
    ? (import.meta.env.VITE_API_BASE_URL as string)
    : undefined;

// If VITE_API_BASE_URL is explicitly configured, use it.
// If not configured: in DEV mode or on localhost, use "" (relative path so Vite proxy forwards to local backend).
// In production builds hosted remotely (e.g. Vercel), fall back to Render production backend.
const rawApiBase =
  envApiBase !== undefined
    ? envApiBase
    : (import.meta.env?.DEV || isLocalhost)
    ? ''
    : 'https://mandiq-backend.onrender.com';

// Aggressively strip any whitespace, carriage returns, newlines, and trailing slashes
const apiBase = rawApiBase.replace(/\s+/g, '').replace(/\/+$/, '');

if (typeof window !== 'undefined' && window.fetch) {
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === 'string') {
      const cleanPath = input.trim();
      if (cleanPath.startsWith('/api/') || cleanPath.startsWith('/health')) {
        const targetUrl = apiBase ? `${apiBase}${cleanPath}` : cleanPath;
        return originalFetch(targetUrl, init);
      }
    }
    return originalFetch(input, init);
  };
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

registerServiceWorker();
