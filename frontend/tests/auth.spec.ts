import { test, expect } from "@playwright/test";

test("Arabic login, account creation, session restore, RBAC and logout", async ({
  page,
  browser,
}) => {
  await page.goto("/users");
  await expect(page).toHaveURL("/login");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByLabel("البريد الإلكتروني").fill("admin@example.com");
  await page.getByLabel("كلمة المرور", { exact: true }).fill("incorrect");
  await page.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await expect(page.getByRole("alert")).toContainText("غير صحيحة");
  await page
    .getByLabel("كلمة المرور", { exact: true })
    .fill("BrowserTestOnly!123");
  await page.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await expect(
    page.getByRole("heading", { name: /مرحبًا، مسؤول الاختبار/ }),
  ).toBeVisible();
  await page.getByRole("button", { name: "إدارة حسابات الفريق ←" }).click();
  await page.getByLabel("الاسم الكامل").fill("موظف الاختبار");
  await page
    .getByLabel("البريد الإلكتروني", { exact: true })
    .fill("employee@example.com");
  await page.getByLabel("كلمة المرور الأولية").fill("EmployeeTestOnly!123");
  await page.getByRole("button", { name: "+ إنشاء الحساب" }).click();
  await expect(page.getByRole("cell", { name: /موظف الاختبار/ })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "حسابات الفريق" }),
  ).toBeVisible();

  const employeeContext = await browser.newContext({
    baseURL: "http://localhost:5174",
  });
  const employee = await employeeContext.newPage();
  await employee.goto("/login");
  await employee.getByLabel("البريد الإلكتروني").fill("employee@example.com");
  await employee
    .getByLabel("كلمة المرور", { exact: true })
    .fill("EmployeeTestOnly!123");
  await employee.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await expect(
    employee.getByRole("heading", { name: /مرحبًا، موظف الاختبار/ }),
  ).toBeVisible();
  await employee.goto("/users");
  await expect(employee).toHaveURL("/");
  const denied = await employee.request.get("/api/users");
  expect(denied.status()).toBe(403);

  await page
    .getByRole("row")
    .filter({ hasText: "employee@example.com" })
    .getByRole("button", { name: "تعطيل", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("تعطيل");
  await employee.reload();
  await expect(employee).toHaveURL("/login");
  await employeeContext.close();

  await page.getByRole("button", { name: "تسجيل الخروج ↗" }).click();
  await expect(page).toHaveURL("/login");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "مرحبًا بعودتك." }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/login-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "تسجيل الدخول ←" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/login-mobile.png",
    fullPage: true,
  });
});
