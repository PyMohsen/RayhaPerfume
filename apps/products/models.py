from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Gender(models.Model):
    """دسته‌بندی جنسیتی عطر: مردانه، زنانه، مشترک"""
    name = models.CharField(max_length=50, verbose_name='نام')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    icon = models.ImageField(
        upload_to='categories/genders/',
        blank=True,
        null=True,
        verbose_name='آیکون'
    )
    description = models.TextField(blank=True, verbose_name='توضیحات')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')

    class Meta:
        verbose_name = 'جنسیت'
        verbose_name_plural = 'جنسیت‌ها'
        ordering = ['order']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"{reverse('products:list')}?gender={self.slug}"


class Season(models.Model):
    """فصل مناسب عطر: بهار، تابستان، پاییز، زمستان"""
    name = models.CharField(max_length=50, verbose_name='نام')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    icon = models.ImageField(
        upload_to='categories/seasons/',
        blank=True,
        null=True,
        verbose_name='آیکون'
    )
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')

    class Meta:
        verbose_name = 'فصل'
        verbose_name_plural = 'فصل‌ها'
        ordering = ['order']

    def __str__(self):
        return self.name


class ScentFamily(models.Model):
    """
    گروه بویایی عطر
    مثال: شرقی، فوگره، گورمند، چوبی، گلی و...
    """
    name = models.CharField(max_length=100, verbose_name='نام')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    color = models.CharField(
        max_length=7,
        default='#6B4C9A',
        verbose_name='رنگ نمایشی',
        help_text='کد رنگ HEX مثل #6B4C9A'
    )
    description = models.TextField(blank=True, verbose_name='توضیحات')

    class Meta:
        verbose_name = 'گروه بویایی'
        verbose_name_plural = 'گروه‌های بویایی'
        ordering = ['name']

    def __str__(self):
        return self.name


class Nature(models.Model):
    """
    طبع عطر: گرم، سرد، معتدل
    """
    name = models.CharField(max_length=50, verbose_name='نام')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    icon = models.ImageField(
        upload_to='categories/natures/',
        blank=True,
        null=True,
        verbose_name='آیکون'
    )
    description = models.TextField(blank=True, verbose_name='توضیحات')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')

    class Meta:
        verbose_name = 'طبع'
        verbose_name_plural = 'طبع‌ها'
        ordering = ['order']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:by_nature', kwargs={'slug': self.slug})


class Taste(models.Model):
    """
    طعم عطر: شیرین، تلخ، تند
    """
    name = models.CharField(max_length=50, verbose_name='نام')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    icon = models.ImageField(
        upload_to='categories/tastes/',
        blank=True,
        null=True,
        verbose_name='آیکون'
    )
    description = models.TextField(blank=True, verbose_name='توضیحات')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')

    class Meta:
        verbose_name = 'طعم'
        verbose_name_plural = 'طعم‌ها'
        ordering = ['order']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:by_taste', kwargs={'slug': self.slug})


class Scent(models.Model):
    """
    رایحه‌های عطر
    مثال: وانیلی، اسطوخودوس، آجیلی، بالزامیک و...
    """
    name = models.CharField(max_length=100, verbose_name='نام')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    color = models.CharField(
        max_length=7,
        default='#D4A574',
        verbose_name='رنگ نمایشی',
        help_text='رنگ نوار نمایشی'
    )
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')

    class Meta:
        verbose_name = 'رایحه'
        verbose_name_plural = 'رایحه‌ها'
        ordering = ['order']

    def __str__(self):
        return self.name


class Note(models.Model):
    """
    نوت‌های عطر (مواد اولیه)
    مثال: وانیل، دارچین، لاوندر، فلفل صورتی و...
    """
    name = models.CharField(max_length=100, verbose_name='نام')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    image = models.ImageField(
        upload_to='notes/',
        blank=True,
        null=True,
        verbose_name='تصویر'
    )
    description = models.TextField(blank=True, verbose_name='توضیحات')

    class Meta:
        verbose_name = 'نوت'
        verbose_name_plural = 'نوت‌ها'
        ordering = ['name']

    def __str__(self):
        return self.name


