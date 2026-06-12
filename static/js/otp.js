/**
 * Rayha Perfume — OTP Timer
 */

(function () {
    var timerEl = document.getElementById('timer-count');
    var timerContainer = document.getElementById('otp-timer');
    var resendLink = document.getElementById('resend-link');

    if (!timerEl) return;

    var seconds = 120;

    var interval = setInterval(function () {
        seconds--;
        timerEl.textContent = seconds;

        if (seconds <= 0) {
            clearInterval(interval);
            if (timerContainer) timerContainer.style.display = 'none';
            if (resendLink) resendLink.style.display = 'inline-block';
        }
    }, 1000);
})();
