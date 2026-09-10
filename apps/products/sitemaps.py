from django.contrib.sitemaps import Sitemap
from .models import Perfume


class PerfumeSitemap(Sitemap):
    """نقشه سایت داینامیک محصولات فعال عطر"""
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Perfume.objects.filter(is_active=True).prefetch_related('images').order_by('-created_at')

    def lastmod(self, obj):
        return obj.updated_at
