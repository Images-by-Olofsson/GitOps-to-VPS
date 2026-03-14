/* ============================================
   DevOps Dashboard v2 – Application Logic
   ============================================ */

const DATA_URL = 'data.json';
const REFRESH_INTERVAL = 10000; // 10 seconds

// ---- Data Fetching ----

async function fetchData() {
    try {
        const response = await fetch(DATA_URL + '?t=' + Date.now());
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        renderDashboard(data);
    } catch (error) {
        console.error('Fetch error:', error);
        document.getElementById('services-grid').innerHTML = `
            <div class="loading" style="color: var(--error)">
                Failed to load dashboard data.<br>
                <small>Ensure the updater service is running.</small>
            </div>`;
    }
}

// ---- Main Render ----

function renderDashboard(data) {
    renderHeader(data);
    renderStats(data);
    renderServices(data);
    renderCertificates(data);
    renderDeploys(data);
}

// ---- Header ----

function renderHeader(data) {
    const ts = document.getElementById('timestamp');
    const badge = document.getElementById('overall-status');

    ts.textContent = data.timestamp
        ? new Date(data.timestamp).toLocaleString('sv-SE')
        : '--';

    const statusMap = {
        ok:       { cls: 'ok',      text: '● System Healthy' },
        degraded: { cls: 'warning', text: '▲ Services Down' },
        failed:   { cls: 'failed',  text: '✖ Issues Detected' }
    };

    const s = statusMap[data.summary] || statusMap.failed;
    badge.className = 'status-badge ' + s.cls;
    badge.textContent = s.text;
}

// ---- Stats Bar ----

function renderStats(data) {
    const services = Object.values(data.services || {});
    const healthy = services.filter(s => s.status === 'healthy').length;
    const issues = services.filter(s => s.status !== 'healthy').length;
    const certs = (data.certificates || []).length;

    document.getElementById('stat-total').textContent = services.length;
    document.getElementById('stat-healthy').textContent = healthy;
    document.getElementById('stat-issues').textContent = issues;
    document.getElementById('stat-certs').textContent = certs;
}

// ---- Services Grid ----

function renderServices(data) {
    const grid = document.getElementById('services-grid');
    const entries = Object.entries(data.services || {});
    const resources = data.resources || {};

    if (!entries.length) {
        grid.innerHTML = '<div class="empty-state">No services found.</div>';
        return;
    }

    grid.innerHTML = '';
    entries.forEach(([name, info]) => {
        grid.appendChild(createServiceCard(name, info, resources));
    });
}

function createServiceCard(name, info, resources) {
    const isHealthy = info.status === 'healthy';
    const isRunning = (info.runtime_state || '').toLowerCase() === 'running';

    const card = document.createElement('div');
    card.className = `card ${isHealthy ? 'healthy' : 'error'}`;

    // Find resource data (match by container name pattern)
    const resData = findResourceData(name, resources);

    let resourceHtml = '';
    if (resData) {
        resourceHtml = `
            <div class="resource-bar-container">
                ${createResourceBar('CPU', resData.cpu_percent)}
                ${createResourceBar('MEM', resData.mem_percent, resData.mem_usage + ' / ' + resData.mem_limit)}
            </div>`;
    }

    let issuesHtml = '';
    if (info.issues && info.issues.length > 0) {
        issuesHtml = `
            <div class="issues-list">
                ${info.issues.map(issue => `
                    <div class="issue-item">
                        <span class="issue-icon">✗</span>
                        <span>${escapeHtml(issue)}</span>
                    </div>
                `).join('')}
            </div>`;
    }

    // Determine status dot class
    let dotClass = 'offline';
    let dotLabel = 'Offline';
    if (isRunning) {
        dotClass = isHealthy ? 'healthy' : 'warning';
        dotLabel = isHealthy ? 'Healthy' : 'Issues';
    } else if (info.runtime_state !== 'Not Running') {
        dotClass = 'warning';
        dotLabel = info.runtime_state;
    }

    const memoryDisplay = formatMemory(info.config?.memory);

    const domain = info.config?.domain;
    const serviceNameHtml = domain 
        ? `<a href="https://${domain}" target="_blank" class="service-link">${escapeHtml(name)} 🔗</a>`
        : `<span class="service-name">${escapeHtml(name)}</span>`;

    card.innerHTML = `
        <div class="card-header">
            ${serviceNameHtml}
            <div class="status-indicator">
                <span style="color: var(--text-muted); font-size: 0.7rem">${dotLabel}</span>
                <span class="status-dot ${dotClass}" title="${dotLabel}"></span>
            </div>
        </div>
        <div class="card-body">
            <div class="info-row">
                <span class="info-label">State</span>
                <span class="info-value ${isRunning ? 'running' : 'stopped'}">${info.runtime_state || '-'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Limits</span>
                <span class="info-value">${info.config?.cpu || '-'} CPU / ${memoryDisplay}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Access</span>
                <span class="info-value ${info.config?.public ? 'public' : ''}">${info.config?.public ? '🌐 Public' : '🔒 Internal'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Routers</span>
                <span class="info-value">${info.config?.routers || 0}</span>
            </div>
            ${resourceHtml}
            ${issuesHtml}
        </div>
    `;

    return card;
}

