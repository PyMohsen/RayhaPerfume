from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

# تنظیمات پنل ادمین
admin.site.site_header = 'پنل مدیریت عطر رایحا'
admin.site.site_title = 'عطر رایحا'
admin.site.index_title = 'مدیریت فروشگاه'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('products/', include('apps.products.urls')),
    path('cart/', include('apps.cart.urls')),
    path('orders/', include('apps.orders.urls')),
]

# سرو فایل‌های استاتیک و مدیا در حالت توسعه
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
