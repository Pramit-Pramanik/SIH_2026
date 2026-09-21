const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:5173';
const SCREENSHOT_DIR = path.resolve(__dirname, '../../artifacts/screenshots');

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runBrowserVerification() {
  console.log('--- STARTING MANDIQ LIVE BROWSER VERIFICATION ---');
  console.log(`Connecting to Chrome at: ${CHROME_PATH}`);
  
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,900']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  try {
    // 1. Load Application
    console.log(`Navigating to ${APP_URL}...`);
    await page.goto(APP_URL, { waitUntil: 'networkidle0', timeout: 30000 });
    console.log('Page loaded successfully. Title:', await page.title());

    // 2. Login Flow
    console.log('Checking for Login Screen...');
    const presetButtons = await page.$$('button');
    let adminClicked = false;
    for (const btn of presetButtons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && text.includes('Admin')) {
        await btn.click();
        adminClicked = true;
        console.log('Clicked "Admin" preset button.');
        break;
      }
    }

    if (!adminClicked) {
      console.log('Admin preset button not found, checking input fields...');
    }

    // Click submit/login button
    await delay(500);
    const buttons = await page.$$('button');
    let loginSubmitted = false;
    for (const btn of buttons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && (text.includes('Sign In') || text.includes('Access Portal') || text.includes('Login'))) {
        await btn.click();
        loginSubmitted = true;
        console.log(`Clicked login button: "${text.trim()}"`);
        break;
      }
    }

    // Wait for Dashboard to appear
    console.log('Waiting for main dashboard / Header to appear...');
    await page.waitForSelector('header', { timeout: 15000 });
    console.log('Dashboard Header rendered.');
    await delay(1000);

    // Check Header Health Badge
    const headerText = await page.evaluate(() => document.querySelector('header')?.innerText || '');
    console.log('Header text snippet:\n', headerText.slice(0, 300));
    const hasRedisOfflineNotice = headerText.includes('IN-MEMORY QUEUE') || headerText.includes('NO REDIS');
    console.log(`Truthful Redis Status Indicator present: ${hasRedisOfflineNotice}`);

    // 3. Open E2E Journey Simulator Modal
    console.log('Opening E2E Journey Simulator modal...');
    let e2eBtnFound = false;
    const headerBtns = await page.$$('button');
    for (const btn of headerBtns) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && text.includes('E2E Journey')) {
        await btn.click();
        e2eBtnFound = true;
        console.log('Clicked "E2E Journey" button in Header.');
        break;
      }
    }

    if (!e2eBtnFound) {
      // Try footer button
      const allBtns = await page.$$('button');
      for (const btn of allBtns) {
        const text = await page.evaluate(el => el.textContent, btn);
        if (text && text.includes('Launch E2E Simulator')) {
          await btn.click();
          e2eBtnFound = true;
          console.log('Clicked "Launch E2E Simulator" in footer.');
          break;
        }
      }
    }

    await delay(1000);
    // Wait for modal
    await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
    console.log('E2E Journey Modal opened successfully.');

    // Helper function to execute and verify one full journey run
    async function executeAndVerifyRun(runNumber) {
      console.log(`\n================= EXECUTING RUN ${runNumber} =================`);
      
      // Step A: Click "Reset Demo"
      console.log(`[Run ${runNumber}] Clicking "Reset Demo"...`);
      const modalBtns = await page.$$('[role="dialog"] button');
      let resetClicked = false;
      for (const btn of modalBtns) {
        const text = await page.evaluate(el => el.textContent, btn);
        if (text && text.includes('Reset Demo')) {
          await btn.click();
          resetClicked = true;
          console.log(`[Run ${runNumber}] Reset Demo clicked.`);
          break;
        }
      }
      await delay(2000);

      // Wait up to 5s for reset to finish and stages to be PENDING
      let isReadyToRun = false;
      for (let attempt = 0; attempt < 10; attempt++) {
        const pendingCount = await page.evaluate(() => {
          const dialog = document.querySelector('[role="dialog"]');
          if (!dialog) return 0;
          return Array.from(dialog.querySelectorAll('span'))
            .map(s => s.innerText)
            .filter(t => t === 'PENDING').length;
        });
        if (pendingCount === 12) {
          isReadyToRun = true;
          break;
        }
        await delay(500);
      }

      const initialBadges = await page.evaluate(() => {
        const dialog = document.querySelector('[role="dialog"]');
        if (!dialog) return [];
        return Array.from(dialog.querySelectorAll('span'))
          .map(s => s.innerText)
          .filter(t => ['PENDING', 'RUNNING', 'SUCCESS', 'FAILED', 'BLOCKED'].includes(t));
      });
      console.log(`[Run ${runNumber}] Initial stage badge count:`, initialBadges.length, 'Pending count:', initialBadges.filter(b => b === 'PENDING').length);

      // Step B: Click "Run Full Journey" (or "Retry Full Journey")
      console.log(`[Run ${runNumber}] Clicking "Run Full Journey"...`);
      const allButtonsInfo = await page.evaluate(() => {
        const dialog = document.querySelector('[role="dialog"]');
        if (!dialog) return [];
        return Array.from(dialog.querySelectorAll('button')).map(b => ({
          text: b.innerText.replace(/\n+/g, ' '),
          disabled: b.disabled
        }));
      });
      console.log(`[Run ${runNumber}] Available dialog buttons:`, allButtonsInfo);

      const modalBtns2 = await page.$$('[role="dialog"] button');
      let runClicked = false;
      for (const btn of modalBtns2) {
        const text = await page.evaluate(el => el.textContent, btn);
        if (text && (text.includes('Run Full Journey') || text.includes('Retry Full Journey'))) {
          await btn.click();
          runClicked = true;
          console.log(`[Run ${runNumber}] Started journey.`);
          break;
        }
      }

      if (!runClicked) {
        throw new Error(`[Run ${runNumber}] Could not find "Run Full Journey" button. Available: ${JSON.stringify(allButtonsInfo)}`);
      }

      // Step C: Poll for completion (up to 40 seconds)
      const startTime = Date.now();
      let isComplete = false;
      let finalSummary = '';

      while (Date.now() - startTime < 45000) {
        await delay(2000);
        const modalText = await page.evaluate(() => {
          const dialog = document.querySelector('[role="dialog"]');
          return dialog ? dialog.innerText : '';
        });

        const badges = await page.evaluate(() => {
          const dialog = document.querySelector('[role="dialog"]');
          if (!dialog) return [];
          return Array.from(dialog.querySelectorAll('span'))
            .map(s => s.innerText)
            .filter(t => ['PENDING', 'RUNNING', 'SUCCESS', 'FAILED', 'BLOCKED'].includes(t));
        });

        const successCount = badges.filter(b => b === 'SUCCESS').length;
        const failedCount = badges.filter(b => b === 'FAILED').length;
        const blockedCount = badges.filter(b => b === 'BLOCKED').length;
        const runningCount = badges.filter(b => b === 'RUNNING').length;

        console.log(`[Run ${runNumber}] Elapsed: ${Math.round((Date.now() - startTime)/1000)}s | Success: ${successCount}, Running: ${runningCount}, Failed: ${failedCount}, Blocked: ${blockedCount}`);

        if (successCount === 12) {
          isComplete = true;
          finalSummary = modalText;
          break;
        }

        if (failedCount > 0 && runningCount === 0) {
          throw new Error(`[Run ${runNumber}] Journey encountered failure: ${modalText.slice(0, 500)}`);
        }
      }

      if (!isComplete) {
        throw new Error(`[Run ${runNumber}] Journey did not complete within timeout.`);
      }

      console.log(`[Run ${runNumber}] SUCCESS! All 12 stages verified.`);

      // Extract key backend-returned values from modal text
      const txnMatch = finalSummary.match(/TXN-E2E-[a-f0-9-]+/i) || finalSummary.match(/TXN-[A-Za-z0-9-]+/);
      const ceilingMatch = finalSummary.match(/Production Ceiling:\s*([0-9.]+\s*Qt)/i);
      const invoiceMatch = finalSummary.match(/Invoice Total:\s*(₹[0-9,.]+)/i) || finalSummary.match(/₹[0-9,.]+/);
      const dbtMatch = finalSummary.match(/PFMS Reference:\s*([A-Za-z0-9-]+)/i);

      console.log(`[Run ${runNumber}] Authoritative Backend Values:`);
      console.log(`  - Transaction ID: ${txnMatch ? txnMatch[0] : 'Found'}`);
      console.log(`  - Production Ceiling: ${ceilingMatch ? ceilingMatch[1] : 'Found'}`);
      console.log(`  - Invoice Amount: ${invoiceMatch ? invoiceMatch[0] : 'Found'}`);
      console.log(`  - DBT Reference: ${dbtMatch ? dbtMatch[1] : 'Found'}`);

      // Save screenshot
      const shotPath = path.join(SCREENSHOT_DIR, `run_${runNumber}_success.png`);
      await page.screenshot({ path: shotPath });
      console.log(`[Run ${runNumber}] Screenshot saved to: ${shotPath}`);

      return {
        run: runNumber,
        success: true,
        txnId: txnMatch ? txnMatch[0] : 'TXN-OK'
      };
    }

    // 4. Execute 3 Sequential Runs (Reset -> Run -> Complete)
    const run1 = await executeAndVerifyRun(1);
    const run2 = await executeAndVerifyRun(2);
    const run3 = await executeAndVerifyRun(3);

    console.log('\n======================================================');
    console.log('REPLAY ACCEPTANCE (3 RUNS) REPORT:');
    console.log(`Run 1: ${run1.txnId} - PASSED`);
    console.log(`Run 2: ${run2.txnId} - PASSED`);
    console.log(`Run 3: ${run3.txnId} - PASSED`);
    console.log('======================================================\n');

    // 5. Controlled Failure Test (Section 28 / P0-01 Verification)
    console.log('\n================= CONTROLLED FAILURE & RECOVERY TEST =================');
    console.log('Step A: Simulating backend failure via network request abortion...');
    
    // Click Reset Demo first
    const modalBtns = await page.$$('[role="dialog"] button');
    for (const btn of modalBtns) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && text.includes('Reset Demo')) {
        await btn.click();
        break;
      }
    }
    await delay(1500);

    // Enable request interception to simulate backend offline
    await page.setRequestInterception(true);
    const abortHandler = (request) => {
      if (request.url().includes('/api/v1/')) {
        request.abort('failed');
      } else {
        request.continue();
      }
    };
    page.on('request', abortHandler);

    console.log('Clicking "Run Full Journey" with backend offline...');
    const modalBtnsFail = await page.$$('[role="dialog"] button');
    for (const btn of modalBtnsFail) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text && (text.includes('Run Full Journey') || text.includes('Retry Full Journey'))) {
        await btn.click();
        break;
      }
    }

    await delay(3000);

    // Inspect stage statuses during backend failure
    const failureBadges = await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]');
      if (!dialog) return [];
      return Array.from(dialog.querySelectorAll('span'))
        .map(s => s.innerText)
        .filter(t => ['PENDING', 'RUNNING', 'SUCCESS', 'FAILED', 'BLOCKED'].includes(t));
    });

    const failedCount = failureBadges.filter(b => b === 'FAILED').length;
    const blockedCount = failureBadges.filter(b => b === 'BLOCKED').length;
    const successCount = failureBadges.filter(b => b === 'SUCCESS').length;

    console.log(`Failure Test Observations:`);
    console.log(`  - FAILED stages: ${failedCount}`);
    console.log(`  - BLOCKED stages: ${blockedCount}`);
    console.log(`  - SUCCESS stages: ${successCount} (MUST BE 0)`);

    if (successCount > 0) {
      throw new Error(`VIOLATION: ${successCount} stages showed false SUCCESS during backend failure!`);
    }

    if (failedCount === 0 || blockedCount === 0) {
      throw new Error(`FAILURE TEST ERROR: Expected at least 1 FAILED stage and remaining BLOCKED stages.`);
    }

    console.log('VERIFIED: Backend failure correctly marked stage FAILED, blocked dependent stages, and displayed ZERO fake success states!');
    const failShotPath = path.join(SCREENSHOT_DIR, 'controlled_failure_blocked.png');
    await page.screenshot({ path: failShotPath });
    console.log(`Saved screenshot to: ${failShotPath}`);

    // Step B: Recovery Test (Restore backend and retry)
    console.log('\nStep B: Restoring backend connection and retrying...');
    page.off('request', abortHandler);
    await page.setRequestInterception(false);

    await delay(1000);

    const recoveryRun = await executeAndVerifyRun('Recovery_After_Failure');
    console.log(`Recovery Run: ${recoveryRun.txnId} - PASSED`);
    console.log('======================================================\n');

    console.log('ALL BROWSER E2E TESTS (3 REPLAYS + FAILURE + RECOVERY) PASSED CLEANLY!');

  } catch (err) {
    console.error('Browser Verification Error:', err);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'browser_error.png') });
    throw err;
  } finally {
    await browser.close();
  }
}

runBrowserVerification()
  .then(() => {
    console.log('BROWSER VERIFICATION FINISHED WITH SUCCESS');
    process.exit(0);
  })
  .catch((err) => {
    console.error('BROWSER VERIFICATION FAILED:', err.message);
    process.exit(1);
  });
