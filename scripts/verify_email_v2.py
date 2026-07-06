#!/usr/bin/env python3
"""LLM 验证邮件内容 - 完整版"""
import json
import urllib.request
import ssl
import re

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

# 读取 email_body.html
with open("email_body.html", "r", encoding="utf-8") as f:
    html = f.read()

title_en = re.search(r'<h1>(.*?)</h1>', html).group(1)
title_cn = re.search(r'<h2>(.*?)</h2>', html).group(1)
date = re.search(r'<p class="date">(.*?)</p>', html).group(1)

en_texts = re.findall(r'<p class="en-text">(.*?)</p>', html)
zh_texts = re.findall(r'<p class="zh-text">(.*?)</p>', html)

print(f"标题英文: {title_en}")
print(f"标题中文: {title_cn}")
print(f"日期: {date}")
print(f"英文句子数: {len(en_texts)}")
print(f"中文句子数: {len(zh_texts)}")

# 读取 F盘文档全文
doc_path = r"F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md"
with open(doc_path, "r", encoding="utf-8") as f:
    doc_full = f.read()

# 构造验证 prompt
pairs_text = ""
for i in range(min(5, len(en_texts))):
    pairs_text += f"英文{i+1}: {en_texts[i]}\n中文{i+1}: {zh_texts[i]}\n\n"

prompt = f"""你是内容审核专家。请验证以下邮件内容：

## 邮件标题
- 英文: {title_en}
- 中文: {title_cn}
- 日期: {date}

## 前 5 句对照
{pairs_text}

## F盘官方文档全文
{doc_full}

## 验证要求
1. 标题验证：中文标题是否与英文标题语义对应？
2. 句子验证：前5句中，中文是否出现在 F盘官方文档中？
3. 完整性：中文句子是否完整？

## 输出格式
{{
  "title_valid": true/false,
  "alignment": [
    {{
      "index": 1,
      "en": "英文",
      "zh": "中文",
      "in_official": true/false,
      "complete": true/false
    }}
  ],
  "overall": "通过/不通过"
}}"""

payload = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是内容审核专家。"},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.0,
    "max_tokens": 4000
}

ssl_context = ssl.create_default_context()
req = urllib.request.Request(
    BASE_URL + "/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    method="POST"
)

print("调用 LLM 验证...")
with urllib.request.urlopen(req, timeout=180, context=ssl_context) as response:
    resp = json.loads(response.read().decode("utf-8"))
    content = resp["choices"][0]["message"]["content"]
    print("\n=== LLM 验证结果 ===")
    print(content)
