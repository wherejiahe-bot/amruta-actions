#!/usr/bin/env python3
"""测试 LLM 标题获取"""
import json
import urllib.request
import ssl
import re

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

# 读取 F盘文档
doc_path = r"F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md"
with open(doc_path, "r", encoding="utf-8") as f:
    doc = f.read()

doc_body = re.sub(r'^---\n.*?\n---\n', '', doc, flags=re.DOTALL)

en_title = "Fixing up priorities"

# 方法1：直接问 LLM
prompt1 = f"""从以下 F盘官方文档中找到英文标题 "{en_title}" 对应的中文关键词。

F盘官方文档全文:
{doc_body}

只输出中文标题关键词，不要输出其他内容。"""

payload = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是翻译专家。"},
        {"role": "user", "content": prompt1}
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

with urllib.request.urlopen(req, timeout=180, context=ssl_context) as response:
    resp = json.loads(response.read().decode("utf-8"))
    result = resp["choices"][0]["message"]["content"]
    print(f"方法1结果: {result}")

# 方法2：让 LLM 搜索"优先级"
prompt2 = f"""在以下 F盘官方文档中，搜索"优先级"这个词，告诉我它在什么上下文中出现的。

F盘官方文档全文:
{doc_body}"""

payload2 = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是搜索专家。"},
        {"role": "user", "content": prompt2}
    ],
    "temperature": 0.0,
    "max_tokens": 200
}

req2 = urllib.request.Request(
    BASE_URL + "/chat/completions",
    data=json.dumps(payload2).encode("utf-8"),
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    method="POST"
)

with urllib.request.urlopen(req2, timeout=180, context=ssl_context) as response:
    resp2 = json.loads(response.read().decode("utf-8"))
    result2 = resp2["choices"][0]["message"]["content"]
    print(f"\n方法2结果:\n{result2}")
