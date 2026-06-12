from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .backends import PhoneBackend
from .forms import (
    PhoneLoginForm,
    OTPVerifyForm,
    ProfileCompleteForm,
    ProfileUpdateForm,
    UserAddressForm,
)
from .models import CustomUser, OTPCode, UserAddress


def login_view(request):
    """صفحه ورود با شماره موبایل"""
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'POST':
        form = PhoneLoginForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']

            # بررسی محدودیت ارسال OTP (حداقل ۶۰ ثانیه فاصله)
            recent_otp = OTPCode.objects.filter(
                phone_number=phone_number,
                is_used=False,
                created_at__gte=timezone.now() - timezone.timedelta(seconds=60)
            ).first()

            if recent_otp:
                messages.warning(request, 'لطفاً ۶۰ ثانیه صبر کنید و دوباره تلاش کنید.')
                return render(request, 'accounts/login.html', {'form': form})

            # ایجاد و ارسال OTP
            OTPCode.create_otp(phone_number)

            # ذخیره شماره در session
            request.session['otp_phone'] = phone_number

            messages.success(request, f'کد تأیید به شماره {phone_number} ارسال شد.')
            return redirect('accounts:verify_otp')
    else:
        form = PhoneLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def verify_otp_view(request):
    """صفحه تأیید کد OTP"""
    phone_number = request.session.get('otp_phone')
    if not phone_number:
        return redirect('accounts:login')

    if request.method == 'POST':
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']

            # بررسی کد OTP
            otp = OTPCode.objects.filter(
                phone_number=phone_number,
                code=code,
                is_used=False,
            ).first()

            if otp and otp.is_valid:
                # علامت‌گذاری کد به عنوان استفاده شده
                otp.is_used = True
                otp.save()

                # بررسی وجود کاربر
                user, created = CustomUser.objects.get_or_create(
                    phone_number=phone_number
                )

                # ورود کاربر
                backend = PhoneBackend()
                user = backend.authenticate(request, phone_number=phone_number)
                if user:
                    login(request, user, backend='apps.accounts.backends.PhoneBackend')

                    # پاک کردن session
                    if 'otp_phone' in request.session:
                        del request.session['otp_phone']

                    if created or not user.full_name:
                        # کاربر جدید - تکمیل پروفایل
                        messages.success(request, 'خوش آمدید! لطفاً اطلاعات خود را تکمیل کنید.')
                        return redirect('accounts:complete_profile')
                    else:
                        messages.success(request, f'خوش آمدید {user.full_name}!')
                        # بازگشت به صفحه قبلی یا صفحه اصلی
                        next_url = request.session.get('next', 'core:home')
                        return redirect(next_url)
            else:
                if otp and otp.is_expired:
                    messages.error(request, 'کد تأیید منقضی شده است. لطفاً دوباره تلاش کنید.')
                else:
                    messages.error(request, 'کد تأیید نامعتبر است.')
    else:
        form = OTPVerifyForm()

    return render(request, 'accounts/verify_otp.html', {
        'form': form,
        'phone_number': phone_number,
    })


def resend_otp_view(request):
    """ارسال مجدد کد OTP"""
    phone_number = request.session.get('otp_phone')
    if not phone_number:
        return redirect('accounts:login')

    # بررسی محدودیت زمانی
    recent_otp = OTPCode.objects.filter(
        phone_number=phone_number,
        is_used=False,
        created_at__gte=timezone.now() - timezone.timedelta(seconds=60)
    ).first()

    if recent_otp:
        messages.warning(request, 'لطفاً ۶۰ ثانیه صبر کنید.')
    else:
        OTPCode.create_otp(phone_number)
        messages.success(request, 'کد تأیید جدید ارسال شد.')

    return redirect('accounts:verify_otp')


@login_required
def complete_profile_view(request):
    """تکمیل پروفایل پس از ثبت‌نام"""
    if request.method == 'POST':
        form = ProfileCompleteForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'اطلاعات شما با موفقیت ذخیره شد.')
            return redirect('core:home')
    else:
        form = ProfileCompleteForm(instance=request.user)

    return render(request, 'accounts/complete_profile.html', {'form': form})


@login_required
def profile_view(request):
    """صفحه پروفایل کاربر"""
    return render(request, 'accounts/profile.html')


@login_required
def profile_update_view(request):
    """ویرایش پروفایل"""
    if request.method == 'POST':
        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'پروفایل شما به‌روزرسانی شد.')
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, 'accounts/profile_update.html', {'form': form})


@login_required
def address_list_view(request):
    """لیست آدرس‌های کاربر"""
    addresses = request.user.addresses.all()
    return render(request, 'accounts/address_list.html', {'addresses': addresses})


@login_required
def address_create_view(request):
    """افزودن آدرس جدید"""
    if request.method == 'POST':
        form = UserAddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'آدرس جدید اضافه شد.')
            return redirect('accounts:address_list')
    else:
        form = UserAddressForm()

    return render(request, 'accounts/address_form.html', {
        'form': form,
        'title': 'افزودن آدرس جدید',
    })


@login_required
def address_update_view(request, pk):
    """ویرایش آدرس"""
    address = get_object_or_404(UserAddress, pk=pk, user=request.user)

    if request.method == 'POST':
        form = UserAddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'آدرس به‌روزرسانی شد.')
            return redirect('accounts:address_list')
    else:
        form = UserAddressForm(instance=address)

    return render(request, 'accounts/address_form.html', {
        'form': form,
        'title': 'ویرایش آدرس',
    })


@login_required
@require_POST
def address_delete_view(request, pk):
    """حذف آدرس"""
    address = get_object_or_404(UserAddress, pk=pk, user=request.user)
    address.delete()
    messages.success(request, 'آدرس حذف شد.')
    return redirect('accounts:address_list')


@login_required
def order_history_view(request):
    """تاریخچه سفارشات کاربر"""
    orders = request.user.orders.all().order_by('-created_at')
    return render(request, 'accounts/order_history.html', {'orders': orders})


def logout_view(request):
    """خروج کاربر"""
    logout(request)
    messages.success(request, 'با موفقیت خارج شدید.')
    return redirect('core:home')
