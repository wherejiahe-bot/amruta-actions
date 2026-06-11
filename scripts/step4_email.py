"""
Step 4: Send email notification with bilingual content.
Input: /tmp/article_raw.json, /tmp/email_body.html
"""
import json, smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

smtp_user = os.environ.get("SMTP_USER", "")
smtp_pass = os.environ.get("SMTP_PASS", "")
if not smtp_user or not smtp_pass:
    print("Step4: SMTP not configured, skip email")
    exit(0)

with open("/tmp/article_raw.json", encoding="utf-8") as f:
    article = json.load(f)
with open("/tmp/email_body.html", encoding="utf-8") as f:
    html_body = f.read()

date = article["date"]
subject = f"每日 Shri Mataji 讲话推送 - {date}"

msg = MIMEMultipart("alternative")
msg["Subject"] = Header(subject, "utf-8")
msg["From"] = formataddr(("Shri Mataji 每日讲话", smtp_user))
msg["To"] = smtp_user
msg.attach(MIMEText(html_body, "html", "utf-8"))

with smtplib.SMTP("smtp.qq.com", 587) as server:
    server.ehlo()
    server.starttls()
    server.login(smtp_user, smtp_pass)
    server.sendmail(smtp_user, [smtp_user], msg.as_string())

print(f"✅ Step4: Email sent: {subject}")
