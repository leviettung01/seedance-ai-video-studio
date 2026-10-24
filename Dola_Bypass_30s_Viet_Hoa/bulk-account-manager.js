/* ============================================================================
   DOLA 30S STUDIO PRO - BULK ACCOUNT MANAGER & TAB SESSION ISOLATOR
   Tác giả & Bản quyền: LÊ VIỆT TÙNG | Zalo / Hotline: 0915967790
   ============================================================================ */

(function () {
    'use strict';

    const PROFILE_STORAGE_KEY = 'multi_profiles';
    const QUEUE_STORAGE_KEY = 'bulk_account_queue';
    const USAGE_STORAGE_KEY = 'bulk_account_tab_usage';
    const DOLA_CHAT_URL = 'https://www.dola.com/chat/create-image';

    let queueOperation = Promise.resolve();
    let bulkOpenInProgress = false;
    const tabSessionMap = new Map();

    function runInQueue(task) {
        const operation = queueOperation.then(task, task);
        queueOperation = operation.catch(() => undefined);
        return operation;
    }

    function storageGet(keys) {
        return new Promise((resolve, reject) => {
            chrome.storage.local.get(keys, (result) => {
                const error = chrome.runtime.lastError;
                if (error) {
                    reject(new Error(error.message));
                    return;
                }
                resolve(result || {});
            });
        });
    }

    function storageSet(values) {
        return new Promise((resolve, reject) => {
            chrome.storage.local.set(values, () => {
                const error = chrome.runtime.lastError;
                if (error) {
                    reject(new Error(error.message));
                    return;
                }
                resolve();
            });
        });
    }

    function tabsCreate(options) {
        return new Promise((resolve, reject) => {
            chrome.tabs.create(options, (tab) => {
                const error = chrome.runtime.lastError;
                if (error) {
                    reject(new Error(error.message));
                    return;
                }
                if (!tab || !Number.isInteger(tab.id)) {
                    reject(new Error('Chrome did not return a valid tab.'));
                    return;
                }
                resolve(tab);
            });
        });
    }

    function tabsUpdate(tabId, options) {
        return new Promise((resolve, reject) => {
            chrome.tabs.update(tabId, options, (tab) => {
                const error = chrome.runtime.lastError;
                if (error) {
                    reject(new Error(error.message));
                    return;
                }
                resolve(tab);
            });
        });
    }

    function tabsRemove(tabId) {
        return new Promise((resolve) => {
            chrome.tabs.remove(tabId, () => {
                void chrome.runtime.lastError;
                resolve();
            });
        });
    }

    // =========================================================================
    // SESSION ISOLATION & COOKIE ENGINE
    // =========================================================================
    function buildCookieHeader(cookies) {
        if (!Array.isArray(cookies)) return '';
        return cookies
            .filter(c => c && c.name && c.value !== undefined)
            .map(c => `${c.name}=${c.value}`)
            .join('; ');
    }

    async function applyTabSessionRule(tabId, profile) {
        if (!tabId || !profile || !Array.isArray(profile.cookies)) return;

        const cookieHeaderString = buildCookieHeader(profile.cookies);

        tabSessionMap.set(tabId, {
            profileName: profile.name || 'Tài khoản',
            cookies: profile.cookies,
            cookieHeaderString,
            color: profile.color || '#3b82f6'
        });

        if (chrome.declarativeNetRequest && chrome.declarativeNetRequest.updateSessionRules) {
            const ruleIdsToRemove = [tabId, tabId + 100000, tabId + 200000, tabId + 300000, tabId + 400000];
            const filterDomains = ['||dola.com', '||doubao.com', '||zijieapi.com', '||byteoversea.com', '||bytedance.com'];
            
            const newRules = filterDomains.map((domainPattern, idx) => ({
                id: tabId + (idx * 100000),
                priority: 1000,
                action: {
                    type: 'modifyHeaders',
                    requestHeaders: [
                        {
                            header: 'Cookie',
                            operation: 'set',
                            value: cookieHeaderString
                        }
                    ]
                },
                condition: {
                    tabIds: [tabId],
                    urlFilter: domainPattern,
                    resourceTypes: ['main_frame', 'sub_frame', 'stylesheet', 'script', 'image', 'font', 'object', 'xmlhttprequest', 'ping', 'csp_report', 'media', 'websocket', 'other']
                }
            }));

            try {
                await chrome.declarativeNetRequest.updateSessionRules({
                    removeRuleIds: ruleIdsToRemove,
                    addRules: newRules
                });
            } catch (err) {
                console.warn('[Session Rule] DeclarativeNetRequest error:', err);
            }
        }
    }

    async function setDolaCookies(cookies) {
        if (!Array.isArray(cookies) || cookies.length === 0) return;
        const now = Math.floor(Date.now() / 1000);
        for (const c of cookies) {
            if (!c || !c.name) continue;
            let rawDomain = String(c.domain || 'dola.com').trim();
            const isHostOnly = !rawDomain.startsWith('.');
            const cleanDomain = rawDomain.startsWith('.') ? rawDomain.substring(1) : rawDomain;
            const isSecure = c.secure !== undefined ? Boolean(c.secure) : true;
            const protocol = isSecure ? 'https://' : 'http://';
            const path = c.path || '/';
            const url = `${protocol}${cleanDomain.startsWith('www.') ? cleanDomain : 'www.' + cleanDomain}${path}`;

            const cookieData = {
                url,
                name: String(c.name).trim(),
                value: String(c.value !== undefined ? c.value : ''),
                path,
                secure: isSecure,
                httpOnly: c.httpOnly !== undefined ? Boolean(c.httpOnly) : false,
                sameSite: c.sameSite || 'no_restriction',
                expirationDate: c.expirationDate && c.expirationDate > now ? Math.floor(c.expirationDate) : (now + 365 * 86400)
            };

            if (!isHostOnly && rawDomain.startsWith('.')) {
                cookieData.domain = rawDomain;
            }

            try {
                await chrome.cookies.set(cookieData);
            } catch (e) {
                try {
                    delete cookieData.domain;
                    await chrome.cookies.set(cookieData);
                } catch (err) {}
            }
        }
    }

    async function clearAllDolaCookies() {
        const domains = ['dola.com', '.dola.com', 'doubao.com', '.doubao.com', 'seaart.ai', '.seaart.ai'];
        for (const domain of domains) {
            try {
                const cookies = await chrome.cookies.getAll({ domain });
                for (const c of cookies) {
                    const url = `${c.secure ? 'https://' : 'http://'}${c.domain.startsWith('.') ? c.domain.substring(1) : c.domain}${c.path || '/'}`;
                    await chrome.cookies.remove({ url, name: c.name }).catch(() => {});
                }
            } catch (e) {}
        }
    }

    // Clean up rules when a tab is closed
    chrome.tabs.onRemoved.addListener((tabId) => {
        if (tabSessionMap.has(tabId)) {
            tabSessionMap.delete(tabId);
            if (chrome.declarativeNetRequest && chrome.declarativeNetRequest.updateSessionRules) {
                chrome.declarativeNetRequest.updateSessionRules({
                    removeRuleIds: [tabId, tabId + 100000, tabId + 200000, tabId + 300000, tabId + 400000]
                }).catch(() => {});
            }
        }
    });

    // =========================================================================
    // MULTI-ACCOUNT WORKFLOW (1 Account = 1 Tab)
    // =========================================================================
    function normalizeQueue(profiles, storedQueue) {
        const profileNames = Object.keys(profiles || {});
        const validNames = new Set(profileNames);
        const seen = new Set();
        const existing = Array.isArray(storedQueue)
            ? storedQueue.filter(name => {
                if (typeof name !== 'string' || !validNames.has(name) || seen.has(name)) {
                    return false;
                }
                seen.add(name);
                return true;
            })
            : [];

        const newNames = profileNames.filter(name => !seen.has(name));
        return [...newNames, ...existing];
    }

    function moveNamesToBottom(queue, usedNames) {
        const used = new Set(usedNames);
        return [
            ...queue.filter(name => !used.has(name)),
            ...queue.filter(name => used.has(name))
        ];
    }

    function usableProfile(profile) {
        return Boolean(profile && Array.isArray(profile.cookies) && profile.cookies.length > 0);
    }

    // Open EXACTLY ONE tab for one account
    async function openSingleIsolatedTab(profileName, profile, shouldActivate = false) {
        const isolatedProfile = profile.name
            ? profile
            : Object.assign({}, profile, { name: profileName });

        // 1. Create a fresh tab
        const tab = await tabsCreate({ url: 'about:blank', active: shouldActivate });

        try {
            // 2. Set Session Rule for this tabId
            await applyTabSessionRule(tab.id, isolatedProfile);

            // 3. Inject cookies
            await setDolaCookies(isolatedProfile.cookies);

            // 4. Navigate directly to Dola Studio
            await tabsUpdate(tab.id, { url: DOLA_CHAT_URL, active: shouldActivate });
            return tab.id;
        } catch (error) {
            console.warn('[Bulk Manager] Error configuring isolated tab:', error);
            try {
                await tabsUpdate(tab.id, { url: DOLA_CHAT_URL, active: shouldActivate });
                return tab.id;
            } catch (navErr) {
                await tabsRemove(tab.id);
                throw error;
            }
        }
    }

    // Open N distinct accounts (1 tab per account)
    async function openMultipleAccounts(rawCount) {
        const inputNum = Number(rawCount);
        if (!Number.isInteger(inputNum) || inputNum < 1) {
            return {
                success: false,
                error: 'Vui lòng nhập số nguyên lớn hơn 0.',
                opened: [],
                failed: []
            };
        }

        const stored = await storageGet([PROFILE_STORAGE_KEY, QUEUE_STORAGE_KEY]);
        const profiles = stored[PROFILE_STORAGE_KEY] || {};
        const queue = normalizeQueue(profiles, stored[QUEUE_STORAGE_KEY]);
        const usableNames = queue.filter(name => usableProfile(profiles[name]));

        if (usableNames.length === 0) {
            return {
                success: false,
                error: 'Chưa có tài khoản nào được lưu cookies.',
                opened: [],
                failed: [],
                available: 0
            };
        }

        const countToOpen = Math.min(inputNum, usableNames.length);
        const targetAccounts = usableNames.slice(0, countToOpen);
        const opened = [];
        const failed = [];

        for (let i = 0; i < targetAccounts.length; i++) {
            const profileName = targetAccounts[i];
            const profile = profiles[profileName];
            const isFirstTab = i === 0;

            try {
                const tabId = await openSingleIsolatedTab(profileName, profile, isFirstTab);
                opened.push({ profileName, tabId });
            } catch (err) {
                failed.push({
                    profileName,
                    error: err?.message || String(err)
                });
            }
        }

        // Move used accounts to the bottom of the queue
        const usedNames = opened.map(o => o.profileName);
        const nextQueue = moveNamesToBottom(queue, usedNames);

        await storageSet({
            [QUEUE_STORAGE_KEY]: nextQueue,
            active_profile_name: usedNames.length ? usedNames[usedNames.length - 1] : undefined
        });

        return {
            success: opened.length > 0,
            requested: inputNum,
            opened,
            failed,
            available: usableNames.length,
            totalTabsOpened: opened.length,
            queue: nextQueue,
            error: opened.length > 0 ? null : 'Không thể mở tab nào.'
        };
    }

    // =========================================================================
    // DOLA COOKIE & SESSION EXTRACTION ENGINE
    // =========================================================================
    async function extractDolaCookiesAndSession(specifiedTabId) {
        // 1. Find target tab
        let targetTab = null;
        if (specifiedTabId && specifiedTabId !== 'auto' && specifiedTabId !== 'active') {
            try {
                targetTab = await new Promise(res => {
                    chrome.tabs.get(Number(specifiedTabId), t => res(chrome.runtime.lastError ? null : t));
                });
            } catch (e) {}
        }
        if (!targetTab || !targetTab.url || (!targetTab.url.includes('dola.com') && !targetTab.url.includes('doubao.com'))) {
            // Check active tab in current window
            const activeTabs = await new Promise(res => chrome.tabs.query({ active: true, currentWindow: true }, res));
            if (activeTabs && activeTabs[0] && activeTabs[0].url && (activeTabs[0].url.includes('dola.com') || activeTabs[0].url.includes('doubao.com'))) {
                targetTab = activeTabs[0];
            } else {
                // Query all Dola tabs across all windows
                const dolaTabs = await new Promise(res => chrome.tabs.query({
                    url: ['*://*.dola.com/*', '*://*.doubao.com/*', '*://dola.com/*', '*://doubao.com/*']
                }, res));
                if (dolaTabs && dolaTabs.length > 0) {
                    targetTab = dolaTabs[0];
                }
            }
        }

        // 2. Query all relevant domain cookies
        const domains = [
            'dola.com', '.dola.com', 'www.dola.com',
            'doubao.com', '.doubao.com', 'www.doubao.com',
            'byteintl.com', '.byteintl.com',
            'zijieapi.com', '.zijieapi.com',
            'facebook.com', '.facebook.com'
        ];

        const cookiePromises = domains.map(domain => new Promise(res => {
            chrome.cookies.getAll({ domain }, list => {
                res(Array.isArray(list) ? list : []);
            });
        }));
        const cookieResults = await Promise.all(cookiePromises);
        const allCookies = cookieResults.flat();

        const uniqueMap = new Map();
        let fbUid = '';
        let dolaUid = '';
        let sessionId = '';

        for (const c of allCookies) {
            if (!c || !c.name) continue;
            const key = `${c.name}@${c.domain || ''}@${c.path || '/'}`;
            if (!uniqueMap.has(key)) {
                uniqueMap.set(key, c);
            }
            const lname = c.name.toLowerCase();
            if (lname === 'c_user' && c.value) fbUid = c.value;
            if ((lname === 'uid_tt' || lname === 'uid_tt_ss') && c.value) dolaUid = c.value;
            if ((lname === 'sessionid' || lname === 'sessionid_ss' || lname === 'sid_tt') && c.value) sessionId = c.value;
        }

        const cleanCookies = Array.from(uniqueMap.values());
        const cookieHeaderString = cleanCookies
            .filter(c => c && c.name && c.value !== undefined)
            .map(c => `${c.name}=${c.value}`)
            .join('; ');

        // 3. Extract localStorage and DOM details if tab is available
        let localStorageData = {};
        let domUserName = '';
        let domAvatar = '';

        if (targetTab && targetTab.id) {
            try {
                const execResults = await chrome.scripting.executeScript({
                    target: { tabId: targetTab.id },
                    func: () => {
                        const ls = {};
                        try {
                            for (let i = 0; i < localStorage.length; i++) {
                                const k = localStorage.key(i);
                                if (k) ls[k] = localStorage.getItem(k);
                            }
                        } catch (e) {}

                        let name = '';
                        let avatar = '';
                        try {
                            const nameEl = document.querySelector('[class*="user-name"], [class*="nickname"], [class*="profile-name"], [class*="avatar-name"]');
                            if (nameEl) name = nameEl.innerText || nameEl.textContent || '';
                            const avatarEl = document.querySelector('img[class*="avatar"], [class*="profile"] img, [class*="user"] img');
                            if (avatarEl) avatar = avatarEl.src || '';
                        } catch (e) {}

                        return { ls, name: name.trim(), avatar: avatar.trim() };
                    }
                });

                if (execResults && execResults[0] && execResults[0].result) {
                    localStorageData = execResults[0].result.ls || {};
                    domUserName = execResults[0].result.name || '';
                    domAvatar = execResults[0].result.avatar || '';
                }
            } catch (err) {
                console.warn('[Bulk Manager] executeScript localStorage error:', err);
            }
        }

        // 4. Auto detect account name
        let detectedName = '';
        if (fbUid) {
            detectedName = `FB_${fbUid}`;
        } else if (dolaUid) {
            detectedName = `Dola_${dolaUid}`;
        } else if (domUserName) {
            detectedName = `Dola_${domUserName.replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1EA0-\u1EF9]/g, '_')}`;
        } else if (targetTab && targetTab.title) {
            const cleanTitle = targetTab.title.replace(/[\r\n\t\-–—|]/g, ' ').trim().slice(0, 20).replace(/\s+/g, '_');
            detectedName = `Dola_${cleanTitle}`;
        } else {
            detectedName = `Dola_${Date.now().toString().slice(-6)}`;
        }

        const isLoggedIn = Boolean(sessionId || (dolaUid && dolaUid.length > 3));

        return {
            success: true,
            cookies: cleanCookies,
            cookies_count: cleanCookies.length,
            cookie_string: cookieHeaderString,
            local_storage: localStorageData,
            ls_count: Object.keys(localStorageData).length,
            detected_name: detectedName,
            fb_uid: fbUid,
            dola_uid: dolaUid,
            session_id: sessionId,
            is_logged_in: isLoggedIn,
            tab_id: targetTab ? targetTab.id : null,
            tab_title: targetTab ? targetTab.title : '',
            tab_url: targetTab ? targetTab.url : ''
        };
    }

    // =========================================================================
    // RUNTIME MESSAGE ROUTER
    // =========================================================================
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (!request || typeof request.action !== 'string') return undefined;

        // 1. Open multiple accounts: 1 tab per account
        if (request.action === 'open_multiple_accounts') {
            if (bulkOpenInProgress) {
                sendResponse({
                    success: false,
                    error: 'Đang mở các tab tài khoản, vui lòng đợi...',
                    opened: [],
                    failed: []
                });
                return undefined;
            }

            bulkOpenInProgress = true;
            runInQueue(() => openMultipleAccounts(request.count))
                .then((result) => {
                    bulkOpenInProgress = false;
                    sendResponse(result);
                })
                .catch((error) => {
                    bulkOpenInProgress = false;
                    sendResponse({
                        success: false,
                        error: error?.message || String(error),
                        opened: [],
                        failed: []
                    });
                });

            return true;
        }

        // 2. Open 1 specific account in a new tab (Button 🌐)
        if (request.action === 'open_account_in_new_tab') {
            const profileName = request.profileName;
            storageGet([PROFILE_STORAGE_KEY]).then((stored) => {
                const profiles = stored[PROFILE_STORAGE_KEY] || {};
                const profile = profiles[profileName];
                if (!profile || !usableProfile(profile)) {
                    sendResponse({ success: false, error: 'Không tìm thấy dữ liệu cookies cho tài khoản này.' });
                    return;
                }
                openSingleIsolatedTab(profileName, profile, true).then((tabId) => {
                    sendResponse({ success: true, tabId });
                }).catch((err) => {
                    sendResponse({ success: false, error: err?.message || String(err) });
                });
            });
            return true;
        }

        // 3. Switch active profile (Button 🔄)
        if (request.action === 'switch_profile') {
            const profileName = request.profileName;
            storageGet([PROFILE_STORAGE_KEY]).then(async (stored) => {
                const profiles = stored[PROFILE_STORAGE_KEY] || {};
                const profile = profiles[profileName];
                if (!profile || !usableProfile(profile)) {
                    sendResponse({ success: false, error: 'Không tìm thấy cookies cho tài khoản này.' });
                    return;
                }
                try {
                    await clearAllDolaCookies();
                    await setDolaCookies(profile.cookies);
                    await storageSet({ active_profile_name: profileName });

                    // Reload current active Dola tab
                    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                        if (tabs && tabs[0] && tabs[0].url && (tabs[0].url.includes('dola.com') || tabs[0].url.includes('doubao.com'))) {
                            chrome.tabs.reload(tabs[0].id);
                        }
                    });

                    sendResponse({ success: true, profileName });
                } catch (err) {
                    sendResponse({ success: false, error: err?.message || String(err) });
                }
            });
            return true;
        }

        // 4. Get session assigned to a tab
        if (request.action === 'get_current_session' || request.action === 'get_tab_session') {
            const tabId = sender.tab ? sender.tab.id : (request.tabId || null);
            if (tabId && tabSessionMap.has(tabId)) {
                sendResponse({
                    isolated: true,
                    session: tabSessionMap.get(tabId)
                });
            } else {
                storageGet(['active_profile_name']).then((stored) => {
                    sendResponse({
                        isolated: false,
                        session: {
                            profileName: stored.active_profile_name || 'Mặc định',
                            color: '#10b981'
                        }
                    });
                });
            }
            return true;
        }

        // 5. Enhanced Capture & Extract Dola Cookies + Session
        if (request.action === 'EXTRACT_DOLA_COOKIES' || request.action === 'capture_active_tab_session') {
            extractDolaCookiesAndSession(request.tabId)
                .then(result => sendResponse(result))
                .catch(err => sendResponse({ success: false, error: err?.message || String(err) }));
            return true;
        }

        // 6. Get all open Dola tabs
        if (request.action === 'GET_DOLA_TABS') {
            chrome.tabs.query({
                url: ['*://*.dola.com/*', '*://*.doubao.com/*', '*://dola.com/*', '*://doubao.com/*']
            }, (tabs) => {
                const list = (tabs || []).map(t => ({
                    id: t.id,
                    title: t.title || 'Dola Tab',
                    url: t.url,
                    active: t.active
                }));
                sendResponse({ success: true, tabs: list });
            });
            return true;
        }

        // 7. Save Dola session into Extension storage
        if (request.action === 'SAVE_DOLA_SESSION') {
            const accountName = String(request.accountName || request.name || '').trim();
            if (!accountName) {
                sendResponse({ success: false, error: 'Tên tài khoản không được để trống.' });
                return false;
            }
            storageGet([PROFILE_STORAGE_KEY]).then(async (stored) => {
                const profiles = stored[PROFILE_STORAGE_KEY] || {};
                profiles[accountName] = {
                    name: accountName,
                    cookies: Array.isArray(request.cookies) ? request.cookies : [],
                    local_storage: request.local_storage || request.localStorage || {},
                    cookie_string: request.cookie_string || request.cookieString || '',
                    fb_uid: request.fb_uid || request.fbUid || '',
                    dola_uid: request.dola_uid || request.dolaUid || '',
                    color: request.color || '#fbbf24',
                    updated_at: Date.now()
                };
                await storageSet({
                    [PROFILE_STORAGE_KEY]: profiles,
                    active_profile_name: accountName
                });
                sendResponse({ success: true, accountName, count: profiles[accountName].cookies.length });
            }).catch(err => {
                sendResponse({ success: false, error: err?.message || String(err) });
            });
            return true;
        }

        return undefined;
    });

    self.ChannaBulkAccountManager = Object.freeze({
        normalizeQueue,
        moveNamesToBottom,
        openMultipleAccounts,
        extractDolaCookiesAndSession
    });
})();
