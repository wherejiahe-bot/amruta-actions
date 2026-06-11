"""
Step 2: Login to sahaja.live, search for Chinese translation.
Follows the original coordinator.py logic:
  1. Login: get nonce from /login/ page, POST credentials
  2. Search: use cookies to search WordPress API by title keywords + date
  3. Fetch post: get bilingual content
Reads /tmp/article_raw.json, outputs /tmp/pairs.json, /tmp/email_body.html
"""
import json, re, os, datetime as dt, ssl
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
from http.cookiejar import CookieJar

ctx = ssl.create_default_context()

with open("/tmp/article_raw.json", encoding="utf-8") as f:
    article = json.load(f)

date_str = article["date"]
title_en = article["title"]
content = article["content"]
link = article.get("link", "")

sahaja_link = None
pairs = []
title_cn = title_en

# --- Helpers (from original coordinator.py) ---

def is_zh_block(text):
    cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return cn >= 3

def has_chinese(pl):
    return any(zh.strip() for _, zh in pl)

def polish_title(zh):
    zh = zh.replace('承担起', '肩负起').replace('承担', '肩负')
    zh = re.sub(r'(来起作用的|起作用的|来发挥作用的)$', '', zh).strip()
    zh = re.sub(r'^(通过你们|通过我们|通过|在于|由于|因为|当你们|当我们)', '', zh).strip()
    return zh

def extract_title_cn(pl, en_title):
    keywords = [w.strip('.,!?"\'-()').lower() for w in en_title.split() if len(w.strip('.,!?"\'-()')) > 2]
    if not keywords: return None
    for en, zh in pl:
        if not zh.strip(): continue
        if all(kw in en.lower() for kw in keywords):
            for part in re.split(r'[，。]', zh):
                p = part.strip()
                if 4 < len(p) <= 25:
                    return polish_title(p)
    return None

def parse_sahaja_text(full_text):
    """Parse pair EN/ZH from sahaja.live HTML content (simplified block-based)."""
    def is_meta_block(b):
        if is_zh_block(b): return True
        if re.match(r'^\d{1,2}\s+\w+\s+\d{4}', b): return True
        if re.search(r'\d{4}年', b): return True
        if any(kw in b for kw in ['Talk Language', 'Transcript', 'VERIFIED', 'NEEDED',
                                   '以下翻译', '供大家参考', 'subtitles', 'Subtitles']):
            return True
        if (re.search(r'\((?:United States|USA|UK|India|France|Italy|Australia|Germany|Spain)\)', b)
                and not re.search(r'\b(is|are|was|were|have|has|will|can|should|must|know|think|feel|decide|come|go)\b', b, re.I)):
            return True
        return False

    blocks = [b.strip() for b in re.split(r'\n{2,}', full_text) if b.strip()]
    result = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if not is_meta_block(b) and len(b) > 40 and re.search(r'[A-Z][a-z]', b):
            break
        i += 1

    while i < len(blocks):
        en_block = blocks[i]
        if is_zh_block(en_block):
            i += 1
            continue
        if i + 1 < len(blocks) and is_zh_block(blocks[i + 1]):
            result.append([en_block, blocks[i + 1]])
            i += 2
        else:
            result.append([en_block, ""])
            i += 1

    return result

# --- Step 2a: Check cache ---
SAHAJA_CACHE = "/tmp/sahaja_cache.json"
print("[2a] Checking cache...", flush=True)
if os.path.exists(SAHAJA_CACHE):
    try:
        with open(SAHAJA_CACHE) as f:
            cached = json.load(f)
        if cached.get("date") == date_str and cached.get("full_text"):
            candidate = parse_sahaja_text(cached["full_text"])
            if has_chinese(candidate):
                pairs = candidate
                sahaja_link = cached.get("source_url", link)
                ext = extract_title_cn(pairs, title_en)
                if ext: title_cn = ext
                print(f"[2a] Cache hit: {len(pairs)} pairs", flush=True)
    except Exception as e:
        print(f"[2a] Cache error: {e}", flush=True)

