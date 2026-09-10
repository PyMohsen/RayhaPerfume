from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """نقشه سایت صفحات مهم و ثابت وب‌سایت"""
    protocol = 'https'

    PAGES = {
        'core:home': {'priority': 1.0, 'changefreq': 'daily'},
        'products:list': {'priority': 0.9, 'changefreq': 'daily'},
        'core:about': {'priority': 0.6, 'changefreq': 'monthly'},
        'core:contact': {'priority': 0.6, 'changefreq': 'monthly'},
        'core:faq': {'priority': 0.5, 'changefreq': 'monthly'},
        'core:terms': {'priority': 0.4, 'changefreq': 'monthly'},
    }

    def items(self):
        return list(self.PAGES.keys())

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return self.PAGES[item]['priority']

    def changefreq(self, item):
        return self.PAGES[item]['changefreq']
