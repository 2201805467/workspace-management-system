"""Local operator recovery. No public reset endpoint or default password."""
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db import get_engine
from .models import AccessSession, Role, User
from .schemas import PasswordReset
from .security import password_hasher


def main():
    with Session(get_engine()) as db:
        admins = db.scalars(select(User).where(User.role == Role.ADMIN, User.is_active.is_(True))
                            .order_by(User.created_at, User.id)).all()
        if not admins:
            print("لا يوجد حساب مسؤول نشط لاستعادة كلمة مروره.")
            return
        for index, admin in enumerate(admins, start=1):
            print(f"{index}. {admin.name} — {admin.email}")
        try:
            while True:
                choice = input("رقم حساب المسؤول (Enter لاختيار الأول): ").strip() or "1"
                if choice.isascii() and choice.isdecimal() and 1 <= int(choice) <= len(admins):
                    admin = admins[int(choice) - 1]
                    break
                print("اختر رقمًا من القائمة.")
            while True:
                password = getpass("كلمة المرور الجديدة (من 12 إلى 128 حرفًا): ")
                if password != getpass("تأكيد كلمة المرور الجديدة: "):
                    print("كلمتا المرور غير متطابقتين. أعد المحاولة.")
                    continue
                try:
                    data = PasswordReset(new_password=password)
                    break
                except ValidationError:
                    # Never print validation inputs: they contain the password.
                    print("كلمة المرور يجب أن تتكون من 12 إلى 128 حرفًا.")
        except (KeyboardInterrupt, EOFError):
            print("\nتم إلغاء إعادة التعيين دون تغيير الحساب.")
            return
        admin.password_hash = password_hasher.hash(data.new_password.get_secret_value())
        db.execute(delete(AccessSession).where(AccessSession.user_id == admin.id))
        db.commit()
        print(f"تم تغيير كلمة مرور {admin.email} وإغلاق جميع جلساته. يمكنك تسجيل الدخول الآن.")


if __name__ == "__main__":
    main()
