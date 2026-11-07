from django.contrib import admin
from django.utils.html import format_html

from .models import Order, OrderItem, CouponCode, PaymentSession, DirectPayment
from .eitaayar import (
    notify_admin_new_order,
    notify_admin_tracking_code_updated,
    notify_admin_order_status_changed,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('perfume_name', 'size', 'quantity', 'price', 'discount_percent')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'user', 'full_name', 'final_price',
        'status', 'return_reason_preview', 'payment_method', 'ref_id', 'created_at'
    )
    list_filter = ('status', 'payment_method', 'created_at', 'province')
    search_fields = (
        'order_number', 'full_name', 'phone_number', 'ref_id',
        'torob_transaction_id', 'return_reason',
    )
    readonly_fields = (
        'order_number', 'user', 'total_price', 'discount_amount',
        'coupon_discount', 'final_price', 'payment_token', 'payment_ref_num',
        'ref_id', 'torob_payment_token', 'torob_transaction_id',
        'paid_at', 'return_image_preview', 'return_requested_at', 'pre_return_status', 'created_at', 'updated_at'
    )
    raw_id_fields = ('user', 'coupon')
    inlines = [OrderItemInline]

    fieldsets = (
        ('اطلاعات سفارش', {
            'fields': ('order_number', 'user', 'status', 'payment_method', 'note', 'admin_note')
        }),
        ('اطلاعات مرجوعی', {
            'fields': ('return_reason', 'return_image', 'return_image_preview', 'return_requested_at', 'pre_return_status'),
        }),
        ('اطلاعات گیرنده', {
            'fields': ('full_name', 'phone_number', 'province', 'city', 'address', 'postal_code')
        }),
        ('مبالغ', {
            'fields': (
                'total_price', 'discount_amount', 'coupon_discount',
                'shipping_cost', 'final_price', 'coupon'
            )
        }),
        ('پرداخت', {
            'fields': (
                'payment_token', 'payment_ref_num', 'torob_payment_token',
                'torob_transaction_id', 'ref_id', 'paid_at'
            )
        }),
        ('ارسال', {
            'fields': ('tracking_code',)
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='علت مرجوعی')
    def return_reason_preview(self, obj):
        if not obj.return_reason:
            return '-'
        return (obj.return_reason[:35] + '...') if len(obj.return_reason) > 35 else obj.return_reason

    @admin.display(description='پیش‌نمایش تصویر مرجوعی')
    def return_image_preview(self, obj):
        if obj.return_image:
            return format_html(
                '<a href="{0}" target="_blank" rel="noopener noreferrer">'
                '<img src="{0}" style="max-height: 120px; max-width: 180px; border-radius: 8px; border: 1px solid #ccc; object-fit: cover;" />'
                '</a>',
                obj.return_image.url
            )
        return 'تصویری ثبت نشده است'

    actions = ['send_order_to_eitaa']

    @admin.action(description='ارسال اعلان اطلاعات سفارش به گروه ایتا')
    def send_order_to_eitaa(self, request, queryset):
        count = 0
        for order in queryset:
            notify_admin_new_order(order)
            count += 1
        self.message_user(request, f'اعلان {count} سفارش با موفقیت به صف ارسال ایتا فرستاده شد.', level='success')

    def save_model(self, request, obj, form, change):
        old_tracking = None
        old_status = None
        if change and obj.pk:
            old_order = Order.objects.filter(pk=obj.pk).values('tracking_code', 'status').first()
            if old_order:
                old_tracking = old_order.get('tracking_code')
                old_status = old_order.get('status')

        super().save_model(request, obj, form, change)

        if change:
            # اگر کد رهگیری پستی اضافه یا ویرایش شد
            if 'tracking_code' in form.changed_data and obj.tracking_code and obj.tracking_code != old_tracking:
                notify_admin_tracking_code_updated(obj.id)
            # اگر وضعیت سفارش توسط ادمین تغییر کرد
            elif 'status' in form.changed_data and obj.status != old_status:
                notify_admin_order_status_changed(obj.id, old_status or '', obj.status)


@admin.register(CouponCode)
class CouponCodeAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'discount_percent', 'max_discount',
        'usage_limit', 'used_count', 'is_active',
        'valid_from', 'valid_to'
    )
    list_filter = ('is_active', 'valid_from', 'valid_to')
    search_fields = ('code',)


@admin.register(PaymentSession)
class PaymentSessionAdmin(admin.ModelAdmin):
    list_display = (
        'session_key', 'user', 'payment_method', 'final_price',
        'status', 'order', 'created_at'
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('session_key', 'user__phone_number', 'payment_token', 'torob_payment_token')
    readonly_fields = (
        'session_key', 'user', 'payment_method', 'address_data', 'items_data',
        'total_price', 'discount_amount', 'coupon_discount', 'shipping_cost',
        'final_price', 'coupon', 'note', 'payment_token', 'torob_payment_token',
        'status', 'order', 'created_at', 'updated_at'
    )

    def has_add_permission(self, request):
        return False


@admin.register(DirectPayment)
class DirectPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'tracking_number', 'user', 'amount_display', 'payment_method_display',
        'status_badge', 'ref_id', 'created_at', 'paid_at'
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = (
        'tracking_number', 'user__phone_number', 'user__full_name',
        'ref_id', 'payment_ref_num', 'torob_transaction_id', 'description'
    )
    readonly_fields = (
        'tracking_number', 'user', 'amount', 'payment_method',
        'description', 'status', 'payment_token', 'payment_ref_num',
        'ref_id', 'card_number', 'torob_payment_token', 'torob_transaction_id',
        'paid_at', 'created_at', 'updated_at'
    )
    raw_id_fields = ('user',)
    actions = ['recheck_torobpay_status']
    fieldsets = (
        ('اطلاعات پرداخت', {
            'fields': ('tracking_number', 'user', 'amount', 'payment_method', 'status', 'description')
        }),
        ('اطلاعات تراکنش درگاه بانکی سپ (SEP)', {
            'fields': ('payment_token', 'payment_ref_num', 'ref_id', 'card_number'),
            'classes': ('collapse',),
        }),
        ('اطلاعات تراکنش ترب‌پی', {
            'fields': ('torob_payment_token', 'torob_transaction_id'),
            'classes': ('collapse',),
        }),
        ('زمان‌ها', {
            'fields': ('paid_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='مبلغ (تومان)', ordering='amount')
    def amount_display(self, obj):
        return f'{obj.amount:,} تومان'

    @admin.display(description='روش پرداخت')
    def payment_method_display(self, obj):
        return obj.get_payment_method_display()

    @admin.display(description='وضعیت')
    def status_badge(self, obj):
        colors = {
            'pending': ('#b45309', '#fef3c7'),
            'completed': ('#065f46', '#d1fae5'),
            'failed': ('#991b1b', '#fee2e2'),
            'cancelled': ('#374151', '#f3f4f6'),
        }
        color, bg = colors.get(obj.status, ('#374151', '#f3f4f6'))
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 8px; border-radius:10px; font-weight:600; font-size:12px;">{}</span>',
            bg, color, obj.get_status_display()
        )

    @admin.action(description='استعلام و بررسی مجدد وضعیت از ترب‌پی')
    def recheck_torobpay_status(self, request, queryset):
        from .views import verify_and_settle_direct_payment
        success_count = 0
        failed_count = 0
        for payment in queryset:
            if payment.payment_method == 'torobpay' and payment.torob_payment_token:
                if payment.status == DirectPayment.Status.COMPLETED:
                    continue
                success, msg = verify_and_settle_direct_payment(payment)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    self.message_user(request, f'پرداخت {payment.tracking_number}: {msg}', level='warning')
        if success_count:
            self.message_user(request, f'{success_count} پرداخت ترب‌پی با موفقیت استعلام و تأیید شد.', level='success')
        elif not failed_count:
            self.message_user(request, 'تراکنش ترب‌پی قابل استعلام در موارد انتخابی یافت نشد.', level='info')