# --- Step 2b: Login to sahaja.live (original coordinator approach) ---
if not pairs:
    UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    SAHAJA_EMAIL = os.environ.get("SAHAJA_EMAIL", "17338708029")
    SAHAJA_PASSWORD = os.environ.get("SAHAJA_PASSWORD", "jsm108108")

    # Build cookie-handling opener
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))

    print("[2b] Getting login page for nonce...", flush=True)
    try:
        login_req = Request("https://www.sahaja.live/login/",
                            headers={"User-Agent": UA})
        login_resp = opener.open(login_req, timeout=30)
        login_html = login_resp.read().decode("utf-8", errors="replace")

        # Extract nonce
        nonce_m = re.search(r'piereg_login_form_nonce.*?value="([^"]+)"', login_html, re.DOTALL)
        if not nonce_m:
            print("[2b] ❌ Cannot find login nonce (Cloudflare blocking?)", flush=True)
        else:
            nonce = nonce_m.group(1)
            print(f"[2b] Got nonce: {nonce[:10]}...", flush=True)

            # POST login
            post_data = urlencode({
                "log": SAHAJA_EMAIL,
                "pwd": SAHAJA_PASSWORD,
                "rememberme": "forever",
                "piereg_login_form_nonce": nonce,
                "_wp_http_referer": "/login/",
                "wp-submit": "Log In",
                "redirect_to": "",
                "testcookie": "1"
            }).encode()
            login_post_req = Request("https://www.sahaja.live/login/",
                                     data=post_data,
                                     headers={
                                         "User-Agent": UA,
                                         "Referer": "https://www.sahaja.live/login/",
                                         "Content-Type": "application/x-www-form-urlencoded"
                                     })
            login_post_resp = opener.open(login_post_req, timeout=30)
            login_post_resp.read()  # consume response
            print("[2b] ✅ Login successful", flush=True)

            # --- Search by date first (MM-DD) ---
            mm_dd = date_str[5:]  # e.g. "06-11"
            search_url = f"https://www.sahaja.live/wp-json/wp/v2/posts?search={mm_dd}&per_page=20"
            print(f"[2b] Date search: {mm_dd}", flush=True)
            search_req = Request(search_url, headers={"User-Agent": UA})
            search_resp = opener.open(search_req, timeout=30)
            posts_text = search_resp.read().decode("utf-8")

            if posts_text.strip():
                posts = json.loads(posts_text)
                if isinstance(posts, list):
                    print(f"[2b] Found {len(posts)} posts from date search", flush=True)
                    for p in posts:
                        pid = p['id']
                        # Fetch post content
                        post_url = f"https://www.sahaja.live/wp-json/wp/v2/posts/{pid}"
                        post_req = Request(post_url, headers={"User-Agent": UA})
                        post_resp = opener.open(post_req, timeout=30)
                        pd = json.loads(post_resp.read().decode("utf-8"))

                        html_text = pd.get('content', {}).get('rendered', '')
                        text_raw = re.sub(r'<[^>]+>', '\n', html_text)
                        for ent, rep in [('&amp;','&'),('&#038;','&'),('&#8211;','-'),('&#8217;',"'"),
                                          ('&#8216;',"'"),('&#8220;','"'),('&#8221;','"'),('&nbsp;',' ')]:
                            text_raw = text_raw.replace(ent, rep)

                        raw_title = pd.get('title', {}).get('rendered', '')
                        t_cn = re.sub(r'^\d{4}-\d{2}-\d{2}\s*', '', raw_title).strip()
                        s_link = pd.get('link', '')

                        candidate = parse_sahaja_text(text_raw)
                        if has_chinese(candidate):
                            pairs = candidate
                            sahaja_link = s_link
                            ext = extract_title_cn(pairs, title_en)
                            if ext: title_cn = ext
                            print(f"[2b] ✅ HIT post_id={pid}, pairs={len(pairs)}", flush=True)
                            # Save cache
                            try:
                                with open(SAHAJA_CACHE, "w") as f:
                                    json.dump({"date": date_str, "full_text": text_raw, "source_url": sahaja_link}, f)
                            except:
                                pass
                            break
                        else:
                            print(f"[2b] post_id={pid}: no Chinese, skip", flush=True)

        if not pairs:
            print("[2b] Date search found nothing, trying keyword search...", flush=True)
            # Try keyword search
            kw = " ".join([w for w in title_en.split() if len(w) > 2][:5])
            if kw:
                search_url = f"https://www.sahaja.live/wp-json/wp/v2/posts?search={kw.replace(' ', '%20')}&per_page=5"
                print(f"[2b] Keyword: {kw}", flush=True)
                search_req = Request(search_url, headers={"User-Agent": UA})
                search_resp = opener.open(search_req, timeout=30)
                posts = json.loads(search_resp.read().decode("utf-8"))
                if isinstance(posts, list):
                    for p in posts:
                        pid = p['id']
                        post_url = f"https://www.sahaja.live/wp-json/wp/v2/posts/{pid}"
                        post_req = Request(post_url, headers={"User-Agent": UA})
                        post_resp = opener.open(post_req, timeout=30)
                        pd = json.loads(post_resp.read().decode("utf-8"))

                        html_text = pd.get('content', {}).get('rendered', '')
                        text_raw = re.sub(r'<[^>]+>', '\n', html_text)
                        for ent, rep in [('&amp;','&'),('&#038;','&'),('&#8211;','-'),('&#8217;',"'"),
                                          ('&#8216;',"'"),('&#8220;','"'),('&#8221;','"'),('&nbsp;',' ')]:
                            text_raw = text_raw.replace(ent, rep)

                        s_link = pd.get('link', '')
                        candidate = parse_sahaja_text(text_raw)
                        if has_chinese(candidate):
                            pairs = candidate
                            sahaja_link = s_link
                            print(f"[2b] Keyword HIT post_id={pid}", flush=True)
                            break

    except Exception as e:
        print(f"[2b] Login/search error: {e}", flush=True)

