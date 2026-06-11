/**
 * Push daily article to GitHub Pages site
 *
 * Usage: node push_article.js < input.json
 * Input JSON format:
 * {
 *   "date": "2026-06-06",
 *   "title": "English title",
 *   "titleCn": "中文标题",
 *   "pairs": [["en sentence 1", "zh sentence 1"], ["en sentence 2", "zh sentence 2"]],
 *   "sourceUrl": "https://www.amruta.org/..."
 * }
 */

const https = require('https');
const fs = require('fs');
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;
const OWNER = 'wherejiahe-bot';
const REPO = 'amruta-daily-archive';
const BRANCH = 'main';

function githubGet(path) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.github.com',
      path: `/repos/${OWNER}/${REPO}/contents/${path}?ref=${BRANCH}`,
      method: 'GET',
      headers: {
        'Authorization': `token ${GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'nodejs'
      }
    };
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        if (res.statusCode === 200) resolve(JSON.parse(body));
        else if (res.statusCode === 404) resolve(null);
        else reject(new Error(`GET ${path} HTTP ${res.statusCode}: ${body}`));
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function githubPut(path, content, message, sha) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({
      message,
      content: Buffer.from(content).toString('base64'),
      branch: BRANCH,
      ...(sha ? { sha } : {})
    });
    const options = {
      hostname: 'api.github.com',
      path: `/repos/${OWNER}/${REPO}/contents/${path}`,
      method: 'PUT',
      headers: {
        'Authorization': `token ${GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'nodejs',
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data)
      }
    };
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        if (res.statusCode === 201 || res.statusCode === 200) resolve(JSON.parse(body));
        else reject(new Error(`PUT ${path} HTTP ${res.statusCode}: ${body}`));
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