class Perfume(models.Model):
    """مدل اصلی محصول عطر"""

    class Longevity(models.TextChoices):
        VERY_LOW = 'very_low', 'بسیار کم'
        LOW = 'low', 'کم'
        MODERATE = 'moderate', 'متوسط'
        HIGH = 'high', 'بالا'
        VERY_HIGH = 'very_high', 'بسیار بالا'

    class Sillage(models.TextChoices):
        INTIMATE = 'intimate', 'ملایم'
        MODERATE = 'moderate', 'متوسط'
        STRONG = 'strong', 'قوی'
        ENORMOUS = 'enormous', 'قوی و نافذ'

    name = models.CharField(max_length=200, verbose_name='نام عطر')
    slug = models.SlugField(
        max_length=250,
        unique=True,
        allow_unicode=True,
        verbose_name='اسلاگ'
    )
    brand = models.CharField(max_length=200, verbose_name='برند')
    description = models.TextField(verbose_name='توضیحات')
    short_description = models.CharField(
        max_length=300,
        blank=True,
        verbose_name='توضیح کوتاه'
    )

    # دسته‌بندی‌ها
    gender = models.ForeignKey(
        Gender,
        on_delete=models.SET_NULL,
        null=True,
        related_name='perfumes',
        verbose_name='جنسیت'
    )
    seasons = models.ManyToManyField(
        Season,
        blank=True,
        related_name='perfumes',
        verbose_name='فصل‌ها'
    )
    scent_family = models.ForeignKey(
        ScentFamily,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfumes',
        verbose_name='گروه بویایی'
    )
    nature = models.ForeignKey(
        Nature,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfumes',
        verbose_name='طبع'
    )
    tastes = models.ManyToManyField(
        Taste,
        blank=True,
        related_name='perfumes',
        verbose_name='طعم‌ها'
    )
    scents = models.ManyToManyField(
        Scent,
        blank=True,
        related_name='perfumes',
        verbose_name='رایحه‌ها'
    )

    # مشخصات فنی
    longevity = models.CharField(
        max_length=20,
        choices=Longevity.choices,
        default=Longevity.MODERATE,
        verbose_name='ماندگاری'
    )
    sillage = models.CharField(
        max_length=20,
        choices=Sillage.choices,
        default=Sillage.MODERATE,
        verbose_name='پراکندگی'
    )

    # درصد جنسیت
    gender_male_percent = models.PositiveIntegerField(
        default=50,
        verbose_name='درصد مردانه',
        help_text='درصد مناسب بودن برای آقایان'
    )
    gender_female_percent = models.PositiveIntegerField(
        default=50,
        verbose_name='درصد زنانه',
        help_text='درصد مناسب بودن برای خانم‌ها'
    )

    # نوت‌ها
    notes = models.ManyToManyField(
        Note,
        through='PerfumeNote',
        blank=True,
        verbose_name='نوت‌ها'
    )

    # وضعیت
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    is_featured = models.BooleanField(default=False, verbose_name='محصول ویژه')
    views_count = models.PositiveIntegerField(default=0, verbose_name='تعداد بازدید')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')

    class Meta:
        verbose_name = 'عطر'
        verbose_name_plural = 'عطرها'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('products:detail', kwargs={'slug': self.slug})

    @property
    def primary_image(self):
        """تصویر اصلی محصول"""
        img = self.images.filter(is_primary=True).first()
        if not img:
            img = self.images.first()
        return img

    @property
    def min_price(self):
        """کمترین قیمت واریانت‌ها"""
        variant = self.variants.filter(stock__gt=0).order_by('price').first()
        return variant.price if variant else 0

    @property
    def max_price(self):
        """بیشترین قیمت واریانت‌ها"""
        variant = self.variants.order_by('-price').first()
        return variant.price if variant else 0

    @property
    def has_discount(self):
        """آیا تخفیف دارد؟"""
        return self.variants.filter(discount_percent__gt=0).exists()

    @property
    def max_discount(self):
        """بیشترین درصد تخفیف"""
        variant = self.variants.order_by('-discount_percent').first()
        return variant.discount_percent if variant else 0

    @property
    def is_available(self):
        """آیا موجود است؟"""
        return self.variants.filter(stock__gt=0).exists()

    @property
    def top_notes(self):
        """نوت‌های آغازی"""
        return self.perfume_notes.filter(category='top').select_related('note')

    @property
    def middle_notes(self):
        """نوت‌های میانی"""
        return self.perfume_notes.filter(category='middle').select_related('note')

    @property
    def base_notes(self):
        """نوت‌های پایانی"""
        return self.perfume_notes.filter(category='base').select_related('note')

    def increment_views(self):
        """افزایش تعداد بازدید"""
        self.views_count += 1
        self.save(update_fields=['views_count'])


