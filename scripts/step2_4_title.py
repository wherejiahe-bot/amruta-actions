#!/usr/bin/env python3
"""
Step2.4: 获取中文标题
LLM 从 tmp01.md 中找到英文标题关键词对应的中文
"""
import json
import re
import urllib.request
import ssl

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

def call_llm(user_prompt, system_prompt="你是专家。", max_tokens=50):
    payload = {
        "model": "agnes-2.0-flash",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens
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
        return resp["choices"][0]["message"]["content"]

# 读取状态
with open(".step2_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)

en_title = state["en_title"]

# 读取 tmp01.md
with open("tmp01.md", "r", encoding="utf-8") as f:
    tmp01 = f.read()

print(f"=== Step2.4: 获取中文标题 ===")
print(f"英文标题: {en_title}")

# 让 LLM 找中文标题
title_prompt = f"""你是翻译专家。从以下文档中找到英文标题 "{en_title}" 对应的中文关键词。

文档内容:
{tmp01}

只输出中文标题关键词，不要输出其他内容。"""

title_cn = call_llm(title_prompt, "你是翻译专家。", max_tokens=50)
print(f"  中文标题: {title_cn.strip()}")

# 保存到状态文件
state["title_cn"] = title_cn.strip()
with open(".step2_state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f"\n✅ Step2.4 完成。")
print(f"确认无误后，执行 Step2.5")
