"""Run by GitHub Actions: fetch amruta article, push to archive, send email."""
import urllib.request, json, re, datetime, subprocess, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

cn = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
m, d = str(cn.month).zfill(2), str(cn.day).zfill(2)
date_str = cn.strftime("%Y-%m-%d")

# Step 1: Fetch
url = f"https://amruta.today/wp-json/everyday-ui/v1/talks/lang/en/month/{m}/day/{d}"
print(f"1. Fetching: {url}")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read().decode())
item = data[0]
title = item.get("title", "")
if isinstance(title, dict): title = title.get("rendered", "")
content_raw = item.get("content", "")
if isinstance(content_raw, dict): content_raw = content_raw.get("rendered", "")
content = re.sub(r"<[^>]+>", "", content_raw).strip()
link = item.get("link", "")
print(f"2. Title: {title}")

# Step 2: Build pairs (English only, no Chinese translation in auto mode)
paras = [p.strip() for p in content.split(chr(10)) if p.strip()]
pairs = [[p, ""] for p in paras]

# Step 3: Push to GitHub Pages
script_dir = os.path.dirname(os.path.abspath(__file__))
payload = {"date": date_str, "title": title, "titleCn": title,
           "sourceUrl": link, "pairs": pairs}
with open("/tmp/push_input.json", "w") as f:
    json.dump(payload, f)
print("3. Pushing to amruta-daily-archive...")
r = subprocess.run(
    ["node", os.path.join(script_dir, "push_article.js"), "--file", "/tmp/push_input.json"],
    capture_output=True, text=True, timeout=120
)
print(r.stdout)
if r.returncode != 0:
    raise RuntimeError(r.stderr)
archive_url = f"https://wherejiahe-bot.github.io/amruta-daily-archive/daily/{date_str}.html"
print(f"4. Pushed: {archive_url}")

# Step 4: Send email
smtp_user = os.environ.get("SMTP_USER", "")
smtp_pass = os.environ.get("SMTP_PASS", "")
if smtp_user and smtp_pass:
    print("5. Sending email...")
    try:
        dd = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y年%-m月%-d日")
    except:
        dd = date_str
    pair_html = ""
    for en, zh in pairs:
        if en:
            pair_html += f'<p style="color:#888;font-size:0.85em;margin:0 0 2px 0;">{en}</p>'
        if zh:
            pair_html += f'<p style="margin:0 0 14px 0;">{zh}</p>'
    email_html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="font-family:Helvetica Neue,Arial,sans-serif;max-width:680px;margin:0 auto;padding:24px;color:#222;line-height:1.7;">'
        f'<h2 style="margin:0 0 4px;font-size:1.25em;font-weight:700;">{title}</h2>'
        f'<p style="color:#aaa;font-size:0.8em;margin:0 0 24px;">{dd}</p>'
        '<hr style="border:none;border-top:1px solid #eee;margin:0 0 24px;">'
        f'{pair_html}'
        '<hr style="border:none;border-top:1px solid #eee;margin:24px 0 16px;">'
        f'<p style="color:#aaa;font-size:0.8em;margin:0;"><a href="{archive_url}" style="color:#aaa;">{archive_url}</a></p>'
        '</body></html>'
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(f"Daily Shri Mataji Talk - {date_str}", "utf-8")
    msg["From"] = formataddr(("Shri Mataji Daily", smtp_user))
    msg["To"] = smtp_user
    msg.attach(MIMEText(email_html, "html", "utf-8"))
    with smtplib.SMTP("smtp.qq.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [smtp_user], msg.as_string())
    print("6. Email sent!")
else:
    print("5. SMTP not configured, skip email")

print(f"Done: {date_str}")
