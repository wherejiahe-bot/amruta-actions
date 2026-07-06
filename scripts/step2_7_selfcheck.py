#!/usr/bin/env python3
"""
Step2.7: LLM 自检
"""
import json
import re
import urllib.request
import ssl

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

def call_llm(user_prompt, system_prompt="你是专家。", max_tokens=2000):
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

# 读取 pairs.json
with open("pairs.json", "r", encoding="utf-8") as f:
    pairs = json.load(f)

print(f"=== Step2.7: LLM 自检 ===")
print(f"句子对数: {sum(len(p['sentences']) for p in pairs)}")

self_check_prompt = f"""你是内容审核专家。请自检以下翻译对齐结果：

## 检查项
1. 英文和中文是否语义对齐
2. 翻译是否准确通顺
3. 中文句子是否完整（未被截断）
4. 中文是否来自 F盘官方文档

## 对齐结果
{json.dumps(pairs, ensure_ascii=False, indent=2)}

## 输出格式
{{
  "total_pairs": 总数,
  "issues_found": 发现的问题数,
  "corrections": [
    {{"pair_index": 0, "issue": "问题描述", "correction": "修正内容"}}
  ]
}}"""

sc_content = call_llm(self_check_prompt, "你是内容审核专家。", max_tokens=2000)
sc_match = re.search(r'\{.*\}', sc_content, re.DOTALL)
if sc_match:
    self_check = json.loads(sc_match.group())
    print(f"  自检问题: {self_check.get('issues_found', 0)}")
    if self_check.get('corrections'):
        for c in self_check['corrections']:
            print(f"    修正: {c['issue']}")
else:
    print(f"  ⚠️ 自检结果解析失败")

print(f"\n✅ Step2.7 完成。")
print(f"确认无误后，执行 Step2.8")