class PerfumeNote(models.Model):
    """جدول واسط برای ارتباط عطر و نوت‌ها"""

    class NoteCategory(models.TextChoices):
        TOP = 'top', 'نوت آغازی'
        MIDDLE = 'middle', 'نوت میانی'
        BASE = 'base', 'نوت پایانی'

    perfume = models.ForeignKey(
        Perfume,
        on_delete=models.CASCADE,
        related_name='perfume_notes',
        verbose_name='عطر'
    )
    note = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='perfume_notes',
        verbose_name='نوت'
    )
    category = models.CharField(
        max_length=10,
        choices=NoteCategory.choices,
        verbose_name='دسته‌بندی نوت'
    )
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')

    class Meta:
        verbose_name = 'نوت عطر'
        verbose_name_plural = 'نوت‌های عطر'
        ordering = ['category', 'order']
        unique_together = ['perfume', 'note', 'category']

    def __str__(self):
        return f'{self.perfume.name} - {self.get_category_display()} - {self.note.name}'


class PerfumeVariant(models.Model):
    """واریانت‌های محصول (حجم‌های مختلف)"""

    SIZE_CHOICES = [
        (50, '۵۰ میلی‌لیتر'),
        (100, '۱۰۰ میلی‌لیتر'),
    ]

    perfume = models.ForeignKey(
        Perfume,
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name='عطر'
    )
    size = models.IntegerField(
        choices=SIZE_CHOICES,
        verbose_name='حجم (میلی‌لیتر)'
    )
    price = models.PositiveIntegerField(verbose_name='قیمت (تومان)')
    discount_percent = models.PositiveIntegerField(
        default=0,
        verbose_name='درصد تخفیف',
        help_text='عدد بین ۰ تا ۱۰۰'
    )
    stock = models.PositiveIntegerField(
        default=0,
        verbose_name='موجودی'
    )
    sku = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='کد محصول (SKU)'
    )

    class Meta:
        verbose_name = 'واریانت عطر'
        verbose_name_plural = 'واریانت‌های عطر'
        ordering = ['size']
        unique_together = ['perfume', 'size']

    def __str__(self):
        return f'{self.perfume.name} - {self.get_size_display()}'

    @property
    def final_price(self):
        """قیمت نهایی پس از تخفیف"""
        if self.discount_percent > 0:
            discount = (self.price * self.discount_percent) // 100
            return self.price - discount
        return self.price

    @property
    def discount_amount(self):
        """مبلغ تخفیف"""
        if self.discount_percent > 0:
            return (self.price * self.discount_percent) // 100
        return 0

    @property
    def is_available(self):
        """آیا موجود است؟"""
        return self.stock > 0


class PerfumeImage(models.Model):
    """تصاویر محصول"""
    perfume = models.ForeignKey(
        Perfume,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name='عطر'
    )
    image = models.ImageField(
        upload_to='perfumes/%Y/%m/',
        verbose_name='تصویر'
    )
    alt_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='متن جایگزین'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='تصویر اصلی'
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name='ترتیب نمایش'
    )

    class Meta:
        verbose_name = 'تصویر عطر'
        verbose_name_plural = 'تصاویر عطر'
        ordering = ['-is_primary', 'order']

    def __str__(self):
        return f'{self.perfume.name} - تصویر {self.order}'

    def save(self, *args, **kwargs):
        # اگر تصویر اصلی تنظیم شده، بقیه را غیرفعال کن
        if self.is_primary:
            PerfumeImage.objects.filter(
                perfume=self.perfume,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class Wishlist(models.Model):
    """لیست علاقه‌مندی‌ها"""
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='wishlists',
        verbose_name='کاربر'
    )
    perfume = models.ForeignKey(
        Perfume,
        on_delete=models.CASCADE,
        related_name='wishlists',
        verbose_name='عطر'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ افزودن')

    class Meta:
        verbose_name = 'علاقه‌مندی'
        verbose_name_plural = 'علاقه‌مندی‌ها'
        unique_together = ['user', 'perfume']
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.perfume.name}'
