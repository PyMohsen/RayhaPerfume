from django.contrib.auth.backends import ModelBackend

from .models import CustomUser


class PhoneBackend(ModelBackend):
    """
    بک‌اند احراز هویت با شماره موبایل
    """

    def authenticate(self, request, phone_number=None, **kwargs):
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            if user.is_active:
                return user
        except CustomUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
