#!/usr/bin/env python3
"""
Step2.3: LLM 摘取官方中文
让 LLM 从 F盘文档中摘取与 amruta.today 英文内容对应的官方中文
"""
import json
import re
import urllib.request
import ssl
import os

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

def call_llm(user_prompt, system_prompt="你是专家。", max_tokens=8000):
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

# 读取 Step2.1/2.2 的状态
with open(".step2_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)

en_title = state["en_title"]
en_content = state["en_content"]
date_str = state["date_str"]
found_doc = state["found_doc"]

print(f"=== Step2.3: LLM 摘取官方中文 ===")
print(f"日期: {date_str}")
print(f"英文标题: {en_title}")
print(f"找到文档: {os.path.basename(found_doc)}")

# 读取 F盘文档全文
with open(found_doc, "r", encoding="utf-8") as f:
    doc_content = f.read()

# 提取 source URL
fm_match = re.match(r'^---\n(.*?)\n---', doc_content, re.DOTALL)
sahaja_link = "https://www.sahaja.live/"
if fm_match:
    link_match = re.search(r'source:\s*(.*)', fm_match.group(1))
    if link_match:
        sahaja_link = link_match.group(1).strip()

# 写入 tmp01.md（amruta.today 英文 + F盘全文）
with open("tmp01.md", "w", encoding="utf-8") as f:
    f.write(f"# 英文标题: {en_title}\n")
    f.write(f"# 日期: {date_str}\n")
    f.write(f"# Source: {sahaja_link}\n\n")
    f.write("## amruta.today 英文内容\n")
    f.write(en_content + "\n\n")
    f.write("## F盘官方文档全文\n")
    f.write(doc_content + "\n")

print(f"  ✅ 已写入 tmp01.md")
print(f"  F盘文档长度: {len(doc_content)} 字符")

# 让 LLM 从 tmp01.md 中摘取对应的官方中文
llm_prompt = f"""你是翻译对齐专家。

## 任务
从 F盘官方文档中摘取与 amruta.today 英文内容对应的官方中文。

## amruta.today 英文内容
{en_content}

## F盘官方文档全文
{doc_content}

## 要求
1. 找到 amruta.today 英文内容在 F盘文档中对应的段落
2. 摘取对应的官方中文翻译
3. 只输出摘取的内容，不要输出其他内容

## 输出格式
[
  {{
    "en": "amruta.today 英文段落",
    "zh": "F盘官方中文段落"
  }},
  ...
]"""

llm_resp = call_llm(llm_prompt, "你是翻译对齐专家。", max_tokens=8000)
json_match = re.search(r'\[.*\]', llm_resp, re.DOTALL)
extracted = json.loads(json_match.group()) if json_match else []

print(f"  LLM 摘取了 {len(extracted)} 段官方中文")

# 只保留 amruta.today 英文 + 摘取的官方中文
with open("tmp01.md", "w", encoding="utf-8") as f:
    f.write(f"# 英文标题: {en_title}\n")
    f.write(f"# 日期: {date_str}\n")
    f.write(f"# Source: {sahaja_link}\n\n")
    f.write("## amruta.today 英文内容\n")
    for item in extracted:
        f.write(f"[AMRUTA-EN] {item['en']}\n\n")
    f.write("## F盘官方中文内容\n")
    for item in extracted:
        f.write(f"[OFFICIAL-ZH] {item['zh']}\n\n")

print(f"  ✅ tmp01.md 已清理，只保留摘取的官方中文")

# 保存到状态文件
state["extracted"] = extracted
state["sahaja_link"] = sahaja_link
with open(".step2_state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f"\n✅ Step2.3 完成。请检查 tmp01.md 的内容是否正确。")
print(f"确认无误后，执行 Step2.4")
