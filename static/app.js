/**
 * 抖音视频下载分析 Web 应用 - 前端逻辑
 */

// ==================== DOM 元素 ====================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const urlInput = $('#urlInput');
const btnParse = $('#btnParse');
const btnPaste = $('#btnPaste');
const btnClear = $('#btnClear');
const btnHistory = $('#btnHistory');
const btnDownload = $('#btnDownload');
const parseError = $('#parseError');
const videoCard = $('#videoCard');
const progressSection = $('#progressSection');
const videoSection = $('#videoSection');
const subtitleSection = $('#subtitleSection');
const aiSection = $('#aiSection');
const historyModal = $('#historyModal');
const toggleAI = $('#toggleAI');

let currentTaskId = null;
let selectedQuality = 0;
let videoData = null;
let eventSource = null;

// ==================== 按钮事件 ====================
btnParse.addEventListener('click', parseUrl);
urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') parseUrl();
});

btnPaste.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        urlInput.value = text;
        parseUrl();
    } catch {
        showToast('无法访问剪贴板，请手动粘贴');
    }
});

btnClear.addEventListener('click', () => {
    urlInput.value = '';
    resetAll();
});

btnHistory.addEventListener('click', openHistory);

btnDownload.addEventListener('click', startProcess);

// ==================== 核心逻辑 ====================
async function parseUrl() {
    const url = urlInput.value.trim();
    if (!url) {
        showError('请输入抖音链接');
        return;
    }

    resetAll();
    btnParse.disabled = true;
    btnParse.textContent = '⏳ 解析中...';
    hideError();

    try {
        const resp = await fetch('/api/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        const data = await resp.json();

        if (!data.success) {
            showError(data.error);
            return;
        }

        // 保存数据
        videoData = data;

        // 渲染视频信息
        renderVideoCard(data);

        // 渲染清晰度选项
        renderQualityOptions(data.qualities);

        videoCard.classList.remove('hidden');

        // 预显示字幕
        if (data.subtitles_preview) {
            subtitleSection.classList.remove('hidden');
            $('#subtitleSource').textContent = '来源: API数据（预览）';
            $('#subtitleContent').textContent = data.subtitles_preview;
        }

        // 滚动到卡片
        videoCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (e) {
        showError('网络错误: ' + e.message);
    } finally {
        btnParse.disabled = false;
        btnParse.textContent = '🔍 解析';
    }
}

function renderVideoCard(data) {
    const info = data.info;
    $('#videoDesc').textContent = info.desc;
    $('#videoAuthor').textContent = info.author;
    $('#videoDuration').textContent = info.duration;
    $('#videoDigg').textContent = formatNumber(info.stats.digg);
    $('#videoComment').textContent = formatNumber(info.stats.comment);
    $('#videoShare').textContent = formatNumber(info.stats.share);

    // 封面
    if (info.cover) {
        $('#videoCover').style.backgroundImage = `url(${info.cover})`;
    } else {
        $('#videoCover').style.background = 'linear-gradient(135deg, #6c5ce7, #ff6b9d)';
    }

    // 话题标签
    const hashtags = info.hashtags.filter(Boolean);
    $('#videoHashtags').innerHTML = hashtags.map(t => `<span class="hashtag">#${t}</span>`).join('');

    // 音乐
    if (info.music && info.music.title) {
        const musicDiv = document.createElement('div');
        musicDiv.className = 'meta-row';
        musicDiv.innerHTML = `<span class="meta-item">🎵 <strong>${info.music.title}</strong>${info.music.author ? ' - ' + info.music.author : ''}</span>`;
        $('#videoHashtags').parentNode.insertBefore(musicDiv, $('#videoHashtags').nextSibling);
    }
}

function renderQualityOptions(qualities) {
    const container = $('#qualityOptions');
    container.innerHTML = '';

    qualities.forEach((q, i) => {
        const div = document.createElement('div');
        div.className = `quality-option${i === selectedQuality ? ' selected' : ''}`;
        const res = q.width ? `${q.width}x${q.height}` : '默认';
        const rate = q.bit_rate ? ` ${(q.bit_rate/1000000).toFixed(1)}Mbps` : '';
        div.innerHTML = `
            <span class="q-label">${q.label}</span>
            <span class="q-info">${res}${rate}</span>
        `;
        div.addEventListener('click', () => {
            selectedQuality = i;
            renderQualityOptions(qualities);
        });
        container.appendChild(div);
    });
}

async function startProcess() {
    if (!videoData) {
        showToast('请先解析链接');
        return;
    }

    // 重置结果区
    videoSection.classList.add('hidden');
    subtitleSection.classList.add('hidden');
    aiSection.classList.add('hidden');

    // 启动进度区
    progressSection.classList.remove('hidden');
    $('#progressFill').style.width = '0%';
    $('#progressPercent').textContent = '0%';
    $('#progressMsg').textContent = '准备中...';
    $('#progressSteps').innerHTML = '';

    btnDownload.disabled = true;
    btnDownload.textContent = '⏳ 处理中...';

    try {
        const resp = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: urlInput.value.trim(),
                quality_index: selectedQuality,
                ai: toggleAI.checked,
            }),
        });
        const data = await resp.json();

        if (!data.success) {
            showToast('启动失败');
            return;
        }

        currentTaskId = data.task_id;
        connectSSE(currentTaskId);

    } catch (e) {
        showToast('请求失败: ' + e.message);
        btnDownload.disabled = false;
        btnDownload.textContent = '📥 下载视频';
    }
}

