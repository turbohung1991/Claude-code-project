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

if (btnParse) {
    btnParse.textContent = '解析';
}
const parseError = $('#parseError');
const videoCard = $('#videoCard');
const videoSection = $('#videoSection');
const subtitleSection = $('#subtitleSection');
const historyModal = $('#historyModal');

// Tab elements
const tabBtns = document.querySelectorAll('.ftab-btn');

let currentTaskId = null;
let selectedQuality = 0;
let videoData = null;
let eventSource = null;
let currentTab = 'tab-download';

// ==================== Tab 切换 ====================
tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        if (tab === currentTab) return;
        currentTab = tab;

        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        document.querySelectorAll('.ftab-panel').forEach(p => p.classList.add('hidden'));
        const panel = document.getElementById(tab);
        if (panel) panel.classList.remove('hidden');
    });
});

// ==================== 按钮事件 ====================
btnParse.addEventListener('click', parseUrl);
urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') parseUrl();
});

btnPaste.addEventListener('click', async () => {
    try {
        const text = await navigator.clipboard.readText();
        if (text && text.trim()) {
            urlInput.value = text.trim();
            parseUrl();
            return;
        }
    } catch {}
    urlInput.focus();
    showToast('请使用 Ctrl+V / Cmd+V 粘贴链接');
});

btnClear.addEventListener('click', () => {
    urlInput.value = '';
    resetAll();
});

btnHistory.addEventListener('click', openHistory);

btnDownload.addEventListener('click', startProcess);

// Strategy & comment button listeners (dynamic, attach when video card shows)
document.addEventListener('click', (e) => {
    if (e.target.id === 'btnRunStrategy') runStrategyAnalysis();
    if (e.target.id === 'btnFetchComments') fetchAndAnalyzeComments();
});

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
        btnParse.textContent = '解析';
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

    videoSection.classList.add('hidden');
    subtitleSection.classList.add('hidden');

    const downloadProgress = $('#downloadProgress');
    downloadProgress.classList.remove('hidden');
    $('#progressFill').style.width = '0%';
    $('#progressPercent').textContent = '0%';
    $('#progressMsg').textContent = '准备中...';
    $('#progressSteps').innerHTML = '';

    btnDownload.disabled = true;
    btnDownload.textContent = '...';

    try {
        const resp = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: urlInput.value.trim(),
                quality_index: selectedQuality,
                ai: false,
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
        'parse': { label: '解析', icon: 'parse' },
        'download': { label: '📥 下载', icon: 'download' },
        'subtitle': { label: '📝 字幕', icon: 'subtitle' },
        'ai': { label: '🧠 AI分析', icon: 'ai' },
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

function stripScrollStyles(html) {
    // Remove max-height and overflow from the outer scroll wrapper so export captures full content
    return html.replace(/max-height:\s*65vh\s*;?/gi, '')
               .replace(/overflow-y:\s*auto\s*;?/gi, '')
               .replace(/overflow:\s*auto\s*;?/gi, '');
}

async function doExport(format) {
    const el = $('#aiContent');
    let html = el ? el.innerHTML : '';
    if ((!html || html.length < 50) && el && el.dataset.raw) {
        html = renderAIReport(el.dataset.raw) || simpleMarkdown(el.dataset.raw);
    }
    if (!html || html.length < 50) { showToast('没有可导出的分析内容'); return; }
    html = stripScrollStyles(html);
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
    html = stripScrollStyles(html);
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
    $('#downloadProgress').classList.add('hidden');
    currentTaskId = null;
}

function finishStrategy() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    if ($('#btnRunStrategy')) $('#btnRunStrategy').disabled = false;
    if ($('#btnRunStrategy')) $('#btnRunStrategy').textContent = '🧠 开始 AI 策略分析';
    currentTaskId = null;
}

