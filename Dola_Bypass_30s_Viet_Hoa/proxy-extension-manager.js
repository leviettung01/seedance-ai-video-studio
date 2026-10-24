/* ============================================================================
   DOLA 30S STUDIO PRO - PROXY EXTENSION MANAGER
   Tác giả & Bản quyền: LÊ VIỆT TÙNG | Zalo / Hotline: 0915967790
   Quản lý Proxy VPN độc lập cho từng profile Chrome (cả chạy thủ công lẫn chạy qua Tool)
   Hỗ trợ HTTP / SOCKS5, tự động xác thực Basic Auth (admin:admin123), bypass local APIs.
   ============================================================================ */

(() => {
  'use strict';

  // 1. Áp dụng Proxy cho Profile Chrome hiện tại
  function applyExtensionProxy(config, callback) {
    if (!chrome.proxy || !chrome.proxy.settings) {
      console.warn('[Dola Proxy] chrome.proxy API không khả dụng.');
      if (callback) callback({ ok: false, error: 'chrome.proxy API not available' });
      return;
    }

    if (!config || !config.enabled) {
      clearExtensionProxy(callback);
      return;
    }

    const host = String(config.host || '127.0.0.1').trim();
    const port = parseInt(config.port, 10) || 10000;
    const scheme = String(config.scheme || 'http').toLowerCase();
    const username = String(config.username || config.user || '').trim();
    const password = String(config.password || config.pass || '').trim();

    const proxyConfig = {
      mode: 'fixed_servers',
      rules: {
        singleProxy: {
          scheme: scheme.includes('socks') ? 'socks5' : 'http',
          host: host,
          port: port
        },
        // Không đi qua proxy đối với localhost & API tool Seedance / OCProxy
        bypassList: [
          'localhost',
          '127.0.0.1',
          '127.0.0.1:8899',
          '127.0.0.1:9090'
        ]
      }
    };

    chrome.proxy.settings.set(
      { value: proxyConfig, scope: 'regular' },
      () => {
        const lastErr = chrome.runtime.lastError;
        if (lastErr) {
          console.error('[Dola Proxy] Lỗi cài đặt proxy:', lastErr);
          if (callback) callback({ ok: false, error: lastErr.message });
          return;
        }

        const toSave = {
          enabled: true,
          scheme: scheme,
          host: host,
          port: port,
          username: username,
          password: password,
          raw_proxy: config.raw_proxy || `${host}:${port}:${username}:${password}`,
          account_name: config.account_name || '',
          source: config.source === 'vpn_tool' ? 'vpn_tool' : 'custom',
          updated_at: Date.now()
        };

        chrome.storage.local.set({
          dola_proxy_config: toSave,
          dola_proxy_enabled: true,
          dola_proxy_auth: { username, password }
        }, () => {
          console.log(`[Dola Proxy] ✅ Đã kích hoạt Proxy [${scheme}://${host}:${port}] cho profile này.`);
          if (callback) callback({ ok: true, config: toSave });
        });
      }
    );
  }

  // 2. Xóa Proxy và quay về mạng trực tiếp (Direct)
  function clearExtensionProxy(callback) {
    if (!chrome.proxy || !chrome.proxy.settings) {
      if (callback) callback({ ok: true });
      return;
    }

    chrome.proxy.settings.set({ value: { mode: 'direct' }, scope: 'regular' }, () => {
      chrome.storage.local.set({
        dola_proxy_enabled: false,
        dola_proxy_config: { enabled: false }
      }, () => {
        console.log('[Dola Proxy] ⚪ Đã tắt proxy, quay về mạng trực tiếp.');
        if (callback) callback({ ok: true, cleared: true });
      });
    });
  }

  // 3. Đăng ký Listener tự động xác thực Basic Auth (Không bao giờ hiện popup HTTP 407)
  if (chrome.webRequest && chrome.webRequest.onAuthRequired) {
    try {
      chrome.webRequest.onAuthRequired.addListener(
        (details, asyncCallback) => {
          if (!details.isProxy) {
            asyncCallback({});
            return;
          }

          chrome.storage.local.get(['dola_proxy_config', 'dola_proxy_auth', 'dola_proxy_enabled'], (res) => {
            if (!res || !res.dola_proxy_enabled) {
              asyncCallback({});
              return;
            }

            const auth = res.dola_proxy_auth || res.dola_proxy_config;
            const u = (auth && auth.username) ? String(auth.username).trim() : 'admin';
            const p = (auth && auth.password) ? String(auth.password).trim() : 'admin123';

            if (u) {
              console.log(`[Dola Proxy] 🔐 Tự động cung cấp xác thực Proxy cho ${details.challenger?.host || 'Proxy'}: user=${u}`);
              asyncCallback({
                authCredentials: {
                  username: u,
                  password: p
                }
              });
            } else {
              asyncCallback({});
            }
          });
        },
        { urls: ['<all_urls>'] },
        ['asyncBlocking']
      );
      console.log('[Dola Proxy] ✅ Đã đăng ký tự động xác thực Proxy (webRequest.onAuthRequired asyncBlocking)');
    } catch (err) {
      console.warn('[Dola Proxy] Đăng ký asyncBlocking không thành công, thử blocking sync:', err);
    }
  }

  // 4. Tự động phục hồi cấu hình Proxy khi khởi động Chrome
  chrome.storage.local.get(['dola_proxy_config', 'dola_proxy_enabled'], (res) => {
    if (res && res.dola_proxy_enabled && res.dola_proxy_config) {
      console.log('[Dola Proxy] Tự động nạp proxy đã lưu:', res.dola_proxy_config.host, res.dola_proxy_config.port);
      applyExtensionProxy(res.dola_proxy_config);
    } else if (res && res.dola_proxy_enabled === false) {
      clearExtensionProxy();
    }
  });

  // 5. Message Bus điều khiển từ Popup & Content Scripts
  // MV3 workers sleep when the popup closes. Alarms renew a lease, while
  // the hub alone owns the 300-second rotation clock for each port.
  const rotationAlarm = 'dola-vpn2proxy-rotation-lease';
  let rotationQueue = Promise.resolve();
  function syncRotationLease() {
    rotationQueue = rotationQueue.catch(() => {}).then(async () => {
      const saved = await chrome.storage.local.get([
        'dola_proxy_config', 'dola_proxy_enabled', 'dola_vpn_auto_rotate', 'dola_rotation_client_id'
      ]);
      let id = saved.dola_rotation_client_id;
      if (!id) {
        id = `dola-${crypto.randomUUID()}`;
        await chrome.storage.local.set({ dola_rotation_client_id: id });
      }
      const cfg = saved.dola_proxy_config || {};
      const enabled = !!saved.dola_proxy_enabled && cfg.source === 'vpn_tool' &&
        saved.dola_vpn_auto_rotate !== false && ['127.0.0.1', 'localhost', '::1'].includes(cfg.host);
      try {
        const response = await fetch('http://127.0.0.1:9090/api/rotation/client', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ client_id: id, enabled, ports: enabled ? [Number(cfg.port)] : [] }),
          signal: AbortSignal.timeout(4000), cache: 'no-store'
        });
        if (!response.ok) throw new Error('hub_offline');
        const data = await response.json();
        if (!data.success) throw new Error('hub_rejected');
        await chrome.storage.local.set({ dola_rotation_status: {
          enabled, success: true, updated_at: Date.now(), interval_seconds: 300,
          ports: (data.ports || []).filter(p => p.port === Number(cfg.port))
        }});
      } catch (_) {
        await chrome.storage.local.set({ dola_rotation_status: {
          enabled, success: false, updated_at: Date.now(),
          error: 'VPN2Proxy chưa chạy hoặc cần mở lại để nạp chức năng xoay IP.'
        }});
      }
    });
    return rotationQueue;
  }
  if (chrome.alarms) {
    const ensureAlarm = () => {
      chrome.alarms.create(rotationAlarm, { periodInMinutes: 1 });
      syncRotationLease();
    };
    chrome.alarms.onAlarm.addListener(alarm => {
      if (alarm.name === rotationAlarm) syncRotationLease();
    });
    chrome.runtime.onStartup.addListener(ensureAlarm);
    chrome.runtime.onInstalled.addListener(ensureAlarm);
    ensureAlarm();
  }
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && ['dola_proxy_config', 'dola_proxy_enabled', 'dola_vpn_auto_rotate'].some(k => k in changes)) {
      syncRotationLease();
    }
  });
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || !message.action) return false;

    // A. Lấy cấu hình proxy hiện tại
    if (message.action === 'GET_EXTENSION_PROXY') {
      chrome.storage.local.get(['dola_proxy_config', 'dola_proxy_enabled'], (res) => {
        chrome.proxy?.settings?.get({ incognito: false }, (details) => {
          sendResponse({
            ok: true,
            enabled: !!res?.dola_proxy_enabled,
            config: res?.dola_proxy_config || null,
            chromeProxyDetails: details || null
          });
        });
      });
      return true;
    }

    // B. Áp dụng cấu hình proxy
    if (message.action === 'SET_EXTENSION_PROXY') {
      applyExtensionProxy(message.config, (result) => {
        sendResponse(result);
      });
      return true;
    }

    // C. Tắt proxy
    if (message.action === 'CLEAR_EXTENSION_PROXY') {
      clearExtensionProxy((result) => {
        sendResponse(result);
      });
      return true;
    }

    // D. Test kết nối IP thực tế từ background
    if (message.action === 'TEST_PROXY_IP') {
      const startTime = Date.now();
      fetch('https://api.ipify.org?format=json', { cache: 'no-store' })
        .then((r) => r.json())
        .then((data) => {
          const latency = Date.now() - startTime;
          sendResponse({ ok: true, ip: data.ip, latency });
        })
        .catch((err) => {
          // Fallback sang ipinfo.io
          fetch('https://ipinfo.io/json', { cache: 'no-store' })
            .then((r) => r.json())
            .then((data) => {
              const latency = Date.now() - startTime;
              sendResponse({
                ok: true,
                ip: data.ip,
                country: data.country,
                city: data.city,
                latency
              });
            })
            .catch((e2) => {
              sendResponse({ ok: false, error: err.message || String(e2) });
            });
        });
      return true;
    }

    return false;
  });

  // Xuất các hàm ra phạm vi global để background script có thể gọi trực tiếp
  self.applyExtensionProxy = applyExtensionProxy;
  self.clearExtensionProxy = clearExtensionProxy;
})();

