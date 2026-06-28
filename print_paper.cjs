const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const htmlPath = process.argv[2];
  const pdfPath = process.argv[3];

  if (!htmlPath || !pdfPath) {
    console.error("Usage: node print_paper.cjs <htmlPath> <pdfPath>");
    process.exit(1);
  }

  const absoluteHtmlPath = path.resolve(htmlPath);
  const absolutePdfPath = path.resolve(pdfPath);

  console.log(`Printing HTML to PDF...\nSource: ${absoluteHtmlPath}\nOutput: ${absolutePdfPath}`);

  const browser = await puppeteer.launch({
    headless: 'shell',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-web-security',
      '--disable-gpu'
    ]
  });

  const page = await browser.newPage();
  
  // Set viewport to A4 aspect ratio representation
  await page.setViewport({ width: 1200, height: 1600 });

  try {
    await page.goto('file://' + absoluteHtmlPath, { waitUntil: 'domcontentloaded', timeout: 5000 });
  } catch (e) {
    console.log("Navigation timeout or warning, proceeding to print PDF anyway:", e.message);
  }

  // Wait for web fonts to load (with a 2-second timeout fallback)
  try {
    await Promise.race([
      page.evaluate(() => document.fonts.ready),
      new Promise(resolve => setTimeout(resolve, 2000))
    ]);
  } catch (e) {
    console.log("Web fonts ready check skipped/timed out:", e.message);
  }

  // Give a small buffer for page layout stabilization
  await page.evaluate(() => new Promise(r => setTimeout(r, 500)));

  await page.pdf({
    path: absolutePdfPath,
    format: 'A4',
    margin: {
      top: '15mm',
      right: '15mm',
      bottom: '15mm',
      left: '15mm'
    },
    printBackground: true
  });

  await browser.close();
  console.log(`✓ PDF printed successfully.`);
})();
