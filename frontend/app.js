// app.js

const token = localStorage.getItem('vc_token');
if (!token) {
    window.location.href = '/login_page';
}

let isEditMode = false;
let currentEditTokenId = null;
let currentTokensData = {};
let tokenIdList = [];
let vcTokenIdList = [];
let vcDraftInputs = {};
let vcPollInterval = null;

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
}

function showSection(sectionId) {
    document.querySelectorAll('.section-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    document.getElementById(`section-${sectionId}`).classList.add('active');
    document.getElementById(`nav-${sectionId}`).classList.add('active');

    if (vcPollInterval) {
        clearInterval(vcPollInterval);
        vcPollInterval = null;
    }

    if (sectionId === 'dashboard') {
        loadTokens();
    }
    if (sectionId === 'vc') {
        loadVC();
        vcPollInterval = setInterval(loadVC, 4000);
    }
}

async function fetchWithAuth(url, options = {}) {
    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };
    const response = await fetch(url, options);
    if (response.status === 401) {
        localStorage.removeItem('vc_token');
        window.location.href = '/login_page';
    }
    return response;
}

function captureVcInputs() {
    const values = {};
    vcTokenIdList.forEach((tokenId, index) => {
        const gEl = document.getElementById(`vc-g-${index}`);
        const cEl = document.getElementById(`vc-c-${index}`);
        if (gEl && cEl) {
            values[tokenId] = { guild: gEl.value, channel: cEl.value };
        }
    });
    return values;
}

async function loadTokens() {
    try {
        const res = await fetchWithAuth('/api/tokens');
        if (!res.ok) return;
        currentTokensData = await res.json();
        tokenIdList = Object.keys(currentTokensData);

        let total = 0, online = 0, rpc = 0, vc = 0;
        for (const [, config] of Object.entries(currentTokensData)) {
            total++;
            if (config.status && config.status !== 'offline') online++;
            if (config.rpc?.name) rpc++;
            if (config.voice?.channel_id) vc++;
        }
        document.getElementById('stat-total').innerText = total;
        document.getElementById('stat-online').innerText = online;
        document.getElementById('stat-rpc').innerText = rpc;
        document.getElementById('stat-vc').innerText = vc;

        const grid = document.getElementById('token-grid');
        grid.innerHTML = '';

        if (tokenIdList.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1/-1;">
                    <div class="icon">🎙️</div>
                    <h3>No tokens yet</h3>
                    <p>Add your first Discord token to get started.</p>
                    <button class="btn" onclick="openAddModal()">+ Add Token</button>
                </div>`;
            return;
        }

        tokenIdList.forEach((tokenId, index) => {
            const config = currentTokensData[tokenId];
            const profile = config.profile;
            let displayName = tokenId.substring(0, 15) + '...';
            let avatarHtml = `<div class="token-avatar-placeholder">${displayName.charAt(0).toUpperCase()}</div>`;

            if (profile && profile.username) {
                displayName = profile.global_name || profile.username;
                if (profile.avatar) {
                    const avatarUrl = `https://cdn.discordapp.com/avatars/${profile.id}/${profile.avatar}.png`;
                    avatarHtml = `<img src="${avatarUrl}" class="token-avatar" alt="${escapeHtml(displayName)}">`;
                }
            }

            const status = config.status || 'offline';
            const statusText = config.status_text || 'No custom status';
            const platformBadge = config.platform === 'mobile'
                ? '<span class="badge mobile">📱 Mobile</span>'
                : '<span class="badge">💻 PC</span>';

            const card = document.createElement('div');
            card.className = `token-card ${status}`;
            card.innerHTML = `
                <div class="token-card-accent"></div>
                <div class="token-card-body">
                    <div class="token-card-header">
                        ${avatarHtml}
                        <div class="token-card-name">
                            <div class="name">${escapeHtml(displayName)}</div>
                            <div class="sub">${platformBadge}</div>
                        </div>
                        <span class="badge ${status}"><span class="status-dot ${status}"></span>${escapeHtml(status)}</span>
                    </div>
                    <div class="token-card-meta">
                        <div class="row"><span>Status:</span><span class="val">${escapeHtml(statusText)}</span></div>
                        <div class="row"><span>Activity:</span><span class="val">${escapeHtml(config.rpc?.name || 'None')}</span></div>
                        <div class="row"><span>Voice:</span><span class="val">${config.voice?.channel_id ? 'Auto-join enabled' : 'Disabled'}</span></div>
                    </div>
                    <div class="token-card-actions">
                        <button class="btn btn-sm" onclick="openEditModal(${index})">Edit</button>
                        <button class="btn btn-warning btn-sm" onclick="restartToken(${index})">Restart</button>
                        <button class="btn btn-danger btn-sm" onclick="deleteToken(${index})">Delete</button>
                    </div>
                </div>`;
            grid.appendChild(card);
        });
    } catch (err) {
        console.error(err);
    }
}

