#!/usr/bin/env python3
"""LLM 获取中文标题"""
import json
import urllib.request
import ssl
import re

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

en_title = "Fixing up priorities"

# 读取 F盘文档
doc_path = r"F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md"
with open(doc_path, "r", encoding="utf-8") as f:
    doc = f.read()

# 去掉 frontmatter
doc = re.sub(r'^---\n.*?\n---\n', '', doc, flags=re.DOTALL)

prompt = f"""你是翻译专家。

## 任务
从 F盘官方文档中找到英文标题 "{en_title}" 对应的中文关键词。

## F盘官方文档全文
{doc}

## 要求
- 找到英文标题中关键词对应的中文翻译
- 只输出中文关键词，不要输出其他内容

## 输出
只输出中文标题，如：优先级"""

payload = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是翻译专家。"},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.0,
    "max_tokens": 50
}

ssl_context = ssl.create_default_context()
req = urllib.request.Request(
    BASE_URL + "/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(req, timeout=60, context=ssl_context) as response:
    resp = json.loads(response.read().decode("utf-8"))
    title_cn = resp["choices"][0]["message"]["content"].strip()
    print(f"中文标题: {title_cn}")
