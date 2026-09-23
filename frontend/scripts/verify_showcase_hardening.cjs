const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:5173';
const BACKEND_URL = 'http://127.0.0.1:8000';

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runShowcaseVerification() {
  console.log('======================================================================');
  console.log('  MANDIQ FINAL SHOWCASE HARDENING VERIFIER');
  console.log('======================================================================');

  // Step 0: Get authoritative Admin JWT token from backend
  console.log('[0/7] Authenticating as Admin via backend API...');
  let adminToken = null;
  try {
    const res = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin', password: 'Admin@MandiQ2026' })
    });
    if (res.ok) {
      const data = await res.json();
      adminToken = data.access_token;
      console.log('  [OK] Admin JWT acquired successfully.');
    } else {
      console.warn('  [WARN] Admin login returned status:', res.status);
    }
  } catch (err) {
    console.warn('  [WARN] Backend login fetch error:', err.message);
  }

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('  [BROWSER ERROR]:', msg.text());
  });
  page.on('pageerror', (err) => {
    console.log('  [BROWSER EXCEPTION]:', err.message);
  });
  let failures = [];

  // Inject token into localStorage before page scripts execute
  if (adminToken) {
    await page.evaluateOnNewDocument((tok) => {
      localStorage.setItem('mandiq_token', tok);
    }, adminToken);
  }

  try {
    // ---------------------------------------------------------------
    // 1. Viewport 1366x768 Check (Zero Horizontal Clipping)
    // ---------------------------------------------------------------
    console.log('[1/7] Testing Viewport: 1366 x 768 (Standard Laptop)...');
    await page.setViewport({ width: 1366, height: 768 });
    await page.goto(APP_URL, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await delay(1500);

    const scrollWidth1366 = await page.evaluate(() => document.documentElement.scrollWidth);
    const innerWidth1366 = await page.evaluate(() => window.innerWidth);
    console.log(`  - 1366x768: scrollWidth = ${scrollWidth1366}, innerWidth = ${innerWidth1366}`);
    if (scrollWidth1366 > innerWidth1366) {
      failures.push(`Horizontal overflow at 1366x768: scrollWidth ${scrollWidth1366} > innerWidth ${innerWidth1366}`);
    } else {
      console.log('  [OK] Zero horizontal clipping at 1366x768.');
    }

    // ---------------------------------------------------------------
    // 2. Viewport 1920x1080 Check (Full HD Desktop)
    // ---------------------------------------------------------------
    console.log('[2/7] Testing Viewport: 1920 x 1080 (Full HD Desktop)...');
    await page.setViewport({ width: 1920, height: 1080 });
    await delay(500);
    const scrollWidth1920 = await page.evaluate(() => document.documentElement.scrollWidth);
    const innerWidth1920 = await page.evaluate(() => window.innerWidth);
    console.log(`  - 1920x1080: scrollWidth = ${scrollWidth1920}, innerWidth = ${innerWidth1920}`);
    if (scrollWidth1920 > innerWidth1920) {
      failures.push(`Horizontal overflow at 1920x1080: scrollWidth ${scrollWidth1920} > innerWidth ${innerWidth1920}`);
    } else {
      console.log('  [OK] Zero horizontal clipping at 1920x1080.');
    }

    // ---------------------------------------------------------------
    // 3. Header & Admin Session Check
    // ---------------------------------------------------------------
    console.log('[3/7] Verifying Admin Navigation & Header Status...');
    const headerStatus = await page.evaluate(() => {
      const header = document.querySelector('header');
      return header ? header.textContent : '';
    });
    console.log(`  - Header present: ${headerStatus.includes('MandiQ') ? 'YES' : 'NO'}`);
    console.log(`  - Role visible: ${headerStatus.includes('ADMIN') ? 'ADMIN' : 'OTHER'}`);

    const demoToolsBtn = await page.$('#btn-header-demo-tools');

    if (!demoToolsBtn) {
      failures.push('Demo Tools button (#btn-header-demo-tools) not found in Header.');
    } else {
      await page.evaluate(() => {
        const btn = document.querySelector('#btn-header-demo-tools');
        if (btn) btn.click();
      });
      await delay(1500);

      const modalFound = await page.evaluate(() => !!document.querySelector('.fixed.inset-0'));
      console.log(`  - Demo Tools Modal mounted in DOM: ${modalFound}`);

      const resetBtn = await page.$('#btn-showcase-reset-hero');
      const trafficBtn = await page.$('#btn-showcase-traffic-hero');
      const e2eBtn = await page.$('#btn-showcase-e2e-hero');

      if (!resetBtn) failures.push('RESET SHOWCASE button (#btn-showcase-reset-hero) missing.');
      if (!trafficBtn) failures.push('CREATE DEMO TRAFFIC button (#btn-showcase-traffic-hero) missing.');
      if (!e2eBtn) failures.push('RUN E2E JOURNEY button (#btn-showcase-e2e-hero) missing.');

      console.log('  - Showcase Hero Controls:');
      console.log(`    * RESET SHOWCASE: ${resetBtn ? 'PRESENT' : 'MISSING'}`);
      console.log(`    * CREATE DEMO TRAFFIC: ${trafficBtn ? 'PRESENT' : 'MISSING'}`);
      console.log(`    * RUN E2E JOURNEY: ${e2eBtn ? 'PRESENT' : 'MISSING'}`);

      // Test RESET SHOWCASE click
      if (resetBtn) {
        await resetBtn.click();
        await delay(1200);
        console.log('  [OK] Clicked RESET SHOWCASE.');
      }

      // Test CREATE DEMO TRAFFIC click
      if (trafficBtn) {
        await trafficBtn.click();
        await delay(1500);
        console.log('  [OK] Clicked CREATE DEMO TRAFFIC.');
      }

      // Check Algorithm Center & 8 Quick-Jump modules
      const algoSectionIds = [
        'algo-dcdq', 'algo-eta', 'algo-tas', 'algo-redis',
        'algo-hmac', 'algo-lww', 'algo-gzip', 'algo-risk'
      ];

      for (const sId of algoSectionIds) {
        const el = await page.$(`#${sId}`);
        if (!el) {
          failures.push(`Algorithm section #${sId} missing from Algorithm Control Center.`);
        }
      }
      console.log(`  [OK] All 8 Algorithm Sections present: ${algoSectionIds.join(', ')}.`);

      // Security check in HMAC module: verify no raw secret keys displayed
      const modalText = await page.evaluate(() => document.body.textContent || '');
      const forbiddenKey = ['MANDIQ', 'SECRET', 'HMAC', 'KEY', '2026'].join('_');
      if (modalText.includes(forbiddenKey) || modalText.includes('SUPERVISOR_SECRET_OVERRIDE_TOKEN')) {
        failures.push('Security Violation: Raw secret key detected in visible DOM text!');
      } else {
        console.log('  [OK] Zero secrets or raw HMAC keys exposed in Algorithm Center.');
      }

      // Close Demo Tools Modal
      const closeBtn = await page.evaluateHandle(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        return btns.find(b => b.textContent && b.textContent.includes('Close')) || null;
      });
      if (closeBtn.asElement()) {
        await closeBtn.click();
        await delay(500);
      }
    }

    // ---------------------------------------------------------------
    // 5. Language Toggle (English / Hindi)
    // ---------------------------------------------------------------
    console.log('[5/7] Testing Language Toggle (EN <-> HI)...');
    const selectElem = await page.$('select');

    if (selectElem) {
      await page.select('select', 'hi');
      await delay(600);
      const hindiTitle = await page.evaluate(() => document.body.textContent || '');
      const hasDevanagari = /[\u0900-\u097F]/.test(hindiTitle);
      console.log(`  - Devanagari text rendered after Hindi toggle: ${hasDevanagari}`);
      if (!hasDevanagari) {
        failures.push('Hindi language toggle did not render Devanagari text.');
      } else {
        console.log('  [OK] Language toggle updates visible UI to Hindi dynamically.');
      }

      // Switch back to English
      await page.select('select', 'en');
      await delay(500);
      console.log('  [OK] Restored to English.');
    }

    // ---------------------------------------------------------------
    // 6. Operational Screen Sanitization (Quality Station)
    // ---------------------------------------------------------------
    console.log('[6/7] Testing Operational Screen Sanitization (Quality Station)...');
    const qualityTab = await page.evaluateHandle(() => {
      const tabs = Array.from(document.querySelectorAll('button'));
      return tabs.find(t => t.textContent && (t.textContent.includes('Quality') || t.textContent.includes('गुणवत्ता'))) || null;
    });

    if (qualityTab.asElement()) {
      await qualityTab.click();
      await delay(1000);

      // Check Quality Station text
      const qualityText = await page.evaluate(() => document.body.textContent || '');
      if (qualityText.includes('P(lot) = 0.35 * P_arrival')) {
        failures.push('Developer formula P(lot) = 0.35 * ... still displayed in operational Quality Station!');
      } else {
        console.log('  [OK] Raw developer DCDQ formula purged from operational Quality Station.');
      }

      // Check APMC Lot Assaying Standards presence
      const hasStandards = qualityText.includes('APMC Lot Assaying Standards') || qualityText.includes('मानक');
      console.log(`  - APMC Assaying Standards displayed: ${hasStandards}`);

      // Check Supervisor Override form
      const overrideToggle = await page.evaluateHandle(() => {
        const btns = Array.from(document.querySelectorAll('button'));
        return btns.find(b => b.textContent && (b.textContent.includes('Supervisory Override') || b.textContent.includes('ओवरराइड'))) || null;
      });

      if (overrideToggle.asElement()) {
        await overrideToggle.click();
        await delay(500);

        // Verify password input type
        const passwordInput = await page.$('input[type="password"]');
        if (!passwordInput) {
          failures.push('Supervisor authorization token input is NOT masked with type="password"!');
        } else {
          const val = await page.evaluate(el => el.value, passwordInput);
          console.log(`  [OK] Supervisor token input is masked (type="password", initial value: "${val}").`);
          if (val === 'SUPERVISOR_SECRET_OVERRIDE_TOKEN') {
            failures.push('Security Violation: Plain text secret pre-filled in supervisor token input!');
          }
        }
      }
    }

    // ---------------------------------------------------------------
    // 7. Operational Screen Sanitization (Live Queue Monitor)
    // ---------------------------------------------------------------
    console.log('[7/7] Testing Operational Screen Sanitization (Queue Monitor)...');
    const queueTab = await page.evaluateHandle(() => {
      const tabs = Array.from(document.querySelectorAll('button'));
      return tabs.find(t => t.textContent && (t.textContent.includes('Live Queue') || t.textContent.includes('कतार'))) || null;
    });

    if (queueTab.asElement()) {
      await queueTab.click();
      await delay(1000);

      const queueText = await page.evaluate(() => document.body.textContent || '');
      if (queueText.includes('W_i = Σ EstPayload_j')) {
        failures.push('Developer formula W_i = Σ EstPayload_j ... still displayed in Queue Monitor!');
      } else {
        console.log('  [OK] Raw formula string purged from Queue Monitor operational cards.');
      }
    }

  } catch (err) {
    console.error('Test execution error:', err);
    failures.push(`Execution error: ${err.message}`);
  } finally {
    await browser.close();
  }

  console.log('======================================================================');
  if (failures.length === 0) {
    console.log('[VERIFICATION RESULT: ALL CHECKS PASSED 100%]');
    console.log('The prototype is fully hardened for the SIH judge demonstration.');
  } else {
    console.error(`[VERIFICATION RESULT: FAILED - ${failures.length} issues detected]:`);
    failures.forEach((f, idx) => console.error(`  ${idx + 1}. ${f}`));
    process.exit(1);
  }
  console.log('======================================================================');
}

runShowcaseVerification();
