from django.contrib import admin

from .models import SiteSettings, Slider, FAQ, ContactMessage


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """تنظیمات سایت - فقط یک نمونه مجاز"""
    fieldsets = (
        ('اطلاعات سایت', {
            'fields': ('site_name', 'logo', 'favicon')
        }),
        ('اطلاعات تماس', {
            'fields': ('phone', 'email', 'address')
        }),
        ('شبکه‌های اجتماعی', {
            'fields': ('instagram', 'telegram', 'whatsapp'),
            'classes': ('collapse',),
        }),
        ('محتوا', {
            'fields': ('about_text', 'shipping_info', 'return_policy', 'terms'),
            'classes': ('collapse',),
        }),
        ('سئو', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        # فقط یک نمونه مجاز
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Slider)
class SliderAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'order')
    list_filter = ('is_active',)
    list_editable = ('is_active', 'order')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'is_active', 'order')
    list_filter = ('is_active',)
    list_editable = ('is_active', 'order')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'subject', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('name', 'phone', 'subject', 'message')
    readonly_fields = ('name', 'phone', 'email', 'subject', 'message', 'created_at')
    list_editable = ('is_read',)

    def has_add_permission(self, request):
        return False
