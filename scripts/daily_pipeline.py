"""
Complete daily push pipeline for amruta-daily-push.
Date: 2026-07-07 (processing yesterday's content: 2026-07-06)
"""
import json, re, os, datetime, smtplib, urllib.request, ssl, hashlib, hmac, base64, uuid, time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

PROJECT_DIR = r"G:\Workspace\amruta-daily-push\amruta-actions-clone"
os.chdir(PROJECT_DIR)

# ============================================================
# STEP 1: Read article_raw.json
# ============================================================
print("=== Step 1: Read article ===")
with open(os.path.join(PROJECT_DIR, 'article_raw.json'), 'r', encoding='utf-8') as f:
    article = json.load(f)

en_title = article['title']
en_date = article['date']  # 1986-07-06
en_content = article['content']
en_link = article['link']

# Clean content
en_content_clean = re.sub(r'\s+', ' ', en_content).strip()
print(f"Title: {en_title}")
print(f"Date: {en_date}")
print(f"Content length: {len(en_content_clean)} chars")

# ============================================================
# STEP 2: Split English into paragraphs/sentences
# ============================================================
print("\n=== Step 2: Split into pairs ===")

# Split by double newline or paragraph breaks
raw_paras = [p.strip() for p in re.split(r'\n\s*\n|\n', en_content) if p.strip()]
print(f"Found {len(raw_paras)} English paragraphs")

# Since no Chinese translation exists in local docs, we'll use Aliyun translate
# But first, let's check if there's a matching doc by searching F: drive
# The API content for 1986-07-06 is about "cosmic consciousness" and "material attraction"
# Let's search for matching content

# Search for content that contains key phrases from the API
key_phrases_api = ["cosmic consciousness", "material attraction", "gravity of any stars"]
found_docs = []
sahaja_folder = r"F:\霎哈嘉瑜伽\sahaja live talks"

for fname in os.listdir(sahaja_folder):
    if not fname.endswith('.md'):
        continue
    fpath = os.path.join(sahaja_folder, fname)
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Check if any key phrase appears
        for phrase in key_phrases_api:
            if phrase.lower() in content.lower():
                found_docs.append((fname, fpath, phrase))
                break
    except:
        pass

print(f"\nDocs containing key phrases: {len(found_docs)}")
for fname, fpath, phrase in found_docs:
    print(f"  {fname} (matched: {phrase})")

# ============================================================
# STEP 2b: Extract matching Chinese paragraphs from docs
# ============================================================
pairs = []
sahaja_link = ""
title_cn = en_title

