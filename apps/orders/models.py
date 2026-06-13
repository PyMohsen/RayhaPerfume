import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.products.models import PerfumeVariant


class Order(models.Model):
    """مدل سفارش"""

    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار پرداخت'
        PAID = 'paid', 'پرداخت شده'
        PROCESSING = 'processing', 'در حال پردازش'
        SHIPPED = 'shipped', 'ارسال شده'
        DELIVERED = 'delivered', 'تحویل داده شده'
        CANCELLED = 'cancelled', 'لغو شده'
        REFUNDED = 'refunded', 'مرجوع شده'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name='کاربر'
    )
    order_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='شماره سفارش'
    )

    # اطلاعات گیرنده
    full_name = models.CharField(max_length=150, verbose_name='نام گیرنده')
    phone_number = models.CharField(max_length=11, verbose_name='شماره تماس')
    province = models.CharField(max_length=100, verbose_name='استان')
    city = models.CharField(max_length=100, verbose_name='شهر')
    address = models.TextField(verbose_name='آدرس')
    postal_code = models.CharField(max_length=10, verbose_name='کد پستی')

    # مبالغ
    total_price = models.PositiveIntegerField(verbose_name='مبلغ کل')
    discount_amount = models.PositiveIntegerField(default=0, verbose_name='مبلغ تخفیف')
    coupon_discount = models.PositiveIntegerField(default=0, verbose_name='تخفیف کد تخفیف')
    shipping_cost = models.PositiveIntegerField(default=0, verbose_name='هزینه ارسال')
    final_price = models.PositiveIntegerField(verbose_name='مبلغ نهایی')

    # وضعیت
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='وضعیت'
    )

    # اطلاعات پرداخت
    payment_authority = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='کد Authority'
    )
    ref_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='شماره پیگیری'
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان پرداخت'
    )

    # کد تخفیف
    coupon = models.ForeignKey(
        'CouponCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='کد تخفیف'
    )

    # کد پیگیری پستی
    tracking_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='کد پیگیری پستی'
    )

    note = models.TextField(blank=True, verbose_name='یادداشت مشتری')
    admin_note = models.TextField(blank=True, verbose_name='یادداشت ادمین')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')

    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارشات'
        ordering = ['-created_at']

    def __str__(self):
        return f'سفارش {self.order_number}'

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_order_number():
        """تولید شماره سفارش یکتا"""
        return f'RP-{uuid.uuid4().hex[:8].upper()}'

    @property
    def status_display_class(self):
        """کلاس CSS مناسب وضعیت"""
        classes = {
            'pending': 'status-pending',
            'paid': 'status-paid',
            'processing': 'status-processing',
            'shipped': 'status-shipped',
            'delivered': 'status-delivered',
            'cancelled': 'status-cancelled',
            'refunded': 'status-refunded',
        }
        return classes.get(self.status, '')


class OrderItem(models.Model):
    """آیتم‌های سفارش"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='سفارش'
    )
    variant = models.ForeignKey(
        PerfumeVariant,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='واریانت'
    )
    # ذخیره اطلاعات در زمان خرید (برای حفظ تاریخچه)
    perfume_name = models.CharField(max_length=200, verbose_name='نام عطر')
    size = models.IntegerField(verbose_name='حجم (ml)')
    quantity = models.PositiveIntegerField(verbose_name='تعداد')
    price = models.PositiveIntegerField(verbose_name='قیمت واحد')
    discount_percent = models.PositiveIntegerField(
        default=0,
        verbose_name='درصد تخفیف'
    )

    class Meta:
        verbose_name = 'آیتم سفارش'
        verbose_name_plural = 'آیتم‌های سفارش'

    def __str__(self):
        return f'{self.perfume_name} ({self.size}ml) x{self.quantity}'

    @property
    def final_price(self):
        """قیمت نهایی آیتم"""
        if self.discount_percent > 0:
            discount = (self.price * self.discount_percent) // 100
            return (self.price - discount) * self.quantity
        return self.price * self.quantity

    @property
    def unit_final_price(self):
        """قیمت واحد نهایی"""
        if self.discount_percent > 0:
            discount = (self.price * self.discount_percent) // 100
            return self.price - discount
        return self.price


class CouponCode(models.Model):
    """کد تخفیف"""
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='کد تخفیف'
    )
    discount_percent = models.PositiveIntegerField(
        verbose_name='درصد تخفیف',
        help_text='عدد بین ۱ تا ۱۰۰'
    )
    max_discount = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='حداکثر مبلغ تخفیف (تومان)',
        help_text='حداکثر مبلغ تخفیف قابل اعمال. خالی = بدون محدودیت'
    )
    min_order_amount = models.PositiveIntegerField(
        default=0,
        verbose_name='حداقل مبلغ سفارش (تومان)'
    )
    usage_limit = models.PositiveIntegerField(
        default=1,
        verbose_name='محدودیت تعداد استفاده'
    )
    used_count = models.PositiveIntegerField(
        default=0,
        verbose_name='تعداد استفاده شده'
    )
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    valid_from = models.DateTimeField(verbose_name='معتبر از')
    valid_to = models.DateTimeField(verbose_name='معتبر تا')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')

    class Meta:
        verbose_name = 'کد تخفیف'
        verbose_name_plural = 'کدهای تخفیف'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} ({self.discount_percent}%)'

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.upper()
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """بررسی اعتبار کد"""
        now = timezone.now()
        return (
            self.is_active and
            self.valid_from <= now <= self.valid_to and
            self.used_count < self.usage_limit
        )

    def calculate_discount(self, total_amount):
        """محاسبه مبلغ تخفیف"""
        if not self.is_valid:
            return 0
        if total_amount < self.min_order_amount:
            return 0

        discount = (total_amount * self.discount_percent) // 100
        if self.max_discount:
            discount = min(discount, self.max_discount)
        return discount
