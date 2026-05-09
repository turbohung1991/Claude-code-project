/**
 * 批量下载页面 — 前端逻辑
 */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const urlInput = $('#batchUrls');
const btnStart = $('#btnBatchStart');
const btnPause = $('#btnBatchPause');
const btnResume = $('#btnBatchResume');
const btnClear = $('#btnBatchClear');
const progressSection = $('#batchProgressSection');
const taskCards = $('#taskCards');
const globalProgressFill = $('#globalProgressFill');
const globalProgressText = $('#globalProgressText');

let currentBatchId = null;
let taskStates = {};
let eventSources = {};

// ==================== Actions ====================
btnStart.addEventListener('click', startBatch);
btnPause.addEventListener('click', pauseBatch);
btnResume.addEventListener('click', resumeBatch);
btnClear.addEventListener('click', clearAll);

async function startBatch() {
    const text = urlInput.value.trim();
    if (!text) { showToast('请粘贴抖音链接，一行一个'); return; }

    const urls = text.split('\n').map(s => s.trim()).filter(Boolean);
    if (urls.length === 0) { showToast('未检测到有效链接'); return; }
    if (urls.length > 50) { showToast('单次最多50个链接'); return; }

    btnStart.disabled = true;
    btnStart.textContent = '...';

    try {
        const resp = await fetch('/api/batch/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls }),
        });
        const data = await resp.json();

        if (!data.success) {
            showToast(data.error || '创建失败');
            btnStart.disabled = false;
            btnStart.textContent = '批量下载';
            return;
        }

        currentBatchId = data.batch_id;

        taskCards.innerHTML = '';
        data.tasks.forEach(task => {
            taskStates[task.task_id] = task;
            taskCards.appendChild(createTaskCard(task));
        });

        progressSection.classList.remove('hidden');
        btnStart.textContent = '处理中...';
        btnPause.classList.remove('hidden');

        data.tasks.forEach(task => {
            connectTaskSSE(task.task_id);
        });

    } catch (e) {
        showToast('请求失败: ' + e.message);
        btnStart.disabled = false;
        btnStart.textContent = '批量下载';
    }
}

async function pauseBatch() {
    if (!currentBatchId) return;
    await fetch('/api/batch/pause', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_id: currentBatchId }),
    });
    btnPause.classList.add('hidden');
    btnResume.classList.remove('hidden');
}

async function resumeBatch() {
    if (!currentBatchId) return;
    await fetch('/api/batch/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ batch_id: currentBatchId }),
    });
    btnResume.classList.add('hidden');
    btnPause.classList.remove('hidden');
}

function clearAll() {
    urlInput.value = '';
    taskCards.innerHTML = '';
    progressSection.classList.add('hidden');
    currentBatchId = null;
    taskStates = {};
    Object.values(eventSources).forEach(es => { try { es.close(); } catch(e) {} });
    eventSources = {};
    btnStart.disabled = false;
    btnStart.textContent = '批量下载';
    btnPause.classList.add('hidden');
    btnResume.classList.add('hidden');
}

// ==================== Task Card ====================
function createTaskCard(task) {
    const div = document.createElement('div');
    div.className = 'task-card status-queued';
    div.id = 'card-' + task.task_id;
    div.innerHTML = `
        <div class="task-card-header">
            <div class="task-card-cover" id="cover-${task.task_id}"></div>
            <div class="task-card-info">
                <div class="tc-desc" id="desc-${task.task_id}">...</div>
                <div class="tc-author" id="author-${task.task_id}"></div>
                <div class="tc-url">${escHTML(task.url)}</div>
            </div>
            <div class="task-card-status">
                <span class="status-badge queued" id="status-${task.task_id}">排队中</span>
            </div>
        </div>
        <div class="task-card-progress">
            <div class="mini-bar"><div class="mini-fill" id="miniFill-${task.task_id}"></div></div>
            <div class="mini-text" id="miniText-${task.task_id}">...</div>
        </div>
        <div class="task-card-actions" id="actions-${task.task_id}">
            <button class="btn btn-sm" onclick="retryTask('${task.task_id}')" id="btnRetry-${task.task_id}" style="display:none;">重试</button>
            <button class="btn btn-sm" onclick="analyzeComments('${task.task_id}')" id="btnComment-${task.task_id}" style="display:none;">评论分析</button>
        </div>
        <div id="commentPanel-${task.task_id}"></div>
    `;
    return div;
}

