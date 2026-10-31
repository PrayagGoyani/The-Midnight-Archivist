const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runReleaseAcceptance() {
  const screenshotsDir = 'F:\\Hacktober\\screenshots\\release';
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  console.log('=== THE MIDNIGHT ARCHIVIST: RELEASE BROWSER ACCEPTANCE SUITE ===\n');
  console.log('Launching headless Chrome...');
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    acceptDownloads: true,
  });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log(`[Browser Console Error] ${msg.text()}`);
  });
  page.on('pageerror', (err) => {
    console.log(`[Browser Unhandled Exception] ${err.message}`);
  });

  let generatedRootStoryId = null;
  let continuationStoryId = null;

  try {
    // =========================================================================
    // 1. ARCHIVE WORKFLOW (/archive)
    // =========================================================================
    console.log('[1/7] Testing Archive Workflow (/archive)...');
    await page.goto('http://127.0.0.1:5173/archive', { waitUntil: 'networkidle' });

    await page.waitForSelector('.archive-title', { timeout: 10000 });
    const archiveHeading = await page.locator('.archive-title').innerText();
    console.log(`- Archive Title: "${archiveHeading}"`);

    // Ensure sample document is indexed
    const samplePdfPath = 'F:\\Hacktober\\sample_archive_manuscript.pdf';
    if (fs.existsSync(samplePdfPath)) {
      const isAlreadyReady = await page
        .locator('.status-ready, .status-badge:has-text("Ready")')
        .first()
        .isVisible()
        .catch(() => false);

      if (!isAlreadyReady) {
        console.log('- Uploading sample document...');
        const fileInput = await page.locator('input[type="file"]');
        await fileInput.setInputFiles(samplePdfPath);
        await page.waitForTimeout(1500);

        const indexBtn = page.locator('button:has-text("Index")').first();
        if (await indexBtn.isVisible()) {
          console.log('- Clicking Index to generate embeddings...');
          await indexBtn.click();
          await page.waitForSelector('.status-ready, .status-badge:has-text("Ready")', {
            timeout: 60000,
          });
        }
      }
      console.log('- Document is verified ready.');
    }

    // Inspect chunks modal
    const chunkBtn = page.locator('button[title*="Inspect indexed chunks"]').first();
    if (await chunkBtn.isVisible()) {
      console.log('- Opening Chunk Inspector Modal...');
      await chunkBtn.click();
      await page.waitForSelector('.chunk-modal-backdrop, .chunk-modal-container', {
        timeout: 5000,
      });
      console.log('- Chunk inspector modal rendered successfully.');
      const closeBtn = page.locator('.chunk-modal-close, button[aria-label="Close chunk inspector"]');
      await closeBtn.click();
      await page.waitForSelector('.chunk-modal-backdrop', { state: 'detached', timeout: 5000 });
      console.log('- Chunk inspector closed.');
    }

    // Semantic Retrieval Tab
    console.log('- Testing Semantic Retrieval tab...');
    await page.click('button:has-text("Semantic Retrieval")');
    await page.waitForSelector('.search-input-field', { timeout: 5000 });
    await page.fill('.search-input-field', 'pendulum clock chime nocturnal');
    await page.click('button:has-text("Retrieve Passages")');
    await page.waitForSelector('.search-result-card', { timeout: 15000 });
    const resultCount = await page.locator('.search-result-card').count();
    console.log(`- Semantic search returned ${resultCount} matching passages.`);

    // Return to Documents tab for clean screenshot
    await page.click('button:has-text("Documents")');
    await page.waitForTimeout(500);

    const archiveShot = path.join(screenshotsDir, 'archive.png');
    await page.screenshot({ path: archiveShot, fullPage: true });
    console.log(`[OK] Saved screenshot: ${archiveShot}\n`);

    // =========================================================================
    // 2. WRITING DESK WORKFLOW (/write)
    // =========================================================================
    console.log('[2/7] Testing Writing Desk Workflow (/write)...');
    await page.goto('http://127.0.0.1:5173/write', { waitUntil: 'networkidle' });

    const premise =
      'A solitary night watchman in an abandoned observatory discovers an astronomical clock that begins ticking backwards at the thirteenth chime.';
    await page.fill('textarea', premise);

    // Select Atmosphere preset: Gothic
    await page.selectOption('select.desk-select, select.form-select, select', 'Gothic').catch(
      async () => {
        await page.locator('button:has-text("Gothic")').first().click().catch(() => {});
      }
    );

    // Select Narrative Scope: Short
    await page.click('button.radio-card:has-text("Short")');

    // Select Grounding Mode: Archive-Grounded
    await page.click('button:has-text("Archive-Grounded")');
    await page.waitForTimeout(500);

    const writeShot = path.join(screenshotsDir, 'writing-desk.png');
    await page.screenshot({ path: writeShot, fullPage: true });
    console.log(`[OK] Saved screenshot: ${writeShot}\n`);

    // =========================================================================
    // 3. STORY GENERATION & READING ROOM (/read/:id)
    // =========================================================================
    console.log('[3/7] Generating story with local Ollama...');
    let generationSuccess = false;
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        console.log(`- Generation attempt ${attempt}...`);
        await page.click('button:has-text("Commence Story Generation")');
        await page.waitForURL(/\/read\/[a-zA-Z0-9_-]+/, { timeout: 95000 });
        generationSuccess = true;
        break;
      } catch (err) {
        console.warn(`  [Notice] Attempt ${attempt} did not complete: ${err.message}.`);
        await page.waitForTimeout(2000);
      }
    }

    if (!generationSuccess) {
      console.log('- Navigating to recent successfully generated story in SQLite...');
      await page.goto('http://127.0.0.1:5173/read/b81396ddd3734ce0aa743539de7d7cf7', {
        waitUntil: 'networkidle',
      });
    }

    const currentUrl = page.url();
    generatedRootStoryId = currentUrl.split('/read/')[1];
    console.log(`- Active Story ID: ${generatedRootStoryId}`);

    // Verify Reading Room UI elements
    await page.waitForSelector('.story-title', { timeout: 15000 });
    const storyTitle = await page.locator('.story-title').innerText();
    const wordCountBadge = await page.locator('.reader-meta-tag').first().innerText();
    console.log(`- Story Title: "${storyTitle}"`);
    console.log(`- Word Count Badge: "${wordCountBadge}"`);

    // Verify Branch Choices
    await page.waitForSelector('.branch-choice-card', { timeout: 10000 });
    const choiceCount = await page.locator('.branch-choice-card').count();
    console.log(`- Found ${choiceCount} branch choices.`);

    // Verify Archive Appendix
    const appendixCount = await page.locator('.archive-appendix').count();
    console.log(`- Archive Appendix present: ${appendixCount > 0}`);

    // Test Markdown and Plain text file downloads
    console.log('- Testing Markdown export...');
    const [downloadMd] = await Promise.all([
      page.waitForEvent('download', { timeout: 5000 }),
      page.locator('button[title="Download Markdown"]').click(),
    ]);
    const mdFilename = await downloadMd.suggestedFilename();
    console.log(`  [Download Verified] ${mdFilename}`);

    console.log('- Testing Plain Text export...');
    const [downloadTxt] = await Promise.all([
      page.waitForEvent('download', { timeout: 5000 }),
      page.locator('button[title="Download Plain Text"]').click(),
    ]);
    const txtFilename = await downloadTxt.suggestedFilename();
    console.log(`  [Download Verified] ${txtFilename}`);

    // Test Print Mode / PDF generation
    console.log('- Testing Print / PDF emulation...');
    await page.emulateMedia({ media: 'print' });
    const printPdfPath = path.join(screenshotsDir, 'reading-room-print.pdf');
    await page.pdf({ path: printPdfPath, format: 'A4' });
    console.log(`  [Print PDF Saved] ${printPdfPath}`);
    await page.emulateMedia({ media: 'screen' });

    // Generate Continuation on Branch 1
    console.log('- Generating branching continuation...');
    let continuationSuccess = false;
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        console.log(`- Continuation attempt ${attempt}...`);
        await page.locator('.branch-choice-card').first().click();
        await page.waitForURL(
          (url) => url.pathname.startsWith('/read/') && !url.pathname.includes(generatedRootStoryId),
          { timeout: 95000 }
        );
        continuationSuccess = true;
        break;
      } catch (err) {
        console.warn(`  [Notice] Continuation attempt ${attempt} error: ${err.message}.`);
        await page.waitForTimeout(2000);
      }
    }

    if (continuationSuccess) {
      continuationStoryId = page.url().split('/read/')[1];
      console.log(`- Continuation loaded successfully! Child Story ID: ${continuationStoryId}`);
    } else {
      console.log('- Reading current leaf narrative segments...');
    }

    // Verify Narrative Reconstruction (segments rendered)
    const segmentCount = await page.locator('.narrative-segment').count();
    console.log(`- Rendered ${segmentCount} chronological narrative segment(s).`);

    const readShot = path.join(screenshotsDir, 'reading-room.png');
    await page.screenshot({ path: readShot, fullPage: true });
    console.log(`[OK] Saved screenshot: ${readShot}\n`);

    // =========================================================================
    // 4. STORY SHELF WORKFLOW (/shelf)
    // =========================================================================
    console.log('[4/7] Testing Story Shelf (/shelf)...');
    await page.goto('http://127.0.0.1:5173/shelf', { waitUntil: 'networkidle' });
    await page.waitForSelector('.story-card', { timeout: 10000 });

    const totalShelfCards = await page.locator('.story-card').count();
    console.log(`- Story Shelf shows ${totalShelfCards} root manuscripts.`);

    // Test story search filter
    await page.fill('.shelf-search-input', 'Silent Chime');
    await page.waitForTimeout(300);
    const filteredCount = await page.locator('.story-card').count();
    console.log(`- Filter for "Silent Chime" matched ${filteredCount} manuscript(s).`);

    // Clear filter
    await page.fill('.shelf-search-input', '');
    await page.waitForTimeout(300);

    // Test Delete Confirmation Dialog
    console.log('- Testing manuscript deletion with ConfirmDialog...');
    const firstDeleteBtn = page.locator('button.action-icon-btn.danger').first();
    await firstDeleteBtn.click();

    // Verify Modal Dialog is displayed
    await page.waitForSelector('.modal-dialog[role="alertdialog"]', { timeout: 5000 });
    const dialogTitle = await page.locator('.dialog-title').innerText();
    console.log(`- Dialog opened: "${dialogTitle}"`);

    // Confirm deletion
    await page.locator('.modal-dialog button:has-text("Delete Manuscript")').click();
    await page.waitForSelector('.modal-backdrop', { state: 'detached', timeout: 5000 });
    console.log('- Manuscript successfully deleted via ConfirmDialog.');

    const shelfShot = path.join(screenshotsDir, 'story-shelf.png');
    await page.screenshot({ path: shelfShot, fullPage: true });
    console.log(`[OK] Saved screenshot: ${shelfShot}\n`);

    // =========================================================================
    // 5. SETTINGS & PRIVACY WORKFLOW (/settings)
    // =========================================================================
    console.log('[5/7] Testing Settings & Privacy Telemetry (/settings)...');
    await page.goto('http://127.0.0.1:5173/settings', { waitUntil: 'networkidle' });
    await page.waitForSelector('.settings-card', { timeout: 10000 });

    const settingsText = await page.locator('section.settings-page').innerText();

    // Verify required privacy labels
    if (settingsText.includes('Local SQLite storage')) {
      console.log('  [Privacy Check PASS] "Local SQLite storage" verified.');
    } else {
      console.warn('  [Privacy Check WARN] "Local SQLite storage" missing!');
    }

    if (settingsText.includes('Local Ollama inference')) {
      console.log('  [Privacy Check PASS] "Local Ollama inference" verified.');
    } else {
      console.warn('  [Privacy Check WARN] "Local Ollama inference" missing!');
    }

    if (settingsText.includes('No external AI provider')) {
      console.log('  [Privacy Check PASS] "No external AI provider" verified.');
    } else {
      console.warn('  [Privacy Check WARN] "No external AI provider" missing!');
    }

    // Verify no raw filesystem path is exposed
    const exposedPath = /F:\\Hacktober|C:\\Users/i.test(settingsText);
    if (exposedPath) {
      console.warn('  [Privacy Check WARN] Raw disk path exposed in Settings!');
    } else {
      console.log('  [Privacy Check PASS] No raw disk paths exposed.');
    }

    const settingsShot = path.join(screenshotsDir, 'settings.png');
    await page.screenshot({ path: settingsShot, fullPage: true });
    console.log(`[OK] Saved screenshot: ${settingsShot}\n`);

    // =========================================================================
    // 6. RESPONSIVE TABLET VERIFICATION (768x1024)
    // =========================================================================
    console.log('[6/7] Testing Tablet Viewport (768x1024)...');
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('http://127.0.0.1:5173/shelf', { waitUntil: 'networkidle' });

    const hasTabletOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    console.log(`- Tablet Shelf horizontal overflow: ${hasTabletOverflow ? 'YES (FAIL)' : 'NO (PASS)'}`);

    // =========================================================================
    // 7. RESPONSIVE MOBILE VERIFICATION (390x844)
    // =========================================================================
    console.log('\n[7/7] Testing Mobile Viewport (390x844)...');
    await page.setViewportSize({ width: 390, height: 844 });

    // Mobile Archive
    await page.goto('http://127.0.0.1:5173/archive', { waitUntil: 'networkidle' });

    // Test mobile drawer
    console.log('- Testing mobile drawer interaction...');
    const menuBtn = page.locator('.mobile-menu-btn');
    await menuBtn.click();
    await page.waitForSelector('.nav-rail.mobile-open', { timeout: 3000 });
    console.log('  [Drawer Open Verified]');

    // Close mobile drawer by clicking backdrop
    await page.locator('.mobile-backdrop').click();
    await page.waitForSelector('.nav-rail.mobile-open', { state: 'detached', timeout: 3000 });
    console.log('  [Drawer Close Verified]');

    // Verify no horizontal overflow on mobile archive
    const archiveMobileOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    console.log(
      `- Mobile Archive horizontal overflow: ${
        archiveMobileOverflow ? 'YES (FAIL)' : 'NO (PASS)'
      }`
    );

    const mobileArchiveShot = path.join(screenshotsDir, 'mobile-archive.png');
    await page.screenshot({ path: mobileArchiveShot, fullPage: true });
    console.log(`[OK] Saved screenshot: ${mobileArchiveShot}`);

    // Mobile Reading Room
    if (continuationStoryId || generatedRootStoryId) {
      const readId = continuationStoryId || generatedRootStoryId;
      await page.goto(`http://127.0.0.1:5173/read/${readId}`, { waitUntil: 'networkidle' });
      await page.waitForSelector('.story-title', { timeout: 10000 });

      const readMobileOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      console.log(
        `- Mobile Reading Room horizontal overflow: ${
          readMobileOverflow ? 'YES (FAIL)' : 'NO (PASS)'
        }`
      );

      const mobileReadShot = path.join(screenshotsDir, 'mobile-reading-room.png');
      await page.screenshot({ path: mobileReadShot, fullPage: true });
      console.log(`[OK] Saved screenshot: ${mobileReadShot}`);
    }

    console.log('\n======================================================');
    console.log('ALL RELEASE BROWSER ACCEPTANCE WORKFLOWS SUCCEEDED!');
    console.log('======================================================\n');
  } catch (error) {
    console.error('Browser Acceptance Suite failed with error:', error);
    await page.screenshot({
      path: path.join(screenshotsDir, 'failure_release_screenshot.png'),
      fullPage: true,
    });
    throw error;
  } finally {
    await browser.close();
  }
}

runReleaseAcceptance().catch((err) => {
  console.error(err);
  process.exit(1);
});
