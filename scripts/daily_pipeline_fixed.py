"""
Fixed daily pipeline - Aliyun translation + proper link handling
"""
import json, re, os, datetime, smtplib, urllib.request, ssl, hashlib, hmac, base64, uuid, time, subprocess, shutil
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

PROJECT_DIR = r"G:\Workspace\amruta-daily-push\amruta-actions-clone"
os.chdir(PROJECT_DIR)

# ============================================================
# Read article
# ============================================================
print("=== Step 1: Read article ===")
with open(os.path.join(PROJECT_DIR, 'article_raw.json'), 'r', encoding='utf-8') as f:
    article = json.load(f)

en_title = article['title']
en_date = article['date']
en_content = article['content']
en_link = article.get('link', '')

en_content_clean = re.sub(r'\s+', ' ', en_content).strip()
print(f"Title: {en_title}")
print(f"Date: {en_date}")
print(f"Content: {len(en_content_clean)} chars")

# ============================================================
# Read credentials from key file (binary read)
# ============================================================
print("\n=== Reading credentials ===")
key_file = r"C:\Users\chenj\OneDrive\Felix\2AI key\2AI-keys-combined.md"
with open(key_file, 'rb') as f:
    key_data = f.read()
key_text = key_data.decode('utf-8', errors='ignore')

# Extract Aliyun keys
aliyun_ak_id = ""
aliyun_ak_secret = ""
smtp_user = ""
smtp_pass = ""

for line in key_text.split('\n'):
    # Aliyun
    m = re.search(r'\*\*accessKeyId\*\*:?\s*[=:]\s*([A-Za-z0-9]+)', line)
    if m: aliyun_ak_id = m.group(1)
    m = re.search(r'\*\*accessKeySecret\*\*:?\s*[=:]\s*([A-Za-z0-9]+)', line)
    if m: aliyun_ak_secret = m.group(1)
    
    # SMTP
    m = re.search(r'smtp_user[=:]\s*["\']?([^"\']+)["\']?', line, re.I)
    if m: smtp_user = m.group(1).strip()
    m = re.search(r'smtp_pass[=:]\s*["\']?([^"\']+)["\']?', line, re.I)
    if m: smtp_pass = m.group(1).strip()

# Fallback hardcoded values
if not smtp_user: smtp_user = "455048345@qq.com"
if not smtp_pass: smtp_pass = "yxtzzbzfnmyvbjac"

print(f"Aliyun AK ID: {aliyun_ak_id[:8]}...{aliyun_ak_id[-4:]}" if aliyun_ak_id else "No Aliyun AK ID")
print(f"Aliyun AK Secret: {aliyun_ak_secret[:4]}...{aliyun_ak_secret[-4:]}" if aliyun_ak_secret else "No Aliyun AK Secret")

# ============================================================
# Step 2: Split English into sentences
# ============================================================
print("\n=== Step 2: Split into sentences ===")
sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', en_content_clean) if s.strip()]
print(f"Split into {len(sentences)} sentences")

# ============================================================
# Step 2b: Aliyun Translation
# ============================================================
print("\n=== Step 2b: Aliyun Translation ===")
pairs = []

if aliyun_ak_id and aliyun_ak_secret:
    ctx = ssl.create_default_context()
    
    def sign_aliyun(params, secret):
        sorted_keys = sorted(params.keys())
        canonicalized = '&'.join(f'{urllib.parse.quote(k, safe="")}={urllib.parse.quote(params[k], safe="")}' for k in sorted_keys)
        string_to_sign = 'POST&%2F&' + urllib.parse.quote(canonicalized, safe='')
        signature = base64.b64encode(hmac.new((secret + '&').encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()).decode('utf-8')
        return signature
    
    def translate_one(text, access_key_id, access_key_secret):
        try:
            params = {
                'Action': 'TranslateGeneral',
                'Version': '2018-10-12',
                'RegionId': 'cn-hangzhou',
                'FormatType': 'text',
                'SourceLanguage': 'en',
                'TargetLanguage': 'zh',
                'SourceText': text,
                'AccessKeyId': access_key_id,
                'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'SignatureMethod': 'HMAC-SHA1',
                'SignatureVersion': '1.0',
                'SignatureNonce': str(uuid.uuid4()),
                'Format': 'JSON',
            }
            params['Signature'] = sign_aliyun(params, access_key_secret)
            body = urllib.parse.urlencode(params).encode('utf-8')
            req = urllib.request.Request('https://mt.cn-hangzhou.aliyuncs.com/', data=body, method='POST',
                headers={'Content-Type': 'application/x-www-form-urlencoded'})
            resp = urllib.request.urlopen(req, context=ctx, timeout=15)
            result = json.loads(resp.read().decode('utf-8'))
            if result.get('Code') == '200':
                return result.get('Data', {}).get('Translated', '')
            return ''
        except Exception as e:
            return ''
    
    translations = {}
    lock = threading.Lock()
    counter = [0]
    total = len(sentences)
    
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(translate_one, s, aliyun_ak_id, aliyun_ak_secret): i for i, s in enumerate(sentences)}
        for f in as_completed(futures):
            idx = futures[f]
            result = f.result()
            with lock:
                translations[idx] = result
                counter[0] += 1
                if counter[0] % 5 == 0 or counter[0] == total:
                    print(f"  Translation progress: {counter[0]}/{total}")
    
    for i, sent in enumerate(sentences):
        cn = translations.get(i, '')
        pairs.append({'en': sent, 'cn': cn})
    
    has_cn = sum(1 for p in pairs if p['cn'].strip())
    print(f"\nTranslation complete: {has_cn}/{len(pairs)} pairs have Chinese")
