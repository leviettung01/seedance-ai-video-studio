/**
 * Seedance AI Video Studio — App JavaScript
 * SPA logic, API client, real-time polling, drag & drop.
 */

const API_BASE = '';

// ─── State ───────────────────────────────────────────────────
let currentSection = 'dashboard';
let currentJobId = null;
let jobPollTimer = null;
let uploadedFilePath = '';

// ─── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initToggleGroups();
    initUploadArea();
    initButtons();
    loadDashboardStats();
    loadAccounts();
    loadProxyPool();
    loadLicense();
});

// ─── Navigation ──────────────────────────────────────────────
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const section = btn.dataset.section;
            switchSection(section);
        });
    });

    // Hash routing
    if (window.location.hash) {
        const hash = window.location.hash.replace('#', '');
        switchSection(hash);
    }
}

function switchSection(section) {
    currentSection = section;
    window.location.hash = section;

    // Update nav
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.section === section);
    });

    // Show/hide sections
    document.querySelectorAll('.section').forEach(sec => {
        sec.classList.toggle('active', sec.id === `section-${section}`);
    });

    // Refresh data
    if (section === 'accounts') loadAccounts();
    if (section === 'gallery') loadGallery();
    if (section === 'jobs') loadJobs();
    if (section === 'proxy') loadProxyPool();
}

// ─── Toggle Groups ───────────────────────────────────────────
function initToggleGroups() {
    document.querySelectorAll('.toggle-group').forEach(group => {
        group.querySelectorAll('.toggle-option').forEach(option => {
            option.addEventListener('click', () => {
                group.querySelectorAll('.toggle-option').forEach(o => o.classList.remove('active'));
                option.classList.add('active');
            });
        });
    });
}

function getToggleValue(groupId) {
    const group = document.getElementById(groupId);
    const active = group.querySelector('.toggle-option.active');
    return active ? active.dataset.value : '';
}

// ─── Upload Area ─────────────────────────────────────────────
function initUploadArea() {
    const area = document.getElementById('upload-area');
    const input = document.getElementById('file-input');
    const preview = document.getElementById('upload-preview');

    area.addEventListener('click', () => input.click());

    area.addEventListener('dragover', (e) => {
        e.preventDefault();
        area.classList.add('dragover');
    });

    area.addEventListener('dragleave', () => area.classList.remove('dragover'));

    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleFileUpload(file);
    });

    input.addEventListener('change', () => {
        if (input.files[0]) handleFileUpload(input.files[0]);
    });
}

async function handleFileUpload(file) {
    const preview = document.getElementById('upload-preview');
    const area = document.getElementById('upload-area');

    // Preview
    const reader = new FileReader();
    reader.onload = (e) => {
        preview.src = e.target.result;
        preview.style.display = 'block';
    };
    reader.readAsDataURL(file);

    // Upload to server
    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch(`${API_BASE}/api/upload-file`, {
            method: 'POST',
            body: formData,
        });
        const data = await resp.json();
        if (data.success) {
            uploadedFilePath = data.path;
            area.innerHTML = `<div class="upload-icon">✅</div><div class="upload-text">${file.name}</div>`;
            showToast('Đã tải ảnh thành công', 'success');
        }
    } catch (e) {
        showToast('Lỗi tải ảnh: ' + e.message, 'error');
    }
}

