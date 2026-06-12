from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomUser, OTPCode, UserAddress


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """تنظیمات پنل ادمین برای مدل CustomUser"""
    list_display = ('phone_number', 'full_name', 'email', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'date_joined')
    search_fields = ('phone_number', 'full_name', 'email')
    ordering = ('-date_joined',)

    fieldsets = (
        ('اطلاعات ورود', {
            'fields': ('phone_number', 'password')
        }),
        ('اطلاعات شخصی', {
            'fields': ('full_name', 'email', 'avatar')
        }),
        ('آدرس', {
            'fields': ('province', 'city', 'address', 'postal_code'),
            'classes': ('collapse',),
        }),
        ('دسترسی‌ها', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
    )

    add_fieldsets = (
        ('ایجاد کاربر جدید', {
            'classes': ('wide',),
            'fields': ('phone_number', 'full_name', 'password1', 'password2'),
        }),
    )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    """تنظیمات پنل ادمین برای کدهای OTP"""
    list_display = ('phone_number', 'code', 'created_at', 'expires_at', 'is_used')
    list_filter = ('is_used', 'created_at')
    search_fields = ('phone_number',)
    readonly_fields = ('phone_number', 'code', 'created_at', 'expires_at')
    ordering = ('-created_at',)


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    """تنظیمات پنل ادمین برای آدرس‌ها"""
    list_display = ('user', 'title', 'full_name', 'city', 'province', 'is_default')
    list_filter = ('is_default', 'province', 'city')
    search_fields = ('user__phone_number', 'full_name', 'address')
    raw_id_fields = ('user',)
