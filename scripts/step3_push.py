"""
Step 3: Build daily HTML + Push to amruta-daily-archive via push_article.js
Input: /tmp/article_raw.json, /tmp/pairs.json, /tmp/email_body.html
"""
import json, subprocess, os, re, datetime, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aliyun_translate import extract_words, build_word_map

with open("/tmp/article_raw.json", encoding="utf-8") as f:
    article = json.load(f)
with open("/tmp/pairs_flat.json", encoding="utf-8") as f:
    pairs = json.load(f)

raw_date = article["date"]
title_en = article["title"]

cn_now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
cur_year = str(cn_now.year)
mm_dd = raw_date[4:]
date = cur_year + mm_dd

# sahaja link
sahaja_link = ""
if os.path.exists("/tmp/sahaja_link.txt"):
    with open("/tmp/sahaja_link.txt", encoding="utf-8") as f:
        sahaja_link = f.read().strip()
else:
    print("[step3] sahaja_link.txt NOT FOUND (OK if first run)")
source_url = sahaja_link or "https://amruta.today/"

# 阿里云翻译：预翻译文章中所有独特英文单词
ak_id = os.environ.get("ALIYUN_ACCESS_KEY_ID", "")
ak_secret = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")
word_map = {}
if ak_id and ak_secret:
    words = extract_words(pairs)
    print(f"[step3] 提取到 {len(words)} 个独特单词，开始阿里云翻译...")
    if words:
        word_map = build_word_map(words, ak_id, ak_secret)
        print(f"[step3] 阿里云翻译完成: {len(word_map)}/{len(words)} 个单词")

# Extract Chinese title from email_body.html
title_cn = title_en
if os.path.exists("/tmp/email_body.html"):
    with open("/tmp/email_body.html") as f:
        html = f.read()
    m = re.search(r'<h2[^>]*>([^<]+)</h2>', html)
    if m:
        title_cn = m.group(1).strip()

payload = {"date": date, "title": title_en, "titleCn": title_cn,
           "sourceUrl": source_url, "pairs": pairs, "wordMap": word_map}

with open("/tmp/push_input.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

script_dir = os.path.dirname(os.path.abspath(__file__))
result = subprocess.run(
    ["node", os.path.join(script_dir, "push_article.js"), "--file", "/tmp/push_input.json"],
    capture_output=True, text=True, timeout=180, env=os.environ.copy()
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

if result.returncode != 0:
    raise RuntimeError(f"push_article.js failed (code {result.returncode})")

os.remove("/tmp/push_input.json")
archive_url = f"https://wherejiahe-bot.github.io/amruta-daily-archive/daily/{date}.html"
print(f"✅ Step3: {archive_url}")

# Save result
with open("/tmp/push_result.txt", "w", encoding="utf-8") as f:
    f.write(f"✅ GitHub推送成功\n日期: {date}\n网页: {archive_url}")