async function loadVC() {
    try {
        const savedInputs = captureVcInputs();
        Object.assign(vcDraftInputs, savedInputs);

        const res = await fetchWithAuth('/api/vc-states');
        if (!res.ok) return;
        const vcStates = await res.json();
        vcTokenIdList = Object.keys(vcStates);

        const list = document.getElementById('vc-list');
        list.innerHTML = '';

        if (vcTokenIdList.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="icon">🔊</div>
                    <h3>No tokens configured</h3>
                    <p>Add a token from the dashboard first.</p>
                </div>`;
            return;
        }

        vcTokenIdList.forEach((tokenId, index) => {
            const data = vcStates[tokenId];
            const profile = data.profile;
            const vcState = data.vc_state || {};
            const isConnected = !!vcState.connected;
            const draft = vcDraftInputs[tokenId];

            const guildValue = draft?.guild ?? vcState.guild_id ?? '';
            const channelValue = draft?.channel ?? vcState.channel_id ?? '';

            let displayName = profile?.username ? (profile.global_name || profile.username) : (tokenId.substring(0, 15) + '...');
            let avatarHtml = `<div class="vc-card-avatar-ph">${displayName.charAt(0).toUpperCase()}</div>`;
            if (profile?.avatar) {
                const avatarUrl = `https://cdn.discordapp.com/avatars/${profile.id}/${profile.avatar}.png`;
                avatarHtml = `<img src="${avatarUrl}" class="vc-card-avatar-ph" alt="${escapeHtml(displayName)}">`;
            }

            let serverDetailsHtml = `
                <div class="vc-card-status">
                    <span class="badge disconnected">Disconnected</span>
                    <span style="font-size:0.8rem;color:var(--text-muted);">Not in any voice channel</span>
                </div>`;

            if (isConnected) {
                const guildName = vcState.guild_name || vcState.guild_id || 'Unknown Server';
                const channelName = vcState.channel_name || vcState.channel_id || 'Unknown Channel';
                const guildIcon = vcState.guild_icon;
                let guildIconHtml = `<div style="width:32px;height:32px;border-radius:8px;background:var(--blurple);display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:0.8rem;">${escapeHtml(guildName.substring(0, 2).toUpperCase())}</div>`;
                if (guildIcon) {
                    guildIconHtml = `<img src="${guildIcon}" style="width:32px;height:32px;border-radius:8px;" alt="${escapeHtml(guildName)}">`;
                }

                serverDetailsHtml = `
                    <div class="vc-card-status">
                        <div style="display:flex;align-items:center;gap:6px;">
                            <span class="badge connected">Connected</span>
                            <span style="font-size:0.8rem;font-weight:600;color:var(--green);">${escapeHtml(channelName)}</span>
                        </div>
                        <div class="vc-state-info" style="margin-top:6px;">
                            ${guildIconHtml}
                            <div style="display:flex;flex-direction:column;line-height:1.2;">
                                <span class="val" style="font-size:0.85rem;font-weight:600;">${escapeHtml(guildName)}</span>
                                <span style="font-size:0.75rem;color:var(--text-muted);">ID: ${escapeHtml(vcState.guild_id || '')}</span>
                            </div>
                        </div>
                    </div>`;
            }

            const item = document.createElement('div');
            item.className = 'vc-card';
            item.innerHTML = `
                <div class="vc-card-user">
                    ${avatarHtml}
                    <div class="vc-name">${escapeHtml(displayName)}</div>
                </div>
                ${serverDetailsHtml}
                <div class="vc-card-controls">
                    <div class="vc-input-row">
                        <input type="text" id="vc-g-${index}" placeholder="Server ID" value="${escapeHtml(guildValue)}" oninput="saveVcDraft(${index})">
                        <input type="text" id="vc-c-${index}" placeholder="Channel ID" value="${escapeHtml(channelValue)}" oninput="saveVcDraft(${index})">
                    </div>
                    <div class="vc-btn-row">
                        <button class="btn btn-success btn-sm" style="flex:1;" onclick="joinVC(${index})">Join</button>
                        <button class="btn btn-danger btn-sm" style="flex:1;" onclick="disconnectVC(${index})">Disconnect</button>
                    </div>
                </div>`;
            list.appendChild(item);
        });
    } catch (err) {
        console.error(err);
    }
}

