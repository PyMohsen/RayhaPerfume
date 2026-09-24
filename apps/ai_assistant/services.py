import logging
import os
import re
from typing import Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache
from apps.products.models import Perfume

logger = logging.getLogger(__name__)


def build_compact_catalog() -> str:
    """
    ایجاد یک فهرست کاتالوگ بسیار فشرده و کم‌حجم از عطرهای فعال
    برای بهینه‌سازی مصرف توکن در Gemini API.
    هر عطر به صورت یک خط تلگرافی فشرده تبدیل می‌شود (~۲۵ الی ۳۵ توکن).
    """
    cached_catalog = cache.get('ai_compact_catalog')
    if cached_catalog:
        return cached_catalog

    perfumes = (
        Perfume.objects.filter(is_active=True)
        .select_related('gender', 'nature')
        .prefetch_related('seasons', 'scent_families', 'tastes', 'perfume_notes__note', 'variants')
        .order_by('-is_featured', '-views_count')[:150]
    )

    lines = []
    for p in perfumes:
        gender = p.gender.name if p.gender else 'نامشخص'
        nature = p.nature.name if p.nature else 'معتدل'
        tastes = '،'.join([t.name for t in p.tastes.all()[:2]]) or 'ندارد'
        seasons = '،'.join([s.name for s in p.seasons.all()[:3]]) or 'چهارفصل'
        
        # استخراج خلاصه نوت‌ها (حداکثر ۲-۳ نوت مهم)
        notes = []
        for pn in p.perfume_notes.all()[:3]:
            notes.append(pn.note.name)
        notes_str = '،'.join(notes) if notes else 'کلاسیک'

        min_price = p.min_price
        price_str = f"{min_price // 1000}هزارتومان" if min_price else "نامشخص"

        # قالب یک‌خطی فوق‌العاده کم‌مصرف
        line = (
            f"[کد:{p.slug}|نام:{p.name}|برند:{p.brand}|جنسیت:{gender}|"
            f"طبع:{nature}|طعم:{tastes}|فصل:{seasons}|نوت:{notes_str}|قیمت:{price_str}]"
        )
        lines.append(line)

    catalog_str = "\n".join(lines)
    # کش کردن کاتالوگ به مدت ۱۰ دقیقه
    cache.set('ai_compact_catalog', catalog_str, 600)
    return catalog_str


def get_system_instruction() -> str:
    """
    پرامپت دستورالعمل سیستم برای مشاور هوشمند عطر با حداقل توکن ممکن
    """
    catalog = build_compact_catalog()
    return (
        "تو مشاور حرفه‌ای، مؤدب و مهربان عطر در فروشگاه عطر رایحا هستی.\n"
        "وظیفه تو:\n"
        "۱. راهنمایی کاربر برای انتخاب بهترین عطر بر اساس سلیقه، جنسیت، فصل یا موقعیت.\n"
        "۲. فقط و فقط از عطرهای موجود در لیست زیر پیشنهاد بده و به هیچ عنوان نام عطری خارج از این لیست نبر.\n"
        "۳. پاسخ‌هایت بسیار کوتاه، جذاب و حداکثر ۲ تا ۳ جمله باشد تا کاربر خسته نشود.\n"
        "۴. اگر کاربر اطلاعات کافی نداد، یک سوال کوتاه و دوستانه بپرس (مثلاً: عطر خنک ترجیح میدهید یا گرم؟ زنانه یا مردانه؟).\n"
        "۵. هر زمان که یک یا دو عطر را پیشنهاد دادی، حتماً در آخرین سطر پاسخ کد اسلاگ آنها را دقیقاً به این الگو درج کن:\n"
        "[پیشنهاد: slug1, slug2]\n"
        "۶. هیچ متن اضافی، لینک، قیمت یا کد HTML داخل متن تولید نکن؛ تمام این موارد به صورت خودکار توسط سیستم به کاربر نمایش داده می‌شود.\n\n"
        "لیست عطرهای فعال فروشگاه:\n"
        f"{catalog}"
    )


