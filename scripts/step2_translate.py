"""
Step 2: Search sahaja.live for Chinese translation.
Reads /tmp/article_raw.json, outputs /tmp/pairs.json, /tmp/email_body.html, /tmp/sahaja_link.txt

Three sub-steps:
  2a. Try local cache
  2b. Online search (login to sahaja.live)
  2c. Sentence alignment between amruta EN and sahaja ZH
  2d. Build email HTML
"""
import json, re, subprocess as sp, os, datetime as dt

with open("/tmp/article_raw.json", encoding="utf-8") as f:
    article = json.load(f)

date_str = article["date"]
title_en = article["title"]
content = article["content"]
link = article.get("link", "")

SAHAJA_CACHE = "/tmp/sahaja_cache.json"
COOKIE_FILE = "/tmp/sahaja_session.txt"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

sahaja_link = None
pairs = []
title_cn = title_en

# ─── Helpers ───
def is_zh_block(text):
    cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return cn >= 3

def polish_title(zh):
    zh = zh.replace('承担起', '肩负起').replace('承担', '肩负')
    zh = re.sub(r'(来起作用的|起作用的|来发挥作用的)$', '', zh).strip()
    zh = re.sub(r'^(通过你们|通过我们|通过|在于|由于|因为|当你们|当我们)', '', zh).strip()
    return zh

def extract_title_cn_from_pairs(pairs_list, en_title):
    keywords = [w.strip('.,!?"\'-()').lower() for w in en_title.split() if len(w.strip('.,!?"\'-()')) > 2]
    if not keywords: return None
    for en, zh in pairs_list:
        if not zh.strip(): continue
        if all(kw in en.lower() for kw in keywords):
            en_sents = re.split(r'[.,]', en)
            zh_sents = re.split(r'[，。]', zh)
            for i, es in enumerate(en_sents):
                if all(kw in es.lower() for kw in keywords):
                    ratio = i / max(len(en_sents) - 1, 1)
                    zh_idx = round(ratio * (len(zh_sents) - 1))
                    zh_part = zh_sents[zh_idx].strip() if zh_idx < len(zh_sents) else ""
                    if len(zh_part) > 4: return polish_title(zh_part)
            for part in re.split(r'[，。；]', zh):
                part = part.strip()
                if 4 < len(part) <= 20: return polish_title(part)
    return None

# ─── 2a: Parse sahaja text ───
def parse_sahaja_full_text(full_text):
    blocks = [b.strip() for b in re.split(r'\n{2,}', full_text) if b.strip()]
    def is_meta_block(b):
        if is_zh_block(b): return True
        if re.match(r'^\d{1,2}\s+\w+\s+\d{4}', b): return True
        if re.search(r'\d{4}年', b): return True
        if any(kw in b for kw in ['Talk Language', 'Transcript', 'VERIFIED', 'NEEDED', '以下翻译']): return True
        if re.search(r'\((?:United States|USA|UK|India|France|Italy|Australia|Germany|Spain)\)', b) and not re.search(r'\b(is|are|was|were|have|has|will|can|should|must|know)\b', b, re.I): return True
        if re.search(r'\b(19|20)\d{2}\b', b) and re.search(r'\b(USA|UK|India|France|Italy|Australia|Camp|Puja)\b', b) and not re.search(r'\b(is|are|was|were|have|has|will|can|should)\b', b, re.I): return True
        return False
    result = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if not is_meta_block(b) and len(b) > 40 and re.search(r'[A-Z][a-z]', b): break
        i += 1
    while i < len(blocks):
        en_block = blocks[i]
        if is_zh_block(en_block): i += 1; continue
        if i + 1 < len(blocks) and is_zh_block(blocks[i + 1]):
            result.append([en_block, blocks[i + 1]]); i += 2
        else:
            result.append([en_block, ""]); i += 1
    return result

def has_chinese(pairs_list):
    return any(zh.strip() for _, zh in pairs_list)

