/**
 * Migration script: re-generate all daily pages with vocabulary feature
 * + push wordbook.html + rebuild index.html
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
      headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'nodejs' }
    };
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        if (res.statusCode === 200) resolve(JSON.parse(body));
        else if (res.statusCode === 404) resolve(null);
        else reject(new Error(`GET ${path} HTTP ${res.statusCode}: ${body.slice(0,200)}`));
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function githubPut(path, content, message, sha) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({ message, content: Buffer.from(content).toString('base64'), branch: BRANCH, ...(sha ? { sha } : {}) });
    const options = {
      hostname: 'api.github.com',
      path: `/repos/${OWNER}/${REPO}/contents/${path}`,
      method: 'PUT',
      headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'nodejs', 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }
    };
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        if (res.statusCode === 201 || res.statusCode === 200) resolve(JSON.parse(body));
        else reject(new Error(`PUT ${path} HTTP ${res.statusCode}: ${body.slice(0,200)}`));
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

function escapeHtml(text) {
  return String(text).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

// Extract pairs from existing daily HTML
function extractPairs(html) {
  const pairs = [];
  // Match all en-text and zh-text content in order
  const enMatches = [...html.matchAll(/<div class="en-text(?:[^"]*)">([\s\S]*?)<\/div>/g)];
  const zhMatches = [...html.matchAll(/<div class="zh-text(?:[^"]*)">([\s\S]*?)<\/div>/g)];
  const len = Math.min(enMatches.length, zhMatches.length);
  for (let i = 0; i < len; i++) {
    // Unescape html entities
    const en = enMatches[i][1].trim().replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#039;/g,"'");
    const zh = zhMatches[i][1].trim().replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#039;/g,"'");
    pairs.push([en, zh]);
  }
  return pairs;
}

function extractSourceUrl(html) {
  const m = html.match(/href="(https?:\/\/[^"]+)"[^>]*>(?:www\.[^<]+|[^<]+)<\/a>\s*<\/div>\s*<\/div>/);
  if (m) return m[1];
  // fallback: look for article-source link
  const m2 = html.match(/class="article-source"[^>]*>[\s\S]*?href="([^"]+)"/);
  return m2 ? m2[1] : '';
}

function wrapWords(text) {
  return escapeHtml(text).replace(/([A-Za-z''\u2019]+)/g, '<span class="word" data-word="$1">$1</span>');
}

function buildDailyHtml(article) {
  const { date, title, titleCn, pairs, sourceUrl } = article;
  const year = date.split('-')[0];
  const monthNum = date.split('-')[1];
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const monthName = monthNames[parseInt(monthNum) - 1];
  const dayNum = date.split('-')[2];
  const dateDisplay = `${monthName} ${parseInt(dayNum)}, ${year}`;

  let contentBlocks = '';
  for (const [en, zh] of pairs) {
    contentBlocks += `
  <div class="en-block">
    <div class="lang-label">English</div>
    <div class="en-text clickable-text">${wrapWords(en)}</div>
  </div>

  <div class="zh-block">
    <div class="lang-label">中文</div>
    <div class="zh-text">${escapeHtml(zh)}</div>
  </div>`;
  }

  const srcDomain = sourceUrl ? ((sourceUrl.match(/https?:\/\/([^/]+)/) || [])[1] || sourceUrl) : 'amruta.today';

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
.article-content{background:rgba(255,255,255,0.6);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,0.8);border-radius:16px;padding:40px 48px;margin-bottom:40px}
.article-content .lang-label{font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC',sans-serif;font-size:12px;color:#bbb;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px}
.article-content .en-block{margin-bottom:28px;padding-bottom:24px;border-bottom:1px solid rgba(0,0,0,0.05)}
.article-content .zh-block{margin-bottom:28px;padding-bottom:24px;border-bottom:1px solid rgba(0,0,0,0.05)}
.article-content .en-block:last-child,.article-content .zh-block:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0}
.article-content .en-text{font-size:17px;color:#3a3a3a;line-height:1.75}
.article-content .zh-text{font-size:17px;color:#555;line-height:1.85;word-break:keep-all;overflow-wrap:anywhere;text-wrap:balance}
footer{text-align:center;padding:32px 0 48px;font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC',sans-serif}
footer a{color:#8a7a6a;text-decoration:none;font-size:14px;transition:color .2s}
footer a:hover{color:#5a4a3a}
footer .sep{color:#ddd;margin:0 8px}
/* Word click */
.clickable-text .word{cursor:pointer;border-radius:3px;transition:background .15s}
.clickable-text .word:hover{background:rgba(138,122,106,0.15)}
.clickable-text .word.saved{color:#8a7a6a;border-bottom:1px dotted #8a7a6a}
/* Popup */
#word-popup{display:none;position:fixed;z-index:9999;background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,0.12);padding:24px 28px;max-width:340px;width:90vw;font-family:-apple-system,BlinkMacSystemFont,'Noto Sans SC',sans-serif}
#word-popup .popup-word{font-size:22px;font-weight:600;color:#1a1a1a;margin-bottom:4px}
#word-popup .popup-phonetic{font-size:14px;color:#999;margin-bottom:12px;font-style:italic}
#word-popup .popup-defs{max-height:200px;overflow-y:auto;margin-bottom:16px}
#word-popup .popup-def{margin-bottom:10px}
#word-popup .popup-pos{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#bbb;margin-bottom:3px}
#word-popup .popup-meaning{font-size:14px;color:#444;line-height:1.6}
#word-popup .popup-example{font-size:13px;color:#aaa;font-style:italic;margin-top:3px}
#word-popup .popup-notfound{font-size:14px;color:#aaa;padding:8px 0}
#word-popup .popup-actions{display:flex;gap:10px}
#word-popup .btn-save{flex:1;padding:9px 0;background:#2c2c2c;color:#fff;border:none;border-radius:10px;font-size:14px;cursor:pointer;transition:background .2s}
#word-popup .btn-save:hover{background:#1a1a1a}
#word-popup .btn-save.saved-state{background:#e8f4ee;color:#2a8a55}
#word-popup .btn-close{padding:9px 16px;background:rgba(0,0,0,0.04);color:#666;border:none;border-radius:10px;font-size:14px;cursor:pointer}
#word-popup-overlay{display:none;position:fixed;inset:0;z-index:9998}
@media(max-width:600px){.article-content{padding:24px 20px}.article-header{padding:24px 0}.article-content .en-text,.article-content .zh-text{font-size:16px}}
</style>
</head>
<body>
<div id="word-popup-overlay" onclick="closePopup()"></div>
<div id="word-popup">
  <div class="popup-word" id="pp-word"></div>
  <div class="popup-phonetic" id="pp-phonetic"></div>
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
  <div class="article-source">Source: <a href="${sourceUrl || 'https://amruta.today/'}" target="_blank">${srcDomain}</a></div>
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
function getWordbook(){try{return JSON.parse(localStorage.getItem(WB_KEY)||'{}')}catch(e){return {}}}
function saveWordbook(wb){localStorage.setItem(WB_KEY,JSON.stringify(wb))}
function refreshSavedMarks(){
  const wb=getWordbook();
  document.querySelectorAll('.word').forEach(el=>{
    el.classList.toggle('saved',!!wb[el.dataset.word.toLowerCase()]);
  });
  const count=Object.keys(wb).length;
  const navEl=document.getElementById('nav-wb-count');
  if(navEl)navEl.textContent=count>0?'单词本 '+count:'单词本';
}
let currentWord='',currentData=null;
function closePopup(){
  document.getElementById('word-popup').style.display='none';
  document.getElementById('word-popup-overlay').style.display='none';
}
function positionPopup(el){
  const popup=document.getElementById('word-popup');
  popup.style.display='block';
  const rect=el.getBoundingClientRect();
  const pw=popup.offsetWidth,ph=popup.offsetHeight;
  let top=rect.bottom+8+window.scrollY;
  let left=rect.left+window.scrollX;
  if(left+pw>window.innerWidth-12)left=window.innerWidth-pw-12;
  if(left<12)left=12;
  if(top+ph>window.scrollY+window.innerHeight-12)top=rect.top+window.scrollY-ph-8;
  popup.style.top=top+'px';
  popup.style.left=left+'px';
}
async function openWordPopup(el,word){
  currentWord=word.toLowerCase().replace(/['\u2019]/g,"'");
  currentData=null;
  document.getElementById('pp-word').textContent=word;
  document.getElementById('pp-phonetic').textContent='加载中…';
  document.getElementById('pp-defs').innerHTML='';
  document.getElementById('word-popup-overlay').style.display='block';
  positionPopup(el);
  updateSaveBtn();
  try{
    const res=await fetch('https://api.dictionaryapi.dev/api/v2/entries/en/'+encodeURIComponent(currentWord));
    if(!res.ok)throw new Error('not found');
    const data=await res.json();
    currentData=data[0];
    const phonetic=currentData.phonetic||(currentData.phonetics||[]).find(p=>p.text)?.text||'';
    document.getElementById('pp-phonetic').textContent=phonetic;
    let defsHtml='';
    (currentData.meanings||[]).slice(0,3).forEach(m=>{
      const def=(m.definitions||[])[0];
      if(!def)return;
      defsHtml+='<div class="popup-def"><div class="popup-pos">'+m.partOfSpeech+'</div><div class="popup-meaning">'+def.definition+'</div>'+(def.example?'<div class="popup-example">"'+def.example+'"</div>':'')+'</div>';
    });
    document.getElementById('pp-defs').innerHTML=defsHtml||'<div class="popup-notfound">无释义</div>';
  }catch(e){
    document.getElementById('pp-phonetic').textContent='';
    document.getElementById('pp-defs').innerHTML='<div class="popup-notfound">未找到释义，可直接加入单词本</div>';
  }
}
function updateSaveBtn(){
  const wb=getWordbook();
  const btn=document.getElementById('pp-save-btn');
  if(wb[currentWord]){btn.textContent='✓ 已在单词本';btn.classList.add('saved-state');}
  else{btn.textContent='加入单词本';btn.classList.remove('saved-state');}
}
function saveWord(){
  const wb=getWordbook();
  if(wb[currentWord]){delete wb[currentWord];saveWordbook(wb);updateSaveBtn();refreshSavedMarks();return;}
  const phonetic=document.getElementById('pp-phonetic').textContent.replace('加载中…','');
  let defs=[];
  if(currentData&&currentData.meanings){
    currentData.meanings.slice(0,3).forEach(m=>{
      const d=(m.definitions||[])[0];
      if(d)defs.push({pos:m.partOfSpeech,def:d.definition,example:d.example||''});
    });
  }
  wb[currentWord]={word:currentWord,phonetic,defs,source:ARTICLE_DATE,savedAt:Date.now()};
  saveWordbook(wb);
  updateSaveBtn();
  refreshSavedMarks();
}
document.querySelectorAll('.word').forEach(el=>{
  el.addEventListener('click',e=>{
    e.stopPropagation();
    const w=el.dataset.word;
    if(/^[A-Za-z]/.test(w))openWordPopup(el,w);
  });
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePopup();});
refreshSavedMarks();
</script>
</body>
</html>`;
}

function buildIndexHtml(articles) {
  articles.sort((a, b) => (b.pushDate || b.date).localeCompare(a.pushDate || a.date));
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  let cards = '';
  for (const a of articles) {
    const pushDate = a.pushDate || a.date;
    const pushYear = pushDate.split('-')[0];
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
.toolbar{display:flex;align-items:center;justify-content:space-between;padding:16px 0 24px;border-bottom:1px solid rgba(0,0,0,0.06);margin-bottom:32px;flex-wrap:wrap;gap:10px}
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
<div class="article-list">${cards}
</div>
<footer>
  <a href="https://amruta.today/" target="_blank">Amruta.today</a>
  &nbsp;·&nbsp;
  <a href="wordbook.html">📖 单词本</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/wherejiahe-bot/amruta-daily-archive" target="_blank">GitHub</a>
</footer>
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
</body>
</html>`;
}

async function main() {
  // 1. Load articles.json
  const articlesFile = await githubGet('articles.json');
  const articles = JSON.parse(Buffer.from(articlesFile.content, 'base64').toString('utf-8'));
  console.log(`Found ${articles.length} articles`);

  // 2. Re-generate each daily HTML
  for (const a of articles) {
    const path = `daily/${a.date}.html`;
    console.log(`\nProcessing ${path}...`);
    const existing = await githubGet(path);
    if (!existing) { console.log(`  ⚠️  Not found, skipping`); continue; }
    const existingHtml = Buffer.from(existing.content, 'base64').toString('utf-8');

    // Extract pairs from existing HTML
    const pairs = extractPairs(existingHtml);
    const sourceUrl = a.source || extractSourceUrl(existingHtml);
    console.log(`  Extracted ${pairs.length} pairs, source: ${sourceUrl}`);

    // Verify extraction
    if (pairs.length === 0) { console.log('  ⚠️  No pairs extracted, skipping'); continue; }

    const newHtml = buildDailyHtml({
      date: a.date,
      title: a.title,
      titleCn: a.titleCn,
      pairs,
      sourceUrl
    });

    await githubPut(path, newHtml, `feat: add vocabulary feature to ${a.date}`, existing.sha);
    console.log(`  ✅ ${path} pushed`);
  }

  // 3. Rebuild index.html
  console.log('\nRebuilding index.html...');
  const indexHtml = buildIndexHtml(articles);
  const existingIndex = await githubGet('index.html');
  await githubPut('index.html', indexHtml, 'feat: add wordbook link to homepage', existingIndex?.sha);
  console.log('✅ index.html updated');

  // 4. Push wordbook.html
  console.log('\nPushing wordbook.html...');
  const wordbookContent = fs.readFileSync('/workspace/wordbook.html', 'utf-8');
  const existingWb = await githubGet('wordbook.html');
  await githubPut('wordbook.html', wordbookContent, 'feat: add wordbook page with flashcard review', existingWb?.sha);
  console.log('✅ wordbook.html pushed');

  console.log('\n🎉 All done! Vocabulary feature deployed.');
  console.log('🌐 https://wherejiahe-bot.github.io/amruta-daily-archive/');
}

main().catch(err => {
  console.error('❌', err.message);
  process.exit(1);
});