// ─── Buttons ─────────────────────────────────────────────────
function initButtons() {
    // Create Video
    document.getElementById('btn-create-video').addEventListener('click', createVideo);

    // Cancel Job
    document.getElementById('btn-cancel-job').addEventListener('click', cancelJob);

    // Open output folder
    document.getElementById('btn-open-output').addEventListener('click', openOutputFolder);

    // New job
    document.getElementById('btn-new-job').addEventListener('click', resetJobUI);

    // Add Account
    document.getElementById('btn-add-account').addEventListener('click', () => openModal('modal-add-account'));
    document.getElementById('btn-confirm-add-account').addEventListener('click', addAccount);

    // Cookie Modal Actions
    document.getElementById('btn-inject-and-open-fb')?.addEventListener('click', injectAndOpenFB);
    document.getElementById('btn-save-cookie-only')?.addEventListener('click', saveCookieOnly);

    // Proxy
    document.getElementById('btn-save-proxy').addEventListener('click', saveProxy);
    document.getElementById('btn-test-proxy').addEventListener('click', testProxy);

    // Gallery
    document.getElementById('btn-refresh-gallery')?.addEventListener('click', loadGallery);
    document.getElementById('btn-open-gallery-folder')?.addEventListener('click', openOutputFolder);

    // License
    document.getElementById('btn-activate-license').addEventListener('click', activateLicense);
}