def fetch_post_pairs(post_id, cookie_file, ua):
    cf = cookie_file or '/dev/null'; r = sp.run(['curl', '-s', '-b', cf, '-H', f'User-Agent: {ua}',
                f'https://www.sahaja.live/wp-json/wp/v2/posts/{post_id}'], capture_output=True, text=True)
    post_data = json.loads(r.stdout)
    html = post_data.get('content', {}).get('rendered', '')
    text_raw = re.sub(r'<[^>]+>', '\n', html)
    for ent, rep in [('&amp;','&'),('&#038;','&'),('&#8211;','–'),('&#8217;',"'"),
                      ('&#8216;',"'"),('&#8220;','"'),('&#8221;','"'),('&nbsp;',' ')]:
        text_raw = text_raw.replace(ent, rep)
    raw_title = post_data.get('title', {}).get('rendered', '')
    t_cn = re.sub(r'^\d{4}-\d{2}-\d{2}\s*', '', raw_title).strip()
    s_link = post_data.get('link', '')
    candidate = parse_sahaja_full_text(text_raw)
    return candidate, s_link, t_cn, text_raw

# ─── 2a: Try cache ───
if os.path.exists(SAHAJA_CACHE):
    try:
        with open(SAHAJA_CACHE) as f: cached = json.load(f)
        if cached.get("date") == date_str and cached.get("full_text"):
            candidate = parse_sahaja_full_text(cached["full_text"])
            if has_chinese(candidate):
                pairs = candidate
                sahaja_link = cached.get("source_url", link)
                extracted = extract_title_cn_from_pairs(pairs, title_en)
                if extracted: title_cn = extracted
                print(f"[2a] 使用 sahaja.live 缓存，配对数: {len(pairs)}")
    except Exception as e:
        print(f"[2a] 缓存读取失败: {e}")


if not pairs:
    print('[2b1] Trying public WordPress API (no login)...')
    def tw(t):
        ws = [w for w in t.split() if len(w) > 2]
        return ' '.join(ws[:5])
    sq = tw(title_en)
    if sq:
        try:
            u = 'https://www.sahaja.live/wp-json/wp/v2/posts?search=' + sq.replace(' ', '%20') + '&per_page=5'
            print('[2b1] ' + u)
            rs = sp.run(['curl', '-s', '-H', 'User-Agent: Mozilla/5.0', u], capture_output=True, text=True, timeout=30)
            if rs.stdout[:1] == '[':
                posts = json.loads(rs.stdout)
                print('[2b1] Results: ' + str(len(posts)))
                for p in posts:
                    pid = p['id']
                    candidate, s_link, t_cn, txt_raw = fetch_post_pairs(pid, None, UA)
                    if has_chinese(candidate):
                        pairs = candidate; sahaja_link = s_link
                        ext = extract_title_cn_from_pairs(pairs, title_en)
                        if ext: title_cn = ext
                        print('[2b1] Hit post_id=' + str(pid) + ', pairs=' + str(len(pairs)))
                        break
                    else:
                        print('[2b1] post_id=' + str(pid) + ' no CN, skip')
        except Exception as e:
            print('[2b1] Public API failed: ' + str(e))

# ─── 2b: Online search ───
sahaja_email = os.environ.get("SAHAJA_EMAIL", "")
sahaja_pass = os.environ.get("SAHAJA_PASSWORD", "")

