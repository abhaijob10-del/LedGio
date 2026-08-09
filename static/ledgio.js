/**
 * ledgio.js — LedGio global scripts (theme, toast notifications, confetti).
 *
 * Loaded with defer from base.html. Extracted from inline <script> blocks
 * so the browser can cache this file across pages.
 */

/* ────────────────────────────────────────────────────────────────────────
   THEME SYSTEM
   Reads from localStorage, applies [data-theme] on <html>, persists choice.
──────────────────────────────────────────────────────────────────────── */
(function () {
    const root   = document.documentElement;
    const btn    = document.getElementById('theme-toggle');
    const icon   = btn ? btn.querySelector('.theme-icon') : null;
    const DARK   = 'dark';
    const LIGHT  = 'light';

    function applyTheme(theme) {
        root.setAttribute('data-theme', theme);
        if (icon) icon.textContent = theme === DARK ? '🌙' : '☀️';
        localStorage.setItem('ledgio-theme', theme);
    }

    // On load — restore saved preference (default dark)
    const saved = localStorage.getItem('ledgio-theme') || DARK;
    applyTheme(saved);

    if (btn) {
        btn.addEventListener('click', function () {
            const current = root.getAttribute('data-theme') || DARK;
            applyTheme(current === DARK ? LIGHT : DARK);
        });
    }
})();


/* ────────────────────────────────────────────────────────────────────────
   TOAST NOTIFICATION SYSTEM
   Reads Django messages from hidden DOM elements and shows animated toasts.
──────────────────────────────────────────────────────────────────────── */
(function () {
    const container = document.getElementById('toast-container');
    if (!container) return;

    function showToast(text, level) {
        const toast = document.createElement('div');
        toast.className = 'toast toast-' + (level || 'info');

        const icon = {
            success: '✅',
            error:   '❌',
            warning: '⚠️',
            info:    'ℹ️',
            messages: 'ℹ️'
        }[level] || 'ℹ️';

        toast.innerHTML =
            '<span class="toast-icon">' + icon + '</span>' +
            '<span class="toast-text">' + text + '</span>' +
            '<button class="toast-close" onclick="this.parentElement.remove()" aria-label="Close">&times;</button>';

        container.appendChild(toast);

        // Trigger enter animation
        requestAnimationFrame(function () { toast.classList.add('toast-visible'); });

        // Auto-dismiss after 4 seconds
        setTimeout(function () {
            toast.classList.remove('toast-visible');
            toast.classList.add('toast-exit');
            setTimeout(function () { toast.remove(); }, 400);
        }, 4000);
    }

    // Read Django messages
    const msgContainer = document.getElementById('django-messages');
    if (msgContainer) {
        const spans = msgContainer.querySelectorAll('span[data-text]');
        spans.forEach(function (span) {
            const level = span.dataset.level || 'info';
            const text  = span.dataset.text  || '';
            if (text) showToast(text, level);
        });
    }

    // Expose globally so other scripts can trigger toasts
    window.LedGio = window.LedGio || {};
    window.LedGio.toast = showToast;
})();


/* ────────────────────────────────────────────────────────────────────────
   CONFETTI SYSTEM
   Call window.LedGio.confetti() to fire a celebration burst.
──────────────────────────────────────────────────────────────────────── */
(function () {
    const canvas = document.getElementById('confetti-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let particles = [];
    let animId;

    function resize() {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    const COLORS = ['#38bdf8','#a855f7','#22c55e','#f59e0b','#ef4444','#ec4899','#fbbf24'];

    function createParticle() {
        return {
            x:    Math.random() * canvas.width,
            y:    -10,
            w:    Math.random() * 12 + 6,
            h:    Math.random() * 6 + 4,
            color: COLORS[Math.floor(Math.random() * COLORS.length)],
            rot:  Math.random() * 360,
            vx:   (Math.random() - 0.5) * 4,
            vy:   Math.random() * 4 + 2,
            vr:   (Math.random() - 0.5) * 8,
            alpha: 1,
        };
    }

    function fireConfetti() {
        canvas.style.display = 'block';
        particles = [];
        for (let i = 0; i < 120; i++) {
            const p = createParticle();
            p.x = Math.random() * canvas.width;
            particles.push(p);
        }
        if (animId) cancelAnimationFrame(animId);
        animate();
        setTimeout(function () {
            cancelAnimationFrame(animId);
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            canvas.style.display = 'none';
            particles = [];
        }, 3500);
    }

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(function (p) {
            p.x  += p.vx;
            p.y  += p.vy;
            p.rot += p.vr;
            p.vy += 0.08;
            if (p.y > canvas.height * 0.7) p.alpha -= 0.02;

            ctx.save();
            ctx.globalAlpha = Math.max(p.alpha, 0);
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot * Math.PI / 180);
            ctx.fillStyle = p.color;
            ctx.fillRect(-p.w/2, -p.h/2, p.w, p.h);
            ctx.restore();
        });
        particles = particles.filter(function (p) { return p.alpha > 0; });
        if (particles.length > 0) {
            animId = requestAnimationFrame(animate);
        } else {
            canvas.style.display = 'none';
        }
    }

    window.LedGio = window.LedGio || {};
    window.LedGio.confetti = fireConfetti;
})();
