/* ============================================================================
   DOLA 30S STUDIO PRO - BACKGROUND SERVICE WORKER
   Tác giả & Bản quyền: LÊ VIỆT TÙNG | Zalo / Hotline: 0915967790
   ============================================================================ */

/* 1. Import Sub-modules */
importScripts('bulk-account-manager.js');
importScripts('reliable-watermark-free-downloader.js');
importScripts('image-overlay-background.js');
importScripts('facebook-via-manager.js');
importScripts('proxy-extension-manager.js');

/* 2. Universal Watermark-Free Raw Master Auto-Downloader */
const brandAiRawDownloadKeys = new Set();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message) return false;

  const isDownloadReq = (
    message.type === 'AUTO_DOWNLOAD_VIDEO' ||
    message.type === 'AUTO_DOWNLOAD_COMPLETED' ||
    message.action === 'fast_download' ||
    message.action === 'ZDOLA_CLEAN_AND_DOWNLOAD' ||
    message.action === 'download_video'
  );
  if (!isDownloadReq) return false;

  const video = message.video || message || {};
  const url = String(video.url || message.url || '').trim();
  if (!/^https?:\/\//i.test(url)) {
    sendResponse({ ok: false, downloaded: false, reason: 'Invalid or missing video URL' });
    return false;
  }

  const key = String(video.vid || url);
  if (!message.force && (brandAiRawDownloadKeys.has(key) || brandAiRawDownloadKeys.has(url))) {
    sendResponse({ ok: true, downloaded: false, reason: 'Already downloaded' });
    return false;
  }
  brandAiRawDownloadKeys.add(key);
  brandAiRawDownloadKeys.add(url);

  const batch = video.seedanceBatch || message.seedanceBatch || {};
  const rawPrompt = String(video.prompt || message.filename || video.topicTitle || video.title || 'Video_30s').trim();
  const strippedPrompt = rawPrompt.replace(/^(?:generated\s+videos?|generated|create\s+videos?|prompt|video)\s*[:：\-–—]\s*/i, '').trim();
  const cleanPrompt = (strippedPrompt || rawPrompt).replace(/[\r\n\t]+/g, ' ').replace(/[<>:"/\\|?*\x00-\x1F]/g, '').trim();
  const promptSlice = (cleanPrompt || 'video').slice(0, 45).trim();
  const safeName = promptSlice.replace(/\s+/g, '_').replace(/^_+|_+$/g, '') || `video_${Date.now()}`;
  const promptTag = Number(batch.promptNumber) > 0 ? `prompt_${String(batch.promptNumber).padStart(2, '0')}_` : '';
  const accountTag = String(batch.accountName || '').replace(/[^A-Za-z0-9_-]+/g, '_').slice(0, 40);
  const batchPrefix = `${promptTag}${accountTag ? `${accountTag}_` : ''}${safeName}.mp4`;
  const filename = batch.autoDownload === true
    ? batchPrefix
    : `Dola_Videos_1080P/${batchPrefix}`;

  chrome.downloads.download({ url, filename, saveAs: false, conflictAction: 'uniquify' }, (downloadId) => {
    const error = chrome.runtime.lastError;
    if (error) {
      brandAiRawDownloadKeys.delete(key);
      brandAiRawDownloadKeys.delete(url);
      sendResponse({ ok: false, downloaded: false, error: error.message });
      return;
    }

    // Save recent download to storage
    chrome.storage.local.get(['zdola_recent_downloads'], (res) => {
      const list = Array.isArray(res?.zdola_recent_downloads) ? res.zdola_recent_downloads : [];
      list.unshift({
        filename: `${safeName}.mp4`,
        prompt: cleanPrompt,
        promptNumber: Number(batch.promptNumber) || null,
        accountName: accountTag,
        batchId: String(batch.batchId || ''),
        jobId: String(batch.jobId || ''),
        timestamp: Date.now(),
        url
      });
      chrome.storage.local.set({ zdola_recent_downloads: list.slice(0, 30) });
    });

    try {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon128.png',
        title: '🎬 Đã bắt đầu tải video Dola',
        message: `${batchPrefix}\nĐã lưu vào thư mục tải chung của tool.`,
        priority: 1
      });
    } catch (e) {}

    sendResponse({ ok: true, downloaded: true, downloadId, filename });
  });
  return true;
});