// ─── Create Video ────────────────────────────────────────────
async function createVideo() {
    const prompt = document.getElementById('input-prompt').value.trim();
    if (!prompt) {
        showToast('Vui lòng nhập prompt', 'error');
        return;
    }

    const mode = getToggleValue('toggle-mode');
    const ratio = getToggleValue('toggle-ratio');
    const model = getToggleValue('toggle-model');
    const upscale = getToggleValue('toggle-upscale');

    const body = {
        prompt,
        aspect_ratio: ratio,
        mode,
        duration_target: mode === 'standard' ? 31 : 15,
        model_version: model,
        enable_upscale: upscale !== 'off',
        upscale_target: upscale === 'off' ? '2K' : upscale,
        image_path: uploadedFilePath,
    };

    try {
        const btn = document.getElementById('btn-create-video');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Đang tạo...';

        const resp = await fetch(`${API_BASE}/api/${uploadedFilePath ? 'image-to-video' : 'text-to-video'}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        const data = await resp.json();
        if (data.success) {
            currentJobId = data.job_id;
            showJobProgress(data.job);
            startJobPolling(data.job_id);
            showToast(`Job ${data.job_id} đã được tạo!`, 'success');
        } else {
            showToast('Lỗi tạo video: ' + (data.detail || 'Unknown'), 'error');
        }
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    } finally {
        const btn = document.getElementById('btn-create-video');
        btn.disabled = false;
        btn.innerHTML = '🎬 Tạo Video';
    }
}

// ─── Job Polling ─────────────────────────────────────────────
function showJobProgress(job) {
    document.getElementById('job-progress-area').style.display = 'none';
    document.getElementById('job-active-area').style.display = 'block';
    document.getElementById('job-result-area').style.display = 'none';

    updateJobStatus(job);
}

function startJobPolling(jobId) {
    if (jobPollTimer) clearInterval(jobPollTimer);

    const startTime = Date.now();

    jobPollTimer = setInterval(async () => {
        try {
            const resp = await fetch(`${API_BASE}/api/jobs/${jobId}`);
            const job = await resp.json();

            // Update elapsed time
            const elapsed = Math.round((Date.now() - startTime) / 1000);
            document.getElementById('job-elapsed').textContent = formatElapsed(elapsed);

            updateJobStatus(job);

            if (['completed', 'failed', 'cancelled'].includes(job.status)) {
                clearInterval(jobPollTimer);
                jobPollTimer = null;
                showJobResult(job);
                loadDashboardStats();
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    }, 3000);
}

function updateJobStatus(job) {
    // Status badge
    const badge = document.getElementById('job-status-badge');
    const statusMap = {
        'queued': ['Đang chờ', 'badge-muted'],
        'running': ['Đang chạy', 'badge-info'],
        'completed': ['Hoàn thành', 'badge-success'],
        'failed': ['Thất bại', 'badge-danger'],
        'cancelled': ['Đã hủy', 'badge-warning'],
    };
    const [text, cls] = statusMap[job.status] || ['Unknown', 'badge-muted'];
    badge.textContent = text;
    badge.className = `badge ${cls}`;

    // Progress text
    document.getElementById('job-progress-text').textContent = job.progress || 'Đang xử lý...';

    // Progress bar (estimate)
    let pct = 5;
    if (job.progress?.includes('proxy')) pct = 10;
    if (job.progress?.includes('Chrome')) pct = 20;
    if (job.progress?.includes('Extension')) pct = 30;
    if (job.progress?.includes('Dola')) pct = 40;
    if (job.progress?.includes('prompt')) pct = 50;
    if (job.progress?.includes('chờ')) pct = 60;
    if (job.progress?.includes('tải')) pct = 80;
    if (job.progress?.includes('nâng cấp')) pct = 90;
    if (job.status === 'completed') pct = 100;
    document.getElementById('job-progress-bar').style.width = pct + '%';

    // Log
    if (job.progress) {
        addLogLine(job.progress);
    }
}

function showJobResult(job) {
    document.getElementById('job-active-area').style.display = 'none';
    document.getElementById('job-result-area').style.display = 'block';

    if (job.status === 'completed') {
        document.getElementById('result-icon').textContent = '✅';
        document.getElementById('result-title').textContent = 'Video đã tạo thành công!';
        document.getElementById('result-detail').textContent = job.output_path || '';
    } else if (job.status === 'failed') {
        document.getElementById('result-icon').textContent = '❌';
        document.getElementById('result-title').textContent = 'Tạo video thất bại';
        document.getElementById('result-detail').textContent = job.error || '';
    } else {
        document.getElementById('result-icon').textContent = '🚫';
        document.getElementById('result-title').textContent = 'Job đã bị hủy';
        document.getElementById('result-detail').textContent = '';
    }
}

function resetJobUI() {
    currentJobId = null;
    document.getElementById('job-progress-area').style.display = 'block';
    document.getElementById('job-active-area').style.display = 'none';
    document.getElementById('job-result-area').style.display = 'none';
    document.getElementById('job-log').innerHTML = '';
    document.getElementById('job-status-badge').textContent = 'Chờ';
    document.getElementById('job-status-badge').className = 'badge badge-muted';
}

const logLines = new Set();
function addLogLine(text) {
    if (logLines.has(text)) return;
    logLines.add(text);

    const log = document.getElementById('job-log');
    const line = document.createElement('div');
    line.className = 'log-line';
    if (text.includes('✅') || text.includes('thành công')) line.className += ' success';
    if (text.includes('❌') || text.includes('Lỗi')) line.className += ' error';
    if (text.includes('⚠️') || text.includes('chờ')) line.className += ' warning';
    line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
}

async function cancelJob() {
    if (!currentJobId) return;
    try {
        await fetch(`${API_BASE}/api/jobs/${currentJobId}/cancel`, { method: 'POST' });
        showToast('Đã hủy job', 'info');
    } catch (e) {
        showToast('Lỗi hủy job', 'error');
    }
}

// ─── Dashboard Stats ─────────────────────────────────────────
async function loadDashboardStats() {
    try {
        const [acResp, vidResp] = await Promise.all([
            fetch(`${API_BASE}/api/accounts`),
            fetch(`${API_BASE}/api/list-videos`),
        ]);
        const acData = await acResp.json();
        const vidData = await vidResp.json();

        const accounts = acData.accounts || [];
        const videos = vidData.videos || [];

        document.getElementById('stat-accounts').textContent = accounts.length;
        document.getElementById('stat-active').textContent = accounts.filter(a => a.status === 'active' && (a.quota_max - a.quota_used - a.quota_reserved) > 0).length;
        document.getElementById('stat-videos').textContent = videos.length;

        // Jobs count today
        try {
            const jobsResp = await fetch(`${API_BASE}/api/jobs`);
            const jobsData = await jobsResp.json();
            const today = new Date().toDateString();
            const todayJobs = (jobsData.jobs || []).filter(j => new Date(j.created_at * 1000).toDateString() === today);
            document.getElementById('stat-jobs').textContent = todayJobs.length;
        } catch(e) {
            document.getElementById('stat-jobs').textContent = '0';
        }
    } catch (e) {
        console.error('Stats error:', e);
    }
}

// ─── Accounts ────────────────────────────────────────────────
async function loadAccounts() {
    try {
        const resp = await fetch(`${API_BASE}/api/accounts`);
        const data = await resp.json();
        renderAccounts(data.accounts || []);
    } catch (e) {
        console.error('Load accounts error:', e);
    }
}

function renderAccounts(accounts) {
    const tbody = document.getElementById('accounts-tbody');
    if (!accounts.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:32px">Chưa có tài khoản nào. Click "+ Thêm Account"</td></tr>';
        return;
    }

    tbody.innerHTML = accounts.map(acc => {
        const statusBadge = {
            'active': '<span class="badge badge-success">✅ Active</span>',
            'cooldown': '<span class="badge badge-warning">⏳ Cooldown</span>',
            'error': '<span class="badge badge-danger">❌ Error</span>',
        }[acc.status] || '<span class="badge badge-muted">Unknown</span>';

        const loginBadge = {
            'logged_in': '<span class="badge badge-success">✅ Đã Login</span>',
            'failed': '<span class="badge badge-danger">❌ Chưa Login</span>',
        }[acc.login_status] || '<span class="badge badge-muted">❓ Chưa rõ</span>';

        const hasCookie = acc.fb_cookies && acc.fb_cookies.trim().length > 0;
        const cookieBadge = hasCookie ? '<span style="font-size:11px;color:#4ade80" title="Đã có Cookie VIA">🍪 Có Cookie</span>' : '<span style="font-size:11px;color:var(--text-muted)">Chưa nạp</span>';

        const remaining = acc.quota_max - acc.quota_used - (acc.quota_reserved || 0);
        let quotaHTML = '<div class="quota-bar">';
        for (let i = 0; i < acc.quota_max; i++) {
            if (i < acc.quota_used) quotaHTML += '<div class="quota-block used"></div>';
            else if (i < acc.quota_used + (acc.quota_reserved || 0)) quotaHTML += '<div class="quota-block reserved"></div>';
            else quotaHTML += '<div class="quota-block"></div>';
        }
        quotaHTML += ` <span style="font-size:11px;color:var(--text-muted);margin-left:4px">${remaining}/${acc.quota_max}</span></div>`;

        const proxyText = acc.proxy ? acc.proxy.substring(0, 20) + '...' : '<span style="color:var(--text-muted)">Pool</span>';

        return `<tr>
            <td>
                <strong>${acc.name}</strong>
                <div style="font-size:11px">${cookieBadge}</div>
            </td>
            <td><span class="badge badge-info">${acc.login_type === 'facebook' ? '📘 Facebook' : '🔴 Google'}</span></td>
            <td>${statusBadge}</td>
            <td>${loginBadge}</td>
            <td>${quotaHTML}</td>
            <td style="font-size:11px">${proxyText}</td>
            <td>
                <div style="display:flex;gap:4px">
                    <button class="btn btn-secondary btn-sm" onclick="openProfile('${acc.name}')" title="Mở Chrome Profile sạch có Extension để login">🌐 Mở</button>
                    <button class="btn btn-primary btn-sm" onclick="openCookieModal('${acc.name}')" title="Nạp Cookie VIA Facebook">🍪 Cookie</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteAccount('${acc.name}')" title="Xóa tài khoản">🗑️</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

async function addAccount() {
    const name = document.getElementById('new-account-name').value.trim();
    if (!name) { showToast('Nhập tên account', 'error'); return; }

    const cookies = document.getElementById('new-account-cookies')?.value.trim() || '';

    try {
        const resp = await fetch(`${API_BASE}/api/accounts/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                login_type: document.getElementById('new-account-type').value,
                fb_cookies: cookies,
                proxy: document.getElementById('new-account-proxy').value.trim(),
                quota_max: parseInt(document.getElementById('new-account-quota').value) || 4,
            }),
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`Đã tạo Profile sạch cho account: ${name}`, 'success');
            closeModal('modal-add-account');
            loadAccounts();
            loadDashboardStats();
            // Tự động mở modal cookie nếu chưa nhập hoặc mở profile
            if (cookies) {
                showToast(`Cookie Facebook đã được lưu cho ${name}! Bấm "🌐 Mở" để kiểm tra.`, 'info');
            }
        } else {
            showToast(data.detail || 'Lỗi thêm account', 'error');
        }
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    }
}

let activeCookieAccount = '';

async function openCookieModal(name) {
    activeCookieAccount = name;
    document.getElementById('cookie-account-name').value = name;
    document.getElementById('cookie-account-display').textContent = name;
    document.getElementById('cookie-inject-status').textContent = '';

    // Tìm cookie hiện tại nếu có
    try {
        const resp = await fetch(`${API_BASE}/api/accounts`);
        const data = await resp.json();
        const acc = (data.accounts || []).find(a => a.name === name);
        if (acc && acc.fb_cookies) {
            document.getElementById('cookie-account-input').value = acc.fb_cookies;
        } else {
            document.getElementById('cookie-account-input').value = '';
        }
    } catch (e) {}

    openModal('modal-cookie-account');
}

async function injectAndOpenFB() {
    const name = document.getElementById('cookie-account-name').value || activeCookieAccount;
    const rawCookies = document.getElementById('cookie-account-input').value.trim();
    const statusEl = document.getElementById('cookie-inject-status');

    if (!rawCookies) {
        statusEl.style.color = '#f87171';
        statusEl.textContent = '⚠️ Vui lòng dán Cookie hoặc dòng VIA!';
        return;
    }

    statusEl.style.color = '#60a5fa';
    statusEl.textContent = '⏳ Đang nạp Cookie và mở Chrome Profile...';

    try {
        const resp = await fetch(`${API_BASE}/api/inject-facebook-cookie`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_name: name, cookies: rawCookies })
        });
        const data = await resp.json();
        
        statusEl.style.color = '#4ade80';
        statusEl.textContent = `✅ Đã lưu ${data.count || ''} Cookie! Đang mở Chrome Profile...`;
        showToast(`Đã nạp Cookie Facebook cho ${name}!`, 'success');
        
        // Mở Chrome profile cho account này
        await openProfile(name);
        loadAccounts();
        setTimeout(() => closeModal('modal-cookie-account'), 1500);
    } catch (e) {
        statusEl.style.color = '#f87171';
        statusEl.textContent = `❌ Lỗi: ${e.message}`;
    }
}

async function saveCookieOnly() {
    const name = document.getElementById('cookie-account-name').value || activeCookieAccount;
    const rawCookies = document.getElementById('cookie-account-input').value.trim();
    const statusEl = document.getElementById('cookie-inject-status');

    statusEl.style.color = '#60a5fa';
    statusEl.textContent = '⏳ Đang lưu Cookie...';

    try {
        const resp = await fetch(`${API_BASE}/api/inject-facebook-cookie`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_name: name, cookies: rawCookies })
        });
        const data = await resp.json();
        statusEl.style.color = '#4ade80';
        statusEl.textContent = `✅ Đã lưu Cookie thành công!`;
        showToast(`Đã lưu Cookie cho ${name}!`, 'success');
        loadAccounts();
        setTimeout(() => closeModal('modal-cookie-account'), 1000);
    } catch (e) {
        statusEl.style.color = '#f87171';
        statusEl.textContent = `❌ Lỗi: ${e.message}`;
    }
}

async function deleteAccount(name) {
    if (!confirm(`Xóa account "${name}"? Thư mục Profile của tài khoản này sẽ được giữ lại an toàn.`)) return;
    try {
        await fetch(`${API_BASE}/api/accounts/${name}`, { method: 'DELETE' });
        showToast(`Đã xóa: ${name}`, 'success');
        loadAccounts();
        loadDashboardStats();
    } catch (e) {
        showToast('Lỗi xóa account', 'error');
    }
}

async function openProfile(name) {
    try {
        showToast(`Đang mở Chrome profile sạch có Extension: ${name}...`, 'info');
        const resp = await fetch(`${API_BASE}/api/profiles/open`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_name: name }),
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`Chrome Profile ${name} đã mở sẵn sàng!`, 'success');
        } else {
            showToast(data.detail || 'Lỗi mở profile', 'error');
        }
    } catch (e) {
        showToast('Lỗi: ' + e.message, 'error');
    }
}

// ─── Proxy ───────────────────────────────────────────────────
let loadedProxyPool = {};
async function loadProxyPool() {
    try {
        const resp = await fetch(`${API_BASE}/api/proxy-pool`);
        const data = await resp.json();
        loadedProxyPool = data;
        document.getElementById('proxy-vpn-auto-rotate').checked = data.vpn_auto_rotate !== false;
        document.getElementById('proxy-keys').value = (data.proxies || []).join('\n');
        document.getElementById('proxy-carrier').value = data['5stars_carrier'] || 'random';
        document.getElementById('proxy-province').value = data['5stars_province'] || '0';
    } catch (e) {
        console.error('Load proxy error:', e);
    }
}

async function saveProxy() {
    const keys = document.getElementById('proxy-keys').value.trim().split('\n').filter(k => k.trim());
    const carrier = document.getElementById('proxy-carrier').value;
    const province = document.getElementById('proxy-province').value;

    try {
        const resp = await fetch(`${API_BASE}/api/proxy-pool`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...loadedProxyPool, proxies: keys, carrier, province,
                vpn_auto_rotate: document.getElementById('proxy-vpn-auto-rotate').checked }),
        });
        const data = await resp.json();
        if (data.success) showToast('Đã lưu Proxy Pool!', 'success');
    } catch (e) {
        showToast('Lỗi lưu proxy', 'error');
    }
}

async function testProxy() {
    const keys = document.getElementById('proxy-keys').value.trim().split('\n').filter(k => k.trim());
    if (!keys.length) { showToast('Chưa có proxy key nào', 'error'); return; }

    const resultEl = document.getElementById('proxy-test-result');
    resultEl.style.display = 'block';
    resultEl.innerHTML = '<span class="spinner"></span> Đang test proxy...';

    try {
        const resp = await fetch(`${API_BASE}/api/accounts/test-proxy`, {
            method: 'POST',
            body: new FormData(Object.assign(document.createElement('form'), {
                innerHTML: `<input name="proxy_url" value="${keys[0]}">`
            })),
        });
        const data = await resp.json();
        if (data.success) {
            resultEl.innerHTML = `<span class="badge badge-success">✅ IP: ${data.ip} | Latency: ${data.latency_ms}ms</span>`;
        } else {
            resultEl.innerHTML = `<span class="badge badge-danger">❌ ${data.error || 'Failed'}</span>`;
        }
    } catch (e) {
        resultEl.innerHTML = `<span class="badge badge-danger">❌ ${e.message}</span>`;
    }
}

// ─── Gallery ─────────────────────────────────────────────────
async function loadGallery() {
    try {
        const resp = await fetch(`${API_BASE}/api/list-videos`);
        const data = await resp.json();
        const videos = data.videos || [];
        const grid = document.getElementById('video-grid');
        const empty = document.getElementById('gallery-empty');

        if (!videos.length) {
            grid.innerHTML = '';
            empty.style.display = 'block';
            return;
        }

        empty.style.display = 'none';
        grid.innerHTML = videos.map(v => {
            const sizeMB = (v.size / 1024 / 1024).toFixed(1);
            const date = new Date(v.created_at * 1000).toLocaleString();
            return `<div class="video-card">
                <video src="/output_videos/${v.filename}" preload="metadata" muted onclick="this.paused?this.play():this.pause()"></video>
                <div class="video-info">
                    <div class="video-name">${v.filename}</div>
                    <div class="video-meta">${sizeMB}MB · ${date}</div>
                </div>
            </div>`;
        }).join('');
    } catch (e) {
        console.error('Load gallery error:', e);
    }
}

// ─── Jobs ────────────────────────────────────────────────────
async function loadJobs() {
    try {
        const resp = await fetch(`${API_BASE}/api/jobs`);
        const data = await resp.json();
        renderJobs(data.jobs || []);
    } catch (e) {
        console.error('Load jobs error:', e);
    }
}

function renderJobs(jobs) {
    const tbody = document.getElementById('jobs-tbody');
    if (!jobs.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:32px">Chưa có job nào</td></tr>';
        return;
    }

    tbody.innerHTML = jobs.map(j => {
        const statusBadge = {
            'queued': '<span class="badge badge-muted">Chờ</span>',
            'running': '<span class="badge badge-info"><span class="spinner" style="width:10px;height:10px"></span> Đang chạy</span>',
            'completed': '<span class="badge badge-success">✅ Xong</span>',
            'failed': '<span class="badge badge-danger">❌ Lỗi</span>',
            'cancelled': '<span class="badge badge-warning">🚫 Hủy</span>',
        }[j.status] || j.status;

        const prompt = j.prompt.length > 50 ? j.prompt.substring(0, 50) + '...' : j.prompt;
        const time = j.created_at ? new Date(j.created_at * 1000).toLocaleString() : '';
        const output = j.output_path ? j.output_path.split(/[\\/]/).pop() : '-';

        return `<tr>
            <td><code style="font-size:11px;color:var(--accent-2)">${j.id}</code></td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${j.prompt}">${prompt}</td>
            <td>${statusBadge}</td>
            <td>${j.account_name || '-'}</td>
            <td style="font-size:11px">${time}</td>
            <td style="font-size:11px">${output}</td>
        </tr>`;
    }).join('');
}

// ─── License ─────────────────────────────────────────────────
async function loadLicense() {
    try {
        const resp = await fetch(`${API_BASE}/api/license`);
        const data = await resp.json();
        document.getElementById('device-id').value = data.device_id || '';
        document.getElementById('license-key').value = data.license_key || '';

        const statusEl = document.getElementById('license-status');
        if (data.activated) {
            statusEl.innerHTML = '<span class="badge badge-success">✅ License đã kích hoạt</span>';
        }
    } catch (e) {}
}

async function activateLicense() {
    const key = document.getElementById('license-key').value.trim();
    if (!key) { showToast('Nhập license key', 'error'); return; }

    try {
        const resp = await fetch(`${API_BASE}/api/license`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ license_key: key }),
        });
        const data = await resp.json();
        if (data.success) {
            showToast('Kích hoạt license thành công!', 'success');
            loadLicense();
        }
    } catch (e) {
        showToast('Lỗi kích hoạt', 'error');
    }
}

// ─── Output Folder ───────────────────────────────────────────
async function openOutputFolder() {
    try {
        const form = new FormData();
        const resp = await fetch(`${API_BASE}/api/open-folder`, { method: 'POST', body: form });
    } catch (e) {}
}

// ─── Modal ───────────────────────────────────────────────────
function openModal(id) {
    document.getElementById(id).classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

// ─── Toast ───────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    toast.innerHTML = `<span>${icons[type] || '•'}</span><span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ─── Helpers ─────────────────────────────────────────────────
function formatElapsed(seconds) {
    if (seconds < 60) return seconds + 's';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
}