def extract_recommended_slugs(text: str) -> Tuple[str, List[str]]:
    """
    استخراج کدهای اسلاگ پیشنهادی از متن پاسخ و پاک‌سازی آن برچسب از متن نهایی
    """
    slugs = []
    # جستجوی الگوی [پیشنهاد: ...] یا [RECOMMEND: ...]
    pattern = r'\[(?:پیشنهاد|RECOMMEND|کد):\s*([^\]]+)\]'
    match = re.search(pattern, text)
    if match:
        raw_slugs = match.group(1).split(',')
        slugs = [s.strip() for s in raw_slugs if s.strip()]
        # حذف برچسب از متن خروجی تا برای کاربر نمایش داده نشود
        clean_text = re.sub(pattern, '', text).strip()
        return clean_text, slugs
    return text.strip(), []


def enrich_perfumes(slugs: List[str]) -> List[Dict]:
    """
    دریافت اطلاعات غنی عطرها (تصویر، قیمت، لینک، ویژگی‌ها) از دیتابیس بدون مصرف توکن AI
    """
    if not slugs:
        return []

    perfumes = (
        Perfume.objects.filter(slug__in=slugs, is_active=True)
        .prefetch_related('images', 'variants')
        .select_related('gender', 'nature')
    )

    result = []
    for p in perfumes:
        img_url = ''
        if p.primary_image and p.primary_image.image:
            img_url = p.primary_image.image.url

        price = p.min_price
        price_formatted = f"{price:,.0f} تومان".replace(',', '،') if price else 'تماس بگیرید'

        result.append({
            'id': p.id,
            'name': p.name,
            'name_en': p.name_en,
            'brand': p.brand,
            'slug': p.slug,
            'url': p.get_absolute_url(),
            'image_url': img_url,
            'price': price,
            'price_formatted': price_formatted,
            'has_discount': p.has_discount,
            'discount_percent': p.max_discount,
            'gender': p.gender.name if p.gender else '',
            'nature': p.nature.name if p.nature else '',
            'short_description': p.short_description or '',
        })
    return result


