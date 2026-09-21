const puppeteer = require('puppeteer-core');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox']
  });
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:5173');

  // Clear and type admin credentials
  await page.click('#username', { clickCount: 3 });
  await page.keyboard.press('Backspace');
  await page.type('#username', 'admin');

  await page.click('#password', { clickCount: 3 });
  await page.keyboard.press('Backspace');
  await page.type('#password', 'Admin@MandiQ2026');

  await new Promise(r => setTimeout(r, 200));

  // Click Sign in
  const btns = await page.$$('button');
  for (const b of btns) {
    const txt = await page.evaluate(el => el.textContent, b);
    if (txt && (txt.includes('Sign In') || txt.includes('Access Portal'))) {
      await b.click();
      break;
    }
  }

  await page.waitForSelector('header');

  const results = await page.evaluate(async () => {
    const token = localStorage.getItem('mandiq_token');
    const h = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = `Bearer ${token}`;

    const testEndpoint = async (url) => {
      try {
        const res = await fetch(url, { headers: h });
        const text = await res.text();
        let json = null;
        try { json = JSON.parse(text); } catch {}
        return { status: res.status, ok: res.ok, dataSnippet: json ? JSON.stringify(json).slice(0, 100) : text.slice(0, 100) };
      } catch (err) {
        return { error: err.message };
      }
    };

    return {
      token: token ? token.slice(0, 25) + '...' : null,
      mandis: await testEndpoint('/api/v1/mandis'),
      crops: await testEndpoint('/api/v1/crops'),
      users: await testEndpoint('/api/v1/admin/users'),
      metrics: await testEndpoint('/api/v1/admin/metrics?mandi_id=1'),
      health: await testEndpoint('/api/v1/health'),
      slots: await testEndpoint('/api/v1/slots?mandi_id=1&scheduled_date=2026-09-19'),
    };
  });

  console.log('Results from inside browser context:');
  console.log(JSON.stringify(results, null, 2));

  await browser.close();
}

main().catch(console.error);
