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
- `src/components/Brand.tsx`: الهوية المشتركة.
- `src/api.ts`: أنواع المستخدمين وعميل HTTP ومعالجة الأخطاء.
- `tests/auth.spec.ts`: اختبار المتصفح على بيئة منفصلة ومؤقتة.
- `examples/TaskCounter.tsx`: تمرين عدّ المهام السابق محفوظ للتعلّم.

اختبار المتصفح يستخدم Microsoft Edge افتراضيًا، ويتطلب بيئة Python وتبعيات التطوير في `../backend/.venv`. للتفاصيل وإعداد PostgreSQL وحساب المسؤول راجع [تعليمات المشروع](../README.md).
