from django import template

register = template.Library()


def to_persian_digits(value):
    """تبدیل اعداد انگلیسی به فارسی در رشته"""
    if value is None:
        return ""
    translation_table = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    return str(value).translate(translation_table)


@register.filter
def persian_digits(value):
    """فیلتر تبدیل اعداد انگلیسی به فارسی"""
    return to_persian_digits(value)


@register.filter
def price_format(value):
    """فرمت قیمت با جداکننده هزارگان و تبدیل به اعداد فارسی"""
    try:
        value = int(value)
        formatted = '{:,}'.format(value)
        return to_persian_digits(formatted)
    except (ValueError, TypeError):
        return to_persian_digits(value)


@register.filter
def to_toman(value):
    """تبدیل ریال به تومان و فرمت به اعداد فارسی"""
    try:
        value = int(value)
        formatted = '{:,}'.format(value)
        return to_persian_digits(formatted)
    except (ValueError, TypeError):
        return to_persian_digits(value)


@register.filter
def discount_price(price, discount_percent):
    """محاسبه قیمت پس از تخفیف و فرمت به اعداد فارسی"""
    try:
        price = int(price)
        discount = int(discount_percent)
        final = price - (price * discount // 100)
        formatted = '{:,}'.format(final)
        return to_persian_digits(formatted)
    except (ValueError, TypeError):
        return to_persian_digits(price)


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