function findResourceData(serviceName, resources) {
    if (!resources || !Object.keys(resources).length) return null;

    // Exact match first
    if (resources[serviceName]) return resources[serviceName];

    // Try matching by container name (service names often become container names)
    for (const [containerName, data] of Object.entries(resources)) {
        if (containerName.includes(serviceName) || serviceName.includes(containerName)) {
            return data;
        }
    }
    return null;
}

function createResourceBar(label, percent, detail) {
    const pct = Math.min(100, Math.max(0, parseFloat(percent) || 0));
    const levelClass = pct < 60 ? 'low' : (pct < 85 ? 'mid' : 'high');
    const displayText = detail || `${pct.toFixed(1)}%`;

    return `
        <div class="resource-bar-label">
            <span>${label}</span>
            <span>${displayText}</span>
        </div>
        <div class="resource-bar-track">
            <div class="resource-bar-fill ${levelClass}" style="width: ${pct}%"></div>
        </div>
    `;
}

function formatMemory(bytes) {
    if (!bytes || bytes === 'N/A') return 'N/A';
    const num = typeof bytes === 'string' ? parseInt(bytes) : bytes;
    if (isNaN(num)) return bytes;
    if (num >= 1073741824) return (num / 1073741824).toFixed(1) + ' GiB';
    if (num >= 1048576) return (num / 1048576).toFixed(0) + ' MiB';
    if (num >= 1024) return (num / 1024).toFixed(0) + ' KiB';
    return num + ' B';
}

// ---- Certificates ----

function renderCertificates(data) {
    const section = document.getElementById('certs-section');
    const grid = document.getElementById('certs-grid');
    const certs = data.certificates || [];

    if (!certs.length) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    section.className = '';
    grid.innerHTML = '';

    certs.forEach(cert => {
        grid.appendChild(createCertCard(cert));
    });
}

function createCertCard(cert) {
    const days = cert.days_left;
    let level, icon, badgeText;

    if (days < 0 || days === -1) {
        level = 'fail';
        icon = '⚠';
        badgeText = 'UNKNOWN';
    } else if (days <= 7) {
        level = 'fail';
        icon = '🔴';
        badgeText = `${days}d LEFT`;
    } else if (days <= 30) {
        level = 'warn';
        icon = '🟡';
        badgeText = `${days}d LEFT`;
    } else {
        level = 'ok';
        icon = '🟢';
        badgeText = `${days}d LEFT`;
    }

    const expiryText = cert.expiry !== 'unknown'
        ? new Date(cert.expiry).toLocaleDateString('sv-SE')
        : 'Unknown';

    const el = document.createElement('div');
    el.className = 'cert-card';
    el.innerHTML = `
        <div class="cert-icon ${level}">${icon}</div>
        <div class="cert-info">
            <div class="cert-domain" title="${escapeHtml(cert.domain)}">${escapeHtml(cert.domain)}</div>
            <div class="cert-expiry">Expires: ${expiryText}</div>
        </div>
        <span class="cert-badge ${level}">${badgeText}</span>
    `;
    return el;
}

// ---- Deploy Timeline ----

function renderDeploys(data) {
    const section = document.getElementById('deploys-section');
    const timeline = document.getElementById('deploy-timeline');
    const deploys = data.deploys || [];

    if (!deploys.length) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';
    section.className = '';
    timeline.innerHTML = '';

    // Show newest first
    [...deploys].reverse().forEach(deploy => {
        timeline.appendChild(createDeployEntry(deploy));
    });
}

function formatDeployTime(ts) {
    if (!ts || ts.length !== 15 || !ts.includes('_')) return escapeHtml(ts);
    const yyyy = ts.substring(0, 4);
    const mm = ts.substring(4, 6);
    const dd = ts.substring(6, 8);
    const hh = ts.substring(9, 11);
    const min = ts.substring(11, 13);
    const ss = ts.substring(13, 15);
    return `Date: <${yyyy}:${mm}:${dd}> Time: <${hh}:${min}:${ss}>`;
}

function createDeployEntry(deploy) {
    const isSuccess = deploy.status === 'SUCCESS';
    const el = document.createElement('a');
    el.className = 'deploy-entry';
    el.href = 'https://github.com/Images-by-Olofsson/GitOps-to-VPS/actions/workflows/deploy_validation.yml';
    el.target = '_blank';
    el.style.textDecoration = 'none';
    el.style.color = 'inherit';
    el.style.display = 'flex';
    el.innerHTML = `
        <span class="deploy-dot ${isSuccess ? 'success' : 'failed'}"></span>
        <div class="deploy-info">
            <div class="deploy-action">${escapeHtml(deploy.action)}</div>
            <div class="deploy-time">${formatDeployTime(deploy.timestamp)}</div>
        </div>
        <span class="deploy-status ${isSuccess ? 'success' : 'failed'}">${escapeHtml(deploy.status)}</span>
    `;
    return el;
}

// ---- Utils ----

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// ---- Init ----

fetchData();
setInterval(fetchData, REFRESH_INTERVAL);