/* 3. Synchronized Multi-Tab Click Mirroring Relay */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.action === 'broadcast_mirrored_click') {
    const targetData = message.targetData;
    const sourceTabId = sender.tab ? sender.tab.id : null;
    chrome.tabs.query({ url: ['*://*.dola.com/*', '*://dola.com/*'] }, (tabs) => {
      if (!tabs) return;
      tabs.forEach((tab) => {
        if (tab.id && tab.id !== sourceTabId) {
          chrome.tabs.sendMessage(tab.id, { action: 'execute_mirrored_click', targetData }).catch(() => {});
        }
      });
    });
    sendResponse({ ok: true });
    return true;
  }
});

/* 4. Sequential Multi-Tab Prompt Distribute & Paste Handler */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.action === 'paste_all_tabs_sequentially') {
    const STORAGE_KEY = 'ctb_saved_prompts';
    chrome.storage.local.get([STORAGE_KEY], (res) => {
      const saved = Array.isArray(res?.[STORAGE_KEY]) ? res[STORAGE_KEY] : [];
      let uncompleted = saved.filter(p => !p.done);
      if (!uncompleted.length) uncompleted = saved;

      if (!uncompleted.length) {
        sendResponse({ success: false, reason: 'No prompts found in list' });
        return;
      }

      chrome.tabs.query({ url: ['*://*.dola.com/*', '*://dola.com/*'] }, (tabs) => {
        if (!tabs || !tabs.length) {
          sendResponse({ success: false, reason: 'No Dola tabs open' });
          return;
        }

        let pastedCount = 0;
        tabs.forEach((tab, index) => {
          if (!tab.id) return;
          const promptObj = uncompleted[index % uncompleted.length];
          if (promptObj) {
            pastedCount++;
            const realIdx = saved.indexOf(promptObj);
            if (realIdx !== -1) saved[realIdx].done = true;

            chrome.tabs.sendMessage(tab.id, {
              action: 'paste_specific_prompt',
              text: promptObj.text,
              tabIndex: index + 1,
              totalTabs: tabs.length
            }).catch(() => {});
          }
        });

        chrome.storage.local.set({ [STORAGE_KEY]: saved }, () => {
          sendResponse({ success: true, pastedCount, tabCount: tabs.length });
        });
      });
    });
    return true;
  }
});

/* 5. Enable side panel open on action click */
chrome.runtime.onInstalled.addListener(() => {
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  }
});
if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
}

/* 6. VIDEO_COMPLETED Handler (Agent Pro Video Detection) */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== 'VIDEO_COMPLETED') return false;

  const { requestId, videoUrl, videoType, detectedAt, chatUrl, prompt } = message;
  console.log(`[Background] Video completed for request ${requestId}: ${videoUrl}`);

  if (!videoUrl || !/^https?:\/\//i.test(videoUrl)) {
    sendResponse({ ok: false, reason: 'Invalid video URL' });
    return false;
  }

  // 1. Save to completed videos archive
  chrome.storage.local.get(['zdola_completed_videos', 'zdola_recent_downloads', 'zdola_auto_download'], (res) => {
    const list = Array.isArray(res?.zdola_completed_videos) ? res.zdola_completed_videos : [];
    const record = {
      requestId: requestId || 'unknown',
      prompt: prompt || 'Dola AI Agent Pro Video',
      videoUrl,
      videoType: videoType || 'unknown',
      detectedAt: detectedAt || Date.now(),
      chatUrl: chatUrl || ''
    };
    list.unshift(record);
    chrome.storage.local.set({ zdola_completed_videos: list.slice(0, 50) });

    // 2. Add to recent downloads list in popup
    const recents = Array.isArray(res?.zdola_recent_downloads) ? res.zdola_recent_downloads : [];
    const safePrompt = (prompt || 'Agent_Video').replace(/[\r\n\t]+/g, ' ').replace(/[<>:"/\\|?*\x00-\x1F]/g, '').slice(0, 40).trim();
    const filename = `Agent_${requestId || Date.now()}.mp4`;
    recents.unshift({
      filename,
      prompt: safePrompt,
      timestamp: Date.now(),
      url: videoUrl
    });
    chrome.storage.local.set({ zdola_recent_downloads: recents.slice(0, 30) });

    // 3. Do not auto-download DOM preview videos (they contain watermarks).
    // The reliable watermark-free downloader handles unwatermarked fallback_api streams exclusively.
  });

  // 4. Show Chrome desktop notification
  try {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icon128.png',
      title: '🎬 AI Agent Pro: Video Hoàn Thành!',
      message: `Request: ${requestId || 'AI Agent'}\nĐã bắt link & tải về Downloads/Dola_Videos_1080P/`,
      priority: 2
    });
  } catch (e) {}

  sendResponse({ ok: true, videoUrl });
  return true;
});

