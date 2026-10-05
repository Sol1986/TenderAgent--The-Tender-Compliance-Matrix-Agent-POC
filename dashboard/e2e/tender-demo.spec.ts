import { expect, test } from "@playwright/test";

test("sample package produces one downloadable Excel matrix", async ({ page, request }) => {
  test.skip(process.env.DEMO_TEST_LIVE_PROVIDER !== "1", "Opt in to real parser and paid model execution.");
  const posts: string[] = [];
  page.on("request", req => { if (req.method() === "POST" && req.url().endsWith("/api/runs")) posts.push(req.url()); });
  await page.goto("/");
  await page.getByRole("button", { name: "Generate compliance matrix", exact: true }).click();
  await expect(page).toHaveURL(/run=/);
  const runId = new URL(page.url()).searchParams.get("run");
  await expect(page.getByRole("button", { name: "Analysis in progress" })).toBeDisabled();
  await expect(page.locator(".timeline-item")).not.toHaveCount(0);
  await expect(page.getByText("While this runs, explain")).toBeVisible();
  await page.reload();
  await expect(page.locator(".run-meta")).toContainText("Run");
  await expect(page.getByRole("button", { name: "Analyze again" })).toBeEnabled({ timeout: 540000 });
  const response = await request.get(`${process.env.DEMO_API_URL || "http://127.0.0.1:8000"}/api/runs/${runId}`);
  expect(response.ok()).toBeTruthy();
  const snapshot = await response.json();
  expect(snapshot.status).toBe("completed");
  const link = page.getByRole("link", { name: "Download Excel matrix" });
  await expect(link).toBeVisible();
  const workbook = await request.get(`${process.env.DEMO_API_URL || "http://127.0.0.1:8000"}${snapshot.output.excel_url}`);
  expect(workbook.ok()).toBeTruthy();
  expect(workbook.headers()["content-type"]).toContain("spreadsheetml.sheet");
  expect(posts).toHaveLength(1);
});