// ==================== 策略分析（Tab 3） ====================
async function runStrategyAnalysis() {
    if (!videoData || !videoData.video_id) {
        showToast('请先解析链接');
        return;
    }

    const loading = $('#strategyLoading');
    const content = $('#strategyContent');
    const btn = $('#btnRunStrategy');

    btn.disabled = true;
    btn.textContent = '...';
    loading.classList.remove('hidden');
    content.innerHTML = '';

    try {
        const resp = await fetch('/api/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: urlInput.value.trim(),
                quality_index: 0,
                ai: true,
            }),
        });
        const data = await resp.json();
        if (!data.success) { showToast('启动失败'); btn.disabled = false; btn.textContent = '🧠 开始 AI 策略分析'; loading.classList.add('hidden'); return; }

        currentTaskId = data.task_id;
        const es = new EventSource('/api/stream/' + data.task_id);
        eventSource = es;

        es.addEventListener('ai_ready', (e) => {
            const d = JSON.parse(e.data);
            loading.classList.add('hidden');
            if (d.error) {
                content.innerHTML = '<p style="color:var(--danger);">' + (d.analysis || '分析失败') + '</p>';
            } else {
                const html = renderAIReport(d.analysis);
                const rawText = d.analysis || '';
                content.innerHTML = (html || simpleMarkdown(rawText)) + `
                <div style="margin-top:16px;padding-top:14px;border-top:1px solid #2a2a3a;display:flex;gap:10px;">
                    <button class="btn btn-sm" onclick="exportStrategyReport('pdf')">🖨️ 导出 PDF</button>
                    <button class="btn btn-sm" onclick="exportStrategyReport('img')">🖼️ 导出图片</button>
                </div>`;
                content.querySelector('.markdown-body')?.style?.setProperty('max-height','none');
            }
            es.close();
            finishStrategy();
        });

        es.addEventListener('progress', (e) => {
            const d = JSON.parse(e.data);
            if (d.step === 'ai') {
                loading.querySelector('span') && (loading.querySelector('span').textContent = 'AI 正在深度分析中...');
            }
        });

        es.addEventListener('error', (e) => {
            try { const d = JSON.parse(e.data); showToast(d.message || '分析失败'); } catch(_) {}
            loading.classList.add('hidden');
            finishStrategy();
            es.close();
        });

        es.onerror = () => { if (es.readyState === EventSource.CLOSED) { loading.classList.add('hidden'); finishStrategy(); } };

    } catch (e) {
        showToast('请求失败: ' + e.message);
        btn.disabled = false;
        btn.textContent = '🧠 开始 AI 策略分析';
        loading.classList.add('hidden');
    }
}

function exportStrategyReport(format) {
    const el = $('#strategyContent');
    let html = el?.innerHTML || '';
    if (!html || html.length < 50) { showToast('没有可导出内容'); return; }
    const title = (videoData?.info?.desc || '分析报告').substring(0, 30);
    doExportRaw(format, html, title);
}

async function doExportRaw(format, html, title) {
    const endpoint = format === 'pdf' ? '/api/export/pdf' : '/api/export/image';
    const ext = format === 'pdf' ? '.pdf' : '.png';
    try {
        showToast('正在生成...');
        const resp = await fetch(endpoint, {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({html, title}),
        });
        if (!resp.ok) { const e = await resp.json(); throw new Error(e.error); }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = title + ext; a.click();
        URL.revokeObjectURL(url);
    } catch(e) { showToast('导出失败: ' + e.message); }
}

// ==================== 评论分析（Tab 2） ====================
let _commentPollTimer = null;

async function fetchAndAnalyzeComments() {
    if (!videoData || !videoData.video_id) {
        showToast('请先解析链接');
        return;
    }

    const loading = $('#commentLoading');
    const result = $('#commentResult');
    const btn = $('#btnFetchComments');

    btn.disabled = true;
    btn.textContent = '...';
    loading.classList.remove('hidden');
    result.innerHTML = '';

    try {
        await fetch('/api/comments/fetch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ video_id: videoData.video_id }),
        });
        pollCommentResult(videoData.video_id);
    } catch (e) {
        showToast('请求失败: ' + e.message);
        btn.disabled = false;
        btn.textContent = '🔍 抓取评论并分析';
        loading.classList.add('hidden');
    }
}

