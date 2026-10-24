// ==========================================================================
// DOLA 30S STUDIO PRO - ADVANCED AI VIDEO SUITE CONTROLLER
// Tác giả: LÊ VIỆT TÙNG | Zalo: 0915967790 | Facebook: https://www.facebook.com/tungbinh.38/
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // Global State
  let activeRatio = '9:16';
  let activeDuration = 30;
  let activeModel = '2.5';
  let activeTabName = 'tab-generate';
  let savedPrompts = [];
  let currentPromptFilter = 'all';
  let savedMultiRequests = [];
  let currentMreqFilter = 'all';
  let isPipelineRunning = false;
  let isPipelinePaused = false;
  let singleRefImage = null; // for Tab 1
  let mreqDraftImage = null;  // for Multi-Request draft
  let savedProfiles = {};
  let recentDownloads = [];
  let activeProfileName = 'Mặc định';

  // Sample Prompts Library
  const samplePrompts = [
    "Cinematic 8k shot of a futuristic cyberpunk neon samurai in heavy rain, ultra-realistic reflections, 30s dynamic camera movement, octane render.",
    "Hyper-realistic cinematic slow motion of a majestic dragon flying over snow-covered crystal mountains at golden hour sunrise, dramatic volumetric lighting, 8k.",
    "Fashion model in iridescent avant-garde neon holographic dress walking through cybernetic botanical garden with glowing butterflies, cinematic 30s commercial.",
    "Breathtaking drone view flying through a lush tropical waterfall canyon at sunset, crystal clear turquoise water, photorealistic 8k 30s video.",
    "Fast action cyberpunk motorcycle speeding through futuristic Tokyo highway at night with neon motion blur trails, dynamic low angle camera, 8k 60fps."
  ];

  // ========================================================================
  // 1. NAVIGATION TABS CONTROLLER
  // ========================================================================
  const navButtons = document.querySelectorAll('.nav-btn');
  const tabContents = {
    'tab-generate': document.getElementById('view-generate'),
    'tab-multi-req': document.getElementById('view-multi-req'),
    'tab-prompts': document.getElementById('view-prompts'),
    'tab-accounts': document.getElementById('view-accounts'),
    'tab-proxy': document.getElementById('view-proxy'),
    'tab-settings': document.getElementById('view-settings'),
    'tab-logs': document.getElementById('view-logs')
  };

  function switchTab(tabId) {
    activeTabName = tabId;
    navButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    Object.entries(tabContents).forEach(([id, element]) => {
      if (element) {
        element.classList.toggle('hidden', id !== tabId);
      }
    });

    addLog('TAB', `Đã chuyển sang tab: ${tabId.replace('tab-', '').toUpperCase()}`, 'info');
    if (typeof loadDolaTabsList === 'function' && (tabId === 'tab-accounts' || tabId === 'tab-generate')) {
      loadDolaTabsList();
    }
  }

  navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.tab) switchTab(btn.dataset.tab);
    });
  });

  // ========================================================================
  // 2. TERMINAL LOGGING SYSTEM
  // ========================================================================
  const logsContainer = document.getElementById('logs-terminal-container');
  const btnCopyLogs = document.getElementById('logs-btn-copy');
  const btnClearLogs = document.getElementById('logs-btn-clear');

  function getTimestamp() {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
  }

  function addLog(tag, message, type = 'info') {
    if (!logsContainer) return;
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
      <span class="log-time">[${getTimestamp()}]</span>
      <span class="log-tag ${type}">[${tag}]</span>
      <span>${String(message).replace(/</g, '&lt;')}</span>
    `;
    logsContainer.appendChild(entry);
    logsContainer.scrollTop = logsContainer.scrollHeight;
  }

  if (btnCopyLogs) {
    btnCopyLogs.addEventListener('click', () => {
      navigator.clipboard.writeText(logsContainer.innerText).then(() => {
        addLog('LOGS', 'Đã sao chép nhật ký vào clipboard!', 'success');
      });
    });
  }

  if (btnClearLogs) {
    btnClearLogs.addEventListener('click', () => {
      logsContainer.innerHTML = '';
      addLog('LOGS', 'Nhật ký đã được xóa.', 'info');
    });
  }

  // ========================================================================
  // 3. TAB 1: TẠO VIDEO 30S (ẢNH THAM CHIẾU + PROMPT GỢI Ý MODEL PRO)
  // ========================================================================
  const genRefImgInput = document.getElementById('gen-ref-image-input');
  const genBtnChooseImg = document.getElementById('gen-btn-choose-img');
  const genBtnAttachRef = document.getElementById('gen-btn-attach-ref');
  const genBtnClearImg = document.getElementById('gen-btn-clear-img');
  const genRefPreviewBox = document.getElementById('gen-ref-preview-box');

  const genPromptInput = document.getElementById('gen-prompt-input');
  const genCharCount = document.getElementById('gen-char-count');
  const genBtnPaste = document.getElementById('gen-btn-paste');
  const genBtnClear = document.getElementById('gen-btn-clear');
  const genBtnSample = document.getElementById('gen-btn-sample');
  const genBtnQuickGenerate = document.getElementById('btn-quick-generate');
  const genToggleAutoDl = document.getElementById('gen-toggle-autodownload');
  const genRatioButtons = document.querySelectorAll('.ratio-btn');
  const genRecentList = document.getElementById('gen-recent-list');
  const genRecentCountBadge = document.getElementById('gen-recent-count');

  // Engine Mode Selection (Studio 30s vs AI Agent Pro 15s)
  let currentEngineMode = 'studio'; // 'studio' | 'agent'
  const btnModeStudio = document.getElementById('gen-mode-studio');
  const btnModeAgent = document.getElementById('gen-mode-agent');
  const genEngineDesc = document.getElementById('gen-engine-desc');
  const studioConfigPanel = document.getElementById('studio-config-panel');
  const agentConfigPanel = document.getElementById('agent-config-panel');
  const labelCurrentRatio = document.getElementById('label-current-ratio');
  const labelCurrentDuration = document.getElementById('label-current-duration');
  const labelCurrentModel = document.getElementById('label-current-model');

  function setEngineMode(mode) {
    currentEngineMode = mode;
    chrome.storage.local.set({ zdola_engine_mode: mode });
    if (btnModeStudio && btnModeAgent) {
      if (mode === 'agent') {
        btnModeAgent.classList.add('active');
        btnModeAgent.style.borderColor = 'var(--primary)';
        btnModeAgent.style.background = 'rgba(255,126,0,0.18)';
        btnModeAgent.style.color = '#fbbf24';

        btnModeStudio.classList.remove('active');
        btnModeStudio.style.borderColor = 'rgba(255,255,255,0.12)';
        btnModeStudio.style.background = 'rgba(255,255,255,0.05)';
        btnModeStudio.style.color = '#94a3b8';

        // Ẩn panel cấu hình Studio (Tỷ lệ & Thời lượng), hiện panel thông tin tự động của Agent Pro
        if (studioConfigPanel) studioConfigPanel.style.display = 'none';
        if (agentConfigPanel) agentConfigPanel.style.display = 'block';

        if (genEngineDesc) genEngineDesc.innerHTML = '💎 <b>Chế độ AI Agent Pro:</b> KHÔNG TỐN CREDIT · Model Seedance 2.5 Pro · 15 Giây · Tạo số lượng lớn không giới hạn!';
        if (genBtnQuickGenerate) genBtnQuickGenerate.innerHTML = '<span>🚀 TẠO QUA AI AGENT PRO (FREE CREDIT)</span>';
        addLog('MODE', 'Đã chuyển sang: 🤖 AI Agent Pro (Không tốn credit · Model 2.5 15s)', 'success');
      } else {
        btnModeStudio.classList.add('active');
        btnModeStudio.style.borderColor = 'var(--primary)';
        btnModeStudio.style.background = 'rgba(255,126,0,0.18)';
        btnModeStudio.style.color = '#fbbf24';

        btnModeAgent.classList.remove('active');
        btnModeAgent.style.borderColor = 'rgba(255,255,255,0.12)';
        btnModeAgent.style.background = 'rgba(255,255,255,0.05)';
        btnModeAgent.style.color = '#94a3b8';

        // Hiện panel cấu hình Studio (Model, Tỷ lệ & Thời lượng), ẩn panel thông tin Agent
        if (studioConfigPanel) studioConfigPanel.style.display = 'block';
        if (agentConfigPanel) agentConfigPanel.style.display = 'none';

        if (genEngineDesc) genEngineDesc.innerHTML = `✨ <b>Chế độ Studio 30s:</b> Model Seedance ${activeModel} · Tỷ lệ ${activeRatio} · ${activeDuration}s`;
        if (genBtnQuickGenerate) genBtnQuickGenerate.innerHTML = `<span>🚀 TẠO VIDEO ${activeDuration}S KHÔNG LOGO</span>`;
        addLog('MODE', `Đã chuyển sang: ⚡ Studio Bypass (Model: Seedance ${activeModel}, Tỷ lệ: ${activeRatio}, Thời lượng: ${activeDuration}s)`, 'info');
      }
    }
  }

  if (btnModeStudio) btnModeStudio.addEventListener('click', () => setEngineMode('studio'));
  if (btnModeAgent) btnModeAgent.addEventListener('click', () => setEngineMode('agent'));

  chrome.storage.local.get(['zdola_engine_mode'], (res) => {
    if (res && res.zdola_engine_mode) {
      setEngineMode(res.zdola_engine_mode);
    } else {
      setEngineMode('studio');
    }
  });

  // ============================================================
  // AGENT TEMPLATE BUILDER LOGIC
  // ============================================================
  let agentPromptMode = 'custom'; // 'custom' | 'template'
  let agentTplRatio = '9:16';

  const agentModeCustomBtn = document.getElementById('agent-mode-custom');
  const agentModeTemplateBtn = document.getElementById('agent-mode-template');
  const agentCustomInfo = document.getElementById('agent-custom-info');
  const agentTemplateForm = document.getElementById('agent-template-form');
  const agentTplCount = document.getElementById('agent-tpl-count');
  const agentTplType = document.getElementById('agent-tpl-type');
  const agentTplModel = document.getElementById('agent-tpl-model');
  const agentTplDuration = document.getElementById('agent-tpl-duration');
  const agentTplPromptInput = document.getElementById('agent-tpl-prompt');
  const agentTplPreview = document.getElementById('agent-tpl-preview');
  const agentTplCopyBtn = document.getElementById('agent-tpl-copy');

  function setAgentPromptMode(mode) {
    agentPromptMode = mode;
    const isTemplate = mode === 'template';

    if (agentModeCustomBtn && agentModeTemplateBtn) {
      if (isTemplate) {
        agentModeTemplateBtn.classList.add('active');
        agentModeTemplateBtn.style.background = 'rgba(56,189,248,0.2)';
        agentModeTemplateBtn.style.borderColor = 'rgba(56,189,248,0.5)';
        agentModeTemplateBtn.style.color = '#38bdf8';
        agentModeCustomBtn.classList.remove('active');
        agentModeCustomBtn.style.background = 'rgba(255,255,255,0.05)';
        agentModeCustomBtn.style.borderColor = 'rgba(255,255,255,0.12)';
        agentModeCustomBtn.style.color = '#94a3b8';
      } else {
        agentModeCustomBtn.classList.add('active');
        agentModeCustomBtn.style.background = 'rgba(56,189,248,0.2)';
        agentModeCustomBtn.style.borderColor = 'rgba(56,189,248,0.5)';
        agentModeCustomBtn.style.color = '#38bdf8';
        agentModeTemplateBtn.classList.remove('active');
        agentModeTemplateBtn.style.background = 'rgba(255,255,255,0.05)';
        agentModeTemplateBtn.style.borderColor = 'rgba(255,255,255,0.12)';
        agentModeTemplateBtn.style.color = '#94a3b8';
      }
    }

    if (agentCustomInfo) agentCustomInfo.style.display = isTemplate ? 'none' : 'block';
    if (agentTemplateForm) agentTemplateForm.style.display = isTemplate ? 'block' : 'none';

    if (isTemplate) updateAgentTemplatePreview();
  }

  function buildAgentPromptFromTemplate() {
    const count = agentTplCount ? agentTplCount.value : '1';
    const type = agentTplType ? agentTplType.value : 'img2video';
    const model = agentTplModel ? agentTplModel.value : '2.5 pro';
    const duration = agentTplDuration ? agentTplDuration.value : '15s';
    const ratio = agentTplRatio || '9:16';
    const videoPrompt = agentTplPromptInput ? agentTplPromptInput.value.trim() : '';

    const typeClause = type === 'img2video'
      ? 'Dùng các ảnh tham chiếu đó tạo video từ ảnh storyboard vừa hoàn thành(img2video)'
      : '';

    let prompt = `[Tạo video](skill://creative-video?type=2&id=294222337297) Đừng hỏi hay thông báo gì cả, tôi sẽ đi ra ngoài và bạn cần tạo ${count} video cho tôi khi tôi trở về.`;

    if (typeClause) {
      prompt += ` ${typeClause};`;
    }

    prompt += ` model seedance ${model}, thời lượng ${duration}, tỷ lệ khung hình ${ratio}, chất lượng video 1k, hiển thị video đã hoàn thành ở chế độ notifyhuman.`;

    if (videoPrompt) {
      prompt += `\nPrompt video: ${videoPrompt}`;
    }

    return prompt;
  }

  function updateAgentTemplatePreview() {
    if (!agentTplPreview) return;
    const prompt = buildAgentPromptFromTemplate();
    agentTplPreview.textContent = prompt;
  }

  // Template mode toggle buttons
  if (agentModeCustomBtn) agentModeCustomBtn.addEventListener('click', () => setAgentPromptMode('custom'));
  if (agentModeTemplateBtn) agentModeTemplateBtn.addEventListener('click', () => setAgentPromptMode('template'));

  // Live preview on any template field change
  [agentTplCount, agentTplType, agentTplModel, agentTplDuration].forEach(el => {
    if (el) el.addEventListener('change', updateAgentTemplatePreview);
  });
  if (agentTplPromptInput) agentTplPromptInput.addEventListener('input', updateAgentTemplatePreview);

  // Ratio buttons
  document.querySelectorAll('.agent-tpl-ratio').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.agent-tpl-ratio').forEach(b => {
        b.classList.remove('active');
        b.style.background = '';
        b.style.borderColor = '';
        b.style.color = '';
      });
      btn.classList.add('active');
      btn.style.background = 'rgba(56,189,248,0.2)';
      btn.style.borderColor = 'rgba(56,189,248,0.5)';
      btn.style.color = '#38bdf8';
      agentTplRatio = btn.dataset.ratio;
      updateAgentTemplatePreview();
    });
  });

  // Copy button
  if (agentTplCopyBtn) {
    agentTplCopyBtn.addEventListener('click', () => {
      const prompt = buildAgentPromptFromTemplate();
      navigator.clipboard.writeText(prompt).then(() => {
        agentTplCopyBtn.textContent = '✅ Đã copy!';
        setTimeout(() => { agentTplCopyBtn.textContent = '📋 Copy'; }, 1500);
      });
    });
  }

  // Pro Model Generator elements
  const genBtnToggleProPresets = document.getElementById('gen-btn-toggle-pro-presets');
  const proPresetsPanel = document.getElementById('pro-presets-panel');
  const proBtnClosePanel = document.getElementById('pro-btn-close-panel');
  const proSelectGenre = document.getElementById('pro-select-genre');
  const proSelectCamera = document.getElementById('pro-select-camera');
  const proSelectLighting = document.getElementById('pro-select-lighting');
  const proSelectMotion = document.getElementById('pro-select-motion');
  const proBtnApply = document.getElementById('pro-btn-apply');

  // Toggle Pro Presets Panel
  if (genBtnToggleProPresets && proPresetsPanel) {
    genBtnToggleProPresets.addEventListener('click', () => {
      const isVisible = proPresetsPanel.style.display !== 'none';
      proPresetsPanel.style.display = isVisible ? 'none' : 'block';
    });
  }
  if (proBtnClosePanel && proPresetsPanel) {
    proBtnClosePanel.addEventListener('click', () => {
      proPresetsPanel.style.display = 'none';
    });
  }

  // Apply Pro Presets
  if (proBtnApply && genPromptInput) {
    proBtnApply.addEventListener('click', () => {
      const genre = proSelectGenre ? proSelectGenre.value : '';
      const camera = proSelectCamera ? proSelectCamera.value : '';
      const lighting = proSelectLighting ? proSelectLighting.value : '';
      const motion = proSelectMotion ? proSelectMotion.value : '';

      const compiled = `${genre}, ${camera}, ${lighting}, ${motion}, 30s master video quality, 8k resolution, sharp focus, hyper-realistic.`;
      genPromptInput.value = compiled;
      if (genCharCount) genCharCount.textContent = `${compiled.length} ký tự`;
      if (proPresetsPanel) proPresetsPanel.style.display = 'none';
      addLog('PROMPT_PRO', 'Đã áp dụng công thức prompt chuẩn Model Pro 30s!', 'success');
    });
  }

  // Single Reference Image handling
  if (genBtnChooseImg && genRefImgInput) {
    genBtnChooseImg.addEventListener('click', () => genRefImgInput.click());
  }

  if (genRefPreviewBox && genRefImgInput) {
    genRefPreviewBox.addEventListener('click', (e) => {
      if (!e.target.closest('#gen-btn-clear-img')) genRefImgInput.click();
    });
    genRefPreviewBox.addEventListener('dragover', (e) => {
      e.preventDefault();
      genRefPreviewBox.style.borderColor = '#ff7e00';
    });
    genRefPreviewBox.addEventListener('dragleave', () => {
      genRefPreviewBox.style.borderColor = 'rgba(255,255,255,0.1)';
    });
    genRefPreviewBox.addEventListener('drop', (e) => {
      e.preventDefault();
      genRefPreviewBox.style.borderColor = 'rgba(255,255,255,0.1)';
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        loadSingleRefImage(e.dataTransfer.files[0]);
      }
    });
  }

  if (genRefImgInput) {
    genRefImgInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        loadSingleRefImage(e.target.files[0]);
      }
      genRefImgInput.value = '';
    });
  }

  function loadSingleRefImage(file) {
    const reader = new FileReader();
    reader.onload = (evt) => {
      singleRefImage = {
        name: file.name,
        size: file.size,
        type: file.type || 'image/png',
        dataUrl: evt.target.result
      };
      renderSingleRefImage();
      addLog('REF_IMAGE', `Đã nạp ảnh tham chiếu: ${file.name}`, 'success');
    };
    reader.readAsDataURL(file);
  }

  // Local bridge import avoids the native Windows picker. The bridge serves
  // the user's project assets from 127.0.0.1:8767 and the fetched Blob is
  // passed through the same FileReader path as a normal selected file.
  async function loadReferenceFromLocalBridge(kind) {
    const presets = {
      character: {
        url: 'http://127.0.0.1:8767/Gym%202D/Test/nhanvat.png',
        name: 'nhanvat.png'
      },
      product: {
        url: 'http://127.0.0.1:8767/Gym%202D/Test/sanpham.webp',
        name: 'sanpham.webp'
      }
    };
    const preset = presets[kind];
    if (!preset) return;

    addLog('REF_IMAGE', `Đang nạp ${preset.name} từ local bridge...`, 'info');
    try {
      const response = await fetch(preset.url, {cache: 'no-store'});
      if (!response.ok) throw new Error(`Local bridge HTTP ${response.status}`);
      const blob = await response.blob();
      if (!blob.size) throw new Error('Ảnh nhận được rỗng.');
      const file = new File([blob], preset.name, {
        type: blob.type || (kind === 'product' ? 'image/webp' : 'image/png'),
        lastModified: Date.now()
      });
      loadSingleRefImage(file);
    } catch (error) {
      addLog('REF_IMAGE', `❌ Không nạp được ${preset.name}: ${error.message}`, 'error');
      alert(`Không nạp được ${preset.name}. Hãy kiểm tra local bridge 127.0.0.1:8767 đang chạy.`);
    }
  }

  document.getElementById('gen-btn-load-character')?.addEventListener('click', () => {
    loadReferenceFromLocalBridge('character');
  });
  document.getElementById('gen-btn-load-product')?.addEventListener('click', () => {
    loadReferenceFromLocalBridge('product');
  });

  // Manual smoke-test / attach-only path. This deliberately does not send a
  // prompt: it proves that the image already held by the extension is really
  // committed to the currently selected Dola Studio composer.
  if (genBtnAttachRef) {
    genBtnAttachRef.addEventListener('click', async () => {
      if (!singleRefImage?.dataUrl) {
        alert('Hãy chọn Char Sheet hoặc ảnh sản phẩm trước.');
        return;
      }

      genBtnAttachRef.disabled = true;
      const oldLabel = genBtnAttachRef.textContent;
      genBtnAttachRef.textContent = '⏳ Đang gắn vào Dola...';
      try {
        const tabId = await resolveTargetDolaTab('studio');
        await attachReferenceImageToDolaTab(tabId, singleRefImage);
        addLog('REF_IMAGE', `✅ Đã gắn và xác minh ${singleRefImage.name} trên Tab Dola #${tabId}.`, 'success');
        alert(`✅ Đã gắn ảnh vào composer Dola (Tab #${tabId}).`);
      } catch (error) {
        addLog('REF_IMAGE', `❌ Gắn ảnh thất bại: ${error?.message || error}`, 'error');
        alert(`Không gắn được ảnh vào Dola: ${error?.message || error}`);
      } finally {
        genBtnAttachRef.disabled = false;
        genBtnAttachRef.textContent = oldLabel || '📎 Gắn vào Dola';
      }
    });
  }

  function renderSingleRefImage() {
    if (!genRefPreviewBox) return;
    if (!singleRefImage) {
      genRefPreviewBox.innerHTML = '<span>📸 Chọn hoặc kéo thả ảnh bắt đầu / tham chiếu vào đây</span>';
      if (genBtnClearImg) genBtnClearImg.style.display = 'none';
      return;
    }

    genRefPreviewBox.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;width:100%;">
        <img src="${singleRefImage.dataUrl}" style="width:36px;height:36px;object-fit:cover;border-radius:6px;border:1px solid #fbbf24;" />
        <div style="flex:1;overflow:hidden;">
          <div style="font-weight:700;color:#fed7aa;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${singleRefImage.name}</div>
          <div style="font-size:9.5px;color:#94a3b8;">${(singleRefImage.size / 1024).toFixed(1)} KB · Sẵn sàng đính kèm tạo video</div>
        </div>
      </div>
    `;
    if (genBtnClearImg) genBtnClearImg.style.display = 'inline-block';
  }

  if (genBtnClearImg) {
    genBtnClearImg.addEventListener('click', (e) => {
      e.stopPropagation();
      singleRefImage = null;
      renderSingleRefImage();
      addLog('REF_IMAGE', 'Đã gỡ ảnh tham chiếu.', 'info');
    });
  }

  // Quick navigation buttons
  const btnOpenDolaStudio = document.getElementById('btn-open-dola-studio');
  const btnOpenDolaChat = document.getElementById('btn-open-dola-chat');
  const genSelectAccountTab = document.getElementById('gen-select-account-tab');
  const genBtnRefreshTabs = document.getElementById('gen-btn-refresh-tabs');

  // Populate open Dola Tabs in Tab 1 Selector
  async function refreshAccountTabList() {
    if (!genSelectAccountTab) return;

    chrome.tabs.query({ url: ['*://*.dola.com/*', '*://*.doubao.com/*', '*://*.zdola.com/*'] }, (tabs) => {
      const prevVal = genSelectAccountTab.value;
      genSelectAccountTab.innerHTML = '<option value="active">📍 Tab Đang Mở Hiện Tại</option>';

      if (!tabs || !tabs.length) {
        const opt = document.createElement('option');
        opt.value = 'none';
        opt.textContent = '⚠️ Chưa mở tab Dola nào (Bấm Mở Chat/Studio bên dưới)';
        genSelectAccountTab.appendChild(opt);
        return;
      }

      tabs.forEach((tab, index) => {
        const opt = document.createElement('option');
        opt.value = String(tab.id);
        const isChat = tab.url && tab.url.includes('/chat') && !tab.url.includes('/create-image');
        const pageType = isChat ? 'Chat Pro' : 'Studio 30s';
        const rawTitle = (tab.title || `Tab ${index + 1}`).replace(/[-–|].*$/, '').trim();
        opt.textContent = `[Tab #${index + 1}] ${rawTitle.substring(0, 20)} (${pageType})`;
        if (tab.active) {
          opt.textContent += ' [Đang xem]';
        }
        genSelectAccountTab.appendChild(opt);
      });

      if (prevVal && genSelectAccountTab.querySelector(`option[value="${prevVal}"]`)) {
        genSelectAccountTab.value = prevVal;
      }
    });
  }

  if (genBtnRefreshTabs) {
    genBtnRefreshTabs.addEventListener('click', () => {
      refreshAccountTabList();
      addLog('TAB', 'Đã quét và cập nhật danh sách Tab Dola!', 'info');
    });
  }

  // Refresh tab list on popup init
  refreshAccountTabList();

  // Helper to ensure target tab is at the desired URL, loaded, and responsive to messages
  async function ensureTabReadyAndResponsive(tabId, desiredUrl) {
    const tab = await new Promise(resolve => {
      chrome.tabs.get(tabId, t => {
        if (chrome.runtime.lastError || !t) resolve(null);
        else resolve(t);
      });
    });

    if (!tab) throw new Error(`Không tìm thấy Tab Dola #${tabId}`);

    const currentUrl = tab.url || tab.pendingUrl || '';
    const isDola = currentUrl.includes('dola.com') || currentUrl.includes('doubao.com');
    const isAgentTarget = Boolean(desiredUrl && desiredUrl.includes('/chat') && !desiredUrl.includes('create-image'));
    const isStudioTarget = Boolean(desiredUrl && desiredUrl.includes('create-image'));
    const needsNav = !isDola || (isAgentTarget && currentUrl.includes('create-image')) || (isStudioTarget && !currentUrl.includes('create-image'));

    if (needsNav) {
      addLog('NAV', `Đang chuyển Tab sang đúng trang: ${isAgentTarget ? 'Chat Pro (15s Free)' : 'Studio 30s'}...`, 'info');
      await new Promise(resolve => {
        let done = false;
        const listener = (updatedId, changeInfo) => {
          if (updatedId === tabId && changeInfo.status === 'complete') {
            chrome.tabs.onUpdated.removeListener(listener);
            done = true;
            setTimeout(resolve, 1400); // Wait 1.4s for scripts to initialize
          }
        };
        chrome.tabs.onUpdated.addListener(listener);
        chrome.tabs.update(tabId, { url: desiredUrl, active: true }, () => {
          setTimeout(() => {
            if (!done) {
              chrome.tabs.onUpdated.removeListener(listener);
              resolve();
            }
          }, 9000);
        });
      });
    } else {
      chrome.tabs.update(tabId, { active: true });
      await new Promise(r => setTimeout(r, 300));
    }

    // Ping content.js to verify it is responsive and NOT in back/forward cache
    let isResponsive = false;
    for (let attempt = 0; attempt < 8; attempt++) {
      const pong = await new Promise(resolve => {
        chrome.tabs.sendMessage(tabId, { type: 'PING' }, res => {
          if (chrome.runtime.lastError || !res || !res.pong) resolve(false);
          else resolve(true);
        });
      });

      if (pong) {
        isResponsive = true;
        break;
      }

      if (attempt === 2 || attempt === 4) {
        // Rehydrate all three sides of the upload bridge when a Dola SPA tab
        // has survived a reload without its content scripts: MAIN world
        // commits the FileList, verified isolated world waits for evidence,
        // and content.js handles the generation task.
        try {
          await chrome.scripting.executeScript({
            target: { tabId },
            files: ['image-attachment-main.js'],
            world: 'MAIN'
          });
        } catch (e) {}
        try {
          await chrome.scripting.executeScript({
            target: { tabId },
            files: ['verified-image-upload-content.js']
          });
        } catch (e) {}
        try {
          await chrome.scripting.executeScript({
            target: { tabId },
            files: ['content.js']
          });
        } catch (e) {}
      }

      await new Promise(r => setTimeout(r, 500));
    }

    if (!isResponsive) {
      throw new Error(`Tab Dola #${tabId} chưa phản hồi. Vui lòng F5 làm mới lại trang Dola!`);
    }

    // Do not assume that a cached SPA document also retained the MAIN-world
    // bridge. The content script can answer PING while image attachment is
    // still broken, so force an idempotent bridge installation before any
    // image-backed request. Both bridge files have their own install guards.
    await ensureImageUploadBridgeInjected(tabId);

    return true;
  }

  async function ensureImageUploadBridgeInjected(tabId) {
    const failures = [];
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['image-attachment-main.js'],
        world: 'MAIN'
      });
    } catch (error) {
      failures.push(`MAIN bridge: ${error?.message || error}`);
    }
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['verified-image-upload-content.js']
      });
    } catch (error) {
      failures.push(`verified bridge: ${error?.message || error}`);
    }
    if (failures.length) {
      throw new Error(`Không nạp được cầu nối upload ảnh (${failures.join('; ')}).`);
    }
    return true;
  }

  async function ensureAgentBridgeInTab(tabId) {
    const result = await new Promise(resolve => {
      chrome.runtime.sendMessage({action: 'studioRelayEnsureAgentBridge', tabId}, response => {
        const runtimeError = chrome.runtime.lastError;
        if (runtimeError) resolve({success: false, error: runtimeError.message});
        else resolve(response || {success: false, error: 'Không nhận được phản hồi Agent bridge.'});
      });
    });
    if (!result.success) throw new Error(result.error || 'Không nạp được Agent bridge.');
    return result;
  }

  // Helper to resolve the exact target tab
  async function resolveTargetDolaTab(engineMode) {
    const desiredUrl = engineMode === 'agent' ? 'https://www.dola.com/chat' : 'https://www.dola.com/chat/create-image';
    const selectedVal = genSelectAccountTab ? genSelectAccountTab.value : 'active';

    // 1. If specific tab is chosen in selector
    if (selectedVal && selectedVal !== 'active' && selectedVal !== 'none') {
      const specificTabId = parseInt(selectedVal, 10);
      if (!isNaN(specificTabId)) {
        await ensureTabReadyAndResponsive(specificTabId, desiredUrl);
        return specificTabId;
      }
    }

    // 2. Default: look at active tab
    const activeTabs = await new Promise(resolve => chrome.tabs.query({ active: true, currentWindow: true }, resolve));
    const activeTab = activeTabs && activeTabs[0];
    const isActiveDola = activeTab && activeTab.url && (activeTab.url.includes('dola.com') || activeTab.url.includes('doubao.com'));

    if (isActiveDola) {
      await ensureTabReadyAndResponsive(activeTab.id, desiredUrl);
      return activeTab.id;
    }

    // 3. Fallback to any open Dola tab
    const allDolaTabs = await new Promise(resolve => chrome.tabs.query({ url: ['*://*.dola.com/*', '*://*.doubao.com/*'] }, resolve));
    if (allDolaTabs && allDolaTabs.length > 0) {
      const target = allDolaTabs[0];
      await ensureTabReadyAndResponsive(target.id, desiredUrl);
      return target.id;
    }

    // 4. If none open, create one
    const newTab = await new Promise(resolve => chrome.tabs.create({ url: desiredUrl, active: true }, resolve));
    await ensureTabReadyAndResponsive(newTab.id, desiredUrl);
    refreshAccountTabList();
    return newTab.id;
  }

  if (btnOpenDolaStudio) {
    btnOpenDolaStudio.addEventListener('click', async () => {
      try {
        const tabId = await resolveTargetDolaTab('studio');
        addLog('NAV', `Đang xem Studio Tạo Video (Tab #${tabId})...`, 'success');
      } catch (err) {
        chrome.tabs.create({ url: 'https://www.dola.com/chat/create-image' });
      }
    });
  }

  if (btnOpenDolaChat) {
    btnOpenDolaChat.addEventListener('click', async () => {
      try {
        const tabId = await resolveTargetDolaTab('agent');
        addLog('NAV', `Đang xem Chat AI Agent Pro (Tab #${tabId})...`, 'info');
      } catch (err) {
        chrome.tabs.create({ url: 'https://www.dola.com/chat' });
      }
    });
  }

  // Prompt input helpers
  if (genPromptInput) {
    genPromptInput.addEventListener('input', () => {
      if (genCharCount) genCharCount.textContent = `${genPromptInput.value.length} ký tự`;
    });
  }

  if (genBtnPaste) {
    genBtnPaste.addEventListener('click', async () => {
      try {
        const text = await navigator.clipboard.readText();
        if (text && genPromptInput) {
          genPromptInput.value = text;
          if (genCharCount) genCharCount.textContent = `${text.length} ký tự`;
          addLog('PROMPT', 'Đã dán prompt từ bộ nhớ tạm.', 'success');
        }
      } catch (e) {
        if (genPromptInput) genPromptInput.focus();
        document.execCommand('paste');
      }
    });
  }

  if (genBtnClear) {
    genBtnClear.addEventListener('click', () => {
      if (genPromptInput) {
        genPromptInput.value = '';
        if (genCharCount) genCharCount.textContent = '0 ký tự';
        genPromptInput.focus();
      }
    });
  }

  if (genBtnSample) {
    genBtnSample.addEventListener('click', () => {
      const rand = samplePrompts[Math.floor(Math.random() * samplePrompts.length)];
      if (genPromptInput) {
        genPromptInput.value = rand;
        if (genCharCount) genCharCount.textContent = `${rand.length} ký tự`;
        addLog('SAMPLE', 'Đã nạp prompt mẫu.', 'info');
      }
    });
  }

  // Aspect ratio & Duration Configuration (Studio 30s Bypass)
  const ratioLabelMap = {
    '9:16': '9:16 (Dọc)',
    '16:9': '16:9 (Ngang)',
    '1:1': '1:1 (Vuông)',
    '3:4': '3:4',
    '4:3': '4:3',
    '21:9': '21:9 (Rộng)'
  };

  function updateRatioUI(ratio) {
    activeRatio = ratio;
    const allRatioBtns = document.querySelectorAll('.ratio-btn');
    allRatioBtns.forEach(b => {
      b.classList.toggle('active', b.dataset.ratio === ratio);
    });
    if (labelCurrentRatio) {
      labelCurrentRatio.textContent = ratioLabelMap[ratio] || ratio;
    }
  }

  function updateDurationUI(dur) {
    activeDuration = Number(dur) || 30;
    const allDurBtns = document.querySelectorAll('.duration-btn');
    allDurBtns.forEach(b => {
      b.classList.toggle('active', Number(b.dataset.duration) === activeDuration);
    });
    if (labelCurrentDuration) {
      labelCurrentDuration.textContent = activeDuration === 30 ? '30 Giây (Bypass Pro)' : `${activeDuration} Giây`;
    }
    if (currentEngineMode === 'studio' && genBtnQuickGenerate) {
      genBtnQuickGenerate.innerHTML = `<span>🚀 TẠO VIDEO ${activeDuration}S KHÔNG LOGO</span>`;
    }
  }

  // Model Video (Studio)
  const modelLabelMap = {
    '2.5': 'Seedance 2.5 (Tốt nhất)',
    '2.0': 'Seedance 2.0 Nhanh',
    '1.0': 'Seedance 1.0 Cơ bản'
  };

  function updateModelUI(model) {
    activeModel = model || '2.5';
    const allModelBtns = document.querySelectorAll('.model-btn');
    allModelBtns.forEach(b => {
      b.classList.toggle('active', b.dataset.model === activeModel);
    });
    if (labelCurrentModel) {
      labelCurrentModel.textContent = modelLabelMap[activeModel] || `Model ${activeModel}`;
    }
    if (currentEngineMode === 'studio' && genEngineDesc) {
      genEngineDesc.innerHTML = `✨ <b>Chế độ Studio 30s:</b> Model Seedance ${activeModel} · Tỷ lệ ${activeRatio} · ${activeDuration}s`;
    }
  }

  document.addEventListener('click', (e) => {
    // Model button click
    const modelBtn = e.target.closest('.model-btn');
    if (modelBtn && modelBtn.dataset.model) {
      const selectedModel = modelBtn.dataset.model;
      updateModelUI(selectedModel);
      chrome.storage.local.set({ zdola_saved_model: selectedModel });
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, { type: 'SET_ACTIVE_MODEL', model: selectedModel }).catch(() => {});
        }
      });
      addLog('MODEL', `Đã chọn model video: ${modelLabelMap[selectedModel] || selectedModel}`, 'info');
    }

    // Ratio button click
    const ratioBtn = e.target.closest('.ratio-btn');
    if (ratioBtn && ratioBtn.dataset.ratio) {
      const selectedRatio = ratioBtn.dataset.ratio;
      updateRatioUI(selectedRatio);
      chrome.storage.local.set({ zdola_saved_ratio: selectedRatio });
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, { type: 'SET_ACTIVE_RATIO', ratio: selectedRatio }).catch(() => {});
        }
      });
      addLog('RATIO', `Đã chọn tỉ lệ khung hình: ${selectedRatio} (${ratioLabelMap[selectedRatio] || selectedRatio})`, 'info');
    }

    // Duration button click
    const durBtn = e.target.closest('.duration-btn');
    if (durBtn && durBtn.dataset.duration) {
      const selectedDur = parseInt(durBtn.dataset.duration, 10) || 30;
      updateDurationUI(selectedDur);
      chrome.storage.local.set({ zdola_saved_duration: selectedDur });
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, { type: 'SET_ACTIVE_DURATION', duration: selectedDur }).catch(() => {});
        }
      });
      addLog('DURATION', `Đã chọn thời lượng video: ${selectedDur}s`, 'info');
    }
  });

  // Load saved ratio, duration & model
  chrome.storage.local.get(['zdola_saved_ratio', 'zdola_saved_duration', 'zdola_saved_model'], (res) => {
    if (res && res.zdola_saved_ratio) {
      updateRatioUI(res.zdola_saved_ratio);
    }
    if (res && res.zdola_saved_duration) {
      updateDurationUI(res.zdola_saved_duration);
    }
    if (res && res.zdola_saved_model) {
      updateModelUI(res.zdola_saved_model);
    }
  });

  // ========================================================================
  // REAL-TIME PROGRESS BAR & CANCEL/RESUME CONTROLLER
  // ========================================================================
  const genProgressCard = document.getElementById('gen-progress-card');
  const genProgressStatus = document.getElementById('gen-progress-status');
  const genProgressPercent = document.getElementById('gen-progress-percent');
  const genProgressBar = document.getElementById('gen-progress-bar');
  const genProgressTime = document.getElementById('gen-progress-time');
  const genProgressStage = document.getElementById('gen-progress-stage');
  const btnCancelGeneration = document.getElementById('btn-cancel-generation');
  const btnResumeGeneration = document.getElementById('btn-resume-generation');

  let activeProgressInterval = null;
  let progressElapsedSeconds = 0;
  let isGenerationCancelled = false;
  let currentActiveTaskTabId = null;

  function formatTimeMinSec(totalSeconds) {
    const m = Math.floor(totalSeconds / 60).toString().padStart(2, '0');
    const s = (totalSeconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  }

  function startProgressTracker(mode = 'agent', estimatedSec = 75) {
    clearInterval(activeProgressInterval);
    progressElapsedSeconds = 0;
    isGenerationCancelled = false;

    if (genProgressCard) genProgressCard.style.display = 'block';
    if (btnCancelGeneration) {
      btnCancelGeneration.style.display = 'flex';
      btnCancelGeneration.disabled = false;
    }
    if (btnResumeGeneration) btnResumeGeneration.style.display = 'none';

    updateProgressUI(3, '[1/3] Chuẩn bị cấu hình...', `Đang chuẩn bị ${mode === 'agent' ? 'AI Agent Pro' : 'Studio 30s'}...`, estimatedSec);

    activeProgressInterval = setInterval(() => {
      progressElapsedSeconds++;
      const ratio = Math.min(progressElapsedSeconds / estimatedSec, 1);
      let currentPct = Math.round(5 + (Math.sin((ratio * Math.PI) / 2) * 88));
      currentPct = Math.min(96, Math.max(5, currentPct));

      let stageText = '[3/3] Đang render video trên Dola...';
      let statusText = '⏳ Dola đang xử lý video (Nút Dừng Tạo đang bật)...';
      if (progressElapsedSeconds < 5) {
        stageText = '[1/3] Chuẩn bị cấu hình...';
        statusText = 'Đang chuẩn bị...';
      } else if (progressElapsedSeconds < 12) {
        stageText = '[2/3] Gửi prompt & ảnh tham chiếu...';
        statusText = 'Đang nạp dữ liệu vào Dola...';
      }

      updateProgressUI(currentPct, stageText, statusText, estimatedSec);
    }, 1000);
  }

  function updateProgressUI(percent, stageText, statusText, estimatedSec = 75) {
    if (genProgressBar) genProgressBar.style.width = `${percent}%`;
    if (genProgressPercent) genProgressPercent.textContent = `${percent}%`;
    if (genProgressStatus && statusText) genProgressStatus.textContent = statusText;
    if (genProgressStage && stageText) genProgressStage.textContent = stageText;
    if (genProgressTime) {
      genProgressTime.textContent = `⏱️ ${formatTimeMinSec(progressElapsedSeconds)} / ~${formatTimeMinSec(estimatedSec)}`;
    }
  }

  function completeProgressTracker(isSuccess = true, message = '') {
    clearInterval(activeProgressInterval);
    if (isSuccess) {
      updateProgressUI(100, '[Hoàn tất]', message || '🎉 Tạo video thành công!', 75);
      if (genProgressBar) {
        genProgressBar.style.width = '100%';
        genProgressBar.style.background = 'linear-gradient(90deg, #10b981, #059669)';
      }
      setTimeout(() => {
        if (genProgressCard) genProgressCard.style.display = 'none';
        if (genProgressBar) {
          genProgressBar.style.background = 'linear-gradient(90deg, #ff7e00, #fbbf24, #38bdf8)';
        }
      }, 3500);
    } else {
      if (genProgressStatus) genProgressStatus.textContent = message || 'Đã dừng tạo video.';
    }
  }

  function stopProgressTracker(reason = 'Đã dừng tạo video') {
    clearInterval(activeProgressInterval);
    isGenerationCancelled = true;
    if (genProgressStatus) genProgressStatus.textContent = reason;
    if (genProgressStage) genProgressStage.textContent = '[ĐÃ DỪNG]';
    if (btnCancelGeneration) btnCancelGeneration.style.display = 'none';
    if (btnResumeGeneration) btnResumeGeneration.style.display = 'flex';
  }

  // Handle Stop Button Click
  if (btnCancelGeneration) {
    btnCancelGeneration.addEventListener('click', () => {
      stopProgressTracker('⏹️ Đã bấm dừng tạo!');
      addLog('CANCEL', '⏹️ Đang gửi lệnh Dừng Tạo sang tab Dola...', 'warn');

      if (currentActiveTaskTabId) {
        chrome.tabs.sendMessage(currentActiveTaskTabId, { type: 'STOP_GENERATION' }, (res) => {
          if (res?.success) {
            addLog('CANCEL', '✅ Đã click nút Dừng Tạo trên Dola thành công!', 'success');
          } else {
            addLog('CANCEL', '⚠️ Đã dừng kiểm tra tiến trình (Dola đã kết thúc hoặc không tìm thấy nút dừng).', 'info');
          }
        });
      }

      if (genBtnQuickGenerate) {
        genBtnQuickGenerate.disabled = false;
        genBtnQuickGenerate.innerHTML = currentEngineMode === 'agent'
          ? '<span>🚀 TẠO QUA AI AGENT PRO (FREE CREDIT)</span>'
          : '<span>🚀 TẠO VIDEO 30S KHÔNG LOGO</span>';
      }
    });
  }

  // Handle Resume / Continue Button Click
  if (btnResumeGeneration) {
    btnResumeGeneration.addEventListener('click', () => {
      if (btnResumeGeneration) btnResumeGeneration.style.display = 'none';
      if (genBtnQuickGenerate) genBtnQuickGenerate.click();
    });
  }

  // Helper to monitor Chat AI Agent generation status with stop-button detection
  async function monitorChatAgentTaskWithRetry(tabId, promptText, refImages) {
    currentActiveTaskTabId = tabId;
    startProgressTracker('agent', 75);

    const images = (Array.isArray(refImages) ? refImages : (refImages ? [refImages] : []))
      .filter((image, index, all) => image?.dataUrl && all.findIndex(item => item?.dataUrl === image.dataUrl) === index);

    addLog('AGENT_PRO', 'Chuẩn bị tab và gửi câu lệnh tạo video qua AI Agent Pro...', 'info');

    try {
      await ensureTabReadyAndResponsive(tabId, 'https://www.dola.com/chat');
      await ensureAgentBridgeInTab(tabId);
    } catch (e) {
      addLog('AGENT_PRO', `⚠️ Lỗi chuẩn bị tab: ${e.message}`, 'warn');
      completeProgressTracker(false, 'Lỗi kết nối tab');
      return { success: false, error: e.message };
    }

    if (isGenerationCancelled) {
      completeProgressTracker(false, 'Đã hủy');
      return { success: false, error: 'Đã hủy bởi người dùng' };
    }

    updateProgressUI(12, '[2/3] Gửi prompt...', 'Đang gửi prompt & ảnh tham chiếu vào Chat...', 75);

    const sendAgentRequest = () => new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, {
        type: 'CHAT_AGENT_PRO_TASK',
        prompt: promptText,
        images,
        image: images[0] || null,
        newChat: true,
        ratio: activeRatio || '9:16'
      }, (res) => {
        if (chrome.runtime.lastError || !res || !res.success) {
          resolve({
            success: false,
            noResponse: Boolean(chrome.runtime.lastError || !res),
            error: chrome.runtime.lastError?.message || res?.error
          });
        } else {
          resolve({...res, noResponse: false});
        }
      });
    });

    let sendResult = await sendAgentRequest();

    // Retry the exact same Agent request on the same chat URL.  The previous
    // implementation incorrectly reloaded /chat/create-image, which switched
    // to credit-based Studio and discarded the Agent workflow.
    if (sendResult.noResponse) {
      addLog('RETRY', '⚠️ Chat Agent không phản hồi. Đang reload đúng /chat và gửi lại nguyên request...', 'warn');
      await new Promise((resolve, reject) => {
        chrome.tabs.reload(tabId, {bypassCache: true}, () => {
          const runtimeError = chrome.runtime.lastError;
          if (runtimeError) reject(new Error(runtimeError.message));
          else resolve();
        });
      });
      await ensureTabReadyAndResponsive(tabId, 'https://www.dola.com/chat');
      await ensureAgentBridgeInTab(tabId);
      sendResult = await sendAgentRequest();
    }

    if (!sendResult.success) {
      addLog('AGENT_PRO', `⚠️ Gửi lệnh thất bại: ${sendResult.error || 'Lỗi không xác định'}`, 'warn');
      completeProgressTracker(false, 'Gửi lệnh thất bại');
      return { success: false, error: sendResult.error };
    }

    addLog('AGENT_PRO', '⚡ Đã gửi câu lệnh Agent Pro thành công! Đang theo dõi tiến trình render...', 'success');
    updateProgressUI(25, '[3/3] Đang render video...', 'Dola đang tạo video 15s Free Credit...', 75);

    // Status polling loop: check if Stop Button ("Dừng tạo") is active
    let waitSeconds = 0;
    let hasStartedGenerating = false;
    let isDone = false;
    const MAX_WAIT_SECONDS = 300; // 5 minutes max

    while (waitSeconds < MAX_WAIT_SECONDS) {
      if (isGenerationCancelled) {
        completeProgressTracker(false, 'Đã hủy tạo');
        return { success: false, error: 'Người dùng hủy tạo' };
      }

      await new Promise(r => setTimeout(r, 2500));
      waitSeconds += 3;

      const status = await new Promise(resolve => {
        chrome.tabs.sendMessage(tabId, { type: 'CHECK_CHAT_STATUS' }, (res) => {
          if (chrome.runtime.lastError || !res) resolve({ isGenerating: false, isReady: true });
          else resolve(res);
        });
      });

      if (status.isGenerating) {
        hasStartedGenerating = true;
        if (waitSeconds % 12 === 0) {
          addLog('AGENT_PRO', `⏳ AI Agent Pro đang tạo video (${waitSeconds}s) [Nút Dừng Tạo đang bật]...`, 'info');
        }
      } else {
        // Check if new videos were detected
        if (status.hasNewVideo && status.completedVideos && status.completedVideos.length > 0) {
          const videoInfo = status.completedVideos[0];
          addLog('AGENT_PRO', `🎬 Video phát hiện! URL: ${(videoInfo.url || '').substring(0, 80)}...`, 'success');
          addLog('AGENT_PRO', '🎉 AI Agent Pro đã hoàn tất video! Master Downloader sẽ tự động lưu file MP4.', 'success');
          completeProgressTracker(true, '🎉 Video AI Agent Pro đã hoàn tất!');
          isDone = true;
          break;
        }
        // If it was generating and now is done (fallback)
        if (hasStartedGenerating) {
          addLog('AGENT_PRO', '🎉 AI Agent Pro đã hoàn tất video! Master Downloader sẽ tự động lưu file MP4.', 'success');
          completeProgressTracker(true, '🎉 Video AI Agent Pro đã hoàn tất!');
          isDone = true;
          break;
        }
      }
    }

    if (isDone) {
      return { success: true };
    }

    completeProgressTracker(false, 'Hết thời gian chờ');
    return { success: false, error: 'Thời gian tạo vượt quá giới hạn' };
  }

  // Helper giám sát tiến trình tạo video 30s trong chế độ Studio
  async function monitorStudioTaskStatus(tabId, promptText, duration = 30, model = '2.5') {
    currentActiveTaskTabId = tabId;
    startProgressTracker('studio', duration === 30 ? 115 : 70);

    let waitSeconds = 0;
    let hasStartedRendering = false;
    let isDone = false;
    const MAX_WAIT_SECONDS = 450; // 7.5 phút tối đa

    updateProgressUI(22, '[3/4] Đang render video 30s...', `Dola đang tạo video Model ${model} (${duration}s)...`, duration === 30 ? 115 : 70);

    while (waitSeconds < MAX_WAIT_SECONDS) {
      if (isGenerationCancelled) {
        completeProgressTracker(false, 'Đã hủy tạo');
        addLog('CANCEL', '⏹️ Người dùng đã dừng tạo video.', 'warn');
        return { success: false, error: 'Người dùng hủy' };
      }

      await new Promise(r => setTimeout(r, 2500));
      waitSeconds += 3;

      const status = await new Promise(resolve => {
        chrome.tabs.sendMessage(tabId, { type: 'CHECK_STUDIO_STATUS' }, (res) => {
          if (chrome.runtime.lastError || !res) {
            chrome.tabs.sendMessage(tabId, { type: 'CHECK_CHAT_STATUS' }, (res2) => {
              resolve(res2 || { isGenerating: false });
            });
          } else {
            resolve(res);
          }
        });
      });

      // 1. Kiểm tra Lỗi từ Dola (Quota / Vi phạm chính sách / Từ chối thời lượng)
      if (status.hasError) {
        const errorMsg = status.errorText || 'Dola báo lỗi khi tạo video!';
        addLog('ERROR', `❌ ${errorMsg}`, 'error');
        completeProgressTracker(false, errorMsg);
        alert(`Lỗi Dola: ${errorMsg}`);
        return { success: false, error: errorMsg };
      }

      // 2. Kiểm tra Video Hoàn Thành
      if (status.hasVideo && (status.videoUrl || (status.videos && status.videos.length > 0))) {
        const finalUrl = status.videoUrl || status.videos[0].url;
        addLog('DONE', `🎉 Video ${duration}s Model ${model} đã hoàn tất thành công!`, 'success');
        addLog('VIDEO', `🎬 Link video: ${finalUrl.substring(0, 80)}...`, 'info');
        completeProgressTracker(true, `🎉 Video ${duration}s đã tạo xong!`);

        // Tự động tải video sạch không logo
        try {
          chrome.runtime.sendMessage({
            action: 'fast_download',
            url: finalUrl,
            filename: `Dola_30s_${model}_${Date.now()}.mp4`
          });
          addLog('DOWNLOAD', '⬇️ Đã kích hoạt tải Video 1080P sạch về máy!', 'success');
        } catch (e) {}

        isDone = true;
        break;
      }

      // 3. Đang Render
      if (status.isGenerating) {
        hasStartedRendering = true;
        const pct = status.progressPercent ? `${status.progressPercent}%` : `${waitSeconds}s`;
        if (waitSeconds % 12 === 0) {
          addLog('STUDIO', `⏳ Dola đang render video ${duration}s (${pct})...`, 'info');
        }
        const calcPercent = status.progressPercent 
          ? Math.max(15, Math.min(95, status.progressPercent))
          : Math.min(92, Math.max(22, Math.round((waitSeconds / (duration === 30 ? 115 : 70)) * 88)));

        updateProgressUI(
          calcPercent,
          `[3/4] Đang render video (${pct})...`,
          `Dola đang tạo video Model ${model} (${duration}s)...`,
          duration === 30 ? 115 : 70
        );
      } else if (hasStartedRendering) {
        // Nếu trước đó đang render mà giờ spinner biến mất -> chờ 2s kiểm tra lần cuối
        await new Promise(r => setTimeout(r, 2000));
        const finalStatus = await new Promise(resolve => {
          chrome.tabs.sendMessage(tabId, { type: 'CHECK_STUDIO_STATUS' }, resolve);
        });
        if (finalStatus?.hasVideo && finalStatus.videoUrl) {
          addLog('DONE', `🎉 Video ${duration}s Model ${model} đã hoàn tất thành công!`, 'success');
          completeProgressTracker(true, `🎉 Video ${duration}s đã tạo xong!`);
          try {
            chrome.runtime.sendMessage({
              action: 'fast_download',
              url: finalStatus.videoUrl,
              filename: `Dola_30s_${model}_${Date.now()}.mp4`
            });
          } catch (e) {}
          isDone = true;
          break;
        } else {
          addLog('DONE', `⚡ Quá trình render video ${duration}s trên Dola đã kết thúc!`, 'success');
          completeProgressTracker(true, '⚡ Quá trình render đã kết thúc!');
          isDone = true;
          break;
        }
      }
    }

    if (!isDone) {
      addLog('WARN', '⚠️ Quá thời gian chờ render (7.5 phút). Vui lòng kiểm tra tab Dola.', 'warn');
      completeProgressTracker(false, 'Hết thời gian chờ');
    }

    return { success: isDone };
  }

  // Quick Generate Button
  if (genBtnQuickGenerate) {
    genBtnQuickGenerate.addEventListener('click', async () => {
      let promptText = genPromptInput ? genPromptInput.value.trim() : '';

      // If Agent mode + Template mode → use built template prompt
      if (currentEngineMode === 'agent' && agentPromptMode === 'template') {
        promptText = buildAgentPromptFromTemplate();
      }

      if (!promptText && !singleRefImage) {
        alert('Vui lòng nhập prompt hoặc chọn ảnh tham chiếu trước khi tạo!');
        return;
      }

      genBtnQuickGenerate.disabled = true;
      genBtnQuickGenerate.innerHTML = currentEngineMode === 'agent' 
        ? '<span>🤖 Đang kết nối Tab AI Agent Pro...</span>'
        : '<span>⚡ Đang kết nối Tab Studio 30s...</span>';

      try {
        const targetTabId = await resolveTargetDolaTab(currentEngineMode);
        await executeGenerateWithOptionalImage(targetTabId, promptText, singleRefImage);
      } catch (err) {
        addLog('ERROR', `Lỗi kết nối Tab: ${err.message}`, 'error');
        alert(`Lỗi: ${err.message}`);
        genBtnQuickGenerate.disabled = false;
        genBtnQuickGenerate.innerHTML = currentEngineMode === 'agent'
          ? '<span>🚀 TẠO QUA AI AGENT PRO (FREE CREDIT)</span>'
          : '<span>🚀 TẠO VIDEO 30S KHÔNG LOGO</span>';
      }
    });
  }

  async function executeGenerateWithOptionalImage(tabId, promptText, refImage) {
    currentActiveTaskTabId = tabId;

    const finish = () => {
      genBtnQuickGenerate.disabled = false;
      genBtnQuickGenerate.innerHTML = currentEngineMode === 'agent'
        ? '<span>🚀 TẠO QUA AI AGENT PRO (FREE CREDIT)</span>'
        : '<span>🚀 TẠO VIDEO 30S KHÔNG LOGO</span>';
    };

    if (currentEngineMode === 'agent') {
      addLog('START', `🤖 Khởi chạy AI Agent Pro: 15s • Free Credit • Seedance 2.5 Pro trên Tab #${tabId}...`, 'info');
      const res = await monitorChatAgentTaskWithRetry(tabId, promptText, refImage);
      if (res.success) {
        addLog('DONE', '✨ Quá trình tạo video qua AI Agent Pro đã hoàn tất!', 'success');
      } else {
        addLog('FAIL', `❌ Lỗi Agent: ${res.error || 'Không thành công'}`, 'error');
      }
      finish();
    } else {
      addLog('START', `🚀 Đang khởi chạy Studio Bypass 30s: Model Seedance ${activeModel} • Tỷ lệ ${activeRatio} • ${activeDuration}s trên Tab #${tabId}...`, 'info');
      startProgressTracker('studio', activeDuration === 30 ? 115 : 70);

      try {
        await ensureTabReadyAndResponsive(tabId, 'https://www.dola.com/chat/create-image');
      } catch (e) {
        addLog('WARN', `⚠️ Tab chuẩn bị: ${e.message}`, 'warn');
      }

      if (isGenerationCancelled) {
        completeProgressTracker(false, 'Đã hủy');
        finish();
        return;
      }

      updateProgressUI(15, '[2/4] Gửi prompt & ảnh tham chiếu...', 'Đang nạp dữ liệu vào Studio...', activeDuration === 30 ? 115 : 70);

      // Attach through the extension relay as a separate, verified step.
      // The old flow only carried the image inside STUDIO_AUTOMATE_TASK, so a
      // missing content-script response could still reach the prompt-only
      // fallback. Keep the image out of the task after this succeeds to avoid
      // a second attachment; the retry hook re-attaches it after a tab reload.
      if (refImage?.dataUrl) {
        try {
          await attachReferenceImageToDolaTab(tabId, refImage);
          addLog('REF_IMAGE', `✅ Đã gắn và xác nhận ${refImage.name || 'ảnh tham chiếu'} trên composer Dola.`, 'success');
        } catch (error) {
          addLog('REF_IMAGE', `❌ Không thể gắn ảnh tham chiếu: ${error?.message || error}`, 'error');
          completeProgressTracker(false, 'Upload ảnh tham chiếu thất bại');
          finish();
          return;
        }
      }

      const taskPayload = {
        type: 'STUDIO_AUTOMATE_TASK',
        prompt: promptText,
        ratio: activeRatio || '9:16',
        duration: activeDuration || 30,
        image: null,
        referenceAlreadyAttached: Boolean(refImage?.dataUrl),
        model: activeModel || '2.5'
      };

      const taskReply = await sendStudioTaskWithRetry(tabId, taskPayload, {
        beforeRetry: refImage?.dataUrl ? () => attachReferenceImageToDolaTab(tabId, refImage) : null
      });
      const res = taskReply.response;

      // An image-backed request must never fall through to prompt-only DOM
      // injection. A missing/negative task acknowledgement means the image
      // contract was not proven, so stop and let the user retry visibly.
      if (refImage?.dataUrl && (taskReply.noResponse || !res || res.success !== true)) {
        const reason = res?.error || taskReply.error || 'Dola không xác nhận request có ảnh tham chiếu.';
        addLog('REF_IMAGE', `❌ ${reason}`, 'error');
        completeProgressTracker(false, 'Ảnh tham chiếu chưa được gắn');
        finish();
        return;
      }

      if (!res || !res.success) {
          // Fallback: directDomInjectPrompt via executeScript
          chrome.scripting.executeScript({
            target: { tabId },
            func: directDomInjectPrompt,
            args: [promptText, activeRatio || '9:16', activeDuration || 30, activeModel || '2.5']
          }).then(async () => {
            addLog('EXEC', `⚡ Đã tiêm prompt và click tạo video Model ${activeModel} (${activeDuration}s) qua fallback!`, 'info');
            await monitorStudioTaskStatus(tabId, promptText, activeDuration || 30, activeModel || '2.5');
            finish();
          }).catch((err) => {
            addLog('ERROR', `Lỗi: ${err?.message || err}`, 'error');
            completeProgressTracker(false, 'Lỗi tiêm lệnh');
            finish();
          });
      } else {
        addLog('EXEC', `⚡ Đã nạp cấu hình Model ${activeModel} (${activeDuration}s) & gửi prompt vào Dola Studio!`, 'success');
        await monitorStudioTaskStatus(tabId, promptText, activeDuration || 30, activeModel || '2.5');
        finish();
      }
    }
  }

  function sendStudioTaskOnce(tabId, payload) {
    return new Promise(resolve => {
      chrome.tabs.sendMessage(tabId, payload, response => {
        const runtimeError = chrome.runtime.lastError;
        if (runtimeError) {
          resolve({
            response: null,
            noResponse: true,
            error: runtimeError.message || 'Tab Dola không phản hồi.'
          });
          return;
        }
        if (!response) {
          resolve({response: null, noResponse: true, error: 'Tab Dola không trả kết quả.'});
          return;
        }
        resolve({response, noResponse: false, error: ''});
      });
    });
  }

  function sendReferenceImageOnce(tabId, image) {
    return new Promise(resolve => {
      chrome.tabs.sendMessage(tabId, {
        action: 'studioRelayUploadImage',
        image: {
          name: String(image?.name || 'reference.png'),
          type: String(image?.type || 'image/png'),
          size: Number(image?.size) || 0,
          lastModified: Number(image?.lastModified) || Date.now(),
          dataUrl: String(image?.dataUrl || '')
        }
      }, response => {
        const runtimeError = chrome.runtime.lastError;
        if (runtimeError) {
          resolve({response: null, noResponse: true, error: runtimeError.message || 'Tab Dola không phản hồi upload.'});
          return;
        }
        if (!response) {
          resolve({response: null, noResponse: true, error: 'Tab Dola không trả kết quả upload.'});
          return;
        }
        resolve({response, noResponse: false, error: ''});
      });
    });
  }

  async function attachReferenceImageToDolaTab(tabId, image) {
    if (!image?.dataUrl) throw new Error('Ảnh tham chiếu không có dữ liệu.');

    let first = await sendReferenceImageOnce(tabId, image);
    if (!first.noResponse) {
      if (first.response?.success && first.response?.verified === true) return first.response;
      throw new Error(first.response?.error || 'Dola chưa xác nhận thumbnail ảnh tham chiếu.');
    }

    addLog('RETRY', '⚠️ Upload không phản hồi. Đang reload tab rồi gắn lại ảnh...', 'warn');
    await new Promise((resolve, reject) => {
      chrome.tabs.reload(tabId, {bypassCache: true}, () => {
        const runtimeError = chrome.runtime.lastError;
        if (runtimeError) reject(new Error(runtimeError.message));
        else resolve();
      });
    });
    await ensureTabReadyAndResponsive(tabId, 'https://www.dola.com/chat/create-image');
    first = await sendReferenceImageOnce(tabId, image);
    if (first.noResponse || !first.response?.success || first.response?.verified !== true) {
      throw new Error(first.response?.error || first.error || 'Dola vẫn chưa xác nhận ảnh sau khi reload.');
    }
    return first.response;
  }

  async function sendStudioTaskWithRetry(tabId, payload, options = {}) {
    let first = await sendStudioTaskOnce(tabId, payload);
    if (!first.noResponse) return first;

    addLog('RETRY', '⚠️ Dola không phản hồi. Đang reload tab và gửi lại đúng request...', 'warn');
    try {
      await new Promise((resolve, reject) => {
        chrome.tabs.reload(tabId, {bypassCache: true}, () => {
          const runtimeError = chrome.runtime.lastError;
          if (runtimeError) reject(new Error(runtimeError.message));
          else resolve();
        });
      });
      await ensureTabReadyAndResponsive(tabId, 'https://www.dola.com/chat/create-image');
      if (typeof options.beforeRetry === 'function') {
        await options.beforeRetry();
      }
      const second = await sendStudioTaskOnce(tabId, payload);
      if (second.noResponse) {
        return {
          ...second,
          error: second.error || 'Tab Dola vẫn không phản hồi sau khi reload.'
        };
      }
      addLog('RETRY', '✅ Dola đã phản hồi sau khi reload; request được gửi lại.', 'success');
      return second;
    } catch (error) {
      return {
        response: null,
        noResponse: true,
        error: error?.message || String(error)
      };
    }
  }

  function directDomInjectPrompt(text, ratio, duration = 30, model = '2.5') {
    const findComposer = () => {
      const selectors = [
        'textarea.semi-input-textarea',
        'textarea[placeholder*="Nhắn tin"]',
        'textarea[placeholder*="chat" i]',
        'textarea[placeholder*="prompt" i]',
        'textarea',
        'div[contenteditable="true"]',
        'div[role="textbox"]'
      ];
      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) return el;
      }
      return null;
    };

    const textarea = findComposer();
    if (textarea) {
      textarea.focus();
      if (textarea.tagName === 'TEXTAREA' || textarea.tagName === 'INPUT') {
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype,
          'value'
        )?.set || Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          'value'
        )?.set;

        if (setter) {
          setter.call(textarea, text);
        } else {
          textarea.value = text;
        }
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        textarea.dispatchEvent(new Event('change', { bubbles: true }));
      } else {
        textarea.innerText = text;
        document.execCommand('selectAll', false, null);
        document.execCommand('insertText', false, text);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        textarea.dispatchEvent(new Event('change', { bubbles: true }));
      }

      window.postMessage({ type: 'PURZA_UPDATE_SETTINGS', ratio, duration, model }, '*');
      window.postMessage({ type: 'SET_RATIO_OVERRIDE', ratio, duration, model }, '*');
      window.dispatchEvent(new CustomEvent('DOLA_SET_SEEDANCE_CONFIG', { detail: { duration: Number(duration) || 30, enabled: true } }));

      setTimeout(() => {
        const triggerFullClick = (element) => {
          if (!element) return false;
          try {
            element.focus();
            const opts = { bubbles: true, cancelable: true, view: window };
            element.dispatchEvent(new PointerEvent('pointerdown', opts));
            element.dispatchEvent(new MouseEvent('mousedown', opts));
            element.dispatchEvent(new PointerEvent('pointerup', opts));
            element.dispatchEvent(new MouseEvent('mouseup', opts));
            element.dispatchEvent(new MouseEvent('click', opts));
            if (typeof element.click === 'function') element.click();
            return true;
          } catch (e) { return false; }
        };

        const sendButtons = [
          '#flow-end-msg-send',
          '#channa-create-btn',
          '.studio-relay-create-btn',
          '#create-video-btn',
          '.create-video-btn',
          '#btn-create-video',
          'button[aria-label*="Create Video" i]',
          'button[title*="Create Video" i]',
          'button[aria-label*="Create video" i]',
          'button[title*="Create video" i]',
          'button[aria-label*="Generate" i]',
          'button[title*="Generate" i]',
          'button[type="submit"]',
          'form button[type="submit"]',
          'form button',
          'div[role="button"][class*="send" i]',
          'button[class*="send" i]',
          '[data-testid*="send" i]',
          '[aria-label*="Gửi" i]',
          '[aria-label*="Send" i]',
          '[aria-label*="Tạo" i]',
          'button:has(svg)'
        ];

        let clicked = false;
        for (const sel of sendButtons) {
          try {
            const btns = document.querySelectorAll(sel);
            for (const b of btns) {
              const clickable = b.closest('button, div[role="button"]') || b;
              if (clickable && !clickable.disabled && (clickable.offsetWidth > 0 || clickable.offsetHeight > 0)) {
                if (triggerFullClick(clickable)) {
                  clicked = true;
                  break;
                }
              }
            }
            if (clicked) break;
          } catch (e) {}
        }

        if (!clicked) {
          textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
        }
      }, 350);
    }
  }

  function renderRecentDownloads() {
    if (!genRecentList) return;
    if (!recentDownloads || recentDownloads.length === 0) {
      genRecentList.innerHTML = '<div class="empty-state" style="padding: 10px;">Chưa có video nào được tạo trong phiên này.</div>';
      if (genRecentCountBadge) genRecentCountBadge.textContent = '0 video';
      return;
    }

    if (genRecentCountBadge) genRecentCountBadge.textContent = `${recentDownloads.length} video`;
    genRecentList.innerHTML = '';

    recentDownloads.slice(0, 8).forEach((item) => {
      const card = document.createElement('div');
      card.className = 'item-card';
      const hasUrl = !!item.url && /^https?:\/\//i.test(item.url);
      card.innerHTML = `
        <div class="item-info" style="flex: 1; min-width: 0;">
          <span class="item-title" title="${item.filename || item.prompt}" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block;">${item.filename || item.prompt || 'Video 30s'}</span>
          <span class="item-subtitle">${new Date(item.timestamp || Date.now()).toLocaleTimeString()}</span>
        </div>
        <div class="item-actions" style="display: flex; gap: 4px; align-items: center; flex-shrink: 0;">
          ${hasUrl ? `
            <a href="${item.url}" target="_blank" class="btn-mini" style="text-decoration: none; color: #38bdf8; background: rgba(56,189,248,0.15); border: 1px solid rgba(56,189,248,0.3); padding: 2px 6px; font-size: 9px; font-weight: 700; border-radius: 4px;" title="Mở xem video">▶ Xem</a>
            <button type="button" class="btn-mini btn-copy-vid-link" data-url="${item.url}" style="color: #cbd5e1; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.15); padding: 2px 6px; font-size: 9px; border-radius: 4px;" title="Sao chép link video MP4">📋 Link</button>
          ` : ''}
          <span style="font-size: 9px; font-weight: 700; color: #34d399; background: rgba(52, 211, 153, 0.15); padding: 2px 5px; border-radius: 4px;">1080P Raw</span>
        </div>
      `;

      const copyBtn = card.querySelector('.btn-copy-vid-link');
      if (copyBtn) {
        copyBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          navigator.clipboard.writeText(copyBtn.dataset.url).then(() => {
            copyBtn.textContent = '✅ Đã chép!';
            setTimeout(() => { copyBtn.textContent = '📋 Link'; }, 1500);
          });
        });
      }

      genRecentList.appendChild(card);
    });
  }

  // ========================================================================
  // 4. TAB 2: MULTI-REQUEST (DANH SÁCH REQUEST: PROMPT + ẢNH THAM CHIẾU)
  // ========================================================================
  const mreqInputPrompt = document.getElementById('mreq-input-prompt');
  const mreqSingleImgInput = document.getElementById('mreq-single-img-input');
  const mreqBtnAddImg = document.getElementById('mreq-btn-add-img');
  const mreqImgPreviewTag = document.getElementById('mreq-img-preview-tag');
  const mreqThumbImg = document.getElementById('mreq-thumb-img');
  const mreqThumbName = document.getElementById('mreq-thumb-name');
  const mreqThumbRemove = document.getElementById('mreq-thumb-remove');
  const mreqBtnAddToList = document.getElementById('mreq-btn-add-to-list');

  const mreqFileInput = document.getElementById('mreq-file-input');
  const mreqBtnImport = document.getElementById('mreq-btn-import');
  const mreqBtnClearAll = document.getElementById('mreq-btn-clear-all');

  const mreqBtnRunPipeline = document.getElementById('mreq-btn-run-pipeline');
  const mreqBtnRunMultithread = document.getElementById('mreq-btn-run-multithread');
  const mreqBtnPausePipeline = document.getElementById('mreq-btn-pause-pipeline');
  const mreqBtnStopPipeline = document.getElementById('mreq-btn-stop-pipeline');
  const mreqProgressLabel = document.getElementById('mreq-progress-label');
  const mreqProgressPercent = document.getElementById('mreq-progress-percent');
  const mreqProgressBar = document.getElementById('mreq-progress-bar');

  const mreqRenderContainer = document.getElementById('mreq-render-container');
  const mreqTotalBadge = document.getElementById('mreq-total-badge');
  const mreqFAll = document.getElementById('mreq-f-all');
  const mreqFQueued = document.getElementById('mreq-f-queued');
  const mreqFDone = document.getElementById('mreq-f-done');
  const mreqFilterButtons = document.querySelectorAll('[data-mreq-filter]');

  // Draft Image for Multi-Request
  if (mreqBtnAddImg && mreqSingleImgInput) {
    mreqBtnAddImg.addEventListener('click', () => mreqSingleImgInput.click());
  }

  if (mreqSingleImgInput) {
    mreqSingleImgInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (evt) => {
        mreqDraftImage = {
          name: file.name,
          size: file.size,
          type: file.type || 'image/png',
          dataUrl: evt.target.result
        };
        if (mreqImgPreviewTag && mreqThumbImg && mreqThumbName) {
          mreqThumbImg.src = mreqDraftImage.dataUrl;
          mreqThumbName.textContent = mreqDraftImage.name;
          mreqImgPreviewTag.style.display = 'inline-flex';
        }
      };
      reader.readAsDataURL(file);
      mreqSingleImgInput.value = '';
    });
  }

  if (mreqThumbRemove) {
    mreqThumbRemove.addEventListener('click', () => {
      mreqDraftImage = null;
      if (mreqImgPreviewTag) mreqImgPreviewTag.style.display = 'none';
    });
  }

  function saveMultiRequestsToStorage() {
    chrome.storage.local.set({ ctb_multi_requests: savedMultiRequests }, () => {
      renderMultiRequestsList();
    });
  }

  // Multi-Request Engine Choice Handlers
  let mreqSelectedEngine = 'studio';
  const mreqChoiceStudio = document.getElementById('mreq-choice-studio');
  const mreqChoiceAgent = document.getElementById('mreq-choice-agent');

  function setMreqChoice(engine) {
    mreqSelectedEngine = engine;
    if (mreqChoiceStudio && mreqChoiceAgent) {
      if (engine === 'agent') {
        mreqChoiceAgent.classList.add('active');
        mreqChoiceAgent.style.background = 'rgba(255,126,0,0.2)';
        mreqChoiceAgent.style.borderColor = 'rgba(251,191,36,0.4)';
        mreqChoiceAgent.style.color = '#fbbf24';

        mreqChoiceStudio.classList.remove('active');
        mreqChoiceStudio.style.background = 'rgba(255,255,255,0.05)';
        mreqChoiceStudio.style.borderColor = 'rgba(255,255,255,0.1)';
        mreqChoiceStudio.style.color = '#94a3b8';
      } else {
        mreqChoiceStudio.classList.add('active');
        mreqChoiceStudio.style.background = 'rgba(255,126,0,0.2)';
        mreqChoiceStudio.style.borderColor = 'rgba(251,191,36,0.4)';
        mreqChoiceStudio.style.color = '#fbbf24';

        mreqChoiceAgent.classList.remove('active');
        mreqChoiceAgent.style.background = 'rgba(255,255,255,0.05)';
        mreqChoiceAgent.style.borderColor = 'rgba(255,255,255,0.1)';
        mreqChoiceAgent.style.color = '#94a3b8';
      }
    }
  }

  if (mreqChoiceStudio) mreqChoiceStudio.addEventListener('click', () => setMreqChoice('studio'));
  if (mreqChoiceAgent) mreqChoiceAgent.addEventListener('click', () => setMreqChoice('agent'));

  // Add request to list
  if (mreqBtnAddToList && mreqInputPrompt) {
    mreqBtnAddToList.addEventListener('click', () => {
      const prompt = mreqInputPrompt.value.trim();
      if (!prompt && !mreqDraftImage) {
        alert('Vui lòng nhập prompt hoặc đính kèm ảnh tham chiếu cho request này!');
        return;
      }

      savedMultiRequests.push({
        id: `req_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
        prompt: prompt || 'Sinh video từ ảnh tham chiếu',
        image: mreqDraftImage ? { ...mreqDraftImage } : null,
        ratio: activeRatio,
        duration: mreqSelectedEngine === 'agent' ? 15 : 30,
        engine: mreqSelectedEngine, // 'studio' | 'agent'
        status: 'queued'
      });

      mreqInputPrompt.value = '';
      mreqDraftImage = null;
      if (mreqImgPreviewTag) mreqImgPreviewTag.style.display = 'none';

      saveMultiRequestsToStorage();
      addLog('MULTI_REQ', `Đã thêm Request #${savedMultiRequests.length} (${mreqSelectedEngine === 'agent' ? '🤖 Agent Pro 15s' : '⚡ Studio 30s'}) vào hàng đợi.`, 'success');
    });
  }

  function renderMultiRequestsList() {
    if (!mreqRenderContainer) return;
    const total = savedMultiRequests.length;
    const doneCount = savedMultiRequests.filter(r => r.status === 'done').length;
    const queuedCount = savedMultiRequests.filter(r => r.status === 'queued').length;

    if (mreqTotalBadge) mreqTotalBadge.textContent = String(total);
    if (mreqFAll) mreqFAll.textContent = String(total);
    if (mreqFQueued) mreqFQueued.textContent = String(queuedCount);
    if (mreqFDone) mreqFDone.textContent = String(doneCount);

    const percent = total > 0 ? Math.round((doneCount / total) * 100) : 0;
    if (mreqProgressLabel) mreqProgressLabel.textContent = `Tiến độ: ${doneCount} / ${total} Request`;
    if (mreqProgressPercent) mreqProgressPercent.textContent = `${percent}%`;
    if (mreqProgressBar) mreqProgressBar.style.width = `${percent}%`;

    let filtered = savedMultiRequests;
    if (currentMreqFilter === 'queued') filtered = savedMultiRequests.filter(r => r.status === 'queued');
    else if (currentMreqFilter === 'done') filtered = savedMultiRequests.filter(r => r.status === 'done');

    if (!filtered.length) {
      mreqRenderContainer.innerHTML = '<div class="empty-state">Chưa có request nào trong danh sách.</div>';
      return;
    }

    mreqRenderContainer.innerHTML = '';

    filtered.forEach((req, idx) => {
      const realIdx = savedMultiRequests.indexOf(req);
      const card = document.createElement('div');
      card.className = 'item-card';

      let statusBadge = '<span style="color:#94a3b8;font-size:9.5px;background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;">⚪ Chờ</span>';
      if (req.status === 'running') {
        statusBadge = '<span style="color:#fbbf24;font-size:9.5px;background:rgba(245,158,11,0.2);padding:2px 6px;border-radius:4px;font-weight:700;">⏳ Đang gửi...</span>';
      } else if (req.status === 'done') {
        statusBadge = '<span style="color:#34d399;font-size:9.5px;background:rgba(16,185,129,0.2);padding:2px 6px;border-radius:4px;font-weight:700;">✅ Đã tạo</span>';
      }

      const engineBadge = req.engine === 'agent'
        ? '<span style="color:#38bdf8;font-size:9px;background:rgba(56,189,248,0.15);padding:1px 5px;border-radius:3px;font-weight:700;">🤖 Agent Pro</span>'
        : '<span style="color:#fbbf24;font-size:9px;background:rgba(251,191,36,0.15);padding:1px 5px;border-radius:3px;font-weight:700;">⚡ Studio 30s</span>';

      card.innerHTML = `
        <div style="display:flex;align-items:center;gap:6px;width:100%;">
          ${req.image && req.image.dataUrl ? `<img src="${req.image.dataUrl}" style="width:28px;height:28px;object-fit:cover;border-radius:4px;flex-shrink:0;border:1px solid #fbbf24;" />` : '<div style="width:28px;height:28px;border-radius:4px;background:#1a2336;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;">🎬</div>'}
          <div class="item-info">
            <div style="display:flex;align-items:center;gap:4px;">
              <span class="item-title">#${String(realIdx + 1).padStart(2, '0')}</span>
              ${engineBadge}
              ${statusBadge}
            </div>
            <span class="item-subtitle" title="${req.prompt}">${req.prompt}</span>
          </div>
          <div class="item-actions">
            <button type="button" class="btn-mini btn-del-req" style="color: #fca5a5;">✕</button>
          </div>
        </div>
      `;

      card.querySelector('.btn-del-req')?.addEventListener('click', () => {
        savedMultiRequests.splice(realIdx, 1);
        saveMultiRequestsToStorage();
      });

      mreqRenderContainer.appendChild(card);
    });
  }

  mreqFilterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      mreqFilterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentMreqFilter = btn.dataset.mreqFilter || 'all';
      renderMultiRequestsList();
    });
  });

  if (mreqBtnClearAll) {
    mreqBtnClearAll.addEventListener('click', () => {
      if (confirm('Xóa sạch toàn bộ danh sách Multi-Request?')) {
        savedMultiRequests = [];
        saveMultiRequestsToStorage();
        addLog('MULTI_REQ', 'Đã xóa toàn bộ request.', 'warn');
      }
    });
  }

  // Import multi-request from file
  if (mreqBtnImport && mreqFileInput) {
    mreqBtnImport.addEventListener('click', () => mreqFileInput.click());
    mreqFileInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (evt) => {
        const text = evt.target.result || '';
        try {
          if (text.startsWith('[') || text.startsWith('{')) {
            const parsed = JSON.parse(text);
            const list = Array.isArray(parsed) ? parsed : (parsed.requests || []);
            list.forEach((item, i) => {
              savedMultiRequests.push({
                id: `req_${Date.now()}_${i}`,
                prompt: item.prompt || item.text || String(item),
                image: item.image || null,
                ratio: item.ratio || '9:16',
                duration: 30,
                status: 'queued'
              });
            });
          } else {
            const lines = text.split(/\r?\n+/).map(l => l.trim()).filter(Boolean);
            lines.forEach((line, i) => {
              savedMultiRequests.push({
                id: `req_${Date.now()}_${i}`,
                prompt: line,
                image: null,
                ratio: activeRatio,
                duration: 30,
                status: 'queued'
              });
            });
          }
          saveMultiRequestsToStorage();
          addLog('MULTI_REQ', `Đã nạp request từ file: ${file.name}`, 'success');
        } catch(err) {
          alert('Lỗi nạp file: ' + err.message);
        }
        mreqFileInput.value = '';
      };
      reader.readAsText(file);
    });
  }

  // Multi-Request Pipeline Runner (Sequential & Multi-Thread)
  if (mreqBtnRunPipeline) {
    mreqBtnRunPipeline.addEventListener('click', async () => {
      if (isPipelineRunning) return;
      const queuedList = savedMultiRequests.filter(r => r.status === 'queued');
      if (!queuedList.length) {
        alert('Không có request nào ở trạng thái "Chờ chạy"!');
        return;
      }

      isPipelineRunning = true;
      isPipelinePaused = false;
      updatePipelineUIState();

      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const currentTab = tabs && tabs[0];
        const isDola = currentTab && currentTab.url && (currentTab.url.includes('dola.com') || currentTab.url.includes('doubao.com'));

        if (!isDola) {
          chrome.tabs.query({ url: ['*://*.dola.com/*', '*://*.doubao.com/*'] }, (dolaTabs) => {
            if (dolaTabs && dolaTabs.length > 0) {
              const targetTab = dolaTabs[0];
              chrome.tabs.update(targetTab.id, { active: true });
              runNextPipelineRequest(targetTab.id);
            } else {
              alert('Vui lòng mở trang Dola trước khi chạy danh sách!');
              isPipelineRunning = false;
              updatePipelineUIState();
            }
          });
          return;
        }

        runNextPipelineRequest(currentTab.id);
      });
    });
  }

  // Multi-Thread Multi-Account Runner Across All Open Tabs
  if (mreqBtnRunMultithread) {
    mreqBtnRunMultithread.addEventListener('click', async () => {
      if (isPipelineRunning) return;
      const queuedList = savedMultiRequests.filter(r => r.status === 'queued');
      if (!queuedList.length) {
        alert('Không có request nào ở trạng thái "Chờ chạy"!');
        return;
      }

      chrome.tabs.query({ url: ['*://*.dola.com/*', '*://*.doubao.com/*'] }, async (dolaTabs) => {
        if (!dolaTabs || !dolaTabs.length) {
          alert('Không tìm thấy tab Dola nào đang mở!\nVui lòng sang Tab 4 và bấm "🚀 Mở Các Tab Tài Khoản" trước.');
          return;
        }

        isPipelineRunning = true;
        isPipelinePaused = false;
        updatePipelineUIState();
        addLog('PIPELINE', `⚡ KHỞI CHẠY ĐA LUỒNG: Phân phối danh sách qua ${dolaTabs.length} Tab Tài Khoản song song!`, 'success');

        const workers = dolaTabs.map((tab, idx) => runWorkerForTab(tab.id, idx + 1, dolaTabs.length));
        await Promise.allSettled(workers);

        isPipelineRunning = false;
        isPipelinePaused = false;
        updatePipelineUIState();
        addLog('PIPELINE', '🎉 ĐÃ HOÀN THÀNH TOÀN BỘ DANH SÁCH TRÊN TẤT CẢ CÁC TÀI KHOẢN!', 'success');
      });
    });
  }

  function updatePipelineUIState() {
    if (isPipelineRunning) {
      if (mreqBtnRunPipeline) mreqBtnRunPipeline.style.display = 'none';
      if (mreqBtnRunMultithread) mreqBtnRunMultithread.style.display = 'none';
      if (mreqBtnPausePipeline) {
        mreqBtnPausePipeline.style.display = 'inline-block';
        mreqBtnPausePipeline.textContent = isPipelinePaused ? '▶️ Tiếp Tục' : '⏸️ Tạm Dừng';
      }
      if (mreqBtnStopPipeline) mreqBtnStopPipeline.style.display = 'inline-block';
    } else {
      if (mreqBtnRunPipeline) {
        mreqBtnRunPipeline.style.display = 'block';
        mreqBtnRunPipeline.textContent = '🚀 Chạy Tuần Tự (1 Tab)';
      }
      if (mreqBtnRunMultithread) {
        mreqBtnRunMultithread.style.display = 'block';
      }
      if (mreqBtnPausePipeline) mreqBtnPausePipeline.style.display = 'none';
      if (mreqBtnStopPipeline) mreqBtnStopPipeline.style.display = 'none';
    }
  }

  if (mreqBtnPausePipeline) {
    mreqBtnPausePipeline.addEventListener('click', () => {
      isPipelinePaused = !isPipelinePaused;
      updatePipelineUIState();
      addLog('PIPELINE', isPipelinePaused ? 'Đã tạm dừng Pipeline.' : 'Tiếp tục chạy Pipeline...', 'info');
      if (!isPipelinePaused && isPipelineRunning) {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          if (tabs && tabs[0]) runNextPipelineRequest(tabs[0].id);
        });
      }
    });
  }

  if (mreqBtnStopPipeline) {
    mreqBtnStopPipeline.addEventListener('click', () => {
      isPipelineRunning = false;
      isPipelinePaused = false;
      updatePipelineUIState();
      addLog('PIPELINE', 'Đã dừng hoàn toàn Pipeline.', 'warn');
    });
  }

  async function runNextPipelineRequest(tabId) {
    if (!isPipelineRunning || isPipelinePaused) return;

    const nextReq = savedMultiRequests.find(r => r.status === 'queued');
    if (!nextReq) {
      isPipelineRunning = false;
      updatePipelineUIState();
      addLog('PIPELINE', '🎉 ĐÃ HOÀN THÀNH TẤT CẢ REQUEST TRONG DANH SÁCH!', 'success');
      alert('Đã hoàn thành toàn bộ danh sách Multi-Request!');
      return;
    }

    nextReq.status = 'running';
    saveMultiRequestsToStorage();
    const realIdx = savedMultiRequests.indexOf(nextReq) + 1;
    const reqEngine = nextReq.engine || currentEngineMode || 'studio';
    addLog('PIPELINE', `[${realIdx}/${savedMultiRequests.length}] Đang xử lý (${reqEngine === 'agent' ? '🤖 Agent Pro' : '⚡ Studio 30s'}): ${nextReq.prompt.substring(0, 35)}...`, 'info');

    if (reqEngine === 'agent') {
      await monitorChatAgentTaskWithRetry(tabId, nextReq.prompt, nextReq.image);
    } else {
      try {
        await ensureTabReadyAndResponsive(tabId, 'https://www.dola.com/chat/create-image');
      } catch (e) {}
      await new Promise(resolve => {
        chrome.tabs.sendMessage(tabId, {
          type: 'STUDIO_AUTOMATE_TASK',
          prompt: nextReq.prompt,
          duration: nextReq.duration || 30,
          ratio: nextReq.ratio || activeRatio,
          image: nextReq.image || null,
          model: nextReq.model || activeModel || '2.5'
        }, async (res) => {
          if (chrome.runtime.lastError || !res || !res.success) {
            chrome.scripting.executeScript({
              target: { tabId },
              func: directDomInjectPrompt,
              args: [nextReq.prompt, nextReq.ratio || activeRatio, nextReq.duration || 30, nextReq.model || activeModel || '2.5']
            }).catch(() => {});
          }
          await monitorStudioTaskStatus(tabId, nextReq.prompt, nextReq.duration || 30, nextReq.model || activeModel || '2.5');
          resolve();
        });
      });
    }

    nextReq.status = 'done';
    saveMultiRequestsToStorage();

    if (isPipelineRunning && !isPipelinePaused) {
      setTimeout(() => runNextPipelineRequest(tabId), 2000);
    }
  }

  async function runWorkerForTab(tabId, tabIndex, totalTabs) {
    while (isPipelineRunning) {
      if (isPipelinePaused) {
        await new Promise(r => setTimeout(r, 1000));
        continue;
      }

      const nextReq = savedMultiRequests.find(r => r.status === 'queued');
      if (!nextReq) break;

      nextReq.status = 'running';
      saveMultiRequestsToStorage();
      const realIdx = savedMultiRequests.indexOf(nextReq) + 1;
      const reqEngine = nextReq.engine || currentEngineMode || 'studio';
      addLog('MULTI_THREAD', `[Tab #${tabIndex}/${totalTabs} | Req #${realIdx}] (${reqEngine === 'agent' ? '🤖 Agent Pro' : '⚡ Studio 30s'}) Gửi prompt: ${nextReq.prompt.substring(0, 30)}...`, 'info');

      if (reqEngine === 'agent') {
        await monitorChatAgentTaskWithRetry(tabId, nextReq.prompt, nextReq.image);
      } else {
        try {
          await ensureTabReadyAndResponsive(tabId, 'https://www.dola.com/chat/create-image');
        } catch (e) {}
        await new Promise(resolve => {
          chrome.tabs.sendMessage(tabId, {
            type: 'STUDIO_AUTOMATE_TASK',
            prompt: nextReq.prompt,
            duration: nextReq.duration || 30,
            ratio: nextReq.ratio || activeRatio,
            image: nextReq.image || null,
            model: nextReq.model || activeModel || '2.5'
          }, async (res) => {
            if (chrome.runtime.lastError || !res || !res.success) {
              chrome.scripting.executeScript({
                target: { tabId },
                func: directDomInjectPrompt,
                args: [nextReq.prompt, nextReq.ratio || activeRatio, nextReq.duration || 30, nextReq.model || activeModel || '2.5']
              }).catch(() => {});
            }
            await monitorStudioTaskStatus(tabId, nextReq.prompt, nextReq.duration || 30, nextReq.model || activeModel || '2.5');
            resolve();
          });
        });
      }

      nextReq.status = 'done';
      saveMultiRequestsToStorage();
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  // ========================================================================
  // 5. TAB 3: QUẢN LÝ PROMPTS HÀNG LOẠT (BULK PROMPTS)
  // ========================================================================
  const promptsFileInput = document.getElementById('prompts-file-input');
  const promptsBtnUpload = document.getElementById('prompts-btn-upload');
  const promptsBtnClear = document.getElementById('prompts-btn-clear');
  const promptsBatchTextarea = document.getElementById('prompts-batch-textarea');
  const promptsBtnAdd = document.getElementById('prompts-btn-add');
  const promptsToggleBulkMode = document.getElementById('prompts-toggle-bulkmode');
  const promptsBtnSyncClick = document.getElementById('prompts-btn-sync-click');
  const promptsBtnAutoScroll = document.getElementById('prompts-btn-autoscroll');
  const promptsRenderContainer = document.getElementById('prompts-render-container');
  const promptsTotalBadge = document.getElementById('prompts-total-badge');
  const filterCountAll = document.getElementById('filter-count-all');
  const filterCountQueued = document.getElementById('filter-count-queued');
  const filterCountDone = document.getElementById('filter-count-done');
  const promptFilterButtons = document.querySelectorAll('[data-filter]');

  function savePromptsToStorage() {
    chrome.storage.local.set({ ctb_saved_prompts: savedPrompts }, () => {
      renderPromptsList();
    });
  }

  function renderPromptsList() {
    if (!promptsRenderContainer) return;
    const total = savedPrompts.length;
    const doneCount = savedPrompts.filter(p => p.done).length;
    const queuedCount = total - doneCount;

    if (promptsTotalBadge) promptsTotalBadge.textContent = String(total);
    if (filterCountAll) filterCountAll.textContent = String(total);
    if (filterCountQueued) filterCountQueued.textContent = String(queuedCount);
    if (filterCountDone) filterCountDone.textContent = String(doneCount);

    let filtered = savedPrompts;
    if (currentPromptFilter === 'queued') filtered = savedPrompts.filter(p => !p.done);
    else if (currentPromptFilter === 'done') filtered = savedPrompts.filter(p => p.done);

    if (!filtered.length) {
      promptsRenderContainer.innerHTML = '<div class="empty-state" id="prompts-empty-box">📁 Danh sách trống. Bấm vào đây để chọn file prompt (.txt, .csv)...</div>';
      const emptyBox = document.getElementById('prompts-empty-box');
      if (emptyBox && promptsFileInput) {
        emptyBox.addEventListener('click', () => promptsFileInput.click());
      }
      return;
    }

    promptsRenderContainer.innerHTML = '';

    filtered.forEach((prompt, idx) => {
      const realIdx = savedPrompts.indexOf(prompt);
      const card = document.createElement('div');
      card.className = `item-card ${prompt.done ? 'done-state' : ''}`;
      card.style.borderLeft = prompt.done ? '3px solid #34d399' : '3px solid #ff7e00';

      card.innerHTML = `
        <div class="item-info">
          <span class="item-title">#${String(realIdx + 1).padStart(2, '0')}: ${prompt.title || 'Prompt'}</span>
          <span class="item-subtitle" title="${prompt.text}">${prompt.text}</span>
        </div>
        <div class="item-actions">
          <button type="button" class="btn-mini btn-paste-dola" title="Gửi prompt này vào ô chat Dola">📋 Dán</button>
          <button type="button" class="btn-mini btn-toggle-done" style="color: ${prompt.done ? '#34d399' : '#94a3b8'}" title="Đánh dấu trạng thái">${prompt.done ? '✓' : '○'}</button>
          <button type="button" class="btn-mini btn-del-prompt" style="color: #fca5a5;" title="Xóa">✕</button>
        </div>
      `;

      card.querySelector('.btn-paste-dola')?.addEventListener('click', () => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          if (tabs && tabs[0]) {
            chrome.tabs.sendMessage(tabs[0].id, {
              action: 'paste_prompt_to_page',
              prompt: prompt.text,
              ratio: activeRatio || '9:16',
              duration: 30
            }, (res) => {
              if (chrome.runtime.lastError || !res || !res.success) {
                chrome.scripting.executeScript({
                  target: { tabId: tabs[0].id },
                  func: directDomInjectPrompt,
                  args: [prompt.text, activeRatio || '9:16', 30]
                });
              }
            });
            prompt.done = true;
            savePromptsToStorage();
            addLog('PROMPT', `⚡ Đã dán và kích hoạt tạo prompt #${realIdx + 1} (30s) trên Dola!`, 'success');
          }
        });
      });

      card.querySelector('.btn-toggle-done')?.addEventListener('click', () => {
        prompt.done = !prompt.done;
        savePromptsToStorage();
      });

      card.querySelector('.btn-del-prompt')?.addEventListener('click', () => {
        savedPrompts.splice(realIdx, 1);
        savePromptsToStorage();
        addLog('PROMPT', `Đã xóa prompt #${realIdx + 1}.`, 'warn');
      });

      promptsRenderContainer.appendChild(card);
    });
  }

  promptFilterButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      promptFilterButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPromptFilter = btn.dataset.filter || 'all';
      renderPromptsList();
    });
  });

  if (promptsBtnAdd && promptsBatchTextarea) {
    promptsBtnAdd.addEventListener('click', () => {
      const text = promptsBatchTextarea.value.trim();
      if (!text) return;
      const lines = text.split(/\r?\n+/).map(l => l.trim()).filter(Boolean);
      if (!lines.length) return;

      lines.forEach((line) => {
        savedPrompts.push({
          title: `Prompt #${savedPrompts.length + 1}`,
          text: line,
          done: false
        });
      });

      promptsBatchTextarea.value = '';
      savePromptsToStorage();
      addLog('PROMPT', `Đã thêm ${lines.length} prompt mới vào danh sách.`, 'success');
    });
  }

  if (promptsBtnUpload && promptsFileInput) {
    promptsBtnUpload.addEventListener('click', () => promptsFileInput.click());
    promptsFileInput.addEventListener('change', (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (evt) => {
        const content = evt.target.result || '';
        const lines = content.split(/\r?\n+/).map(l => l.trim()).filter(Boolean);
        if (lines.length) {
          lines.forEach(l => {
            savedPrompts.push({
              title: `Prompt #${savedPrompts.length + 1}`,
              text: l,
              done: false
            });
          });
          savePromptsToStorage();
          addLog('FILE', `Đã nạp ${lines.length} prompt từ file ${file.name}.`, 'success');
        }
        promptsFileInput.value = '';
      };
      reader.readAsText(file);
    });
  }

  if (promptsBtnClear) {
    promptsBtnClear.addEventListener('click', () => {
      if (confirm('Xóa sạch danh sách prompt?')) {
        savedPrompts = [];
        savePromptsToStorage();
        addLog('PROMPT', 'Đã xóa toàn bộ prompt.', 'warn');
      }
    });
  }

  if (promptsBtnSyncClick) {
    promptsBtnSyncClick.addEventListener('click', () => {
      chrome.tabs.query({ url: ['*://*.dola.com/*', '*://dola.com/*'] }, (tabs) => {
        if (!tabs || !tabs.length) {
          addLog('SYNC', '⚠️ Không tìm thấy tab Dola nào đang mở!', 'warn');
          return;
        }
        let count = 0;
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'hit_create_video' }, (res) => {
            if (chrome.runtime.lastError) {
              chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: () => {
                  const btn = document.querySelector('#flow-end-msg-send, #create-video-btn, #channa-create-btn, button[aria-label*="Create Video" i], button[type="submit"]');
                  if (btn) btn.click();
                }
              }).catch(() => {});
            }
          });
          count++;
        });
        addLog('SYNC', `⚡ Đã gửi lệnh click tạo video tới ${count} tab Dola!`, 'success');
      });
    });
  }

  if (promptsBtnAutoScroll) {
    promptsBtnAutoScroll.addEventListener('click', () => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, { type: 'BRANDAI_START_CHAT_SCROLL' }).catch(() => {});
          addLog('SCROLL', 'Đã kích hoạt tự động cuộn chat để bắt video cũ.', 'info');
          window.close();
        }
      });
    });
  }

  if (promptsToggleBulkMode) {
    promptsToggleBulkMode.addEventListener('change', (e) => {
      const isBulk = e.target.checked;
      chrome.storage.local.set({ brandai_bulk_mode: isBulk });
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          if (tab.id && tab.url && (tab.url.includes('dola.com') || tab.url.includes('doubao.com'))) {
            chrome.tabs.sendMessage(tab.id, { type: 'BRANDAI_SET_BULK_MODE', enabled: isBulk }).catch(() => {});
          }
        });
      });
      addLog('BULK', isBulk ? 'Đã BẬT Thanh Dock tải hàng loạt trên Web' : 'Đã TẮT Thanh Dock tải hàng loạt', 'info');
    });
  }

  // ========================================================================
  // 6. TAB 4: VIA FACEBOOK & QUẢN LÝ TÀI KHOẢN
  // ========================================================================
  // 6. TAB 4: VIA FACEBOOK & QUẢN LÝ TÀI KHOẢN & COOKIES DOLA
  // ========================================================================
  const viaInputText = document.getElementById('via-input-text');
  const viaBtnAutoLogin = document.getElementById('via-btn-auto-login');
  const via2FaInfo = document.getElementById('via-2fa-info');
  const via2FaCode = document.getElementById('via-2fa-code');
  const viaBtnCopy2Fa = document.getElementById('via-btn-copy-2fa');

  // Dola Cookies Extractor elements
  const dolaSelectTabs = document.getElementById('dola-select-tabs');
  const dolaBtnScanTabs = document.getElementById('dola-btn-scan-tabs');
  const dolaInputAccName = document.getElementById('dola-input-acc-name');
  const dolaBtnAutoName = document.getElementById('dola-btn-auto-name');
  const dolaBtnExtractSave = document.getElementById('dola-btn-extract-save');
  const dolaExtractStatusBox = document.getElementById('dola-extract-status-box');
  const dolaStatusText = document.getElementById('dola-status-text');
  const dolaBtnCopyHeader = document.getElementById('dola-btn-copy-header');
  const dolaBtnCopyJson = document.getElementById('dola-btn-copy-json');
  const dolaBtnExportFile = document.getElementById('dola-btn-export-file');
  const dolaBtnSyncDesktop = document.getElementById('dola-btn-sync-desktop');

  // Tab 1 shortcut
  const genBtnSaveDolaCookie = document.getElementById('gen-btn-save-dola-cookie');

  let latestDolaSession = null;

  const accBtnCapture = document.getElementById('acc-btn-capture');
  const accInputTabCount = document.getElementById('acc-input-tab-count');
  const accBtnOpenTabs = document.getElementById('acc-btn-open-tabs');
  const accOpenStatus = document.getElementById('acc-open-status');
  const accFileInput = document.getElementById('acc-file-input');
  const accBtnImportFile = document.getElementById('acc-btn-import-file');
  const accBtnExportFile = document.getElementById('acc-btn-export-file');
  const accBtnClearAll = document.getElementById('acc-btn-clear-all');
  const accBtnFetchDesktop = document.getElementById('acc-btn-fetch-desktop');
  const accBtnPushDesktop = document.getElementById('acc-btn-push-desktop');
  const accSyncDesktopStatus = document.getElementById('acc-sync-desktop-status');
  const accInputName = document.getElementById('acc-input-name');
  const accInputCookies = document.getElementById('acc-input-cookies');
  const accBtnSaveProfile = document.getElementById('acc-btn-save-profile');
  const accRenderContainer = document.getElementById('acc-render-container');
  const accTotalBadge = document.getElementById('acc-total-badge');
  const accountNameBadge = document.getElementById('account-name-badge');

  // Auto Login VIA Facebook
  if (viaBtnAutoLogin && viaInputText) {
    viaBtnAutoLogin.addEventListener('click', () => {
      const rawVIA = viaInputText.value.trim();
      if (!rawVIA) {
        alert('Vui lòng dán chuỗi VIA (UID|Pass|2FA hoặc Cookie c_user=...; xs=...)!');
        return;
      }

      viaBtnAutoLogin.disabled = true;
      viaBtnAutoLogin.textContent = '⏳ Đang xử lý đăng nhập VIA Facebook...';

      chrome.runtime.sendMessage({ action: 'AUTO_LOGIN_VIA_FB', viaText: rawVIA }, (res) => {
        viaBtnAutoLogin.disabled = false;
        viaBtnAutoLogin.textContent = '🚀 ĐĂNG NHẬP VIA FACEBOOK';

        if (res && res.success) {
          addLog('VIA_FB', `✅ ${res.message || `Đã đăng nhập Facebook [UID: ${res.uid}]! Đã mở tab Dola (chưa có tài khoản) để bạn bấm Đăng nhập.`}`, 'success');

          if (res.totpCode) {
            if (via2FaInfo && via2FaCode) {
              via2FaInfo.style.display = 'flex';
              via2FaCode.textContent = res.totpCode;
            }
            try {
              navigator.clipboard.writeText(res.totpCode);
              addLog('VIA_FB', `📋 Đã sao chép mã 2FA [${res.totpCode}] vào Clipboard.`, 'info');
            } catch (e) {}
          }

          // Add to profiles
          const profName = `VIA_FB_${res.uid}`;
          savedProfiles[profName] = {
            name: profName,
            cookies: [{ name: 'fb_uid', value: res.uid, domain: '.facebook.com', path: '/' }],
            color: '#2563eb'
          };
          saveProfilesToStorage();
        } else {
          addLog('VIA_FB', `Lỗi đăng nhập VIA: ${res?.error || 'Không hợp lệ'}`, 'error');
          alert('Lỗi đăng nhập VIA: ' + (res?.error || 'Không hợp lệ'));
        }
      });
    });
  }

  if (viaBtnCopy2Fa && via2FaCode) {
    viaBtnCopy2Fa.addEventListener('click', () => {
      const code = via2FaCode.textContent.trim();
      if (code && code !== '------') {
        navigator.clipboard.writeText(code);
        viaBtnCopy2Fa.textContent = '✓ Đã chép';
        setTimeout(() => { viaBtnCopy2Fa.textContent = '📋 Copy'; }, 1500);
      }
    });
  }

  function saveProfilesToStorage() {
    chrome.storage.local.set({ multi_profiles: savedProfiles }, () => {
      renderProfilesList();
    });
  }

  function renderProfilesList() {
    if (!accRenderContainer) return;
    const names = Object.keys(savedProfiles || {});
    if (accTotalBadge) accTotalBadge.textContent = String(names.length);

    if (accountNameBadge) accountNameBadge.textContent = activeProfileName || 'Mặc định';

    const maxTabs = names.length * 2;
    if (accOpenStatus) {
      accOpenStatus.textContent = `${names.length} tài khoản sẵn sàng · Tối đa mở ${maxTabs} tab (2 tab/tài khoản)`;
    }

    if (!names.length) {
      accRenderContainer.innerHTML = '<div class="empty-state">Chưa có tài khoản nào được lưu.</div>';
      return;
    }

    accRenderContainer.innerHTML = '';

    names.forEach((name) => {
      const profile = savedProfiles[name];
      const card = document.createElement('div');
      card.className = 'item-card';

      const cookieCount = Array.isArray(profile.cookies) ? profile.cookies.length : 0;
      const isActive = name === activeProfileName;

      card.innerHTML = `
        <div style="width: 8px; height: 8px; border-radius: 50%; background: ${profile.color || '#ff7e00'}; flex-shrink: 0;"></div>
        <div class="item-info">
          <span class="item-title">${name} ${isActive ? '👑' : ''}</span>
          <span class="item-subtitle">${cookieCount} cookies</span>
        </div>
        <div class="item-actions">
          <button type="button" class="btn-mini btn-switch-acc" style="color: #38bdf8;" title="Chuyển sang tài khoản này">🔄</button>
          <button type="button" class="btn-mini btn-open-tab" style="color: #34d399;" title="Mở tab mới">🌐</button>
          <button type="button" class="btn-mini btn-del-acc" style="color: #fca5a5;" title="Xóa">✕</button>
        </div>
      `;

      card.querySelector('.btn-switch-acc')?.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'switch_profile', profileName: name }, (res) => {
          if (res && res.success) {
            activeProfileName = name;
            chrome.storage.local.set({ active_profile_name: name });
            renderProfilesList();
            addLog('ACCOUNT', `Đã chuyển sang tài khoản: ${name}`, 'success');
          } else {
            addLog('ACCOUNT', `Lỗi chuyển sang ${name}: ${res?.error || ''}`, 'error');
          }
        });
      });

      card.querySelector('.btn-open-tab')?.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'open_account_in_new_tab', profileName: name }, (res) => {
          if (res && res.success) {
            addLog('ACCOUNT', `Đã mở tab độc lập cho tài khoản: ${name}`, 'success');
          } else {
            addLog('ACCOUNT', `Lỗi mở tab cho ${name}: ${res?.error || ''}`, 'error');
          }
        });
      });

      card.querySelector('.btn-del-acc')?.addEventListener('click', () => {
        delete savedProfiles[name];
        saveProfilesToStorage();
        addLog('ACCOUNT', `Đã xóa tài khoản: ${name}`, 'warn');
      });

      accRenderContainer.appendChild(card);
    });
  }

  // ========================================================================
  // DOLA COOKIE EXTRACTOR & MANAGER LOGIC
  // ========================================================================
  function setDolaStatus(text, type = 'normal') {
    if (!dolaStatusText) return;
    dolaStatusText.innerHTML = text;
    if (dolaExtractStatusBox) {
      if (type === 'success') {
        dolaExtractStatusBox.style.borderColor = 'rgba(52, 211, 153, 0.45)';
        dolaExtractStatusBox.style.background = 'rgba(6, 78, 59, 0.35)';
      } else if (type === 'error') {
        dolaExtractStatusBox.style.borderColor = 'rgba(248, 113, 113, 0.45)';
        dolaExtractStatusBox.style.background = 'rgba(127, 29, 29, 0.35)';
      } else if (type === 'loading') {
        dolaExtractStatusBox.style.borderColor = 'rgba(251, 191, 36, 0.45)';
        dolaExtractStatusBox.style.background = 'rgba(120, 53, 15, 0.35)';
      } else {
        dolaExtractStatusBox.style.borderColor = 'rgba(255, 255, 255, 0.08)';
        dolaExtractStatusBox.style.background = 'rgba(11, 16, 27, 0.75)';
      }
    }
  }

  function loadDolaTabsList() {
    chrome.runtime.sendMessage({ action: 'GET_DOLA_TABS' }, (res) => {
      const tabs = res?.tabs || [];
      if (dolaSelectTabs) {
        dolaSelectTabs.innerHTML = '<option value="auto">🔍 Tự động nhận diện Tab Dola</option>';
        tabs.forEach(t => {
          const opt = document.createElement('option');
          opt.value = String(t.id);
          const titleCut = (t.title || 'Dola Tab').slice(0, 35);
          opt.textContent = `[Tab ${t.id}] ${titleCut}${t.active ? ' (Đang xem)' : ''}`;
          dolaSelectTabs.appendChild(opt);
        });
      }
      if (genSelectAccountTab) {
        genSelectAccountTab.innerHTML = '<option value="active">📍 Tab Đang Mở Hiện Tại</option>';
        tabs.forEach(t => {
          const opt = document.createElement('option');
          opt.value = String(t.id);
          const titleCut = (t.title || 'Dola Tab').slice(0, 35);
          opt.textContent = `[Tab ${t.id}] ${titleCut}${t.active ? ' (Active)' : ''}`;
          genSelectAccountTab.appendChild(opt);
        });
      }
    });
  }

  async function syncDolaSessionToDesktop(accountName, sessionData) {
    try {
      const resp = await fetch('http://127.0.0.1:8899/api/accounts/save-dola-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_name: accountName,
          cookies: sessionData.cookies || [],
          local_storage: sessionData.local_storage || {},
          cookie_string: sessionData.cookie_string || '',
          fb_uid: sessionData.fb_uid || ''
        })
      });
      if (resp.ok) {
        const data = await resp.json();
        return { ok: true, data };
      }
      return { ok: false, status: resp.status };
    } catch (err) {
      return { ok: false, error: err.message || String(err) };
    }
  }

  async function performDolaExtractionAndSave(specifiedTabId, customName = '') {
    setDolaStatus('⏳ Đang quét cookies & trích xuất session từ Dola...', 'loading');
    if (dolaBtnExtractSave) {
      dolaBtnExtractSave.disabled = true;
      dolaBtnExtractSave.textContent = '⏳ Đang trích xuất cookies Dola...';
    }

    return new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: 'EXTRACT_DOLA_COOKIES',
        tabId: specifiedTabId || (dolaSelectTabs ? dolaSelectTabs.value : 'auto')
      }, async (res) => {
        if (dolaBtnExtractSave) {
          dolaBtnExtractSave.disabled = false;
          dolaBtnExtractSave.textContent = '💾 LẤY & LƯU SESSION DOLA NGAY';
        }

        if (!res || !res.success || !res.cookies || res.cookies.length === 0) {
          const errMsg = res?.error || 'Không tìm thấy cookies Dola nào. Hãy đảm bảo bạn đã mở tab Dola!';
          setDolaStatus(`❌ ${errMsg}`, 'error');
          addLog('DOLA_COOKIE', errMsg, 'error');
          resolve({ success: false, error: errMsg });
          return;
        }

        latestDolaSession = res;
        const accountName = customName || (dolaInputAccName && dolaInputAccName.value.trim()) || res.detected_name || `Dola_${Date.now().toString().slice(-6)}`;
        if (dolaInputAccName) dolaInputAccName.value = accountName;

        // Lưu vào savedProfiles
        savedProfiles[accountName] = {
          name: accountName,
          cookies: res.cookies,
          local_storage: res.local_storage || {},
          cookie_string: res.cookie_string || '',
          fb_uid: res.fb_uid || '',
          dola_uid: res.dola_uid || '',
          color: '#fbbf24',
          updated_at: Date.now()
        };
        activeProfileName = accountName;
        saveProfilesToStorage();

        // Gửi sang Tool Desktop 8899
        let desktopSyncMsg = '';
        const syncRes = await syncDolaSessionToDesktop(accountName, res);
        if (syncRes.ok) {
          desktopSyncMsg = ' · <strong style="color:#34d399;">⚡ Đã đồng bộ Tool 8899</strong>';
          addLog('SYNC', `✅ Đã đồng bộ session '${accountName}' sang Seedance Studio (Port 8899)!`, 'success');
        } else {
          desktopSyncMsg = ' · <span style="color:#94a3b8;">(Tool 8899 offline, đã lưu an toàn trong Extension)</span>';
        }

        const loginBadge = res.is_logged_in 
          ? '<span style="color:#34d399;font-weight:bold;">🟢 ĐÃ ĐĂNG NHẬP</span>' 
          : '<span style="color:#fbbf24;font-weight:bold;">🟡 Chưa có sessionid</span>';

        setDolaStatus(
          `✅ <strong>${accountName}</strong>: Lấy thành công <strong>${res.cookies_count} cookies</strong> + <strong>${res.ls_count || 0} keys LS</strong> [${loginBadge}]${desktopSyncMsg}`,
          'success'
        );

        addLog('DOLA_COOKIE', `✅ Đã lưu session Dola '${accountName}' (${res.cookies_count} cookies).`, 'success');
        resolve({ success: true, accountName, res });
      });
    });
  }

  // Bind Buttons
  if (dolaBtnScanTabs) {
    dolaBtnScanTabs.addEventListener('click', () => {
      loadDolaTabsList();
      addLog('SCAN', 'Đã quét lại danh sách Tab Dola đang mở.', 'info');
    });
  }
  if (genBtnRefreshTabs) {
    genBtnRefreshTabs.addEventListener('click', () => {
      loadDolaTabsList();
      addLog('SCAN', 'Đã quét lại danh sách Tab Dola.', 'info');
    });
  }

  if (dolaBtnAutoName) {
    dolaBtnAutoName.addEventListener('click', () => {
      chrome.runtime.sendMessage({
        action: 'EXTRACT_DOLA_COOKIES',
        tabId: dolaSelectTabs ? dolaSelectTabs.value : 'auto'
      }, (res) => {
        if (res && res.detected_name) {
          if (dolaInputAccName) dolaInputAccName.value = res.detected_name;
          addLog('ACCOUNT', `Đã nhận diện tên: ${res.detected_name}`, 'info');
        } else {
          alert('Chưa nhận diện được ID từ Dola. Hãy mở tab Dola trước!');
        }
      });
    });
  }

  if (dolaBtnExtractSave) {
    dolaBtnExtractSave.addEventListener('click', () => {
      performDolaExtractionAndSave();
    });
  }

  if (dolaBtnCopyHeader) {
    dolaBtnCopyHeader.addEventListener('click', () => {
      let str = latestDolaSession?.cookie_string;
      if (!str) {
        const activeProf = savedProfiles[activeProfileName];
        if (activeProf?.cookie_string) str = activeProf.cookie_string;
        else if (Array.isArray(activeProf?.cookies)) {
          str = activeProf.cookies.map(c => `${c.name}=${c.value}`).join('; ');
        }
      }
      if (!str) {
        alert('Chưa có cookies nào. Vui lòng bấm "LẤY & LƯU SESSION DOLA" trước!');
        return;
      }
      navigator.clipboard.writeText(str).then(() => {
        const oldText = dolaBtnCopyHeader.textContent;
        dolaBtnCopyHeader.textContent = '✅ Đã Copy!';
        setTimeout(() => dolaBtnCopyHeader.textContent = oldText, 2000);
        addLog('CLIPBOARD', 'Đã copy chuỗi cookie Dola vào Clipboard', 'info');
      });
    });
  }

  if (dolaBtnCopyJson) {
    dolaBtnCopyJson.addEventListener('click', () => {
      let cookies = latestDolaSession?.cookies;
      if (!cookies) {
        const activeProf = savedProfiles[activeProfileName];
        if (Array.isArray(activeProf?.cookies)) cookies = activeProf.cookies;
      }
      if (!cookies || !cookies.length) {
        alert('Chưa có cookies nào. Vui lòng bấm "LẤY & LƯU SESSION DOLA" trước!');
        return;
      }
      navigator.clipboard.writeText(JSON.stringify(cookies, null, 2)).then(() => {
        const oldText = dolaBtnCopyJson.textContent;
        dolaBtnCopyJson.textContent = '✅ Đã Copy JSON!';
        setTimeout(() => dolaBtnCopyJson.textContent = oldText, 2000);
        addLog('CLIPBOARD', `Đã copy ${cookies.length} cookies dạng JSON`, 'info');
      });
    });
  }

  if (dolaBtnExportFile) {
    dolaBtnExportFile.addEventListener('click', () => {
      const activeProf = (latestDolaSession && {
        name: dolaInputAccName?.value || latestDolaSession.detected_name,
        cookies: latestDolaSession.cookies,
        local_storage: latestDolaSession.local_storage
      }) || savedProfiles[activeProfileName];

      if (!activeProf || !activeProf.cookies || !activeProf.cookies.length) {
        alert('Chưa có dữ liệu session để xuất file! Hãy bấm "LẤY & LƯU SESSION DOLA" trước.');
        return;
      }
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(activeProf, null, 2));
      const a = document.createElement('a');
      a.setAttribute("href", dataStr);
      a.setAttribute("download", `dola_session_${activeProf.name || 'account'}.json`);
      document.body.appendChild(a);
      a.click();
      a.remove();
      addLog('EXPORT', `Đã tải về file JSON session cho '${activeProf.name}'`, 'success');
    });
  }

  if (dolaBtnSyncDesktop) {
    dolaBtnSyncDesktop.addEventListener('click', async () => {
      const name = (dolaInputAccName && dolaInputAccName.value.trim()) || activeProfileName;
      const prof = savedProfiles[name] || latestDolaSession;
      if (!prof || !prof.cookies) {
        alert('Chưa có session Dola nào để đồng bộ! Hãy lấy cookies trước.');
        return;
      }
      dolaBtnSyncDesktop.textContent = '⏳ Đang gửi...';
      const syncRes = await syncDolaSessionToDesktop(name, prof);
      dolaBtnSyncDesktop.textContent = '⚡ Đồng Bộ Tool 8899';
      if (syncRes.ok) {
        alert(`✅ Đã đồng bộ thành công session '${name}' vào Seedance AI Video Studio (Port 8899)!`);
        addLog('SYNC', `Đồng bộ thành công session '${name}' sang Desktop Tool`, 'success');
      } else {
        alert(`⚠️ Không thể kết nối tới Tool tại http://127.0.0.1:8899: ${syncRes.error || syncRes.status}\nHãy mở ứng dụng Seedance AI Video Studio trên máy.`);
      }
    });
  }

  // Quick button from Tab 1
  if (genBtnSaveDolaCookie) {
    genBtnSaveDolaCookie.addEventListener('click', () => {
      const selectedTab = genSelectAccountTab ? genSelectAccountTab.value : 'auto';
      performDolaExtractionAndSave(selectedTab).then(res => {
        if (res && res.success) {
          alert(`✅ Đã lấy và lưu ${res.res.cookies_count} cookies Dola thành công cho tài khoản '${res.accountName}'!`);
        }
      });
    });
  }

  // Initial load of open Dola tabs
  loadDolaTabsList();

  if (accBtnCapture) {
    accBtnCapture.addEventListener('click', () => {
      accBtnCapture.disabled = true;
      accBtnCapture.textContent = '⏳ Đang bắt...';
      chrome.runtime.sendMessage({ action: 'capture_active_tab_session' }, (res) => {
        accBtnCapture.disabled = false;
        accBtnCapture.textContent = '+ Bắt Tab Hiện Tại';
        if (res && res.success) {
          const profName = res.profileName || `Tài khoản #${Object.keys(savedProfiles).length + 1}`;
          savedProfiles[profName] = {
            name: profName,
            cookies: res.cookies || [],
            color: '#10b981'
          };
          saveProfilesToStorage();
          addLog('SESSION', `Đã bắt phiên đăng nhập: ${profName}`, 'success');
        } else {
          addLog('SESSION', res?.error || 'Không thể bắt cookies.', 'error');
        }
      });
    });
  }

  if (accBtnOpenTabs && accInputTabCount) {
    accBtnOpenTabs.addEventListener('click', () => {
      const count = parseInt(accInputTabCount.value) || 1;
      accBtnOpenTabs.disabled = true;
      accBtnOpenTabs.textContent = '⏳ Đang mở...';

      chrome.runtime.sendMessage({ action: 'open_multiple_accounts', count }, (res) => {
        accBtnOpenTabs.disabled = false;
        accBtnOpenTabs.textContent = '🚀 Mở Các Tab Tài Khoản';
        if (res && res.success) {
          addLog('TABS', `Đã mở ${res.opened ? res.opened.length : count} tab tài khoản!`, 'success');
        } else {
          addLog('TABS', res?.error || 'Lỗi mở tab.', 'error');
        }
      });
    });
  }

  if (accBtnSaveProfile && accInputCookies) {
    accBtnSaveProfile.addEventListener('click', () => {
      const rawText = accInputCookies.value.trim();
      if (!rawText) return;
      const defaultName = (accInputName && accInputName.value.trim()) || '';
      const colors = ['#ff7e00', '#2563eb', '#10b981', '#fbbf24', '#ec4899', '#8b5cf6', '#06b6d4', '#f97316'];

      // Kiểm tra xem có phải định dạng JSON nhiều tài khoản hoặc JSON array/dict không
      if (rawText.startsWith('[') || rawText.startsWith('{')) {
        try {
          const parsed = JSON.parse(rawText);
          let multiImported = 0;

          // Case A: Array các tài khoản: [{ name: "acc1", cookies: [...] }]
          if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].name && parsed[0].cookies) {
            parsed.forEach((acc, idx) => {
              const aName = acc.name || `Tài khoản #${Object.keys(savedProfiles).length + 1}`;
              savedProfiles[aName] = {
                name: aName,
                cookies: Array.isArray(acc.cookies) ? acc.cookies : [],
                local_storage: acc.local_storage || {},
                fb_uid: acc.fb_uid || '',
                dola_uid: acc.dola_uid || '',
                color: colors[(Object.keys(savedProfiles).length + idx) % colors.length]
              };
              multiImported++;
            });
          }
          // Case B: Multi-account Object: { "acc1": [...], "acc2": { cookies: [...] } } hoặc { accounts: [...] }
          else if (typeof parsed === 'object' && !Array.isArray(parsed) && !parsed.name && !parsed.value) {
            const dataObj = (parsed.accounts && typeof parsed.accounts === 'object') ? parsed.accounts : (parsed.sessions || parsed.profiles || parsed);
            if (Array.isArray(dataObj)) {
              dataObj.forEach((acc, idx) => {
                const aName = acc.name || `Tài khoản #${Object.keys(savedProfiles).length + 1}`;
                savedProfiles[aName] = {
                  name: aName,
                  cookies: Array.isArray(acc.cookies) ? acc.cookies : (Array.isArray(acc) ? acc : []),
                  local_storage: acc.local_storage || {},
                  fb_uid: acc.fb_uid || '',
                  dola_uid: acc.dola_uid || '',
                  color: colors[(Object.keys(savedProfiles).length + idx) % colors.length]
                };
                multiImported++;
              });
            } else {
              Object.entries(dataObj).forEach(([accName, accVal], idx) => {
                let cList = [];
                let ls = {};
                let fbUid = '';
                let dolaUid = '';
                if (Array.isArray(accVal)) {
                  cList = accVal;
                } else if (accVal && typeof accVal === 'object') {
                  cList = Array.isArray(accVal.cookies) ? accVal.cookies : [];
                  ls = accVal.local_storage || {};
                  fbUid = accVal.fb_uid || '';
                  dolaUid = accVal.dola_uid || '';
                }
                if (cList.length > 0) {
                  savedProfiles[accName] = {
                    name: accName,
                    cookies: cList,
                    local_storage: ls,
                    fb_uid: fbUid,
                    dola_uid: dolaUid,
                    color: colors[(Object.keys(savedProfiles).length + idx) % colors.length]
                  };
                  multiImported++;
                }
              });
            }
          }

          if (multiImported > 0) {
            accInputCookies.value = '';
            if (accInputName) accInputName.value = '';
            saveProfilesToStorage();
            addLog('ACCOUNT', `✅ Đã lưu ${multiImported} tài khoản vào danh sách!`, 'success');
            alert(`✅ Đã nhận diện và lưu thành công ${multiImported} tài khoản!`);
            return;
          }
        } catch (e) {
          // Bỏ qua lỗi để fallback xuống parse tài khoản đơn bên dưới
        }
      }

      // Fallback: Parse 1 tài khoản đơn (JSON array hoặc chuỗi c_user=...; xs=...)
      const name = defaultName || `Tài khoản #${Object.keys(savedProfiles).length + 1}`;
      let cookies = [];
      try {
        if (rawText.startsWith('[') || rawText.startsWith('{')) {
          cookies = JSON.parse(rawText);
          if (!Array.isArray(cookies) && cookies.cookies) cookies = cookies.cookies;
        } else {
          const lines = rawText.split(/\r?\n+/);
          lines.forEach(line => {
            if (!line.includes('=')) return;
            const parts = line.split(';');
            parts.forEach(p => {
              const [k, v] = p.trim().split('=');
              if (k && v) cookies.push({ name: k, value: v, domain: '.dola.com', path: '/' });
            });
          });
        }
      } catch (e) {
        alert('Lỗi định dạng cookies!');
        return;
      }

      savedProfiles[name] = {
        name,
        cookies: Array.isArray(cookies) ? cookies : [cookies],
        color: '#ff7e00'
      };

      accInputCookies.value = '';
      if (accInputName) accInputName.value = '';
      saveProfilesToStorage();
      addLog('ACCOUNT', `Đã lưu tài khoản: ${name}`, 'success');
    });
  }

  if (accBtnImportFile && accFileInput) {
    accBtnImportFile.addEventListener('click', () => accFileInput.click());
    accFileInput.addEventListener('change', (e) => {
      const files = Array.from(e.target.files || []);
      if (!files.length) return;

      const colors = ['#ff7e00', '#2563eb', '#10b981', '#fbbf24', '#ec4899', '#8b5cf6', '#06b6d4', '#f97316'];
      let importedCount = 0;

      files.forEach((file) => {
        const reader = new FileReader();
        reader.onload = (evt) => {
          const content = (evt.target.result || '').trim();
          try {
            const parsed = JSON.parse(content);

            // Case A: Array of account objects [{ name: "acc1", cookies: [...] }, ...]
            if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].name && parsed[0].cookies) {
              parsed.forEach((acc, idx) => {
                const aName = acc.name || `Tài khoản #${Object.keys(savedProfiles).length + 1}`;
                savedProfiles[aName] = {
                  name: aName,
                  cookies: Array.isArray(acc.cookies) ? acc.cookies : [],
                  color: colors[(Object.keys(savedProfiles).length + idx) % colors.length]
                };
                importedCount++;
              });
            }
            // Case B: Simple cookie list [ { name: "...", value: "..." }, ... ]
            else if (Array.isArray(parsed)) {
              const name = file.name.replace(/\.[^/.]+$/, "") || `Tài khoản #${Object.keys(savedProfiles).length + 1}`;
              savedProfiles[name] = {
                name,
                cookies: parsed,
                color: colors[Object.keys(savedProfiles).length % colors.length]
              };
              importedCount++;
            }
            // Case C: Multi-account Object { "fb01": [...], "tungdhc": { cookies: [...] } }
            else if (typeof parsed === 'object' && parsed !== null) {
              // Check if wrapped in "accounts" or "sessions"
              const dataObj = parsed.accounts && typeof parsed.accounts === 'object' ? parsed.accounts : (parsed.sessions || parsed);
              
              if (Array.isArray(dataObj)) {
                dataObj.forEach((acc, idx) => {
                  const aName = acc.name || `Tài khoản #${Object.keys(savedProfiles).length + 1}`;
                  savedProfiles[aName] = {
                    name: aName,
                    cookies: Array.isArray(acc.cookies) ? acc.cookies : (Array.isArray(acc) ? acc : []),
                    color: colors[(Object.keys(savedProfiles).length + idx) % colors.length]
                  };
                  importedCount++;
                });
              } else {
                Object.entries(dataObj).forEach(([accName, accVal], idx) => {
                  let cList = [];
                  if (Array.isArray(accVal)) {
                    cList = accVal;
                  } else if (accVal && Array.isArray(accVal.cookies)) {
                    cList = accVal.cookies;
                  }
                  if (cList.length > 0) {
                    savedProfiles[accName] = {
                      name: accName,
                      cookies: cList,
                      color: colors[(Object.keys(savedProfiles).length + idx) % colors.length]
                    };
                    importedCount++;
                  }
                });
              }
            }
            saveProfilesToStorage();
            addLog('IMPORT', `✅ Đã nạp thành công ${importedCount} tài khoản từ ${file.name}!`, 'success');
          } catch(err) {
            addLog('ERROR', `Lỗi đọc file ${file.name}: ${err?.message || err}`, 'error');
          }
        };
        reader.readAsText(file);
      });
      accFileInput.value = '';
    });
  }

  if (accBtnClearAll) {
    accBtnClearAll.addEventListener('click', () => {
      if (confirm('Xóa toàn bộ danh sách tài khoản đã lưu?')) {
        savedProfiles = {};
        saveProfilesToStorage();
        addLog('ACCOUNT', 'Đã xóa toàn bộ tài khoản.', 'warn');
      }
    });
  }

  // --- SYNC WITH DESKTOP STUDIO (PORT 8899) & EXPORT PROFILES ---
  function setSyncStatus(msg, isSuccess = true) {
    if (!accSyncDesktopStatus) return;
    accSyncDesktopStatus.innerHTML = isSuccess
      ? `<span style="color: #34d399;">${msg}</span>`
      : `<span style="color: #f87171;">${msg}</span>`;
  }

  if (accBtnExportFile) {
    accBtnExportFile.addEventListener('click', () => {
      const names = Object.keys(savedProfiles || {});
      if (!names.length) {
        alert('Chưa có tài khoản nào được lưu để xuất file!');
        return;
      }
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(savedProfiles, null, 2));
      const a = document.createElement('a');
      a.setAttribute("href", dataStr);
      a.setAttribute("download", `dola_multi_profiles_${Date.now()}.json`);
      document.body.appendChild(a);
      a.click();
      a.remove();
      addLog('EXPORT', `Đã xuất ${names.length} tài khoản ra file JSON.`, 'success');
    });
  }

  if (accBtnFetchDesktop) {
    accBtnFetchDesktop.addEventListener('click', async () => {
      accBtnFetchDesktop.disabled = true;
      accBtnFetchDesktop.textContent = '⏳ Đang lấy...';
      setSyncStatus('⏳ Đang kết nối tới Tool Seedance Studio (Port 8899)...');

      try {
        const resp = await fetch('http://127.0.0.1:8899/api/accounts/export-cookies');
        if (!resp.ok) {
          throw new Error(`Mã lỗi HTTP: ${resp.status}`);
        }
        const data = await resp.json();
        const accounts = data.accounts || [];
        if (!accounts.length) {
          throw new Error('Tool chưa có session tài khoản nào được lưu!');
        }

        const colors = ['#ff7e00', '#2563eb', '#10b981', '#fbbf24', '#ec4899', '#8b5cf6', '#06b6d4', '#f97316'];
        let imported = 0;

        accounts.forEach((acc, idx) => {
          const aName = acc.name || `Tài khoản #${Object.keys(savedProfiles).length + 1}`;
          savedProfiles[aName] = {
            name: aName,
            cookies: Array.isArray(acc.cookies) ? acc.cookies : [],
            local_storage: acc.local_storage || {},
            cookie_string: acc.cookie_string || '',
            fb_uid: acc.fb_uid || '',
            dola_uid: acc.dola_uid || '',
            color: colors[(Object.keys(savedProfiles).length + idx) % colors.length],
            updated_at: Date.now()
          };
          imported++;
        });

        saveProfilesToStorage();
        const succMsg = `✅ Đã đồng bộ thành công ${imported} tài khoản từ Tool Seedance Studio!`;
        setSyncStatus(succMsg, true);
        addLog('SYNC', succMsg, 'success');
        alert(succMsg);
      } catch (err) {
        const errMsg = `❌ Không thể kết nối tới Tool (Port 8899): ${err.message || err}. Hãy khởi chạy file Chay_Seedance_Studio.bat!`;
        setSyncStatus(errMsg, false);
        addLog('SYNC', errMsg, 'error');
        alert(errMsg);
      } finally {
        accBtnFetchDesktop.disabled = false;
        accBtnFetchDesktop.textContent = '⬇️ LẤY HẾT TỪ TOOL';
      }
    });
  }

  if (accBtnPushDesktop) {
    accBtnPushDesktop.addEventListener('click', async () => {
      const names = Object.keys(savedProfiles || {});
      if (!names.length) {
        alert('Extension chưa có tài khoản nào để đẩy sang Tool!');
        return;
      }

      accBtnPushDesktop.disabled = true;
      accBtnPushDesktop.textContent = '⏳ Đang gửi...';
      setSyncStatus(`⏳ Đang đẩy ${names.length} tài khoản sang Tool Seedance Studio...`);

      try {
        const resp = await fetch('http://127.0.0.1:8899/api/accounts/update-bulk-cookies', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profiles: savedProfiles })
        });
        if (!resp.ok) {
          throw new Error(`Mã lỗi HTTP: ${resp.status}`);
        }
        const data = await resp.json();
        const succMsg = `✅ Đã cập nhật thành công ${data.count || names.length} tài khoản vào Tool Seedance Studio!`;
        setSyncStatus(succMsg, true);
        addLog('SYNC', succMsg, 'success');
        alert(succMsg);
      } catch (err) {
        const errMsg = `❌ Không thể đẩy sang Tool (Port 8899): ${err.message || err}. Hãy khởi chạy Seedance Studio!`;
        setSyncStatus(errMsg, false);
        addLog('SYNC', errMsg, 'error');
        alert(errMsg);
      } finally {
        accBtnPushDesktop.disabled = false;
        accBtnPushDesktop.textContent = '⬆️ ĐẨY HẾT SANG TOOL';
      }
    });
  }

  // ========================================================================
  // 7. TAB 5: CÀI ĐẶT BYPASS (SETTINGS)
  // ========================================================================
  const setSelectDuration = document.getElementById('set-select-duration');
  const setChkAutoRotate = document.getElementById('set-chk-autorotate');
  const setChkAutoNext = document.getElementById('set-chk-autonext');
  const setChkAutoDownload = document.getElementById('set-chk-autodownload');
  const setChkOnlyNewVideos = document.getElementById('set-chk-only-new-videos');
  const setChkShowVideoBtn = document.getElementById('set-chk-show-video-btn');
  const setChkBulkMode = document.getElementById('set-chk-bulkmode');
  const setChkSafety = document.getElementById('set-chk-safety');

  function saveSettings() {
    const settings = {
      setting_enforce_duration: setSelectDuration ? setSelectDuration.value : '30',
      setting_auto_rotate: setChkAutoRotate ? setChkAutoRotate.checked : true,
      setting_auto_advance: setChkAutoNext ? setChkAutoNext.checked : true,
      setting_auto_download: setChkAutoDownload ? setChkAutoDownload.checked : true,
      setting_only_new_videos: setChkOnlyNewVideos ? setChkOnlyNewVideos.checked : true,
      setting_show_video_btn: setChkShowVideoBtn ? setChkShowVideoBtn.checked : true,
      brandai_bulk_mode: setChkBulkMode ? setChkBulkMode.checked : false,
      setting_safety_filter: setChkSafety ? setChkSafety.checked : true
    };
    chrome.storage.local.set(settings);

    chrome.tabs.query({}, (tabs) => {
      tabs.forEach(tab => {
        if (tab.id && tab.url && (tab.url.includes('dola.com') || tab.url.includes('doubao.com'))) {
          chrome.tabs.sendMessage(tab.id, { type: 'UPDATE_SETTINGS', settings }).catch(() => {});
          chrome.tabs.sendMessage(tab.id, { type: 'BRANDAI_SET_BULK_MODE', enabled: settings.brandai_bulk_mode }).catch(() => {});
          chrome.tabs.sendMessage(tab.id, {
            type: 'BRANDAI_SET_DOWNLOAD_PREFERENCES',
            onlyNewVideos: settings.setting_only_new_videos,
            showVideoBtn: settings.setting_show_video_btn
          }).catch(() => {});
        }
      });
    });
    addLog('SETTINGS', `Đã lưu cấu hình: ${settings.setting_enforce_duration}s (Chỉ tải mới: ${settings.setting_only_new_videos ? 'Bật' : 'Tắt'})`, 'info');
  }

  [setSelectDuration, setChkAutoRotate, setChkAutoNext, setChkAutoDownload, setChkOnlyNewVideos, setChkShowVideoBtn, setChkBulkMode, setChkSafety].forEach(elem => {
    if (elem) elem.addEventListener('change', saveSettings);
  });

  // ========================================================================
  // 8. INITIAL LOAD FROM CHROME STORAGE
  // ========================================================================
  chrome.storage.local.get([
    'zdola_saved_ratio',
    'ctb_saved_prompts',
    'ctb_multi_requests',
    'multi_profiles',
    'active_profile_name',
    'zdola_recent_downloads',
    'setting_enforce_duration',
    'setting_auto_rotate',
    'setting_auto_advance',
    'setting_auto_download',
    'setting_only_new_videos',
    'setting_show_video_btn',
    'brandai_bulk_mode',
    'setting_safety_filter'
  ], (res) => {
    if (res.zdola_saved_ratio) {
      activeRatio = res.zdola_saved_ratio;
      genRatioButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.ratio === activeRatio);
      });
    }

    if (Array.isArray(res.ctb_saved_prompts)) {
      savedPrompts = res.ctb_saved_prompts;
      renderPromptsList();
    }

    if (Array.isArray(res.ctb_multi_requests)) {
      savedMultiRequests = res.ctb_multi_requests;
      renderMultiRequestsList();
    }

    if (res.multi_profiles && typeof res.multi_profiles === 'object') {
      savedProfiles = res.multi_profiles;
      if (res.active_profile_name) activeProfileName = res.active_profile_name;
      renderProfilesList();
    }

    if (Array.isArray(res.zdola_recent_downloads)) {
      recentDownloads = res.zdola_recent_downloads;
      renderRecentDownloads();
    }

    if (res.setting_enforce_duration && setSelectDuration) {
      setSelectDuration.value = String(res.setting_enforce_duration);
    }
    if (typeof res.setting_auto_rotate === 'boolean' && setChkAutoRotate) {
      setChkAutoRotate.checked = res.setting_auto_rotate;
    }
    if (typeof res.setting_auto_advance === 'boolean' && setChkAutoNext) {
      setChkAutoNext.checked = res.setting_auto_advance;
    }
    if (typeof res.setting_auto_download === 'boolean' && setChkAutoDownload) {
      setChkAutoDownload.checked = res.setting_auto_download;
      if (genToggleAutoDl) genToggleAutoDl.checked = res.setting_auto_download;
    }
    if (typeof res.setting_only_new_videos === 'boolean' && setChkOnlyNewVideos) {
      setChkOnlyNewVideos.checked = res.setting_only_new_videos;
    }
    if (typeof res.setting_show_video_btn === 'boolean' && setChkShowVideoBtn) {
      setChkShowVideoBtn.checked = res.setting_show_video_btn;
    }
    if (typeof res.brandai_bulk_mode === 'boolean') {
      if (setChkBulkMode) setChkBulkMode.checked = res.brandai_bulk_mode;
      if (promptsToggleBulkMode) promptsToggleBulkMode.checked = res.brandai_bulk_mode;
    }
    if (typeof res.setting_safety_filter === 'boolean' && setChkSafety) {
      setChkSafety.checked = res.setting_safety_filter;
    }

    addLog('INIT', 'Dola 30s Studio Pro đã sẵn sàng!', 'success');
  });

  // Listen for auto download verified messages
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === 'BRANDAI_RAW_VIDEO_DOWNLOAD_VERIFIED' || msg?.type === 'AUTO_DOWNLOAD_COMPLETED') {
      const cleanName = String(msg.filename || 'Dola_30s_Video.mp4').replace(/^TheBrandAI_Videos\//i, '').replace(/\.mp4$/i, '');
      const item = {
        filename: cleanName,
        timestamp: Date.now(),
        prompt: cleanName
      };
      recentDownloads.unshift(item);
      chrome.storage.local.set({ zdola_recent_downloads: recentDownloads });
      renderRecentDownloads();
      addLog('DOWNLOAD', `🎬 Đã tải video Master 1080P: ${cleanName}`, 'success');
    }
  });

  // ========================================================================
  // 8. PROXY VPN MANAGER CONTROLLER (PER-PROFILE / PER-ACCOUNT)
  // ========================================================================
  const proxyStatusBadge = document.getElementById('proxy-status-badge');
  const proxyCurrentIpDisplay = document.getElementById('proxy-current-ip-display');
  const proxyGeoDisplay = document.getElementById('proxy-geo-display');
  const proxyBtnTestLive = document.getElementById('proxy-btn-test-live');
  const proxyToggleEnabled = document.getElementById('proxy-toggle-enabled');
  const proxyModeBadgeBox = document.getElementById('proxy-mode-badge-box');
  const proxyModeBadgeText = document.getElementById('proxy-mode-badge-text');
  const proxyBtnQuickToggle = document.getElementById('proxy-btn-quick-toggle');
  const proxySrcBtnVpn = document.getElementById('proxy-src-btn-vpn');
  const proxySrcBtnCustom = document.getElementById('proxy-src-btn-custom');
  const proxySectionVpn = document.getElementById('proxy-section-vpn');
  const proxySectionCustom = document.getElementById('proxy-section-custom');
  const proxySelectVpnPort = document.getElementById('proxy-select-vpn-port');
  const proxyBtnRefreshVpnList = document.getElementById('proxy-btn-refresh-vpn-list');
  const proxySelectScheme = document.getElementById('proxy-select-scheme');
  const proxyInputAccName = document.getElementById('proxy-input-acc-name');
  const proxyInputHost = document.getElementById('proxy-input-host');
  const proxyInputPort = document.getElementById('proxy-input-port');
  const proxyInputUser = document.getElementById('proxy-input-user');
  const proxyInputPass = document.getElementById('proxy-input-pass');
  const proxyInputRaw = document.getElementById('proxy-input-raw');
  const proxyBtnApply = document.getElementById('proxy-btn-apply');
  const proxyBtnSyncTool = document.getElementById('proxy-btn-sync-tool');
  const proxyBtnDisable = document.getElementById('proxy-btn-disable');
  const proxyApplyStatusText = document.getElementById('proxy-apply-status-text');

  let activeProxySource = 'vpn_tool';
  const rotate5m = document.getElementById('proxy-auto-rotate-5m');
  const rotateStatus = document.getElementById('proxy-rotation-status');
  function showRotationStatus(status) {
    if (!rotateStatus || !status) return;
    if (!status.enabled) { rotateStatus.textContent = 'Tự xoay đang tắt hoặc đang dùng proxy ngoài.'; return; }
    if (!status.success) { rotateStatus.textContent = status.error || 'Chưa kết nối được VPN2Proxy.'; return; }
    const row = status.ports?.[0];
    const labels = { waiting: 'Đã hẹn lịch 5 phút', rotating: 'Đang xoay IP', changed: 'Đã xác minh IP mới',
      unchanged: 'Đã kết nối lại nhưng IP không đổi', rotation_failed: 'Xoay IP thất bại / engine chưa hỗ trợ',
      proxy_not_running: 'Proxy chưa chạy; chưa thể xoay IP' };
    rotateStatus.textContent = row ? `${labels[row.last_result] || row.last_result}${row.active && row.next_at ? ' · Lượt tới: ' + new Date(row.next_at * 1000).toLocaleTimeString() : ''}` : 'Chờ cổng proxy hợp lệ.';
  }
  chrome.storage.local.get(['dola_vpn_auto_rotate', 'dola_rotation_status'], saved => {
    if (rotate5m) rotate5m.checked = saved.dola_vpn_auto_rotate !== false;
    showRotationStatus(saved.dola_rotation_status);
  });
  rotate5m?.addEventListener('change', () => {
    chrome.storage.local.set({ dola_vpn_auto_rotate: rotate5m.checked });
  });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.dola_rotation_status) showRotationStatus(changes.dola_rotation_status.newValue);
  });

  function updateProxyModeUI(isEnabled) {
    if (proxyToggleEnabled) proxyToggleEnabled.checked = isEnabled;
    if (isEnabled) {
      if (proxyModeBadgeBox) {
        proxyModeBadgeBox.style.background = 'rgba(16,185,129,0.15)';
        proxyModeBadgeBox.style.borderColor = 'rgba(16,185,129,0.35)';
      }
      if (proxyModeBadgeText) {
        proxyModeBadgeText.textContent = '🟢 CHẾ ĐỘ PROXY: ĐANG BẬT';
        proxyModeBadgeText.style.color = '#34d399';
      }
      if (proxyBtnQuickToggle) {
        proxyBtnQuickToggle.textContent = 'Tắt Proxy';
        proxyBtnQuickToggle.style.background = 'rgba(239,68,68,0.2)';
        proxyBtnQuickToggle.style.color = '#fca5a5';
        proxyBtnQuickToggle.style.borderColor = 'rgba(239,68,68,0.4)';
      }
    } else {
      if (proxyModeBadgeBox) {
        proxyModeBadgeBox.style.background = 'rgba(100,116,139,0.15)';
        proxyModeBadgeBox.style.borderColor = 'rgba(100,116,139,0.35)';
      }
      if (proxyModeBadgeText) {
        proxyModeBadgeText.textContent = '⚪ CHẾ ĐỘ PROXY: ĐÃ TẮT (MẠNG TRỰC TIẾP)';
        proxyModeBadgeText.style.color = '#94a3b8';
      }
      if (proxyBtnQuickToggle) {
        proxyBtnQuickToggle.textContent = 'Bật Proxy';
        proxyBtnQuickToggle.style.background = 'rgba(16,185,129,0.2)';
        proxyBtnQuickToggle.style.color = '#34d399';
        proxyBtnQuickToggle.style.borderColor = 'rgba(16,185,129,0.4)';
      }
      if (proxyStatusBadge) {
        proxyStatusBadge.textContent = 'DIRECT (OFF)';
        proxyStatusBadge.style.color = '#94a3b8';
        proxyStatusBadge.style.background = 'rgba(255,255,255,0.1)';
      }
      if (proxyCurrentIpDisplay) proxyCurrentIpDisplay.textContent = 'Mạng trực tiếp (Direct)';
      if (proxyGeoDisplay) proxyGeoDisplay.textContent = 'Proxy đang tắt. Chrome kết nối bằng IP mạng thật của bạn.';
    }
  }

  function switchProxySourceUI(source) {
    activeProxySource = source || 'vpn_tool';
    if (activeProxySource === 'custom') {
      if (proxySrcBtnVpn) {
        proxySrcBtnVpn.style.background = 'rgba(255,255,255,0.05)';
        proxySrcBtnVpn.style.borderColor = 'rgba(255,255,255,0.15)';
        proxySrcBtnVpn.style.color = '#94a3b8';
      }
      if (proxySrcBtnCustom) {
        proxySrcBtnCustom.style.background = 'rgba(167,139,250,0.2)';
        proxySrcBtnCustom.style.borderColor = '#a78bfa';
        proxySrcBtnCustom.style.color = '#a78bfa';
      }
      if (proxySectionVpn) proxySectionVpn.style.display = 'none';
      if (proxySectionCustom) proxySectionCustom.style.display = 'block';
    } else {
      if (proxySrcBtnVpn) {
        proxySrcBtnVpn.style.background = 'rgba(56,189,248,0.2)';
        proxySrcBtnVpn.style.borderColor = '#38bdf8';
        proxySrcBtnVpn.style.color = '#38bdf8';
      }
      if (proxySrcBtnCustom) {
        proxySrcBtnCustom.style.background = 'rgba(255,255,255,0.05)';
        proxySrcBtnCustom.style.borderColor = 'rgba(255,255,255,0.15)';
        proxySrcBtnCustom.style.color = '#94a3b8';
      }
      if (proxySectionVpn) proxySectionVpn.style.display = 'block';
      if (proxySectionCustom) proxySectionCustom.style.display = 'none';
    }
  }

  if (proxySrcBtnVpn) {
    proxySrcBtnVpn.addEventListener('click', () => switchProxySourceUI('vpn_tool'));
  }
  if (proxySrcBtnCustom) {
    proxySrcBtnCustom.addEventListener('click', () => switchProxySourceUI('custom'));
  }

  if (proxyBtnQuickToggle) {
    proxyBtnQuickToggle.addEventListener('click', () => {
      const isCurrentlyEnabled = proxyToggleEnabled ? proxyToggleEnabled.checked : true;
      if (isCurrentlyEnabled) {
        if (proxyBtnDisable) proxyBtnDisable.click();
      } else {
        if (proxyToggleEnabled) proxyToggleEnabled.checked = true;
        if (proxyBtnApply) proxyBtnApply.click();
      }
    });
  }

  function parseProxyString(raw) {
    if (!raw) return null;
    raw = String(raw).trim();
    if (!raw) return null;

    let scheme = 'http';
    let user = '', pass = '', host = '', port = '';

    if (raw.startsWith('http://') || raw.startsWith('https://') || raw.startsWith('socks5://') || raw.startsWith('socks4://')) {
      const parts = raw.split('://');
      scheme = parts[0].toLowerCase();
      let rest = parts[1];
      if (rest.includes('@')) {
        const atParts = rest.split('@');
        const up = atParts[0].split(':');
        user = up[0] || '';
        pass = up[1] || '';
        const hp = atParts[1].split(':');
        host = hp[0] || '127.0.0.1';
        port = hp[1] || '80';
      } else {
        const hp = rest.split(':');
        host = hp[0] || '127.0.0.1';
        port = hp[1] || '80';
      }
    } else if (raw.split(':').length === 4) {
      const p = raw.split(':');
      host = p[0];
      port = p[1];
      user = p[2];
      pass = p[3];
    } else if (raw.includes('@')) {
      const atParts = raw.split('@');
      const up = atParts[0].split(':');
      user = up[0] || '';
      pass = up[1] || '';
      const hp = atParts[1].split(':');
      host = hp[0] || '127.0.0.1';
      port = hp[1] || '80';
    } else if (raw.split(':').length === 2) {
      const p = raw.split(':');
      host = p[0];
      port = p[1];

    }

    return {
      scheme: scheme.includes('socks') ? 'socks5' : 'http',
      host: host || '127.0.0.1',
      port: parseInt(port) || 10000,
      user,
      pass
    };
  }

  function checkCurrentPublicIp() {
    if (proxyCurrentIpDisplay) proxyCurrentIpDisplay.textContent = '⏳ Đang kiểm tra...';
    if (proxyGeoDisplay) proxyGeoDisplay.textContent = 'Đang đo kết nối mạng thực tế...';
    if (proxyStatusBadge) {
      proxyStatusBadge.textContent = 'CHECKING...';
      proxyStatusBadge.style.color = '#38bdf8';
    }

    chrome.runtime.sendMessage({ action: 'TEST_PROXY_IP' }, (res) => {
      if (res && res.ok && res.ip) {
        if (proxyCurrentIpDisplay) proxyCurrentIpDisplay.textContent = res.ip;
        const country = res.country ? `[${res.country}] ` : '';
        const city = res.city ? `${res.city}, ` : '';
        const latency = res.latency ? ` • Ping: ${res.latency}ms` : '';
        if (proxyGeoDisplay) proxyGeoDisplay.textContent = `📍 ${country}${city}Kết nối hoạt động ổn định${latency}`;
        if (proxyStatusBadge) {
          proxyStatusBadge.textContent = 'ONLINE (ACTIVE)';
          proxyStatusBadge.style.color = '#34d399';
          proxyStatusBadge.style.background = 'rgba(16,185,129,0.2)';
        }
        addLog('PROXY', `Kiểm tra IP thành công: ${res.ip}${latency}`, 'success');
      } else {
        if (proxyCurrentIpDisplay) proxyCurrentIpDisplay.textContent = 'Lỗi kết nối';
        if (proxyGeoDisplay) proxyGeoDisplay.textContent = `Không đo được IP (${res?.error || 'Timeout'}). Kiểm tra xem Tool VPN đã mở chưa.`;
        if (proxyStatusBadge) {
          proxyStatusBadge.textContent = 'ERROR / OFFLINE';
          proxyStatusBadge.style.color = '#f87171';
          proxyStatusBadge.style.background = 'rgba(239,68,68,0.2)';
        }
        addLog('PROXY', `Lỗi kiểm tra IP: ${res?.error || 'Timeout'}`, 'error');
      }
    });
  }

  function loadSavedProxySettings() {
    chrome.runtime.sendMessage({ action: 'GET_EXTENSION_PROXY' }, (res) => {
      if (res && res.ok) {
        const isEnabled = !!res.enabled;
        const cfg = res.config;
        updateProxyModeUI(isEnabled);
        if (cfg) {
          switchProxySourceUI(cfg.source || 'vpn_tool');
          if (proxyInputHost) proxyInputHost.value = cfg.host || '127.0.0.1';
          if (proxyInputPort) proxyInputPort.value = cfg.port || 10000;
          if (proxyInputUser) proxyInputUser.value = cfg.username || '';
          if (proxyInputPass) proxyInputPass.value = cfg.password || '';
          if (proxySelectScheme) proxySelectScheme.value = cfg.scheme || 'http';
          if (proxyInputAccName && cfg.account_name) proxyInputAccName.value = cfg.account_name;
          if (proxyInputRaw && cfg.raw_proxy) proxyInputRaw.value = cfg.raw_proxy;

          const matchingRaw = `${cfg.host || '127.0.0.1'}:${cfg.port || 10000}:${cfg.username || ''}:${cfg.password || ''}`;
          if (proxySelectVpnPort) {
            let matched = false;
            for (let i = 0; i < proxySelectVpnPort.options.length; i++) {
              if (proxySelectVpnPort.options[i].value === matchingRaw) {
                proxySelectVpnPort.selectedIndex = i;
                matched = true;
                break;
              }
            }
            if (!matched) {
              const option = document.createElement('option');
              option.value = matchingRaw;
              option.textContent = `Đã lưu: ${cfg.host}:${cfg.port} · Quét để kiểm tra`;
              proxySelectVpnPort.appendChild(option);
              option.selected = true;
            }
          }
        }
        if (isEnabled) {
          checkCurrentPublicIp();
        }
      }
    });
  }

  if (proxySelectVpnPort) {
    proxySelectVpnPort.addEventListener('change', () => {
      const val = proxySelectVpnPort.value;
      const parsed = parseProxyString(val);
      if (parsed) {
        if (proxyInputHost) proxyInputHost.value = parsed.host;
        if (proxyInputPort) proxyInputPort.value = parsed.port;
        if (proxyInputUser) proxyInputUser.value = parsed.user;
        if (proxyInputPass) proxyInputPass.value = parsed.pass;
        if (proxySelectScheme) proxySelectScheme.value = parsed.scheme;
        if (proxyInputRaw) proxyInputRaw.value = val;
      }
    });
  }

  if (proxyInputRaw) {
    proxyInputRaw.addEventListener('input', () => {
      const parsed = parseProxyString(proxyInputRaw.value);
      if (parsed) {
        if (proxyInputHost) proxyInputHost.value = parsed.host;
        if (proxyInputPort) proxyInputPort.value = parsed.port;
        if (proxyInputUser) proxyInputUser.value = parsed.user;
        if (proxyInputPass) proxyInputPass.value = parsed.pass;
        if (proxySelectScheme) proxySelectScheme.value = parsed.scheme;
      }
    });
  }

  if (proxyBtnApply) {
    proxyBtnApply.addEventListener('click', () => {
      let host = '127.0.0.1';
      let port = 10000;
      let user = '';
      let pass = '';
      let scheme = 'http';

      if (activeProxySource === 'vpn_tool' && proxySelectVpnPort) {
        const parsed = parseProxyString(proxySelectVpnPort.value);
        if (!parsed) {
          if (proxyApplyStatusText) proxyApplyStatusText.textContent = 'Chưa có proxy thật. Bấm Quét Cổng Tool hoặc Đồng Bộ Từ Tool 8899.';
          return;
        }
        if (parsed) {
          host = parsed.host;
          port = parsed.port;
          user = parsed.user;
          pass = parsed.pass;
          scheme = parsed.scheme;
        }
      } else {
        host = proxyInputHost ? proxyInputHost.value.trim() : '127.0.0.1';
        port = proxyInputPort ? parseInt(proxyInputPort.value.trim(), 10) : 10000;
        user = proxyInputUser ? proxyInputUser.value.trim() : '';
        pass = proxyInputPass ? proxyInputPass.value.trim() : '';
        scheme = proxySelectScheme ? proxySelectScheme.value : 'http';
      }

      const accName = proxyInputAccName ? proxyInputAccName.value.trim() : '';
      const isEnabled = proxyToggleEnabled ? proxyToggleEnabled.checked : true;

      const config = {
        enabled: isEnabled,
        host,
        port,
        username: user,
        password: pass,
        scheme,
        account_name: accName,
        source: activeProxySource,
        raw_proxy: user && pass ? `${host}:${port}:${user}:${pass}` : `${host}:${port}`
      };

      if (proxyApplyStatusText) proxyApplyStatusText.innerHTML = '⏳ Đang áp dụng proxy cho trình duyệt...';

      chrome.runtime.sendMessage({ action: 'SET_EXTENSION_PROXY', config }, (res) => {
        if (res && res.ok) {
          updateProxyModeUI(true);
          const srcLabel = activeProxySource === 'vpn_tool' ? 'Tool VPN2proxy' : 'Proxy Ngoài';
          if (proxyApplyStatusText) {
            proxyApplyStatusText.innerHTML = `✅ <b>Thành công!</b> Đã áp dụng [${scheme.toUpperCase()}://${host}:${port}] (${srcLabel})!`;
            proxyApplyStatusText.style.color = '#34d399';
          }
          addLog('PROXY', `Đã áp dụng proxy ${host}:${port} (${srcLabel})`, 'success');
          setTimeout(checkCurrentPublicIp, 1000);
        } else {
          if (proxyApplyStatusText) {
            proxyApplyStatusText.innerHTML = `❌ Lỗi áp dụng: ${res?.error || 'Không xác định'}`;
            proxyApplyStatusText.style.color = '#f87171';
          }
          addLog('PROXY', `Lỗi áp dụng proxy: ${res?.error}`, 'error');
        }
      });
    });
  }

  if (proxyBtnDisable) {
    proxyBtnDisable.addEventListener('click', () => {
      updateProxyModeUI(false);
      chrome.runtime.sendMessage({ action: 'CLEAR_EXTENSION_PROXY' }, (res) => {
        if (proxyApplyStatusText) {
          proxyApplyStatusText.innerHTML = '⚪ Đã tắt proxy. Trình duyệt đang chạy MẠNG TRỰC TIẾP (Direct).';
          proxyApplyStatusText.style.color = '#94a3b8';
        }
        addLog('PROXY', 'Đã tắt proxy, quay về mạng trực tiếp', 'info');
        setTimeout(checkCurrentPublicIp, 800);
      });
    });
  }

  if (proxyToggleEnabled) {
    proxyToggleEnabled.addEventListener('change', () => {
      if (proxyToggleEnabled.checked) {
        if (proxyBtnApply) proxyBtnApply.click();
      } else {
        if (proxyBtnDisable) proxyBtnDisable.click();
      }
    });
  }

  if (proxyBtnTestLive) {
    proxyBtnTestLive.addEventListener('click', () => {
      checkCurrentPublicIp();
    });
  }

  if (proxyBtnSyncTool) {
    proxyBtnSyncTool.addEventListener('click', async () => {
      if (proxyApplyStatusText) proxyApplyStatusText.innerHTML = '🔄 Đang đồng bộ cấu hình Proxy từ Tool Studio (Port 8899)...';
      try {
        const resp = await fetch('http://127.0.0.1:8899/api/proxy-pool');
        const poolInfo = await resp.json();

        if (poolInfo) {
          const isEnabled = typeof poolInfo.enabled === 'boolean' ? poolInfo.enabled : true;
          const source = poolInfo.source || 'vpn_tool';
          if (rotate5m) rotate5m.checked = poolInfo.vpn_auto_rotate !== false;
          chrome.storage.local.set({ dola_vpn_auto_rotate: poolInfo.vpn_auto_rotate !== false });
          if (source === 'vpn_tool' && isEnabled && !poolInfo.proxies?.length) {
            throw new Error('Tool chưa có cổng proxy đang chạy; không dùng cổng mặc định giả.');
          }
          updateProxyModeUI(isEnabled);
          switchProxySourceUI(source);

          if (source === 'custom' && Array.isArray(poolInfo.custom_proxies) && poolInfo.custom_proxies.length > 0) {
            const firstCustom = poolInfo.custom_proxies[0];
            const parsed = parseProxyString(firstCustom);
            if (parsed) {
              if (proxyInputHost) proxyInputHost.value = parsed.host;
              if (proxyInputPort) proxyInputPort.value = parsed.port;
              if (proxyInputUser) proxyInputUser.value = parsed.user;
              if (proxyInputPass) proxyInputPass.value = parsed.pass;
              if (proxySelectScheme) proxySelectScheme.value = parsed.scheme;
              if (proxyInputRaw) proxyInputRaw.value = firstCustom;
            }
          }

          // Cập nhật danh sách cổng VPN
          if (Array.isArray(poolInfo.proxies) && poolInfo.proxies.length > 0 && proxySelectVpnPort) {
            proxySelectVpnPort.innerHTML = '';
            poolInfo.proxies.forEach((rawProxy, idx) => {
              const opt = document.createElement('option');
              opt.value = rawProxy;
              const portMatch = rawProxy.match(/:(\d+)/);
              const portNum = portMatch ? portMatch[1] : (10000 + idx);
              opt.textContent = `🌐 Cổng ${portNum} - VPN từ Studio`;
              if (idx === 0) opt.selected = true;
              proxySelectVpnPort.appendChild(opt);
            });
            proxySelectVpnPort.dispatchEvent(new Event('change'));
          }

          if (isEnabled) {
            if (proxyBtnApply) proxyBtnApply.click();
          } else {
            if (proxyBtnDisable) proxyBtnDisable.click();
          }

          const statusStr = isEnabled ? 'BẬT' : 'TẮT';
          const srcStr = source === 'vpn_tool' ? 'Tool VPN2proxy' : 'Proxy Ngoài Riêng';
          if (proxyApplyStatusText) {
            proxyApplyStatusText.innerHTML = `✅ Đã đồng bộ từ Tool Studio! Trạng thái: <b>${statusStr}</b> | Nguồn: <b>${srcStr}</b>`;
            proxyApplyStatusText.style.color = '#34d399';
          }
          addLog('PROXY', `Đã đồng bộ từ Studio 8899: Proxy ${statusStr} (Nguồn: ${srcStr})`, 'success');
        }
      } catch (err) {
        if (proxyApplyStatusText) {
          proxyApplyStatusText.innerHTML = `⚠️ Không kết nối được Tool 8899 (${err.message}). Đang dùng cấu hình Extension.`;
          proxyApplyStatusText.style.color = '#fbbf24';
        }
        addLog('PROXY', `Lưu ý kết nối Tool 8899: ${err.message}`, 'info');
      }
    });
  }

  if (proxyBtnRefreshVpnList) {
    proxyBtnRefreshVpnList.addEventListener('click', async () => {
      try {
        const resp = await fetch('http://127.0.0.1:8899/api/proxy/active-vpn-list');
        const data = await resp.json();
        if (data && Array.isArray(data.proxies) && proxySelectVpnPort) {
          proxySelectVpnPort.innerHTML = '';
          data.proxies.forEach((p) => {
            const opt = document.createElement('option');
            opt.value = p.raw;
            opt.textContent = p.label;
            proxySelectVpnPort.appendChild(opt);
          });
          if (!data.proxies.length) {
            const empty = document.createElement('option');
            empty.value = ''; empty.textContent = 'Không có cổng proxy đang chạy';
            proxySelectVpnPort.appendChild(empty);
          }
          addLog('PROXY', `Đã làm mới ${data.proxies.length} cổng proxy VPN`, 'info');
        }
      } catch (e) {
        addLog('PROXY', `Không làm mới được từ port 8899: ${e.message}`, 'info');
      }
    });
  }

  // Load saved proxy on start
  loadSavedProxySettings();

});