function connectSSE(taskId) {
    if (eventSource) eventSource.close();

    const steps = new Set();
    eventSource = new EventSource(`/api/stream/${taskId}`);

    eventSource.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        updateProgress(data);
    });

    eventSource.addEventListener('video_ready', (e) => {
        const data = JSON.parse(e.data);
        showVideoReady(data);
    });

    eventSource.addEventListener('subtitle_ready', (e) => {
        const data = JSON.parse(e.data);
        showSubtitleReady(data);
    });

    eventSource.addEventListener('ai_ready', (e) => {
        const data = JSON.parse(e.data);
        showAIReady(data);
    });

    eventSource.addEventListener('complete', () => {
        finishProcess();
    });

    eventSource.addEventListener('error', (e) => {
        const data = JSON.parse(e.data);
        showToast(data.message || '处理失败');
        finishProcess();
    });

    eventSource.onerror = () => {
        // SSE连接中断，可能任务已完成
        if (eventSource.readyState === EventSource.CLOSED) {
            finishProcess();
        }
    };
}

function updateProgress(data) {
    const pct = data.percent || 0;
    $('#progressFill').style.width = `${pct}%`;
    $('#progressPercent').textContent = `${pct}%`;
    $('#progressMsg').textContent = data.message;

    // 步骤指示器
    const stepMap = {
        'parse': { label: '🔍 解析', icon: 'parse' },
        'download': { label: '📥 下载', icon: 'download' },
        'subtitle': { label: '📝 字幕', icon: 'subtitle' },
        'ai': { label: '✨ AI分析', icon: 'ai' },
        'done': { label: '✅ 完成', icon: 'done' },
    };

    const stepInfo = stepMap[data.step];
    if (stepInfo && !steps.has(data.step)) {
        // 标记之前的步骤为完成
        const stepOrder = ['parse', 'download', 'subtitle', 'ai', 'done'];
        const currentIdx = stepOrder.indexOf(data.step);

        const badgesHtml = stepOrder.slice(0, currentIdx + 1).map((s, i) => {
            const info = stepMap[s];
            const cls = i < currentIdx ? 'done' : 'active';
            return `<span class="step-badge ${cls}">${info.label}</span>`;
        }).join(' → ');

        $('#progressSteps').innerHTML = badgesHtml;

        if (data.step === 'done') {
            // 全部标记完成
            $('#progressSteps').innerHTML = stepOrder.slice(0, -1).map(s => {
                const info = stepMap[s];
                return `<span class="step-badge done">${info.label}</span>`;
            }).join(' → ') + '<span class="step-badge done">✅ 完成</span>';
        }
    }
}

function showVideoReady(data) {
    videoSection.classList.remove('hidden');
    const player = $('#videoPlayer');
    player.src = data.url;
    player.load();

    $('#videoInfo').innerHTML = `
        <strong>${data.filename}</strong> · ${data.size_display} · ${data.quality}
        <br><a href="${data.url}" download style="color:var(--primary);font-size:0.85rem;">💾 点击下载到本地</a>
    `;

    videoSection.scrollIntoView({ behavior: 'smooth' });
}

function showSubtitleReady(data) {
    subtitleSection.classList.remove('hidden');
    const sourceLabels = { api: 'API数据', ocr: 'OCR识别', speech: '语音识别', none: '无' };
    $('#subtitleSource').textContent = `来源: ${sourceLabels[data.source] || data.source}`;
    $('#subtitleContent').textContent = data.text || '(无内容)';
}

