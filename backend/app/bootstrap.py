"""Create the first administrator interactively; never ship a default account."""
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_engine
from .models import Role, User
from .schemas import UserCreate
from .security import password_hasher


def prompt_admin_data():
    while True:
        name = input("اسم المسؤول: ")
        email = input("البريد الإلكتروني: ")
        password = getpass("كلمة المرور (من 12 إلى 128 حرفًا): ")
        if password != getpass("تأكيد كلمة المرور: "):
            print("كلمتا المرور غير متطابقتين. أعد المحاولة.")
            continue
        try:
            return UserCreate(name=name, email=email, password=password, role=Role.ADMIN)
        except ValidationError as error:
            # Never print ValidationError itself: it may contain the raw password.
            messages = {
                "name": "الاسم يجب أن يتكون من حرفين إلى 100 حرف.",
                "email": "أدخل بريدًا إلكترونيًا صحيحًا.",
                "password": "كلمة المرور يجب أن تتكون من 12 إلى 128 حرفًا.",
            }
            for field in dict.fromkeys(item["loc"][0] for item in error.errors()):
                print(messages.get(field, "تحقق من صحة البيانات."))
            print("أعد إدخال بيانات المسؤول. للإلغاء اضغط Ctrl+C.")


def main():
    with Session(get_engine()) as db:
        if db.scalar(select(User.id).where(User.role == Role.ADMIN)):
            raise SystemExit("يوجد حساب مسؤول بالفعل. أنشئ الحسابات من الواجهة.")
        try:
            data = prompt_admin_data()
        except (KeyboardInterrupt, EOFError):
            print("\nتم إلغاء إنشاء الحساب.")
            return
        db.add(User(name=data.name, email=data.email, role=data.role,
                    password_hash=password_hasher.hash(data.password.get_secret_value())))
        db.commit()
        print("تم إنشاء حساب المسؤول.")


if __name__ == "__main__":
    main()
