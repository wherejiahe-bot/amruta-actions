const https = require('https');
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
        else reject(new Error(`GET ${path} HTTP ${res.statusCode}`));
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function githubPut(path, content, message, sha) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({
      message, content: Buffer.from(content).toString('base64'), branch: BRANCH,
      ...(sha ? { sha } : {})
    });
    const options = {
      hostname: 'api.github.com',
      path: `/repos/${OWNER}/${REPO}/contents/${path}`,
      method: 'PUT',
      headers: {
        'Authorization': `token ${GITHUB_TOKEN}`, 'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'nodejs', 'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data)
      }
    };
    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        if (res.statusCode === 200 || res.statusCode === 201) resolve(JSON.parse(body));
        else reject(new Error(`PUT ${path} HTTP ${res.statusCode}: ${body.substring(0,200)}`));
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function extractPairs(html) {
  const pairs = [];
  const re = /<div class="pair">\s*<div class="en-text">([\s\S]*?)<\/div>\s*<div class="zh-text">([\s\S]*?)<\/div>\s*<\/div>/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    const en = m[1].replace(/<[^>]+>/g, '').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').trim();
    const zh = m[2].replace(/<[^>]+>/g, '').replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>').trim();
    if (en || zh) pairs.push([en, zh]);
  }
  return pairs;
}

function extractSource(html) {
  const m = html.match(/Source:\s*<a href="([^"]+)"/);
  return m ? m[1] : '';
}

