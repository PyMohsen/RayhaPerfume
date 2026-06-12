from django import forms

from .models import ContactMessage


class ContactForm(forms.ModelForm):
    """فرم تماس با ما"""
    class Meta:
        model = ContactMessage
        fields = ['name', 'phone', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'نام و نام خانوادگی',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '09123456789',
                'dir': 'ltr',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'ایمیل (اختیاری)',
                'dir': 'ltr',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'موضوع',
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'پیام خود را بنویسید...',
                'rows': 5,
            }),
        }


class SearchForm(forms.Form):
    """فرم جستجو"""
    q = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'search-input',
            'placeholder': 'جستجوی عطر...',
            'autocomplete': 'off',
        })
    )
