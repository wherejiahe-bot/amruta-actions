"""
Step 2: Search sahaja.live for Chinese translation.
Uses public WordPress REST API with urllib.request (NOT curl).
Search strategy: date prefix first, then keyword fallback.
Reads /tmp/article_raw.json, outputs /tmp/pairs.json, /tmp/email_body.html
"""
import json, re, os, datetime as dt, urllib.request, ssl, sys

ctx = ssl.create_default_context()

with open("/tmp/article_raw.json", encoding="utf-8") as f:
    article = json.load(f)

date_str = article["date"]
title_en = article["title"]
content = article["content"]
link = article.get("link", "")

SAHAJA_CACHE = "/tmp/sahaja_cache.json"
sahaja_link = None
pairs = []
title_cn = title_en

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
    """Simplified parser: skip header, then pair EN lines with following ZH lines."""
    lines_raw = full_text.split('\n')
    lines = []
    for l in lines_raw:
        l = l.strip()
        if l and l != '&nbsp;':
            lines.append(l)
    result = []
    # Skip header - find first long English sentence
    start = 0
    for i, l in enumerate(lines):
        cn = sum(1 for c in l if '\u4e00' <= c <= '\u9fff')
        if cn == 0 and len(l) > 40 and re.search(r'[A-Z][a-z]', l):
            start = i
            break
    # Pair EN followed by ZH
    i = start
    while i < len(lines):
        en = lines[i]
        cn_en = sum(1 for c in en if '\u4e00' <= c <= '\u9fff')
        if cn_en > 0:
            i += 1
            continue
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            cn_nxt = sum(1 for c in nxt if '\u4e00' <= c <= '\u9fff')
            if cn_nxt >= 3:
                result.append([en, nxt])
                i += 2
                continue
        result.append([en, ""])
        i += 1
    return result