function buildDailyHtml(article) {
  const { date, title, titleCn, pairs, sourceUrl } = article;
  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const [year, monthNum, dayNum] = date.split('-');
  const dateDisplay = `${monthNames[parseInt(monthNum)-1]} ${parseInt(dayNum)}, ${year}`;

  function wrapWords(text) {
    return escapeHtml(text).replace(/\b([A-Za-z]{2,}(?:'[a-z]+)?)\b/g, '<span class="w">$1</span>');
  }
  let contentBlocks = '';
  for (const [en, zh] of pairs) {
    contentBlocks += `\n  <div class="pair">\n    <div class="en-text">${wrapWords(en)}</div>\n    <div class="zh-text">${escapeHtml(zh)}</div>\n  </div>`;
  }
  const srcHost = sourceUrl ? ((sourceUrl.match(/https?:\/\/([^/]+)/) || [])[1] || sourceUrl) : 'amruta.today';
  const srcHref = sourceUrl || 'https://amruta.today/';

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(title)} \u00b7 ${date}</title>
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
.en-text .w{cursor:pointer;border-radius:2px;transition:background .12s}
.en-text .w:hover,.en-text .w:active{background:rgba(138,122,106,0.18)}
.en-text .w.saved{color:#8a7a6a;border-bottom:1.5px dotted #8a7a6a}
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
    <button class="btn-speak" id="pp-speak-btn" onclick="speakWord()" title="\u6717\u8bfb" style="display:none">\uD83D\uDD0A</button>
  </div>
  <div class="popup-defs" id="pp-defs"></div>
  <div class="popup-actions">
    <button class="btn-save" id="pp-save-btn" onclick="saveWord()">\u52a0\u5165\u5355\u8bcd\u672c</button>
    <button class="btn-close" onclick="closePopup()">\u5173\u95ed</button>
  </div>
</div>
<div class="container">
<nav class="nav-bar">
  <a href="../index.html">\u2190 \u8fd4\u56de\u9996\u9875</a>
  <a href="../wordbook.html" style="display:flex;align-items:center;gap:5px;font-size:13px;color:#8a7a6a;text-decoration:none" id="nav-wb-link">\uD83D\uDCD6 <span id="nav-wb-count"></span></a>
  <a href="https://amruta.today/" target="_blank">Amruta.today</a>
</nav>
<div class="article-header">
  <div class="article-date">${dateDisplay}</div>
  <h1>${escapeHtml(title)}</h1>
  <div class="chinese-title">${escapeHtml(titleCn)}</div>
  <div class="article-source">Source: <a href="${srcHref}" target="_blank">${srcHost}</a></div>
</div>
<div class="divider">\u25c7</div>
<div class="article-content">${contentBlocks}
</div>
<footer>
  <a href="../index.html">\u2190 \u8fd4\u56de\u9996\u9875</a>
  <span class="sep">\u00b7</span>
  <a href="../wordbook.html">\uD83D\uDCD6 \u5355\u8bcd\u672c</a>
  <span class="sep">\u00b7</span>
  <a href="https://amruta.today/" target="_blank">Amruta.today</a>
  <span class="sep">\u00b7</span>
  <a href="https://github.com/wherejiahe-bot/amruta-daily-archive" target="_blank">GitHub</a>
</footer>
</div>
<script>
const ARTICLE_DATE='${date}',WB_KEY='amruta_wordbook';
function getWordbook(){try{return JSON.parse(localStorage.getItem(WB_KEY)||'{}')}catch(e){return{}}}
function saveWordbook(wb){localStorage.setItem(WB_KEY,JSON.stringify(wb))}
function refreshSavedMarks(){
  const wb=getWordbook();
  document.querySelectorAll('.en-text .w').forEach(el=>{
    const w=el.textContent.replace(/[^A-Za-z']/g,'').toLowerCase();
    el.classList.toggle('saved',!!wb[w]);
  });
  const c=Object.keys(wb).length,n=document.getElementById('nav-wb-count');
  if(n)n.textContent=c>0?'\u5355\u8bcd\u672c '+c:'\u5355\u8bcd\u672c';
}
let currentWord='',currentData=null,currentAudioUrl='';
const POS_CN={noun:'\u540d\u8bcd',verb:'\u52a8\u8bcd',adjective:'\u5f62\u5bb9\u8bcd',adverb:'\u526f\u8bcd',pronoun:'\u4ee3\u8bcd',preposition:'\u4ecb\u8bcd',conjunction:'\u8fde\u8bcd',interjection:'\u611f\u53f9\u8bcd',article:'\u51a0\u8bcd',determiner:'\u9650\u5b9a\u8bcd',exclamation:'\u611f\u53f9\u8bcd',abbreviation:'\u7f29\u5199'};
function posLabel(p){return POS_CN[p]||p}
function speakWord(){if(currentAudioUrl){const a=new Audio(currentAudioUrl);a.play().catch(()=>synthSpeak());}else synthSpeak();}
function synthSpeak(){if(!window.speechSynthesis)return;const u=new SpeechSynthesisUtterance(currentWord);u.lang='en-US';u.rate=0.9;window.speechSynthesis.cancel();window.speechSynthesis.speak(u);}
async function translateDef(t){try{const r=await fetch('https://api.mymemory.translated.net/get?q='+encodeURIComponent(t)+'&langpair=en|zh',{signal:AbortSignal.timeout(4000)});if(!r.ok)return'';const d=await r.json();const s=d?.responseData?.translatedText||'';return(!s||s===t)?'':s;}catch(e){return''}}
function closePopup(){document.getElementById('word-popup').classList.remove('open');document.getElementById('word-popup-overlay').style.display='none';}
function openSheet(){const o=document.getElementById('word-popup-overlay'),p=document.getElementById('word-popup');o.style.display='block';p.getBoundingClientRect();p.classList.add('open');}
async function openWordPopup(el,word){
  currentWord=word.toLowerCase().replace(/['\u2019]/g,"'");currentData=null;currentAudioUrl='';
  document.getElementById('pp-word').textContent=word;
  document.getElementById('pp-phonetic').textContent='';
  document.getElementById('pp-speak-btn').style.display='none';
  document.getElementById('pp-defs').innerHTML='<div class="popup-loading">\u67e5\u8be2\u4e2d\u2026</div>';
  updateSaveBtn();openSheet();
  try{
    const ctrl=new AbortController(),t=setTimeout(()=>ctrl.abort(),6000);
    const res=await fetch('https://api.dictionaryapi.dev/api/v2/entries/en/'+encodeURIComponent(currentWord),{signal:ctrl.signal});
    clearTimeout(t);if(!res.ok)throw new Error('not found');
    const data=await res.json();currentData=data[0];
    const pts=currentData.phonetics||[],ph=currentData.phonetic||pts.find(p=>p.text)?.text||'';
    document.getElementById('pp-phonetic').textContent=ph;
    const ae=pts.find(p=>p.audio&&p.audio.length>0);
    if(ae)currentAudioUrl=ae.audio.startsWith('http')?ae.audio:'https:'+ae.audio;
    if(currentAudioUrl||window.speechSynthesis)document.getElementById('pp-speak-btn').style.display='';
    const ms=(currentData.meanings||[]).slice(0,3);
    let html='';
    ms.forEach((m,i)=>{const def=(m.definitions||[])[0];if(!def)return;html+='<div class="popup-def" id="pp-def-'+i+'"><div class="popup-pos">'+posLabel(m.partOfSpeech)+'</div><div class="popup-meaning-cn" id="pp-cn-'+i+'">'+def.definition+'</div>'+(def.example?'<div class="popup-example">'+def.example+'</div>':'')+'</div>';});
    document.getElementById('pp-defs').innerHTML=html||'<div class="popup-notfound">\u65e0\u91ca\u4e49</div>';
    ms.forEach((m,i)=>{const def=(m.definitions||[])[0];if(!def)return;translateDef(def.definition).then(cn=>{const el=document.getElementById('pp-cn-'+i);if(!el||!cn)return;el.textContent=cn;const s=document.createElement('div');s.className='popup-meaning-en';s.textContent=def.definition;el.after(s);});});
  }catch(e){
    document.getElementById('pp-phonetic').textContent='';
    if(window.speechSynthesis)document.getElementById('pp-speak-btn').style.display='';
    document.getElementById('pp-defs').innerHTML='<div class="popup-notfound">\u672a\u627e\u5230\u91ca\u4e49\uff0c\u53ef\u76f4\u63a5\u52a0\u5165\u5355\u8bcd\u672c</div>';
  }
}
function updateSaveBtn(){const wb=getWordbook(),btn=document.getElementById('pp-save-btn');if(wb[currentWord]){btn.textContent='\u2713 \u5df2\u5728\u5355\u8bcd\u672c';btn.classList.add('saved-state');}else{btn.textContent='\u52a0\u5165\u5355\u8bcd\u672c';btn.classList.remove('saved-state');}}
function saveWord(){const wb=getWordbook();if(wb[currentWord]){delete wb[currentWord];saveWordbook(wb);updateSaveBtn();refreshSavedMarks();return;}const phonetic=document.getElementById('pp-phonetic').textContent.trim();let defs=[];if(currentData&&currentData.meanings){currentData.meanings.slice(0,3).forEach((m,i)=>{const d=(m.definitions||[])[0];if(!d)return;const cnEl=document.getElementById('pp-cn-'+i);const cnText=cnEl?cnEl.textContent.trim():'';defs.push({pos:m.partOfSpeech,posCn:posLabel(m.partOfSpeech),def:d.definition,defCn:cnText!==d.definition?cnText:'',example:d.example||''});});}wb[currentWord]={word:currentWord,phonetic,defs,source:ARTICLE_DATE,savedAt:Date.now()};saveWordbook(wb);updateSaveBtn();refreshSavedMarks();}
document.addEventListener('click',e=>{const t=e.target;if(t.classList.contains('w')&&t.closest('.en-text')){e.stopPropagation();const word=t.textContent.replace(/[^A-Za-z']/g,'');if(word.length>=2)openWordPopup(t,word);}});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closePopup();});
refreshSavedMarks();
// Hash-based word highlight: #word-{word} scrolls to first occurrence and highlights the pair
(function(){
  const hash = location.hash;
  if (!hash || !hash.startsWith('#word-')) return;
  const target = decodeURIComponent(hash.slice(6)).toLowerCase();
  // Find first .w span matching the word
  const spans = document.querySelectorAll('.en-text .w');
  let found = null;
  for (const s of spans) {
    if (s.textContent.replace(/[^A-Za-z']/g,'').toLowerCase() === target) { found = s; break; }
  }
  if (!found) return;
  const pair = found.closest('.pair');
  if (!pair) return;
  // Mark the pair
  pair.id = 'highlight-pair';
  pair.style.cssText += ';border-radius:8px;transition:background .4s;';
  // Scroll
  setTimeout(() => {
    pair.scrollIntoView({ behavior: 'smooth', block: 'center' });
    pair.style.background = 'rgba(138,122,106,0.13)';
    // Mark the word spans
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

async function sleep(ms){return new Promise(r=>setTimeout(r,ms));}

async function main(){
  const af=await githubGet('articles.json');
  const articles=JSON.parse(Buffer.from(af.content,'base64').toString('utf-8'));
  console.log(`Found ${articles.length} articles`);
  const results=[];
  for(const a of articles){
    const path=`daily/${a.date}.html`;
    process.stdout.write(`\n${a.date}... `);
    try{
      const existing=await githubGet(path);
      if(!existing){console.log('not found, skip');results.push({date:a.date,status:'skipped'});continue;}
      const html=Buffer.from(existing.content,'base64').toString('utf-8');
      const pairs=extractPairs(html);
      const sourceUrl=extractSource(html)||a.source||'';
      if(pairs.length===0){console.log('no pairs, skip');results.push({date:a.date,status:'no_pairs'});continue;}
      const newHtml=buildDailyHtml({date:a.date,title:a.title,titleCn:a.titleCn,pairs,sourceUrl});
      await githubPut(path,newHtml,`rebuild: update popup for ${a.date}`,existing.sha);
      console.log(`OK (${pairs.length} pairs)`);
      results.push({date:a.date,status:'ok',pairs:pairs.length});
      await sleep(800);
    }catch(e){
      console.log(`ERROR: ${e.message}`);
      results.push({date:a.date,status:'error',error:e.message});
    }
  }
  console.log('\n=== Summary ===');
  results.forEach(r=>console.log(`  ${r.date}: ${r.status}${r.pairs?' ('+r.pairs+' pairs)':''}${r.error?' - '+r.error:''}`));
  const ok=results.filter(r=>r.status==='ok').length;
  console.log(`\nDone: ${ok}/${articles.length} rebuilt`);
}

main().catch(e=>{console.error('Fatal:',e.message);process.exit(1);});