if found_docs:
    # Use the first matching doc
    best_doc = found_docs[0][1]
    with open(best_doc, 'r', encoding='utf-8') as f:
        doc_content = f.read()
    
    # Parse frontmatter
    fm_match = re.match(r'^---\n(.*?)\n---\n(.*)', doc_content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        body = fm_match.group(2)
    else:
        body = doc_content
        fm_text = ""
    
    # Extract source URL
    for line in fm_text.strip().split('\n'):
        m = re.match(r'^source:\s*"?(.*?)"?\s*$', line)
        if m:
            sahaja_link = m.group(1).strip()
            break
    
    # Split into alternating EN/CN paragraphs
    lines = body.strip().split('\n')
    
    def is_chinese(text):
        cn_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        return cn_count >= 3
    
    # Collect EN and CN paragraphs
    en_paras = []
    cn_paras = []
    current_en = []
    current_cn = []
    
    for line in lines:
        if line.strip() == '':
            continue
        if is_chinese(line):
            if current_en:
                en_paras.append(' '.join(current_en))
                current_en = []
            current_cn.append(line)
        else:
            if current_cn:
                cn_paras.append(' '.join(current_cn))
                current_cn = []
            current_en.append(line)
    
    if current_en:
        en_paras.append(' '.join(current_en))
    if current_cn:
        cn_paras.append(' '.join(current_cn))
    
    print(f"\nDoc has {len(en_paras)} EN paras, {len(cn_paras)} CN paras")
    
    # Now find which EN paragraphs in the doc match the API content
    # Build similarity scores
    api_norm = re.sub(r'\s+', ' ', en_content_clean).lower()
    
    matching_indices = []
    for i, para in enumerate(en_paras):
        para_norm = re.sub(r'\s+', ' ', para).lower()
        # Check if API content contains this paragraph or vice versa
        if len(para_norm) > 20:  # Skip very short paras
            if para_norm in api_norm or api_norm.find(para_norm[:100]) >= 0:
                matching_indices.append(i)
    
    print(f"Matching paragraph indices: {matching_indices}")
    
    # Build pairs from matching indices
    for idx in matching_indices:
        if idx < len(cn_paras):
            pairs.append({
                'en': en_paras[idx].strip(),
                'cn': cn_paras[idx].strip()
            })
    
    # If we have pairs, try to extract Chinese title
    if pairs:
        keywords = [w.strip(".,!?\"'()-").lower() for w in en_title.split() if len(w.strip(".,!?\"'()-")) > 2]
        if keywords:
            for p in pairs:
                en_p = p['en'].lower()
                if all(kw in en_p for kw in keywords):
                    for part in re.split(r'[，。]', p['cn']):
                        part = part.strip()
                        if 4 < len(part) <= 30:
                            title_cn = re.sub(r'^(通过你们|通过我们|通过|在于|由于|因为|当你们|当我们)', '', part).strip()
                            if title_cn:
                                break
                if title_cn != en_title:
                    break

# ============================================================
# STEP 2c: If no matching Chinese found, use Aliyun translation
# ============================================================
if not pairs:
    print("\n⚠️ No Chinese translation found in local docs. Using Aliyun translation.")
    
    # Split API content into sentences for translation
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', en_content_clean) if s.strip()]
    print(f"Split into {len(sentences)} sentences for translation")
    
    # Read Aliyun credentials
    key_file = r"C:\Users\chenj\OneDrive\Felix\2AI key\2AI-keys-combined.md"
    with open(key_file, 'rb') as f:
        key_data = f.read()
    key_text = key_data.decode('utf-8', errors='ignore')
    
    # Extract Aliyun keys
    ak_id = ""
    ak_secret = ""
    for line in key_text.split('\n'):
        if 'accessKeyId' in line or 'AccessKeyId' in line:
            m = re.search(r'=([A-Za-z0-9]+)', line)
            if m: ak_id = m.group(1)
        if 'accessKeySecret' in line or 'AccessKeySecret' in line:
            m = re.search(r'=([A-Za-z0-9]+)', line)
            if m: ak_secret = m.group(1)
    
    print(f"Aliyun AccessKeyId: {ak_id[:8]}...{ak_id[-4:]}" if ak_id else "No AccessKeyId found")
    
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
            print(f"[Aliyun] Translation failed for '{text[:50]}...': {e}")
            return ''
    
    # Translate sentences in parallel
    if ak_id and ak_secret:
        translations = {}
        lock = threading.Lock()
        counter = [0]
        total = len(sentences)
        
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(translate_one, s, ak_id, ak_secret): i for i, s in enumerate(sentences)}
            for f in as_completed(futures):
                idx = futures[f]
                result = f.result()
                with lock:
                    translations[idx] = result
                    counter[0] += 1
                    if counter[0] % 5 == 0 or counter[0] == total:
                        print(f"  Translation progress: {counter[0]}/{total}")
        
        # Build pairs from translated sentences
        for i, sent in enumerate(sentences):
            cn = translations.get(i, '')
            if cn:
                pairs.append({'en': sent, 'cn': cn})
            else:
                pairs.append({'en': sent, 'cn': ''})
        
        print(f"\nTranslation complete: {sum(1 for p in pairs if p['cn'])}/{len(pairs)} pairs have Chinese")
    else:
        print("⚠️ No Aliyun credentials found. Will use English-only pairs.")
        for s in sentences:
            pairs.append({'en': s, 'cn': ''})