async function pollCommentResult(videoId) {
    const maxAttempts = 240;
    let attempts = 0;
    const loading = $('#commentLoading');
    const result = $('#commentResult');
    const btn = $('#btnFetchComments');

    const poll = async () => {
        if (attempts >= maxAttempts) {
            loading.classList.add('hidden');
            result.innerHTML = '<p style="color:var(--danger);">评论分析超时，请重试</p>';
            btn.disabled = false;
            btn.textContent = '🔍 抓取评论并分析';
            return;
        }
        attempts++;
        try {
            const resp = await fetch('/api/comments/result/' + videoId);
            const data = await resp.json();
            if (data.status !== 'fetching') {
                loading.classList.add('hidden');
                renderCommentOnMain(data);
                btn.disabled = false;
                btn.textContent = '🔄 重新抓取';
                return;
            }
        } catch (e) {}
        _commentPollTimer = setTimeout(poll, 2000);
    };
    poll();
}

function renderCommentOnMain(data) {
    const result = $('#commentResult');
    const analysis = data.analysis || {};
    const totalFetched = data.total_fetched || 0;
    const C = ['#6c5ce7', '#ff6b9d', '#4ecdc4', '#ffa502', '#00d68f', '#45aaf2'];

    // Sentiment
    let sHtml = '';
    if (analysis.sentiment) {
        const s = analysis.sentiment;
        const items = [
            { label: '正面', pct: s.positive, count: s.positive_count||0, color: '#00d68f', icon: '😊' },
            { label: '中性', pct: s.neutral, count: s.neutral_count||0, color: '#ffa502', icon: '😐' },
            { label: '负面', pct: s.negative, count: s.negative_count||0, color: '#ff6b6b', icon: '😟' },
        ];
        sHtml = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px;">' +
            items.map(it => (
                '<div style="text-align:center;padding:16px 10px;border-radius:12px;background:linear-gradient(135deg,'+it.color+'18,transparent);border:1px solid '+it.color+'33;">'+
                '<div style="font-size:2rem;">'+it.icon+'</div>'+
                '<div style="font-size:1.4rem;font-weight:700;color:'+it.color+';">'+it.pct+'%</div>'+
                '<div style="font-size:0.78rem;color:var(--text-dim);">'+it.label+' ('+it.count+'条)</div></div>'
            )).join('') + '</div>';
    }

    // Word cloud
    let cloudHtml = '';
    if (analysis.keywords && analysis.keywords.length > 0) {
        const maxCount = analysis.keywords[0].count || 1;
        const minCount = analysis.keywords[analysis.keywords.length-1].count || 1;
        const palette = ['#a78bfa','#e879f9','#f472b6','#fb7185','#fbbf24','#34d399','#38bdf8','#818cf8','#c084fc','#fb923c','#4ade80'];
        const rots = [-6,-2,0,0,3,-4,1,-5,-1,4,0,-3,2,5,-7];
        cloudHtml = '<div style="background:radial-gradient(ellipse at center,rgba(108,92,231,0.08),rgba(15,15,19,0.3));border-left:3px solid #6c5ce7;border-radius:0 10px 10px 0;padding:22px 20px;margin-bottom:18px;border-top:1px solid #1e1e2e;border-right:1px solid #1e1e2e;border-bottom:1px solid #1e1e2e;">'+
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:18px;">'+
            '<span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:8px;background:rgba(108,92,231,0.13);font-size:1rem;">☁️</span>'+
            '<span style="font-size:1.05rem;font-weight:700;color:#6c5ce7;">评论词云</span></div>'+
            '<div style="display:flex;flex-wrap:wrap;gap:10px 8px;align-items:center;justify-content:center;padding:16px 4px;min-height:120px;line-height:1.4;">'+
            analysis.keywords.map((k,i) => {
                const ratio = (k.count - minCount) / (maxCount - minCount || 1);
                const size = 0.75 + ratio * 1.45;
                const weight = ratio>0.6?700:ratio>0.25?600:400;
                const color = ratio>0.5?'#f472b6':ratio>0.3?'#a78bfa':palette[i%palette.length];
                const rot = rots[i%rots.length];
                const bgAlpha = 0.08+ratio*0.14;
                const glow = ratio>0.5?'0 0 16px '+color+'22, ':'';
                return '<span style="display:inline-block;padding:'+(4+ratio*6).toFixed(0)+'px '+(12+ratio*14).toFixed(0)+'px;border-radius:'+(16+ratio*10).toFixed(0)+'px;font-size:'+size.toFixed(2)+'rem;font-weight:'+weight+';color:'+color+';background:'+color+Math.round(bgAlpha*255).toString(16).padStart(2,'0')+';border:1px solid '+color+'33;transform:rotate('+rot+'deg);box-shadow:'+glow+'0 1px 4px rgba(0,0,0,0.2);transition:all 0.25s cubic-bezier(0.4,0,0.2,1);cursor:default;white-space:nowrap;">'+escHTML(k.word)+'</span>';
            }).join('')+'</div></div>';
    }

    // Summary
    let sumHtml = '';
    if (analysis.summary) {
        sumHtml = '<div style="background:linear-gradient(135deg,rgba(255,107,157,0.06),transparent);border-left:3px solid #ff6b9d;border-radius:0 10px 10px 0;padding:18px;margin-bottom:8px;border-top:1px solid #1e1e2e;border-right:1px solid #1e1e2e;border-bottom:1px solid #1e1e2e;">'+
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">'+
            '<span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:8px;background:rgba(255,107,157,0.13);font-size:1rem;">🧠</span>'+
            '<span style="font-size:1.05rem;font-weight:700;color:#ff6b9d;">AI 综合总结</span></div>'+
            '<div style="color:#b8b4c4;font-size:0.9rem;line-height:1.85;">'+
            analysis.summary
                .replace(/\*\*(.+?)\*\*/g,'<strong style="color:#ff6b9d;background:rgba(255,107,157,0.12);padding:1px 5px;border-radius:4px;">$1</strong>')
                .replace(/^### (.+)$/gm,'<h3 style="font-size:0.95rem;color:#4ecdc4;margin:12px 0 6px;">$1</h3>')
                .replace(/^## (.+)$/gm,'<h2 style="font-size:1rem;color:#ff6b9d;margin:14px 0 6px;padding-bottom:4px;border-bottom:1px solid #2a2a3a;">$1</h2>')
                .replace(/^[-*] (.+)$/gm,'<li style="margin-left:16px;margin-bottom:6px;color:#b8b4c4;">$1</li>')
                .replace(/\n/g,'<br>')+'</div></div>';
    }

    result.innerHTML = `
        <div class="comment-panel" style="margin-top:12px;padding-top:12px;border-top:1px solid var(--card-border);">
            <h4 style="font-size:0.95rem;color:var(--text);margin-bottom:14px;">💬 评论分析 <span style="color:var(--text-dim);font-weight:400;">(${totalFetched}条)</span></h4>
            ${sHtml}${cloudHtml}${sumHtml}
            <div style="margin-top:16px;padding-top:14px;border-top:1px solid #2a2a3a;display:flex;gap:10px;flex-wrap:wrap;">
                <button class="btn btn-sm" onclick="exportMainComment('pdf')">🖨 导出 PDF</button>
                <button class="btn btn-sm" onclick="exportMainComment('img')">🖼 导出图片</button>
                <button class="btn btn-sm" onclick="downloadMainCommentCSV()">📊 导出评论数据</button>
            </div>
        </div>
    `;
}

function exportMainComment(format) {
    const content = $('#commentResult').innerHTML;
    const title = (videoData?.info?.desc || '评论分析').substring(0,30);
    doExportRaw(format, content, title);
}

function downloadMainCommentCSV() {
    if (!videoData || !videoData.video_id) { showToast('未找到视频ID'); return; }
    const a = document.createElement('a');
    a.href = '/api/comments/export-data/' + videoData.video_id;
    a.download = 'comments_' + videoData.video_id + '.csv';
    a.click();
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
                    <button class="btn btn-sm" onclick="deleteVideo('${v.filename}', this)" style="color:#ff6b6b;">✕</button>
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
                <div class="history-item analysis-item" style="cursor:pointer;">
                    <div style="flex:1;min-width:0;" onclick="viewAnalysis('${a.file}')">
                        <div class="h-name">${a.desc || a.filename}</div>
                        <div style="font-size:0.78rem;color:var(--text-dim);">👤 ${a.author} · ${dt} · ${a.model}</div>
                    </div>
                    <span class="analysis-preview-tag" onclick="viewAnalysis('${a.file}')">查看 →</span>
                    <button class="btn btn-sm" onclick="event.stopPropagation();deleteAnalysis('${a.file}', this)" style="color:#ff6b6b;margin-left:8px;">✕</button>
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

async function deleteAnalysis(filename, btn) {
    if (!confirm(`确定删除这份分析报告吗？`)) return;
    try {
        const resp = await fetch('/api/analyses/' + encodeURIComponent(filename), { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            btn.closest('.history-item').remove();
            showToast('已删除');
        } else {
            showToast('删除失败: ' + (data.error || '未知错误'));
        }
    } catch(e) {
        showToast('删除失败: ' + e.message);
    }
}

async function deleteVideo(filename, btn) {
    if (!confirm(`确定删除「${filename}」吗？`)) return;
    try {
        const resp = await fetch('/api/videos/' + encodeURIComponent(filename), { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            btn.closest('.history-item').remove();
            showToast('已删除');
        } else {
            showToast('删除失败: ' + (data.error || '未知错误'));
        }
    } catch(e) {
        showToast('删除失败: ' + e.message);
    }
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
    videoSection.classList.add('hidden');
    subtitleSection.classList.add('hidden');
    // Reset tabs
    document.querySelectorAll('.ftab-panel').forEach(p => {
        if (p.id !== 'tab-download') p.classList.add('hidden');
        else p.classList.remove('hidden');
    });
    tabBtns.forEach(b => {
        b.classList.remove('active');
        if (b.dataset.tab === 'tab-download') b.classList.add('active');
    });
    currentTab = 'tab-download';
    $('#downloadProgress').classList.add('hidden');
    $('#btnFetchComments').disabled = false;
    $('#btnFetchComments').textContent = '🔍 抓取评论并分析';
    $('#commentResult').innerHTML = '';
    $('#commentLoading').classList.add('hidden');
    $('#strategyContent').innerHTML = '';
    $('#strategyLoading').classList.add('hidden');
    if ($('#btnRunStrategy')) { $('#btnRunStrategy').disabled = false; $('#btnRunStrategy').textContent = '🧠 开始 AI 策略分析'; }
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
    // Try structured sections first
    var sections = parseAISections(rawText);
    if (sections.length >= 2) {
        return renderCardSections(sections);
    }
    // Fallback to rich markdown → HTML (always produces good output)
    return richMarkdown(rawText);
}

function renderCardSections(sections) {
    var html = '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;max-height:65vh;overflow-y:auto;padding-right:6px;scrollbar-width:thin;scrollbar-color:#2a2a3a #111119;">';
    sections.forEach(function(sec, i) {
        var c = AI_COLORS[i % AI_COLORS.length];
        var grad = AI_GRADIENTS[i % AI_GRADIENTS.length];
        var icon = AI_ICONS[i % AI_ICONS.length];
        html += '<div style="background:linear-gradient(135deg,' + grad + ',transparent);border-left:3px solid ' + c + ';border-radius:0 10px 10px 0;padding:16px 18px;margin-bottom:16px;border-top:1px solid #1e1e2e;border-right:1px solid #1e1e2e;border-bottom:1px solid #1e1e2e;">';
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

// Rich markdown fallback — works with any markdown, always produces styled output
function richMarkdown(md) {
    if (!md) return '';
    var lines = md.trim().split('\n');
    var html = [];
    var inList = false;
    var colorIdx = 0;

    for (var i = 0; i < lines.length; i++) {
        var s = lines[i].trim();
        if (!s) {
            if (inList) { html.push('</ul>'); inList = false; }
            html.push('<div style="height:6px;"></div>');
            continue;
        }
        // H2 → pink header with bottom border
        if (/^##\s/.test(s)) {
            if (inList) { html.push('</ul>'); inList = false; }
            var h2 = s.replace(/^##\s+/, '');
            colorIdx = Math.floor((colorIdx + 1) % AI_COLORS.length);
            var c = AI_COLORS[colorIdx];
            html.push('<h2 style="font-size:1.1rem;color:' + c + ';margin:18px 0 8px;padding-bottom:5px;border-bottom:1px solid #2a2a3a;">' + escHTML(h2) + '</h2>');
            continue;
        }
        // H3 → cyan sub-header
        if (/^###\s/.test(s)) {
            if (inList) { html.push('</ul>'); inList = false; }
            var h3 = s.replace(/^###\s+/, '');
            html.push('<h3 style="font-size:0.95rem;color:#4ecdc4;margin:12px 0 6px;">' + escHTML(h3) + '</h3>');
            continue;
        }
        // Bullet list
        if (/^[-*]\s/.test(s)) {
            if (!inList) { html.push('<ul style="margin:4px 0;padding-left:18px;">'); inList = true; }
            var txt = s.replace(/^[-*]\s+/, '');
            txt = txt.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#fff;background:rgba(108,92,231,0.2);padding:1px 5px;border-radius:3px;">$1</strong>');
            html.push('<li style="margin:3px 0;line-height:1.7;color:#b8b4c4;font-size:0.9rem;">' + txt + '</li>');
            continue;
        }
        // Numbered → card
        if (/^\d+[\.\)]\s/.test(s)) {
            if (inList) { html.push('</ul>'); inList = false; }
            var ntxt = s.replace(/^\d+[\.\)]\s+/, '');
            ntxt = ntxt.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#fff;background:rgba(108,92,231,0.2);padding:1px 5px;border-radius:3px;">$1</strong>');
            html.push('<div style="margin:5px 0;padding:8px 14px;background:#14101e;border-radius:6px;border-left:3px solid #6c5ce7;line-height:1.7;font-size:0.9rem;color:#b8b4c4;">' + ntxt + '</div>');
            continue;
        }
        // Regular paragraph
        if (inList) { html.push('</ul>'); inList = false; }
        var p = s.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#fff;background:rgba(108,92,231,0.2);padding:1px 5px;border-radius:3px;">$1</strong>');
        // Highlight scores like 8/10
        p = p.replace(/\b(\d+)\s*\/\s*10\b/g, '<span style="display:inline-block;background:rgba(108,92,231,0.2);color:#a78bfa;padding:1px 10px;border-radius:12px;font-weight:700;font-size:0.85rem;margin:0 2px;">$1<span style="opacity:0.5">/10</span></span>');
        html.push('<p style="margin:5px 0;line-height:1.8;color:#b8b4c4;font-size:0.9rem;">' + p + '</p>');
    }
    if (inList) html.push('</ul>');

    return '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;max-height:65vh;overflow-y:auto;padding-right:6px;scrollbar-width:thin;scrollbar-color:#2a2a3a #111119;">' + html.join('\n') + '</div>';
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
