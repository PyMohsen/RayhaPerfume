import hashlib
import logging
import os
import re
import time
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
        self.primary_model = getattr(settings, 'GEMINI_MODEL', '') or os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')
        self.fallback_models = [
            'gemini-3.5-flash-lite',
            'gemini-3.5-flash',
            'gemini-2.5-flash',
        ]
        # تنظیمات retry و timeout
        self.max_retries_per_model = 2
        self.base_timeout = (10, 45)  # (connect, read)
        # ساخت session با connection pooling
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=Retry(total=0), pool_connections=5, pool_maxsize=5)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

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

        # کلید کش برای پاسخ‌های موفق قبلی
        cache_key = 'ai_resp_' + hashlib.md5(user_message.encode()).hexdigest()[:12]

        # تلاش برای فراخوانی با مدل‌ها
        models_to_try = [self.primary_model]
        for fb in self.fallback_models:
            if fb not in models_to_try:
                models_to_try.append(fb)

        headers = {'Content-Type': 'application/json'}

        last_error = None
        for model in models_to_try:
            # Circuit breaker: اگر مدل اخیراً خراب بوده رد شو
            cb_key = f'ai_cb_{model}'
            if cache.get(cb_key):
                logger.info(f"Circuit breaker active for {model}, skipping")
                continue

            for attempt in range(self.max_retries_per_model):
                try:
                    url = f"{self.base_url}/v1beta/models/{model}:generateContent?key={self.api_key}"
                    resp = self.session.post(url, json=payload, headers=headers, timeout=self.base_timeout)

                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get('candidates', [])
                        if candidates and 'content' in candidates[0]:
                            parts = candidates[0]['content'].get('parts', [])
                            if parts:
                                raw_reply = parts[0].get('text', '')
                                clean_reply, recommended_slugs = extract_recommended_slugs(raw_reply)
                                perfume_cards = enrich_perfumes(recommended_slugs)
                                result = {
                                    'status': 'success',
                                    'reply': clean_reply,
                                    'recommended_perfumes': perfume_cards,
                                    'model_used': model
                                }
                                # کش کردن پاسخ موفق برای ۱۵ دقیقه
                                cache.set(cache_key, result, 900)
                                return result

                    status = resp.status_code
                    logger.warning(f"Gemini {model} attempt {attempt+1} status {status}: {resp.text[:200]}")
                    last_error = f"Error {status}"

                    if status in (404, 403, 400):
                        # خطای دائمی: مدل رو circuit break کن و برو مدل بعدی
                        cache.set(cb_key, True, 300)
                        break
                    if status in (503, 429, 500):
                        # خطای موقت: صبر کن و retry
                        wait = (attempt + 1) * 3
                        time.sleep(wait)
                        continue
                    break

                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout on {model} attempt {attempt+1}")
                    last_error = 'timeout'
                    time.sleep((attempt + 1) * 2)
                except requests.exceptions.ConnectionError:
                    logger.warning(f"ConnectionError on {model} attempt {attempt+1}")
                    last_error = 'connection_error'
                    time.sleep((attempt + 1) * 2)
                except Exception as e:
                    logger.error(f"Unexpected error on {model}: {e}")
                    last_error = str(e)
                    break

        # ===== فال‌بک: هرگز ارور به کاربر نشان نده =====

        # ۱. پاسخ کش‌شده قبلی
        cached = cache.get(cache_key)
        if cached:
            cached['reply'] += '\n(پاسخ از حافظه مشاور)'
            return cached

        # ۲. پیشنهاد هوشمند محلی بدون AI
        return self._local_smart_fallback(user_message)

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

    def _local_smart_fallback(self, user_message: str) -> Dict:
        """
        فال‌بک هوشمند محلی: وقتی هیچ مدل AI در دسترس نیست،
        بر اساس کلمات کلیدی پیام کاربر از دیتابیس عطر پیشنهاد می‌دهد.
        کاربر هرگز پیام خطا نمی‌بیند.
        """
        msg = user_message.lower()

        # نگاشت کلمات کلیدی به فیلترهای دیتابیس
        filters = {'is_active': True}

        # تشخیص جنسیت
        if any(w in msg for w in ['مردانه', 'مردونه', 'آقایان', 'مرد']):
            filters['gender__name__icontains'] = 'مردانه'
        elif any(w in msg for w in ['زنانه', 'زنونه', 'خانم', 'زن']):
            filters['gender__name__icontains'] = 'زنانه'

        # تشخیص فصل
        season_map = {
            'بهار': 'بهار', 'تابستان': 'تابستان', 'تابستون': 'تابستان',
            'پاییز': 'پاییز', 'پائیز': 'پاییز', 'زمستان': 'زمستان',
            'زمستون': 'زمستان', 'سرد': 'زمستان', 'گرم': 'تابستان',
            'خنک': 'بهار',
        }
        for keyword, season in season_map.items():
            if keyword in msg:
                filters['seasons__name__icontains'] = season
                break

        # تشخیص طبع
        nature_map = {
            'شیرین': 'شیرین', 'تلخ': 'تلخ', 'خنک': 'خنک',
            'گرم': 'گرم', 'تند': 'تند', 'ملایم': 'ملایم',
        }
        for keyword, nature in nature_map.items():
            if keyword in msg:
                filters['nature__name__icontains'] = nature
                break

        try:
            perfumes = (
                Perfume.objects.filter(**filters)
                .select_related('gender', 'nature')
                .order_by('-is_featured', '-views_count')[:3]
            )

            if not perfumes.exists():
                perfumes = (
                    Perfume.objects.filter(is_active=True)
                    .order_by('-is_featured', '-views_count')[:3]
                )

            slugs = [p.slug for p in perfumes]
            cards = enrich_perfumes(slugs)

            names = '، '.join([p.name for p in perfumes[:2]])
            reply = (
                f"بر اساس درخواست شما، این عطرها رو پیشنهاد میدم: {names} 🌸\n"
                "برای مشاوره دقیق‌تر، لطفاً کمی بعد دوباره امتحان کنید."
            )
        except Exception:
            cards = []
            reply = (
                "ممنون از صبرتون! 🌸 الان سرویس مشاوره شلوغه.\n"
                "پیشنهاد میکنم عطرهای پرفروش سایت رو ببینید یا چند دقیقه بعد دوباره امتحان کنید."
            )

        return {
            'status': 'success',
            'reply': reply,
            'recommended_perfumes': cards,
            'model_used': 'local-fallback'
        }
