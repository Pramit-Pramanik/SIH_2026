const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox']
  });
  const page = await browser.newPage();
  
  page.on('response', async res => {
    if (res.url().includes('/auth/')) {
      console.log('HTTP', res.status(), res.url());
      try {
        console.log('Response body:', await res.text());
      } catch {}
    }
  });

  await page.goto('http://127.0.0.1:5173');
  await new Promise(r => setTimeout(r, 1000));

  // Check if logged in, if so click logout
  const isDashboard = await page.evaluate(() => {
    const btn = document.querySelector('header button[title*="Sign out"]');
    if (btn) {
      btn.click();
      return true;
    }
    return false;
  });

  if (isDashboard) {
    console.log('Logged out of previous session.');
    await new Promise(r => setTimeout(r, 1000));
  }

  // Print all buttons on login screen
  const btnTexts = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim());
  });
  console.log('Buttons on screen:', btnTexts);

  // Click the 'Admin' button
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const admin = btns.find(b => b.innerText.trim() === 'Admin');
    if (admin) {
      admin.click();
      console.log('Clicked exact Admin button');
    }
  });

  await new Promise(r => setTimeout(r, 500));

  // Inspect the input fields
  const inputs = await page.evaluate(() => {
    const u = document.querySelector('#username');
    const p = document.querySelector('#password');
    return {
      username: u ? u.value : null,
      password: p ? p.value : null
    };
  });
  console.log('Inputs after clicking Admin button:', inputs);

  // Now click Sign in
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const signin = btns.find(b => b.innerText.includes('Sign In'));
    if (signin) signin.click();
  });

  await new Promise(r => setTimeout(r, 2000));

  await new Promise(r => setTimeout(r, 2500));

  const adminDashboardState = await page.evaluate(() => {
    const main = document.querySelector('main');
    if (!main) return { error: 'No main tag' };

    const heading = main.querySelector('h2')?.innerText;
    const statsCards = Array.from(main.querySelectorAll('.grid > div')).map(d => d.innerText.replace(/\n+/g, ' | '));
    const subtabs = Array.from(main.querySelectorAll('button')).map(b => b.innerText.trim()).filter(t => t.includes('('));
    const feedback = main.querySelector('.bg-rose-50, .bg-emerald-50')?.innerText;
    const offlineWarning = main.querySelector('h4')?.innerText;

    return {
      heading,
      offlineWarning: offlineWarning || null,
      feedback: feedback || null,
      subtabs,
      statsSample: statsCards.slice(0, 6)
    };
  });

  console.log('Admin Dashboard Rendered State:');
  console.log(JSON.stringify(adminDashboardState, null, 2));

  await page.screenshot({ path: path.resolve(__dirname, '../../artifacts/screenshots/admin_dashboard_verified.png') });
  console.log('Saved screenshot to admin_dashboard_verified.png');

  await browser.close();
}

main().catch(console.error);