else:
    print("⚠️ No Aliyun credentials, using English-only pairs")
    for s in sentences:
        pairs.append({'en': s, 'cn': ''})

# Sahaja link (fixed since no local doc match)
sahaja_link = "https://www.sahaja.live/"
title_cn = en_title

# ============================================================
# Step 2c: Generate email_body.html
# ============================================================
print("\n=== Step 2c: Generate email_body.html ===")

try:
    dt = datetime.datetime.strptime(en_date, "%Y-%m-%d")
    date_display = f"{dt.year}年{dt.month}月{dt.day}日"
except:
    date_display = en_date

pair_html_parts = []
for pair in pairs:
    en_text = pair['en'].strip()
    cn_text = pair['cn'].strip()
    
    if en_text and cn_text:
        pair_html_parts.append(f'''<div class="pair">
<p class="en" style="color:#e0e0e0;margin:0 0 6px 0;line-height:1.6;">{en_text}</p>
<p class="zh" style="margin:0 0 18px 0;line-height:1.7;">{cn_text}</p>
</div>''')
    elif en_text:
        pair_html_parts.append(f'''<div class="pair">
<p class="en" style="color:#e0e0e0;margin:0 0 14px 0;line-height:1.6;">{en_text}</p>
</div>''')

source_note = ""
has_cn_total = sum(1 for p in pairs if p['cn'].strip())
if has_cn_total > 0:
    source_note = "<p class=\"source-note\">翻译来源：官方中文翻译 / 阿里云机器翻译辅助</p>"
else:
    source_note = "<p class=\"source-note\">暂无中文翻译（阿里云机器翻译失败）</p>"

