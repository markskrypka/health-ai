import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { join, resolve } from "node:path";

const videoDir = resolve(import.meta.dirname, "..");
const capturesDir = join(videoDir, "capture", "screens");
const recordingsDir = join(videoDir, "capture", "recordings");
await mkdir(capturesDir, { recursive: true });
await mkdir(recordingsDir, { recursive: true });

async function run() {
  console.log("Launching Chromium...");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"]
  });

  // Context with video recording
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    recordVideo: {
      dir: recordingsDir,
      size: { width: 1920, height: 1080 }
    }
  });

  const page = await context.newPage();

  console.log("Navigating to http://127.0.0.1:3100/desk ...");
  await page.goto("http://127.0.0.1:3100/desk", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  // Take full desk overview
  await page.screenshot({ path: join(capturesDir, "01-desk-overview.png") });
  console.log("Captured 01-desk-overview.png");

  // Select a past call to show rich card history
  const pastTab = page.locator("button:has-text('Past')").first();
  if (await pastTab.isVisible()) {
    await pastTab.click();
    await page.waitForTimeout(1000);
  }

  // Click on the first call
  const firstCall = page.locator("button:has-text('Lucía')").or(page.locator("button:has-text('Josefa')")).first();
  if (await firstCall.isVisible()) {
    await firstCall.click();
    await page.waitForTimeout(1500);
  }

  await page.screenshot({ path: join(capturesDir, "02-call-detail-cards.png") });
  console.log("Captured 02-call-detail-cards.png");

  // Hover over an action card or scroll down chat
  const chatScroll = page.locator("main");
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(capturesDir, "03-booking-decision.png") });
  console.log("Captured 03-booking-decision.png");

  // Open "Compare pipelines" modal
  const compareBtn = page.locator("button:has-text('Compare pipelines')");
  if (await compareBtn.isVisible()) {
    await compareBtn.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: join(capturesDir, "04-pipeline-comparison.png") });
    console.log("Captured 04-pipeline-comparison.png");
    // Close comparison modal
    await page.keyboard.press("Escape");
    await page.waitForTimeout(1000);
  }

  // Click "Replay ten at once"
  const replayTenBtn = page.locator("button:has-text('Replay ten at once')");
  if (await replayTenBtn.isVisible()) {
    await replayTenBtn.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: join(capturesDir, "05-replay-ten-concurrency.png") });
    console.log("Captured 05-replay-ten-concurrency.png");
  }

  // Navigate to Caller's screen (/call)
  console.log("Navigating to http://127.0.0.1:3100/call ...");
  await page.goto("http://127.0.0.1:3100/call", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(capturesDir, "06-caller-screen-initial.png") });
  console.log("Captured 06-caller-screen-initial.png");

  // Pre-fill Josefa Domínguez Navarro
  const nameInput = page.locator("input[placeholder*='name' i]").or(page.locator("input#name")).first();
  if (await nameInput.isVisible()) {
    await nameInput.fill("Josefa Domínguez Navarro");
  }
  const dniInput = page.locator("input[placeholder*='id' i]").or(page.locator("input[placeholder*='DNI' i]")).first();
  if (await dniInput.isVisible()) {
    await dniInput.fill("48064716Y");
  }
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(capturesDir, "07-caller-screen-prefilled.png") });
  console.log("Captured 07-caller-screen-prefilled.png");

  // Keep recording for a few seconds to get smooth UI motion
  await page.waitForTimeout(2000);

  await page.close();
  await context.close();
  await browser.close();

  console.log("Screen capture and UI recording completed successfully!");
}

run().catch((err) => {
  console.error("Capture failed:", err);
  process.exit(1);
});
