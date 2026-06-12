from django import template

register = template.Library()


@register.filter
def price_format(value):
    """فرمت قیمت با جداکننده هزارگان"""
    try:
        value = int(value)
        return '{:,}'.format(value)
    except (ValueError, TypeError):
        return value


@register.filter
def to_toman(value):
    """تبدیل ریال به تومان و فرمت"""
    try:
        value = int(value)
        return '{:,}'.format(value)
    except (ValueError, TypeError):
        return value


@register.filter
def discount_price(price, discount_percent):
    """محاسبه قیمت پس از تخفیف"""
    try:
        price = int(price)
        discount = int(discount_percent)
        final = price - (price * discount // 100)
        return '{:,}'.format(final)
    except (ValueError, TypeError):
        return price


@register.filter
def multiply(value, arg):
    """ضرب دو عدد"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def query_transform(request, **kwargs):
    """به‌روزرسانی query string"""
    updated = request.GET.copy()
    for k, v in kwargs.items():
        if v is not None:
            updated[k] = v
        elif k in updated:
            del updated[k]
    return updated.urlencode()
