import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import { registerServiceWorker } from './services/serviceWorkerRegistration.ts';

// Dynamic API base URL resolution from environment (AC-VITE / Section 6)
const apiBase = (
  (typeof import.meta !== 'undefined' && import.meta.env && (import.meta.env.VITE_API_BASE_URL as string)) || ''
).replace(/\/+$/, '');

if (apiBase && typeof window !== 'undefined' && window.fetch) {
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === 'string' && input.startsWith('/api/')) {
      return originalFetch(`${apiBase}${input}`, init);
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
