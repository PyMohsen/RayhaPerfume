from django.db import models


class SiteSettings(models.Model):
    """تنظیمات کلی سایت (Singleton)"""
    site_name = models.CharField(
        max_length=200,
        default='عطر رایحا',
        verbose_name='نام سایت'
    )
    logo = models.ImageField(
        upload_to='site/',
        blank=True,
        null=True,
        verbose_name='لوگو'
    )
    favicon = models.ImageField(
        upload_to='site/',
        blank=True,
        null=True,
        verbose_name='فاویکون'
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='شماره تماس'
    )
    email = models.EmailField(
        blank=True,
        verbose_name='ایمیل'
    )
    address = models.TextField(
        blank=True,
        verbose_name='آدرس'
    )
    instagram = models.URLField(
        blank=True,
        verbose_name='اینستاگرام'
    )
    telegram = models.URLField(
        blank=True,
        verbose_name='تلگرام'
    )
    whatsapp = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='واتساپ'
    )
    about_text = models.TextField(
        blank=True,
        verbose_name='متن درباره ما'
    )
    shipping_info = models.TextField(
        blank=True,
        verbose_name='اطلاعات ارسال'
    )
    return_policy = models.TextField(
        blank=True,
        verbose_name='سیاست بازگشت'
    )
    terms = models.TextField(
        blank=True,
        verbose_name='قوانین و مقررات'
    )

    # متا تگ‌ها
    meta_title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='عنوان متا'
    )
    meta_description = models.TextField(
        blank=True,
        verbose_name='توضیحات متا'
    )

    class Meta:
        verbose_name = 'تنظیمات سایت'
        verbose_name_plural = 'تنظیمات سایت'

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        # فقط یک نمونه مجاز است (Singleton)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Slider(models.Model):
    """اسلایدر صفحه اصلی"""
    title = models.CharField(max_length=200, verbose_name='عنوان')
    subtitle = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='زیرعنوان'
    )
    image = models.ImageField(
        upload_to='sliders/',
        verbose_name='تصویر'
    )
    link = models.URLField(
        blank=True,
        verbose_name='لینک'
    )
    button_text = models.CharField(
        max_length=50,
        blank=True,
        default='مشاهده',
        verbose_name='متن دکمه'
    )
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')

    class Meta:
        verbose_name = 'اسلایدر'
        verbose_name_plural = 'اسلایدرها'
        ordering = ['order']

    def __str__(self):
        return self.title


class FAQ(models.Model):
    """سوالات متداول"""
    question = models.CharField(max_length=500, verbose_name='سوال')
    answer = models.TextField(verbose_name='پاسخ')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب')
    is_active = models.BooleanField(default=True, verbose_name='فعال')

    class Meta:
        verbose_name = 'سوال متداول'
        verbose_name_plural = 'سوالات متداول'
        ordering = ['order']

    def __str__(self):
        return self.question


class ContactMessage(models.Model):
    """پیام‌های تماس با ما"""
    name = models.CharField(max_length=150, verbose_name='نام')
    phone = models.CharField(max_length=11, verbose_name='شماره تماس')
    email = models.EmailField(blank=True, verbose_name='ایمیل')
    subject = models.CharField(max_length=200, verbose_name='موضوع')
    message = models.TextField(verbose_name='پیام')
    is_read = models.BooleanField(default=False, verbose_name='خوانده شده')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ارسال')

    class Meta:
        verbose_name = 'پیام تماس'
        verbose_name_plural = 'پیام‌های تماس'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.subject}'
