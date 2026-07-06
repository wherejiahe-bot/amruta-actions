#!/usr/bin/env python3
"""测试 tmp01.md 标题获取"""
import json
import urllib.request
import ssl

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

with open("tmp01.md", "r", encoding="utf-8") as f:
    tmp01 = f.read()

en_title = "Fixing up priorities"

prompt = f"""你是翻译专家。从以下文档中找到英文标题 "{en_title}" 对应的中文关键词。

文档内容:
{tmp01}

只输出中文标题关键词，不要输出其他内容。"""

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

with urllib.request.urlopen(req, timeout=180, context=ssl_context) as response:
    resp = json.loads(response.read().decode("utf-8"))
    result = resp["choices"][0]["message"]["content"]
    print(f"LLM 返回: '{result}'")