# --- Fallback: English only ---
if not pairs:
    print("[2b] No Chinese found - English only", flush=True)
    paras = [p.strip() for p in content.split('\n') if p.strip()]
    pairs = [[p, ""] for p in paras]

# --- Build email HTML ---
print(f"[2c] Building email... ({len(pairs)} pairs, {sum(1 for _,zh in pairs if zh)} with Chinese)", flush=True)
pair_html = ""
for en, zh in pairs:
    en_s = str(en).strip() if en else ""
    zh_s = str(zh).strip() if zh else ""
    if not en_s and not zh_s: continue
    if en_s and zh_s:
        pair_html += '<p style="color:#888;font-size:0.85em;margin:0 0 2px 0;">' + en_s + '</p><p style="margin:0 0 14px 0;">' + zh_s + '</p>\n'
    elif en_s:
        pair_html += '<p style="color:#888;font-size:0.85em;margin:0 0 14px 0;">' + en_s + '</p>\n'

try:
    dd = dt.datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y年%-m月%-d日")
except:
    dd = date_str

final_link = sahaja_link or link
email_html = f'''<!DOCTYPE html>
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
  <a href="https://amruta.today/" style="color:#aaa;">https://amruta.today/</a><br>
  <a href="{final_link}" style="color:#aaa;">{final_link}</a>
</p>
</body>
</html>'''

with open("/tmp/pairs.json", "w", encoding="utf-8") as f:
    json.dump(pairs, f, ensure_ascii=False, indent=2)
with open("/tmp/email_body.html", "w", encoding="utf-8") as f:
    f.write(email_html)
with open("/tmp/sahaja_link.txt", "w", encoding="utf-8") as f:
    f.write(final_link or "")

print("OK Step2: " + str(len(pairs)) + " pairs, " + str(sum(1 for _,zh in pairs if zh)) + " with Chinese", flush=True)
