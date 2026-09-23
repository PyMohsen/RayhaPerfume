/**
 * AI Perfume Advisor Client — Rayha Perfume
 * Lightweight, zero-dependency, token-optimized assistant controller.
 */

document.addEventListener('DOMContentLoaded', function () {
    const root = document.getElementById('ai-advisor-root');
    if (!root) return;

    const triggerBtn = document.getElementById('ai-advisor-trigger');
    const chatWindow = document.getElementById('ai-chat-window');
    const closeBtn = document.getElementById('ai-close-btn');
    const resetBtn = document.getElementById('ai-reset-btn');
    const messagesContainer = document.getElementById('ai-messages-container');
    const typingIndicator = document.getElementById('ai-typing-indicator');
    const chatForm = document.getElementById('ai-chat-form');
    const userInput = document.getElementById('ai-user-input');

    let isInitialized = false;
    let isSending = false;

    // Helper: دریافت CSRF Token
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) return meta.content;
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input && input.value) return input.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    }

    // باز و بسته کردن پنجره چت
    function toggleChat(forceState) {
        const isOpen = typeof forceState === 'boolean' ? forceState : !chatWindow.classList.contains('is-open');
        if (isOpen) {
            chatWindow.classList.add('is-open');
            chatWindow.setAttribute('aria-hidden', 'false');
            userInput.focus();
            if (!isInitialized) {
                initAdvisor();
            }
        } else {
            chatWindow.classList.remove('is-open');
            chatWindow.setAttribute('aria-hidden', 'true');
        }
    }

    triggerBtn.addEventListener('click', () => toggleChat());
    closeBtn.addEventListener('click', () => toggleChat(false));

    // بستن با کلید Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && chatWindow.classList.contains('is-open')) {
            toggleChat(false);
        }
    });

    // بارگذاری داده‌های اولیه و پیشنهادات شروع (بدون مصرف توکن)
    async function initAdvisor() {
        isInitialized = true;
        try {
            const resp = await fetch('/ai/init/');
            if (!resp.ok) throw new Error('خطا در بارگذاری اولیه');
            const data = await resp.json();
            renderWelcome(data.welcome_message, data.quick_suggestions);
        } catch (err) {
            console.error('AI Advisor init error:', err);
            renderWelcome(
                'سلام! من مشاور هوشمند عطر رایحا هستم. چه سبک عطری مد نظرتونه؟',
                ['عطر تلخ و خنک', 'عطر شیرین و گرم', 'عطر با ماندگاری بالا']
            );
        }
    }

    // رندر بخش خوش‌آمدگویی و چیپ‌های شروع سریع
    function renderWelcome(message, suggestions) {
        messagesContainer.innerHTML = '';
        const welcomeBox = document.createElement('div');
        welcomeBox.className = 'ai-welcome-box';

        const title = document.createElement('h4');
        title.className = 'ai-welcome-title';
        title.textContent = 'مشاوره هوشمند و تخصصی عطر';
        welcomeBox.appendChild(title);

        const text = document.createElement('p');
        text.className = 'ai-welcome-text';
        text.textContent = message;
        welcomeBox.appendChild(text);

        if (suggestions && suggestions.length > 0) {
            const chipsWrap = document.createElement('div');
            chipsWrap.className = 'ai-quick-chips';

            suggestions.forEach(suggestion => {
                const chip = document.createElement('button');
                chip.type = 'button';
                chip.className = 'ai-chip-btn';
                chip.innerHTML = `
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    <span>${suggestion}</span>
                `;
                chip.addEventListener('click', () => {
                    sendMessage(suggestion);
                });
                chipsWrap.appendChild(chip);
            });

            welcomeBox.appendChild(chipsWrap);
        }

        messagesContainer.appendChild(welcomeBox);
        scrollToBottom();
    }

    // اسکرول به انتهای پیام‌ها
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // ایجاد حباب پیام
    function appendMessage(role, text, recommendedPerfumes) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `ai-msg ai-msg-${role}`;

        const bubble = document.createElement('div');
        bubble.className = 'ai-msg-bubble';
        bubble.textContent = text;
        msgDiv.appendChild(bubble);

        // اگر کارت‌های محصول معرفی شده باشد
        if (recommendedPerfumes && recommendedPerfumes.length > 0) {
            const cardsList = document.createElement('div');
            cardsList.className = 'ai-cards-list';

            recommendedPerfumes.forEach(p => {
                const card = document.createElement('a');
                card.className = 'ai-perfume-card';
                card.href = p.url || '#';
                card.target = '_blank';

                const imgHtml = p.image_url 
                    ? `<img src="${p.image_url}" alt="${p.name}" class="ai-card-img" loading="lazy" />`
                    : `<div style="width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#cca04b;">
                         <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 3h12l4 6-10 12L2 9z"/></svg>
                       </div>`;

                const discountBadge = (p.has_discount && p.discount_percent > 0)
                    ? `<span class="ai-card-discount-badge">${p.discount_percent}% تخفیف</span>`
                    : '';

                card.innerHTML = `
                    <div class="ai-card-img-wrap">
                        ${imgHtml}
                        ${discountBadge}
                    </div>
                    <div class="ai-card-details">
                        <div class="ai-card-title" title="${p.name}">${p.name}</div>
                        <div class="ai-card-meta">
                            <span class="ai-card-brand">${p.brand || 'رایحا'}</span>
                            ${p.nature ? `<span>• طبع ${p.nature}</span>` : ''}
                        </div>
                        <div class="ai-card-price-row">
                            <span class="ai-card-price">${p.price_formatted}</span>
                            <span class="ai-card-btn">
                                <span>مشاهده</span>
                                <svg viewBox="0 0 20 20" fill="currentColor">
                                    <path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
                                </svg>
                            </span>
                        </div>
                    </div>
                `;
                cardsList.appendChild(card);
            });

            msgDiv.appendChild(cardsList);
        }

        messagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    // ارسال پیام به سرور
    async function sendMessage(text) {
        if (!text || isSending) return;
        isSending = true;

        // نمایش پیام کاربر در چت
        appendMessage('user', text);
        userInput.value = '';

        // نمایش لودینگ
        typingIndicator.style.display = 'flex';
        scrollToBottom();

        try {
            const response = await fetch('/ai/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ message: text })
            });

            const data = await response.json();
            typingIndicator.style.display = 'none';

            if (data.status === 'success' || data.status === 'notice') {
                appendMessage('assistant', data.reply, data.recommended_perfumes);
            } else {
                appendMessage(
                    'assistant',
                    data.reply || 'متأسفانه مشکلی رخ داد. لطفاً چند لحظه بعد تلاش کنید.'
                );
            }
        } catch (err) {
            console.error('AI chat error:', err);
            typingIndicator.style.display = 'none';
            appendMessage('assistant', 'خطا در ارتباط با سرور. لطفاً اتصال اینترنت خود را بررسی نمایید.');
        } finally {
            isSending = false;
        }
    }

    // فرم ارسال پیام
    chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const text = userInput.value.trim();
        if (text) {
            sendMessage(text);
        }
    });

    // شروع مجدد گفتگو
    resetBtn.addEventListener('click', async function () {
        if (!confirm('آیا مایلید گفتگو با مشاور عطر را از نو آغاز کنید؟')) return;
        try {
            await fetch('/ai/reset/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() }
            });
            initAdvisor();
        } catch (err) {
            console.error('Reset error:', err);
        }
    });
});
