from django.contrib import admin

from .models import Order, OrderItem, CouponCode, PaymentSession


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('perfume_name', 'size', 'quantity', 'price', 'discount_percent')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'user', 'full_name', 'final_price',
        'status', 'payment_method', 'ref_id', 'created_at'
    )
    list_filter = ('status', 'payment_method', 'created_at', 'province')
    search_fields = (
        'order_number', 'full_name', 'phone_number', 'ref_id',
        'torob_transaction_id',
    )
    readonly_fields = (
        'order_number', 'user', 'total_price', 'discount_amount',
        'coupon_discount', 'final_price', 'payment_token', 'payment_ref_num',
        'ref_id', 'torob_payment_token', 'torob_transaction_id',
        'paid_at', 'created_at', 'updated_at'
    )
    raw_id_fields = ('user', 'coupon')
    inlines = [OrderItemInline]

    fieldsets = (
        ('اطلاعات سفارش', {
            'fields': ('order_number', 'user', 'status', 'payment_method', 'note', 'admin_note')
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