function saveVcDraft(index) {
    const tokenId = vcTokenIdList[index];
    if (!tokenId) return;
    const gEl = document.getElementById(`vc-g-${index}`);
    const cEl = document.getElementById(`vc-c-${index}`);
    if (gEl && cEl) {
        vcDraftInputs[tokenId] = { guild: gEl.value, channel: cEl.value };
    }
}

async function joinVC(index) {
    const tokenId = vcTokenIdList[index];
    const guild = document.getElementById(`vc-g-${index}`).value.trim();
    const channel = document.getElementById(`vc-c-${index}`).value.trim();
    if (!guild || !channel) {
        showToast('Server ID and Channel ID are required', 'error');
        return;
    }

    try {
        const response = await fetchWithAuth('/api/vc/join', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token: tokenId,
                guild_id: guild,
                channel_id: channel,
                self_mute: true,
                self_deaf: false
            })
        });
        if (response.ok) {
            vcDraftInputs[tokenId] = { guild, channel };
            showToast('Join request sent!', 'success');
            loadVC();
        } else {
            showToast('Failed to join voice channel', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('An error occurred', 'error');
    }
}

async function disconnectVC(index) {
    const tokenId = vcTokenIdList[index];
    const guild = document.getElementById(`vc-g-${index}`).value.trim();
    try {
        const response = await fetchWithAuth('/api/vc/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: tokenId, guild_id: guild })
        });
        if (response.ok) {
            vcDraftInputs[tokenId] = { guild, channel: '' };
            showToast('Disconnect request sent!', 'success');
            loadVC();
        } else {
            showToast('Failed to disconnect', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('An error occurred', 'error');
    }
}

async function restartToken(index) {
    const tokenId = tokenIdList[index];
    try {
        const res = await fetchWithAuth(`/api/tokens/${encodeURIComponent(tokenId)}/restart`, { method: 'POST' });
        if (res.ok) {
            showToast('Token restarted!', 'success');
            loadTokens();
        } else {
            showToast('Failed to restart token', 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('An error occurred', 'error');
    }
}

function toggleStreamingUrl() {
    const type = document.getElementById('t-rpc-type').value;
    document.getElementById('streaming-url-group').style.display = type === 'streaming' ? 'block' : 'none';
}

function normalizeUrl(url) {
    const trimmed = url.trim();
    if (!trimmed) return '';
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
    return `https://${trimmed}`;
}

function openAddModal() {
    isEditMode = false;
    currentEditTokenId = null;
    document.getElementById('modal-title').innerText = 'Add New Token';
    document.getElementById('t-token').value = '';
    document.getElementById('t-token').disabled = false;
    document.getElementById('token-form').reset();
    document.getElementById('t-vc-mute').checked = true;
    toggleStreamingUrl();
    document.getElementById('token-modal').classList.add('active');
}

function openEditModal(index) {
    const tokenId = tokenIdList[index];
    const config = currentTokensData[tokenId];
    if (!config) return;

    isEditMode = true;
    currentEditTokenId = tokenId;

    document.getElementById('modal-title').innerText = 'Edit Token';
    document.getElementById('t-token').value = tokenId;
    document.getElementById('t-token').disabled = true;

    document.getElementById('t-status').value = config.status || 'online';
    document.getElementById('t-platform').value = config.platform || 'pc';
    document.getElementById('t-status-text').value = config.status_text || '';

    document.getElementById('t-app-id').value = config.rpc?.application_id || '';
    document.getElementById('t-rpc-type').value = config.rpc?.activity_type || 'playing';
    document.getElementById('t-rpc-url').value = config.rpc?.url || '';
    document.getElementById('t-rpc-name').value = config.rpc?.name || '';
    document.getElementById('t-rpc-details').value = config.rpc?.details || '';
    document.getElementById('t-rpc-state').value = config.rpc?.state || '';
    document.getElementById('t-rpc-large-img').value = config.rpc?.large_image || '';
    document.getElementById('t-rpc-large-text').value = config.rpc?.large_text || '';
    document.getElementById('t-rpc-small-img').value = config.rpc?.small_image || '';
    document.getElementById('t-rpc-small-text').value = config.rpc?.small_text || '';
    document.getElementById('t-rpc-timestamp-start').value = config.rpc?.timestamp_start || '';
    document.getElementById('t-rpc-timestamp-end').value = config.rpc?.timestamp_end || '';
    document.getElementById('t-rpc-btn1-label').value = config.rpc?.btn1_label || '';
    document.getElementById('t-rpc-btn1-url').value = config.rpc?.btn1_url || '';
    document.getElementById('t-rpc-btn2-label').value = config.rpc?.btn2_label || '';
    document.getElementById('t-rpc-btn2-url').value = config.rpc?.btn2_url || '';
    document.getElementById('t-vc-guild').value = config.voice?.guild_id || '';
    document.getElementById('t-vc-channel').value = config.voice?.channel_id || '';
    document.getElementById('t-vc-mute').checked = config.voice?.self_mute !== false;
    document.getElementById('t-vc-deaf').checked = config.voice?.self_deaf === true;

    toggleStreamingUrl();
    document.getElementById('token-modal').classList.add('active');
}

function closeModal() {
    document.getElementById('token-modal').classList.remove('active');
}

async function saveToken() {
    const tokenId = document.getElementById('t-token').value.trim();
    if (!tokenId) {
        showToast('Token is required', 'error');
        return;
    }

    const btn1Label = document.getElementById('t-rpc-btn1-label').value.trim();
    const btn1Url = normalizeUrl(document.getElementById('t-rpc-btn1-url').value);
    const btn2Label = document.getElementById('t-rpc-btn2-label').value.trim();
    const btn2Url = normalizeUrl(document.getElementById('t-rpc-btn2-url').value);
    const appId = document.getElementById('t-app-id').value.trim();
    const rpcName = document.getElementById('t-rpc-name').value.trim();

    const hasButtons = (btn1Label && btn1Url) || (btn2Label && btn2Url);
    if (hasButtons && !appId) {
        showToast('Application ID is required when using RPC buttons', 'error');
        return;
    }
    if (hasButtons && !rpcName) {
        showToast('Activity Name is required when using RPC buttons', 'error');
        return;
    }

    const config = {
        status: document.getElementById('t-status').value,
        platform: document.getElementById('t-platform').value,
        status_text: document.getElementById('t-status-text').value,
        rpc: {
            application_id: appId,
            activity_type: document.getElementById('t-rpc-type').value,
            url: normalizeUrl(document.getElementById('t-rpc-url').value),
            name: rpcName,
            details: document.getElementById('t-rpc-details').value,
            state: document.getElementById('t-rpc-state').value,
            large_image: document.getElementById('t-rpc-large-img').value,
            large_text: document.getElementById('t-rpc-large-text').value,
            small_image: document.getElementById('t-rpc-small-img').value,
            small_text: document.getElementById('t-rpc-small-text').value,
            timestamp_start: document.getElementById('t-rpc-timestamp-start').value,
            timestamp_end: document.getElementById('t-rpc-timestamp-end').value,
            btn1_label: btn1Label,
            btn1_url: btn1Url,
            btn2_label: btn2Label,
            btn2_url: btn2Url
        },
        voice: {
            guild_id: document.getElementById('t-vc-guild').value,
            channel_id: document.getElementById('t-vc-channel').value,
            self_mute: document.getElementById('t-vc-mute').checked,
            self_deaf: document.getElementById('t-vc-deaf').checked
        }
    };

    try {
        let res;
        if (isEditMode) {
            res = await fetchWithAuth(`/api/tokens/${encodeURIComponent(currentEditTokenId)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
        } else {
            res = await fetchWithAuth('/api/tokens', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: tokenId, config })
            });
        }

        if (res.ok) {
            closeModal();
            showToast('Token saved successfully!', 'success');
            loadTokens();
        } else {
            const data = await res.json();
            showToast('Error: ' + (data.detail || 'Save failed'), 'error');
        }
    } catch (err) {
        console.error(err);
        showToast('An error occurred', 'error');
    }
}

async function deleteToken(index) {
    const tokenId = tokenIdList[index];
    if (!confirm('Are you sure you want to delete this token?')) return;
    try {
        const res = await fetchWithAuth(`/api/tokens/${encodeURIComponent(tokenId)}`, { method: 'DELETE' });
        if (res.ok) {
            delete vcDraftInputs[tokenId];
            showToast('Token deleted', 'success');
            loadTokens();
        }
    } catch (err) {
        console.error(err);
    }
}

async function bulkChangeStatus(status) {
    if (!confirm(`Set all tokens to ${status.toUpperCase()}?`)) return;
    try {
        const res = await fetchWithAuth('/api/tokens/bulk/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        if (res.ok) {
            showToast(`All tokens set to ${status}`, 'success');
            loadTokens();
        } else {
            showToast('Failed to update status', 'error');
        }
    } catch (err) {
        console.error(err);
    }
}

async function bulkRestart() {
    if (!confirm('Restart all token clients?')) return;
    try {
        const res = await fetchWithAuth('/api/tokens/bulk/restart', { method: 'POST' });
        if (res.ok) {
            showToast('All tokens restarted!', 'success');
            loadTokens();
        } else {
            showToast('Failed to restart tokens', 'error');
        }
    } catch (err) {
        console.error(err);
    }
}

async function bulkDisconnectVC() {
    if (!confirm('Disconnect all tokens from voice channels?')) return;
    try {
        const res = await fetchWithAuth('/api/tokens/bulk/disconnect-vc', { method: 'POST' });
        if (res.ok) {
            showToast('Disconnect requests sent!', 'success');
            if (document.getElementById('section-vc').classList.contains('active')) {
                loadVC();
            } else {
                loadTokens();
            }
        } else {
            showToast('Failed to disconnect tokens', 'error');
        }
    } catch (err) {
        console.error(err);
    }
}

function logout() {
    localStorage.removeItem('vc_token');
    window.location.href = '/login_page';
}

showSection('dashboard');