class GeminiAdvisorService:
    """
    سرویس ارتباط با Gemini API با تمرکز بر حداقل مصرف توکن و مدل Flash
    """
    def __init__(self):
        from dotenv import load_dotenv
        from pathlib import Path
        base_dir = getattr(settings, 'BASE_DIR', Path('.'))
        load_dotenv(base_dir / '.env', override=True)

        self.api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
        self.base_url = (getattr(settings, 'GEMINI_BASE_URL', '') or os.getenv('GEMINI_BASE_URL', '') or 'https://generativelanguage.googleapis.com').rstrip('/')
        self.proxy = getattr(settings, 'GEMINI_PROXY', '') or os.getenv('GEMINI_PROXY', '')
        # مدل پیش‌فرض انتخابی یا مدل درخواستی
        self.primary_model = getattr(settings, 'GEMINI_MODEL', '') or os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')
        # لیست مدل‌های پشتیبان به ترتیب سرعت و در دسترس بودن
        self.fallback_models = [
            'gemini-3.5-flash-lite',
            'gemini-flash-lite-latest',
            'gemini-3.5-flash',
            'gemini-3.6-flash',
            'gemini-2.5-flash',
        ]

    def ask(self, user_message: str, conversation_history: Optional[List[Dict]] = None) -> Dict:
        """
        ارسال پیام به همراه تاریخچه کوتاه (حداکثر ۲-۳ پیام اخیر) به Gemini
        """
        if not self.api_key:
            return self._handle_missing_key(user_message)

        system_instruction = get_system_instruction()

        # ساخت محتوای پیام‌ها با پنجره لغزان تاریخچه (حداکثر ۳ تبادل اخیر)
        contents = []
        if conversation_history:
            recent_history = conversation_history[-4:]
            for msg in recent_history:
                role = 'user' if msg.get('role') == 'user' else 'model'
                text = msg.get('content', '').strip()
                if text:
                    contents.append({
                        'role': role,
                        'parts': [{'text': text}]
                    })

        # افزودن پیام جدید کاربر
        contents.append({
            'role': 'user',
            'parts': [{'text': user_message}]
        })

        payload = {
            'system_instruction': {
                'parts': [{'text': system_instruction}]
            },
            'contents': contents,
            'generationConfig': {
                # سقف توکن خروجی برای پیشگیری از پرحرفی و کاهش هزینه/سهمیه
                'maxOutputTokens': 350,
                'temperature': 0.7,
                'topP': 0.9,
            }
        }

        # تلاش برای فراخوانی با مدل مشخص شده و در صورت نیاز فال‌بک خودکار
        models_to_try = [self.primary_model]
        for fb in self.fallback_models:
            if fb not in models_to_try:
                models_to_try.append(fb)

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        proxies = None
        if self.proxy:
            proxy_str = self.proxy.strip()
            if not any(proxy_str.startswith(p) for p in ('http://', 'https://', 'socks5://', 'socks5h://')):
                proxy_str = f"http://{proxy_str}"
            proxies = {'http': proxy_str, 'https': proxy_str}

        last_error = None
        for model in models_to_try:
            try:
                url = f"{self.base_url}/v1beta/models/{model}:generateContent?key={self.api_key}"
                resp = requests.post(url, json=payload, headers=headers, proxies=proxies, timeout=25)

                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get('candidates', [])
                    if candidates and 'content' in candidates[0]:
                        parts = candidates[0]['content'].get('parts', [])
                        if parts:
                            raw_reply = parts[0].get('text', '')
                            clean_reply, recommended_slugs = extract_recommended_slugs(raw_reply)
                            perfume_cards = enrich_perfumes(recommended_slugs)
                            return {
                                'status': 'success',
                                'reply': clean_reply,
                                'recommended_perfumes': perfume_cards,
                                'model_used': model
                            }

                # ثبت لاگ خطا در کنسول جهت مشاهده در ترمینال
                error_msg = resp.text
                print(f"[Gemini API Warning] Model {model} status {resp.status_code}: {error_msg[:200]}")
                logger.warning(f"Gemini API model {model} returned status {resp.status_code}: {error_msg}")
                last_error = f"Error {resp.status_code}: {error_msg}"

                # اگر مدل در دسترس نبود (503 high demand)، پیدا نشد (404)، سهمیه پر شد (429) یا خطای سرور (500)
                # بلافاصله مدل پشتیبان بعدی را امتحان کن
                if resp.status_code in (404, 503, 429, 500):
                    continue
                else:
                    # برای خطاهای دائمی مثل 400 یا 403 شکستن حلقه
                    break
            except Exception as e:
                logger.error(f"Error calling Gemini API on {model}: {e}")
                last_error = str(e)

        return {
            'status': 'error',
            'reply': 'متأسفانه در برقراری ارتباط با سرویس هوش مصنوعی مشکلی رخ داد. لطفاً بعداً دوباره امتحان کنید.',
            'error_detail': last_error,
            'recommended_perfumes': []
        }

    def _handle_missing_key(self, user_message: str) -> Dict:
        """
        مدیریت حالت عدم وجود کلید API با پاسخ آزمایشی هوشمند برای پیش‌نمایش
        """
        # جستجوی اولیه در دیتابیس برای پیشنهاد نمونه
        sample_perfume = Perfume.objects.filter(is_active=True).first()
        cards = []
        if sample_perfume:
            cards = enrich_perfumes([sample_perfume.slug])

        return {
            'status': 'notice',
            'reply': (
                "سلام! من مشاور هوشمند عطر رایحا هستم. 🌸\n"
                "برای فعال‌سازی کامل پاسخ‌های برخط هوش مصنوعی، لطفاً کلید GEMINI_API_KEY را در فایل .env پروژه تنظیم نمایید.\n"
                "در ادامه یک نمونه از عطرهای محبوب سایت برای شما قرار داده شده است:"
            ),
            'recommended_perfumes': cards,
            'model_used': 'mock-preview'
        }
