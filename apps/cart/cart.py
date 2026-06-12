from apps.products.models import PerfumeVariant


class Cart:
    """
    سبد خرید Session-based
    ساختار Session:
    {
        'cart': {
            '<variant_id>': {
                'quantity': 2,
                'price': 350000,
            },
            ...
        }
    }
    """

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        self.cart = cart

    def add(self, variant, quantity=1):
        """افزودن محصول به سبد خرید"""
        variant_id = str(variant.id)

        if variant_id not in self.cart:
            self.cart[variant_id] = {
                'quantity': 0,
                'price': variant.final_price,
            }

        self.cart[variant_id]['quantity'] += quantity
        self.cart[variant_id]['price'] = variant.final_price
        self.save()

    def remove(self, variant_id):
        """حذف محصول از سبد خرید"""
        variant_id = str(variant_id)
        if variant_id in self.cart:
            del self.cart[variant_id]
            self.save()

    def update_quantity(self, variant_id, quantity):
        """به‌روزرسانی تعداد محصول"""
        variant_id = str(variant_id)
        if variant_id in self.cart:
            if quantity > 0:
                self.cart[variant_id]['quantity'] = quantity
            else:
                del self.cart[variant_id]
            self.save()

    def save(self):
        """ذخیره تغییرات در Session"""
        self.session.modified = True

    def clear(self):
        """خالی کردن سبد خرید"""
        del self.session['cart']
        self.save()

    def get_items(self):
        """دریافت آیتم‌های سبد خرید با اطلاعات کامل"""
        variant_ids = self.cart.keys()
        variants = PerfumeVariant.objects.filter(
            id__in=variant_ids
        ).select_related('perfume').prefetch_related('perfume__images')

        items = []
        for variant in variants:
            variant_id = str(variant.id)
            cart_item = self.cart[variant_id]
            item = {
                'variant': variant,
                'quantity': cart_item['quantity'],
                'price': variant.final_price,
                'total_price': variant.final_price * cart_item['quantity'],
                'original_price': variant.price,
                'total_original_price': variant.price * cart_item['quantity'],
            }
            items.append(item)

        return items

    def get_total_price(self):
        """مبلغ کل سبد خرید (با تخفیف)"""
        items = self.get_items()
        return sum(item['total_price'] for item in items)

    def get_total_original_price(self):
        """مبلغ کل بدون تخفیف"""
        items = self.get_items()
        return sum(item['total_original_price'] for item in items)

    def get_total_discount(self):
        """مبلغ کل تخفیف"""
        return self.get_total_original_price() - self.get_total_price()

    def __len__(self):
        """تعداد کل آیتم‌ها"""
        return sum(item['quantity'] for item in self.cart.values())

    def __iter__(self):
        """تکرار روی آیتم‌ها"""
        return iter(self.get_items())

    def __bool__(self):
        """آیا سبد خرید خالی است؟"""
        return bool(self.cart)
