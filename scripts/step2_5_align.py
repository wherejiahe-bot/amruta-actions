#!/usr/bin/env python3
"""
Step2.5 + 2.6: LLM 段落对齐 + 句子拆分
"""
import json
import re
import urllib.request
import ssl

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

# 读取 tmp01.md
with open("tmp01.md", "r", encoding="utf-8") as f:
    tmp01 = f.read()

print(f"=== Step2.5+2.6: LLM 段落对齐 + 句子拆分 ===")

align_prompt = f"""你是翻译对齐专家。

## 任务
1. 从以下文档中提取官方中文，与英文段落对齐
2. 根据句意将段落拆分为句子
3. 一句英文对应一句完整中文
4. 允许 1对1、多对1、1对多，但不允许多对多

## 文档内容
{tmp01}

## 要求
- 中文必须来自文档中的官方中文段落
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

align_resp = call_llm(align_prompt, "你是翻译对齐专家。", max_tokens=8000)
json_match = re.search(r'\[.*\]', align_resp, re.DOTALL)
pairs = json.loads(json_match.group()) if json_match else []
print(f"  ✅ 对齐完成: {len(pairs)} 段落, {sum(len(p['sentences']) for p in pairs)} 句子")

# 保存 pairs.json
with open("pairs.json", "w", encoding="utf-8") as f:
    json.dump(pairs, f, ensure_ascii=False, indent=2)

print(f"  ✅ pairs.json 已保存")

# 保存到状态文件
with open(".step2_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)
state["pairs"] = pairs
with open(".step2_state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f"\n✅ Step2.5+2.6 完成。请检查 pairs.json 的内容是否正确。")
print(f"确认无误后，执行 Step2.7")
