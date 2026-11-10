# WorkSpace Frontend

واجهة عربية RTL باستخدام React وTypeScript وVite وReact Router.

```sh
npm ci
npm run dev
npm run build
npm run test:e2e
```

تتصل الواجهة بمسارات `/api` على نفس المضيف. يمرر Vite الطلبات إلى FastAPI على `127.0.0.1:8000`، ويمكن تغيير وجهته عبر `API_PROXY_TARGET`. يستخدم Docker خادم Nginx مع نفس المسارات.

- `src/App.tsx`: التحقق من الجلسة وحماية المسارات وتخطيط مساحة العمل.
- `src/pages/`: الدخول، الحسابات، وتغيير كلمة المرور.
- `src/pages/Projects.tsx` و`ProjectDetails.tsx`: المشاريع وعضويتها ومهامها.
- `src/pages/MyTasks.tsx` و`TaskDetails.tsx`: المهام الشخصية وتفاصيل المهمة.
- `src/hooks/useResource.ts`: جلب البيانات وحالات التحميل والخطأ وإعادة المحاولة وتجاهل الردود القديمة.
- `src/components/ProjectForm.tsx` و`TaskForm.tsx` و`TaskList.tsx`: نماذج مشتركة وقوائم قابلة للتصفية والتصفح.
- `src/components/Brand.tsx`: الهوية المشتركة.
- `src/api.ts`: أنواع المستخدمين وعميل HTTP ومعالجة الأخطاء.
- `tests/auth.spec.ts`: اختبار المتصفح على بيئة منفصلة ومؤقتة.
- `tests/projects.spec.ts`: اختبار إدارة مشروع وتوزيع مهمة وإكمالها وصلاحيات الموظف والأرشفة والعرض على الهاتف.
- `src/components/ProjectFiles.tsx` و`FileUpload.tsx`: الوثائق والتصفية وتقدم الرفع والتنزيل والحذف.
- `src/files.ts`: أنواع الملفات ورفع multipart باستخدام XMLHttpRequest للتقدم وتنزيل محمي مع حالات الخطأ.
- `tests/files.spec.ts`: اختبار الأسماء العربية والتنزيل المطابق والرفض والتصفية وصلاحية حذف الموظف لملفه.
- `examples/TaskCounter.tsx`: تمرين عدّ المهام السابق محفوظ للتعلّم.

اختبار المتصفح يستخدم Microsoft Edge افتراضيًا، ويتطلب بيئة Python وتبعيات التطوير في `../backend/.venv`. للتفاصيل وإعداد PostgreSQL وحساب المسؤول راجع [تعليمات المشروع](../README.md).
