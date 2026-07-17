from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import CustomUser, OTPCode

class OTPLoginRedirectTests(TestCase):
    def setUp(self):
        self.phone_number = '09123456789'
        self.login_url = reverse('accounts:login')
        self.verify_url = reverse('accounts:verify_otp')
        self.complete_profile_url = reverse('accounts:complete_profile')

    def test_login_redirect_existing_user(self):
        """
        An existing user with a completed profile should be redirected to the 'next' URL
        after entering the correct OTP code.
        """
        # Create the user first
        CustomUser.objects.create(phone_number=self.phone_number, full_name='Test User')

        # Step 1: GET request to login with next parameter
        next_path = reverse('accounts:profile')
        response = self.client.get(f"{self.login_url}?next={next_path}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('next'), next_path)

        # Step 2: POST request to login
        response = self.client.post(f"{self.login_url}?next={next_path}", {
            'phone_number': self.phone_number
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.verify_url)

        # Get the generated OTP code
        otp = OTPCode.objects.filter(phone_number=self.phone_number, is_used=False).first()
        self.assertIsNotNone(otp)

        # Step 3: POST request to verify OTP
        response = self.client.post(self.verify_url, {
            'code': otp.code
        })
        self.assertEqual(response.status_code, 302)
        # Verify redirect to next_path
        self.assertRedirects(response, next_path)
        # Session 'next' should be popped/cleared
        self.assertNotIn('next', self.client.session)

    def test_login_redirect_new_user(self):
        """
        A new user (without a full name) should be redirected to complete profile,
        and then to the 'next' URL after completing their profile.
        """
        # Step 1: GET request to login with next parameter
        next_path = reverse('accounts:profile')
        response = self.client.get(f"{self.login_url}?next={next_path}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('next'), next_path)

        # Step 2: POST request to login
        response = self.client.post(f"{self.login_url}?next={next_path}", {
            'phone_number': self.phone_number
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.verify_url)

        # Get the OTP
        otp = OTPCode.objects.filter(phone_number=self.phone_number, is_used=False).first()

        # Step 3: POST request to verify OTP
        response = self.client.post(self.verify_url, {
            'code': otp.code
        })
        self.assertEqual(response.status_code, 302)
        # Should redirect to complete profile
        self.assertRedirects(response, self.complete_profile_url)
        # Session 'next' should still be preserved
        self.assertEqual(self.client.session.get('next'), next_path)

        # Step 4: POST request to complete profile
        response = self.client.post(self.complete_profile_url, {
            'full_name': 'New Test User',
            'email': 'newuser@example.com'
        })
        self.assertEqual(response.status_code, 302)
        # Should redirect to next_path
        self.assertRedirects(response, next_path)
        # Session 'next' should be popped/cleared
        self.assertNotIn('next', self.client.session)

    def test_login_no_redirect(self):
        """
        If there is no 'next' URL in session, the user should be redirected
        to the homepage (core:home) by default.
        """
        # Create user
        CustomUser.objects.create(phone_number=self.phone_number, full_name='Test User')

        # GET request to login without next parameter
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('next', self.client.session)

        # POST request to login
        response = self.client.post(self.login_url, {
            'phone_number': self.phone_number
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.verify_url)

        # Get OTP
        otp = OTPCode.objects.filter(phone_number=self.phone_number, is_used=False).first()

        # POST request to verify OTP
        response = self.client.post(self.verify_url, {
            'code': otp.code
        })
        self.assertEqual(response.status_code, 302)
        # Should redirect to home page
        self.assertRedirects(response, reverse('core:home'))
        self.assertNotIn('next', self.client.session)