def api_get(url):
    """Fetch JSON from a URL using urllib.request with standard headers."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; AmrutaBot/1.0)'})
    resp = urllib.request.urlopen(req, context=ctx, timeout=30)
    raw = resp.read().decode('utf-8')
    print(f"[api_get] {url[:80]} -> {len(raw)} bytes", flush=True)
    if not raw.strip():
        print("[api_get] EMPTY RESPONSE!", flush=True)
        return None
    return json.loads(raw)

def fetch_post(post_id):
    """Fetch a single post by ID, return (pairs, source_link, title_cn, text_raw)."""
    try:
        pd = api_get(f'https://www.sahaja.live/wp-json/wp/v2/posts/{post_id}')
    except Exception as e:
        print(f"[fetch_post] API error for post {post_id}: {e}", flush=True)
        return [], "", "", ""
    if not pd:
        return [], "", "", ""
    html = pd.get('content', {}).get('rendered', '')
    text_raw = re.sub(r'<[^>]+>', '\n', html)
    for ent, rep in [('&amp;','&'),('&#038;','&'),('&#8211;','-'),('&#8217;',"'"),
                      ('&#8216;',"'"),('&#8220;','"'),('&#8221;','"'),('&nbsp;',' ')]:
        text_raw = text_raw.replace(ent, rep)
    raw_title = pd.get('title', {}).get('rendered', '')
    t_cn = re.sub(r'^\d{4}-\d{2}-\d{2}\s*', '', raw_title).strip()
    s_link = pd.get('link', '')
    candidate = parse_sahaja_text(text_raw)
    print(f"[fetch_post] post_id={post_id}, pairs={len(candidate)}, title_cn={t_cn}", flush=True)
    return candidate, s_link, t_cn, text_raw

# --- 2a: Try cache ---
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

# --- 2b: Date-based search (most reliable for sahaja.live) ---
if not pairs:
    mm_dd = date_str[5:]  # e.g. "06-11"
    search_url = f"https://www.sahaja.live/wp-json/wp/v2/posts?search={mm_dd}&per_page=20"
    print(f"[2b] Date search: {search_url}", flush=True)
    try:
        posts = api_get(search_url)
        if posts and isinstance(posts, list):
            print(f"[2b] Date search found {len(posts)} posts", flush=True)
            for p in posts:
                pid = p['id']
                candidate, s_link, t_cn, text_raw = fetch_post(pid)
                if has_chinese(candidate):
                    pairs = candidate
                    sahaja_link = s_link
                    ext = extract_title_cn(pairs, title_en)
                    if ext: title_cn = ext
                    print(f"[2b] HIT post_id={pid}, pairs={len(pairs)}, title_cn={title_cn}", flush=True)
                    try:
                        with open(SAHAJA_CACHE, "w") as f:
                            json.dump({"date": date_str, "full_text": text_raw, "source_url": sahaja_link}, f)
                    except:
                        pass
                    break
                else:
                    print(f"[2b] post_id={pid}: no Chinese, skip", flush=True)
        else:
            print(f"[2b] No posts found from date search", flush=True)
    except Exception as e:
        print(f"[2b] Date search error: {e}", flush=True)

# --- 2c: Keyword fallback (if date search failed) ---
if not pairs:
    print("[2c] Fallback: keyword search...", flush=True)
    search_words = " ".join([w for w in title_en.split() if len(w) > 2][:5])
    if search_words:
        search_url = f"https://www.sahaja.live/wp-json/wp/v2/posts?search={search_words.replace(' ', '%20')}&per_page=5"
        print(f"[2c] {search_url}", flush=True)
        try:
            posts = api_get(search_url)
            if posts and isinstance(posts, list):
                print(f"[2c] Found {len(posts)} posts", flush=True)
                for p in posts:
                    pid = p['id']
                    candidate, s_link, t_cn, text_raw = fetch_post(pid)
                    if has_chinese(candidate):
                        pairs = candidate
                        sahaja_link = s_link
                        ext = extract_title_cn(pairs, title_en)
                        if ext: title_cn = ext
                        print(f"[2c] HIT post_id={pid}, pairs={len(pairs)}", flush=True)
                        break
                    else:
                        print(f"[2c] post_id={pid}: no Chinese, skip", flush=True)
        except Exception as e:
            print(f"[2c] Search error: {e}", flush=True)

    # Individual keyword fallback
    if not pairs:
        print("[2c] Fallback: individual keywords...", flush=True)
        for w in [w for w in title_en.split() if len(w) > 2][:3]:
            kw_url = f"https://www.sahaja.live/wp-json/wp/v2/posts?search={w}&per_page=5"
            try:
                posts = api_get(kw_url)
                if posts and isinstance(posts, list):
                    for p in posts:
                        pid = p['id']
                        candidate, s_link, t_cn, text_raw = fetch_post(pid)
                        if has_chinese(candidate):
                            pairs = candidate
                            sahaja_link = s_link
                            ext = extract_title_cn(pairs, title_en)
                            if ext: title_cn = ext
                            print(f"[2c] Keyword HIT post_id={pid}", flush=True)
                            break
                    if pairs: break
            except:
                pass

# --- Fallback: English only ---
if not pairs:
    print("[2b] No Chinese found - English only", flush=True)
    paras = [p.strip() for p in content.split('\n') if p.strip()]
    pairs = [[p, ""] for p in paras]

# --- Build email HTML ---
print(f"[2d] Building email... ({len(pairs)} pairs, {sum(1 for _,zh in pairs if zh)} with Chinese)", flush=True)
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
email_html = '''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:'Helvetica Neue',Arial,sans-serif;max-width:680px;margin:0 auto;padding:24px 16px;color:#222;line-height:1.7;">
<h2 style="margin:0 0 4px 0;font-size:1.25em;font-weight:700;">''' + title_cn + '''</h2>
<p style="color:#888;font-size:0.85em;margin:0 0 4px 0;font-style:italic;">''' + title_en + '''</p>
<p style="color:#aaa;font-size:0.8em;margin:0 0 24px 0;">''' + dd + '''</p>
<hr style="border:none;border-top:1px solid #eee;margin:0 0 24px 0;">
''' + pair_html + '''
<hr style="border:none;border-top:1px solid #eee;margin:24px 0 16px 0;">
<p style="color:#aaa;font-size:0.8em;margin:0;word-break:break-all;">
  <a href="https://amruta.today/" style="color:#aaa;">https://amruta.today/</a><br>
  <a href="''' + final_link + '''" style="color:#aaa;">''' + final_link + '''</a>
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
