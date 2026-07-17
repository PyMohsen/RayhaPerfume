import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import CustomUserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    مدل کاربر سفارشی
    از شماره موبایل به عنوان شناسه اصلی استفاده می‌کند
    """
    phone_number = models.CharField(
        max_length=11,
        unique=True,
        verbose_name='شماره موبایل',
        help_text='شماره موبایل ۱۱ رقمی (مثال: 09123456789)'
    )
    full_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='نام و نام خانوادگی'
    )
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name='ایمیل'
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name='تصویر پروفایل'
    )

    # آدرس پیش‌فرض
    address = models.TextField(
        blank=True,
        verbose_name='آدرس'
    )
    postal_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='کد پستی'
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='شهر'
    )
    province = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='استان'
    )

    is_active = models.BooleanField(default=True, verbose_name='فعال')
    is_staff = models.BooleanField(default=False, verbose_name='دسترسی ادمین')
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ عضویت')

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'
        ordering = ['-date_joined']

    def __str__(self):
        return self.full_name or self.phone_number

    def get_full_name(self):
        return self.full_name or self.phone_number

    def get_short_name(self):
        if self.full_name:
            return self.full_name.split(' ')[0]
        return self.phone_number


class OTPCode(models.Model):
    """
    مدل کد یکبار مصرف (OTP)
    برای احراز هویت با شماره موبایل
    """
    phone_number = models.CharField(
        max_length=11,
        verbose_name='شماره موبایل'
    )
    code = models.CharField(
        max_length=5,
        verbose_name='کد تأیید'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='زمان ایجاد'
    )
    expires_at = models.DateTimeField(
        verbose_name='زمان انقضا'
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name='استفاده شده'
    )

    class Meta:
        verbose_name = 'کد تأیید'
        verbose_name_plural = 'کدهای تأیید'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone_number} - {self.code}'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=2)
        super().save(*args, **kwargs)

    @staticmethod
    def generate_code():
        """تولید کد ۵ رقمی تصادفی"""
        return str(secrets.randbelow(90000) + 10000)

    @property
    def is_expired(self):
        """بررسی انقضای کد"""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """بررسی معتبر بودن کد"""
        return not self.is_used and not self.is_expired

    @classmethod
    def create_otp(cls, phone_number):
        """
        ایجاد و ارسال کد OTP جدید
        کدهای قبلی را غیرفعال می‌کند
        """
        # غیرفعال کردن کدهای قبلی
        cls.objects.filter(
            phone_number=phone_number,
            is_used=False
        ).update(is_used=True)

        # ایجاد کد جدید
        otp = cls.objects.create(phone_number=phone_number)

        # ارسال SMS (فعلاً console)
        cls.send_otp(phone_number, otp.code)

        return otp

    @staticmethod
    def send_otp(phone_number, code):
        """
        ارسال کد OTP از طریق SMS
        """
        import requests
        import logging
        from django.conf import settings

        logger = logging.getLogger(__name__)

        # چاپ در کنسول برای توسعه و دیباگ
        print(f'\n{"="*40}')
        print(f'  OTP Code for {phone_number}: {code}')
        print(f'{"="*40}\n')

        api_key = getattr(settings, 'SMS_API_KEY', '')
        template_id = getattr(settings, 'SMS_TEMPLATE_ID', '')

        if not api_key or not template_id or api_key == 'your-sms-api-key' or template_id == 'your-template-id':
            logger.warning("تنظیمات SMS.ir (SMS_API_KEY یا SMS_TEMPLATE_ID) به درستی در فایل .env تعریف نشده است. پیامک ارسال نشد.")
            return False

        url = "https://api.sms.ir/v1/send/verify"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": api_key,
        }
        payload = {
            "mobile": phone_number,
            "templateId": int(template_id),
            "parameters": [
                {
                    "name": "Code",
                    "value": str(code)
                }
            ]
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response_json = response.json()
            
            if response.status_code == 200 and response_json.get('status') == 1:
                logger.info(f"کد تأیید با موفقیت به شماره {phone_number} ارسال شد. شناسه پیام: {response_json.get('data')}")
                return True
            else:
                logger.error(
                    f"خطا در ارسال پیامک به شماره {phone_number}. "
                    f"کد وضعیت: {response.status_code}، پاسخ سرور: {response_json}"
                )
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"خطای شبکه در ارسال پیامک به شماره {phone_number}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"خطای غیرمنتظره در ارسال پیامک به شماره {phone_number}: {str(e)}")
            return False


class UserAddress(models.Model):
    """
    مدل آدرس‌های کاربر
    هر کاربر می‌تواند چند آدرس داشته باشد
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name='کاربر'
    )
    title = models.CharField(
        max_length=100,
        verbose_name='عنوان آدرس',
        help_text='مثال: خانه، محل کار'
    )
    full_name = models.CharField(
        max_length=150,
        verbose_name='نام گیرنده'
    )
    phone_number = models.CharField(
        max_length=11,
        verbose_name='شماره تماس'
    )
    province = models.CharField(
        max_length=100,
        verbose_name='استان'
    )
    city = models.CharField(
        max_length=100,
        verbose_name='شهر'
    )
    address = models.TextField(
        verbose_name='آدرس کامل'
    )
    postal_code = models.CharField(
        max_length=10,
        verbose_name='کد پستی'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='آدرس پیش‌فرض'
    )

    class Meta:
        verbose_name = 'آدرس'
        verbose_name_plural = 'آدرس‌ها'
        ordering = ['-is_default', '-id']

    def __str__(self):
        return f'{self.title} - {self.full_name}'

    def save(self, *args, **kwargs):
        # اگر آدرس پیش‌فرض تنظیم شده، بقیه را غیرفعال کن
        if self.is_default:
            UserAddress.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
