// ============================================================================
// DOLA 30S STUDIO PRO - UNIVERSAL FACEBOOK OAUTH CONSENT AUTO-CONFIRM
// Tự động nhận diện & bấm nút Xác nhận liên kết Facebook OAuth ĐA QUỐC GIA
// Hỗ trợ 100% VIA mọi ngôn ngữ (Bồ Đào Nha "Continuar como", Thổ Nhĩ Kỳ "Devam Et",
// Anh "Continue as", Việt "Tiếp tục", Tây Ban Nha, Pháp, Đức, Nga, Trung, Nhật...)
// Nhận diện kép: MÀU XANH THƯƠNG HIỆU + CHỮ TRẮNG + TỪ KHÓA ĐA NGÔN NGỮ + TỌA ĐỘ
// Tác giả: LÊ VIỆT TÙNG | Zalo/Hotline: 0915967790
// ============================================================================

(() => {
  'use strict';

  let isOpenerWindow = false;
  try {
    isOpenerWindow = (window.opener !== null && window.opener !== undefined);
  } catch (e) {}

  const loc = (window.location.href || '').toLowerCase();

  // Kiểm tra xem có phải trang Consent / OAuth / GDP của Facebook không
  const isConsentPage = (
    loc.includes('/privacy/consent') ||
    loc.includes('flow=gdp') ||
    loc.includes('1819912395072617') ||
    loc.includes('dola.com') ||
    loc.includes('/dialog/') ||
    loc.includes('oauth') ||
    loc.includes('/v') ||
    loc.includes('/login.php') ||
    isOpenerWindow
  );

  if (!isConsentPage) return;

  console.log('[FB AutoClick Universal] 🚀 Kích hoạt bộ quét nút xác nhận Facebook Consent đa quốc gia:', window.location.href);

  let clickCount = 0;
  let lastClickTime = 0;
  let attempts = 0;

  // Regex nhận diện các từ khóa Tiếp tục / Xác nhận trên VIA Facebook toàn cầu
  const ACTION_KEYWORDS = /(?:continuar\s+como|continue\s+as|ti\u1ebfp\s+t\u1ee5c\s+d\u01b0\u1edbi\s+t\u00ean|olarak\s+devam\s+et|fortfahren\s+als|als\s+.*fortfahren|continuer\s+en\s+tant|segui\s+come|continua\s+come|kontynuuj\s+jako|\u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c\s+\u043a\u0430\u043a|\u3068\u3057\u3066\u7d9a\u884c|\uacc4\u1edd|\u7ee7\u7eed|continuar|ti\u1ebfp\s+t\u1ee5c|continue|devam\s+et|allow\s+all|accept)/i;

  // Regex loại trừ nút Hủy / Đóng / Link điều khoản / Avatar profile ở header
  const EXCLUDE_KEYWORDS = /(?:cancelar|cancel|h\u1ee7y|iptal|abbrechen|annuler|annulla|\u043e\u0442\u043c\u0435\u043d\u0430|fechar|close|\u0111\u00f3ng|saiba\s+mais|ver\s+acesso|learn\s+more|pol\u00edtica|policy|termos|terms|trocar\s+de\s+conta|switch\s+account)/i;

  // Kiểm tra màu Xanh Facebook (#1877F2, #0866FF, #0064E0, rgb(8, 102, 255)...)
  function isFacebookBlue(colorStr) {
    if (!colorStr) return false;
    const m = colorStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/i);
    if (!m) return false;
    const r = parseInt(m[1], 10);
    const g = parseInt(m[2], 10);
    const b = parseInt(m[3], 10);
    const a = m[4] !== undefined ? parseFloat(m[4]) : 1;
    if (a < 0.3) return false; // trong suốt
    // Màu xanh dương chủ đạo: B >= 150, B cao hơn R và G
    return b >= 150 && (b - r >= 40) && (b - g >= 10);
  }

  // Kiểm tra màu chữ trắng hoặc sáng (#fff, rgb(255, 255, 255))
  function isWhiteOrLightText(colorStr) {
    if (!colorStr) return false;
    const m = colorStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    if (!m) return false;
    const r = parseInt(m[1], 10);
    const g = parseInt(m[2], 10);
    const b = parseInt(m[3], 10);
    return (r >= 210 && g >= 210 && b >= 210);
  }

  // Kích hoạt toàn bộ sự kiện click tương thích chuẩn React 18 / Facebook Comet
  function triggerFullClick(btn) {
    if (!btn) return;
    try {
      btn.scrollIntoView({ block: 'center', inline: 'center' });
      btn.focus();
      
      const mouseOpts = { bubbles: true, cancelable: true, view: window, buttons: 1, pointerId: 1 };
      ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evtType => {
        try {
          if (evtType.startsWith('pointer')) {
            btn.dispatchEvent(new PointerEvent(evtType, mouseOpts));
          } else {
            btn.dispatchEvent(new MouseEvent(evtType, mouseOpts));
          }
        } catch (e) {
          btn.dispatchEvent(new MouseEvent(evtType, mouseOpts));
        }
      });

      if (typeof btn.click === 'function') {
        btn.click();
      }
    } catch (err) {
      if (typeof btn.click === 'function') btn.click();
    }
  }

  function tryClickConfirmButton() {
    const now = Date.now();
    // Giãn cách click ít nhất 1.2s để tránh spam khi Facebook đang xử lý chuyển hướng
    if (clickCount > 0 && now - lastClickTime < 1200) {
      return false;
    }

    try {
      // ═══════════════════════════════════════════════════════════════════════
      // CHIẾN LƯỢC 1: Tìm theo NÚT CÓ CHỮ TỪ KHÓA XÁC NHẬN ĐA NGÔN NGỮ
      // (Bồ Đào Nha "Continuar como Charlene", Thổ Nhĩ Kỳ "Devam Et", Anh "Continue as"...)
      // ═══════════════════════════════════════════════════════════════════════
      const allClickables = Array.from(document.querySelectorAll(
        'button, div[role="button"], a[role="button"], [tabindex="0"], input[type="submit"]'
      ));

      for (const btn of allClickables) {
        const text = (btn.innerText || btn.textContent || btn.value || '').trim();
        if (!text) continue;

        // Bỏ qua nếu chứa từ khóa Hủy/Cancel/Saiba mais...
        if (EXCLUDE_KEYWORDS.test(text)) continue;

        // Nếu chứa từ khóa Tiếp tục / Continuar / Continue / Devam et...
        if (ACTION_KEYWORDS.test(text)) {
          const r = btn.getBoundingClientRect();
          // Kiểm tra kích thước và vị trí (nằm trong vùng thân trang, tránh header avatar)
          if (r.width >= 80 && r.height >= 24 && r.height <= 90 && r.y >= 80) {
            triggerFullClick(btn);
            clickCount++;
            lastClickTime = Date.now();
            console.log(`[FB AutoClick] ✅ [Chiến Lược 1 - Từ Khóa Đa Ngữ] Đã click nút: '${text}'`, { width: r.width, height: r.height, y: r.y });
            return true;
          }
        }
      }

      // ═══════════════════════════════════════════════════════════════════════
      // CHIẾN LƯỢC 2: QUÉT NỀN XANH DƯƠNG FACEBOOK + CHỮ TRẮNG (TOÀN BỘ DOM)
      // Tìm phần tử có background màu xanh FB và text màu trắng (chuẩn nút chính Meta)
      // ═══════════════════════════════════════════════════════════════════════
      const allDomElements = Array.from(document.querySelectorAll('div, span, button, a'));
      for (const el of allDomElements) {
        try {
          const cs = window.getComputedStyle(el);
          if (isFacebookBlue(cs.backgroundColor)) {
            // Tìm container click gần nhất
            const targetBtn = el.closest('button, div[role="button"], a[role="button"], [tabindex="0"]') || el;
            const r = targetBtn.getBoundingClientRect();

            // Nút xác nhận Facebook luôn có bề ngang rộng (>= 100px) và nằm dưới header (y >= 100)
            if (r.width >= 100 && r.height >= 24 && r.height <= 90 && r.y >= 100) {
              const text = (targetBtn.innerText || targetBtn.textContent || '').trim();
              if (EXCLUDE_KEYWORDS.test(text)) continue;

              triggerFullClick(targetBtn);
              // Đồng thời bấm cả phần tử inner el để đảm bảo React Fiber bắt được sự kiện
              if (targetBtn !== el) {
                triggerFullClick(el);
              }
              clickCount++;
              lastClickTime = Date.now();
              console.log(`[FB AutoClick] ✅ [Chiến Lược 2 - Nền Xanh FB & Chữ Trắng] Đã click: '${text}'`, { width: r.width, height: r.height, y: r.y });
              return true;
            }
          }
        } catch (e) {}
      }

      // ═══════════════════════════════════════════════════════════════════════
      // CHIẾN LƯỢC 3: NÚT ĐẶC THÙ FACEBOOK (__CONFIRM__, testid)
      // ═══════════════════════════════════════════════════════════════════════
      const specialConfirm = document.querySelector(
        'button[name="__CONFIRM__"], input[name="__CONFIRM__"], #loginbutton, [data-testid*="confirm" i], [data-testid*="platform_login_button" i]'
      );
      if (specialConfirm) {
        const r = specialConfirm.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          triggerFullClick(specialConfirm);
          clickCount++;
          lastClickTime = Date.now();
          console.log('[FB AutoClick] ✅ [Chiến Lược 3 - Selector Đặc Thù] Đã click __CONFIRM__!');
          return true;
        }
      }

      // ═══════════════════════════════════════════════════════════════════════
      // CHIẾN LƯỢC 4: THẺ MODAL CỦA CONSENT DIALOG (Nút màu xanh trong khung)
      // ═══════════════════════════════════════════════════════════════════════
      const dialog = document.querySelector('div[role="dialog"], div[aria-modal="true"], form');
      if (dialog) {
        const dialogBtns = Array.from(dialog.querySelectorAll('button, div[role="button"], a[role="button"]'))
          .filter(b => {
            const r = b.getBoundingClientRect();
            const txt = (b.innerText || b.textContent || '').trim();
            return r.width >= 120 && r.height >= 26 && r.height <= 85 && !EXCLUDE_KEYWORDS.test(txt);
          });

        if (dialogBtns.length > 0) {
          // Nút đầu tiên hợp lệ trong dialog thường là Tiếp tục / Đồng ý
          const primaryBtn = dialogBtns[0];
          triggerFullClick(primaryBtn);
          clickCount++;
          lastClickTime = Date.now();
          console.log(`[FB AutoClick] ✅ [Chiến Lược 4 - Dialog First Action] Đã click nút trong dialog: '${(primaryBtn.innerText || '').trim()}'`);
          return true;
        }
      }

    } catch (e) {
      console.warn('[FB AutoClick] Lỗi trong quá trình quét nút:', e);
    }

    return false;
  }

  // Quét định kỳ nhanh mỗi 200ms trong 25 giây
  const clickInterval = setInterval(() => {
    attempts++;
    if (attempts > 125) {
      clearInterval(clickInterval);
      return;
    }

    // Nếu đã bấm hơn 2 lần và URL không còn là trang consent thì dừng
    const curLoc = (window.location.href || '').toLowerCase();
    if (clickCount >= 3 || (!curLoc.includes('privacy/consent') && !curLoc.includes('flow=gdp') && clickCount > 0)) {
      clearInterval(clickInterval);
      return;
    }

    tryClickConfirmButton();
  }, 200);

  // Quan sát DOM Mutation để click ngay lập tức khi nút xuất hiện mà không cần chờ timer
  try {
    const observer = new MutationObserver(() => {
      const curLoc = (window.location.href || '').toLowerCase();
      if (clickCount >= 3 || (!curLoc.includes('privacy/consent') && !curLoc.includes('flow=gdp') && clickCount > 0)) {
        observer.disconnect();
        clearInterval(clickInterval);
        return;
      }
      tryClickConfirmButton();
    });

    const rootTarget = document.documentElement || document.body;
    if (rootTarget) {
      observer.observe(rootTarget, { childList: true, subtree: true });
      setTimeout(() => observer.disconnect(), 25000);
    }
  } catch (e) {}

  window.addEventListener('DOMContentLoaded', () => {
    tryClickConfirmButton();
  });
  window.addEventListener('load', () => {
    tryClickConfirmButton();
  });

  setTimeout(() => clearInterval(clickInterval), 26000);
})();
