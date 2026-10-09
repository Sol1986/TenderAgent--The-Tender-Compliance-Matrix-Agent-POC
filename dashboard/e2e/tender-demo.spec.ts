import { expect, test } from "@playwright/test";

test("sample package produces one downloadable Excel matrix", async ({ page, request }) => {
  test.skip(process.env.DEMO_TEST_LIVE_PROVIDER !== "1", "Opt in to real parser and paid model execution.");
  const posts: string[] = [];
  page.on("request", req => { if (req.method() === "POST" && req.url().endsWith("/api/runs")) posts.push(req.url()); });
  await page.goto("/");
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  await expect(page).toHaveURL(/run=/);
  const runId = new URL(page.url()).searchParams.get("run");
  await expect(page.getByRole("button", { name: "Analysis in progress" })).toBeDisabled();
  await expect(page.locator(".timeline-item")).not.toHaveCount(0);
  await expect(page.getByText("While this runs, explain")).toBeVisible();
  await page.reload();
  await expect(page.locator(".run-meta")).toContainText("Run");
  await expect(page.getByRole("button", { name: "Analyze", exact: true })).toBeEnabled({ timeout: 840000 });
  const response = await request.get(`${process.env.DEMO_API_URL || "http://127.0.0.1:8000"}/api/runs/${runId}`);
  expect(response.ok()).toBeTruthy();
  const snapshot = await response.json();
  expect(snapshot.status).toBe("completed");
  const link = page.getByRole("link", { name: "Download Excel matrix" });
  await expect(link).toBeVisible();
  const workbook = await request.get(`${process.env.DEMO_API_URL || "http://127.0.0.1:8000"}${snapshot.output.excel_url}`);
  expect(workbook.ok()).toBeTruthy();
  expect(workbook.headers()["content-type"]).toContain("spreadsheetml.sheet");
  const download = await link.getAttribute("href");
  expect(download).toContain(snapshot.output.excel_url);
  await page.screenshot({ path: "../outputs/dashboard-live-result.png", fullPage: true });
  console.log(JSON.stringify({ run_id: runId, requirements: snapshot.metrics.final_requirements, duration_ms: snapshot.duration_ms, workbook_bytes: (await workbook.body()).length }));
  expect(posts).toHaveLength(1);
});

test("completed run restores and downloads its workbook through the browser", async ({ page }) => {
  const runId = process.env.DEMO_COMPLETED_RUN;
  test.skip(!runId, "Provide a completed run ID; this check never starts an analysis.");
  await page.goto(`/?run=${runId}`);
  const link = page.getByRole("link", { name: "Download Excel matrix" });
  await expect(link).toBeVisible();
  const downloadEvent = page.waitForEvent("download");
  await link.click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe("compliance_matrix.xlsx");
  await download.saveAs("../outputs/dashboard-browser-download.xlsx");
  expect(await download.failure()).toBeNull();
});
