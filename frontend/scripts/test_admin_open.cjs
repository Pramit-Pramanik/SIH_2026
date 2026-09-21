const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:5173';

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function testAdminTab() {
  console.log('--- TESTING ADMIN DASHBOARD TAB OPENING ---');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,900']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  const consoleLogs = [];
  const pageErrors = [];

  page.on('console', (msg) => {
    consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
  });

  page.on('pageerror', (err) => {
    pageErrors.push(err.toString());
    console.error('PAGE ERROR:', err);
  });

  try {
    await page.goto(APP_URL, { waitUntil: 'networkidle0', timeout: 30000 });
    console.log('Loaded login screen.');

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
      await delay(1000);
    }

    // Click exact Admin preset button
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const admin = btns.find(b => b.innerText.trim() === 'Admin');
      if (admin) admin.click();
    });

    await delay(500);

    // Click Sign In button
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const signin = btns.find(b => b.innerText.includes('Sign In'));
      if (signin) signin.click();
    });

    await page.waitForSelector('header', { timeout: 10000 });
    console.log('Header appeared. Checking active tab and visible tabs...');
    await delay(1000);

    const tabInfo = await page.evaluate(() => {
      const tabs = Array.from(document.querySelectorAll('header nav button, header button'));
      return tabs.map(t => ({ text: t.innerText.trim(), active: t.className.includes('emerald') || t.className.includes('bg-') }));
    });
    console.log('Visible tabs/buttons:', tabInfo.slice(0, 10));

    // Check if Admin Hub button exists and click it
    const navButtons = await page.$$('button');
    let adminTabClicked = false;
    for (const btn of navButtons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && (text.includes('Admin Hub') || text.includes('व्यवस्थापक'))) {
        await btn.click();
        adminTabClicked = true;
        console.log('Clicked Admin Hub tab button!');
        break;
      }
    }

    await delay(3000);

    // Check each subtab
    const subtabs = ['Commodities & MSP', 'Staff Directory', 'Capacity & Slots', 'APMC Mandis'];
    for (const st of subtabs) {
      console.log(`Switching to subtab: ${st}...`);
      const clickedText = await page.evaluate((name) => {
        const btns = Array.from(document.querySelectorAll('main button'));
        const btn = btns.find(b => b.innerText.includes(name));
        if (btn) {
          btn.click();
          return btn.innerText.replace(/\n+/g, ' ');
        }
        return 'BUTTON NOT FOUND';
      }, st);
      console.log(`Subtab [${st}] button clicked: "${clickedText}"`);
      await delay(1200);

      const itemData = await page.evaluate((subtab) => {
        if (subtab === 'APMC Mandis') {
          const headings = Array.from(document.querySelectorAll('main h4')).map(h => h.innerText);
          const allText = document.querySelector('main')?.innerText.slice(0, 500) || '';
          return {
            count: headings.length,
            sample: headings.join(', ') || allText
          };
        }
        const rows = Array.from(document.querySelectorAll('table tbody tr'));
        return {
          count: rows.length,
          sample: rows[0] ? rows[0].innerText.replace(/\n+/g, ' | ').slice(0, 100) : 'NO ROWS'
        };
      }, st);
      console.log(`Subtab [${st}]: ${itemData.count} items rendered. Sample: ${itemData.sample}`);
      if (itemData.count === 0) {
        throw new Error(`Subtab [${st}] rendered 0 items! Expected active records.`);
      }
    }

    // Test Refresh State button
    console.log('Testing "Refresh State" button...');
    await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('main button')).find(b => b.innerText.includes('Refresh State'));
      if (btn) btn.click();
    });
    await delay(1200);
    console.log('Refresh State executed successfully.');

    const screenshotPath = path.resolve(__dirname, '../../artifacts/screenshots/admin_dashboard_open.png');
    await page.screenshot({ path: screenshotPath });
    console.log('Saved screenshot to:', screenshotPath);

    console.log('\nPage errors recorded:', pageErrors.length);
    if (pageErrors.length > 0) {
      pageErrors.forEach(e => console.error('  ERROR:', e));
      throw new Error('Page errors detected during Admin dashboard verification!');
    }
    console.log('--- ADMIN DASHBOARD FULL VERIFICATION PASSED ---');
  } finally {
    await browser.close();
  }
}

testAdminTab().catch(err => {
  console.error('Fatal error in testAdminTab:', err);
  process.exit(1);
});
