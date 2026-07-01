"""
Amruta Daily Push Workflow Runner
Run by GitHub Actions daily at 04:00 Beijing time.

Full pipeline: fetch article → search sahaja.live for Chinese translation → 
sentence alignment → push bilingual HTML to GitHub → send email notification.
"""
import urllib.request, json, re, datetime, subprocess, os, smtplib, sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

SAHAJA_CACHE = "/tmp/sahaja_cache.json"
COOKIE_FILE = "/tmp/sahaja_session.txt"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def log(s):
    print(f"[{datetime.datetime.utcnow().strftime('%H:%M:%S')}] {s}")

# ─── Stage 1: Fetch today's article from amruta.today ───
log("=== Stage 1: Fetch article ===")
cn = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
month = str(cn.month).zfill(2)
day = str(cn.day).zfill(2)
date_str = cn.strftime("%Y-%m-%d")

url = f"https://amruta.today/wp-json/everyday-ui/v1/talks/lang/en/month/{month}/day/{day}"
log(f"Fetching: {url}")
req = urllib.request.Request(url, headers={"User-Agent": UA})
with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read().decode())
if not data:
    raise ValueError(f"No article for {date_str}")
item = data[0]
title_en = item.get("title", "")
if isinstance(title_en, dict): title_en = title_en.get("rendered", "")
content_raw = item.get("content", "")
if isinstance(content_raw, dict): content_raw = content_raw.get("rendered", "")
content_text = re.sub(r"<[^>]+>", "", content_raw).strip()
link = item.get("link", "")
# amruta.today 为永久链接，amruta.org 为旧短暂链接
link = link.replace("www.amruta.org", "amruta.today") if link else ""
log(f"Title: {title_en}")

article = {"date": date_str, "title": title_en, "content": content_text, "link": link}

# ─── Stage 2: Search sahaja.live for Chinese translation ───
log("=== Stage 2: Search Chinese translation ===")

pairs = []            # [(en, zh), ...]
sahaja_link = None     # source URL on sahaja.live
title_cn = title_en    # Chinese title (fallback to English)

sahaja_email = os.environ.get("SAHAJA_EMAIL", "")
sahaja_pass = os.environ.get("SAHAJA_PASSWORD", "")

def is_zh_block(text):
    cn_count = sum(1 for c in text if '一' <= c <= '龥')
    return cn_count >= 3

def parse_sahaja_text(full_text):
    """Parse sahaja.live full text into [(en, zh), ...] pairs."""
    blocks = [b.strip() for b in re.split(r'\n{2,}', full_text) if b.strip()]
    
    def is_meta(b):
        if is_zh_block(b): return True
        if re.match(r'^\d{1,2}\s+\w+\s+\d{4}', b): return True
        if re.search(r'\d{4}年', b): return True
        if any(kw in b for kw in ['Talk Language', 'Transcript', 'VERIFIED', 'NEEDED',
                                   'subtitles', 'Subtitles', '以下翻译', '供大家参考']): return True
        if re.search(r'\((?:United States|USA|UK|India|France|Italy)\)', b) and not re.search(r'\b(is|are|was|were|have|has|will|can|should)\b', b, re.I): return True
        return False

    result = []
    i = 0
    while i < len(blocks):
        if not is_meta(blocks[i]) and len(blocks[i]) > 40 and re.search(r'[A-Z][a-z]', blocks[i]):
            break
        i += 1
    while i < len(blocks):
        en = blocks[i]
        if is_zh_block(en): i += 1; continue
        if i + 1 < len(blocks) and is_zh_block(blocks[i+1]):
            result.append([en, blocks[i+1]]); i += 2
        else:
            result.append([en, ""]); i += 1
    return result

def has_chinese(pl):
    return any(zh.strip() for _, zh in pl)

def extract_title_cn(pl, en_title):
    """Find Chinese title from translation pairs."""
    keywords = [w.strip(".,!?'\"-()").lower() for w in en_title.split() if len(w.strip(".,!?'\"-()")) > 2]
    if not keywords: return None
    for en, zh in pl:
        if not zh.strip(): continue
        if all(kw in en.lower() for kw in keywords):
            for part in re.split(r'[，。]', zh):
                p = part.strip()
                if 4 < len(p) <= 25:
                    return re.sub(r'^(通过你们|通过我们|通过|在于|由于|因为|当你们|当我们)', '', p).strip()
    return None

# Try cache first
if os.path.exists(SAHAJA_CACHE):
    with open(SAHAJA_CACHE) as f:
        cached = json.load(f)
    if cached.get("date") == date_str and cached.get("full_text"):
        candidate = parse_sahaja_text(cached["full_text"])
        if has_chinese(candidate):
            pairs = candidate
            sahaja_link = cached.get("source_url", link)
            ext = extract_title_cn(pairs, title_en)
            if ext: title_cn = ext
            log(f"Using cached sahaja content, pairs: {len(pairs)}")

