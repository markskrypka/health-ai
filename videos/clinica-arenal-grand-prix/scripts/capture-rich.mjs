import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { join, resolve } from "node:path";

const videoDir = resolve(import.meta.dirname, "..");
const capturesDir = join(videoDir, "capture", "screens");
const assetsDir = join(videoDir, "assets", "ui");
await mkdir(capturesDir, { recursive: true });
await mkdir(assetsDir, { recursive: true });

async function run() {
  console.log("Launching Chromium...");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"]
  });

  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  console.log("Navigating to http://localhost:3100/desk ...");
  await page.goto("http://localhost:3100/desk", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  // Click the 'Past' tab
  const pastTab = page.getByRole("button", { name: /Past/i });
  console.log("Clicking Past tab...");
  await pastTab.click();
  await page.waitForTimeout(1000);

  // Click on a call in the list (Josefa or Lucía)
  const callBtn = page.getByRole("button", { name: /Josefa|Lucía|Teresa|Álvaro/i }).first();
  console.log("Selecting call in list...");
  await callBtn.click();
  await page.waitForTimeout(2000);

  console.log("Capturing 01-desk-overview.png...");
  await page.screenshot({ path: join(capturesDir, "01-desk-overview.png") });
  await page.screenshot({ path: join(assetsDir, "01-desk-overview.png") });

  console.log("Capturing 02-call-detail-cards.png...");
  // Scroll chat down slightly to center action cards
  await page.mouse.wheel(0, 300);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: join(capturesDir, "02-call-detail-cards.png") });
  await page.screenshot({ path: join(assetsDir, "02-call-detail-cards.png") });

  console.log("Capturing 03-booking-decision.png...");
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: join(capturesDir, "03-booking-decision.png") });
  await page.screenshot({ path: join(assetsDir, "03-booking-decision.png") });

  console.log("Capturing 04-pipeline-comparison.png...");
  const compareBtn = page.getByRole("button", { name: /Compare pipelines/i });
  await compareBtn.click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: join(capturesDir, "04-pipeline-comparison.png") });
  await page.screenshot({ path: join(assetsDir, "04-pipeline-comparison.png") });

  // Close modal by clicking the X button in header
  const closeBtn = page.locator("div.fixed header button");
  if (await closeBtn.isVisible()) {
    await closeBtn.click();
  } else {
    await page.keyboard.press("Escape");
  }
  await page.waitForTimeout(1000);

  console.log("Triggering Replay ten at once...");
  const replayTenBtn = page.getByRole("button", { name: /Replay ten at once/i });
  await replayTenBtn.click();
  await page.waitForTimeout(3000);
  console.log("Capturing 05-replay-ten-concurrency.png...");
  await page.screenshot({ path: join(capturesDir, "05-replay-ten-concurrency.png") });
  await page.screenshot({ path: join(assetsDir, "05-replay-ten-concurrency.png") });

  // Open /call
  console.log("Navigating to http://localhost:3100/call ...");
  await page.goto("http://localhost:3100/call", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  console.log("Capturing 06-caller-screen-initial.png...");
  await page.screenshot({ path: join(capturesDir, "06-caller-screen-initial.png") });
  await page.screenshot({ path: join(assetsDir, "06-caller-screen-initial.png") });

  // Pre-fill inputs
  const inputs = page.locator("input");
  const count = await inputs.count();
  if (count >= 2) {
    await inputs.nth(0).fill("Josefa Domínguez Navarro");
    await inputs.nth(1).fill("48064716Y");
  }
  await page.waitForTimeout(1500);
  console.log("Capturing 07-caller-screen-prefilled.png...");
  await page.screenshot({ path: join(capturesDir, "07-caller-screen-prefilled.png") });
  await page.screenshot({ path: join(assetsDir, "07-caller-screen-prefilled.png") });

  await browser.close();
  console.log("All rich screenshots captured successfully!");
}

run().catch((e) => {
  console.error("Error capturing demo screens:", e);
  process.exit(1);
});
