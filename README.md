# WorkSpace

نظام داخلي لشركة واحدة. المرحلة الأولى: React + TypeScript + FastAPI + PostgreSQL، مع تسجيل الدخول وإدارة الحسابات وواجهة عربية RTL.

## تشغيل محلي باستخدام Docker

المتطلبات: Docker Desktop يعمل بوضع Linux containers مع Docker Compose.

1. انسخ ملف الإعدادات، ثم استبدل كلمة مرور قاعدة البيانات بقيمة عشوائية من الحروف والأرقام:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

2. من المجلد الرئيسي:

   ```powershell
   docker compose up --build -d
   docker compose exec backend python -m app.bootstrap
   ```

   الأمر الثاني ينشئ أول مسؤول بطريقة تفاعلية. استخدم بريدًا صحيحًا وكلمة مرور من 12 حرفًا على الأقل. لا توجد حسابات أو كلمات مرور افتراضية. لن يسمح الأمر بإنشاء مسؤول أول جديد إذا كان مسؤول موجودًا بالفعل.

3. افتح http://localhost:8080 وسجّل الدخول. يمكن للمسؤول إنشاء حسابات Admin وManager وEmployee من «حسابات الفريق».

توثيق API: http://localhost:8000/docs — فحص الاتصال بقاعدة البيانات: http://localhost:8000/api/health.

```powershell
docker compose logs -f backend
docker compose down
docker compose up -d
```

تبقى البيانات محفوظة في Volume اسمه `workspace_postgres_data` عند الإيقاف وإعادة التشغيل. لا تستخدم `down -v` على بيانات تحتاجها. تعديل كلمة مرور PostgreSQL في `.env` بعد تهيئة Volume لا يغيّر كلمة مرور المستخدم الموجود داخل قاعدة البيانات.

## التطوير خارج الحاويات

يمكن تشغيل PostgreSQL وحده عبر `docker compose up -d db` ثم تشغيل الخلفية والواجهة محليًا للاستفادة من التحديث الفوري.

الخلفية (Python 3.13 أو أحدث، من مجلد `backend`):

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
$env:DATABASE_URL = 'postgresql+psycopg://workspace:YOUR_DB_PASSWORD@localhost:5433/workspace'
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m app.bootstrap
.venv/Scripts/python -m uvicorn app.main:app --reload
```

الواجهة (Node.js 24، في نافذة ثانية ومن مجلد `frontend`):

```powershell
npm ci
npm run dev
```

افتح http://localhost:5173. يمرّر Vite طلبات `/api` إلى FastAPI على المنفذ 8000؛ تستخدم نسخة Docker Nginx لنفس الغرض. لا حاجة إلى تخزين الرموز في JavaScript أو تفعيل CORS.

## السلوك والصلاحيات في المرحلة الأولى

- لا يوجد تسجيل عام. Admin فقط يستطيع إنشاء الحسابات وعرض قائمة الفريق وتعطيل الحسابات وإعادة تعيين كلمات المرور.
- يستطيع كل مستخدم عرض حسابه وتغيير كلمة مروره وتسجيل الخروج.
- يمنع النظام تعطيل المسؤول لحسابه الحالي.
- كلمات المرور مجزأة باستخدام Argon2. الردود لا تحتوي على كلمات المرور أو بصماتها.
- Access Token عشوائي محفوظ في Cookie بـ`HttpOnly` و`SameSite=Strict`، وتُخزّن بصمته SHA-256 في قاعدة البيانات. مدة الجلسة 8 ساعات ثابتة، دون Refresh Token في هذه المرحلة.
- تسجيل الخروج يبطل الجلسة الحالية في الخادم. تغيير كلمة المرور أو إعادة تعيينها أو تعطيل الحساب يبطل جميع جلسات المستخدم، ولا تعيد إعادة التفعيل صلاحية الرموز القديمة.
- تُحمى طلبات التعديل بترويسة `X-Requested-With: WorkSpace` والتحقق من Origin. لا تُقبل طلبات مواقع أخرى، ولا يُفعّل CORS.
- تسجيل الدخول محدود بعشر محاولات في الدقيقة لكل بريد ومصدر اتصال. المحدِّد في ذاكرة عملية واحدة ومناسب للتدريب المحلي؛ يلزم محدِّد مشترك قبل تشغيل عدة Workers على الإنترنت.
- إنشاء المشاريع والمهام والملفات والمقالات والتقارير يأتي في المراحل التالية. الصفحة الرئيسية الحالية تعرض الحساب فقط، دون إحصائيات وهمية.

عند تجربة POST/PATCH من Swagger أضف قيمة `WorkSpace` في حقل `x-requested-with`. استخدم `localhost` في جميع العناوين، ولا تخلط بينه وبين `127.0.0.1` لأن Cookies تتبع اسم المضيف.

## الاختبارات

من `backend` بعد تثبيت `requirements-dev.txt`:

```powershell
.venv/Scripts/python -m pytest -q
```

تستخدم الاختبارات SQLite في الذاكرة افتراضيًا. لتشغيل نفس اختبارات المصادقة على PostgreSQL، اضبط `TEST_DATABASE_URL` إلى **قاعدة اختبار مستقلة وفارغة**؛ الاختبارات تنشئ الجداول ثم تحذفها. لا تستخدم قاعدة التطبيق لهذا المتغير.

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://workspace:YOUR_DB_PASSWORD@localhost:5433/workspace_test'
.venv/Scripts/python -m pytest -q
```