function showAIReady(data) {
    aiSection.classList.remove('hidden');
    $('#aiLoading').classList.add('hidden');

    if (data.error) {
        $('#aiContent').innerHTML = `<p style="color:var(--danger);">${data.analysis}</p>`;
        $('#aiExportBtns').classList.add('hidden');
    } else {
        const html = renderAIReport(data.analysis);
        const markdownText = data.analysis || '';
        $('#aiContent').innerHTML = html || simpleMarkdown(markdownText);
        // Store raw markdown for export
        $('#aiContent').dataset.raw = markdownText;
        $('#aiExportBtns').classList.remove('hidden');
    }

    aiSection.scrollIntoView({ behavior: 'smooth' });
}

async function doExport(format) {
    const el = $('#aiContent');
    let html = el ? el.innerHTML : '';
    // Fallback: render raw markdown if DOM is empty
    if ((!html || html.length < 50) && el && el.dataset.raw) {
        html = renderAIReport(el.dataset.raw) || simpleMarkdown(el.dataset.raw);
    }
    if (!html || html.length < 50) { showToast('没有可导出的分析内容'); return; }
    const title = (videoData?.info?.desc || '分析报告').substring(0, 30);
    const endpoint = format === 'pdf' ? '/api/export/pdf' : '/api/export/image';
    const ext = format === 'pdf' ? '.pdf' : '.png';
    try {
        showToast('正在生成' + (format === 'pdf' ? 'PDF' : '图片') + '...');
        const resp = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({html: html, title: title}),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.error); }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = title + ext; a.click();
        URL.revokeObjectURL(url);
    } catch(e) { showToast('导出失败: ' + e.message); }
}

function exportAnalysisPDF() { doExport('pdf'); }
function exportAnalysisImage() { doExport('img'); }

async function exportHistoryRaw(format) {
    const el = $('#analysisDetailContent');
    let html = '';
    if (el) {
        html = el.querySelector('.ai-card') ? el.innerHTML : (el.querySelector('div') ? el.innerHTML : '');
        // Fallback: render from stored raw markdown
        if ((!html || html.length < 50) && el.dataset.raw) {
            html = renderAIReport(el.dataset.raw) || simpleMarkdown(el.dataset.raw);
        }
    }
    if (!html || html.length < 50) { showToast('没有可导出的分析内容'); return; }
    const title = el.dataset.title || '分析报告';
    const endpoint = format === 'pdf' ? '/api/export/pdf' : '/api/export/image';
    const ext = format === 'pdf' ? '.pdf' : '.png';
    try {
        showToast('正在生成' + (format === 'pdf' ? 'PDF' : '图片') + '...');
        const resp = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({html: html, title: title}),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.error); }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = title + ext; a.click();
        URL.revokeObjectURL(url);
    } catch(e) { showToast('导出失败: ' + e.message); }
}

function finishProcess() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    btnDownload.disabled = false;
    btnDownload.textContent = '📥 下载视频';
    currentTaskId = null;
}

// ==================== 历史记录弹窗 ====================
let historyTab = 'downloads';

async function openHistory() {
    historyModal.classList.remove('hidden');
    switchHistoryTab('downloads');
}

function switchHistoryTab(tab) {
    historyTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    if (tab === 'downloads') {
        document.querySelector('.tab-btn:nth-child(1)').classList.add('active');
        $('#analysisDetail').classList.add('hidden');
        $('#historyList').classList.remove('hidden');
        loadHistoryDownloads();
    } else {
        document.querySelector('.tab-btn:nth-child(2)').classList.add('active');
        $('#analysisDetail').classList.add('hidden');
        $('#historyList').classList.remove('hidden');
        loadHistoryAnalyses();
    }
}

async function loadHistoryDownloads() {
    try {
        const resp = await fetch('/api/videos');
        const data = await resp.json();
        const list = $('#historyList');

        if (data.videos.length === 0) {
            list.innerHTML = '<p style="color:var(--text-dim);padding:24px;text-align:center;">暂无下载记录</p>';
        } else {
            list.innerHTML = data.videos.map(v => `
                <div class="history-item">
                    <span class="h-name" title="${v.filename}">${v.filename}</span>
                    <span class="h-size">${v.size_display}</span>
                    <a href="${v.url}" download class="btn btn-sm">💾</a>
                    <button class="btn btn-sm" onclick="playVideo('${v.url}')">▶</button>
                </div>
            `).join('');
        }
    } catch {
        showToast('获取下载记录失败');
    }
}

