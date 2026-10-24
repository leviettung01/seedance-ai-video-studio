// Dola 30s Bypass Pro - Giao diện điều khiển một màn hình
// Tác giả: LÊ VIỆT TÙNG (Zalo: 0915967790)

document.addEventListener('DOMContentLoaded', () => {
    const promptInput = document.getElementById('prompt-input');
    const charCount = document.getElementById('char-count');
    const btnPaste = document.getElementById('btn-paste');
    const btnClear = document.getElementById('btn-clear');
    const btnSample = document.getElementById('btn-sample');
    const btnGenerate = document.getElementById('btn-generate');
    const generateBtnText = document.getElementById('generate-btn-text');
    const ratioBtns = document.querySelectorAll('.ratio-btn');
    const toggleAutoDownload = document.getElementById('toggle-auto-download');
    const actionAlert = document.getElementById('action-alert');
    const alertMessage = document.getElementById('alert-message');
    const connectionStatus = document.getElementById('connection-status');
    const downloadsList = document.getElementById('downloads-list');
    const downloadCountBadge = document.getElementById('download-count-badge');

    let activeRatio = '9:16';
    let isAutoDownload = true;
    let recentDownloads = [];

    // Load saved settings
    chrome.storage.local.get(['zdola_saved_ratio', 'zdola_auto_download', 'zdola_recent_downloads'], (res) => {
        if (res.zdola_saved_ratio) {
            activeRatio = res.zdola_saved_ratio;
            ratioBtns.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.ratio === activeRatio);
            });
        }
        if (typeof res.zdola_auto_download === 'boolean') {
            isAutoDownload = res.zdola_auto_download;
            if (toggleAutoDownload) toggleAutoDownload.checked = isAutoDownload;
        }
        if (res.zdola_recent_downloads && Array.isArray(res.zdola_recent_downloads)) {
            recentDownloads = res.zdola_recent_downloads;
            renderDownloads();
        }
    });

    checkDolaTab();

    promptInput.addEventListener('input', () => {
        charCount.textContent = `${promptInput.value.length} ký tự`;
    });

    btnPaste.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                promptInput.value = text;
                charCount.textContent = `${promptInput.value.length} ký tự`;
                showAlert('Đã dán prompt từ clipboard!', 'success');
            }
        } catch (e) {
            promptInput.focus();
            document.execCommand('paste');
        }
    });

    btnClear.addEventListener('click', () => {
        promptInput.value = '';
        charCount.textContent = '0 ký tự';
        promptInput.focus();
    });

    const samples = [
        "Cinematic 8k shot of a futuristic sports car racing through neon-lit rainy Tokyo streets, ultra-realistic reflections, 30s dynamic camera movement.",
        "Hyper-realistic cinematic slow motion of a mystical dragon flying over snow-covered crystal mountains at sunrise, dramatic lighting, 8k resolution.",
        "Fashion model in iridescent avant-garde neon dress walking through cybernetic garden with glowing holographic butterflies, cinematic 30s commercial."
    ];

    btnSample.addEventListener('click', () => {
        const rand = samples[Math.floor(Math.random() * samples.length)];
        promptInput.value = rand;
        charCount.textContent = `${rand.length} ký tự`;
        showAlert('Đã nạp prompt mẫu!', 'info');
    });

    ratioBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            ratioBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeRatio = btn.dataset.ratio;
            chrome.storage.local.set({ zdola_saved_ratio: activeRatio });
            
            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                if (tabs && tabs[0]) {
                    chrome.tabs.sendMessage(tabs[0].id, {
                        type: 'SET_ACTIVE_RATIO',
                        ratio: activeRatio
                    }, () => {
                        if (chrome.runtime.lastError) {}
                    });
                }
            });
        });
    });

    if (toggleAutoDownload) {
        toggleAutoDownload.addEventListener('change', () => {
            isAutoDownload = toggleAutoDownload.checked;
            chrome.storage.local.set({ zdola_auto_download: isAutoDownload });
            showAlert(isAutoDownload ? 'Đã bật Tự động tải' : 'Đã tạm dừng Tự động tải', isAutoDownload ? 'success' : 'info');
        });
    }

    btnGenerate.addEventListener('click', async () => {
        const prompt = promptInput.value.trim();
        if (!prompt) {
            showAlert('Vui lòng nhập hoặc dán prompt trước!', 'error');
            promptInput.focus();
            return;
        }

        btnGenerate.disabled = true;
        generateBtnText.textContent = 'Đang khởi chạy 30s...';

        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const currentTab = tabs && tabs[0];
            if (!currentTab || !currentTab.url || (!currentTab.url.includes('dola.com') && !currentTab.url.includes('dola.ai') && !currentTab.url.includes('doubao.com'))) {
                chrome.tabs.query({ url: ['*://*.dola.com/*', '*://*.dola.ai/*', '*://*.doubao.com/*'] }, (dolaTabs) => {
                    if (dolaTabs && dolaTabs.length > 0) {
                        const targetTab = dolaTabs[0];
                        chrome.tabs.update(targetTab.id, { active: true });
                        sendGenerateCommand(targetTab.id, prompt, activeRatio);
                    } else {
                        chrome.tabs.create({ url: 'https://www.dola.com' }, () => {
                            showAlert('Đang mở Dola... Hãy bấm Tạo Video khi trang tải xong!', 'info');
                            btnGenerate.disabled = false;
                            generateBtnText.textContent = '🚀 Tạo Video 30s Không Logo';
                        });
                    }
                });
                return;
            }

            sendGenerateCommand(currentTab.id, prompt, activeRatio);
        });
    });

    function sendGenerateCommand(tabId, prompt, ratio) {
        chrome.tabs.sendMessage(tabId, {
            type: 'INJECT_DOLA_TASK',
            prompt: prompt,
            duration: 30,
            ratio: ratio
        }, (response) => {
            btnGenerate.disabled = false;
            generateBtnText.textContent = '🚀 Tạo Video 30s Không Logo';

            if (chrome.runtime.lastError || !response || !response.success) {
                chrome.scripting.executeScript({
                    target: { tabId: tabId },
                    func: executeDirectPromptInjection,
                    args: [prompt, ratio]
                }).then(() => {
                    showAlert('⚡ Đã gửi prompt! Đang tạo video 30s.', 'success');
                }).catch(() => {
                    showAlert('Vui lòng làm mới tab Dola và thử lại.', 'error');
                });
            } else {
                showAlert('⚡ Đã kích hoạt tạo video 30s! Tự động tải đang bật.', 'success');
            }
        });
    }

    function executeDirectPromptInjection(promptText, targetRatio) {
        const textarea = document.querySelector('textarea.semi-input-textarea, textarea, div[contenteditable="true"]');
        if (textarea) {
            if (textarea.tagName === 'DIV') {
                textarea.innerText = promptText;
            } else {
                textarea.value = promptText;
            }
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.dispatchEvent(new Event('change', { bubbles: true }));

            window.postMessage({ type: 'PURZA_UPDATE_SETTINGS', ratio: targetRatio, duration: 30 }, '*');

            setTimeout(() => {
                const sendBtn = document.querySelector('button[type="submit"], div[role="button"][class*="send"], button[class*="send"], svg[class*="send"]')?.closest('button, div[role="button"]');
                if (sendBtn) {
                    sendBtn.click();
                }
            }, 300);
        }
    }

    function checkDolaTab() {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const currentTab = tabs && tabs[0];
            const isDola = currentTab && currentTab.url && (currentTab.url.includes('dola.com') || currentTab.url.includes('dola.ai') || currentTab.url.includes('doubao.com'));
            if (isDola) {
                connectionStatus.style.background = 'rgba(16, 185, 129, 0.12)';
                connectionStatus.style.borderColor = 'rgba(16, 185, 129, 0.3)';
                connectionStatus.querySelector('.status-text').textContent = 'Dola Đang Mở';
                connectionStatus.querySelector('.status-text').style.color = '#10b981';
                connectionStatus.querySelector('.status-indicator').style.background = '#10b981';
            } else {
                connectionStatus.style.background = 'rgba(234, 179, 8, 0.12)';
                connectionStatus.style.borderColor = 'rgba(234, 179, 8, 0.3)';
                connectionStatus.querySelector('.status-text').textContent = 'Chưa Mở Dola';
                connectionStatus.querySelector('.status-text').style.color = '#eab308';
                connectionStatus.querySelector('.status-indicator').style.background = '#eab308';
            }
        });
    }

    function showAlert(msg, type = 'info') {
        actionAlert.style.display = 'flex';
        actionAlert.className = `action-alert ${type}`;
        alertMessage.textContent = msg;
        setTimeout(() => {
            actionAlert.style.display = 'none';
        }, 3500);
    }

    function renderDownloads() {
        if (!recentDownloads || recentDownloads.length === 0) {
            downloadsList.innerHTML = '<div class="empty-downloads">Chưa có video nào trong phiên này. Hãy nhập prompt để tạo video!</div>';
            downloadCountBadge.textContent = '0 video';
            return;
        }

        downloadCountBadge.textContent = `${recentDownloads.length} video`;
        downloadsList.innerHTML = '';

        recentDownloads.slice(0, 5).forEach(item => {
            const div = document.createElement('div');
            div.className = 'download-item';
            div.innerHTML = `
                <span class="download-item-name" title="${item.filename || 'Video 30s'}">${item.filename || 'Video 30s'}</span>
                <span class="download-item-tag">1080P HD</span>
            `;
            downloadsList.appendChild(div);
        });
    }

    chrome.runtime.onMessage.addListener((message) => {
        if (message.type === 'AUTO_DOWNLOAD_COMPLETED') {
            const newItem = {
                filename: message.filename || `zDola_30s_${Date.now()}.mp4`,
                timestamp: Date.now()
            };
            recentDownloads.unshift(newItem);
            chrome.storage.local.set({ zdola_recent_downloads: recentDownloads });
            renderDownloads();
            showAlert('🎉 Đã tải video 30s không logo!', 'success');
        }
    });
});