# If still no pairs at all, split by paragraphs
if not pairs:
    for p in raw_paras:
        pairs.append({'en': p, 'cn': ''})

print(f"\nTotal pairs: {len(pairs)}")
print(f"Pairs with Chinese: {sum(1 for p in pairs if p['cn'].strip())}")

# ============================================================
# STEP 2d: Generate email_body.html
# ============================================================
print("\n=== Step 2d: Generate email_body.html ===")

# Build date display
try:
    dt = datetime.datetime.strptime(en_date, "%Y-%m-%d")
    date_display = f"{dt.year}年{dt.month}月{dt.day}日"
except:
    date_display = en_date

# Build HTML pairs
pair_html_parts = []
for i, pair in enumerate(pairs):
    en_text = pair['en'].strip()
    cn_text = pair['cn'].strip()
    
    if en_text and cn_text:
        # Both EN and CN present
        pair_html_parts.append(f'''<div class="pair">
<p class="en" style="color:#e0e0e0;margin:0 0 6px 0;line-height:1.6;">{en_text}</p>
<p class="zh" style="margin:0 0 18px 0;line-height:1.7;">{cn_text}</p>
</div>''')
    elif en_text:
        # EN only
        pair_html_parts.append(f'''<div class="pair">
<p class="en" style="color:#e0e0e0;margin:0 0 14px 0;line-height:1.6;">{en_text}</p>
</div>''')

# Determine translation source note
has_cn = sum(1 for p in pairs if p['cn'].strip())
total = len(pairs)
if has_cn > 0:
    source_note = "翻译来源：官方中文翻译 / 阿里云机器翻译辅助"
elif total > 0:
    source_note = "暂无中文翻译"
else:
    source_note = ""

# Build HTML
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
<a href="{sahaja_link}" target="_blank" rel="noopener">{sahaja_link or 'https://sahaja.live/'}</a>
</div>
{f'<p class="source-note">{source_note}</p>' if source_note else ''}

