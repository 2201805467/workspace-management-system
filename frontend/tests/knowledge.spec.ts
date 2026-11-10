import { test, expect } from "@playwright/test";

test("Knowledge authoring, safe Markdown, dirty navigation and unified PostgreSQL search", async ({
  page,
  browser,
}) => {
  test.skip(
    !process.env.BROWSER_TEST_DATABASE_URL,
    "Requires the dedicated PostgreSQL browser database",
  );
  const headers = {
    "X-Requested-With": "WorkSpace",
    Origin: "http://localhost:5174",
  };
  await page.goto("/login");
  await page.getByLabel("البريد الإلكتروني").fill("admin@example.com");
  await page
    .getByLabel("كلمة المرور", { exact: true })
    .fill("BrowserTestOnly!123");
  await page.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await page
    .getByRole("button", { name: "قاعدة المعرفة", exact: false })
    .click();
  await page.getByRole("link", { name: "إدارة التصنيفات" }).click();
  await page.getByRole("button", { name: "+ تصنيف جديد" }).click();
  await page.getByLabel("اسم التصنيف").fill("إرشادات الموظفين");
  await page.getByLabel("المعرف النصي للتصنيف").fill("employee-guides");
  await page.getByRole("button", { name: "حفظ التصنيف" }).click();
  await expect(
    page.getByRole("cell", { name: "إرشادات الموظفين" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "← قاعدة المعرفة" }).click();
  await page.getByRole("link", { name: "+ مقال جديد" }).click();
  await page.getByLabel("عنوان المقال").fill("دليل إدارة الملفات الداخلية");
  await page.getByLabel("ملخص المقال").fill("إرشادات البحث في ملفات الشركة");
  await page
    .getByLabel("تصنيف المقال", { exact: true })
    .selectOption({ label: "إرشادات الموظفين" });
  await page
    .getByLabel("محتوى المقال بصيغة Markdown")
    .fill(
      '# خطوات العمل\n\n**مرحبًا** بفريق الشركة.\n\n- إدارة الملفات\n- رفع الوثائق\n\n<script>window.__kbInjected = true</script>\n\n[رابط غير آمن](javascript:alert(1))\n\n```python\nprint("safe")\n```',
    );
  await page.getByRole("button", { name: "معاينة Markdown" }).click();
  await expect(page.locator(".markdown-preview strong")).toHaveText("مرحبًا");
  expect(
    await page.evaluate(() =>
      Object.prototype.hasOwnProperty.call(window, "__kbInjected"),
    ),
  ).toBe(false);
  await expect(
    page.locator('.markdown-preview a[href^="javascript:"]'),
  ).toHaveCount(0);
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "الرئيسية", exact: false }).click();
  await expect(page).toHaveURL("/knowledge/new");
  await page.getByRole("button", { name: "حفظ المسودة", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "دليل إدارة الملفات الداخلية" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "نشر المقال", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("تم نشر المقال");
  await page
    .getByRole("button", { name: "البحث الموحد", exact: false })
    .click();
  await page.getByLabel("كلمات البحث").fill("ادارة الملفات");
  await page.getByRole("button", { name: "ابحث في المعرفة والوثائق" }).click();
  await expect(
    page
      .locator(".search-result")
      .filter({ hasText: "دليل إدارة الملفات الداخلية" }),
  ).toBeVisible();
  await expect(page.locator(".search-result mark").first()).toBeVisible();
  await page.screenshot({
    path: "test-results/knowledge-search-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/knowledge-search-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  const employee = await (
    await page.request.post("/api/users", {
      headers,
      data: {
        name: "قارئ المعرفة",
        email: "knowledge-reader@example.com",
        role: "Employee",
        password: "KnowledgeReaderOnly!123",
      },
    })
  ).json();
  const context = await browser.newContext({
    baseURL: "http://localhost:5174",
  });
  const reader = await context.newPage();
  await reader.goto("/login");
  await reader.getByLabel("البريد الإلكتروني").fill(employee.email);
  await reader
    .getByLabel("كلمة المرور", { exact: true })
    .fill("KnowledgeReaderOnly!123");
  await reader.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await reader
    .getByRole("button", { name: "قاعدة المعرفة", exact: false })
    .click();
  await expect(
    reader.getByRole("heading", { name: "دليل إدارة الملفات الداخلية" }),
  ).toBeVisible();
  await expect(reader.getByRole("link", { name: "+ مقال جديد" })).toHaveCount(
    0,
  );
  await reader
    .getByRole("link", { name: "دليل إدارة الملفات الداخلية" })
    .click();
  await expect(reader.getByRole("link", { name: "تعديل المقال" })).toHaveCount(
    0,
  );
  await context.close();
  await page.getByRole("link", { name: "دليل إدارة الملفات الداخلية" }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "أرشفة المقال" }).click();
  await expect(page.getByRole("status")).toContainText("تمت أرشفة");
  await page
    .getByRole("button", { name: "البحث الموحد", exact: false })
    .click();
  await page.getByLabel("كلمات البحث").fill("ادارة الملفات");
  await page.getByRole("button", { name: "ابحث في المعرفة والوثائق" }).click();
  await expect(page.getByText("لا توجد نتائج", { exact: true })).toBeVisible();
});