function updateTaskCard(taskId, updates) {
    const state = taskStates[taskId] = { ...(taskStates[taskId] || {}), ...updates };
    const card = $('#card-' + taskId);
    if (!card) return;

    const badge = $('#status-' + taskId);
    const statusMap = {
        'queued': ['排队中', 'queued'],
        'parsing': ['解析中', 'parsing'],
        'downloading': ['下载中', 'downloading'],
        'done': ['已完成', 'done'],
        'error': ['失败', 'error'],
    };
    const [label, cls] = statusMap[state.status] || [state.status, 'queued'];
    badge.textContent = label;
    badge.className = 'status-badge ' + cls;
    card.className = 'task-card status-' + (
        state.status === 'downloading' || state.status === 'parsing' ? 'processing' : state.status
    );

    if (state.percent !== undefined) {
        $('#miniFill-' + taskId).style.width = state.percent + '%';
    }
    if (state.message) {
        $('#miniText-' + taskId).textContent = state.message;
    }
    if (state.desc) {
        $('#desc-' + taskId).textContent = state.desc;
        $('#desc-' + taskId).title = state.desc;
    }
    if (state.author) {
        $('#author-' + taskId).textContent = '' + state.author;
    }
    if (state.cover) {
        $('#cover-' + taskId).style.backgroundImage = 'url(' + state.cover + ')';
    }

    if (state.status === 'done') {
        $('#btnComment-' + taskId).style.display = '';
        $('#btnRetry-' + taskId).style.display = 'none';
    } else if (state.status === 'error') {
        $('#btnRetry-' + taskId).style.display = '';
        $('#btnComment-' + taskId).style.display = 'none';
    }

    updateGlobalProgress();
}

function updateGlobalProgress() {
    const tasks = Object.values(taskStates);
    const done = tasks.filter(t => t.status === 'done').length;
    const error = tasks.filter(t => t.status === 'error').length;
    const total = tasks.length;
    const finished = done + error;
    const pct = total > 0 ? Math.round(finished * 100 / total) : 0;
    globalProgressFill.style.width = pct + '%';
    globalProgressText.textContent = done + ' / ' + total + ' 完成';

    // All tasks finished
    if (finished >= total && total > 0) {
        btnStart.textContent = '重新开始';
        btnStart.disabled = false;
        btnPause.classList.add('hidden');
        btnResume.classList.add('hidden');
    }
}

// ==================== SSE ====================
function connectTaskSSE(taskId) {
    if (eventSources[taskId]) {
        eventSources[taskId].close();
    }

    const es = new EventSource('/api/stream/' + taskId);
    eventSources[taskId] = es;

    es.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        const statusMap = {
            'parse': 'parsing',
            'download': 'downloading',
            'subtitle': 'downloading',
            'done': 'done',
        };
        updateTaskCard(taskId, {
            status: statusMap[data.step] || 'downloading',
            percent: data.percent || 0,
            message: data.message || '',
        });
    });

    es.addEventListener('meta', (e) => {
        const data = JSON.parse(e.data);
        updateTaskCard(taskId, {
            videoId: data.video_id,
            desc: data.desc,
            author: data.author,
            cover: data.cover,
        });
    });

    es.addEventListener('video_ready', (e) => {
        const data = JSON.parse(e.data);
        updateTaskCard(taskId, { videoUrl: data.url, filename: data.filename });
    });

    es.addEventListener('subtitle_ready', (e) => {
        const data = JSON.parse(e.data);
        updateTaskCard(taskId, { subtitleText: data.text });
    });

    es.addEventListener('complete', () => {
        updateTaskCard(taskId, { status: 'done', percent: 100, message: '完成' });
        es.close();
    });

    es.addEventListener('error', (e) => {
        try {
            const data = JSON.parse(e.data);
            updateTaskCard(taskId, { status: 'error', message: data.message || '' });
        } catch {
            updateTaskCard(taskId, { status: 'error', message: '处理失败' });
        }
        es.close();
    });

    es.onerror = () => {
        if (es.readyState === EventSource.CLOSED) {
            delete eventSources[taskId];
        }
    };
}

// ==================== Retry ====================
async function retryTask(taskId) {
    if (!currentBatchId) return;
    updateTaskCard(taskId, { status: 'parsing', percent: 0, message: '...' });
    await fetch('/api/batch/retry/' + taskId, { method: 'POST' });
    connectTaskSSE(taskId);
}

