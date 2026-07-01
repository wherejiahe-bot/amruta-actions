"""
Step 1: Fetch today's article from amruta.today API.
Output: /tmp/article_raw.json
"""
import urllib.request, json, re, datetime, os

override_str = os.environ.get("DATE_OVERRIDE", "")
if override_str:
    parts = override_str.split("-")
    cn = datetime.datetime(int(parts[0]), int(parts[1]), int(parts[2]))
else:
    cn = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
month = str(cn.month).zfill(2)
day = str(cn.day).zfill(2)
date_str = cn.strftime("%Y-%m-%d")

url = f"https://amruta.today/wp-json/everyday-ui/v1/talks/lang/en/month/{month}/day/{day}"
print(f"Fetching: {url}")

req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode("utf-8"))

if not data:
    raise ValueError(f"API returned empty for {date_str}")

item = data[0]
title = item.get("title", "")
if isinstance(title, dict):
    title = title.get("rendered", "")

raw_date = item.get("date", date_str)
date_clean = raw_date.split(" ")[0] if " " in raw_date else raw_date[:10]

content_raw = item.get("content", "")
if isinstance(content_raw, dict):
    content_raw = content_raw.get("rendered", "")
content_text = re.sub(r"<[^>]+>", "", content_raw).strip()
link = item.get("link", "")
# amruta.today 为永久链接，amruta.org 为旧短暂链接
link = link.replace("www.amruta.org", "amruta.today") if link else ""

article = {"date": date_clean, "title": title, "content": content_text, "link": link}
with open("/tmp/article_raw.json", "w", encoding="utf-8") as f:
    json.dump(article, f, ensure_ascii=False, indent=2)

print(f"✅ Step1: {date_clean} — {title}")
