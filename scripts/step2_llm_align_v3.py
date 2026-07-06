#!/usr/bin/env python3
"""LLM 句子拆分和对齐 - 完整版"""
import json
import urllib.request
import ssl

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

# 读取 amruta.today 英文
with open("article_raw.json", "r", encoding="utf-8") as f:
    article = json.load(f)[0]

en_content = article["content"]

# 读取 F盘文档全文
doc_path = r"F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md"
with open(doc_path, "r", encoding="utf-8") as f:
    doc_full = f.read()

# 构造 prompt
prompt = f"""你是翻译对齐专家。

## 任务
1. 从 F盘官方文档中找到与 amruta.today 英文内容对应的段落
2. 将英文段落拆分为句子
3. 每句英文对应一句官方中文
4. 输出 pairs 列表

## amruta.today 英文内容
{en_content}

## F盘官方文档全文
{doc_full}

## 要求
- 中文必须来自 F盘官方文档
- 一句英文对应一句完整中文
- 如果官方中文有缺失，用 LLM 补充

## 输出格式
[
  {{
    "en_para": "英文段落",
    "zh_para": "官方中文段落",
    "sentences": [
      {{"en": "英文句子", "zh": "中文句子"}}
    ]
  }}
]"""

payload = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是翻译对齐专家。"},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.0,
    "max_tokens": 8000
}

ssl_context = ssl.create_default_context()
req = urllib.request.Request(
    BASE_URL + "/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    method="POST"
)

print("调用 LLM 对齐...")
with urllib.request.urlopen(req, timeout=180, context=ssl_context) as response:
    resp = json.loads(response.read().decode("utf-8"))
    content = resp["choices"][0]["message"]["content"]
    
    import re
    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if json_match:
        pairs = json.loads(json_match.group())
        print(f"✅ 对齐完成: {len(pairs)} 个段落")
        
        with open("pairs.json", "w", encoding="utf-8") as f:
            json.dump(pairs, f, ensure_ascii=False, indent=2)
        
        total_sents = sum(len(p["sentences"]) for p in pairs)
        print(f"总句子数: {total_sents}")
    else:
        print(f"❌ 无法解析: {content[:200]}")