// ==================== Comment Analysis ====================
async function analyzeComments(taskId) {
    const state = taskStates[taskId];
    const videoId = state.videoId;
    if (!videoId) { showToast('未找到视频ID'); return; }

    const panel = $('#commentPanel-' + taskId);
    panel.innerHTML = '<div class="comment-panel"><div class="comment-loading"><div class="spinner"></div>正在抓取评论并分析...</div></div>';

    try {
        const resp = await fetch('/api/comments/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_id: videoId }),
        });
        const fetchData = await resp.json();

        // Poll for results
        await pollCommentResult(taskId, videoId);
    } catch (e) {
        panel.innerHTML = '<div class="comment-panel"><p style="color:var(--danger);">评论分析失败: ' + e.message + '</p></div>';
    }
}

async function pollCommentResult(taskId, videoId) {
    const maxAttempts = 60;
    for (let i = 0; i < maxAttempts; i++) {
        try {
            const resp = await fetch('/api/comments/result/' + videoId);
            const data = await resp.json();

            if (data.status !== 'fetching') {
                taskStates[taskId].commentCursor = data.cursor;
                renderCommentResult(taskId, data);
                return;
            }
        } catch (e) {
            // keep polling
        }
        await new Promise(r => setTimeout(r, 2000));
    }
    $('#commentPanel-' + taskId).innerHTML = '<div class="comment-panel"><p style="color:var(--danger);">评论分析超时，请重试</p></div>';
}

