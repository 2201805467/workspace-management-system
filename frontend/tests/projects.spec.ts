import { test, expect } from "@playwright/test";

test("Admin and employee complete the project/task workflow in Arabic", async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login");
  await page.getByLabel("البريد الإلكتروني").fill("admin@example.com");
  await page
    .getByLabel("كلمة المرور", { exact: true })
    .fill("BrowserTestOnly!123");
  await page.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await page.getByRole("button", { name: "إدارة حسابات الفريق ←" }).click();
  for (const [name, email, role] of [
    ["مدير المشاريع", "project-manager@example.com", "Manager"],
    ["عضو المشروع", "project-employee@example.com", "Employee"],
  ]) {
    await page.getByLabel("الاسم الكامل").fill(name);
    await page.getByLabel("البريد الإلكتروني", { exact: true }).fill(email);
    await page.getByLabel("الدور", { exact: true }).selectOption(role);
    await page
      .getByLabel("كلمة المرور الأولية")
      .fill("ProjectBrowserPassword!123");
    await page.getByRole("button", { name: "+ إنشاء الحساب" }).click();
    await expect(
      page.getByRole("cell", { name: new RegExp(name) }),
    ).toBeVisible();
  }
  await page
    .getByRole("button", { name: "المشاريع", exact: false })
    .first()
    .click();
  await page.getByRole("button", { name: "+ مشروع جديد" }).click();
  await page.getByLabel("اسم المشروع").fill("إطلاق موقع الشركة");
  await page
    .getByLabel("مدير المشروع", { exact: true })
    .selectOption({ label: "مدير المشاريع" });
  await page.getByLabel("حالة المشروع").selectOption("Active");
  await page.getByLabel("تاريخ البداية", { exact: true }).fill("2026-01-01");
  await page.getByLabel("تاريخ النهاية المتوقع").fill("2026-12-31");
  await page
    .getByLabel("وصف المشروع")
    .fill("مشروع لاختبار تعاون الفريق ومتابعة المهام.");
  await page
    .getByRole("button", { name: "إنشاء المشروع", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "إطلاق موقع الشركة" }),
  ).toBeVisible();
  await page
    .getByLabel("إضافة عضو", { exact: true })
    .selectOption({ label: "عضو المشروع" });
  await page.getByRole("button", { name: "إضافة للمشروع" }).click();
  await expect(page.locator(".member-list")).toContainText("عضو المشروع");
  await page.getByRole("button", { name: "+ مهمة جديدة" }).click();
  await page.getByLabel("عنوان المهمة").fill("تصميم الصفحة الرئيسية");
  await page
    .getByLabel("الموظف المسؤول")
    .selectOption({ label: "عضو المشروع" });
  await page
    .getByLabel("الأولوية", { exact: true })
    .first()
    .selectOption("high");
  await page.getByLabel("الموعد النهائي", { exact: true }).fill("2020-01-01");
  await page.getByRole("button", { name: "إنشاء المهمة", exact: true }).click();
  const row = page
    .getByRole("row")
    .filter({ hasText: "تصميم الصفحة الرئيسية" });
  await expect(row).toContainText("متأخرة");
  const projectURL = page.url();
  await page.screenshot({
    path: "test-results/project-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/project-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });

  const employeeContext = await browser.newContext({
    baseURL: "http://localhost:5174",
  });
  const employee = await employeeContext.newPage();
  await employee.goto("/login");
  await employee
    .getByLabel("البريد الإلكتروني")
    .fill("project-employee@example.com");
  await employee
    .getByLabel("كلمة المرور", { exact: true })
    .fill("ProjectBrowserPassword!123");
  await employee.getByRole("button", { name: "تسجيل الدخول ←" }).click();
  await employee
    .getByRole("button", { name: "مهامي", exact: false })
    .first()
    .click();
  await expect(
    employee.getByRole("row").filter({ hasText: "تصميم الصفحة الرئيسية" }),
  ).toBeVisible();
  await employee.getByLabel("حالة تصميم الصفحة الرئيسية").selectOption("done");
  await expect(employee.getByRole("status")).toContainText("تم تحديث");
  await employee.getByRole("link", { name: "تصميم الصفحة الرئيسية" }).click();
  await expect(
    employee.getByRole("heading", { name: "تصميم الصفحة الرئيسية" }),
  ).toBeVisible();
  await expect(
    employee.getByRole("button", { name: "تعديل المهمة" }),
  ).toHaveCount(0);
  await expect(
    employee
      .locator(".detail-grid > div")
      .filter({ has: employee.locator("dt", { hasText: "تاريخ الإكمال" }) })
      .locator("dd"),
  ).not.toHaveText("غير محدد");
  await employee.goto(projectURL);
  await expect(
    employee.getByRole("button", { name: "+ مهمة جديدة" }),
  ).toHaveCount(0);
  await employeeContext.close();

  await page.reload();
  await page
    .getByRole("button", { name: "تعديل المشروع", exact: true })
    .click();
  await page.getByLabel("وصف المشروع").fill("وصف المشروع بعد التعديل.");
  await page.getByRole("button", { name: "حفظ المشروع" }).click();
  await expect(page.locator(".description").first()).toContainText(
    "بعد التعديل",
  );
  await page.getByRole("button", { name: "إزالة", exact: true }).last().click();
  await expect(page.getByRole("alert")).toContainText("أعد توزيعها");
  page.once("dialog", (dialog) => dialog.accept());
  await row.getByRole("button", { name: "حذف", exact: true }).click();
  await expect(page.getByText("لا توجد نتائج", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "إزالة", exact: true }).last().click();
  await expect(page.locator(".member-list")).not.toContainText("عضو المشروع");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "أرشفة المشروع" }).click();
  await expect(page.getByText("مؤرشف · للقراءة فقط")).toBeVisible();
  await expect(page.getByRole("button", { name: "+ مهمة جديدة" })).toHaveCount(
    0,
  );
  await page.getByRole("link", { name: "← جميع المشاريع" }).click();
  await page.getByLabel("عرض المشاريع", { exact: true }).selectOption("true");
  await expect(
    page.getByRole("heading", { name: "إطلاق موقع الشركة" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
