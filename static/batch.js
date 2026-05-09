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
    const total = tasks.length;
    const pct = total > 0 ? Math.round(done * 100 / total) : 0;
    globalProgressFill.style.width = pct + '%';
    globalProgressText.textContent = done + ' / ' + total + ' 完成';
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
    $('#commentPanel-' + taskId).innerHTML = '<div class="comment-panel"><p style="color:var(--danger);"></p></div>';
}

function renderCommentResult(taskId, data) {
    const panel = $('#commentPanel-' + taskId);
    const analysis = data.analysis || {};

    let sentimentHtml = '';
    if (analysis.sentiment) {
        const s = analysis.sentiment;
        sentimentHtml = `
            <div class="comment-stats">
                <div class="comment-stat positive">
                    <div class="cs-value">${s.positive}%</div>
                    <div class="cs-label">正面 (${s.positive_count || 0})</div>
                </div>
                <div class="comment-stat neutral">
                    <div class="cs-value">${s.neutral}%</div>
                    <div class="cs-label">中性 (${s.neutral_count || 0})</div>
                </div>
                <div class="comment-stat negative">
                    <div class="cs-value">${s.negative}%</div>
                    <div class="cs-label">负面 (${s.negative_count || 0})</div>
                </div>
            </div>
        `;
    }

    let kwHtml = '';
    if (analysis.keywords && analysis.keywords.length > 0) {
        kwHtml = '<div class="comment-keywords">' +
            analysis.keywords.map(k =>
                '<span class="comment-keyword">' + escHTML(k.word) + ' (' + k.count + ')</span>'
            ).join('') +
            '</div>';
    }

    let summaryHtml = '';
    if (analysis.summary) {
        summaryHtml = '<div class="comment-summary">' +
            analysis.summary.replace(/\n/g, '<br>') +
            '</div>';
    }

    const hasMore = data.has_more;
    const totalFetched = data.total_fetched || 0;

    panel.innerHTML = `
        <div class="comment-panel">
            <h4>评论分析 (${totalFetched}条)</h4>
            ${sentimentHtml}
            ${kwHtml}
            ${summaryHtml}
            ${hasMore ? `<button class="btn btn-sm" onclick="loadMoreComments('${taskId}')" style="margin-top:12px;">加载更多</button>` : ''}
        </div>
    `;
}

async function loadMoreComments(taskId) {
    const state = taskStates[taskId];
    const videoId = state.videoId;
    const cursor = state.commentCursor || 0;

    try {
        const resp = await fetch('/api/comments/load-more?video_id=' + videoId + '&cursor=' + cursor + '&count=50');
        const data = await resp.json();
        taskStates[taskId].commentCursor = data.cursor;
        renderCommentResult(taskId, data);
        showToast('已加载更多评论');
    } catch (e) {
        showToast('加载失败: ' + e.message);
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
