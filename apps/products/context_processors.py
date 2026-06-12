from .models import Gender, Nature, Taste


def categories_context(request):
    """دسته‌بندی‌ها برای نمایش در منو و سایدبار"""
    return {
        'nav_genders': Gender.objects.all(),
        'nav_natures': Nature.objects.all(),
        'nav_tastes': Taste.objects.all(),
    }