# Try online search (need credentials)
if not pairs and sahaja_email and sahaja_pass:
    log("Searching sahaja.live for Chinese translation...")
    if os.path.exists(COOKIE_FILE): os.remove(COOKIE_FILE)
    
    # Get login nonce
    r = subprocess.run(["curl", "-s", "-c", COOKIE_FILE, "-H", f"User-Agent: {UA}",
                       "https://www.sahaja.live/login/"], capture_output=True, text=True)
    nonce_m = re.search(r'piereg_login_form_nonce.*?value="([^"]+)"', r.stdout, re.DOTALL)
    
    if nonce_m:
        nonce = nonce_m.group(1)
        # Login
        subprocess.run(["curl", "-s", "-L", "-b", COOKIE_FILE, "-c", COOKIE_FILE,
                       "-H", f"User-Agent: {UA}", "-H", "Referer: https://www.sahaja.live/login/",
                       "--data-urlencode", f"log={sahaja_email}",
                       "--data-urlencode", f"pwd={sahaja_pass}",
                       "-d", f"rememberme=forever&piereg_login_form_nonce={nonce}&_wp_http_referer=%2Flogin%2F&wp-submit=Log+In&redirect_to=&testcookie=1",
                       "https://www.sahaja.live/login/"], capture_output=True, text=True)
        log("Logged in to sahaja.live")
        
        # Search posts
        search_words = " ".join([w for w in title_en.split() if len(w) > 2][:5])
        r = subprocess.run(["curl", "-s", "-b", COOKIE_FILE, "-H", f"User-Agent: {UA}",
                           f"https://www.sahaja.live/wp-json/wp/v2/posts?search={search_words.replace(' ', '+')}&per_page=10"],
                          capture_output=True, text=True)
        try:
            posts = json.loads(r.stdout)
            if isinstance(posts, list):
                for p in posts[:5]:
                    pid = p["id"]
                    r2 = subprocess.run(["curl", "-s", "-b", COOKIE_FILE, "-H", f"User-Agent: {UA}",
                                        f"https://www.sahaja.live/wp-json/wp/v2/posts/{pid}"],
                                       capture_output=True, text=True)
                    pd = json.loads(r2.stdout)
                    html = pd.get("content", {}).get("rendered", "")
                    text_raw = re.sub(r"<[^>]+>", "\n", html)
                    for ent, rep in [("&amp;","&"),("&#8217;","'"),("&nbsp;"," ")]:
                        text_raw = text_raw.replace(ent, rep)
                    candidate = parse_sahaja_text(text_raw)
                    if has_chinese(candidate):
                        pairs = candidate
                        sahaja_link = pd.get("link", "")
                        ext = extract_title_cn(pairs, title_en)
                        if ext: title_cn = ext
                        # Cache it
                        with open(SAHAJA_CACHE, "w") as f:
                            json.dump({"date": date_str, "full_text": text_raw, "source_url": sahaja_link}, f)
                        log(f"Found post_id={pid}, pairs: {len(pairs)}")
                        break
                    else:
                        log(f"post_id={pid}: no Chinese, skip")
        except Exception as e:
            log(f"Search failed: {e}")

# ─── Fallback: English only ───
if not pairs:
    log("No Chinese translation found - using English only")
    paras = [p.strip() for p in content_text.split("\n") if p.strip()]
    pairs = [[p, ""] for p in paras]

# ─── Sentence-level alignment (if we have Chinese pairs) ───
log(f"=== Stage 3: Build pairs ({len(pairs)} pairs) ===")

# ─── Stage 4: Push to GitHub Pages ───
log("=== Stage 4: Push to amruta-daily-archive ===")

script_dir = os.path.dirname(os.path.abspath(__file__))
source_url = sahaja_link or link

payload = {"date": date_str, "title": title_en, "titleCn": title_cn,
           "sourceUrl": source_url, "pairs": pairs}
with open("/tmp/push_input.json", "w") as f:
    json.dump(payload, f)

r = subprocess.run(
    ["node", os.path.join(script_dir, "push_article.js"), "--file", "/tmp/push_input.json"],
    capture_output=True, text=True, timeout=120
)
print(r.stdout)
if r.returncode != 0:
    raise RuntimeError(r.stderr)
archive_url = f"https://wherejiahe-bot.github.io/amruta-daily-archive/daily/{date_str}.html"
log(f"Pushed: {archive_url}")

# ─── Stage 5: Send email ───
log("=== Stage 5: Send email ===")
smtp_user = os.environ.get("SMTP_USER", "")
smtp_pass = os.environ.get("SMTP_PASS", "")

if smtp_user and smtp_pass:
    try:
        dd = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y年%-m月%-d日")
    except:
        dd = date_str

    pair_html = ""
    for en, zh in pairs:
        if en and zh:
            pair_html += f'<p style="color:#888;font-size:0.85em;margin:0 0 2px 0;">{en}</p><p style="margin:0 0 14px 0;">{zh}</p>'
        elif en:
            pair_html += f'<p style="color:#888;font-size:0.85em;margin:0 0 14px 0;">{en}</p>'
        elif zh:
            pair_html += f'<p style="margin:0 0 14px 0;">{zh}</p>'

    email_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:'Helvetica Neue',Arial,sans-serif;max-width:680px;margin:0 auto;padding:24px 16px;color:#222;line-height:1.7;">

<h2 style="margin:0 0 4px 0;font-size:1.25em;font-weight:700;">{title_cn}</h2>
<p style="color:#888;font-size:0.85em;margin:0 0 4px 0;font-style:italic;">{title_en}</p>
<p style="color:#aaa;font-size:0.8em;margin:0 0 24px 0;">{dd}</p>

<hr style="border:none;border-top:1px solid #eee;margin:0 0 24px 0;">

{pair_html}

<hr style="border:none;border-top:1px solid #eee;margin:24px 0 16px 0;">
<p style="color:#aaa;font-size:0.8em;margin:0;word-break:break-all;">
  <a href="{link}" style="color:#aaa;">{link}</a>
  <br>
  <a href="{sahaja_link or 'https://sahaja.live/'}" style="color:#aaa;">{sahaja_link or 'https://sahaja.live/'}</a>
</p>

</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(f"每日 Shri Mataji 讲话推送 - {date_str}", "utf-8")
    msg["From"] = formataddr(("Shri Mataji 每日讲话", smtp_user))
    msg["To"] = smtp_user
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    with smtplib.SMTP("smtp.qq.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [smtp_user], msg.as_string())
    log("Email sent!")
else:
    log("SMTP not configured, skip email")

log(f"\n=== All done: {archive_url} ===")