function renderCommentResult(taskId, data) {
    const panel = $('#commentPanel-' + taskId);
    const analysis = data.analysis || {};
    const totalFetched = data.total_fetched || 0;
    const C = ['#6c5ce7', '#ff6b9d', '#4ecdc4', '#ffa502', '#00d68f', '#45aaf2'];

    // ---- Sentiment cards ----
    let sentimentHtml = '';
    if (analysis.sentiment) {
        const s = analysis.sentiment;
        const items = [
            { label: '正面', pct: s.positive, count: s.positive_count || 0, color: '#00d68f', icon: '😊' },
            { label: '中性', pct: s.neutral, count: s.neutral_count || 0, color: '#ffa502', icon: '😐' },
            { label: '负面', pct: s.negative, count: s.negative_count || 0, color: '#ff6b6b', icon: '😟' },
        ];
        sentimentHtml = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px;">' +
            items.map(it => (
                '<div style="text-align:center;padding:16px 10px;border-radius:12px;background:linear-gradient(135deg,' + it.color + '18,transparent);border:1px solid ' + it.color + '33;">' +
                '<div style="font-size:2rem;">' + it.icon + '</div>' +
                '<div style="font-size:1.4rem;font-weight:700;color:' + it.color + ';">' + it.pct + '%</div>' +
                '<div style="font-size:0.78rem;color:var(--text-dim);">' + it.label + ' (' + it.count + '条)</div>' +
                '</div>'
            )).join('') +
            '</div>';
    }

    // ---- Word cloud ----
    let cloudHtml = '';
    if (analysis.keywords && analysis.keywords.length > 0) {
        const maxCount = analysis.keywords[0].count || 1;
        const minCount = analysis.keywords[analysis.keywords.length - 1].count || 1;
        const palette = ['#a78bfa', '#e879f9', '#f472b6', '#fb7185', '#fbbf24', '#34d399', '#38bdf8', '#818cf8', '#c084fc', '#fb923c', '#4ade80'];
        // Pre-shuffle to avoid adjacent same colors
        const rotations = [-6, -2, 0, 0, 3, -4, 1, -5, -1, 4, 0, -3, 2, 5, -7];

        cloudHtml = '<div style="background:radial-gradient(ellipse at center,rgba(108,92,231,0.08),rgba(15,15,19,0.3));border-left:3px solid #6c5ce7;border-radius:0 10px 10px 0;padding:22px 20px;margin-bottom:18px;border-top:1px solid #1e1e2e;border-right:1px solid #1e1e2e;border-bottom:1px solid #1e1e2e;overflow:hidden;">' +
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:18px;">' +
            '<span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:8px;background:rgba(108,92,231,0.13);font-size:1rem;">☁️</span>' +
            '<span style="font-size:1.05rem;font-weight:700;color:#6c5ce7;">评论词云</span>' +
            '</div>' +
            '<div style="display:flex;flex-wrap:wrap;gap:10px 8px;align-items:center;justify-content:center;padding:16px 4px;min-height:120px;line-height:1.4;">' +
            analysis.keywords.map((k, i) => {
                const ratio = (k.count - minCount) / (maxCount - minCount || 1);
                // Size: 0.75rem ~ 2.2rem
                const size = 0.75 + ratio * 1.45;
                // Weight
                const weight = ratio > 0.6 ? 700 : ratio > 0.25 ? 600 : 400;
                // Color: weight-based
                const color = ratio > 0.5 ? '#f472b6' : ratio > 0.3 ? '#a78bfa' : palette[i % palette.length];
                const rot = rotations[i % rotations.length];
                // Background opacity
                const bgAlpha = 0.08 + ratio * 0.14;
                const glow = ratio > 0.5 ? '0 0 16px ' + color + '22, ' : '';
                return '<span style="display:inline-block;padding:' + (4 + ratio * 6).toFixed(0) + 'px ' + (12 + ratio * 14).toFixed(0) + 'px;border-radius:' + (16 + ratio * 10).toFixed(0) + 'px;font-size:' + size.toFixed(2) + 'rem;font-weight:' + weight + ';color:' + color + ';background:' + color + Math.round(bgAlpha * 255).toString(16).padStart(2, '0') + ';border:1px solid ' + color + '33;transform:rotate(' + rot + 'deg);box-shadow:' + glow + '0 1px 4px rgba(0,0,0,0.2);transition:all 0.25s cubic-bezier(0.4,0,0.2,1);cursor:default;white-space:nowrap;' + '" onmouseover="this.style.transform=\'rotate(0deg) scale(1.15)\';this.style.boxShadow=\'0 4px 20px ' + color + '55, 0 0 8px ' + color + '33\';this.style.zIndex=10;this.style.position=\'relative\';" onmouseout="this.style.transform=\'rotate(' + rot + 'deg) scale(1)\';this.style.boxShadow=\'' + (glow + '0 1px 4px rgba(0,0,0,0.2)').replace(/'/g, "\\'") + '\';this.style.zIndex=0;this.style.position=\'static\';">' + escHTML(k.word) + '</span>';
            }).join('') +
            '</div></div>';
    }

    // ---- AI Summary ----
    let summaryHtml = '';
    if (analysis.summary) {
        summaryHtml = '<div style="background:linear-gradient(135deg,rgba(255,107,157,0.06),transparent);border-left:3px solid #ff6b9d;border-radius:0 10px 10px 0;padding:18px;margin-bottom:8px;border-top:1px solid #1e1e2e;border-right:1px solid #1e1e2e;border-bottom:1px solid #1e1e2e;">' +
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">' +
            '<span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:8px;background:rgba(255,107,157,0.13);font-size:1rem;">🧠</span>' +
            '<span style="font-size:1.05rem;font-weight:700;color:#ff6b9d;">AI 综合总结</span>' +
            '</div>' +
            '<div style="color:#b8b4c4;font-size:0.9rem;line-height:1.85;">' +
            analysis.summary
                .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#ff6b9d;background:rgba(255,107,157,0.12);padding:1px 5px;border-radius:4px;">$1</strong>')
                .replace(/^### (.+)$/gm, '<h3 style="font-size:0.95rem;color:#4ecdc4;margin:12px 0 6px;">$1</h3>')
                .replace(/^## (.+)$/gm, '<h2 style="font-size:1rem;color:#ff6b9d;margin:14px 0 6px;padding-bottom:4px;border-bottom:1px solid #2a2a3a;">$1</h2>')
                .replace(/^[-*] (.+)$/gm, '<li style="margin-left:16px;margin-bottom:6px;color:#b8b4c4;">$1</li>')
                .replace(/\n/g, '<br>') +
            '</div></div>';
    }

    // Store for export
    window._commentExportData = window._commentExportData || {};
    window._commentExportData[taskId] = {
        totalFetched: totalFetched,
        sentimentHtml: sentimentHtml,
        cloudHtml: cloudHtml,
        summaryHtml: summaryHtml,
        sentiment: analysis.sentiment,
        keywords: analysis.keywords,
        summary: analysis.summary,
    };

    panel.innerHTML = `
        <div class="comment-panel">
            <h4 style="font-size:0.95rem;color:var(--text);margin-bottom:14px;">💬 评论分析 <span style="color:var(--text-dim);font-weight:400;">(${totalFetched}条)</span></h4>
            ${sentimentHtml}
            ${cloudHtml}
            ${summaryHtml}
            <div style="margin-top:16px;padding-top:14px;border-top:1px solid #2a2a3a;display:flex;gap:10px;flex-wrap:wrap;">
                <button class="btn btn-sm" onclick="exportCommentReport('${taskId}', 'pdf')" title="导出为PDF">🖨 导出 PDF</button>
                <button class="btn btn-sm" onclick="exportCommentReport('${taskId}', 'img')" title="导出为图片">🖼 导出图片</button>
                <button class="btn btn-sm" onclick="downloadCommentCSV('${taskId}')" title="导出评论原始数据">📊 导出评论数据</button>
            </div>
        </div>
    `;
}

function downloadCommentCSV(taskId) {
    const state = taskStates[taskId];
    const videoId = state && state.videoId;
    if (!videoId) { showToast('未找到视频ID'); return; }
    const a = document.createElement('a');
    a.href = '/api/comments/export-data/' + videoId;
    a.download = 'comments_' + videoId + '.csv';
    a.click();
    showToast('正在下载评论数据...');
}

async function exportCommentReport(taskId, format) {
    const data = window._commentExportData && window._commentExportData[taskId];
    if (!data) { showToast('无导出数据'); return; }

    const sentiment = data.sentiment || {};
    const keywords = data.keywords || [];
    const summary = data.summary || '';

    // Build rich HTML for export
    const kwHtml = keywords.map((k, i) => {
        const colors = ['#6c5ce7', '#ff6b9d', '#4ecdc4', '#ffa502', '#00d68f', '#45aaf2'];
        const c = colors[i % colors.length];
        const ratio = keywords.length > 0 ? k.count / keywords[0].count : 1;
        const size = 12 + Math.round(ratio * 16);
        return `<span style="display:inline-block;padding:4px 12px;margin:4px;border-radius:16px;font-size:${size}px;color:${c};background:${c}18;border:1px solid ${c}33;">${k.word}</span>`;
    }).join('');

    const title = '评论分析报告';

    const html = `<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f0f13;color:#e0e0e0;padding:40px;line-height:1.8;">
<h2 style="color:#6c5ce7;border-bottom:2px solid #2a2a3a;padding-bottom:12px;">💬 ${title}</h2>
<p style="color:#888;">评论总数: ${data.totalFetched} 条</p>

<h3 style="color:#ff6b9d;margin-top:24px;">情感分布</h3>
<table style="width:100%;border-collapse:collapse;margin:16px 0;">
<tr>
<td style="padding:16px;text-align:center;background:rgba(0,214,143,0.08);border:1px solid #2a2a3a;border-radius:8px 0 0 8px;"><div style="font-size:2rem;">😊</div><div style="font-size:1.4rem;font-weight:700;color:#00d68f;">${sentiment.positive || 0}%</div><div style="font-size:0.8rem;color:#888;">正面 (${sentiment.positive_count || 0})</div></td>
<td style="padding:16px;text-align:center;background:rgba(255,165,2,0.08);border:1px solid #2a2a3a;"><div style="font-size:2rem;">😐</div><div style="font-size:1.4rem;font-weight:700;color:#ffa502;">${sentiment.neutral || 0}%</div><div style="font-size:0.8rem;color:#888;">中性 (${sentiment.neutral_count || 0})</div></td>
<td style="padding:16px;text-align:center;background:rgba(255,107,107,0.08);border:1px solid #2a2a3a;border-radius:0 8px 8px 0;"><div style="font-size:2rem;">😟</div><div style="font-size:1.4rem;font-weight:700;color:#ff6b6b;">${sentiment.negative || 0}%</div><div style="font-size:0.8rem;color:#888;">负面 (${sentiment.negative_count || 0})</div></td>
</tr>
</table>

<h3 style="color:#6c5ce7;margin-top:24px;">☁️ 评论词云</h3>
<div style="padding:16px;text-align:center;">${kwHtml}</div>

<h3 style="color:#ff6b9d;margin-top:24px;">🧠 AI 综合总结</h3>
<div style="padding:16px;background:#111119;border-radius:10px;border:1px solid #2a2a3a;">${summary.replace(/\n/g, '<br>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')}</div>
</div>`;

    const endpoint = format === 'pdf' ? '/api/export/pdf' : '/api/export/image';
    try {
        showToast('正在导出...');
        const resp = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ html, title }),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.error); }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = title + (format === 'pdf' ? '.pdf' : '.png');
        a.click();
        URL.revokeObjectURL(url);
        showToast('导出完成');
    } catch (e) {
        showToast('导出失败: ' + e.message);
    }
}


// ==================== Utils ====================
function escHTML(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

let toastTimer;
function showToast(msg) {
    const toast = $('#toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), 3000);
}
