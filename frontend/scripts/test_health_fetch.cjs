const puppeteer = require('puppeteer-core');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function testHealth() {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox']
  });
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:5173');

  const result = await page.evaluate(async () => {
    const t0 = performance.now();
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      const res = await fetch('/api/v1/mandis', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const t1 = performance.now();
      return { ok: res.ok, status: res.status, timeMs: Math.round(t1 - t0) };
    } catch (e) {
      const t1 = performance.now();
      return { errorName: e.name, errorMessage: e.message, timeMs: Math.round(t1 - t0) };
    }
  });

  console.log('Result of fetch(/api/v1/mandis):', result);

  const healthResult = await page.evaluate(async () => {
    const t0 = performance.now();
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      const res = await fetch('/api/v1/health', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const t1 = performance.now();
      const data = await res.json();
      return { ok: res.ok, status: res.status, data, timeMs: Math.round(t1 - t0) };
    } catch (e) {
      const t1 = performance.now();
      return { errorName: e.name, errorMessage: e.message, timeMs: Math.round(t1 - t0) };
    }
  });

  console.log('Result of fetch(/api/v1/health):', healthResult);

  await browser.close();
}

testHealth().catch(console.error);