function buildDailyHtml(article) {
  const { date, title, titleCn, pairs, sourceUrl } = article;
  const year = date.split('-')[0];
  const monthNum = date.split('-')[1];
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const monthName = monthNames[parseInt(monthNum) - 1];
  const dayNum = date.split('-')[2];

  // Format date display
  const dateDisplay = `${monthName} ${parseInt(dayNum)}, ${year}`;

  // Build bilingual content blocks
  // Wrap each English word in a clickable span (only pure letter words)
  function wrapWords(text) {
    return escapeHtml(text).replace(/\b([A-Za-z]{2,}(?:'[a-z]+)?)\b/g, '<span class="w">$1</span>');
  }
  let contentBlocks = '';
  for (const [en, zh] of pairs) {
    contentBlocks += `
  <div class="pair">
    <div class="en-text">${wrapWords(en)}</div>
    <div class="zh-text">${escapeHtml(zh)}</div>
  </div>`;
  }

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(title)} · ${date}</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;-webkit-font-smoothing:antialiased}
body{font-family:'Noto Serif SC','Source Han Serif SC','STSongti','Songti SC',Georgia,'Times New Roman',serif;background:#f8f5f0;color:#2c2c2c;line-height:1.8;min-height:100vh}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse at 15% 8%,rgba(180,160,140,0.10) 0%,transparent 50%),radial-gradient(ellipse at 85% 92%,rgba(200,180,160,0.08) 0%,transparent 50%);pointer-events:none;z-index:-1}
.container{max-width:780px;margin:0 auto;padding:0 24px}
.nav-bar{display:flex;align-items:center;justify-content:space-between;padding:20px 0;font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC','PingFang SC',sans-serif}
.nav-bar a{color:#8a7a6a;text-decoration:none;font-size:14px;transition:color .2s}
.nav-bar a:hover{color:#5a4a3a}
.article-header{padding:40px 0 32px;text-align:center}
.article-header .article-date{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC',sans-serif;font-size:14px;color:#aaa;letter-spacing:.05em;margin-bottom:6px}
.article-header .article-source{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC',sans-serif;font-size:13px;color:#bbb;margin-bottom:16px}
.article-header .article-source a{color:#8a7a6a;text-decoration:none}
.article-header .article-source a:hover{text-decoration:underline}
.article-header h1{font-size:clamp(24px,4vw,34px);font-weight:600;color:#1a1a1a;letter-spacing:.02em;line-height:1.35}
.article-header .chinese-title{font-size:clamp(18px,3vw,24px);color:#666;font-weight:500;margin-top:10px}
.divider{display:flex;align-items:center;gap:16px;margin:8px 0 40px;color:#ddd;font-size:12px;font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC',sans-serif}
.divider::before,.divider::after{content:'';flex:1;height:1px;background:linear-gradient(to right,transparent,#e0d8d0,transparent)}
.article-content{background:rgba(255,255,255,0.6);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,0.8);border-radius:16px;padding:28px 40px;margin-bottom:32px}
.article-content .pair{margin-bottom:20px;padding-bottom:20px;border-bottom:1px solid rgba(0,0,0,0.05)}
.article-content .pair:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0}
.article-content .en-text{font-size:16px;color:#3a3a3a;line-height:1.7;margin-bottom:4px}
.article-content .zh-text{font-size:15px;color:#777;line-height:1.75;word-break:keep-all;overflow-wrap:anywhere}
footer{text-align:center;padding:24px 0 40px;font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC',sans-serif}
footer a{color:#8a7a6a;text-decoration:none;font-size:14px;transition:color .2s}
footer a:hover{color:#5a4a3a}
footer .sep{color:#ddd;margin:0 8px}
@media(max-width:600px){.article-content{padding:18px 16px}.article-header{padding:20px 0 16px}.article-content .en-text{font-size:15px}.article-content .zh-text{font-size:14px}}
/* Word click */
.en-text .w{cursor:pointer;border-radius:2px;transition:background .12s}
.en-text .w:hover,.en-text .w:active{background:rgba(138,122,106,0.18)}
.en-text .w.saved{color:#8a7a6a;border-bottom:1.5px dotted #8a7a6a}
/* Bottom-sheet popup */
#word-popup-overlay{display:none;position:fixed;inset:0;z-index:9998;background:rgba(0,0,0,0.25);backdrop-filter:blur(2px);-webkit-backdrop-filter:blur(2px)}
#word-popup{position:fixed;z-index:9999;left:0;right:0;bottom:0;background:#fff;border-radius:18px 18px 0 0;box-shadow:0 -4px 32px rgba(0,0,0,0.13);padding:0 24px 32px;font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC',sans-serif;transform:translateY(100%);transition:transform .25s cubic-bezier(.32,.72,0,1);will-change:transform;max-height:70vh;overflow-y:auto}
#word-popup.open{transform:translateY(0)}
#word-popup .drag-handle{width:36px;height:4px;background:#e0e0e0;border-radius:2px;margin:12px auto 16px;cursor:grab}
#word-popup .popup-word{font-size:22px;font-weight:700;color:#1a1a1a;margin-bottom:2px}
#word-popup .popup-phonetic-row{display:flex;align-items:center;gap:8px;margin-bottom:12px;min-height:18px}
#word-popup .popup-phonetic{font-size:13px;color:#aaa;font-style:italic}
#word-popup .btn-speak{background:none;border:none;cursor:pointer;padding:2px 4px;font-size:16px;color:#aaa;line-height:1;border-radius:4px;transition:color .15s,background .15s}
#word-popup .btn-speak:hover{color:#5a7a9a;background:rgba(90,122,154,0.1)}
#word-popup .btn-speak:active{color:#2a5a7a}
#word-popup .popup-defs{margin-bottom:16px}
#word-popup .popup-def{margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #f0f0f0}
#word-popup .popup-def:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0}
#word-popup .popup-pos{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:#ccc;margin-bottom:3px}
#word-popup .popup-meaning-cn{font-size:15px;color:#333;line-height:1.6;font-weight:500}
#word-popup .popup-meaning-en{font-size:12px;color:#bbb;line-height:1.5;margin-top:2px}
#word-popup .popup-example{font-size:12px;color:#bbb;font-style:italic;margin-top:3px}
#word-popup .popup-loading{font-size:14px;color:#ccc;padding:8px 0 16px;text-align:center}
#word-popup .popup-notfound{font-size:13px;color:#bbb;padding:6px 0 16px}
#word-popup .popup-actions{display:flex;gap:8px;position:sticky;bottom:0;background:#fff;padding-top:8px}
#word-popup .btn-save{flex:1;padding:11px 0;background:#2c2c2c;color:#fff;border:none;border-radius:10px;font-size:14px;cursor:pointer;transition:background .2s;font-weight:500}
#word-popup .btn-save:active{background:#111}
#word-popup .btn-save.saved-state{background:#e8f4ee;color:#2a8a55}
#word-popup .btn-close{padding:11px 16px;background:rgba(0,0,0,0.05);color:#888;border:none;border-radius:10px;font-size:14px;cursor:pointer}
</style>
</head>
<body>
<div id="word-popup-overlay" onclick="closePopup()"></div>
<div id="word-popup">
  <div class="drag-handle"></div>
  <div class="popup-word" id="pp-word"></div>
  <div class="popup-phonetic-row">
    <span class="popup-phonetic" id="pp-phonetic"></span>
    <button class="btn-speak" id="pp-speak-btn" onclick="speakWord()" title="朗读" style="display:none">🔊</button>
  </div>
  <div class="popup-defs" id="pp-defs"></div>
  <div class="popup-actions">
    <button class="btn-save" id="pp-save-btn" onclick="saveWord()">加入单词本</button>
    <button class="btn-close" onclick="closePopup()">关闭</button>
  </div>
</div>
<div class="container">
<nav class="nav-bar">
  <a href="../index.html">← 返回首页</a>
  <a href="../wordbook.html" style="display:flex;align-items:center;gap:5px;font-size:13px;color:#8a7a6a;text-decoration:none" id="nav-wb-link">📖 <span id="nav-wb-count"></span></a>
  <a href="https://amruta.today/" target="_blank">Amruta.today</a>
</nav>
<div class="article-header">
  <div class="article-date">${dateDisplay}</div>
  <h1>${escapeHtml(title)}</h1>
  <div class="chinese-title">${escapeHtml(titleCn)}</div>
  <div class="article-source">Source: <a href="${sourceUrl || 'https://amruta.today/'}" target="_blank">${sourceUrl ? ((sourceUrl.match(/https?:\/\/([^/]+)/) || [])[1] || sourceUrl) : 'amruta.today'}</a></div>
</div>
<div class="divider">◇</div>
<div class="article-content">${contentBlocks}
</div>
<footer>
  <a href="../index.html">← 返回首页</a>
  <span class="sep">·</span>
  <a href="../wordbook.html">📖 单词本</a>
  <span class="sep">·</span>
  <a href="https://amruta.today/" target="_blank">Amruta.today</a>
  <span class="sep">·</span>
  <a href="https://github.com/wherejiahe-bot/amruta-daily-archive" target="_blank">GitHub</a>
</footer>
</div>
<script>
const ARTICLE_DATE = '${date}';
const WB_KEY = 'amruta_wordbook';

function getWordbook() { try { return JSON.parse(localStorage.getItem(WB_KEY) || '{}'); } catch(e) { return {}; } }
function saveWordbook(wb) { localStorage.setItem(WB_KEY, JSON.stringify(wb)); }

function refreshSavedMarks() {
  const wb = getWordbook();
  document.querySelectorAll('.en-text .w').forEach(el => {
    const w = el.textContent.replace(/[^A-Za-z']/g,'').toLowerCase();
    el.classList.toggle('saved', !!wb[w]);
  });
  const count = Object.keys(wb).length;
  const navEl = document.getElementById('nav-wb-count');
  if (navEl) navEl.textContent = count > 0 ? '单词本 ' + count : '单词本';
}

let currentWord = '';
let currentData = null;
let currentAudioUrl = '';

const POS_CN = {
  noun:'名词', verb:'动词', adjective:'形容词', adverb:'副词',
  pronoun:'代词', preposition:'介词', conjunction:'连词',
  interjection:'感叹词', article:'冠词', determiner:'限定词',
  exclamation:'感叹词', abbreviation:'缩写'
};

function posLabel(pos) {
  return POS_CN[pos] || pos;
}

function speakWord() {
  // Prefer API audio URL; fallback to speechSynthesis
  if (currentAudioUrl) {
    const audio = new Audio(currentAudioUrl);
    audio.play().catch(() => synthSpeak());
  } else {
    synthSpeak();
  }
}

function synthSpeak() {
  if (!window.speechSynthesis) return;
  const utter = new SpeechSynthesisUtterance(currentWord);
  utter.lang = 'en-US';
  utter.rate = 0.9;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utter);
}

async function translateDef(text) {
  try {
    const url = 'https://api.mymemory.translated.net/get?q=' + encodeURIComponent(text) + '&langpair=en|zh';
    const r = await fetch(url, { signal: AbortSignal.timeout(4000) });
    if (!r.ok) return '';
    const d = await r.json();
    const t = d?.responseData?.translatedText || '';
    if (!t || t === text) return '';
    return t;
  } catch(e) { return ''; }
}

function closePopup() {
  const popup = document.getElementById('word-popup');
  const overlay = document.getElementById('word-popup-overlay');
  popup.classList.remove('open');
  overlay.style.display = 'none';
}

function openSheet() {
  const overlay = document.getElementById('word-popup-overlay');
  const popup = document.getElementById('word-popup');
  overlay.style.display = 'block';
  // Force reflow so transition fires
  popup.getBoundingClientRect();
  popup.classList.add('open');
}

async function openWordPopup(el, word) {
  currentWord = word.toLowerCase().replace(/['\u2019]/g, "'");
  currentData = null;
  currentAudioUrl = '';
  document.getElementById('pp-word').textContent = word;
  document.getElementById('pp-phonetic').textContent = '';
  document.getElementById('pp-speak-btn').style.display = 'none';
  document.getElementById('pp-defs').innerHTML = '<div class="popup-loading">查询中…</div>';
  updateSaveBtn();
  openSheet();

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 6000);
    const res = await fetch('https://api.dictionaryapi.dev/api/v2/entries/en/' + encodeURIComponent(currentWord), { signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error('not found');
    const data = await res.json();
    currentData = data[0];

    // Phonetic text
    const phonetics = currentData.phonetics || [];
    const phonetic = currentData.phonetic || phonetics.find(p => p.text)?.text || '';
    document.getElementById('pp-phonetic').textContent = phonetic;

    // Audio URL from API (prefer one with text + audio)
    const audioEntry = phonetics.find(p => p.audio && p.audio.length > 0);
    if (audioEntry) {
      currentAudioUrl = audioEntry.audio.startsWith('http') ? audioEntry.audio : 'https:' + audioEntry.audio;
    }

    // Show speaker button if speechSynthesis available or audio url found
    if (currentAudioUrl || window.speechSynthesis) {
      document.getElementById('pp-speak-btn').style.display = '';
    }

    // Build defs with async CN translation
    const meanings = (currentData.meanings || []).slice(0, 3);
    // Show immediately with English, then patch with Chinese
    let defsHtml = '';
    meanings.forEach((m, i) => {
      const def = (m.definitions || [])[0];
      if (!def) return;
      defsHtml += '<div class="popup-def" id="pp-def-' + i + '">'
        + '<div class="popup-pos">' + posLabel(m.partOfSpeech) + '</div>'
        + '<div class="popup-meaning-cn" id="pp-cn-' + i + '">' + def.definition + '</div>'
        + (def.example ? '<div class="popup-example">' + def.example + '</div>' : '')
        + '</div>';
    });
    document.getElementById('pp-defs').innerHTML = defsHtml || '<div class="popup-notfound">无释义</div>';

    // Async: translate each definition to Chinese
    meanings.forEach((m, i) => {
      const def = (m.definitions || [])[0];
      if (!def) return;
      translateDef(def.definition).then(cn => {
        const cnEl = document.getElementById('pp-cn-' + i);
        if (!cnEl) return;
        if (cn) {
          cnEl.textContent = cn;
          // Add English original as small text below
          const enSmall = document.createElement('div');
          enSmall.className = 'popup-meaning-en';
          enSmall.textContent = def.definition;
          cnEl.after(enSmall);
        }
      });
    });

  } catch(e) {
    document.getElementById('pp-phonetic').textContent = '';
    // Still show speaker via speechSynthesis even on API failure
    if (window.speechSynthesis) {
      document.getElementById('pp-speak-btn').style.display = '';
    }
    document.getElementById('pp-defs').innerHTML = '<div class="popup-notfound">未找到释义，可直接加入单词本</div>';
  }
}

function updateSaveBtn() {
  const wb = getWordbook();
  const btn = document.getElementById('pp-save-btn');
  if (wb[currentWord]) {
    btn.textContent = '✓ 已在单词本';
    btn.classList.add('saved-state');
  } else {
    btn.textContent = '加入单词本';
    btn.classList.remove('saved-state');
  }
}

function saveWord() {
  const wb = getWordbook();
  if (wb[currentWord]) {
    delete wb[currentWord];
    saveWordbook(wb);
    updateSaveBtn();
    refreshSavedMarks();
    return;
  }
  const phonetic = document.getElementById('pp-phonetic').textContent.trim();
  let defs = [];
  if (currentData && currentData.meanings) {
    currentData.meanings.slice(0,3).forEach((m, i) => {
      const d = (m.definitions||[])[0];
      if (!d) return;
      // Try to grab translated CN from DOM if available
      const cnEl = document.getElementById('pp-cn-' + i);
      const cnText = cnEl ? cnEl.textContent.trim() : '';
      defs.push({ pos: m.partOfSpeech, posCn: posLabel(m.partOfSpeech), def: d.definition, defCn: cnText !== d.definition ? cnText : '', example: d.example||'' });
    });
  }
  wb[currentWord] = { word: currentWord, phonetic, defs, source: ARTICLE_DATE, savedAt: Date.now() };
  saveWordbook(wb);
  updateSaveBtn();
  refreshSavedMarks();
}

// Event delegation — handles all .w spans, works regardless of render order
document.addEventListener('click', e => {
  const t = e.target;
  if (t.classList.contains('w') && t.closest('.en-text')) {
    e.stopPropagation();
    const word = t.textContent.replace(/[^A-Za-z']/g, '');
    if (word.length >= 2) openWordPopup(t, word);
  }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePopup(); });
refreshSavedMarks();
// Hash-based word highlight: #word-{word} scrolls to first occurrence and highlights the pair
(function(){
  const hash = location.hash;
  if (!hash || !hash.startsWith('#word-')) return;
  const target = decodeURIComponent(hash.slice(6)).toLowerCase();
  const spans = document.querySelectorAll('.en-text .w');
  let found = null;
  for (const s of spans) {
    if (s.textContent.replace(/[^A-Za-z']/g,'').toLowerCase() === target) { found = s; break; }
  }
  if (!found) return;
  const pair = found.closest('.pair');
  if (!pair) return;
  pair.id = 'highlight-pair';
  pair.style.cssText += ';border-radius:8px;transition:background .4s;';
  setTimeout(() => {
    pair.scrollIntoView({ behavior: 'smooth', block: 'center' });
    pair.style.background = 'rgba(138,122,106,0.13)';
    for (const s of pair.querySelectorAll('.w')) {
      if (s.textContent.replace(/[^A-Za-z']/g,'').toLowerCase() === target) {
        s.style.cssText += ';background:rgba(138,122,106,0.28);border-radius:3px;padding:0 1px;';
      }
    }
    setTimeout(() => { pair.style.background = ''; }, 2200);
  }, 350);
})();
</script>
</body>
</html>`;
}

function buildIndexHtml(articles) {
  // Sort by article date descending (newest date first)
  articles.sort((a, b) => b.date.localeCompare(a.date));

  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  let cards = '';
  for (const a of articles) {
    const pushDate = a.pushDate || a.date;
    const pushYear = pushDate.split('-')[0];
    // Month and day from original speech date; year from push year
    const dateParts = a.date.split('-');
    const articleMonth = monthNames[parseInt(dateParts[1]) - 1];
    const articleDay = parseInt(dateParts[2]);

    cards += `
  <a href="daily/${a.date}.html" class="article-card">
    <div class="date-badge">
      <span class="month">${articleMonth}</span>
      <span class="day">${articleDay}</span>
      <span class="year">${pushYear}</span>
    </div>
    <div class="card-content">
      <div class="card-title">${escapeHtml(a.title)}</div>
      <div class="card-preview">${a.date} · ${escapeHtml(a.titleCn)}</div>
    </div>
    <span class="arrow">→</span>
  </a>`;
  }

  const count = articles.length;

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日 Shri Mataji 讲话 · 中英对照存档</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{font-size:16px;-webkit-font-smoothing:antialiased}
body{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;background:#f5f0eb;color:#2c2c2c;line-height:1.7;min-height:100vh}
body::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse at 20% 10%,rgba(180,160,140,0.12) 0%,transparent 50%),radial-gradient(ellipse at 80% 90%,rgba(200,180,160,0.10) 0%,transparent 50%);pointer-events:none;z-index:-1}
.container{max-width:720px;margin:0 auto;padding:0 24px}
header{padding:64px 0 48px;text-align:center}
header h1{font-size:clamp(28px,5vw,40px);font-weight:600;color:#1a1a1a;letter-spacing:.02em;margin-bottom:12px}
header .subtitle{font-size:clamp(15px,2.5vw,18px);color:#888;font-weight:400}
header .subtitle span{display:inline-block;padding:4px 14px;background:rgba(180,160,140,0.15);border-radius:20px;font-size:14px;color:#8a7a6a;margin-top:8px}
.toolbar{display:flex;align-items:center;justify-content:space-between;padding:16px 0 24px;border-bottom:1px solid rgba(0,0,0,0.06);margin-bottom:32px}
.toolbar .count{font-size:14px;color:#999}
.toolbar .count strong{color:#666;font-weight:500}
.toolbar .rss-link{font-size:14px;color:#8a7a6a;text-decoration:none;padding:4px 14px;border:1px solid rgba(140,125,110,0.25);border-radius:20px;transition:all .2s}
.toolbar .rss-link:hover{background:rgba(140,125,110,0.08);border-color:rgba(140,125,110,0.4)}
.article-list{display:flex;flex-direction:column;gap:12px;padding-bottom:64px}
.article-card{display:flex;align-items:center;gap:20px;padding:18px 24px;background:rgba(255,255,255,0.65);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.8);border-radius:14px;text-decoration:none;color:inherit;transition:all .25s ease;position:relative}
.article-card:hover{background:rgba(255,255,255,0.85);transform:translateY(-1px);box-shadow:0 4px 20px rgba(0,0,0,0.06)}
.article-card:active{transform:translateY(0)}
.article-card .date-badge{flex-shrink:0;text-align:center;min-width:56px}
.article-card .date-badge .month{display:block;font-size:12px;color:#999;text-transform:uppercase;letter-spacing:.08em;line-height:1}
.article-card .date-badge .day{display:block;font-size:26px;font-weight:600;color:#4a4a4a;line-height:1.2;margin-top:2px}
.article-card .date-badge .year{display:block;font-size:11px;color:#bbb;line-height:1}
.article-card .card-content{flex:1;min-width:0}
.article-card .card-content .card-title{font-size:17px;font-weight:500;color:#2c2c2c;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:keep-all;overflow-wrap:anywhere}
.article-card .card-content .card-preview{font-size:14px;color:#aaa;margin-top:4px;display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.article-card .arrow{flex-shrink:0;color:#ccc;font-size:18px;transition:all .2s}
.article-card:hover .arrow{color:#8a7a6a;transform:translateX(3px)}
.empty-state{text-align:center;padding:80px 24px;color:#bbb}
.empty-state .empty-icon{font-size:40px;margin-bottom:16px;opacity:0.4}
.empty-state p{font-size:16px;line-height:1.6}
footer{text-align:center;padding:32px 0 48px;border-top:1px solid rgba(0,0,0,0.04)}
footer a{color:#8a7a6a;text-decoration:none;font-size:14px;transition:color .2s}
footer a:hover{color:#6a5a4a}
@media(max-width:480px){header{padding:40px 0 32px}.article-card{padding:14px 16px;gap:14px}.article-card .date-badge{min-width:44px}.article-card .date-badge .day{font-size:22px}.article-card .card-content .card-title{font-size:15px}.toolbar{flex-direction:column;gap:12px;align-items:flex-start}}
</style>
</head>
<body>
<div class="container">
<header>
  <h1>每日 Shri Mataji 讲话</h1>
  <p class="subtitle">中英对照 · 逐日存档</p>
  <p class="subtitle"><span>Amruta Today Archive</span></p>
</header>
<div class="toolbar">
  <span class="count">共 <strong>${count}</strong> 篇讲话</span>
  <div style="display:flex;gap:10px;align-items:center">
    <a href="wordbook.html" class="rss-link" id="idx-wb-link">📖 单词本 <span id="idx-wb-count"></span></a>
    <a href="https://amruta.today/" class="rss-link" target="_blank">Amruta.today →</a>
  </div>
</div>
<script>
(function(){
  try{
    const wb=JSON.parse(localStorage.getItem('amruta_wordbook')||'{}');
    const n=Object.keys(wb).length;
    const el=document.getElementById('idx-wb-count');
    if(el&&n>0)el.textContent='('+n+')';
  }catch(e){}
})();
</script>
<div class="article-list">${cards}
</div>
<footer>
  <a href="https://amruta.today/" target="_blank">Amruta.today</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/wherejiahe-bot/amruta-daily-archive" target="_blank">GitHub</a>
</footer>
</div>
</body>
</html>`;
}

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

async function main() {
  // Read input JSON: from --file argument, or stdin
  let input;
  const fileArgIdx = process.argv.indexOf('--file');
  if (fileArgIdx >= 0 && process.argv[fileArgIdx + 1]) {
    input = JSON.parse(fs.readFileSync(process.argv[fileArgIdx + 1], 'utf-8'));
  } else {
    input = await new Promise((resolve) => {
      let data = '';
      process.stdin.on('data', (chunk) => data += chunk);
      process.stdin.on('end', () => resolve(JSON.parse(data)));
    });
  }

  const { date, title, titleCn, pairs, sourceUrl } = input;

  if (!date || !title || !pairs || !pairs.length) {
    console.error('Missing required fields: date, title, pairs');
    process.exit(1);
  }

  const year = date.split('-')[0];
  const monthNum = parseInt(date.split('-')[1]);
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const month = monthNames[monthNum - 1];

  // Step 1: Build and push daily HTML
  // Step 1: Build and push daily HTML
  const dailyHtml = buildDailyHtml(input);
  const dailyPath = `daily/${date}.html`;
  console.log(`📝 Building ${dailyPath}...`);
  const existingDaily = await githubGet(dailyPath);
  const dailySha = existingDaily ? existingDaily.sha : null;
  await githubPut(dailyPath, dailyHtml, `feat: add daily article ${date} - ${title}`, dailySha);
  console.log(`✅ ${dailyPath} pushed`);

  // Step 2: Get current articles.json
  console.log('📥 Fetching articles.json...');
  const existing = await githubGet('articles.json');
  let articles = [];
  let articlesSha = null;

  if (existing) {
    articles = JSON.parse(Buffer.from(existing.content, 'base64').toString('utf-8'));
    articlesSha = existing.sha;
    // Remove existing entry for same date (replace)
    articles = articles.filter(a => a.date !== date);
  }

  // Add new entry (pushDate = today in Beijing time, date = original speech date)
  const pushDate = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
  articles.push({ date, title, titleCn, year, month, source: sourceUrl || '', pushDate });

  // Step 3: Push updated articles.json
  console.log('📝 Updating articles.json...');
  await githubPut('articles.json', JSON.stringify(articles, null, 2), `feat: add ${date} to articles index`, articlesSha);
  console.log('✅ articles.json updated');

  // Step 4: Build and push index.html from articles
  console.log('📝 Regenerating index.html...');
  const indexHtml = buildIndexHtml(articles);

  // Get current index.html sha
  const existingIndex = await githubGet('index.html');
  const indexSha = existingIndex ? existingIndex.sha : null;
  await githubPut('index.html', indexHtml, `feat: update navigation with ${date}`, indexSha);
  console.log('✅ index.html updated');

  console.log(`\n🎉 Successfully pushed ${date} to GitHub!`);
  console.log(`🌐 https://github.com/${OWNER}/${REPO}`);
}

main().catch(err => {
  console.error('❌ Push failed:', err.message);
  process.exit(1);
});