async function loadHistoryAnalyses() {
    try {
        const resp = await fetch('/api/analyses');
        const data = await resp.json();
        const list = $('#historyList');

        if (data.analyses.length === 0) {
            list.innerHTML = '<p style="color:var(--text-dim);padding:24px;text-align:center;">暂无分析报告<br><br>下载视频时勾选 <b>AI分析</b> 即可生成</p>';
        } else {
            list.innerHTML = data.analyses.map(a => {
                const dt = a.created_at ? new Date(a.created_at * 1000).toLocaleDateString('zh-CN') : '未知';
                return `
                <div class="history-item analysis-item" style="cursor:pointer;" onclick="viewAnalysis('${a.file}')">
                    <div style="flex:1;min-width:0;">
                        <div class="h-name">${a.desc || a.filename}</div>
                        <div style="font-size:0.78rem;color:var(--text-dim);">👤 ${a.author} · ${dt} · ${a.model}</div>
                    </div>
                    <span class="analysis-preview-tag">查看 →</span>
                </div>`;
            }).join('');
        }
    } catch {
        showToast('获取分析报告失败');
    }
}

async function viewAnalysis(file) {
    try {
        const resp = await fetch('/api/analyses/' + file);
        const data = await resp.json();

        $('#historyList').classList.add('hidden');
        const detail = $('#analysisDetail');
        detail.classList.remove('hidden');

        const dt = data.created_at ? new Date(data.created_at * 1000).toLocaleString('zh-CN') : '';
        const rawText = data.analysis || '';
        const html = `
            <div style="margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid var(--card-border);">
                <div style="font-size:1.1rem;font-weight:700;color:var(--primary);">${escHTML(data.desc || data.filename)}</div>
                <div style="font-size:0.82rem;color:var(--text-dim);margin-top:4px;">
                    👤 ${escHTML(data.author || '未知')} · ⏱ ${data.duration || 0}秒 · 🤖 ${data.model || ''} · ${dt}
                </div>
                <div style="margin-top:10px;display:flex;gap:8px;">
                    <button class="btn btn-sm btn-export-pdf">🖨️ 导出 PDF</button>
                    <button class="btn btn-sm btn-export-img">🖼️ 导出图片</button>
                </div>
            </div>
            ${renderAIReport(rawText)}
        `;
        $('#analysisDetailContent').innerHTML = html;
        // Store raw text on the export buttons' parent for retrieval
        $('#analysisDetailContent').dataset.raw = rawText;
        $('#analysisDetailContent').dataset.title = (data.desc || data.filename || '分析报告').substring(0, 30);
    } catch {
        showToast('加载分析详情失败');
    }
}


function closeHistory() {
    historyModal.classList.add('hidden');
}

function playVideo(url) {
    closeHistory();
    videoSection.classList.remove('hidden');
    $('#videoPlayer').src = url;
    $('#videoInfo').textContent = '';
    videoSection.scrollIntoView({ behavior: 'smooth' });
}

// ==================== 工具函数 ====================
function showError(msg) {
    parseError.textContent = msg;
    parseError.classList.remove('hidden');
}

function hideError() {
    parseError.classList.add('hidden');
}

function resetAll() {
    hideError();
    videoCard.classList.add('hidden');
    progressSection.classList.add('hidden');
    videoSection.classList.add('hidden');
    subtitleSection.classList.add('hidden');
    aiSection.classList.add('hidden');
    $('#aiLoading').classList.add('hidden');
    videoData = null;
    selectedQuality = 0;
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    btnDownload.disabled = false;
    btnDownload.textContent = '📥 下载视频';
}

let toastTimer;
function showToast(msg) {
    const toast = $('#toast');
    toast.textContent = msg;
    toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), 3000);
}

function formatNumber(n) {
    if (!n) return '0';
    if (n >= 10000) return (n / 10000).toFixed(1) + '万';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return n.toString();
}

// ==================== 简易Markdown渲染 ====================
function simpleMarkdown(text) {
    if (!text) return '';
    let html = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^[\*\-] (.+)$/gm, '<li>$1</li>')
        .replace(/^---+$/gm, '<hr>')
        .replace(/\n{2,}/g, '</p><p>')
        .replace(/\n/g, '<br>');

    const lines = html.split(/\n/);
    html = lines.map(line => {
        if (/^<(h[1-4]|li|hr|p|ul|ol|table)/.test(line.trim())) return line;
        return `<p>${line}</p>`;
    }).join('\n');

    return html;
}

