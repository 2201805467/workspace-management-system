import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

const python =
  process.env.TEST_PYTHON ||
  path.resolve(
    import.meta.dirname,
    "../../backend",
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python",
  );
const png = execFileSync(
  python,
  [
    "-c",
    "import sys; from tests.file_samples import image_bytes; sys.stdout.buffer.write(image_bytes())",
  ],
  { cwd: path.resolve(import.meta.dirname, "../../backend") },
);

test("Project files upload, validate, download and enforce employee ownership", async ({
  page,
  browser,
}) => {
  await page.goto("/login");
  await page.getByLabel("البريد الإلكتروني").fill("admin@example.com");
  await page
    .getByLabel("كلمة المرور", { exact: true })
    .fill("BrowserTestOnly!123");
  await page.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await expect(
    page.getByRole("heading", { name: /مرحبًا، مسؤول الاختبار/ }),
  ).toBeVisible();
  const me = await (await page.request.get("/api/auth/me")).json();
  const headers = {
    "X-Requested-With": "WorkSpace",
    Origin: "http://localhost:5174",
  };
  const employee = await (
    await page.request.post("/api/users", {
      headers,
      data: {
        name: "موظف الوثائق",
        email: "files-employee@example.com",
        role: "Employee",
        password: "BrowserFilesOnly!123",
      },
    })
  ).json();
  const project = await (
    await page.request.post("/api/projects", {
      headers,
      data: { name: "وثائق إطلاق الشركة", manager_id: me.id },
    })
  ).json();
  expect(
    (
      await page.request.post(`/api/projects/${project.id}/members`, {
        headers,
        data: { user_id: employee.id },
      })
    ).status(),
  ).toBe(201);
  await page.goto(`/projects/${project.id}`);
  const section = page.locator(".project-files");
  await section.getByRole("button", { name: "+ رفع ملف" }).click();
  await section
    .getByLabel("اختر ملفًا")
    .setInputFiles({
      name: "صورة الفريق.png",
      mimeType: "image/png",
      buffer: png,
    });
  await section.getByRole("button", { name: "رفع الملف", exact: true }).click();
  await expect(section.getByRole("status")).toContainText("تم رفع الملف بنجاح");
  const row = section.getByRole("row").filter({ hasText: "صورة الفريق.png" });
  await expect(row).toBeVisible();
  const downloaded = page.waitForEvent("download");
  await row.getByRole("button", { name: "تنزيل", exact: true }).click();
  const result = await downloaded;
  expect(result.suggestedFilename()).toBe("صورة الفريق.png");
  const downloadedPath = await result.path();
  expect(
    createHash("sha256")
      .update(await readFile(downloadedPath!))
      .digest("hex"),
  ).toBe(createHash("sha256").update(png).digest("hex"));
  await row
    .getByRole("button", { name: "صورة الفريق.png", exact: true })
    .click();
  await expect(
    section.getByRole("heading", { name: "معلومات الملف" }),
  ).toBeVisible();
  await section.getByRole("button", { name: "إغلاق المعلومات" }).click();
  await section
    .getByLabel("اختر ملفًا")
    .setInputFiles({
      name: "script.py",
      mimeType: "text/x-python",
      buffer: Buffer.from("print(1)"),
    });
  await expect(section.getByRole("alert")).toContainText("اختر ملف");
  await expect(
    section.getByRole("button", { name: "رفع الملف", exact: true }),
  ).toBeDisabled();
  await section
    .getByLabel("اختر ملفًا")
    .setInputFiles({
      name: "fake.png",
      mimeType: "image/png",
      buffer: Buffer.from("not a PNG"),
    });
  await section.getByRole("button", { name: "رفع الملف", exact: true }).click();
  await expect(section.getByRole("alert")).toContainText("لا يتطابق");
  await section.getByLabel("نوع الملف", { exact: true }).selectOption("pdf");
  await expect(
    section.getByText("لا توجد نتائج", { exact: true }),
  ).toBeVisible();
  await section.getByLabel("نوع الملف", { exact: true }).selectOption("png");
  await expect(row).toBeVisible();
  await page.screenshot({
    path: "test-results/files-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await section.screenshot({ path: "test-results/files-mobile.png" });

  const context = await browser.newContext({
    baseURL: "http://localhost:5174",
  });
  const user = await context.newPage();
  await user.goto("/login");
  await user.getByLabel("البريد الإلكتروني").fill("files-employee@example.com");
  await user
    .getByLabel("كلمة المرور", { exact: true })
    .fill("BrowserFilesOnly!123");
  await user.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await expect(
    user.getByRole("heading", { name: /مرحبًا، موظف الوثائق/ }),
  ).toBeVisible();
  await user.goto(`/projects/${project.id}`);
  const employeeFiles = user.locator(".project-files");
  await expect(
    employeeFiles.getByRole("row").filter({ hasText: "صورة الفريق.png" }),
  ).toBeVisible();
  await expect(
    employeeFiles.getByRole("button", { name: "حذف الملف", exact: true }),
  ).toHaveCount(0);
  await employeeFiles.getByRole("button", { name: "+ رفع ملف" }).click();
  await employeeFiles
    .getByLabel("اختر ملفًا")
    .setInputFiles({ name: "ملفي.png", mimeType: "image/png", buffer: png });
  await employeeFiles
    .getByRole("button", { name: "رفع الملف", exact: true })
    .click();
  const ownRow = employeeFiles.getByRole("row").filter({ hasText: "ملفي.png" });
  await expect(ownRow).toBeVisible();
  user.once("dialog", (dialog) => dialog.accept());
  await ownRow.getByRole("button", { name: "حذف الملف", exact: true }).click();
  await expect(ownRow).toHaveCount(0);
  await context.close();
  await page.request.delete(`/api/projects/${project.id}`, { headers });
  await page.reload();
  await expect(section.getByRole("button", { name: "+ رفع ملف" })).toHaveCount(
    0,
  );
  await expect(section.getByRole("button", { name: "حذف الملف" })).toHaveCount(
    0,
  );
  await expect(
    section.getByRole("button", { name: "تنزيل", exact: true }),
  ).toBeVisible();
});
