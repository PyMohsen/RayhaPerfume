from django.contrib.auth.models import BaseUserManager


class CustomUserManager(BaseUserManager):
    """
    مدیریت سفارشی برای مدل CustomUser
    از شماره موبایل به جای ایمیل استفاده می‌کند
    """

    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('شماره موبایل الزامی است')
        
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('سوپر یوزر باید is_staff=True باشد')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('سوپر یوزر باید is_superuser=True باشد')

        return self.create_user(phone_number, password, **extra_fields)
