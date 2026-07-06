#!/usr/bin/env python3
"""Step2.5: LLM 提取段落 + 句子对齐"""
import json
import subprocess
import re

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

# 读取文章
with open("article_raw.json", "r", encoding="utf-8") as f:
    article = json.load(f)[0]

en_content = article["content"]

# 读取 F盘文档
doc_path = r"F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md"
with open(doc_path, "r", encoding="utf-8") as f:
    doc_content = f.read()

# 写入临时文件
with open("tmp/en_content.txt", "w", encoding="utf-8") as f:
    f.write(en_content)

with open("tmp/doc_content.txt", "w", encoding="utf-8") as f:
    f.write(doc_content)

# 构造 prompt
prompt = """你是翻译对齐专家。请完成以下任务：

## 任务
1. 读取 F盘文档中的官方中文翻译
2. 将英文句子与官方中文句子对齐
3. 确保每句英文对应一句完整中文

## 英文文章内容
""" + en_content + """

## F盘文档全文
""" + doc_content + """

## 要求
- 一句英文对应一句完整中文
- 中文句子不能被截断
- 如果官方中文有缺失，用 LLM 补充

## 输出格式
请用 JSON 输出：
{
  "pairs": [
    {
      "en_para": "英文段落",
      "zh_para": "官方中文段落",
      "sentences": [
        {"en": "英文句子", "zh": "中文句子"}
      ]
    }
  ]
}

注意：zh_para 和 zh 必须来自 F盘文档的官方中文，不能自己翻译。"""

# 写入 prompt 文件
with open("tmp/prompt.txt", "w", encoding="utf-8") as f:
    f.write(prompt)

# 调用 LLM
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是翻译对齐专家。"},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.0,
    "max_tokens": 8000
}

# 用 Python 调用 API 避免命令行过长
import urllib.request
import ssl

ssl_context = ssl.create_default_context()
req = urllib.request.Request(
    BASE_URL + "/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=120, context=ssl_context) as response:
        resp = json.loads(response.read().decode("utf-8"))
        content = resp["choices"][0]["message"]["content"]
        
        # 提取 JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            align_result = json.loads(json_match.group())
            pairs = align_result.get("pairs", [])
            print(f"  ✅ 对齐完成: {len(pairs)} 个段落")
            
            # 保存
            with open("align_result.json", "w", encoding="utf-8") as f:
                json.dump({"pairs": pairs}, f, ensure_ascii=False, indent=2)
        else:
            print(f"  ❌ 无法解析 LLM 返回")
            print(content[:500])
except Exception as e:
    print(f"  ❌ 调用失败: {e}")
