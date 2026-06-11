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

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function buildIndexHtml(articles) {
  // Sort by pushDate descending (newest push first)
  articles.sort((a, b) => (b.pushDate || b.date).localeCompare(a.pushDate || a.date));

  const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  let cards = '';
  for (const a of articles) {
    const pushDate = a.pushDate || a.date;
    const parts = pushDate.split('-');
    const pushMonth = monthNames[parseInt(parts[1]) - 1];
    const pushDay = parseInt(parts[2]);
    const pushYear = parts[0];

    cards += `
  <a href="daily/${a.date}.html" class="article-card">
    <div class="date-badge">
      <span class="month">${pushMonth}</span>
      <span class="day">${pushDay}</span>
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
  <a href="https://amruta.today/" class="rss-link" target="_blank">Amruta.today →</a>
</div>
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

async function main() {
  // Fetch articles.json
  const existing = await githubGet('articles.json');
  if (!existing) { console.error('articles.json not found'); process.exit(1); }
  const articlesSha = existing.sha;
  let articles = JSON.parse(Buffer.from(existing.content, 'base64').toString('utf-8'));

  // Map of known pushDates from commit history
  const pushDateMap = {
    '1983-06-06': '2026-06-06',
    '1985-06-05': '2026-06-06',
    '1982-06-07': '2026-06-07',
    '2026-06-08': '2026-06-07',  // date was mis-filled; real push was 06-07
    '1980-06-09': '2026-06-08',
    '1997-06-10': '2026-06-10',
  };

  // Add pushDate to each article
  articles = articles.map(a => ({
    ...a,
    pushDate: pushDateMap[a.date] || a.date
  }));

  console.log('Updated articles with pushDate:');
  articles.forEach(a => console.log(`  ${a.date} → pushDate: ${a.pushDate}`));

  // Push updated articles.json
  await githubPut('articles.json', JSON.stringify(articles, null, 2), 'fix: add pushDate field for correct navigation sort order', articlesSha);
  console.log('✅ articles.json updated with pushDate');

  // Rebuild index.html
  const indexHtml = buildIndexHtml(articles);
  const existingIndex = await githubGet('index.html');
  const indexSha = existingIndex ? existingIndex.sha : null;
  await githubPut('index.html', indexHtml, 'fix: sort navigation by pushDate (newest push first)', indexSha);
  console.log('✅ index.html rebuilt, sorted by pushDate');
}

main().catch(err => {
  console.error('❌ Failed:', err.message);
  process.exit(1);
});