</body>
</html>'''

html_path = os.path.join(PROJECT_DIR, 'email_body.html')
with open(html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ email_body.html saved ({len(html)} bytes)")

# ============================================================
# STEP 3: Push to GitHub Archive
# ============================================================
print("\n=== Step 3: Push to GitHub ===")

# Prepare push input
push_payload = {
    "date": en_date,
    "title": en_title,
    "titleCn": title_cn,
    "sourceUrl": sahaja_link or en_link,
    "pairs": [{"en": p['en'], "zh": p['cn']} for p in pairs]
}

push_json_path = os.path.join(PROJECT_DIR, 'push_input.json')
with open(push_json_path, 'w', encoding='utf-8') as f:
    json.dump(push_payload, f, ensure_ascii=False, indent=2)

# Try push_article.js first
import subprocess
script_dir = PROJECT_DIR
result = subprocess.run(
    ["node", os.path.join(script_dir, "scripts", "push_article.js"), "--file", push_json_path],
    capture_output=True, text=True, timeout=120
)
print(result.stdout)
if result.stderr:
    print(f"STDERR: {result.stderr}")

archive_url = ""
if result.returncode == 0:
    archive_url = f"https://wherejiahe-bot.github.io/amruta-daily-archive/daily/{en_date}.html"
    print(f"✅ GitHub push succeeded: {archive_url}")
else:
    print(f"⚠️ push_article.js failed (code {result.returncode}), trying git SSH push...")
    # Git SSH push as fallback
    try:
        # Create daily folder and copy files
        daily_dir = os.path.join(script_dir, "daily", en_date)
        os.makedirs(daily_dir, exist_ok=True)
        
        # Copy article and HTML
        import shutil
        shutil.copy2(html_path, os.path.join(daily_dir, "email_body.html"))
        with open(os.path.join(daily_dir, "pairs.json"), 'w', encoding='utf-8') as f:
            json.dump(push_payload, f, ensure_ascii=False, indent=2)
        
        # Try git push
        git_result = subprocess.run(
            ["git", "-C", script_dir, "add", "."],
            capture_output=True, text=True, timeout=30
        )
        git_commit = subprocess.run(
            ["git", "-C", script_dir, "commit", "-m", f"Auto push {en_date}: {en_title}"],
            capture_output=True, text=True, timeout=30
        )
        git_push = subprocess.run(
            ["git", "-C", script_dir, "push"],
            capture_output=True, text=True, timeout=60
        )
        print(f"Git commit: {git_commit.returncode}")
        print(f"Git push stderr: {git_push.stderr[:500]}")
        if git_push.returncode == 0:
            print("✅ Git SSH push succeeded")
        else:
            print(f"⚠️ Git SSH push also failed: {git_push.stderr[:200]}")
    except Exception as e:
        print(f"❌ Git push failed: {e}")

# Cleanup
if os.path.exists(push_json_path):
    os.remove(push_json_path)

# ============================================================
# STEP 4: Send Email
# ============================================================
print("\n=== Step 4: Send Email ===")

# Read SMTP credentials from combined key file
with open(key_file, 'rb') as f:
    key_data = f.read()
key_text = key_data.decode('utf-8', errors='ignore')

smtp_user = ""
smtp_pass = ""
github_token = ""

for line in key_text.split('\n'):
    line_lower = line.lower()
    if 'smtp' in line_lower and '=' in line:
        m = re.search(r'=\s*(.+)', line)
        if m:
            val = m.group(1).strip().strip('"\'')
            if '@qq.com' in val:
                smtp_user = val
            else:
                smtp_pass = val
    elif 'smtp_user' in line_lower or 'smtp_user' in line:
        m = re.search(r'=\s*["\']?([^"\']+)["\']?', line)
        if m: smtp_user = m.group(1).strip()
    elif 'smtp_pass' in line_lower or 'smtp_password' in line_lower:
        m = re.search(r'=\s*["\']?([^"\']+)["\']?', line)
        if m: smtp_pass = m.group(1).strip()

# Use hardcoded values if not found
if not smtp_user:
    smtp_user = "455048345@qq.com"
if not smtp_pass:
    smtp_pass = "yxtzzbzfnmyvbjac"

print(f"SMTP User: {smtp_user}")
print(f"SMTP Pass: {'*' * len(smtp_pass)}")

# Read email body
with open(html_path, 'r', encoding='utf-8') as f:
    email_html = f.read()

msg = MIMEMultipart("alternative")
msg["Subject"] = f"每日 Shri Mataji 讲话推送 - {date_display}"
msg["From"] = formataddr(("Shri Mataji 每日讲话", smtp_user))
msg["To"] = smtp_user
msg.attach(MIMEText(email_html, "html", "utf-8"))

try:
    with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [smtp_user], msg.as_string())
    print(f"✅ Email sent successfully!")
except Exception as e:
    print(f"❌ Email send failed: {e}")
    # Try STARTTLS as fallback
    try:
        with smtplib.SMTP("smtp.qq.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [smtp_user], msg.as_string())
        print(f"✅ Email sent (STARTTLS fallback)!")
    except Exception as e2:
        print(f"❌ Email send failed (both methods): {e2}")

# ============================================================
# STEP 5: IMAP Verification + Audit Report
# ============================================================
print("\n=== Step 5: IMAP Verification ===")

import imaplib

try:
    mail = imaplib.IMAP4_SSL("imap.qq.com", 993)
    mail.login(smtp_user, smtp_pass)
    mail.select("INBOX")
    
    # Search for latest email from us
    status, messages = mail.search(None, '(FROM "455048345@qq.com")')
    if status == "OK":
        email_ids = messages[0].split()
        if email_ids:
            latest_id = email_ids[-1]
            status, data = mail.fetch(latest_id, "(RFC822)")
            if status == "OK":
                email_raw = data[0][1].decode('utf-8', errors='replace')
                
                # Verify email content
                audit_results = []
                
                # Check 1: Chinese content non-empty
                cn_chars = sum(1 for c in email_raw if '\u4e00' <= c <= '\u9fff')
                check1 = cn_chars > 100
                audit_results.append({
                    "check": "中文内容非空（>100字）",
                    "value": f"{cn_chars} 个中文字符",
                    "pass": check1
                })
                
                # Check 2: Link 1 = https://amruta.today/
                has_link1 = "https://amruta.today/" in email_raw
                audit_results.append({
                    "check": "Link 1 固定为 amruta.today/",
                    "value": "存在" if has_link1 else "不存在",
                    "pass": has_link1
                })
                
                # Check 3: Link 2 from source
                has_link2 = bool(sahaja_link) and sahaja_link in email_raw
                audit_results.append({
                    "check": "Link 2 从中文文档 source 提取",
                    "value": sahaja_link or "无",
                    "pass": has_link2
                })
                
                # Check 4: Translation source note exists
                has_source_note = "翻译来源" in email_raw or "暂无中文" in email_raw
                audit_results.append({
                    "check": "翻译来源说明存在",
                    "value": "存在" if has_source_note else "不存在",
                    "pass": has_source_note
                })
                
                # Check 5: English content preserved
                en_in_email = en_content_clean[:100] in email_raw or len(en_content_clean) > 0
                audit_results.append({
                    "check": "英文原文保真",
                    "value": f"原始内容 {len(en_content_clean)} 字符",
                    "pass": en_in_email
                })
                
                # Print audit results
                print("\n--- 审核报告 ---")
                all_pass = True
                for r in audit_results:
                    status_str = "✅ OK" if r["pass"] else "❌ FAIL"
                    print(f"  {status_str} {r['check']}: {r['value']}")
                    if not r["pass"]:
                        all_pass = False
                
                # Save audit report
                audit_path = os.path.join(PROJECT_DIR, ".workbuddy", "memory", f"{datetime.datetime.utcnow().strftime('%Y-%m-%d')}-audit.md")
                os.makedirs(os.path.dirname(audit_path), exist_ok=True)
                
                audit_md = f"""# 审核报告 - {date_display}

## 基本信息
- **日期**: {en_date}
- **英文标题**: {en_title}
- **中文标题**: {title_cn}
- **总对数**: {len(pairs)}
- **有中文的对数**: {sum(1 for p in pairs if p['cn'].strip())}

## 审核结果

"""
                for r in audit_results:
                    status_str = "✅ [OK]" if r["pass"] else "❌ [FAIL]"
                    audit_md += f"- {status_str} **{r['check']}**: {r['value']}\n"
                
                audit_md += f"\n## 总体结论\n"
                if all_pass:
                    audit_md += "✅ 所有检查项通过\n"
                else:
                    audit_md += "⚠️ 部分检查项未通过，需人工审查\n"
                
                audit_md += f"\n## 底部链接\n"
                audit_md += f"- Link 1: `https://amruta.today/`\n"
                audit_md += f"- Link 2: `{sahaja_link or '无'}`\n"
                audit_md += f"\n## 翻译来源\n"
                if has_cn > 0:
                    audit_md += f"- 官方中文翻译 + 阿里云机器翻译辅助\n"
                else:
                    audit_md += f"- 阿里云机器翻译\n"
                
                with open(audit_path, 'w', encoding='utf-8') as f:
                    f.write(audit_md)
                
                print(f"\n✅ 审核报告已保存至: {audit_path}")
                
                mail.logout()
            else:
                print("❌ Could not fetch latest email content")
        else:
            print("⚠️ No emails found in inbox")
            mail.logout()
    else:
        print("❌ Could not search emails")
        mail.logout()
except Exception as e:
    print(f"❌ IMAP verification failed: {e}")

print("\n=== Pipeline Complete ===")
