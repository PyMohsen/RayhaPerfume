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

    for base_url in service.base_urls:
        test_url = f"{base_url}/v1beta/models?key={service.api_key}"
        start = time.time()
        try:
            resp = req.get(test_url, timeout=(10, 30))
            elapsed = round(time.time() - start, 2)
            results.append({
                'url': base_url[:50],
                'status': resp.status_code,
                'time_sec': elapsed,
                'ok': resp.status_code == 200,
                'body_preview': resp.text[:200] if resp.status_code != 200 else f'{len(resp.json().get("models", []))} models found',
            })
        except req.exceptions.Timeout:
            results.append({'url': base_url[:50], 'status': 'TIMEOUT', 'time_sec': round(time.time() - start, 2), 'ok': False})
        except req.exceptions.ConnectionError as e:
            results.append({'url': base_url[:50], 'status': 'CONNECTION_ERROR', 'time_sec': round(time.time() - start, 2), 'ok': False, 'error': str(e)[:200]})
        except Exception as e:
            results.append({'url': base_url[:50], 'status': 'ERROR', 'time_sec': round(time.time() - start, 2), 'ok': False, 'error': str(e)[:200]})

    return JsonResponse({'results': results})
