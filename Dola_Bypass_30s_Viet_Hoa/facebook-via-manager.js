// ============================================================================
// DOLA 30S STUDIO PRO - FACEBOOK VIA AUTO-LOGIN ENGINE
// Tác giả: LÊ VIỆT TÙNG | Zalo: 0915967790
// ============================================================================

(function () {
  'use strict';

  function base32ToBytes(base32) {
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    const clean = String(base32 || '').toUpperCase().replace(/[^A-Z2-7]/g, '');
    let bits = '';
    for (let i = 0; i < clean.length; i++) {
      const val = alphabet.indexOf(clean[i]);
      if (val === -1) continue;
      bits += val.toString(2).padStart(5, '0');
    }
    const bytes = [];
    for (let i = 0; i + 8 <= bits.length; i += 8) {
      bytes.push(parseInt(bits.substr(i, 8), 2));
    }
    return new Uint8Array(bytes);
  }

  async function generateTOTP(secret, period = 30, digits = 6) {
    if (!secret) return '';
    const keyBytes = base32ToBytes(secret);
    if (!keyBytes.length) return '';
    const epoch = Math.floor(Date.now() / 1000 / period);
    const epochBytes = new Uint8Array(8);
    let temp = epoch;
    for (let i = 7; i >= 0; i--) {
      epochBytes[i] = temp & 0xff;
      temp = Math.floor(temp / 256);
    }

    const cryptoKey = await crypto.subtle.importKey(
      'raw',
      keyBytes,
      { name: 'HMAC', hash: 'SHA-1' },
      false,
      ['sign']
    );
    const signature = await crypto.subtle.sign('HMAC', cryptoKey, epochBytes);
    const hash = new Uint8Array(signature);
    const offset = hash[hash.length - 1] & 0x0f;
    const binary =
      ((hash[offset] & 0x7f) << 24) |
      ((hash[offset + 1] & 0xff) << 16) |
      ((hash[offset + 2] & 0xff) << 8) |
      (hash[offset + 3] & 0xff);
    const otp = (binary % Math.pow(10, digits)).toString().padStart(digits, '0');
    return otp;
  }

  function parseVIAString(rawText) {
    const cookies = [];
    let uid = '';
    let password = '';
    let twoFactorSecret = '';
    let email = '';
    let mailPassword = '';
    let accessToken = '';
    let userAgent = '';

    if (!rawText || typeof rawText !== 'string') {
      return { cookies, uid, password, twoFactorSecret, email, mailPassword, accessToken, userAgent, type: 'unknown' };
    }

    let text = rawText.trim();
    // Bỏ dấu ngoặc kép bọc ngoài nếu có
    if ((text.startsWith('"') && text.endsWith('"')) || (text.startsWith("'") && text.endsWith("'"))) {
      text = text.slice(1, -1).trim();
    }

    // Nếu nhiều dòng, lấy dòng đầu tiên có nội dung (trừ khi là chuỗi JSON)
    if (text.includes('\n')) {
      const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
      if (lines.length > 0 && !text.startsWith('[') && !text.startsWith('{')) {
        text = lines[0];
      }
    }

    // 1. Kiểm tra nếu là mảng JSON cookies hoặc object có trường cookies
    if (text.startsWith('[') || text.startsWith('{')) {
      try {
        let parsed = JSON.parse(text);
        if (!Array.isArray(parsed) && parsed.cookies) parsed = parsed.cookies;
        if (Array.isArray(parsed)) {
          parsed.forEach(c => {
            if (c.name && c.value) {
              cookies.push({ name: String(c.name).trim(), value: String(c.value).trim() });
              if (String(c.name).trim().toLowerCase() === 'c_user') uid = String(c.value).trim();
            }
          });
          if (cookies.length > 0) {
            return { cookies, uid: uid || 'Facebook_User', password, twoFactorSecret, email, mailPassword, accessToken, userAgent, type: 'cookie', raw: text };
          }
        }
      } catch (e) {}
    }

    // Hàm phụ: bóc tách tất cả cookie từ 1 phân đoạn (key=val; key2=val2;)
    function extractCookiesFromSegment(seg) {
      if (!seg) return;
      const cookiePairs = seg.split(';');
      for (const pair of cookiePairs) {
        const trimmed = pair.trim();
        if (!trimmed || !trimmed.includes('=')) continue;
        const eqIdx = trimmed.indexOf('=');
        const name = trimmed.slice(0, eqIdx).trim();
        const val = trimmed.slice(eqIdx + 1).trim();
        if (name && val && !cookies.some(c => c.name.toLowerCase() === name.toLowerCase())) {
          cookies.push({ name, value: val });
          if (name.toLowerCase() === 'c_user' && !uid) {
            uid = val;
          }
        }
      }
    }

    // 2. Định dạng phân cách bởi pipe '|' hoặc tab '\t'
    const separator = text.includes('|') ? '|' : (text.includes('\t') ? '\t' : null);
    if (separator) {
      const rawParts = text.split(separator).map(p => p.trim());
      const parts = rawParts.filter(Boolean);

      // Pass 1: Nhận diện Cookie, Token EAAB, Email, UserAgent, 2FA Secret
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];

        // Đoạn chứa cookies
        if (part.includes('c_user=') || part.includes('xs=') || part.includes('datr=')) {
          extractCookiesFromSegment(part);
          continue;
        }

        // Token EAAB
        if (/^EAAA[A-Za-z0-9]+/.test(part)) {
          accessToken = part;
          continue;
        }

        // User Agent
        if (part.startsWith('Mozilla/5.0')) {
          userAgent = part;
          continue;
        }

        // Email
        if (part.includes('@') && part.includes('.') && !email) {
          email = part;
          continue;
        }

        // Mã 2FA Secret Key (Base32 độ dài 14-36 ký tự)
        const clean2FA = part.replace(/\s+/g, '');
        if (/^[A-Z2-7]{14,36}$/i.test(clean2FA) && !/^\d+$/.test(clean2FA) && clean2FA.toUpperCase() !== 'FACEBOOK') {
          if (!twoFactorSecret) {
            twoFactorSecret = clean2FA.toUpperCase();
            continue;
          }
        }
      }

      // Pass 2: Nhận diện UID và Password
      if (parts.length >= 1 && /^\d{6,24}$/.test(parts[0])) {
        uid = parts[0];
        if (parts.length >= 2) {
          const p1 = parts[1];
          if (!p1.includes('c_user=') && !p1.includes('xs=') && !p1.startsWith('EAAA') && !p1.startsWith('Mozilla/')) {
            password = p1;
          }
        }
      } else if (parts.length >= 2) {
        if (parts[0].includes('@') || /^[a-zA-Z0-9._-]{4,30}$/.test(parts[0])) {
          uid = parts[0];
          password = parts[1];
        }
      }

      // Dự phòng tìm password đứng ngay sau UID
      if (!password && uid) {
        const uidIdx = parts.indexOf(uid);
        if (uidIdx !== -1 && uidIdx + 1 < parts.length) {
          const candidate = parts[uidIdx + 1];
          if (!candidate.includes('=') && !candidate.startsWith('EAAA') && !candidate.startsWith('Mozilla/')) {
            password = candidate;
          }
        }
      }
    } else {
      // Chuỗi cookie đơn thuần
      extractCookiesFromSegment(text);
    }

    let type = 'unknown';
    const hasAuthCookie = cookies.some(c => c.name.toLowerCase() === 'c_user' || c.name.toLowerCase() === 'xs');

    if (hasAuthCookie && (uid && password)) {
      type = 'hybrid'; // Định dạng lai cực mạnh: vừa có Cookie vừa có UID/Mật khẩu
    } else if (hasAuthCookie) {
      type = 'cookie';
    } else if (uid && password) {
      type = 'credentials';
    } else if (cookies.length > 0) {
      type = 'cookie';
    } else if (accessToken) {
      type = 'token';
    }

    return { cookies, uid: uid || 'Facebook_User', password, twoFactorSecret, email, mailPassword, accessToken, userAgent, type, raw: text };
  }

  async function setSingleFBCookie(name, value) {
    if (!name || !value) return false;
    name = name.trim();
    value = value.trim();

    const isHttpOnly = ['xs', 'fr', 'datr', 'sb'].includes(name.toLowerCase());
    const expirationDate = Math.floor(Date.now() / 1000) + (365 * 86400); // 1 năm

    const attempts = [
      // 1. Chuẩn domain facebook.com (không có dấu chấm đầu)
      {
        url: 'https://www.facebook.com/',
        domain: 'facebook.com',
        path: '/',
        name,
        value,
        secure: true,
        httpOnly: isHttpOnly,
        sameSite: 'lax',
        expirationDate
      },
      // 2. Không truyền sameSite
      {
        url: 'https://www.facebook.com/',
        domain: 'facebook.com',
        path: '/',
        name,
        value,
        secure: true,
        httpOnly: isHttpOnly,
        expirationDate
      },
      // 3. Host-only trên www.facebook.com
      {
        url: 'https://www.facebook.com/',
        path: '/',
        name,
        value,
        secure: true,
        httpOnly: isHttpOnly,
        expirationDate
      },
      // 4. Cơ bản
      {
        url: 'https://facebook.com/',
        path: '/',
        name,
        value,
        secure: true
      }
    ];

    for (const details of attempts) {
      try {
        const res = await chrome.cookies.set(details);
        if (res && res.name) return true;
      } catch (e) {}
    }
    return false;
  }

  async function injectFacebookVIA(viaText) {
    const parsed = parseVIAString(viaText);
    if (!parsed.cookies.length) {
      throw new Error('Không tìm thấy cookie Facebook hợp lệ (c_user, xs...) trong chuỗi VIA.');
    }

    let injectedCount = 0;
    for (const c of parsed.cookies) {
      const ok = await setSingleFBCookie(c.name, c.value);
      if (ok) injectedCount++;
    }

    return { success: true, count: injectedCount, uid: parsed.uid || 'Facebook_User', cookies: parsed.cookies };
  }

  // Mở tab Dola mới ở trạng thái sạch / chưa có tài khoản (guest mode) để người dùng tự bấm login
  async function openDolaGuestTab(fbUid = '') {
    // 1. Chỉ dọn cookies của dola.com / doubao / byteintl (KHÔNG xóa facebook, KHÔNG đóng tab người dùng)
    try {
      const allCookies = await chrome.cookies.getAll({});
      for (const c of allCookies) {
        const dom = (c.domain || '').toLowerCase();
        if (dom.includes('dola.com') || dom.includes('doubao.com') || dom.includes('byteintl.com') || dom.includes('zijieapi.com')) {
          const protocol = c.secure ? 'https://' : 'http://';
          const cleanDom = c.domain.startsWith('.') ? c.domain.substring(1) : c.domain;
          const url = `${protocol}${cleanDom}${c.path || '/'}`;
          await chrome.cookies.remove({ url, name: c.name, storeId: c.storeId }).catch(() => {});
        }
      }
    } catch (e) {}

    // 2. Mở tab Dola mới ở chế độ khách (chưa có tài khoản)
    return new Promise((resolve) => {
      chrome.tabs.create({ url: 'https://www.dola.com/chat/create-image', active: true }, (dolaTab) => {
        if (!dolaTab || !dolaTab.id) {
          resolve(null);
          return;
        }

        const tabId = dolaTab.id;

        // Xóa sạch localStorage và sessionStorage để Dola hiển thị giao diện khách chưa có tài khoản
        const cleanGuestStorage = () => {
          chrome.scripting.executeScript({
            target: { tabId },
            func: () => {
              try {
                localStorage.clear();
                sessionStorage.clear();
              } catch (e) {}
            }
          }).catch(() => {});
        };

        const onTabUpdated = (updatedTabId, changeInfo) => {
          if (updatedTabId !== tabId) return;
          if (changeInfo.status === 'loading' || changeInfo.status === 'complete') {
            cleanGuestStorage();
          }
          if (changeInfo.status === 'complete') {
            chrome.tabs.onUpdated.removeListener(onTabUpdated);
          }
        };

        chrome.tabs.onUpdated.addListener(onTabUpdated);
        setTimeout(() => {
          chrome.tabs.onUpdated.removeListener(onTabUpdated);
        }, 20000);

        setTimeout(cleanGuestStorage, 800);

        // Tự động bật watcher theo dõi đăng nhập Dola để tự động lưu profile khi hoàn tất
        startDolaSessionWatcher(fbUid, tabId, 120);

        resolve(dolaTab);
      });
    });
  }

  // Tự động điền tài khoản, mật khẩu và mã 2FA vào trang đăng nhập Facebook
  function loginFacebookCredentials(uid, password, twoFactorSecret, startUrl = 'https://www.facebook.com/login.php') {
    return new Promise(async (resolve, reject) => {
      try {
        let totpCode = '';
        if (twoFactorSecret) {
          try {
            totpCode = await generateTOTP(twoFactorSecret);
          } catch (e) {
            console.warn('[FB VIA] Lỗi tính TOTP:', e);
          }
        }

        let dolaOpened = false;
        const triggerDolaOnce = () => {
          if (dolaOpened) return;
          dolaOpened = true;
          setTimeout(() => {
            void openDolaGuestTab(uid);
          }, 800);
        };

        chrome.tabs.create({ url: startUrl, active: true }, (tab) => {
          if (!tab || !tab.id) {
            reject(new Error('Không thể mở tab Facebook login.'));
            return;
          }

          const tabId = tab.id;

          const onUpdatedListener = (updatedTabId, changeInfo, tabObj) => {
            if (updatedTabId !== tabId) return;

            if (changeInfo.status === 'complete') {
              const currentUrl = (changeInfo.url || tabObj?.url || '').toLowerCase();

              // Nếu tab đang ở trang login hoặc checkpoint -> Tự động điền form
              if (currentUrl.includes('login') || currentUrl.includes('checkpoint')) {
                chrome.scripting.executeScript({
                  target: { tabId },
                  func: (fUid, fPass, fOtp) => {
                    try {
                      // 1. Form đăng nhập thông thường (UID / Email & Password)
                      const emailInput = document.querySelector('#email, input[name="email"], input[type="text"], input[autocomplete="username"]');
                      const passInput = document.querySelector('#pass, input[name="pass"], input[type="password"], input[autocomplete="current-password"]');
                      const loginBtn = document.querySelector('#loginbutton, button[name="login"], button[type="submit"], input[type="submit"]');

                      if (emailInput && passInput && fUid && fPass) {
                        emailInput.focus();
                        emailInput.value = fUid;
                        emailInput.dispatchEvent(new Event('input', { bubbles: true }));
                        emailInput.dispatchEvent(new Event('change', { bubbles: true }));

                        passInput.focus();
                        passInput.value = fPass;
                        passInput.dispatchEvent(new Event('input', { bubbles: true }));
                        passInput.dispatchEvent(new Event('change', { bubbles: true }));

                        setTimeout(() => {
                          if (loginBtn) loginBtn.click();
                        }, 500);
                        return { action: 'submitted_login' };
                      }

                      // 2. Form 2FA / Checkpoint
                      const codeInput = document.querySelector('#approvals_code, input[name="approvals_code"], input[autocomplete*="one-time-code"], input[type="number"], input[name*="code"]');
                      const submitCheckpoint = document.querySelector('#checkpointSubmitButton, button[type="submit"], input[type="submit"]');

                      if (codeInput && fOtp) {
                        codeInput.focus();
                        codeInput.value = fOtp;
                        codeInput.dispatchEvent(new Event('input', { bubbles: true }));
                        codeInput.dispatchEvent(new Event('change', { bubbles: true }));

                        setTimeout(() => {
                          if (submitCheckpoint) submitCheckpoint.click();
                        }, 500);
                        return { action: 'submitted_2fa' };
                      }
                    } catch (e) {
                      return { error: e.message };
                    }
                    return { action: 'none' };
                  },
                  args: [uid, password, totpCode]
                }).catch(() => {});
              } else if (currentUrl.includes('facebook.com')) {
                // Đã vào Facebook (Home feed / trang cá nhân) -> Đăng nhập xong! Mở tab Dola khách
                triggerDolaOnce();
              }
            }
          };

          chrome.tabs.onUpdated.addListener(onUpdatedListener);

          setTimeout(() => {
            chrome.tabs.onUpdated.removeListener(onUpdatedListener);
          }, 90000);

          resolve({
            success: true,
            tabId,
            uid,
            totpCode,
            message: totpCode
              ? `Đang tự động đăng nhập FB (Mã 2FA: ${totpCode}). Khi đăng nhập xong sẽ tự động mở trang Dola (chưa có tài khoản)...`
              : 'Đang tự động đăng nhập FB. Khi đăng nhập xong sẽ tự động mở trang Dola (chưa có tài khoản)...'
          });
        });
      } catch (err) {
        reject(err);
      }
    });
  }

  // Tự động bấm nút Đăng nhập -> Chọn Facebook trên trang Dola
  function triggerDolaFacebookOAuth(tabId) {
    chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        // Kiểm tra xem đã đăng nhập Dola chưa
        const checkAlreadyLoggedIn = () => {
          const avatar = document.querySelector('[class*="avatar"], [class*="user"], [class*="profile"]');
          const headerLoginBtn = document.querySelector('button[class*="login-btn-header"]');
          return (avatar && !headerLoginBtn);
        };

        if (checkAlreadyLoggedIn()) {
          console.log('[Dola FB Login] Dola đã đăng nhập sẵn!');
          return;
        }

        // Bấm nút đăng nhập trên header
        const clickHeaderLogin = () => {
          const btn = document.querySelector('button[class*="login-btn-header"]');
          if (btn) {
            btn.click();
            return true;
          }
          const allButtons = Array.from(document.querySelectorAll('button'));
          for (const b of allButtons) {
            const text = (b.innerText || '').trim().toLowerCase();
            if (text === 'đăng nhập' || text === 'sign in' || text === 'log in' || text.includes('đăng nhập')) {
              b.click();
              return true;
            }
          }
          return false;
        };

        // Bấm icon Facebook trong modal đăng nhập
        const clickFacebookIconInModal = () => {
          const fbCandidates = Array.from(document.querySelectorAll('[class*="login"], [class*="modal"], [role="dialog"], div[class*="dialog"]')).flatMap(container =>
            Array.from(container.querySelectorAll('div, button, a, svg, span'))
          );

          for (const el of fbCandidates) {
            const aria = (el.getAttribute('aria-label') || '').toLowerCase();
            const title = (el.getAttribute('title') || '').toLowerCase();
            const text = (el.innerText || '').toLowerCase();
            const cls = (el.className || '').toString().toLowerCase();

            if (aria.includes('facebook') || title.includes('facebook') || text.includes('facebook') || cls.includes('facebook') || cls.includes('fb')) {
              el.click();
              return true;
            }
          }
          return false;
        };

        // Thực thi luồng: bấm Đăng nhập -> chờ modal -> bấm Facebook
        let step = 0; // 0: click header, 1: click fb icon
        let tries = 0;

        const timer = setInterval(() => {
          tries++;
          if (tries > 40) {
            clearInterval(timer);
            return;
          }

          if (step === 0) {
            if (clickHeaderLogin()) {
              step = 1;
            }
          } else if (step === 1) {
            if (clickFacebookIconInModal()) {
              clearInterval(timer);
              console.log('[Dola FB Login] Hoàn tất kích hoạt OAuth Facebook!');
            }
          }
        }, 350);
      }
    }).catch((err) => {
      console.warn('[Dola FB Login] executeScript error:', err);
    });
  }

  // Auto-Watcher: Tự động phát hiện phiên Dola đăng nhập thành công & Lưu Cookies
  let dolaWatcherTimer = null;
  function startDolaSessionWatcher(fbUid, targetTabId, maxSeconds = 70) {
    if (dolaWatcherTimer) {
      clearInterval(dolaWatcherTimer);
      dolaWatcherTimer = null;
    }

    const startTime = Date.now();
    console.log(`[Dola Watcher] Bắt đầu theo dõi đăng nhập Dola cho UID ${fbUid || 'Auto'} trong ${maxSeconds}s...`);

    dolaWatcherTimer = setInterval(async () => {
      const elapsed = (Date.now() - startTime) / 1000;
      if (elapsed > maxSeconds) {
        clearInterval(dolaWatcherTimer);
        dolaWatcherTimer = null;
        console.log('[Dola Watcher] Hết thời gian theo dõi.');
        return;
      }

      try {
        const allCookies = await chrome.cookies.getAll({});
        const cList = allCookies.filter(c => (c.domain || '').includes('dola.com') || (c.domain || '').includes('doubao.com'));
        const hasSession = (cList || []).some(c => 
          (c.name === 'sessionid' || c.name === 'sessionid_ss' || c.name === 'uid_tt' || c.name === 'sid_tt') && Boolean(c.value)
        );

        // Chủ động quét tất cả tab/cửa sổ để tiêm autoclick vào bất kỳ popup Facebook nào
        chrome.tabs.query({}, (allTabs) => {
          (allTabs || []).forEach(t => {
            if (t.id) injectFBAutoclickIfMatching(t.id, t.url || t.pendingUrl);
          });
        });

        // Tự động bấm nút 'Xác nhận' modal tuổi 18+ trên tab Dola nếu xuất hiện
        if (targetTabId && chrome.scripting && chrome.scripting.executeScript) {
          chrome.scripting.executeScript({
            target: { tabId: targetTabId },
            func: () => {
              try {
                const modals = Array.from(document.querySelectorAll('div[role="dialog"], div[class*="modal"], div[class*="dialog"], div[class*="popup"]'));
                for (const m of modals) {
                  const txt = (m.innerText || '').toLowerCase();
                  if (txt.includes('tuổi') || txt.includes('18') || txt.includes('age') || txt.includes('xác nhận tuổi')) {
                    const btns = Array.from(m.querySelectorAll('button, div[role="button"]'));
                    for (const b of btns) {
                      const bTxt = (b.innerText || '').trim();
                      if (bTxt === 'Xác nhận' || bTxt === 'Confirm' || bTxt === 'Đồng ý') {
                        b.click();
                        return true;
                      }
                    }
                    if (btns.length >= 2) {
                      btns[btns.length - 1].click();
                      return true;
                    }
                  }
                }
              } catch (e) {}
              return false;
            }
          }).catch(() => {});
        }

        if (hasSession) {
          clearInterval(dolaWatcherTimer);
          dolaWatcherTimer = null;
          console.log('[Dola Watcher] ✅ Phát hiện phiên Dola đã đăng nhập thành công!');

          // Tự động đóng popup Facebook Consent sau khi đã có phiên
          try {
            chrome.tabs.query({}, (allTabs) => {
              (allTabs || []).forEach(t => {
                const u = (t.url || '').toLowerCase();
                if (u.includes('facebook.com') && (u.includes('consent') || u.includes('flow=gdp') || u.includes('oauth') || u.includes('1819912395072617'))) {
                  chrome.tabs.remove(t.id).catch(() => {});
                }
              });
            });
          } catch (e) {}

          // Gọi bộ trích xuất cookies
          let extractRes = null;
          if (globalThis.ChannaBulkAccountManager && typeof globalThis.ChannaBulkAccountManager.extractDolaCookiesAndSession === 'function') {
            extractRes = await globalThis.ChannaBulkAccountManager.extractDolaCookiesAndSession(targetTabId);
          } else if (self.ChannaBulkAccountManager && typeof self.ChannaBulkAccountManager.extractDolaCookiesAndSession === 'function') {
            extractRes = await self.ChannaBulkAccountManager.extractDolaCookiesAndSession(targetTabId);
          }

          if (extractRes && extractRes.success && extractRes.cookies_count > 0) {
            const profName = fbUid ? `FB_${fbUid}` : (extractRes.detected_name || `Dola_${Date.now().toString().slice(-6)}`);
            
            // Lưu vào storage extension
            chrome.storage.local.get(['multi_profiles'], async (st) => {
              const profiles = st?.multi_profiles || {};
              profiles[profName] = {
                name: profName,
                cookies: extractRes.cookies,
                local_storage: extractRes.local_storage,
                cookie_string: extractRes.cookie_string,
                fb_uid: fbUid || extractRes.fb_uid,
                dola_uid: extractRes.dola_uid,
                color: '#2563eb',
                updated_at: Date.now()
              };
              await chrome.storage.local.set({
                multi_profiles: profiles,
                active_profile_name: profName
              });
              console.log(`[Dola Watcher] Đã lưu ${extractRes.cookies_count} cookies vào profile '${profName}'!`);
            });

            // Gửi thông báo Chrome
            try {
              chrome.notifications.create({
                type: 'basic',
                iconUrl: 'icon128.png',
                title: '🎉 Đã Tự Động Lưu Cookies Dola!',
                message: `Tài khoản ${profName} đã đăng nhập Dola thành công (${extractRes.cookies_count} cookies).`,
                priority: 2
              });
            } catch (e) {}

            // Đồng bộ trực tiếp sang Desktop Tool 8899 nếu có
            try {
              fetch('http://127.0.0.1:8899/api/accounts/save-dola-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  account_name: profName,
                  cookies: extractRes.cookies,
                  local_storage: extractRes.local_storage,
                  cookie_string: extractRes.cookie_string,
                  fb_uid: fbUid || extractRes.fb_uid
                })
              }).then(r => r.json()).then(res => {
                console.log('[Dola Watcher] Đồng bộ Tool 8899 thành công:', res);
              }).catch(() => {
                console.log('[Dola Watcher] Tool 8899 chưa mở (đã lưu an toàn trong Extension).');
              });
            } catch (e) {}
          }
        }
      } catch (err) {
        console.warn('[Dola Watcher] Lỗi kiểm tra cookie:', err);
      }
    }, 2000);
  }

  // Background runtime listeners
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message) return false;

    if (message.action === 'AUTO_LOGIN_VIA_FB') {
      const viaText = message.viaText;

      (async () => {
        try {
          const parsed = parseVIAString(viaText);
          if (parsed.type === 'unknown') {
            throw new Error('Định dạng VIA không hợp lệ! Vui lòng nhập UID|Pass|2FA hoặc Cookie hoặc chuỗi VIA chuẩn.');
          }

          // Case 1: Đăng nhập bằng Cookie Facebook đơn thuần
          if (parsed.type === 'cookie') {
            let injectedCount = 0;
            for (const c of parsed.cookies) {
              const ok = await setSingleFBCookie(c.name, c.value);
              if (ok) injectedCount++;
            }

            // 1. Mở tab Facebook ngầm (active: false) để trình duyệt thiết lập phiên Facebook
            chrome.tabs.create({ url: 'https://www.facebook.com/', active: false });

            // 2. Mở tab Dola mới (chưa có tài khoản) làm tab active ở tiền cảnh để người dùng bấm login
            await openDolaGuestTab(parsed.uid);

            sendResponse({
              success: true,
              mode: 'cookie',
              uid: parsed.uid || 'Facebook_User',
              count: injectedCount,
              message: `Đã nạp ${injectedCount} Cookie VIA Facebook & Đã mở tab Dola (chưa có tài khoản) thành công! Bạn hãy bấm Đăng nhập bằng Facebook trên Dola.`
            });
            return;
          }

          // Case 2: Đăng nhập Hybrid (vừa có Cookie vừa có UID/Pass)
          if (parsed.type === 'hybrid') {
            let injectedCount = 0;
            for (const c of parsed.cookies) {
              const ok = await setSingleFBCookie(c.name, c.value);
              if (ok) injectedCount++;
            }

            // Mở tab Facebook với URL trang chủ; nếu cookie hoạt động -> vào thẳng, nếu cần pass -> tự điền
            const res = await loginFacebookCredentials(
              parsed.uid,
              parsed.password,
              parsed.twoFactorSecret,
              'https://www.facebook.com/'
            );

            sendResponse({
              success: true,
              mode: 'hybrid',
              uid: parsed.uid,
              count: injectedCount,
              totpCode: res.totpCode,
              message: `Đã nạp ${injectedCount} Cookie FB & Tự động đăng nhập FB [UID: ${parsed.uid}]. Đang mở trang Dola (chưa có tài khoản)...`
            });
            return;
          }

          // Case 3: Đăng nhập bằng tài khoản UID/Email & Password (và 2FA nếu có)
          if (parsed.type === 'credentials') {
            const res = await loginFacebookCredentials(
              parsed.uid,
              parsed.password,
              parsed.twoFactorSecret,
              'https://www.facebook.com/login.php'
            );
            sendResponse({
              success: true,
              mode: 'credentials',
              uid: parsed.uid,
              totpCode: res.totpCode,
              message: res.message
            });
            return;
          }
        } catch (err) {
          sendResponse({ success: false, error: err.message || String(err) });
        }
      })();

      return true;
    }

    if (message.action === 'START_DOLA_LOGIN_WATCHER') {
      startDolaSessionWatcher(message.fbUid, message.tabId, message.maxSeconds || 60);
      sendResponse({ success: true });
      return true;
    }

    if (message.action === 'PARSE_VIA_STRING') {
      const parsed = parseVIAString(message.viaText);
      sendResponse(parsed);
      return true;
    }
  });

  // Hàm kiểm tra và tiêm script tự động xác nhận Facebook Consent đa quốc gia
  function injectFBAutoclickIfMatching(tabId, url) {
    if (!url) return;
    const lowerUrl = url.toLowerCase();
    if (
      lowerUrl.includes('facebook.com/privacy/consent') ||
      (lowerUrl.includes('facebook.com') && (
        lowerUrl.includes('flow=gdp') ||
        lowerUrl.includes('/dialog/') ||
        lowerUrl.includes('oauth') ||
        lowerUrl.includes('1819912395072617')
      ))
    ) {
      if (chrome.scripting && chrome.scripting.executeScript) {
        chrome.scripting.executeScript({
          target: { tabId, allFrames: true },
          files: ['fb_popup_autoclick.js']
        }).catch(() => {});
      }
    }
  }

  // Bắt ngay khi tab hoặc popup Facebook Consent vừa được tạo
  chrome.tabs.onCreated.addListener((tab) => {
    if (tab && tab.id) {
      injectFBAutoclickIfMatching(tab.id, tab.url || tab.pendingUrl);
    }
  });

  // Bắt khi URL tab thay đổi hoặc chuyển hướng tới Facebook Consent
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    injectFBAutoclickIfMatching(tabId, changeInfo.url || tab?.url);
  });

  globalThis.FacebookVIAManager = {
    parseVIAString,
    injectFacebookVIA,
    generateTOTP,
    loginFacebookCredentials,
    openDolaGuestTab,
    triggerDolaFacebookOAuth,
    startDolaSessionWatcher
  };

})();
