import os
from django import forms
from django.core.exceptions import ValidationError
from PIL import Image


class OrderReturnForm(forms.Form):
    """
    فرم ثبت علت مرجوعی سفارش همراه با آپلود امن تصویر.
    بررسی‌های امنیتی:
    1. محدودیت حجم فایل (حداکثر ۵ مگابایت)
    2. بررسی پسوندهای مجاز (JPG, PNG, WEBP)
    3. بررسی نوع MIME
    4. بررسی باینری و هدر فایل توسط Pillow جهت جلوگیری از حملات فایل‌های مخرب، وب‌شل و تغییر نام پسوند
    5. بررسی ابعاد تصویر برای جلوگیری از حملات Decompression Bomb
    """

    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 Megabytes
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
    ALLOWED_PIL_FORMATS = {'JPEG', 'PNG', 'WEBP'}
    MAX_DIMENSION = 8000  # pixels

    return_reason = forms.CharField(
        min_length=5,
        max_length=1000,
        required=True,
        error_messages={
            'required': 'لطفاً علت درخواست مرجوعی را ذکر کنید.',
            'min_length': 'علت مرجوعی باید حداقل ۵ کاراکتر باشد.',
            'max_length': 'علت مرجوعی نمی‌تواند بیش از ۱۰۰۰ کاراکتر باشد.',
        }
    )
    return_image = forms.ImageField(
        required=False,
        error_messages={
            'invalid_image': 'فایل ارسال‌شده یک تصویر معتبر نیست.',
        }
    )

    def clean_return_reason(self):
        reason = self.cleaned_data.get('return_reason', '').strip()
        if not reason or len(reason) < 5:
            raise ValidationError('لطفاً علت درخواست مرجوعی را به صورت کامل (حداقل ۵ کاراکتر) وارد نمایید.')
        return reason

    def clean_return_image(self):
        image = self.cleaned_data.get('return_image')
        if not image:
            return None

        # ۱. بررسی محدودیت حجم فایل
        if hasattr(image, 'size') and image.size > self.MAX_FILE_SIZE:
            raise ValidationError('حجم تصویر نباید بیشتر از ۵ مگابایت باشد.')

        # ۲. بررسی پسوند نام فایل
        filename = getattr(image, 'name', '')
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError('فرمت فایل مجاز نیست. لطفاً یکی از فرمت‌های JPG، PNG یا WEBP را انتخاب کنید.')

        # ۳. بررسی نوع محتوا (MIME type)
        content_type = getattr(image, 'content_type', '').lower()
        if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
            raise ValidationError('نوع محتوای فایل معتبر نیست. تنها فایل‌های تصویری مجاز هستند.')

        # ۴. بررسی عمقی تصویر با Pillow
        try:
            # استریم را در وضعیت شروع قرار می‌دهیم
            if hasattr(image, 'seek'):
                image.seek(0)

            img = Image.open(image)
            img.verify()

            # بررسی فرمت شناسایی‌شده توسط Pillow
            if img.format not in self.ALLOWED_PIL_FORMATS:
                raise ValidationError('فرمت محتوای تصویر معتبر نیست.')

            # بازگشایی مجدد برای استخراج ابعاد و جلوگیری از Decompression Bomb
            if hasattr(image, 'seek'):
                image.seek(0)
            img_detail = Image.open(image)
            width, height = img_detail.size
            if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
                raise ValidationError('ابعاد تصویر بیش از حد مجاز است.')

            # بازگرداندن اشاره‌گر فایل برای فرآیند ذخیره‌سازی بعدی
            if hasattr(image, 'seek'):
                image.seek(0)
        except ValidationError:
            raise
        except Exception:
            raise ValidationError('فایل آپلود شده یک تصویر سالم و معتبر نمی‌باشد.')

        return image