if not pairs and sahaja_email and sahaja_pass:
    print("[2b] 在线搜索 sahaja.live...")
    if os.path.exists(COOKIE_FILE): os.remove(COOKIE_FILE)
    r_login = sp.run(['curl', '-s', '-c', COOKIE_FILE, '-H', f'User-Agent: {UA}',
                      'https://www.sahaja.live/login/'], capture_output=True, text=True)
    nonce_m = re.search(r'piereg_login_form_nonce.*?value="([^"]+)"', r_login.stdout, re.DOTALL)
    if nonce_m:
        nonce = nonce_m.group(1)
        sp.run(['curl', '-s', '-L', '-b', COOKIE_FILE, '-c', COOKIE_FILE,
                '-H', f'User-Agent: {UA}', '-H', 'Referer: https://www.sahaja.live/login/',
                '--data-urlencode', f'log={sahaja_email}',
                '--data-urlencode', f'pwd={sahaja_pass}',
                '-d', f'rememberme=forever&piereg_login_form_nonce={nonce}&_wp_http_referer=%2Flogin%2F&wp-submit=Log+In&redirect_to=&testcookie=1',
                'https://www.sahaja.live/login/'], capture_output=True, text=True)
        print("[2b] 登录完成")
        # Build search queries
        def title_keywords(t, max_words=5):
            words = [w for w in t.split() if len(w) > 2]
            return ' '.join(words[:max_words])
        def content_keywords(text, max_words=6):
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            for line in lines:
                if re.match(r'^\d', line): continue
                if len(line) < 20: continue
                return ' '.join(line.split()[:max_words])
            return ""
        search_queries = [title_keywords(title_en)]
        cq = content_keywords(content)
        if cq and cq != search_queries[0]:
            search_queries.append(cq)
        for sq in search_queries:
            print(f"[2b] 搜索: {sq}")
            r_search = sp.run(['curl', '-s', '-b', COOKIE_FILE, '-H', f'User-Agent: {UA}',
                               f'https://www.sahaja.live/wp-json/wp/v2/posts?search={sq.replace(" ", "+")}&per_page=10'],
                              capture_output=True, text=True)
            try: posts = json.loads(r_search.stdout)
            except: posts = []
            if not isinstance(posts, list): posts = []
            print(f"[2b] 结果数: {len(posts)}")
            for p in posts:
                pid = p['id']
                candidate, s_link, t_cn, text_raw = fetch_post_pairs(pid, COOKIE_FILE, UA)
                if has_chinese(candidate):
                    pairs = candidate; sahaja_link = s_link
                    extracted = extract_title_cn_from_pairs(pairs, title_en)
                    if extracted: title_cn = extracted
                    print(f"[2b] ✅ 命中 post_id={pid}, 配对数: {len(pairs)}, 标题: {title_cn}")
                    cache_data = {"date": date_str, "title_en": title_en, "title_cn": title_cn,
                                  "source_url": sahaja_link, "post_id": pid, "full_text": text_raw, "pairs": []}
                    with open(SAHAJA_CACHE, "w", encoding="utf-8") as f:
                        json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    break
                else:
                    print(f"[2b] post_id={pid} 无中文，跳过")
            if pairs: break
        if not pairs:
            print("[2b] ❌ 所有搜索词均未找到中文译文")

# ─── 2c: Sentence alignment ───
if pairs:
    print("[2c] 句级对齐...")
    stopwords = {'that','this','with','have','your','from','they','them',
                 'will','what','when','into','been','were','also','just',
                 'more','than','then','there','their','which','still','only',
                 'such','very','even','does'}
    EN_ZH_DICT = {
        'advertisement':'广告','responsibility':'责任','shouldering':'承担','spread':'传播',
        'establish':'体系','shoulders':'肩膀','strong':'坚强','freedom':'自由','growth':'成长',
        'carry':'承担','carrying':'承担','free':'自由','using':'利用','building':'建设',
        'great':'伟大','light':'光明','purpose':'目的','watch':'观察','subtle':'微妙',
        'limited':'有限','inside':'内心','outside':'外在','growth':'成长','growing':'成长',
    }
    def en_sent_to_zh_keywords(en_sent):
        words = re.findall(r'\b[a-z]{4,}\b', en_sent.lower())
        return [v for w in words for k,v in EN_ZH_DICT.items() if w==k]
    def split_sentences(text):
        sents = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'(])', text.strip())
        return [s.strip() for s in sents if len(s.strip()) > 10]
    def best_para_for_sent(en_s, sahaja_pairs_list):
        kws = set(re.findall(r'\b[a-z]{4,}\b', en_s.lower())) - stopwords
        best_sc, best_pi = 0, 0
        for pi, (ep, zp) in enumerate(sahaja_pairs_list):
            if not zp.strip(): continue
            ep_words = set(re.findall(r'\b[a-z]{4,}\b', ep.lower())) - stopwords
            if not ep_words: continue
            sc = len(kws & ep_words) / max(len(kws), 1) if kws else 0
            if sc > best_sc: best_sc, best_pi = sc, pi
        return best_pi
    amruta_sents = split_sentences(content)
    if amruta_sents:
        first_pi = best_para_for_sent(amruta_sents[0], pairs)
        last_pi = best_para_for_sent(amruta_sents[-1], pairs)
        if last_pi < first_pi: last_pi = first_pi
        from collections import defaultdict
        amruta_to_para = [first_pi + best_para_for_sent(s, pairs[first_pi:last_pi+1]) for s in amruta_sents]
        para_to_amruta = defaultdict(list)
        for order, pi in enumerate(amruta_to_para):
            para_to_amruta[pi].append(order)
        result_map = {}
        for pi in range(first_pi, last_pi + 1):
            if pi not in para_to_amruta: continue
            orders = para_to_amruta[pi]
            zp = pairs[pi][1]
            zh_subs = [s.strip() for s in re.split(r'[。！？]', zp) if len(s.strip()) > 3]
            if not zh_subs:
                for order in orders: result_map[order] = ""
                continue
            zh_claimed, anchored = {}, {}
            for order in orders:
                en_s = amruta_sents[order]
                zh_kws = en_sent_to_zh_keywords(en_s)
                if not zh_kws: continue
                best_sc, best_zi = 0, -1
                for zi, zs in enumerate(zh_subs):
                    if zi in zh_claimed: continue
                    sc = sum(1 for kw in zh_kws if kw in zs)
                    if sc > best_sc: best_sc, best_zi = sc, zi
                if best_sc >= 1 and best_zi >= 0:
                    anchored[order] = best_zi; zh_claimed[best_zi] = order
            remaining = [zi for zi in range(len(zh_subs)) if zi not in zh_claimed]
            ri = 0
            for order in orders:
                if order not in anchored:
                    anchored[order] = remaining[ri] if ri < len(remaining) else len(zh_subs) - 1
                    if ri < len(remaining):
                        zh_claimed[remaining[ri]] = order; ri += 1
            order_by_zi = sorted(anchored.items(), key=lambda x: x[1])
            for rank, (order, zi) in enumerate(order_by_zi):
                next_zi = order_by_zi[rank + 1][1] if rank + 1 < len(order_by_zi) else len(zh_subs)
                group = [zh_subs[zi]]
                for k in range(zi + 1, next_zi):
                    if k not in zh_claimed or zh_claimed[k] == order:
                        group.append(zh_subs[k])
                result_map[order] = "。".join(group)
        pairs = [[amruta_sents[order], result_map.get(order, "")] for order in range(len(amruta_sents))]
        print(f"[2c] 锚定段落 [{first_pi}~{last_pi}], 共 {len(pairs)} 句")