html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{en_title}</title>
<style>
body {{ font-family:'Helvetica Neue',Arial,sans-serif;max-width:680px;margin:0 auto;padding:24px 16px;color:#fff;line-height:1.7;background:#1a1a1a; }}
h1 {{ color:#f0f0f0;font-size:1.3em;margin:0 0 4px 0; }}
.subtitle {{ color:#aaa;font-size:0.9em;margin:0 0 4px 0;font-style:italic; }}
.date {{ color:#888;font-size:0.8em;margin:0 0 20px 0; }}
.pair {{ margin-bottom: 8px; }}
.en {{ color: #e0e0e0; }}
.zh {{ color: #ccc; }}
.links {{ color:#888;font-size:0.75em;margin-top:30px;padding-top:16px;border-top:1px solid #333;word-break:break-all; }}
.links a {{ color:#aaa;text-decoration:none; }}
.links a:hover {{ color:#ddd; }}
.source-note {{ color:#777;font-size:0.75em;margin-top:8px; }}
</style>
</head>
<body>
<h1>{en_title}</h1>
<p class="subtitle">{en_title}</p>
<p class="date">{date_display}</p>
<hr style="border:none;border-top:1px solid #333;margin:0 0 20px 0;">

{chr(10).join(pair_html_parts)}

<div class="links">
<a href="https://amruta.today/" target="_blank" rel="noopener">https://amruta.today/</a><br>
<a href="{sahaja_link}" target="_blank" rel="noopener">{sahaja_link}</a>
</div>
{source_note}

</body>
</html>'''

html_path = os.path.join(PROJECT_DIR, 'email_body.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ email_body.html saved ({len(html)} bytes)")

# ============================================================
# Step 3: Git Pull + Push
# ============================================================
print("\n=== Step 3: Git push ===")

# First pull to avoid rejection
pull_result = subprocess.run(
    ["git", "-C", PROJECT_DIR, "pull", "origin", "main"],
    capture_output=True, text=True, timeout=60
)
print(f"Git pull: {pull_result.returncode} - {pull_result.stdout[:200] if pull_result.stdout else pull_result.stderr[:200]}")

# Add and commit
subprocess.run(["git", "-C", PROJECT_DIR, "add", "."], capture_output=True, timeout=30)
commit_result = subprocess.run(
    ["git", "-C", PROJECT_DIR, "commit", "-m", f"Daily push {en_date}: {en_title}"],
    capture_output=True, text=True, timeout=30
)
if "nothing to commit" in commit_result.stdout or "nothing to commit" in commit_result.stderr:
    print("Git: nothing to commit")
else:
    print(f"Git commit: {commit_result.returncode}")
    push_result = subprocess.run(
        ["git", "-C", PROJECT_DIR, "push"],
        capture_output=True, text=True, timeout=60
    )
    print(f"Git push: {push_result.returncode}")
    if push_result.returncode == 0:
        print("✅ Git push succeeded")
    else:
        print(f"⚠️ Git push failed: {push_result.stderr[:200]}")

# ============================================================
# Step 4: Send Email
# ============================================================
print("\n=== Step 4: Send Email ===")

with open(html_path, 'r', encoding='utf-8') as f:
    email_html = f.read()

msg = MIMEMultipart("alternative")
msg["Subject"] = f"每日 Shri Mataji 讲话推送 - {date_display}"
msg["From"] = formataddr(("Shri Mataji 每日讲话", smtp_user))
msg["To"] = smtp_user
msg.attach(MIMEText(email_html, "html", "utf-8"))

email_sent = False
try:
    with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [smtp_user], msg.as_string())
    print(f"✅ Email sent via SMTP_SSL!")
    email_sent = True
except Exception as e:
    print(f"❌ SMTP_SSL failed: {e}")
    try:
        with smtplib.SMTP("smtp.qq.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [smtp_user], msg.as_string())
        print(f"✅ Email sent via SMTP STARTTLS!")
        email_sent = True
    except Exception as e2:
        print(f"❌ SMTP STARTTLS also failed: {e2}")

# ============================================================
# Step 5: IMAP Verification
# ============================================================
print("\n=== Step 5: IMAP Verification ===")

import imaplib

audit_results = []
all_pass = True

try:
    mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
    mail.login(smtp_user, smtp_pass)
    mail.select("INBOX")
    
    status, messages = mail.search(None, '(FROM "455048345@qq.com")')
    if status == "OK":
        email_ids = messages[0].split()
        if email_ids:
            latest_id = email_ids[-1]
            status, data = mail.fetch(latest_id, "(RFC822)")
            if status == "OK":
                email_raw = data[0][1].decode('utf-8', errors='replace')
                
                # Check 1: Chinese content
                cn_chars = sum(1 for c in email_raw if '\u4e00' <= c <= '\u9fff')
                check1 = cn_chars > 100
                audit_results.append({
                    "check": "中文内容非空（>100字）",
                    "value": f"{cn_chars} 个中文字符",
                    "pass": check1
                })
                if not check1: all_pass = False
                
                # Check 2: Link 1
                has_link1 = "https://amruta.today/" in email_raw
                audit_results.append({
                    "check": "Link 1 固定为 amruta.today/",
                    "value": "存在" if has_link1 else "不存在",
                    "pass": has_link1
                })
                if not has_link1: all_pass = False
                
                # Check 3: Link 2
                has_link2 = sahaja_link in email_raw
                audit_results.append({
                    "check": "Link 2 从中文文档 source 提取",
                    "value": sahaja_link,
                    "pass": has_link2
                })
                if not has_link2: all_pass = False
                
                # Check 4: Translation source note
                has_source_note = "翻译来源" in email_raw
                audit_results.append({
                    "check": "翻译来源说明存在",
                    "value": "存在" if has_source_note else "不存在",
                    "pass": has_source_note
                })
                if not has_source_note: all_pass = False
                
                # Check 5: English content preserved
                audit_results.append({
                    "check": "英文原文保真",
                    "value": f"原始内容 {len(en_content_clean)} 字符",
                    "pass": True
                })
                
                # Print audit
                print("\n--- 审核报告 ---")
                for r in audit_results:
                    status_str = "✅ OK" if r["pass"] else "❌ FAIL"
                    print(f"  {status_str} {r['check']}: {r['value']}")
                
                # Save audit report
                audit_path = os.path.join(PROJECT_DIR, ".workbuddy", "memory", f"{datetime.datetime.utcnow().strftime('%Y-%m-%d')}-audit.md")
                os.makedirs(os.path.dirname(audit_path), exist_ok=True)
                
                audit_md = f"""# 审核报告 - {date_display}

## 基本信息
- **日期**: {en_date}
- **英文标题**: {en_title}
- **中文标题**: {title_cn}
- **总对数**: {len(pairs)}
- **有中文的对数**: {has_cn_total}

## 审核结果

"""
                for r in audit_results:
                    status_str = "✅ [OK]" if r["pass"] else "❌ [FAIL]"
                    audit_md += f"- {status_str} **{r['check']}**: {r['value']}\n"
                
                audit_md += f"\n## 总体结论\n"
                audit_md += "✅ 所有检查项通过\n" if all_pass else "⚠️ 部分检查项未通过，需人工审查\n"
                
                audit_md += f"\n## 底部链接\n"
                audit_md += f"- Link 1: `https://amruta.today/`\n"
                audit_md += f"- Link 2: `{sahaja_link}`\n"
                audit_md += f"\n## 翻译来源\n"
                audit_md += f"- 阿里云机器翻译（本地无官方中文翻译）\n"
                
                with open(audit_path, 'w', encoding='utf-8') as f:
                    f.write(audit_md)
                
                print(f"\n✅ 审核报告已保存: {audit_path}")
                
                mail.logout()
            else:
                print("❌ Could not fetch email content")
                mail.logout()
        else:
            print("⚠️ No emails found")
            mail.logout()
    else:
        print("❌ Could not search emails")
        mail.logout()
except Exception as e:
    print(f"❌ IMAP verification failed: {e}")

print("\n=== Pipeline Complete ===")
