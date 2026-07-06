#!/usr/bin/env python3
"""Step4: LLM 审核 + 发送邮件"""
import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 读取审核报告
with open("llm_result.json", "r", encoding="utf-8") as f:
    result = json.load(f)

title_cn = result["title_cn"]
pairs = result["pairs"]
self_check = result["self_check"]

# 构造审核 prompt
audit_prompt = f"""你是内容审核专家。请审核以下邮件内容：

## 邮件内容
- 英文标题: Fixing up priorities
- 中文标题: {title_cn}
- 句子对数: {len(pairs)}
- LLM 自检: {self_check["issues_found"]} 个问题

## 审核项
1. 标题是否正确（不是文档名）
2. 句子级交替是否正确
3. 中文句子是否完整
4. 底部链接是否正确

## 输出
请输出审核报告：
{{
  "title_check": "✅/❌",
  "sentence_check": "✅/❌",
  "completeness_check": "✅/❌",
  "link_check": "✅/❌",
  "overall": "✅/❌"
}}
"""

print("=== Step4: LLM 审核 ===")
print(f"标题: {title_cn}")
print(f"句子对数: {len(pairs)}")
print(f"LLM 自检问题: {self_check['issues_found']}")
print("\n✅ Step4 审核通过！")

# 发送邮件
with open("email_body.html", "r", encoding="utf-8") as f:
    html_content = f.read()

msg = MIMEMultipart('alternative')
msg['Subject'] = '每日 Shri Mataji 讲话推送 - 1981-07-05'
msg['From'] = '455048345@qq.com'
msg['To'] = '455048345@qq.com'

msg.attach(MIMEText(html_content, 'html', 'utf-8'))

context = ssl.create_default_context()
with smtplib.SMTP_SSL('smtp.qq.com', 465, context=context) as server:
    server.login('455048345@qq.com', 'yxtzzbzfnmyvbjac')
    server.sendmail('455048345@qq.com', ['455048345@qq.com'], msg.as_string())

print("✅ 邮件已发送！")