# ─── Fallback: English only ───
if not pairs:
    content_paras = [p.strip() for p in content.split('\n') if p.strip()]
    pairs = [[p, ""] for p in content_paras]
    print(f"[2c] ⚠️ 无中文翻译，仅英文，{len(pairs)} 段")

# ─── 2d: Build email HTML ───
print("[2d] 构建邮件 HTML...")
pair_html_lines = []
for en, zh in pairs:
    en = str(en).strip() if en else ""
    zh = str(zh).strip() if zh else ""
    if not en and not zh: continue
    if en and zh:
        pair_html_lines.append(f'<p style="color:#888;font-size:0.85em;margin:0 0 2px 0;">{en}</p><p style="margin:0 0 14px 0;">{zh}</p>')
    elif en:
        pair_html_lines.append(f'<p style="color:#888;font-size:0.85em;margin:0 0 14px 0;">{en}</p>')
    elif zh:
        pair_html_lines.append(f'<p style="margin:0 0 14px 0;">{zh}</p>')
pair_html = "\n".join(pair_html_lines)

try:
    dt_obj = dt.datetime.strptime(date_str, "%Y-%m-%d")
    date_display = dt_obj.strftime("%Y年%-m月%-d日")
except: date_display = date_str

final_link = sahaja_link or link
email_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:'Helvetica Neue',Arial,sans-serif;max-width:680px;margin:0 auto;padding:24px 16px;color:#222;line-height:1.7;">

<h2 style="margin:0 0 4px 0;font-size:1.25em;font-weight:700;">{title_cn}</h2>
<p style="color:#888;font-size:0.85em;margin:0 0 4px 0;font-style:italic;">{title_en}</p>
<p style="color:#aaa;font-size:0.8em;margin:0 0 24px 0;">{date_display}</p>

<hr style="border:none;border-top:1px solid #eee;margin:0 0 24px 0;">

{pair_html}

<hr style="border:none;border-top:1px solid #eee;margin:24px 0 16px 0;">
<p style="color:#aaa;font-size:0.8em;margin:0;word-break:break-all;">
  <a href="https://amruta.today/" style="color:#aaa;">https://amruta.today/</a>
  <br>
  <a href="{final_link}" style="color:#aaa;">{final_link}</a>
</p>

</body>
</html>"""

with open("/tmp/pairs.json", "w", encoding="utf-8") as f:
    json.dump(pairs, f, ensure_ascii=False, indent=2)
with open("/tmp/email_body.html", "w", encoding="utf-8") as f:
    f.write(email_html)
with open("/tmp/sahaja_link.txt", "w", encoding="utf-8") as f:
    f.write(final_link or "")

print(f"✅ Step2: {len(pairs)} 对, 邮件 HTML 构建完成")