فحص الواجهة: `npm run build` من `frontend`. اختبار المتصفح: `npm run test:e2e` (يتطلب Microsoft Edge، أو اضبط `PLAYWRIGHT_CHANNEL=chromium` بعد تثبيت Chromium باستخدام Playwright). ينشئ الاختبار خادم FastAPI وقاعدة SQLite مؤقتة مع حساب اختبار، ويغلقهما بعد الانتهاء؛ لا يستخدم قاعدة التطبيق. يشمل الدخول، إنشاء موظف، استمرار الجلسة بعد تحديث الصفحة، رفض صلاحيات الموظف، تعطيله والخروج، ولقطات سطح المكتب والهاتف.

ترحيلات المخطط تُدار باستخدام Alembic؛ تُشغّل خدمة `migrate` الترحيلات قبل بدء API في Docker. إصدارات Python المقيدة موجودة في `backend/requirements-lock.txt`، ونسخ تبعيات الواجهة مثبتة عبر `package-lock.json`.

## بنية المشروع

يمكن فحص الخدمات معًا بعد تشغيلها باستخدام `python -m tests.check_docker_stack` من مجلد `backend` مع ضبط `DATABASE_URL` المحلي. ينشئ الفحص حسابين مؤقتين ويحذفهما بعد انتهائه، ويختبر المرور عبر Nginx إلى FastAPI وPostgreSQL.

فحص `npm audit --omit=dev` لتبعيات التشغيل لم يُظهر ثغرات عند التحقق. أظهر الفحص الكامل عشرة تنبيهات متوسطة في سلسلة أدوات التطوير المرتبطة بـ`minimatch`؛ لم نُجرِ تخفيضًا قسريًا لإصدارات ESLint لمعالجتها.

```text
backend/app/           إعدادات، نماذج، مخططات البيانات، مصادقة ومسارات API
backend/migrations/    ترحيلات Alembic
backend/tests/         اختبارات المصادقة والصلاحيات والجلسات
frontend/src/          واجهة React وعميل API المكتوب بـTypeScript
frontend/examples/     نسخة محفوظة من تمرين عدّ المهام السابق
compose.yaml          PostgreSQL + migrations + FastAPI + React/Nginx
```

التشغيل الحالي محلي، والمنافذ مربوطة بـ127.0.0.1. منفذ PostgreSQL على الجهاز هو 5433 ويمكن تغييره باستخدام `POSTGRES_PORT`، بينما يبقى 5432 داخل شبكة Docker. قبل النشر الخارجي: إعداد HTTPS، وضبط `COOKIE_SECURE=true` و`ALLOWED_ORIGINS` على عنوان الموقع الفعلي، ومراجعة إعدادات التشغيل. الإعداد الافتراضي `COOKIE_SECURE=false` مخصص لـHTTP المحلي.
