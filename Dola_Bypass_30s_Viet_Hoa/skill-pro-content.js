/* Native Dola Skill installer & activator — LeVietTungSkill30s
   Flow: /chat/skills -> Quản lý / Thêm -> Tải kỹ năng lên -> Upload SKILL.md/ZIP -> Chờ hiển thị -> Click '...' -> Thử trong cuộc trò chuyện mới -> Pro Mode */
(() => {
  'use strict';
  if (!/^(www\.)?dola\.com$/.test(location.hostname)) return;

  const FLOW_KEY = 'seedance_skill_flow_v3';
  const NAME = /^(?:LeVietTungSkill30s|Leviettungskill30s|Le[ _-]?Viet[ _-]?Tung[ _-]?Skill[ _-]?30s|Mianbrothers[ _-]+Seedance[ _-]+2[ _-]+5[ _-]+30s)$/i;
  let busy = false;

  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const visible = el => el && !!el.getClientRects().length;
  const text = el => (el.innerText || el.textContent || '').trim();

  function status(message) {
    let el = document.getElementById('seedance-skill-status');
    if (!el) {
      el = document.createElement('div');
      el.id = 'seedance-skill-status';
      el.style.cssText = 'position:fixed;right:16px;bottom:90px;z-index:2147483646;max-width:400px;padding:12px 16px;background:#16213a;color:#fff;border:1px solid #6366f1;border-radius:10px;font:13px sans-serif;box-shadow:0 8px 24px rgba(0,0,0,0.5);white-space:pre-wrap;line-height:1.4';
      document.body.append(el);
    }
    el.textContent = '⚡ Skill 30s · ' + message;
  }

  async function waitFor(getter, timeout = 15000, stepName = 'điều khiển') {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      try {
        const value = getter();
        if (value) return value;
      } catch (_) {}
      await sleep(250);
    }
    throw new Error(`Không tìm thấy [${stepName}] sau ${Math.round(timeout / 1000)}s.`);
  }

  async function identity() {
    try {
      const response = await fetch('/passport/account/info/v2/', { credentials: 'include' });
      const json = await response.json();
      const user = json.data || {};
      if (json.message !== 'success' || user.is_visitor_account || !user.user_id) {
        throw new Error('Cần đăng nhập Dola trước khi cài Skill.');
      }
      return String(user.user_id_str || user.user_id);
    } catch (err) {
      return 'user_active';
    }
  }

  function save(flow) {
    sessionStorage.setItem(FLOW_KEY, JSON.stringify(flow));
  }

  /* Utility to generate standard uncompressed ZIP containing SKILL.md in browser memory */
  function makeZip(filename, contentStr) {
    const enc = new TextEncoder();
    const fileData = enc.encode(contentStr);
    const nameBytes = enc.encode(filename);

    const crcTable = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = ((c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1));
      crcTable[n] = c;
    }
    let crc = 0 ^ (-1);
    for (let i = 0; i < fileData.length; i++) {
      crc = (crc >>> 8) ^ crcTable[(crc ^ fileData[i]) & 0xFF];
    }
    crc = (crc ^ (-1)) >>> 0;

    const lfh = new Uint8Array(30 + nameBytes.length);
    const dvLfh = new DataView(lfh.buffer);
    dvLfh.setUint32(0, 0x04034b50, true);
    dvLfh.setUint16(4, 20, true);
    dvLfh.setUint16(6, 0x0800, true);
    dvLfh.setUint16(8, 0, true);
    dvLfh.setUint16(10, 0, true);
    dvLfh.setUint16(12, 0, true);
    dvLfh.setUint32(14, crc, true);
    dvLfh.setUint32(18, fileData.length, true);
    dvLfh.setUint32(22, fileData.length, true);
    dvLfh.setUint16(26, nameBytes.length, true);
    dvLfh.setUint16(28, 0, true);
    lfh.set(nameBytes, 30);

    const cdh = new Uint8Array(46 + nameBytes.length);
    const dvCdh = new DataView(cdh.buffer);
    dvCdh.setUint32(0, 0x02014b50, true);
    dvCdh.setUint16(4, 20, true);
    dvCdh.setUint16(6, 20, true);
    dvCdh.setUint16(8, 0x0800, true);
    dvCdh.setUint16(10, 0, true);
    dvCdh.setUint16(12, 0, true);
    dvCdh.setUint16(14, 0, true);
    dvCdh.setUint32(16, crc, true);
    dvCdh.setUint32(20, fileData.length, true);
    dvCdh.setUint32(24, fileData.length, true);
    dvCdh.setUint16(28, nameBytes.length, true);
    dvCdh.setUint16(30, 0, true);
    dvCdh.setUint16(32, 0, true);
    dvCdh.setUint16(34, 0, true);
    dvCdh.setUint16(36, 0, true);
    dvCdh.setUint32(38, 0, true);
    dvCdh.setUint32(42, 0, true);
    cdh.set(nameBytes, 46);

    const cdhOffset = lfh.length + fileData.length;

    const eocd = new Uint8Array(22);
    const dvEocd = new DataView(eocd.buffer);
    dvEocd.setUint32(0, 0x06054b50, true);
    dvEocd.setUint16(4, 0, true);
    dvEocd.setUint16(6, 0, true);
    dvEocd.setUint16(8, 1, true);
    dvEocd.setUint16(10, 1, true);
    dvEocd.setUint32(12, cdh.length, true);
    dvEocd.setUint32(16, cdhOffset, true);
    dvEocd.setUint16(20, 0, true);

    const blob = new Blob([lfh, fileData, cdh, eocd], { type: 'application/zip' });
    return new File([blob], 'LeVietTungSkill30s.zip', { type: 'application/zip' });
  }

  function findSkillItem() {
    const all = [...document.querySelectorAll('span, div, h3, h4, p, strong')].filter(visible);
    return all.find(el => {
      const t = text(el);
      return NAME.test(t) || /Leviettungskill30s/i.test(t);
    });
  }

  function findSkillRow(skillTitleEl) {
    if (!skillTitleEl) return null;
    let cur = skillTitleEl;
    for (let i = 0; i < 6; i++) {
      if (!cur.parentElement || cur.parentElement === document.body) break;
      cur = cur.parentElement;
      if (cur.querySelector('button, [role="button"], [role="switch"], input[type="checkbox"]')) {
        return cur;
      }
    }
    return skillTitleEl.parentElement?.parentElement || skillTitleEl;
  }

  function findManageButton() {
    const elements = [...document.querySelectorAll('button, [role="button"], a, div, span')].filter(visible);
    return elements.find(el => {
      const t = text(el);
      // Strictly match button "Quản lý" or "Manage" without back-arrow
      return (t === 'Quản lý' || t === 'Manage') && el.childElementCount <= 2;
    });
  }

  function findAddButton() {
    const elements = [...document.querySelectorAll('button, [role="button"], a, div, span')].filter(visible);
    // Find button containing "+" and "Thêm" or "Add"
    let match = elements.find(el => {
      const t = text(el);
      return (t === '+ Thêm' || t === 'Thêm' || t === '+ Add' || t === 'Add') && el.childElementCount <= 2;
    });
    if (match) return match;

    return elements.find(el => {
      const t = text(el);
      return t.length <= 15 && /\+.*(?:Thêm|Add)|(?:Thêm|Add)/i.test(t);
    });
  }

  function findUploadMenuItem() {
    const elements = [...document.querySelectorAll('div, li, button, [role="menuitem"], span, p')].filter(visible);
    return elements.find(el => /Tải kỹ năng lên|Upload skill/i.test(text(el)));
  }

  async function launchSkillFromDots(skillRow) {
    status('Tìm nút "..." trên Skill...');
    // Trigger hover to ensure action buttons are rendered
    skillRow.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    skillRow.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
    await sleep(500);

    const buttons = [...skillRow.querySelectorAll('button, [role="button"], span, div')].filter(visible);
    const nonSwitch = buttons.filter(b => {
      const role = b.getAttribute('role') || '';
      const cls = b.className || '';
      return role !== 'switch' && !cls.includes('switch');
    });

    // 1. Text dots '...', '···', '⋮', '⋯'
    let dotsBtn = nonSwitch.find(b => /^\s*(\.\.\.|···|⋮|⋯)\s*$/.test(text(b))) ||
      nonSwitch.find(b => /(thao tác|menu|more|options|hành động)/i.test((b.getAttribute('aria-label') || '') + ' ' + (b.getAttribute('title') || ''))) ||
      nonSwitch.find(b => b.tagName === 'BUTTON' && b.querySelector('svg')) ||
      nonSwitch.find(b => b.tagName === 'BUTTON') ||
      nonSwitch[0];

    if (!dotsBtn) throw new Error('Không tìm thấy nút "..." cạnh Skill.');
    dotsBtn.click();
    await sleep(600);

    status('Chọn "Thử trong cuộc trò chuyện mới"...');
    const tryBtn = await waitFor(() => {
      return [...document.querySelectorAll('div, button, [role="menuitem"], span, li')].find(el => {
        return visible(el) && /Thử trong cuộc trò chuyện mới|Try in new chat/i.test(text(el));
      });
    }, 8000, 'menu "Thử trong cuộc trò chuyện mới"');
    tryBtn.click();
  }

  async function uploadSkillFlow() {
    status('Bấm nút "+ Thêm"...');
    const addBtn = await waitFor(() => findAddButton(), 10000, 'nút "+ Thêm"');
    addBtn.click();
    await sleep(700);

    status('Chọn "Tải kỹ năng lên"...');
    const uploadItem = await waitFor(() => findUploadMenuItem(), 8000, 'mục "Tải kỹ năng lên"');
    uploadItem.click();
    await sleep(1000);

    status('Nạp file SKILL.md & ZIP...');
    const asset = await fetch(chrome.runtime.getURL('skills/video_30s/SKILL.md'));
    if (!asset.ok) throw new Error('Thiếu file skills/video_30s/SKILL.md trong extension.');
    const skillText = await asset.text();

    const mdFile = new File([skillText], 'SKILL.md', { type: 'text/markdown' });
    const zipFile = makeZip('SKILL.md', skillText);

    const dialog = await waitFor(() => {
      return document.querySelector('[role="dialog"]') ||
        [...document.querySelectorAll('div')].find(d => visible(d) && /Tải kỹ năng lên/i.test(text(d)) && /Kéo tập tin|Drag/i.test(text(d)));
    }, 10000, 'hộp thoại tải lên');

    const fileInputs = [...dialog.querySelectorAll('input[type="file"]')].concat(
      [...document.querySelectorAll('input[type="file"]')].filter(visible)
    );

    // Feed files to input[type="file"]
    for (const input of fileInputs) {
      try {
        const dt = new DataTransfer();
        dt.items.add(zipFile);
        dt.items.add(mdFile);
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('input', { bubbles: true }));
      } catch (_) {}
    }

    // Dispatch Drag & Drop onto drop zone
    const dropZone = dialog.querySelector('[class*="drop" i], [class*="upload" i], [class*="area" i]') ||
      [...dialog.querySelectorAll('div')].find(el => visible(el) && /Kéo tập tin|Drag/i.test(text(el))) || dialog;

    if (dropZone) {
      const dtDrop = new DataTransfer();
      dtDrop.items.add(zipFile);
      dtDrop.items.add(mdFile);
      for (const evName of ['dragenter', 'dragover', 'drop']) {
        dropZone.dispatchEvent(new DragEvent(evName, {
          bubbles: true,
          cancelable: true,
          dataTransfer: dtDrop
        }));
      }
    }

    await sleep(2000);

    // Click confirmation button if any
    const confirmBtn = [...dialog.querySelectorAll('button')].find(b => {
      return visible(b) && !b.disabled && /^(Cài đặt|Install|Tải lên|Upload|Thêm|Add|Xác nhận|Confirm|Thay thế|Replace)$/i.test(text(b));
    });
    if (confirmBtn) {
      confirmBtn.click();
      await sleep(2000);
    }

    // Handle replace dialog if duplicate
    const replaceBtn = [...document.querySelectorAll('button')].find(b => visible(b) && /^(Thay thế|Replace)$/i.test(text(b)));
    if (replaceBtn) {
      replaceBtn.click();
      await sleep(2000);
    }

    status('Chờ skill LeVietTungSkill30s hiển thị...');
    await waitFor(() => findSkillItem(), 30000, 'Skill hiển thị trong danh sách');
    await sleep(1000);
  }

  async function ensureProModeInChat() {
    status('Đang kiểm tra chế độ Pro trong chat...');
    await waitFor(() => document.querySelector('[contenteditable="true"]'), 20000, 'ô nhập chat');
    await sleep(1000);

    const fast = [...document.querySelectorAll('span, button, div')].find(el => visible(el) && /^(Nhanh|Fast)(\s|$)/.test(text(el)));
    if (fast) {
      fast.click();
      const proItem = await waitFor(() => {
        return [...document.querySelectorAll('span, button, div, [role="option"]')].find(el => visible(el) && /^Pro(?:\s*(?:Mới|New))?$/i.test(text(el)));
      }, 5000, 'chế độ Pro');
      if (proItem) proItem.click();
      await sleep(800);
    }

    sessionStorage.removeItem(FLOW_KEY);
    status('Đã sẵn sàng! Ô chat có LeVietTungSkill30s + Pro. Hãy nhập prompt 30s rồi gửi.');
  }

  async function runSkillsFlow(flow) {
    status('Kiểm tra Skill trong danh sách...');
    await sleep(1200);

    // If on Explore page (with "Quản lý" button), click "Quản lý" to open user's skills
    const manageBtn = findManageButton();
    if (manageBtn) {
      status('Vào trang "Quản lý" kỹ năng...');
      manageBtn.click();
      await sleep(1200);
    }

    let skillItem = findSkillItem();
    if (!skillItem) {
      status('Chưa có Skill, đang tiến hành cài mới...');
      await uploadSkillFlow();
      skillItem = findSkillItem();
    }

    if (!skillItem) {
      throw new Error('Skill chưa hiển thị sau khi tải lên. Vui lòng thử lại.');
    }

    status('Đã thấy Skill ' + (text(skillItem) || 'LeVietTungSkill30s') + '. Đang mở chat...');
    const skillRow = findSkillRow(skillItem);
    save({ uid: flow.uid, stage: 'chat_ready', started: Date.now() });
    await launchSkillFromDots(skillRow);
  }

  async function resume(flow) {
    if (busy) return;
    busy = true;
    try {
      if (Date.now() - flow.started > 180000) {
        sessionStorage.removeItem(FLOW_KEY);
        throw new Error('Quá thời gian thực hiện. Bấm Cài Skill để thử lại.');
      }

      // Close cookie / consent banner if any
      const consent = [...document.querySelectorAll('button')].find(b => visible(b) && /^(OK|Accept all|Chấp nhận tất cả)$/i.test(text(b)));
      if (consent) consent.click();

      // If we arrived at /chat/ and flow is ready for chat
      if (flow.stage === 'chat_ready' && location.pathname !== '/chat/skills') {
        await ensureProModeInChat();
        return;
      }

      // If on /chat/skills, execute skills management flow
      if (location.pathname === '/chat/skills') {
        await runSkillsFlow(flow);
        return;
      }

      // Otherwise navigate to /chat/skills
      save(flow);
      location.assign('/chat/skills');
    } catch (error) {
      sessionStorage.removeItem(FLOW_KEY);
      console.warn('[Skill Pro Error]', error);
      status(error.message);
    } finally {
      busy = false;
    }
  }

  async function prepare() {
    busy = false;
    sessionStorage.removeItem(FLOW_KEY);

    const uid = await identity();
    sessionStorage.setItem('seedance_pro_skill_native', '1');
    const flow = { uid, stage: 'skills', started: Date.now() };
    save(flow);

    if (location.pathname === '/chat/skills') {
      await resume(flow);
    } else {
      location.assign('/chat/skills');
    }
  }

  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (message?.type !== 'SEEDANCE_PREPARE_SKILL_PRO') return false;
    prepare()
      .then(() => reply({ ok: true, preparing: true }))
      .catch(error => {
        status(error.message);
        reply({ ok: false, error: error.message });
      });
    return true;
  });

  async function start() {
    let flow;
    try {
      flow = JSON.parse(sessionStorage.getItem(FLOW_KEY) || 'null');
    } catch (_) {}

    if (flow) {
      await resume(flow);
      return;
    }

    // Auto-prepare checkbox if enabled
    const config = await chrome.storage.local.get('seedance_auto_skill');
    if (config.seedance_auto_skill && /^\/chat\/?$/.test(location.pathname)) {
      const editor = document.querySelector('[contenteditable="true"]');
      if (!editor || text(editor)) return;
      try { await prepare(); } catch (error) { status(error.message); }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(start, 1200), { once: true });
  } else {
    setTimeout(start, 1200);
  }
})();
