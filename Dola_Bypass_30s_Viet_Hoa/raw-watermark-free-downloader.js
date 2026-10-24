// =========================================================================
// Dola 30s Bypass Pro - Bộ Tải Video Không Logo & Đóng Gói ZIP Hàng Loạt
// Tác giả: LÊ VIỆT TÙNG
// Zalo: 0915967790 | Facebook: https://www.facebook.com/tungbinh.38/
// =========================================================================

(function () {
  'use strict';

  if (window.__brandAiRawDownloaderInstalled) return;
  window.__brandAiRawDownloaderInstalled = true;

  const seenMedia = new Set();
  const cancelledMedia = new Set();
  const cancelledBuildIds = new Set();
  const pendingPageBatches = new Map();
  const extractedVideosPool = new Map();
  const BATCH_SETTLE_MS = 250;
  const ZIP_OVERLAY_ID = 'brandai-video-zip-overlay';
  const MINI_BADGE_ID = 'brandai-video-zip-minibadge';
  const TOAST_ID = 'brandai-individual-video-toast';
  let overlayHideTimer = 0;
  let toastTimer = 0;
  let currentBuildId = '';
  let isCurrentDownloadPaused = false;
  let lastProgressData = null;
  let isAutoScrolling = false;
  let autoScrollTimer = null;
  const sessionStartTime = Date.now();
  const initialHistoryKeys = new Set();
  let isInitialHistoryCaptured = false;
  const newlyCreatedVideoKeys = new Set();
  let seedanceBatchContext = null;
  let settingOnlyNewVideos = true;
  let settingShowVideoBtn = true;

  function formatBytes(value) {
    const bytes = Number(value);
    if (!Number.isFinite(bytes) || bytes <= 0) return '';
    if (bytes < 1024) return `${Math.round(bytes)} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function appendElement(parent, tag, properties = {}) {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(properties)) {
      if (key === 'text') element.textContent = value;
      else if (key === 'html') element.innerHTML = value;
      else if (key === 'style') element.style.cssText = value;
      else element.setAttribute(key, value);
    }
    parent.appendChild(element);
    return element;
  }

  // Chuyển đổi mọi link video sang chuẩn sạch Master 1080P không logo
  function toUnwatermarkedMasterUrl(rawUrl) {
    if (!rawUrl || typeof rawUrl !== 'string') return '';
    let clean = rawUrl.replace(/\\u0026/gi, '&').replace(/&amp;/gi, '&').replace(/\\\//g, '/').trim();
    if (clean.startsWith('http://')) clean = 'https://' + clean.slice(7);
    clean = clean.replace('&download=true', '').replace('?download=true&', '?').replace('download=true&', '');
    if (clean.endsWith('?download=true')) clean = clean.slice(0, -14);
    for (const wm of ['lr=video_gen_watermark_dyn', 'lr=video_gen_watermark', 'lr=watermarked', 'lr=cici_ai']) {
      clean = clean.replace(wm, 'lr=unwatermarked');
    }
    if (!clean.includes('lr=')) {
      clean = clean.includes('?') ? `${clean}&lr=unwatermarked` : `${clean}?lr=unwatermarked`;
    }
    if (!clean.includes('download=true')) {
      clean = clean.includes('?') ? `${clean}&download=true` : `${clean}?download=true`;
    }
    return clean;
  }

  function ensureMiniBadge() {
    let badge = document.getElementById(MINI_BADGE_ID);
    if (badge) return badge;

    badge = appendElement(document.body || document.documentElement, 'div', {
      id: MINI_BADGE_ID,
      style: [
        'position:fixed',
        'bottom:24px',
        'right:24px',
        'z-index:2147483647',
        'display:none',
        'align-items:center',
        'gap:10px',
        'padding:10px 18px',
        'border-radius:30px',
        'background:rgba(17,24,39,0.94)',
        'backdrop-filter:blur(12px)',
        'border:1px solid rgba(129,140,248,0.5)',
        'box-shadow:0 12px 36px rgba(0,0,0,0.55)',
        'color:#f8fafc',
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
        'font-size:13px',
        'font-weight:600',
        'cursor:pointer',
        'transition:all 0.2s ease',
        'user-select:none'
      ].join(';'),
      html: `
        <span id="brandai-minibadge-dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#6366f1;box-shadow:0 0 8px #6366f1;"></span>
        <span id="brandai-minibadge-text">⚡ <b>Tải ZIP</b> Đang tải: <b>0%</b></span>
      `
    });

    badge.addEventListener('click', () => {
      const overlay = document.getElementById(ZIP_OVERLAY_ID);
      if (overlay) overlay.style.display = 'flex';
      badge.style.display = 'none';
    });

    badge.addEventListener('mouseenter', () => {
      badge.style.transform = 'scale(1.04)';
      badge.style.borderColor = '#818cf8';
    });
    badge.addEventListener('mouseleave', () => {
      badge.style.transform = 'scale(1)';
    });

    return badge;
  }

  function updateMiniBadge(progress = {}) {
    const badge = ensureMiniBadge();
    const percent = Math.round(Math.min(100, Math.max(0, Number(progress.percent) || 0)));
    const stage = progress.stage || 'downloading';
    if (stage === 'complete' || stage === 'error' || stage === 'cancelled') {
      badge.style.display = 'none';
      return;
    }
    const dot = badge.querySelector('#brandai-minibadge-dot');
    const text = badge.querySelector('#brandai-minibadge-text');
    const color = progress.isPaused ? '#f59e0b' : '#6366f1';
    if (dot) {
      dot.style.background = color;
      dot.style.boxShadow = `0 0 8px ${color}`;
    }
    if (text) {
      const newHtml = `⚡ <b>Tải ZIP</b> ${progress.isPaused ? 'Đã tạm dừng' : 'Đang tải'}: <b>${percent}%</b>`;
      if (text.innerHTML !== newHtml) {
        text.innerHTML = newHtml;
      }
    }
  }

  function ensureZipOverlay() {
    let overlay = document.getElementById(ZIP_OVERLAY_ID);
    if (overlay) return overlay;

    overlay = appendElement(document.body || document.documentElement, 'div', {
      id: ZIP_OVERLAY_ID,
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': 'brandai-video-zip-title',
      style: [
        'position:fixed',
        'inset:0',
        'z-index:2147483646',
        'display:flex',
        'align-items:center',
        'justify-content:center',
        'padding:20px',
        'background:rgba(15,23,42,.75)',
        'backdrop-filter:blur(6px)',
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
        'user-select:none'
      ].join(';')
    });

    const card = appendElement(overlay, 'div', {
      style: [
        'position:relative',
        'width:min(500px,100%)',
        'box-sizing:border-box',
        'padding:26px 28px',
        'border:1px solid rgba(129,140,248,.45)',
        'border-radius:20px',
        'background:linear-gradient(145deg, #111827, #0f172a)',
        'color:#f8fafc',
        'box-shadow:0 24px 70px rgba(0,0,0,.65)'
      ].join(';')
    });

    // Branding Badge Pill
    const badgeRow = appendElement(card, 'div', {
      style: 'display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;'
    });

    appendElement(badgeRow, 'div', {
      html: '<span style="color:#818cf8;margin-right:4px;">⚡</span> Trình tải hàng loạt • <b>LÊ VIỆT TÙNG</b>',
      style: [
        'display:inline-flex',
        'align-items:center',
        'padding:4px 12px',
        'border-radius:20px',
        'background:rgba(99,102,241,0.18)',
        'border:1px solid rgba(129,140,248,0.35)',
        'font-size:11.5px',
        'font-weight:600',
        'color:#c7d2fe',
        'letter-spacing:0.3px'
      ].join(';')
    });

    const closeBtn = appendElement(badgeRow, 'button', {
      id: 'brandai-video-zip-close-btn',
      text: '✕',
      title: 'Thu nhỏ cửa sổ (Quá trình tải vẫn tiếp tục dưới nền)',
      style: [
        'background:rgba(255,255,255,0.08)',
        'border:none',
        'color:#94a3b8',
        'font-size:15px',
        'font-weight:bold',
        'width:28px',
        'height:28px',
        'border-radius:50%',
        'cursor:pointer',
        'display:flex',
        'align-items:center',
        'justify-content:center',
        'transition:all 0.2s ease'
      ].join(';')
    });

    closeBtn.addEventListener('mouseenter', () => {
      closeBtn.style.background = 'rgba(255,255,255,0.18)';
      closeBtn.style.color = '#ffffff';
    });
    closeBtn.addEventListener('mouseleave', () => {
      closeBtn.style.background = 'rgba(255,255,255,0.08)';
      closeBtn.style.color = '#94a3b8';
    });
    closeBtn.addEventListener('click', () => {
      overlay.style.display = 'none';
      const badge = ensureMiniBadge();
      badge.style.display = 'flex';
    });

    // Title Row
    appendElement(card, 'div', {
      id: 'brandai-video-zip-title',
      text: 'Đang chuẩn bị đóng gói file ZIP video',
      style: 'font-size:20px;font-weight:750;line-height:1.25;margin-bottom:6px;'
    });

    // Subtitle / Status
    appendElement(card, 'div', {
      id: 'brandai-video-zip-status',
      text: 'Đang bắt đầu tải song song (3 luồng tốc độ cao)…',
      role: 'status',
      'aria-live': 'polite',
      style: 'font-size:14px;line-height:1.5;color:#cbd5e1;margin-bottom:16px'
    });

    // Progress Bar Track
    const track = appendElement(card, 'div', {
      role: 'progressbar',
      'aria-valuemin': '0',
      'aria-valuemax': '100',
      'aria-valuenow': '0',
      style: 'height:11px;overflow:hidden;border-radius:999px;background:#1e293b;border:1px solid rgba(255,255,255,0.05);'
    });
    appendElement(track, 'div', {
      id: 'brandai-video-zip-progress',
      style: [
        'width:0%',
        'height:100%',
        'border-radius:inherit',
        'background:linear-gradient(90deg,#6366f1,#a855f7)',
        'transition:width .2s ease'
      ].join(';')
    });

    // Percent & Bytes Row
    const statsRow = appendElement(card, 'div', {
      style: 'display:flex;align-items:center;justify-content:space-between;margin-top:8px;'
    });
    appendElement(statsRow, 'div', {
      id: 'brandai-video-zip-file',
      text: '3 Luồng video đang tải song song',
      style: 'font-size:12.5px;color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:75%;'
    });
    appendElement(statsRow, 'div', {
      id: 'brandai-video-zip-percent',
      text: '0%',
      style: 'font-size:13.5px;font-weight:750;color:#a5b4fc'
    });

    // Action Controls Row: Pause / Resume & Cancel Buttons
    const actionsRow = appendElement(card, 'div', {
      id: 'brandai-video-zip-actions',
      style: 'display:flex;align-items:center;gap:12px;margin-top:20px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08);'
    });

    const pauseBtn = appendElement(actionsRow, 'button', {
      id: 'brandai-video-zip-pause-btn',
      text: '⏸ Tạm dừng',
      style: [
        'flex:1',
        'padding:8px 16px',
        'border-radius:10px',
        'border:1px solid rgba(129,140,248,0.4)',
        'background:rgba(99,102,241,0.15)',
        'color:#e0e7ff',
        'font-size:13px',
        'font-weight:600',
        'cursor:pointer',
        'transition:all 0.2s ease'
      ].join(';')
    });

    pauseBtn.addEventListener('mouseenter', () => {
      pauseBtn.style.background = 'rgba(99,102,241,0.3)';
    });
    pauseBtn.addEventListener('mouseleave', () => {
      pauseBtn.style.background = isCurrentDownloadPaused ? 'rgba(245,158,11,0.2)' : 'rgba(99,102,241,0.15)';
    });

    pauseBtn.addEventListener('click', () => {
      isCurrentDownloadPaused = !isCurrentDownloadPaused;
      pauseBtn.textContent = isCurrentDownloadPaused ? '▶ Tiếp tục' : '⏸ Tạm dừng';
      pauseBtn.style.borderColor = isCurrentDownloadPaused ? 'rgba(245,158,11,0.5)' : 'rgba(129,140,248,0.4)';
      pauseBtn.style.background = isCurrentDownloadPaused ? 'rgba(245,158,11,0.2)' : 'rgba(99,102,241,0.15)';
      pauseBtn.style.color = isCurrentDownloadPaused ? '#fde68a' : '#e0e7ff';

      chrome.runtime.sendMessage({
        type: isCurrentDownloadPaused ? 'BRANDAI_PAUSE_VIDEO_ZIP' : 'BRANDAI_RESUME_VIDEO_ZIP',
        buildId: currentBuildId
      }).catch(() => {});
    });

    const cancelBtn = appendElement(actionsRow, 'button', {
      id: 'brandai-video-zip-cancel-btn',
      text: '⏹ Hủy tải',
      style: [
        'flex:1',
        'padding:8px 16px',
        'border-radius:10px',
        'border:1px solid rgba(239,68,68,0.4)',
        'background:rgba(239,68,68,0.12)',
        'color:#fca5a5',
        'font-size:13px',
        'font-weight:600',
        'cursor:pointer',
        'transition:all 0.2s ease'
      ].join(';')
    });

    cancelBtn.addEventListener('mouseenter', () => {
      cancelBtn.style.background = 'rgba(239,68,68,0.25)';
    });
    cancelBtn.addEventListener('mouseleave', () => {
      cancelBtn.style.background = 'rgba(239,68,68,0.12)';
    });

    cancelBtn.addEventListener('click', () => {
      const buildIdToCancel = currentBuildId;
      if (buildIdToCancel) {
        cancelledBuildIds.add(buildIdToCancel);
      }

      for (const batch of pendingPageBatches.values()) {
        clearTimeout(batch.timerId);
      }
      pendingPageBatches.clear();

      for (const key of seenMedia) {
        cancelledMedia.add(key);
      }

      chrome.runtime.sendMessage({
        type: 'BRANDAI_CANCEL_VIDEO_ZIP',
        buildId: buildIdToCancel
      }).catch(() => {});

      clearTimeout(overlayHideTimer);
      overlay.remove();
      const badge = document.getElementById(MINI_BADGE_ID);
      if (badge) badge.remove();
    });

    // Footer
    const footer = appendElement(card, 'div', {
      style: 'margin-top:14px;font-size:11.5px;line-height:1.45;color:#64748b;display:flex;align-items:center;justify-content:space-between;'
    });
    appendElement(footer, 'span', {
      html: '⚡ Phát triển bởi <b>LÊ VIỆT TÙNG</b> (Zalo: 0915967790)',
      style: 'color:#818cf8;font-weight:600;'
    });
    appendElement(footer, 'span', {
      text: 'Tự động lưu vào thư mục Downloads'
    });

    return overlay;
  }

  function updateZipOverlay(progress = {}) {
    try {
      clearTimeout(overlayHideTimer);
      lastProgressData = progress;
      if (progress.buildId) currentBuildId = progress.buildId;

      if (progress.buildId && cancelledBuildIds.has(progress.buildId)) {
        const overlay = document.getElementById(ZIP_OVERLAY_ID);
        if (overlay) overlay.remove();
        const badge = document.getElementById(MINI_BADGE_ID);
        if (badge) badge.remove();
        return;
      }

      const overlay = ensureZipOverlay();
      const stage = String(progress.stage || 'downloading');
      const total = Math.max(0, Number(progress.total) || 0);
      const completed = Math.min(total, Math.max(0, Number(progress.completed) || 0));
      const percent = Math.min(100, Math.max(0, Number(progress.percent) || 0));
      const status = overlay.querySelector('#brandai-video-zip-status');
      const bar = overlay.querySelector('#brandai-video-zip-progress');
      const percentLabel = overlay.querySelector('#brandai-video-zip-percent');
      const fileLabel = overlay.querySelector('#brandai-video-zip-file');
      const title = overlay.querySelector('#brandai-video-zip-title');
      const actions = overlay.querySelector('#brandai-video-zip-actions');
      const pauseBtn = overlay.querySelector('#brandai-video-zip-pause-btn');

      if (progress.isPaused !== undefined && pauseBtn) {
        isCurrentDownloadPaused = Boolean(progress.isPaused);
        pauseBtn.textContent = isCurrentDownloadPaused ? '▶ Tiếp tục' : '⏸ Tạm dừng';
        pauseBtn.style.borderColor = isCurrentDownloadPaused ? 'rgba(245,158,11,0.5)' : 'rgba(129,140,248,0.4)';
        pauseBtn.style.background = isCurrentDownloadPaused ? 'rgba(245,158,11,0.2)' : 'rgba(99,102,241,0.15)';
        pauseBtn.style.color = isCurrentDownloadPaused ? '#fde68a' : '#e0e7ff';
      }

      const activeConcurrency = progress.concurrency || 3;
      let statusText = total
        ? `Đã tải ${completed} / ${total} video (${activeConcurrency} luồng song song)`
        : 'Đang bắt đầu tải các luồng video song song…';

      if (stage === 'saving') {
        statusText = 'Đang nén và lưu file ZIP vào Downloads…';
      } else if (stage === 'complete') {
        statusText = `Hoàn tất! Đã nén thành công ${completed || total} video vào file ZIP.`;
      } else if (stage === 'paused') {
        statusText = `Đã tạm dừng tải (${completed} / ${total} video đã nạp).`;
      } else if (stage === 'error') {
        statusText = `Lỗi tải file ZIP: ${progress.error || 'Lỗi mạng / CDN'}`;
      } else if (stage === 'cancelled') {
        statusText = 'Người dùng đã hủy tải ZIP.';
      }

      if (title) {
        if (stage === 'saving') title.textContent = 'Đang đóng gói file ZIP…';
        else if (stage === 'complete') title.textContent = '✅ Tải File ZIP Hoàn Tất!';
        else if (stage === 'paused') title.textContent = '⏸ Đã Tạm Dừng Tải ZIP';
        else if (stage === 'error') title.textContent = '❌ Lỗi Tạo File ZIP';
        else if (stage === 'cancelled') title.textContent = '⏹ Đã Hủy Tải ZIP';
        else title.textContent = 'Đang tải video song song…';
      }

      if (status) status.textContent = statusText;
      if (bar) bar.style.width = `${percent}%`;
      if (percentLabel) percentLabel.textContent = `${percent}%`;

      const byteText = progress.currentTotal
        ? `${formatBytes(progress.currentBytes)} / ${formatBytes(progress.currentTotal)}`
        : formatBytes(progress.currentBytes);
      if (fileLabel) {
        fileLabel.textContent = byteText ? `Đang tải song song — ${byteText}` : (progress.filename || '10 Luồng video đang tải');
      }

      updateMiniBadge(progress);

      if (stage === 'complete') {
        if (title) title.textContent = '✅ File ZIP Video Đã Sẵn Sàng!';
        if (bar) bar.style.background = '#22c55e';
        if (actions) actions.style.display = 'none';
        overlayHideTimer = setTimeout(() => {
          overlay.remove();
          const badge = document.getElementById(MINI_BADGE_ID);
          if (badge) badge.remove();
        }, 2500);
      } else if (stage === 'error' || stage === 'cancelled') {
        if (stage === 'cancelled') {
          overlay.remove();
          const badge = document.getElementById(MINI_BADGE_ID);
          if (badge) badge.remove();
          return;
        }
        if (title) title.textContent = 'Tải File ZIP Thất Bại';
        if (bar) bar.style.background = '#ef4444';
        if (actions) actions.style.display = 'none';
        overlayHideTimer = setTimeout(() => {
          overlay.remove();
          const badge = document.getElementById(MINI_BADGE_ID);
          if (badge) badge.remove();
        }, 4000);
      }
    } catch {}
  }

  function mediaKey(video) {
    if (!video) return '';
    const cleanUrl = toUnwatermarkedMasterUrl(String(video.url || ''));
    return String(video.key || video.vid || cleanUrl);
  }

  function releaseVideo(video) {
    const key = mediaKey(video);
    const url = String(video?.url || '');
    if (cancelledMedia.has(key) || cancelledMedia.has(url)) return;
    if (key) seenMedia.delete(key);
    if (url) seenMedia.delete(url);
  }

  function queuePageVideo(video) {
    const pageUrl = String(video.pageUrl || location.href);
    const key = mediaKey(video);
    const url = toUnwatermarkedMasterUrl(String(video?.url || ''));
    if (cancelledMedia.has(key) || cancelledMedia.has(url)) return;

    let batch = pendingPageBatches.get(pageUrl);
    if (!batch) {
      batch = { pageUrl, videos: new Map(), timerId: 0, forceTimerId: 0, pendingRemaining: 0 };
      pendingPageBatches.set(pageUrl, batch);
    }

    batch.videos.set(key, { ...video, url });
    if (typeof video.pendingRemaining === 'number') {
      batch.pendingRemaining = video.pendingRemaining;
    }

    clearTimeout(batch.timerId);

    if (video.batchTotal === 1 && (!video.pendingRemaining || video.pendingRemaining === 0)) {
      batch.timerId = setTimeout(() => void flushPageBatch(pageUrl), 60);
      if (!batch.forceTimerId) {
        batch.forceTimerId = setTimeout(() => {
          if (pendingPageBatches.has(pageUrl)) {
            void flushPageBatch(pageUrl, true);
          }
        }, 1200);
      }
    } else {
      batch.timerId = setTimeout(() => void flushPageBatch(pageUrl), 60);
    }
  }

  window.addEventListener('DOLA_VIDEO_EXTRACTIONS_COMPLETED', event => {
    const pageUrl = String(event?.detail?.pageUrl || location.href);
    const batch = pendingPageBatches.get(pageUrl);
    if (batch && batch.videos.size > 0) {
      batch.pendingRemaining = 0;
      clearTimeout(batch.timerId);
      clearTimeout(batch.forceTimerId);
      batch.forceTimerId = 0;
      batch.timerId = setTimeout(() => void flushPageBatch(pageUrl), 20);
    }
  });

  const BULK_DOCK_ID = 'brandai-bulk-mode-dock';
  let isStorageInitialized = false;
  let isBulkModeActive = false;

  chrome.storage.local.get(['brandai_bulk_mode', 'setting_only_new_videos', 'setting_show_video_btn'], res => {
    isBulkModeActive = Boolean(res?.brandai_bulk_mode);
    if (typeof res?.setting_only_new_videos === 'boolean') {
      settingOnlyNewVideos = res.setting_only_new_videos;
    }
    if (typeof res?.setting_show_video_btn === 'boolean') {
      settingShowVideoBtn = res.setting_show_video_btn;
    }
    isStorageInitialized = true;
    updateBulkDock();
    injectSingleVideoDownloadButtons();
    if (!isBulkModeActive) {
      for (const [pageUrl] of pendingPageBatches) {
        void flushPageBatch(pageUrl);
      }
    }
  });

  chrome.storage.onChanged.addListener(changes => {
    if (changes.brandai_bulk_mode) {
      isBulkModeActive = Boolean(changes.brandai_bulk_mode.newValue);
      isStorageInitialized = true;
      updateBulkDock();
    }
    if (changes.setting_only_new_videos) {
      settingOnlyNewVideos = Boolean(changes.setting_only_new_videos.newValue);
      updateBulkDock();
    }
    if (changes.setting_show_video_btn) {
      settingShowVideoBtn = Boolean(changes.setting_show_video_btn.newValue);
      injectSingleVideoDownloadButtons();
    }
  });

  function setBulkMode(enabled) {
    isBulkModeActive = Boolean(enabled);
    isStorageInitialized = true;
    chrome.storage.local.set({ brandai_bulk_mode: isBulkModeActive });
    updateBulkDock();
  }

  const BATCH_CONFIRM_PROMPT_ID = 'dola-account-batch-download-prompt';
  const confirmedPageBatches = new Set();
  const dismissedPageBatches = new Set();

  function showAccountBatchDownloadPrompt(pageUrl, batch) {
    if (!batch || !batch.videos) return;
    const videos = Array.from(batch.videos.values()).filter(v => {
      const k = mediaKey(v);
      const u = String(v?.url || '');
      return !cancelledMedia.has(k) && !cancelledMedia.has(u);
    });
    if (videos.length === 0) return;

    const batchKey = `${pageUrl}_${videos.length}`;
    // Tool-managed batch profiles opt in to automatic downloads. Regular Chrome
    // profiles keep the existing explicit confirmation to avoid downloading history.
    if (window.__SEEDANCE_BATCH_CONTEXT__?.autoDownload === true) {
      void flushPageBatch(pageUrl, true, true);
      return;
    }
    if (dismissedPageBatches.has(batchKey) || confirmedPageBatches.has(batchKey)) return;

    // Nếu đã có thông báo trên trang, chỉ cần cập nhật số lượng
    let promptEl = document.getElementById(BATCH_CONFIRM_PROMPT_ID);
    if (promptEl) {
      const countEl = promptEl.querySelector('.dola-prompt-count');
      if (countEl) countEl.textContent = String(videos.length);
      const btnConfirm = promptEl.querySelector('.dola-prompt-btn-confirm');
      if (btnConfirm) btnConfirm.textContent = `⚡ Đồng ý tải (${videos.length} video)`;
      return;
    }

    promptEl = document.createElement('div');
    promptEl.id = BATCH_CONFIRM_PROMPT_ID;
    promptEl.style.cssText = [
      'position: fixed',
      'bottom: 24px',
      'right: 24px',
      'z-index: 2147483647',
      'max-width: 420px',
      'background: linear-gradient(135deg, rgba(15, 23, 42, 0.97) 0%, rgba(30, 41, 59, 0.97) 100%)',
      'border: 1px solid rgba(56, 189, 248, 0.45)',
      'box-shadow: 0 20px 48px rgba(0, 0, 0, 0.65), 0 0 24px rgba(56, 189, 248, 0.25)',
      'border-radius: 16px',
      'padding: 18px 20px',
      'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      'color: #f8fafc',
      'box-sizing: border-box',
      'backdrop-filter: blur(16px)',
      'transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
      'animation: dolaPromptSlideUp 0.35s ease-out'
    ].join(';');

    promptEl.innerHTML = `
      <style>
        @keyframes dolaPromptSlideUp {
          from { opacity: 0; transform: translateY(20px) scale(0.96); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        #${BATCH_CONFIRM_PROMPT_ID} button:hover {
          filter: brightness(1.12);
          transform: translateY(-1px);
        }
        #${BATCH_CONFIRM_PROMPT_ID} button:active {
          transform: translateY(1px);
        }
      </style>
      <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 10px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 22px;">🎬</span>
          <div>
            <div style="font-weight: 800; font-size: 14px; color: #f8fafc; line-height: 1.2;">Phát hiện video trong tài khoản</div>
            <div style="font-size: 11px; color: #38bdf8; font-weight: 600;">Dola AI Master 1080P (Không Logo)</div>
          </div>
        </div>
        <span class="dola-prompt-close" style="cursor: pointer; color: #94a3b8; font-size: 18px; line-height: 1; padding: 2px 4px;" title="Đóng">✕</span>
      </div>
      <div style="font-size: 12.5px; color: #cbd5e1; line-height: 1.5; margin-bottom: 14px;">
        Tìm thấy <b class="dola-prompt-count" style="color: #34d399; font-weight: 800;">${videos.length}</b> video trong lịch sử cuộc trò chuyện. Bạn có muốn tải toàn bộ về máy không?
      </div>
      <div style="display: flex; gap: 8px; justify-content: flex-end;">
        <button class="dola-prompt-btn-dismiss" style="background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.15); color: #94a3b8; font-size: 11.5px; font-weight: 600; padding: 8px 13px; border-radius: 9px; cursor: pointer; transition: all 0.2s;">
          ❌ Bỏ qua
        </button>
        <button class="dola-prompt-btn-confirm" style="background: linear-gradient(135deg, #10b981, #059669); border: 1px solid rgba(52, 211, 153, 0.5); color: #ffffff; font-size: 11.5px; font-weight: 800; padding: 8px 14px; border-radius: 9px; cursor: pointer; box-shadow: 0 4px 14px rgba(16, 185, 129, 0.4); transition: all 0.2s;">
          ⚡ Đồng ý tải (${videos.length} video)
        </button>
      </div>
    `;

    document.body.appendChild(promptEl);

    const closeBtn = promptEl.querySelector('.dola-prompt-close');
    const dismissBtn = promptEl.querySelector('.dola-prompt-btn-dismiss');
    const confirmBtn = promptEl.querySelector('.dola-prompt-btn-confirm');

    const handleDismiss = () => {
      dismissedPageBatches.add(batchKey);
      promptEl.style.opacity = '0';
      promptEl.style.transform = 'translateY(16px)';
      setTimeout(() => promptEl.remove(), 250);
      showIndividualToast('Đã bỏ qua tải toàn bộ. Bạn vẫn có thể bấm "Tải video này" trên từng khung hình.');
    };

    closeBtn.addEventListener('click', handleDismiss);
    dismissBtn.addEventListener('click', handleDismiss);

    confirmBtn.addEventListener('click', () => {
      confirmedPageBatches.add(batchKey);
      promptEl.style.opacity = '0';
      promptEl.style.transform = 'translateY(16px)';
      setTimeout(() => promptEl.remove(), 250);
      showIndividualToast(`Đang bắt đầu tải ${videos.length} video về máy...`);
      void flushPageBatch(pageUrl, true, true);
    });
  }

  async function flushPageBatch(pageUrl, force = false, isManualTrigger = false) {
    const batch = pendingPageBatches.get(pageUrl);
    if (!batch) return;

    if (!isStorageInitialized && !isManualTrigger) {
      setTimeout(() => void flushPageBatch(pageUrl, force, isManualTrigger), 80);
      return;
    }

    if (!force && batch.pendingRemaining > 0) {
      clearTimeout(batch.timerId);
      batch.timerId = setTimeout(() => void flushPageBatch(pageUrl), BATCH_SETTLE_MS);
      return;
    }

    const videos = Array.from(batch.videos.values()).filter(v => {
      const k = mediaKey(v);
      const u = String(v?.url || '');
      return !cancelledMedia.has(k) && !cancelledMedia.has(u);
    });
    if (!videos.length) return;

    // 🛑 CHẶN TỰ ĐỘNG TẢI TOÀN BỘ KHI VÀO TÀI KHOẢN MỚI
    // Chỉ tải khi người dùng chủ động bấm xác nhận (isManualTrigger = true)
    if (!isManualTrigger) {
      updateBulkDock();
      showAccountBatchDownloadPrompt(pageUrl, batch);
      return;
    }

    if (isBulkModeActive && !isManualTrigger) {
      updateBulkDock();
      return;
    }

    pendingPageBatches.delete(pageUrl);
    clearTimeout(batch.timerId);
    clearTimeout(batch.forceTimerId);

    try {
      const response = await chrome.runtime.sendMessage({
        type: 'BRANDAI_RAW_VIDEO_BATCH_DOWNLOAD',
        pageUrl,
        videos,
        forceIndividual: Boolean(settingOnlyNewVideos),
        mode: settingOnlyNewVideos ? 'individual' : undefined
      });

      if (!response?.ok) {
        const isCancelled = response?.cancelled ||
          response?.error?.toLowerCase().includes('cancel') ||
          response?.reason?.toLowerCase().includes('cancel') ||
          (currentBuildId && cancelledBuildIds.has(currentBuildId));

        if (!isCancelled) {
          videos.forEach(releaseVideo);
          if (videos.length > 5) {
            updateZipOverlay({
              stage: 'error',
              error: response?.error || response?.reason || 'Không thể bắt đầu tải file ZIP.'
            });
          }
        } else {
          for (const v of videos) {
            const k = mediaKey(v);
            const u = String(v?.url || '');
            if (k) cancelledMedia.add(k);
            if (u) cancelledMedia.add(u);
          }
        }
        return;
      }

      for (const failed of response.failed || []) {
        releaseVideo(failed);
      }
      if (response.mode === 'zip') updateZipOverlay({ stage: 'saving', percent: 100 });
    } catch (error) {
      const isCancelled = error?.message?.toLowerCase().includes('cancel') ||
        (currentBuildId && cancelledBuildIds.has(currentBuildId));

      if (!isCancelled) {
        videos.forEach(releaseVideo);
        if (videos.length > 5) {
          updateZipOverlay({ stage: 'error', error: error?.message || String(error) });
        }
      } else {
        for (const v of videos) {
          const k = mediaKey(v);
          const u = String(v?.url || '');
          if (k) cancelledMedia.add(k);
          if (u) cancelledMedia.add(u);
        }
      }
    }
  }

  function injectScrollStyles() {
    if (document.getElementById('brandai-scroll-styles')) return;
    const style = document.createElement('style');
    style.id = 'brandai-scroll-styles';
    style.textContent = `
      @keyframes brandai-spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
      #${BULK_DOCK_ID} {
        cursor: grab;
      }
      #${BULK_DOCK_ID}:active {
        cursor: grabbing;
      }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  function findChatScrollContainer() {
    const selectors = [
      '[class*="chat-scroll" i]',
      '[class*="chat-list" i]',
      '[class*="chat-body" i]',
      '[class*="chat-content" i]',
      '[class*="chat-container" i]',
      '[class*="message-list" i]',
      '[class*="messageList" i]',
      '[class*="message-container" i]',
      '[class*="messages" i]',
      '[class*="conversation" i]',
      '[class*="history" i]',
      '[data-testid*="chat" i]',
      '[data-testid*="message" i]',
      'main',
      '[role="main"]'
    ];

    for (const sel of selectors) {
      const els = document.querySelectorAll(sel);
      for (const el of els) {
        if (!el) continue;
        const style = window.getComputedStyle(el);
        const isScrollable = (style.overflowY === 'auto' || style.overflowY === 'scroll' || style.overflow === 'auto' || style.overflow === 'scroll');
        if (isScrollable && el.scrollHeight > el.clientHeight + 30) {
          return el;
        }
      }
    }

    let best = null;
    let maxDelta = 30;
    const all = document.querySelectorAll('div, main, section, article');
    for (const el of all) {
      const delta = el.scrollHeight - el.clientHeight;
      if (delta > maxDelta) {
        const style = window.getComputedStyle(el);
        if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
          maxDelta = delta;
          best = el;
        }
      }
    }
    if (best) return best;

    return document.scrollingElement || document.documentElement || document.body || window;
  }

  // 🎯 QUÉT VIDEO CHẶT CHẼ: CHỈ LẤY LINK UNWATERMARKED, KHÔNG LẤY PREVIEW CÓ LOGO
  function scanDomAndChatVideos() {
    try {
      const list = window.__dolaChatVideos || window.chatVideos || [];
      if (Array.isArray(list)) {
        for (const v of list) {
          if (v && v.url && /^https?:\/\//i.test(v.url)) {
            const cleanUrl = toUnwatermarkedMasterUrl(String(v.url));
            const k = String(v.vid || cleanUrl);
            if (!extractedVideosPool.has(k)) {
              const isNew = isInitialHistoryCaptured
                ? (!initialHistoryKeys.has(k) && !initialHistoryKeys.has(cleanUrl))
                : (Date.now() - sessionStartTime > 2500);
              if (isNew) {
                newlyCreatedVideoKeys.add(k);
                newlyCreatedVideoKeys.add(cleanUrl);
              }
              extractedVideosPool.set(k, {
                ...v,
                url: cleanUrl,
                isNewVideo: Boolean(isNew),
                pageUrl: location.href,
                source: 'fallback_api'
              });
            }
          }
        }
      }
    } catch {}
    injectSingleVideoDownloadButtons();
  }

  function captureInitialHistory() {
    if (isInitialHistoryCaptured) return;
    for (const [key, v] of extractedVideosPool) {
      initialHistoryKeys.add(key);
      if (v?.url) initialHistoryKeys.add(v.url);
    }
    const videos = document.querySelectorAll('video');
    videos.forEach(v => {
      const src = v.currentSrc || v.src || '';
      if (src) {
        initialHistoryKeys.add(src);
        initialHistoryKeys.add(toUnwatermarkedMasterUrl(src));
      }
    });
    isInitialHistoryCaptured = true;
    updateBulkDock();
    injectSingleVideoDownloadButtons();
  }

  setTimeout(captureInitialHistory, 1500);

  function isNewlyCreatedVideo(video) {
    if (!video) return false;
    const key = mediaKey(video);
    const url = toUnwatermarkedMasterUrl(String(video?.url || ''));
    if (newlyCreatedVideoKeys.has(key) || newlyCreatedVideoKeys.has(url)) return true;
    if (video.isNewVideo) return true;
    if (!isInitialHistoryCaptured) return false;
    if (initialHistoryKeys.has(key) || initialHistoryKeys.has(url)) return false;
    return true;
  }

  function getNewlyCreatedVideos() {
    const list = [];
    for (const [, v] of extractedVideosPool) {
      if (isNewlyCreatedVideo(v)) {
        list.push(v);
      }
    }
    return list;
  }

  function startAutoScrollChat() {
    if (isAutoScrolling) return;
    isAutoScrolling = true;

    const container = findChatScrollContainer();
    let unchangedCount = 0;
    let lastScrollTop = container?.scrollTop ?? -1;
    let iterations = 0;

    updateBulkDock();

    autoScrollTimer = setInterval(() => {
      if (!isAutoScrolling) {
        clearInterval(autoScrollTimer);
        return;
      }

      iterations++;
      scanDomAndChatVideos();

      if (container) {
        if (typeof container.scrollBy === 'function') {
          container.scrollBy({ top: -600, behavior: 'smooth' });
        } else if (container === window || container === document.documentElement || container === document.body) {
          window.scrollBy({ top: -600, behavior: 'smooth' });
        } else {
          container.scrollTop = Math.max(0, container.scrollTop - 600);
        }

        const currentScrollTop = container?.scrollTop ?? window.scrollY;
        if (Math.abs(currentScrollTop - lastScrollTop) < 5 || currentScrollTop <= 0) {
          unchangedCount++;
        } else {
          unchangedCount = 0;
        }
        lastScrollTop = currentScrollTop;
      }

      updateBulkDock();

      if (unchangedCount >= 4 || iterations >= 60) {
        stopAutoScrollChat(true);
      }
    }, 700);
  }

  function stopAutoScrollChat(completed = false) {
    isAutoScrolling = false;
    if (autoScrollTimer) {
      clearInterval(autoScrollTimer);
      autoScrollTimer = null;
    }
    updateBulkDock(completed);
  }

  function triggerManualBulkDownload() {
    const pageUrl = location.href;
    let batch = pendingPageBatches.get(pageUrl);
    let videos = [];

    if (batch && batch.videos.size > 0) {
      videos = Array.from(batch.videos.values());
    } else if (extractedVideosPool.size > 0) {
      videos = Array.from(extractedVideosPool.values());
    }

    const filtered = videos.filter(v => {
      const k = mediaKey(v);
      const u = String(v?.url || '');
      return !cancelledMedia.has(k) && !cancelledMedia.has(u);
    });

    if (!filtered.length) {
      alert('Chưa trích xuất được video không logo nào. Hãy bấm "Tự động cuộn chat" để trích xuất video cũ trước.');
      return;
    }

    pendingPageBatches.delete(pageUrl);

    void chrome.runtime.sendMessage({
      type: 'BRANDAI_RAW_VIDEO_BATCH_DOWNLOAD',
      pageUrl,
      videos: filtered
    });
  }

  function triggerIndividualNewVideosDownload() {
    const pageUrl = location.href;
    const newVideos = getNewlyCreatedVideos().filter(v => {
      const k = mediaKey(v);
      const u = String(v?.url || '');
      return v?.source === 'fallback_api' && !cancelledMedia.has(k) && !cancelledMedia.has(u);
    });

    if (!newVideos.length) {
      alert('Chưa phát hiện video mới nào vừa tạo trong phiên này!\n\n💡 Gợi ý: Hãy gửi prompt tạo video mới, hoặc bấm "Tải File ZIP" nếu bạn muốn tải lại các video cũ trong lịch sử chat.');
      return;
    }

    void chrome.runtime.sendMessage({
      type: 'BRANDAI_RAW_VIDEO_BATCH_DOWNLOAD',
      pageUrl,
      videos: newVideos,
      forceIndividual: true,
      mode: 'individual'
    });

    showIndividualToast(`Đang tải lẻ ${newVideos.length} video mới không logo (chuẩn Master 1080P)...`);
  }

  // =========================================================================
  // 🔘 CHỨC NĂNG TẢI TRỰC TIẾP VIDEO KHÔNG LOGO TRÊN TỪNG KHUNG VIDEO (1-CLICK)
  // =========================================================================
  // =========================================================================
  // 🔘 CHỨC NĂNG TẢI TRỰC TIẾP VIDEO KHÔNG LOGO TRÊN TỪNG KHUNG VIDEO (1-CLICK)
  // =========================================================================
  function extractVideoFingerprint(url) {
    if (!url || typeof url !== 'string') return '';
    try {
      const u = url.split('?')[0].split('#')[0];
      // 1. Check for 32-64 char unique hex hash
      const hashMatch = u.match(/([a-f0-9]{32,64})/i);
      if (hashMatch) {
        return hashMatch[1].toLowerCase();
      }

      // 2. Generic path components that must NEVER be treated as video identity
      const genericWords = new Set([
        'obj', 'video', 'tos', 'stream', 'default', 'alisg', 'my', 'cn', 'us',
        'media', 'attachment', 'download', 'preview', 'watermarked', 'sign', 'master',
        'play', 'thumb', 'poster', 'first_frame', 'cover'
      ]);

      const segments = u.split('/').filter(Boolean);
      // Look from the end backwards for the unique video identifier
      for (let i = segments.length - 1; i >= 0; i--) {
        const seg = segments[i].replace(/\.[a-z0-9]+$/i, '').trim();
        if (seg.length >= 12 && !genericWords.has(seg.toLowerCase())) {
          return seg.toLowerCase();
        }
      }

      // Fallback: segment with at least 8 chars
      for (let i = segments.length - 1; i >= 0; i--) {
        const seg = segments[i].replace(/\.[a-z0-9]+$/i, '').trim();
        if (seg.length >= 8 && !genericWords.has(seg.toLowerCase())) {
          return seg.toLowerCase();
        }
      }
      return '';
    } catch(e) {
      return '';
    }
  }

  function getElementPoster(videoEl, container) {
    if (!videoEl && !container) return '';
    try {
      if (videoEl?.poster && /^https?:\/\//i.test(videoEl.poster)) {
        return videoEl.poster.trim();
      }

      const root = container || videoEl?.parentElement;
      if (root) {
        const posterEls = root.querySelectorAll('.xgplayer-poster, [class*="poster" i], [class*="cover" i], [class*="thumbnail" i]');
        for (const el of posterEls) {
          const bg = el.style?.backgroundImage || (window.getComputedStyle ? window.getComputedStyle(el).backgroundImage : '');
          if (bg && bg !== 'none') {
            const match = bg.match(/url\(["']?(.*?)["']?\)/i);
            if (match && /^https?:\/\//i.test(match[1])) {
              return match[1].trim();
            }
          }
          const src = el.src || el.getAttribute('data-src') || el.getAttribute('data-url');
          if (src && /^https?:\/\//i.test(src)) {
            return src.trim();
          }
        }

        const imgs = root.querySelectorAll('img:not([class*="avatar" i]):not([alt*="avatar" i])');
        for (const img of imgs) {
          if (img.clientWidth > 80 || img.width > 80 || (!img.clientWidth && !img.className.toLowerCase().includes('avatar'))) {
            const src = img.src || img.getAttribute('data-src');
            if (src && /^https?:\/\//i.test(src)) {
              return src.trim();
            }
          }
        }
      }
    } catch(e) {}
    return '';
  }

  function resolveVideoPrompt(videoEl, container) {
    const stampedPrompt = container?.getAttribute('data-dola-prompt') || videoEl?.getAttribute('data-dola-prompt');
    if (stampedPrompt && stampedPrompt.trim()) {
      return stampedPrompt.trim().replace(/[\r\n\t]+/g, ' ').slice(0, 100);
    }

    let promptText = '';
    const messageRow = (videoEl || container)?.closest('[class*="message" i], [class*="chat-row" i], [class*="v_list_row" i], [class*="item" i], [class*="bubble" i]');
    if (messageRow) {
      const prevRow = messageRow.previousElementSibling;
      if (prevRow) {
        const text = (prevRow.innerText || prevRow.textContent || '').trim();
        if (text && !prevRow.querySelector('video')) {
          promptText = text.replace(/[\r\n\t]+/g, ' ').slice(0, 80);
        }
      }
      if (!promptText) {
        const promptEl = messageRow.querySelector('[class*="prompt" i], [class*="text" i], [class*="content" i]');
        if (promptEl) {
          promptText = (promptEl.innerText || promptEl.textContent || '').replace(/[\r\n\t]+/g, ' ').slice(0, 80);
        }
      }
    }
    return promptText || 'Dola_Video_1080P';
  }

  function findFallbackApiVideoForElement(videoEl, container) {
    if (extractedVideosPool.size === 0) return null;

    const allVideos = Array.from(extractedVideosPool.values()).filter(v => v && v.source === 'fallback_api' && v.url);
    if (allVideos.length === 0) return null;

    // TIER 1: Đóng dấu chuẩn xác từ MAIN world hoặc phiên trước
    const stampedMasterUrl = container?.getAttribute('data-dola-master-url') ||
                             videoEl?.getAttribute('data-dola-master-url') ||
                             container?.getAttribute('data-dola-matched-url') ||
                             videoEl?.getAttribute('data-dola-matched-url');
    if (stampedMasterUrl) {
      const matched = allVideos.find(v => v.url === stampedMasterUrl);
      if (matched) return matched;
    }

    // TIER 2: Khớp theo Stream URL / Video Source / CDN Token trên thẻ video
    const candidateUrls = [
      videoEl?.currentSrc,
      videoEl?.src,
      ...Array.from(videoEl?.querySelectorAll('source') || []).map(s => s.src),
      container?.querySelector('video')?.currentSrc,
      container?.querySelector('video')?.src,
      container?.getAttribute('data-url'),
      container?.getAttribute('data-src'),
      videoEl?.getAttribute('data-url'),
      videoEl?.getAttribute('data-src')
    ].filter(Boolean);

    for (const cUrl of candidateUrls) {
      const cPrint = extractVideoFingerprint(cUrl);
      if (cPrint && cPrint.length >= 8) {
        for (const v of allVideos) {
          const vPreviewPrint = extractVideoFingerprint(v.preview_url);
          const vPrint = extractVideoFingerprint(v.url);
          const rawPrint = extractVideoFingerprint(v.rawUrl);

          if ((vPreviewPrint && vPreviewPrint === cPrint) ||
              (vPrint && vPrint === cPrint) ||
              (rawPrint && rawPrint === cPrint) ||
              (v.preview_url && v.preview_url.includes(cPrint)) ||
              (v.url && v.url.includes(cPrint))) {
            container?.setAttribute('data-dola-matched-url', v.url);
            videoEl?.setAttribute('data-dola-matched-url', v.url);
            return v;
          }
        }
      }
    }

    // TIER 3: Khớp theo ảnh Poster / Thumbnail
    const poster = getElementPoster(videoEl, container);
    if (poster) {
      const pPrint = extractVideoFingerprint(poster);
      for (const v of allVideos) {
        if (v.poster_url) {
          if (v.poster_url === poster || poster.includes(v.poster_url) || v.poster_url.includes(poster)) {
            container?.setAttribute('data-dola-matched-url', v.url);
            videoEl?.setAttribute('data-dola-matched-url', v.url);
            return v;
          }
          if (pPrint && pPrint.length >= 8) {
            const vPosterPrint = extractVideoFingerprint(v.poster_url);
            if (vPosterPrint === pPrint) {
              container?.setAttribute('data-dola-matched-url', v.url);
              videoEl?.setAttribute('data-dola-matched-url', v.url);
              return v;
            }
          }
          const pName1 = v.poster_url.split('?')[0].split('/').pop();
          const pName2 = poster.split('?')[0].split('/').pop();
          if (pName1 && pName2 && pName1.length > 8 && pName1 === pName2) {
            container?.setAttribute('data-dola-matched-url', v.url);
            videoEl?.setAttribute('data-dola-matched-url', v.url);
            return v;
          }
        }
      }
    }

    // TIER 4: Khớp theo Video ID (vid) hoặc Creation ID
    const vid = container?.getAttribute('data-dola-vid') ||
                videoEl?.getAttribute('data-dola-vid') ||
                container?.getAttribute('data-vid') ||
                container?.getAttribute('data-id') ||
                videoEl?.getAttribute('data-vid') || '';
    if (vid) {
      for (const v of allVideos) {
        if ((v.vid && (v.vid === vid || v.vid.includes(vid) || vid.includes(v.vid))) ||
            (v.creationId && (v.creationId === vid || v.creationId.includes(vid)))) {
          container?.setAttribute('data-dola-matched-url', v.url);
          videoEl?.setAttribute('data-dola-matched-url', v.url);
          return v;
        }
      }
    }

    // TIER 5: Khớp theo prompt text trong thẻ tin nhắn chat
    const promptText = resolveVideoPrompt(videoEl, container);
    if (promptText && promptText.length >= 10 && promptText !== 'Dola_Video_1080P') {
      const lowerPrompt = promptText.toLowerCase();
      for (const v of allVideos) {
        const vPrompt = String(v.prompt || v.topicTitle || '').trim().toLowerCase();
        if (vPrompt && vPrompt.length >= 10) {
          const snippet = vPrompt.slice(0, 30);
          if (lowerPrompt.includes(snippet) || vPrompt.includes(lowerPrompt.slice(0, 30))) {
            container?.setAttribute('data-dola-matched-url', v.url);
            videoEl?.setAttribute('data-dola-matched-url', v.url);
            return v;
          }
        }
      }
    }

    // TIER 6: Nếu chỉ có duy nhất 1 video trong chat -> chắc chắn là video đó
    if (allVideos.length === 1) {
      container?.setAttribute('data-dola-matched-url', allVideos[0].url);
      videoEl?.setAttribute('data-dola-matched-url', allVideos[0].url);
      return allVideos[0];
    }

    // TIER 7: Khớp theo thứ tự vị trí hiển thị tương đối trong cuộc hội thoại
    const allVisibleCards = Array.from(document.querySelectorAll('.xgplayer, [class*="xgplayer" i], .xg-video-container, [class*="video-card" i], [class*="videoCard" i]'));
    const uniqueCards = allVisibleCards.filter((card, idx, arr) => arr.indexOf(card) === idx && card.querySelector('video'));
    const targetCard = container?.closest('.xgplayer, [class*="xgplayer" i], .xg-video-container, [class*="video-card" i], [class*="videoCard" i]') || container;
    const cardIdx = uniqueCards.indexOf(targetCard);

    if (cardIdx >= 0 && uniqueCards.length === allVideos.length) {
      const matched = allVideos[cardIdx];
      if (matched) {
        container?.setAttribute('data-dola-matched-url', matched.url);
        videoEl?.setAttribute('data-dola-matched-url', matched.url);
        return matched;
      }
    }

    return null;
  }

  function injectSingleVideoDownloadButtons() {
    if (!settingShowVideoBtn) {
      const existing = document.querySelectorAll('.dola-single-video-download-btn');
      existing.forEach(b => b.remove());
      return;
    }

    const videoElements = document.querySelectorAll('video');
    videoElements.forEach(video => {
      const container = video.closest('.xgplayer, [class*="xgplayer" i], .xg-video-container, [class*="video-card" i], [class*="videoCard" i], [class*="video-container" i]') || video.parentElement;
      if (!container) return;

      const style = window.getComputedStyle(container);
      if (style.position === 'static') {
        container.style.position = 'relative';
      }

      if (container.querySelector('.dola-single-video-download-btn')) return;

      const btn = document.createElement('button');
      btn.className = 'dola-single-video-download-btn';
      btn.type = 'button';
      btn.title = 'Tải trực tiếp video này về máy (Master 1080P không logo)';
      btn.innerHTML = '📥 Tải video này';

      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        e.preventDefault();

        btn.innerHTML = '⏳ Đang lấy link không logo...';
        btn.style.opacity = '0.85';

        // Yêu cầu MAIN world gửi danh sách nếu pool rỗng
        if (extractedVideosPool.size === 0) {
          try {
            window.dispatchEvent(new CustomEvent('DOLA_GET_CHAT_MEDIA'));
          } catch(e) {}
        }

        let targetVideo = findFallbackApiVideoForElement(video, container);
        if (!targetVideo) {
          // Chờ tối đa 3.5s để luồng fallback_api giải mã xong
          const startWait = Date.now();
          while (!targetVideo && Date.now() - startWait < 3500) {
            await new Promise(r => setTimeout(r, 350));
            targetVideo = findFallbackApiVideoForElement(video, container);
          }
        }

        // TUYỆT ĐỐI CHỈ TẢI TỪ FALLBACK_API - KHÔNG BAO GIỜ TẢI VIDEO PREVIEW TRONG DOM
        if (!targetVideo || !targetVideo.url || targetVideo.source !== 'fallback_api') {
          btn.innerHTML = '⚠️ Chưa tìm thấy link';
          setTimeout(() => {
            btn.innerHTML = '📥 Tải video này';
            btn.style.opacity = '0.95';
          }, 2500);
          const shouldOpenPicker = confirm('Chưa xác định chắc chắn luồng video Master không logo cho khung video này để tránh tải nhầm video khác.\n\n👉 Bạn có muốn mở bảng "Chọn Từng Video" để xem ảnh thumbnail và bấm tải chính xác video mong muốn không?');
          if (shouldOpenPicker) {
            openVideoPickerModal();
          }
          return;
        }

        btn.innerHTML = '⏳ Đang tải Master 1080P...';

        const safePrompt = targetVideo.prompt || targetVideo.topicTitle || resolveVideoPrompt(video, container);

        try {
          const res = await chrome.runtime.sendMessage({
            type: 'BRANDAI_RAW_VIDEO_DOWNLOAD',
            video: {
              ...targetVideo,
              url: targetVideo.url,
              source: 'fallback_api',
              prompt: safePrompt,
              force: true
            }
          });

          if (res?.ok !== false) {
            btn.innerHTML = '✅ Đã tải (Sạch logo)!';
            btn.style.background = '#059669';
            showIndividualToast(safePrompt);
          } else {
            btn.innerHTML = '❌ Lỗi tải: ' + (res?.error || res?.reason || '');
          }
        } catch (err) {
          btn.innerHTML = '❌ Lỗi kết nối';
        }

        setTimeout(() => {
          btn.innerHTML = '📥 Tải video này';
          btn.style.background = 'rgba(16, 85, 50, 0.9)';
          btn.style.opacity = '0.95';
        }, 2500);
      });

      container.appendChild(btn);
    });
  }

  // =========================================================================
  // 📋 GIAO DIỆN CHỌN TỪNG VIDEO (VISUAL VIDEO PICKER MODAL)
  // =========================================================================
  function openVideoPickerModal() {
    let overlay = document.getElementById('dola-video-picker-overlay');
    if (overlay) {
      overlay.remove();
    }

    if (extractedVideosPool.size === 0) {
      try {
        window.dispatchEvent(new CustomEvent('DOLA_GET_CHAT_MEDIA'));
      } catch(e) {}
    }

    const allVideos = Array.from(extractedVideosPool.values()).filter(v => v && v.source === 'fallback_api' && v.url);

    overlay = document.createElement('div');
    overlay.id = 'dola-video-picker-overlay';
    overlay.style.cssText = [
      'position: fixed',
      'inset: 0',
      'z-index: 2147483647',
      'background: rgba(0, 0, 0, 0.75)',
      'backdrop-filter: blur(8px)',
      'display: flex',
      'align-items: center',
      'justify-content: center',
      'font-family: Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      'color: #f8fafc',
      'padding: 20px',
      'box-sizing: border-box'
    ].join(';');

    const modal = document.createElement('div');
    modal.id = 'dola-video-picker-modal';
    modal.style.cssText = [
      'background: linear-gradient(145deg, #111827, #0f172a)',
      'border: 1px solid rgba(251, 191, 36, 0.45)',
      'box-shadow: 0 25px 60px rgba(0,0,0,0.8), 0 0 30px rgba(255, 126, 0, 0.2)',
      'border-radius: 20px',
      'width: 100%',
      'max-width: 780px',
      'max-height: 88vh',
      'display: flex',
      'flex-direction: column',
      'overflow: hidden',
      'box-sizing: border-box'
    ].join(';');

    // Header
    const header = document.createElement('div');
    header.style.cssText = [
      'padding: 18px 24px',
      'border-bottom: 1px solid rgba(255,255,255,0.08)',
      'display: flex',
      'align-items: center',
      'justify-content: space-between',
      'background: rgba(255,255,255,0.02)'
    ].join(';');
    header.innerHTML = `
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#ff7e00,#fbbf24);display:flex;align-items:center;justify-content:center;font-size:18px;box-shadow:0 0 12px rgba(255,126,0,0.4);">
          📋
        </div>
        <div>
          <div style="font-size:16px;font-weight:800;color:#f8fafc;display:flex;align-items:center;gap:8px;">
            <span>Danh Sách Video Master Không Logo</span>
            <span id="dola-picker-total-badge" style="background:rgba(255,126,0,0.2);color:#fed7aa;padding:1px 8px;border-radius:8px;font-size:11px;border:1px solid rgba(251,191,36,0.35);">${allVideos.length} video</span>
          </div>
          <div style="font-size:12px;color:#94a3b8;margin-top:2px;">Chọn từng video để tải lẻ • Chuẩn 1080P Master sạch logo 100%</div>
        </div>
      </div>
      <button id="dola-picker-close-btn" style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#cbd5e1;width:32px;height:32px;border-radius:8px;font-size:15px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.15s ease;" title="Đóng">✕</button>
    `;

    // Toolbar
    const toolbar = document.createElement('div');
    toolbar.style.cssText = [
      'padding: 12px 24px',
      'border-bottom: 1px solid rgba(255,255,255,0.06)',
      'display: flex',
      'align-items: center',
      'justify-content: space-between',
      'gap: 16px',
      'background: rgba(0,0,0,0.2)'
    ].join(';');
    toolbar.innerHTML = `
      <div style="flex:1;position:relative;">
        <input id="dola-picker-search-input" type="text" placeholder="🔍 Tìm theo prompt hoặc chủ đề..." style="width:100%;box-sizing:border-box;background:rgba(15,23,42,0.8);border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:8px 14px;color:#f8fafc;font-size:12.5px;outline:none;" />
      </div>
      <div style="display:flex;align-items:center;gap:12px;flex-shrink:0;">
        <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:#cbd5e1;cursor:pointer;user-select:none;">
          <input type="checkbox" id="dola-picker-select-all" style="accent-color:#10b981;cursor:pointer;width:15px;height:15px;" />
          <span>Chọn tất cả</span>
        </label>
        <button id="dola-picker-batch-dl-btn" style="background:linear-gradient(135deg,#10b981,#059669);border:none;color:#fff;padding:8px 14px;border-radius:9px;font-weight:700;font-size:12px;cursor:pointer;box-shadow:0 4px 12px rgba(16,185,129,0.35);display:inline-flex;align-items:center;gap:6px;transition:all 0.2s ease;">
          📥 Tải các video đã chọn (<span id="dola-picker-checked-count">0</span>)
        </button>
      </div>
    `;

    // Body: Video List
    const body = document.createElement('div');
    body.id = 'dola-picker-body';
    body.style.cssText = [
      'padding: 16px 24px',
      'overflow-y: auto',
      'flex: 1',
      'display: flex',
      'flex-direction: column',
      'gap: 12px',
      'box-sizing: border-box'
    ].join(';');

    // Footer
    const footer = document.createElement('div');
    footer.style.cssText = [
      'padding: 12px 24px',
      'border-top: 1px solid rgba(255,255,255,0.08)',
      'display: flex',
      'align-items: center',
      'justify-content: space-between',
      'background: rgba(255,255,255,0.02)'
    ].join(';');
    footer.innerHTML = `
      <div style="font-size:11.5px;color:#64748b;">
        💡 Mỗi video tải về được lưu trực tiếp vào thư mục <b style="color:#94a3b8;">Downloads/TheBrandAI_Videos</b>.
      </div>
      <button id="dola-picker-footer-close-btn" style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#cbd5e1;padding:6px 14px;border-radius:8px;font-size:12px;cursor:pointer;">Đóng</button>
    `;

    modal.appendChild(header);
    modal.appendChild(toolbar);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const selectedKeys = new Set();

    function renderList(filterText = '') {
      body.innerHTML = '';

      const query = filterText.trim().toLowerCase();
      const filtered = allVideos.filter(v => {
        if (!query) return true;
        const text = `${v.prompt || ''} ${v.topicTitle || ''} ${v.vid || ''}`.toLowerCase();
        return text.includes(query);
      });

      if (filtered.length === 0) {
        body.innerHTML = `
          <div style="text-align:center;padding:40px 20px;color:#94a3b8;">
            <div style="font-size:36px;margin-bottom:12px;">🔍</div>
            <div style="font-weight:700;font-size:14px;color:#cbd5e1;margin-bottom:6px;">
              ${allVideos.length === 0 ? 'Chưa phát hiện video nào trong trang chat hiện tại' : 'Không tìm thấy video phù hợp với từ khóa'}
            </div>
            <div style="font-size:12px;color:#64748b;max-width:400px;margin:0 auto 16px auto;">
              ${allVideos.length === 0 ? 'Vui lòng bấm nút "Cuộn Bắt Video Cũ" trên thanh dock để trích xuất link Master từ lịch sử hội thoại.' : 'Thử tìm kiếm với từ khóa khác hoặc xóa bộ lọc.'}
            </div>
            ${allVideos.length === 0 ? `
              <button id="dola-picker-empty-scroll-btn" style="background:linear-gradient(135deg,#ff7e00,#fbbf24);border:none;color:#000;padding:8px 16px;border-radius:9px;font-weight:800;font-size:12px;cursor:pointer;">
                📜 Cuộn Bắt Video Cũ Ngay
              </button>
            ` : ''}
          </div>
        `;
        const scrollBtn = body.querySelector('#dola-picker-empty-scroll-btn');
        if (scrollBtn) {
          scrollBtn.addEventListener('click', () => {
            overlay.remove();
            startAutoScrollChat();
          });
        }
        updateCheckedBadge();
        return;
      }

      filtered.forEach((video, index) => {
        const key = String(video.vid || video.url);
        const card = document.createElement('div');
        card.style.cssText = [
          'background: rgba(30, 41, 59, 0.5)',
          'border: 1px solid rgba(255,255,255,0.08)',
          'border-radius: 14px',
          'padding: 12px 14px',
          'display: flex',
          'align-items: center',
          'gap: 14px',
          'transition: all 0.2s ease',
          'box-sizing: border-box'
        ].join(';');

        card.addEventListener('mouseenter', () => {
          card.style.background = 'rgba(30, 41, 59, 0.85)';
          card.style.borderColor = 'rgba(251, 191, 36, 0.35)';
        });
        card.addEventListener('mouseleave', () => {
          card.style.background = 'rgba(30, 41, 59, 0.5)';
          card.style.borderColor = 'rgba(255,255,255,0.08)';
        });

        const isChecked = selectedKeys.has(key);
        const promptDisplay = video.prompt || video.topicTitle || `Video Master #${index + 1}`;

        card.innerHTML = `
          <input type="checkbox" class="dola-picker-item-checkbox" data-key="${key}" ${isChecked ? 'checked' : ''} style="accent-color:#10b981;cursor:pointer;width:17px;height:17px;flex-shrink:0;" />
          
          <div style="position:relative;width:115px;height:65px;border-radius:8px;overflow:hidden;background:#0f172a;flex-shrink:0;border:1px solid rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;">
            ${video.poster_url ? `
              <img src="${video.poster_url}" style="width:100%;height:100%;object-fit:cover;" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';" />
              <div style="display:none;align-items:center;justify-content:center;width:100%;height:100%;font-size:22px;">🎬</div>
            ` : `
              <div style="font-size:22px;">🎬</div>
            `}
            <span style="position:absolute;bottom:3px;right:4px;background:rgba(0,0,0,0.7);color:#fff;padding:1px 4px;border-radius:4px;font-size:9.5px;font-weight:700;">
              ${video.duration ? `${Math.round(video.duration)}s` : 'MP4'}
            </span>
          </div>

          <div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:4px;">
            <div style="font-size:13px;font-weight:700;color:#f8fafc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${promptDisplay.replace(/"/g, '&quot;')}">
              ${promptDisplay}
            </div>
            <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
              <span style="background:rgba(16,185,129,0.15);color:#34d399;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(16,185,129,0.3);">1080P Master</span>
              ${video.width && video.height ? `
                <span style="background:rgba(99,102,241,0.15);color:#a5b4fc;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600;border:1px solid rgba(99,102,241,0.3);">${video.width}x${video.height}</span>
              ` : ''}
              ${video.isNewVideo ? `
                <span style="background:rgba(251,191,36,0.18);color:#fef08a;padding:1px 5px;border-radius:4px;font-size:10px;font-weight:700;">⚡ Mới</span>
              ` : ''}
            </div>
          </div>

          <button class="dola-picker-single-dl-btn" data-key="${key}" style="background:rgba(16,185,129,0.2);border:1px solid rgba(52,211,153,0.5);color:#6ee7b7;padding:7px 14px;border-radius:9px;font-size:11.5px;font-weight:700;cursor:pointer;flex-shrink:0;transition:all 0.15s ease;" title="Tải trực tiếp video này">
            📥 Tải ngay
          </button>
        `;

        // Wire up checkbox
        const chk = card.querySelector('.dola-picker-item-checkbox');
        chk.addEventListener('change', (e) => {
          if (e.target.checked) selectedKeys.add(key);
          else selectedKeys.delete(key);
          updateCheckedBadge();
        });

        // Wire up single download button
        const dlBtn = card.querySelector('.dola-picker-single-dl-btn');
        dlBtn.addEventListener('click', async (e) => {
          e.stopPropagation();
          dlBtn.innerHTML = '⏳ Đang tải...';
          dlBtn.style.opacity = '0.7';

          try {
            const safePrompt = video.prompt || video.topicTitle || `Video_${index + 1}`;
            const res = await chrome.runtime.sendMessage({
              type: 'BRANDAI_RAW_VIDEO_DOWNLOAD',
              video: {
                ...video,
                url: video.url,
                source: 'fallback_api',
                prompt: safePrompt,
                force: true
              }
            });

            if (res?.ok !== false) {
              dlBtn.innerHTML = '✅ Đã tải!';
              dlBtn.style.background = '#059669';
              dlBtn.style.color = '#ffffff';
              showIndividualToast(safePrompt);
            } else {
              dlBtn.innerHTML = '❌ Lỗi tải';
            }
          } catch(err) {
            dlBtn.innerHTML = '❌ Lỗi';
          }

          setTimeout(() => {
            dlBtn.innerHTML = '📥 Tải lại';
            dlBtn.style.opacity = '1';
          }, 3000);
        });

        body.appendChild(card);
      });

      updateCheckedBadge();
    }

    function updateCheckedBadge() {
      const checkedBadge = overlay.querySelector('#dola-picker-checked-count');
      if (checkedBadge) checkedBadge.textContent = selectedKeys.size;
      const selectAll = overlay.querySelector('#dola-picker-select-all');
      if (selectAll) {
        selectAll.checked = allVideos.length > 0 && selectedKeys.size === allVideos.length;
      }
    }

    // Select all logic
    const selectAllCheckbox = overlay.querySelector('#dola-picker-select-all');
    selectAllCheckbox.addEventListener('change', (e) => {
      if (e.target.checked) {
        allVideos.forEach(v => selectedKeys.add(String(v.vid || v.url)));
      } else {
        selectedKeys.clear();
      }
      renderList(searchInput.value);
    });

    // Search filter
    const searchInput = overlay.querySelector('#dola-picker-search-input');
    searchInput.addEventListener('input', (e) => {
      renderList(e.target.value);
    });

    // Batch download selected button
    const batchDlBtn = overlay.querySelector('#dola-picker-batch-dl-btn');
    batchDlBtn.addEventListener('click', async () => {
      if (selectedKeys.size === 0) {
        alert('Vui lòng tích chọn ít nhất 1 video để tải!');
        return;
      }

      const selectedVideos = allVideos.filter(v => selectedKeys.has(String(v.vid || v.url)));
      batchDlBtn.disabled = true;
      batchDlBtn.style.opacity = '0.75';

      let successCount = 0;
      for (let i = 0; i < selectedVideos.length; i++) {
        const v = selectedVideos[i];
        batchDlBtn.innerHTML = `⏳ Đang tải (${i + 1}/${selectedVideos.length})...`;
        const safePrompt = v.prompt || v.topicTitle || `Video_${i + 1}`;

        try {
          await chrome.runtime.sendMessage({
            type: 'BRANDAI_RAW_VIDEO_DOWNLOAD',
            video: {
              ...v,
              url: v.url,
              source: 'fallback_api',
              prompt: safePrompt,
              force: true
            }
          });
          successCount++;
          showIndividualToast(safePrompt);
        } catch(e) {}

        if (i < selectedVideos.length - 1) {
          await new Promise(r => setTimeout(r, 600));
        }
      }

      batchDlBtn.innerHTML = `✅ Đã tải xong ${successCount} video!`;
      batchDlBtn.style.background = '#059669';

      setTimeout(() => {
        batchDlBtn.disabled = false;
        batchDlBtn.style.opacity = '1';
        batchDlBtn.innerHTML = `📥 Tải các video đã chọn (<span id="dola-picker-checked-count">${selectedKeys.size}</span>)`;
      }, 3000);
    });

    // Close buttons & Click outside & Escape
    const closeBtn = overlay.querySelector('#dola-picker-close-btn');
    const footerCloseBtn = overlay.querySelector('#dola-picker-footer-close-btn');
    const closeModal = () => overlay.remove();

    closeBtn.addEventListener('click', closeModal);
    footerCloseBtn.addEventListener('click', closeModal);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal();
    });
    window.addEventListener('keydown', function escListener(e) {
      if (e.key === 'Escape') {
        closeModal();
        window.removeEventListener('keydown', escListener);
      }
    });

    renderList();
  }

  // 🚀 TÍNH NĂNG KÉO THẢ DI CHUYỂN DOCK TỰ DO
  function makeDockDraggable(dock) {
    if (dock.__draggableInit) return;
    dock.__draggableInit = true;

    try {
      const savedPos = localStorage.getItem('zdola_bulk_dock_pos');
      if (savedPos) {
        const { left, top } = JSON.parse(savedPos);
        if (typeof left === 'number' && typeof top === 'number') {
          dock.style.left = `${left}px`;
          dock.style.top = `${top}px`;
          dock.style.bottom = 'auto';
          dock.style.transform = 'none';
        }
      }
    } catch(e) {}

    let isDragging = false;
    let startX = 0, startY = 0;
    let initialLeft = 0, initialTop = 0;

    dock.addEventListener('mousedown', (e) => {
      if (e.target.closest('button') || e.target.closest('input') || e.target.closest('a')) {
        return;
      }
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;

      const rect = dock.getBoundingClientRect();
      initialLeft = rect.left;
      initialTop = rect.top;

      dock.style.cursor = 'grabbing';
      dock.style.transition = 'none';

      const onMouseMove = (moveEvent) => {
        if (!isDragging) return;
        const dx = moveEvent.clientX - startX;
        const dy = moveEvent.clientY - startY;

        let newLeft = Math.max(10, Math.min(window.innerWidth - dock.offsetWidth - 10, initialLeft + dx));
        let newTop = Math.max(10, Math.min(window.innerHeight - dock.offsetHeight - 10, initialTop + dy));

        dock.style.left = `${newLeft}px`;
        dock.style.top = `${newTop}px`;
        dock.style.bottom = 'auto';
        dock.style.transform = 'none';
      };

      const onMouseUp = () => {
        if (isDragging) {
          isDragging = false;
          dock.style.cursor = 'grab';
          dock.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
          try {
            const rect = dock.getBoundingClientRect();
            localStorage.setItem('zdola_bulk_dock_pos', JSON.stringify({ left: rect.left, top: rect.top }));
          } catch(e) {}
        }
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
      };

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
    });
  }

  const FLOATING_WIDGET_ID = 'brandai-bulk-widget-pill';

  function ensureFloatingWidget() {
    let pill = document.getElementById(FLOATING_WIDGET_ID);
    if (pill) return pill;

    pill = appendElement(document.body || document.documentElement, 'div', {
      id: FLOATING_WIDGET_ID,
      title: 'Bấm để mở Trình Tải Video Hàng Loạt Dola 30s Pro',
      style: [
        'position:fixed',
        'bottom:24px',
        'right:24px',
        'z-index:2147483645',
        'display:flex',
        'align-items:center',
        'gap:8px',
        'padding:8px 16px',
        'border-radius:24px',
        'background:linear-gradient(135deg, rgba(20,26,40,0.95), rgba(10,14,23,0.98))',
        'backdrop-filter:blur(12px)',
        'border:1px solid rgba(251,191,36,0.45)',
        'box-shadow:0 8px 32px rgba(255,126,0,0.3), 0 0 1px 1px rgba(255,255,255,0.08)',
        'color:#f8fafc',
        'font-family:Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        'font-size:12px',
        'font-weight:700',
        'cursor:pointer',
        'transition:all 0.25s ease',
        'user-select:none'
      ].join(';'),
      html: `
        <div style="width:20px;height:20px;border-radius:6px;background:linear-gradient(135deg,#ff7e00,#fbbf24);display:flex;align-items:center;justify-content:center;font-size:11px;">⚡</div>
        <span>Dola 30s Pro</span>
        <span id="brandai-pill-count-badge" style="background:rgba(255,126,0,0.25);border:1px solid rgba(251,191,36,0.4);color:#fed7aa;padding:1px 6px;border-radius:10px;font-size:10.5px;">📦 0</span>
      `
    });

    pill.addEventListener('mouseenter', () => {
      pill.style.transform = 'translateY(-2px) scale(1.03)';
      pill.style.borderColor = '#fbbf24';
      pill.style.boxShadow = '0 12px 36px rgba(255,126,0,0.5)';
    });
    pill.addEventListener('mouseleave', () => {
      pill.style.transform = 'none';
      pill.style.borderColor = 'rgba(251,191,36,0.45)';
      pill.style.boxShadow = '0 8px 32px rgba(255,126,0,0.3)';
    });

    pill.addEventListener('click', () => {
      setBulkMode(true);
    });

    return pill;
  }

  function ensureBulkDock() {
    let dock = document.getElementById(BULK_DOCK_ID);
    if (dock) return dock;

    dock = appendElement(document.body || document.documentElement, 'div', {
      id: BULK_DOCK_ID,
      style: [
        'position:fixed',
        'bottom:24px',
        'left:50%',
        'transform:translateX(-50%)',
        'z-index:2147483646',
        'display:flex',
        'align-items:center',
        'gap:12px',
        'padding:10px 18px',
        'border-radius:18px',
        'background:linear-gradient(135deg, rgba(17,24,38,0.96), rgba(10,14,23,0.98))',
        'backdrop-filter:blur(16px)',
        'border:1px solid rgba(251,191,36,0.5)',
        'box-shadow:0 14px 44px rgba(0,0,0,0.65), 0 0 20px rgba(255,126,0,0.25)',
        'color:#f8fafc',
        'font-family:Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        'font-size:12.5px',
        'user-select:none',
        'transition:all 0.25s cubic-bezier(0.4, 0, 0.2, 1)'
      ].join(';'),
      html: `
        <div style="cursor:grab;color:#64748b;font-size:14px;padding:0 2px;" title="Kéo thả để di chuyển vị trí">⋮⋮</div>
        <div id="brandai-dock-icon-box" style="width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#ff7e00,#fbbf24);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;box-shadow:0 0 14px rgba(255,126,0,0.5);">
          <span id="brandai-dock-icon">📦</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:1px;">
          <span id="brandai-dock-title" style="color:#f8fafc;font-weight:800;display:flex;align-items:center;gap:6px;">
            <span id="brandai-dock-title-text">Trình Tải Video Hàng Loạt</span>
            <span id="brandai-dock-count-badge" style="background:rgba(255,126,0,0.22);color:#fef08a;padding:1px 8px;border-radius:8px;font-size:11px;border:1px solid rgba(251,191,36,0.45);font-weight:800;">Đã quét: 0</span>
          </span>
          <span id="brandai-dock-subtitle" style="color:#94a3b8;font-size:11px;">Tự động tạm dừng • Cuộn chat để bắt thêm video cũ</span>
        </div>
        <div id="brandai-dock-actions" style="display:flex;align-items:center;gap:8px;margin-left:8px;">
          <button id="brandai-dock-scroll-btn" style="background:rgba(255,255,255,0.08);border:1px solid rgba(251,191,36,0.35);color:#fed7aa;padding:7px 11px;border-radius:9px;font-weight:700;font-size:11.5px;cursor:pointer;" title="Cuộn trang chat để trích xuất thêm các video cũ trong lịch sử">
            📜 Cuộn Bắt Video Cũ
          </button>
          <button id="brandai-dock-picker-btn" style="background:rgba(99,102,241,0.22);border:1px solid rgba(129,140,248,0.55);color:#c7d2fe;padding:7px 12px;border-radius:9px;font-weight:700;font-size:11.5px;cursor:pointer;display:inline-flex;align-items:center;gap:5px;" title="Xem ảnh thumbnail các video đã bắt được, tự chọn từng video để tải lẻ">
            📋 Chọn Từng Video (0)
          </button>
          <button id="brandai-dock-download-new-btn" style="background:linear-gradient(135deg,#10b981,#059669);border:1px solid rgba(52,211,153,0.5);color:#ffffff;padding:7px 13px;border-radius:9px;font-weight:800;font-size:11.5px;cursor:pointer;box-shadow:0 4px 14px rgba(16,185,129,0.4);display:inline-flex;align-items:center;gap:5px;" title="Chỉ tải các video vừa tạo mới trong phiên này (tải lẻ từng file MP4 không logo, không nén ZIP)">
            ⚡ Tải Lẻ Video Mới (0)
          </button>
          <button id="brandai-dock-download-btn" style="background:linear-gradient(135deg,#ff7e00,#fbbf24);border:none;color:#000;padding:7px 12px;border-radius:9px;font-weight:800;font-size:11.5px;cursor:pointer;box-shadow:0 4px 14px rgba(255,126,0,0.4);" title="Tải toàn bộ video đã quét được đóng gói thành file ZIP">
            📦 Tải File ZIP (0)
          </button>
          <button id="brandai-dock-stop-btn" style="display:none;background:rgba(239,68,68,0.25);border:1px solid rgba(239,68,68,0.6);color:#fca5a5;padding:7px 14px;border-radius:9px;font-weight:700;cursor:pointer;font-size:11.5px;">
            ⏹️ Dừng cuộn
          </button>
          <button id="brandai-dock-close-btn" style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);color:#cbd5e1;padding:6px 10px;border-radius:8px;cursor:pointer;" title="Thu nhỏ">✕</button>
        </div>
      `
    });

    makeDockDraggable(dock);

    const scrollBtn = dock.querySelector('#brandai-dock-scroll-btn');
    if (scrollBtn) {
      scrollBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        startAutoScrollChat();
      });
    }

    const pickerBtn = dock.querySelector('#brandai-dock-picker-btn');
    if (pickerBtn) {
      pickerBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openVideoPickerModal();
      });
    }

    const dlNewBtn = dock.querySelector('#brandai-dock-download-new-btn');
    if (dlNewBtn) {
      dlNewBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        triggerIndividualNewVideosDownload();
      });
    }

    const dlBtn = dock.querySelector('#brandai-dock-download-btn');
    if (dlBtn) {
      dlBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        triggerManualBulkDownload();
      });
    }

    const stopBtn = dock.querySelector('#brandai-dock-stop-btn');
    if (stopBtn) {
      stopBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        stopAutoScrollChat(false);
      });
    }

    const closeBtn = dock.querySelector('#brandai-dock-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        setBulkMode(false);
      });
    }

    return dock;
  }

  let lastScanTime = 0;

  function updateBulkDock(completed = false) {
    const now = Date.now();
    if (now - lastScanTime >= 600) {
      lastScanTime = now;
      injectScrollStyles();
      scanDomAndChatVideos();
    }

    const totalCount = extractedVideosPool.size;
    const newVideos = getNewlyCreatedVideos();
    const newCount = newVideos.length;

    const pill = ensureFloatingWidget();
    if (pill) {
      const pillBadge = pill.querySelector('#brandai-pill-count-badge');
      if (pillBadge) {
        const text = newCount > 0 ? `📦 ${totalCount} (⚡ ${newCount} mới)` : `📦 ${totalCount}`;
        if (pillBadge.textContent !== text) {
          pillBadge.textContent = text;
        }
      }
      pill.style.display = isBulkModeActive ? 'none' : 'flex';
    }

    if (!isBulkModeActive) {
      const existingDock = document.getElementById(BULK_DOCK_ID);
      if (existingDock) existingDock.remove();
      return;
    }

    const dock = ensureBulkDock();
    dock.style.display = 'flex';

    const iconEl = dock.querySelector('#brandai-dock-icon');
    const iconBox = dock.querySelector('#brandai-dock-icon-box');
    const titleText = dock.querySelector('#brandai-dock-title-text');
    const countBadge = dock.querySelector('#brandai-dock-count-badge');
    const subtitle = dock.querySelector('#brandai-dock-subtitle');
    const scrollBtn = dock.querySelector('#brandai-dock-scroll-btn');
    const dlNewBtn = dock.querySelector('#brandai-dock-download-new-btn');
    const dlBtn = dock.querySelector('#brandai-dock-download-btn');
    const stopBtn = dock.querySelector('#brandai-dock-stop-btn');

    if (isAutoScrolling) {
      if (iconEl) {
        iconEl.textContent = '🔄';
        iconEl.style.animation = 'brandai-spin 1s linear infinite';
        iconEl.style.display = 'inline-block';
      }
      if (iconBox) {
        iconBox.style.background = 'linear-gradient(135deg,#ff7e00,#fbbf24)';
        iconBox.style.boxShadow = '0 0 14px rgba(255,126,0,0.6)';
      }
      if (titleText) {
        titleText.textContent = 'Đang tự động cuộn chat để bắt video...';
        titleText.style.color = '#fef08a';
      }
      if (countBadge) countBadge.style.display = 'none';
      if (subtitle) {
        subtitle.innerHTML = `Đã trích xuất <b style="color:#34d399;">${totalCount}</b> video Master không logo`;
      }
      if (scrollBtn) scrollBtn.style.display = 'none';
      const pickerBtn = dock.querySelector('#brandai-dock-picker-btn');
      if (pickerBtn) {
        pickerBtn.style.display = 'none';
      }
      if (dlNewBtn) dlNewBtn.style.display = 'none';
      if (dlBtn) dlBtn.style.display = 'none';
      if (stopBtn) stopBtn.style.display = 'inline-flex';
      return;
    }

    if (stopBtn) stopBtn.style.display = 'none';

    const pickerBtn = dock.querySelector('#brandai-dock-picker-btn');
    if (pickerBtn) {
      pickerBtn.style.display = 'inline-flex';
      pickerBtn.textContent = `📋 Chọn Từng Video (${totalCount})`;
    }

    if (completed) {
      if (iconEl) {
        iconEl.textContent = '✅';
        iconEl.style.animation = 'none';
      }
      if (iconBox) {
        iconBox.style.background = 'linear-gradient(135deg,#10b981,#059669)';
        iconBox.style.boxShadow = '0 0 14px rgba(16,185,129,0.6)';
      }
      if (titleText) {
        titleText.textContent = 'Đã quét xong toàn bộ video trong chat!';
        titleText.style.color = '#86efac';
      }
      if (countBadge) countBadge.style.display = 'none';
      if (subtitle) {
        subtitle.innerHTML = `Sẵn sàng tải <b style="color:#34d399;">${newCount} video mới</b> • <b style="color:#fef08a;">${totalCount} tổng</b>`;
      }
      if (scrollBtn) scrollBtn.style.display = 'none';
      if (dlNewBtn) {
        dlNewBtn.style.display = 'inline-flex';
        dlNewBtn.textContent = `⚡ Tải Lẻ Video Mới (${newCount})`;
      }
      if (dlBtn) {
        dlBtn.style.display = 'inline-flex';
        dlBtn.textContent = `📦 Tải File ZIP (${totalCount} Video)`;
      }
    } else {
      if (iconEl) {
        iconEl.textContent = '📦';
        iconEl.style.animation = 'none';
      }
      if (iconBox) {
        iconBox.style.background = 'linear-gradient(135deg,#ff7e00,#fbbf24)';
        iconBox.style.boxShadow = '0 0 14px rgba(255,126,0,0.5)';
      }
      if (titleText) {
        titleText.textContent = 'Trình Tải Video Dola 30s Pro';
        titleText.style.color = '#f8fafc';
      }
      if (countBadge) {
        countBadge.style.display = 'inline-block';
        countBadge.textContent = `Đã quét: ${totalCount} (${newCount} mới)`;
      }
      if (subtitle) {
        subtitle.innerHTML = `⚡ Tải lẻ video mới (không ZIP) • Cuộn chat để bắt thêm video cũ`;
      }
      if (scrollBtn) scrollBtn.style.display = 'inline-flex';
      if (dlNewBtn) {
        dlNewBtn.style.display = 'inline-flex';
        dlNewBtn.textContent = `⚡ Tải Lẻ Video Mới (${newCount})`;
      }
      if (dlBtn) {
        dlBtn.style.display = 'inline-flex';
        dlBtn.textContent = `📦 Tải File ZIP (${totalCount})`;
      }
    }
  }

  function showIndividualToast(videoName = 'Video không logo') {
    try {
      const existing = document.getElementById(TOAST_ID);
      if (existing) existing.remove();

      const toast = appendElement(document.body || document.documentElement, 'div', {
        id: TOAST_ID,
        style: [
          'position:fixed',
          'bottom:24px',
          'right:24px',
          'z-index:2147483647',
          'display:flex',
          'align-items:center',
          'gap:12px',
          'padding:12px 18px',
          'border-radius:14px',
          'background:rgba(17,24,39,0.96)',
          'backdrop-filter:blur(12px)',
          'border:1px solid rgba(129,140,248,0.5)',
          'box-shadow:0 14px 40px rgba(0,0,0,0.6)',
          'color:#f8fafc',
          'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
          'font-size:13px',
          'pointer-events:none',
          'transition:all 0.3s ease',
          'user-select:none'
        ].join(';')
      });

      toast.innerHTML = `
        <div style="width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;box-shadow:0 0 12px rgba(99,102,241,0.5);">
          ⚡
        </div>
        <div style="display:flex;flex-direction:column;gap:2px;">
          <div style="font-weight:700;color:#f8fafc;display:flex;align-items:center;gap:6px;">
            <span>Đã tải video không logo!</span>
            <span style="background:rgba(52,211,153,0.18);color:#34d399;padding:1px 6px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(52,211,153,0.35);">1080P Master</span>
          </div>
          <span style="color:#94a3b8;font-size:11.5px;max-width:280px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
            ${String(videoName || 'Đã lưu vào Downloads/TheBrandAI_Videos').replace(/</g, '&lt;')}
          </span>
        </div>
      `;

      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px)';
        setTimeout(() => toast.remove(), 350);
      }, 3500);
    } catch {}
  }

  // 🎯 LẮNG NGHE SỰ KIỆN: CHỈ CHẤP NHẬN FALLBACK_API (MASTER KHÔNG LOGO), KHÔNG TẢI TRÙNG LẶP
  window.addEventListener('DOLA_VIDEO_EXTRACTED', event => {
    const video = event && event.detail;

    if (!video || video.source !== 'fallback_api' || !video.url) return;

    const cleanUrl = toUnwatermarkedMasterUrl(String(video.url).trim());
    if (!/^https?:\/\//i.test(cleanUrl)) return;

    const key = String(video.vid || cleanUrl);
    const isNew = isInitialHistoryCaptured
      ? (!initialHistoryKeys.has(key) && !initialHistoryKeys.has(cleanUrl))
      : (Date.now() - sessionStartTime > 2500);

    if (isNew) {
      newlyCreatedVideoKeys.add(key);
      newlyCreatedVideoKeys.add(cleanUrl);
    }

    const videoObj = {
      ...video,
      url: cleanUrl,
      isNewVideo: Boolean(isNew),
      detectedAt: Date.now(),
      seedanceBatch: seedanceBatchContext || window.__SEEDANCE_BATCH_CONTEXT__ || null
    };

    extractedVideosPool.set(key, videoObj);
    injectSingleVideoDownloadButtons();

    if (isBulkModeActive) {
      updateBulkDock();
      return;
    }

    if (seenMedia.has(key) || seenMedia.has(cleanUrl) || cancelledMedia.has(key) || cancelledMedia.has(cleanUrl)) return;

    // Chế độ "Chỉ tải lẻ video vừa tạo": Bỏ qua các video cũ trong lịch sử chat
    if (settingOnlyNewVideos && !videoObj.isNewVideo) {
      return;
    }

    seenMedia.add(key);
    seenMedia.add(cleanUrl);

    queuePageVideo({
      ...videoObj,
      pageUrl: location.href,
      prompt: video.prompt || video.topicTitle || video.title || '',
      seedanceBatch: seedanceBatchContext || window.__SEEDANCE_BATCH_CONTEXT__ || null
    });
  });

  window.addEventListener('message', event => {
    if (event.source !== window || event.data?.type !== 'SEEDANCE_BATCH_CONTEXT') return;
    const ctx = event.data.context;
    if (ctx && typeof ctx === 'object' && ctx.autoDownload === true) {
      seedanceBatchContext = ctx;
      window.__SEEDANCE_BATCH_CONTEXT__ = ctx;
    }
  });

  chrome.runtime.onMessage.addListener(message => {
    if (message?.type === 'BRANDAI_SET_DOWNLOAD_PREFERENCES') {
      if (typeof message.onlyNewVideos === 'boolean') {
        settingOnlyNewVideos = message.onlyNewVideos;
      }
      if (typeof message.showVideoBtn === 'boolean') {
        settingShowVideoBtn = message.showVideoBtn;
        injectSingleVideoDownloadButtons();
      }
      updateBulkDock();
      return;
    }
    if (message?.type === 'BRANDAI_START_CHAT_SCROLL') {
      if (!isBulkModeActive) {
        setBulkMode(true);
      }
      startAutoScrollChat();
      return;
    }

    if (message?.type === 'BRANDAI_SET_BULK_MODE') {
      setBulkMode(message.enabled);
      return;
    }

    if (message?.type === 'BRANDAI_RAW_VIDEO_DOWNLOAD_FAILED') {
      releaseVideo(message);
      return;
    }

    if (message?.type === 'BRANDAI_RAW_VIDEO_DOWNLOAD_VERIFIED') {
      const cleanName = String(message.filename || 'TheBrandAI_Videos')
        .replace(/^TheBrandAI_Videos\//i, '')
        .replace(/\.mp4$/i, '');
      showIndividualToast(cleanName);
      return;
    }

    if (message?.type === 'BRANDAI_RAW_VIDEO_BATCH_DOWNLOAD_FAILED') {
      const isCancelled = message.cancelled ||
        message.error?.toLowerCase().includes('cancel') ||
        (message.buildId && cancelledBuildIds.has(message.buildId));

      if (isCancelled) {
        for (const video of message.videos || []) {
          const k = mediaKey(video);
          const u = String(video?.url || '');
          if (k) cancelledMedia.add(k);
          if (u) cancelledMedia.add(u);
        }
        return;
      }

      for (const video of message.videos || []) releaseVideo(video);
      updateZipOverlay({ stage: 'error', error: message.error });
      return;
    }

    if (message?.type === 'BRANDAI_VIDEO_ZIP_PROGRESS') {
      if (message.buildId && cancelledBuildIds.has(message.buildId)) {
        clearTimeout(overlayHideTimer);
        const overlay = document.getElementById(ZIP_OVERLAY_ID);
        if (overlay) overlay.remove();
        const badge = document.getElementById(MINI_BADGE_ID);
        if (badge) badge.remove();
        return;
      }
      if (message.stage === 'cancelled') {
        clearTimeout(overlayHideTimer);
        const overlay = document.getElementById(ZIP_OVERLAY_ID);
        if (overlay) overlay.remove();
        const badge = document.getElementById(MINI_BADGE_ID);
        if (badge) badge.remove();
        return;
      }
      updateZipOverlay(message);
      return;
    }

    if (message?.type === 'BRANDAI_RAW_VIDEO_ZIP_VERIFIED') {
      if (message.buildId && cancelledBuildIds.has(message.buildId)) return;
      updateZipOverlay({ stage: 'complete', percent: 100 });
    }
  });

  setInterval(() => {
    if (isBulkModeActive) {
      updateBulkDock();
    }
    injectSingleVideoDownloadButtons();
  }, 1000);

  // Setup MutationObserver để gắn nút "Tải video này" ngay khi khung video vừa render
  const domVideoObserver = new MutationObserver(() => {
    injectSingleVideoDownloadButtons();
  });

  if (document.body) {
    domVideoObserver.observe(document.body, { childList: true, subtree: true });
  } else {
    document.addEventListener('DOMContentLoaded', () => {
      domVideoObserver.observe(document.body || document.documentElement, { childList: true, subtree: true });
    });
  }

  // Lắng nghe phản hồi media từ extractor.js (MAIN world)
  window.addEventListener('DOLA_CHAT_MEDIA_RESPONSE', event => {
    const videos = event?.detail?.videos || [];
    if (Array.isArray(videos)) {
      for (const v of videos) {
        if (v && v.url && v.source === 'fallback_api') {
          const cleanUrl = toUnwatermarkedMasterUrl(String(v.url).trim());
          const k = String(v.vid || cleanUrl);
          if (!extractedVideosPool.has(k)) {
            extractedVideosPool.set(k, {
              ...v,
              url: cleanUrl,
              source: 'fallback_api',
              pageUrl: location.href
            });
          }
        }
      }
      updateBulkDock();
      injectSingleVideoDownloadButtons();
    }
  });

  // Query main world extractor on startup
  setTimeout(() => {
    try {
      window.dispatchEvent(new CustomEvent('DOLA_GET_CHAT_MEDIA'));
    } catch(e) {}
  }, 600);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      injectScrollStyles();
      if (isBulkModeActive) updateBulkDock();
      injectSingleVideoDownloadButtons();
      try { window.dispatchEvent(new CustomEvent('DOLA_GET_CHAT_MEDIA')); } catch(e) {}
    });
  } else {
    injectScrollStyles();
    if (isBulkModeActive) updateBulkDock();
    injectSingleVideoDownloadButtons();
    try { window.dispatchEvent(new CustomEvent('DOLA_GET_CHAT_MEDIA')); } catch(e) {}
  }
})();
