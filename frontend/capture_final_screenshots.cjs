const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function captureFinalScreenshots() {
  const screenshotsDir = 'F:\\Hacktober\\screenshots\\final';
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  console.log('=== CAPTURING FINAL DEMONSTRATION SCREENSHOTS ===\n');
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
  });

  // Desktop Context (1400x900)
  const desktopContext = await browser.newContext({
    viewport: { width: 1400, height: 900 },
  });
  const desktopPage = await desktopContext.newPage();

  // 1. Archive
  console.log('[1/7] Capturing archive.png...');
  await desktopPage.goto('http://127.0.0.1:5173/archive', { waitUntil: 'networkidle' });
  await desktopPage.waitForSelector('.documents-table tbody tr', { timeout: 10000 });
  // Verify exactly 2 rows
  const docRows = await desktopPage.locator('.documents-table tbody tr').count();
  console.log(`  Archive displays ${docRows} curated documents.`);
  await desktopPage.waitForTimeout(600);
  await desktopPage.screenshot({
    path: path.join(screenshotsDir, 'archive.png'),
    fullPage: true,
  });
  console.log('  [OK] Saved archive.png');

  // 2. Writing Desk
  console.log('[2/7] Capturing writing-desk.png...');
  await desktopPage.goto('http://127.0.0.1:5173/write', { waitUntil: 'networkidle' });
  await desktopPage.waitForSelector('textarea', { timeout: 10000 });
  await desktopPage.fill(
    'textarea',
    'A night watchman discovers that the pendulum clock in the bell tower has stopped swinging, yet continues to chime every quarter hour.'
  );
  // Select Gothic
  await desktopPage.selectOption('select.desk-select, select.form-select, select', 'Gothic').catch(
    async () => {
      await desktopPage.locator('button:has-text("Gothic")').first().click().catch(() => {});
    }
  );
  // Select Medium
  await desktopPage.click('button.radio-card:has-text("Medium")');
  // Select Archive-Grounded
  await desktopPage.click('button:has-text("Archive-Grounded")');
  await desktopPage.waitForTimeout(600);
  await desktopPage.screenshot({
    path: path.join(screenshotsDir, 'writing-desk.png'),
    fullPage: true,
  });
  console.log('  [OK] Saved writing-desk.png');

  // 3. Reading Room
  // Using the Gothic archive-grounded story with continuation leaf: 6d04d71404f04dfa8495ac89711a4143
  // It has 2 narrative segments, divider, choices, and archive citations!
  console.log('[3/7] Capturing reading-room.png...');
  await desktopPage.goto('http://127.0.0.1:5173/read/6d04d71404f04dfa8495ac89711a4143', {
    waitUntil: 'networkidle',
  });
  await desktopPage.waitForSelector('.story-title', { timeout: 10000 });
  await desktopPage.waitForSelector('.branch-choice-card', { timeout: 10000 });
  await desktopPage.waitForSelector('.archive-appendix', { timeout: 10000 });
  // Ensure no spinner
  await desktopPage.waitForSelector('.spinner', { state: 'detached', timeout: 5000 }).catch(() => {});
  await desktopPage.waitForTimeout(600);
  await desktopPage.screenshot({
    path: path.join(screenshotsDir, 'reading-room.png'),
    fullPage: true,
  });
  console.log('  [OK] Saved reading-room.png');

  // 4. Story Shelf
  console.log('[4/7] Capturing story-shelf.png...');
  await desktopPage.goto('http://127.0.0.1:5173/shelf', { waitUntil: 'networkidle' });
  await desktopPage.waitForSelector('.story-card', { timeout: 10000 });
  const shelfCards = await desktopPage.locator('.story-card').count();
  console.log(`  Story Shelf displays ${shelfCards} curated root manuscripts.`);
  await desktopPage.waitForTimeout(600);
  await desktopPage.screenshot({
    path: path.join(screenshotsDir, 'story-shelf.png'),
    fullPage: true,
  });
  console.log('  [OK] Saved story-shelf.png');

  // 5. Settings
  console.log('[5/7] Capturing settings.png...');
  await desktopPage.goto('http://127.0.0.1:5173/settings', { waitUntil: 'networkidle' });
  await desktopPage.waitForSelector('.settings-card', { timeout: 10000 });
  // Ensure telemetry is loaded
  await desktopPage.waitForSelector('.status-pill.online', { timeout: 10000 });
  await desktopPage.waitForTimeout(600);
  await desktopPage.screenshot({
    path: path.join(screenshotsDir, 'settings.png'),
    fullPage: true,
  });
  console.log('  [OK] Saved settings.png');

  await desktopContext.close();

  // Mobile Context (390x844)
  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const mobilePage = await mobileContext.newPage();

  // 6. Mobile Archive
  console.log('[6/7] Capturing mobile-archive.png...');
  await mobilePage.goto('http://127.0.0.1:5173/archive', { waitUntil: 'networkidle' });
  await mobilePage.waitForSelector('.documents-table tbody tr', { timeout: 10000 });
  await mobilePage.waitForTimeout(600);
  await mobilePage.screenshot({
    path: path.join(screenshotsDir, 'mobile-archive.png'),
    fullPage: true,
  });
  console.log('  [OK] Saved mobile-archive.png');

  // 7. Mobile Reading Room
  console.log('[7/7] Capturing mobile-reading-room.png...');
  await mobilePage.goto('http://127.0.0.1:5173/read/6d04d71404f04dfa8495ac89711a4143', {
    waitUntil: 'networkidle',
  });
  await mobilePage.waitForSelector('.story-title', { timeout: 10000 });
  await mobilePage.waitForSelector('.branch-choice-card', { timeout: 10000 });
  await mobilePage.waitForTimeout(600);
  await mobilePage.screenshot({
    path: path.join(screenshotsDir, 'mobile-reading-room.png'),
    fullPage: true,
  });
  console.log('  [OK] Saved mobile-reading-room.png');

  await mobileContext.close();
  await browser.close();

  console.log('\n=================================================');
  console.log('ALL FINAL DEMONSTRATION SCREENSHOTS CAPTURED!');
  console.log('=================================================\n');
}

captureFinalScreenshots().catch((err) => {
  console.error('Failed to capture final screenshots:', err);
  process.exit(1);
});
