import fs from "node:fs";
import { expect, test } from "@playwright/test";

const url = process.env.ARKANOID_URL ?? "http://127.0.0.1:4173/";
const screenshotPath = process.env.ARKANOID_SCREENSHOT;
const resultPath = process.env.ARKANOID_BROWSER_RESULT;
const executablePath = process.env.CHROME_BIN;

if (!executablePath) {
  throw new Error("CHROME_BIN is required");
}

if (!screenshotPath || !resultPath) {
  throw new Error("ARKANOID_SCREENSHOT and ARKANOID_BROWSER_RESULT are required");
}

test.use({
  browserName: "chromium",
  launchOptions: {
    executablePath,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  },
});

test("renders a working Arkanoid page", async ({ page }) => {
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto(url, { waitUntil: "networkidle" });

  const canvas = page.locator("canvas").first();
  await expect(canvas).toBeVisible();

  const startControl = page
    .getByRole("button", { name: /start|restart|play/i })
    .or(page.locator('input[type="button"], input[type="submit"]').filter({ hasText: /start|restart|play/i }))
    .first();
  await expect(startControl).toBeVisible();
  await startControl.click();
  await page.waitForTimeout(500);

  const bodyText = await page.locator("body").innerText();
  expect(bodyText).toMatch(/score/i);
  expect(bodyText).toMatch(/lives?/i);

  const canvasState = await canvas.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const context = element.getContext("2d");
    let paintedPixels = 0;
    if (context && element.width > 0 && element.height > 0) {
      const data = context.getImageData(0, 0, element.width, element.height).data;
      const stride = Math.max(4, Math.floor(data.length / 20000 / 4) * 4);
      for (let index = 3; index < data.length; index += stride) {
        if (data[index] !== 0) paintedPixels += 1;
      }
    }
    return {
      width: element.width,
      height: element.height,
      renderedWidth: rect.width,
      renderedHeight: rect.height,
      has2dContext: Boolean(context),
      paintedPixels,
    };
  });

  expect(canvasState.width).toBeGreaterThan(0);
  expect(canvasState.height).toBeGreaterThan(0);
  expect(canvasState.renderedWidth).toBeGreaterThan(0);
  expect(canvasState.renderedHeight).toBeGreaterThan(0);
  expect(canvasState.has2dContext).toBe(true);
  expect(canvasState.paintedPixels).toBeGreaterThan(0);
  expect(pageErrors).toEqual([]);

  await page.screenshot({ path: screenshotPath, fullPage: true });
  fs.writeFileSync(
    resultPath,
    `${JSON.stringify({ url, canvasState, pageErrors }, null, 2)}\n`,
  );
});
