from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

# تنظیمات پنل ادمین
admin.site.site_header = 'پنل مدیریت عطر رایحا'
admin.site.site_title = 'عطر رایحا'
admin.site.index_title = 'مدیریت فروشگاه'

from django.views.generic import RedirectView
from django.contrib.sitemaps.views import sitemap
from apps.core.sitemaps import StaticViewSitemap
from apps.products.sitemaps import PerfumeSitemap
from apps.core.views import robots_txt_view


sitemaps = {
    'static': StaticViewSitemap,
    'perfumes': PerfumeSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('products/', include('apps.products.urls')),
    path('cart/', include('apps.cart.urls')),
    path('orders/', include('apps.orders.urls')),
    path('ai/', include('apps.ai_assistant.urls', namespace='ai')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),

    # سئو: نقشه سایت و ربات‌ها
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt_view, name='robots_txt'),
    
    # مسیرهای فاویکون برای روت اصلی سایت
    path('favicon-96x96.png', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon-96x96.png', permanent=True)),
    path('favicon.svg', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.svg', permanent=True)),
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.ico', permanent=True)),
    path('apple-touch-icon.png', RedirectView.as_view(url=settings.STATIC_URL + 'images/apple-touch-icon.png', permanent=True)),
    path('site.webmanifest', RedirectView.as_view(url=settings.STATIC_URL + 'images/site.webmanifest', permanent=True)),
]


# سرو فایل‌های استاتیک و مدیا در حالت توسعه
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
