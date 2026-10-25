from apps.core.sitemaps import CanonicalSitemap
from .models import Perfume


class PerfumeSitemap(CanonicalSitemap):
    """نقشهٔ سایت داینامیک محصولات فعال و تصاویر آن‌ها."""
    changefreq = 'weekly'
    priority = 0.8
    def items(self):
        return Perfume.objects.filter(is_active=True).prefetch_related('images').order_by('-created_at')

    def lastmod(self, obj):
        return obj.updated_at
