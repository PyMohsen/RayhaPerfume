import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from apps.products.models import Perfume
from .services import GeminiAdvisorService

logger = logging.getLogger(__name__)


@ensure_csrf_cookie
@require_http_methods(["GET"])
def init_advisor_view(request):
    """
    دریافت تنظیمات اولیه و سوالات آماده شروع گفتگو
    این متد هیچ توکنی از هوش مصنوعی مصرف نمی‌کند (Zero-Token).
    """
    active_perfumes_count = Perfume.objects.filter(is_active=True).count()
    
    quick_suggestions = [
        "یک عطر تلخ و گرم برای روزهای سرد سال",
        "عطر خنک و باطراوت برای استفاده روزانه",
        "عطر شیرین و جذاب با ماندگاری بالا",
        "یک عطر شیک برای هدیه دادن",
    ]

    welcome_message = (
        "سلام! من مشاور هوشمند عطر رایحا هستم. ✨\n"
        "چه سبک رایحه‌ای مد نظرتونه؟ خوشحال میشم کمکتون کنم تا بهترین عطر رو پیدا کنید."
    )

    return JsonResponse({
        'status': 'success',
        'welcome_message': welcome_message,
        'quick_suggestions': quick_suggestions,
        'active_perfumes_count': active_perfumes_count,
    })


@require_http_methods(["POST"])
def chat_api_view(request):
    """
    دریافت پیام کاربر، مدیریت تاریخچه کم‌حجم در سشن و ارتباط با جمینای
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'status': 'error', 'reply': 'داده ارسالی نامعتبر است.'}, status=400)

    user_message = data.get('message', '').strip()
    if not user_message:
        return JsonResponse({'status': 'error', 'reply': 'لطفاً پیام خود را وارد کنید.'}, status=400)

    # محدودسازی طول ورودی جهت جلوگیری از سوءاستفاده و هدررفت توکن
    if len(user_message) > 500:
        user_message = user_message[:500]

    # مدیریت تاریخچه مکالمه در سشن با پنجره لغزان بسیار کم‌حجم (حداکثر ۴ آیتم)
    history = request.session.get('ai_chat_history', [])
    if not isinstance(history, list):
        history = []

    service = GeminiAdvisorService()
    result = service.ask(user_message=user_message, conversation_history=history)

    # به‌روزرسانی تاریخچه مکالمه در سشن
    if result.get('status') in ('success', 'notice'):
        history.append({'role': 'user', 'content': user_message})
        clean_reply = result.get('reply', '')
        history.append({'role': 'model', 'content': clean_reply})
        # فقط ۴ پیام آخر (۲ تبادل) نگه‌داری می‌شود تا در مراجعات بعدی توکن هدر نرود
        request.session['ai_chat_history'] = history[-4:]
        request.session.modified = True
    else:
        print(f"[AI Chat Error Debug]: {result.get('error_detail')}")

    return JsonResponse(result)


@require_http_methods(["POST"])
def reset_chat_view(request):
    """
    پاک‌سازی تاریخچه مکالمه مشاور در سشن
    """
    if 'ai_chat_history' in request.session:
        del request.session['ai_chat_history']
        request.session.modified = True
    return JsonResponse({'status': 'success', 'message': 'تاریخچه گفتگو پاک شد.'})


@require_http_methods(["GET"])
def diagnose_api_view(request):
    """
    تست اتصال به هر آدرس Gemini API از سرور — فقط برای دیباگ
    """
    import time
    import requests as req

    service = GeminiAdvisorService()
    results = []

    # پیلود تست ساده و سبک
    test_payload = {
        'contents': [{'role': 'user', 'parts': [{'text': 'سلام'}]}],
        'generationConfig': {'maxOutputTokens': 20}
    }

    for base_url in service.base_urls:
        entry = {'url': base_url[:50]}

        # تست GET (لیست مدل‌ها)
        get_url = f"{base_url}/v1beta/models?key={service.api_key}"
        start = time.time()
        try:
            resp = req.get(get_url, timeout=(10, 30))
            entry['get_status'] = resp.status_code
            entry['get_time'] = round(time.time() - start, 2)
            entry['get_ok'] = resp.status_code == 200
        except Exception as e:
            entry['get_status'] = type(e).__name__
            entry['get_time'] = round(time.time() - start, 2)
            entry['get_ok'] = False

        # تست POST (generateContent واقعی)
        model = service.primary_model
        post_url = f"{base_url}/v1beta/models/{model}:generateContent?key={service.api_key}"
        start = time.time()
        try:
            resp = req.post(post_url, json=test_payload, headers={'Content-Type': 'application/json'}, timeout=(10, 60))
            entry['post_status'] = resp.status_code
            entry['post_time'] = round(time.time() - start, 2)
            entry['post_ok'] = resp.status_code == 200
            entry['post_body'] = resp.text[:300]
        except Exception as e:
            entry['post_status'] = type(e).__name__
            entry['post_time'] = round(time.time() - start, 2)
            entry['post_ok'] = False
            entry['post_error'] = str(e)[:300]

        results.append(entry)

    return JsonResponse({'results': results, 'primary_model': service.primary_model})
