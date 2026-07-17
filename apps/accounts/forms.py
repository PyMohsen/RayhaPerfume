import re

from django import forms

from .models import CustomUser, UserAddress


class PhoneLoginForm(forms.Form):
    """فرم ورود با شماره موبایل"""
    phone_number = forms.CharField(
        max_length=11,
        min_length=11,
        label='شماره موبایل',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '09123456789',
            'dir': 'ltr',
            'autocomplete': 'tel',
            'inputmode': 'numeric',
        })
    )

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        if not re.match(r'^09\d{9}$', phone):
            raise forms.ValidationError('شماره موبایل معتبر نیست. شماره باید با 09 شروع شود.')
        return phone


class OTPVerifyForm(forms.Form):
    """فرم تأیید کد OTP"""
    code = forms.CharField(
        max_length=5,
        min_length=5,
        label='کد تأیید',
        widget=forms.TextInput(attrs={
            'class': 'form-input otp-input',
            'placeholder': '- - - - -',
            'dir': 'ltr',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'maxlength': '5',
        })
    )

    def clean_code(self):
        code = self.cleaned_data['code']
        if not code.isdigit():
            raise forms.ValidationError('کد تأیید باید فقط شامل اعداد باشد.')
        return code


class ProfileCompleteForm(forms.ModelForm):
    """فرم تکمیل پروفایل"""
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'نام و نام خانوادگی',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'ایمیل (اختیاری)',
                'dir': 'ltr',
            }),
        }


class ProfileUpdateForm(forms.ModelForm):
    """فرم ویرایش پروفایل"""
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'avatar']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'نام و نام خانوادگی',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'ایمیل',
                'dir': 'ltr',
            }),
            'avatar': forms.FileInput(attrs={
                'class': 'form-input',
                'accept': 'image/jpeg,image/png,image/webp',
            }),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            # محدودیت سایز فایل (حداکثر ۲ مگابایت)
            max_size = 2 * 1024 * 1024  # 2MB
            if hasattr(avatar, 'size') and avatar.size > max_size:
                raise forms.ValidationError(
                    'حجم تصویر نباید بیشتر از ۲ مگابایت باشد.'
                )
            # محدودیت نوع فایل
            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if hasattr(avatar, 'content_type') and avatar.content_type not in allowed_types:
                raise forms.ValidationError(
                    'فقط فرمت‌های JPEG، PNG و WebP مجاز هستند.'
                )
        return avatar


class UserAddressForm(forms.ModelForm):
    """فرم آدرس کاربر"""
    class Meta:
        model = UserAddress
        fields = ['title', 'full_name', 'phone_number', 'province', 'city',
                  'address', 'postal_code', 'is_default']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'مثال: خانه، محل کار',
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'نام گیرنده',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '09123456789',
                'dir': 'ltr',
            }),
            'province': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'استان',
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'شهر',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'آدرس کامل',
                'rows': 3,
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'کد پستی',
                'dir': 'ltr',
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        if not re.match(r'^09\d{9}$', phone):
            raise forms.ValidationError('شماره موبایل معتبر نیست.')
        return phone

    def clean_postal_code(self):
        code = self.cleaned_data['postal_code']
        if code and not re.match(r'^\d{10}$', code):
            raise forms.ValidationError('کد پستی باید ۱۰ رقم باشد.')
        return code