// ==================== AI 结构化渲染 (增强卡片样式) ====================
const AI_COLORS = ['#6c5ce7', '#ff6b9d', '#4ecdc4', '#ffa502', '#00d68f', '#45aaf2'];
const AI_ICONS  = ['🎯', '🔥', '✍️', '👁️', '📊', '🧬'];
const AI_GRADIENTS = [
    'rgba(108,92,231,0.12)', 'rgba(255,107,157,0.12)', 'rgba(78,205,196,0.12)',
    'rgba(255,165,2,0.12)',  'rgba(0,214,143,0.12)',  'rgba(69,170,242,0.12)'
];

function renderAIReport(rawText) {
    if (!rawText) return '';
    const sections = parseAISections(rawText);
    if (!sections.length) return simpleMarkdown(rawText);

    let html = '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;max-height:65vh;overflow-y:auto;padding-right:6px;scrollbar-width:thin;scrollbar-color:#2a2a3a #111119;">';
    sections.forEach(function(sec, i) {
        var c = AI_COLORS[i % AI_COLORS.length];
        var grad = AI_GRADIENTS[i % AI_GRADIENTS.length];
        var icon = AI_ICONS[i % AI_ICONS.length];
        html += '<div style="background:linear-gradient(135deg,' + grad + ',transparent);border-left:3px solid ' + c + ';border-radius:0 10px 10px 0;padding:16px 18px;margin-bottom:16px;border-top:1px solid #1e1e2e;border-right:1px solid #1e1e2e;border-bottom:1px solid #1e1e2e;transition:transform 0.15s,box-shadow 0.15s;">';
        html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">';
        html += '<span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:8px;background:' + c + '22;font-size:1rem;">' + icon + '</span>';
        html += '<span style="font-size:1.05rem;font-weight:700;color:' + c + ';letter-spacing:0.01em;">' + escHTML(sec.title) + '</span>';
        html += '</div>';
        html += '<div style="color:#b8b4c4;font-size:0.92rem;line-height:1.85;">' + renderAIBody(sec.body, c) + '</div>';
        html += '</div>';
    });
    html += '</div>';
    return html;
}

function parseAISections(text) {
    var sections = [];
    var parts = text.split(/\n(?=#{2,4}\s+\d+[\.\、\s])/g);
    parts.forEach(function(part) {
        part = part.trim();
        if (!part) return;
        var m = part.match(/^#{2,4}\s+(.+?)\n([\s\S]*)/);
        if (m) sections.push({ title: escHTML(m[1].trim()), body: m[2].trim() });
    });
    return sections;
}

function renderAIBody(body, c) {
    return escHTML(body)
        .replace(/^#{1,4}\s+(.+?)$/gm, function(_, t) {
            return t ? '<br><strong style="color:' + c + ';opacity:0.9;font-size:0.95rem;">▸ ' + t + '</strong><br>' : '';
        })
        .replace(/\b(\d+)\s*\/\s*10\b/g, '<span style="display:inline-block;background:' + c + '22;color:' + c + ';padding:2px 12px;border-radius:14px;font-weight:700;font-size:0.9rem;margin:0 3px;border:1px solid ' + c + '44;">$1<span style="opacity:0.55">/10</span></span>')
        .replace(/\*\*(.+?)\*\*/g, '<strong style="color:' + c + ';background:' + c + '15;padding:1px 5px;border-radius:4px;">$1</strong>')
        .replace(/^[\*\-][ \t]+(.+)$/gm, '<li style="margin-left:16px;margin-bottom:6px;">$1</li>')
        .replace(/\n{2,}/g, '<br><br>')
        .replace(/\n/g, '<br>');
}

function escHTML(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ==================== 弹窗外部点击关闭 & 导出按钮 ====================
historyModal.addEventListener('click', (e) => {
    if (e.target === historyModal) closeHistory();
    if (e.target.classList.contains('btn-export-pdf')) exportHistoryRaw('pdf');
    if (e.target.classList.contains('btn-export-img')) exportHistoryRaw('img');
});

// ==================== 初始化 ====================
console.log('🎵 抖音视频下载分析 Web 应用已就绪');
