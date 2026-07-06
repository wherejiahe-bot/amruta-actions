#!/usr/bin/env python3
"""LLM 自检：逐对校验英中句子对齐"""
import json
import subprocess
import sys

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

# 读取 pairs.json
with open("pairs.json", "r", encoding="utf-8") as f:
    pairs = json.load(f)

# 提取所有句子对
sents = []
for item in pairs:
    for s in item.get("sentences", []):
        en = (s.get("en") or "").strip()
        zh = (s.get("zh") or "").strip()
        if en or zh:
            sents.append({"idx": len(sents), "en": en, "zh": zh})

print(f"提取了 {len(sents)} 个句子对")

# 构建 prompt
pairs_text = ""
for p in sents:
    pairs_text += f'Pair {p["idx"]}:\n  EN: {p["en"][:150]}\n  ZH: {p["zh"][:150]}\n\n'

prompt = f"""你是一个专业的英中翻译质量审核员。请逐对检查以下英中句子对齐结果。

任务：
1. 语义对齐检查：英文句子和中文句子是否意思对应？
2. 翻译质量检查：中文翻译是否准确、通顺？有无漏译、错译？
3. 明显错误检查：是否有完全不对应的句子对？

请返回一个 JSON 数组，每个元素包含：
- idx: 句子对索引
- status: "ok" 或 "fix"
- corrected_en: 修正后的英文
- corrected_zh: 修正后的中文
- reason: 修正原因

输入句子对：
{pairs_text}

注意：只对确实有问题的句子对进行修正。只返回 JSON 数组，不要其他文字。"""

# 构建 API 请求 payload
payload = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是一个专业的英中翻译质量审核员。"},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.1,
    "max_tokens": 8000
}

# 用 curl 调用
cmd = [
    "curl", "-s", "-k", "--max-time", "60",
    f"{BASE_URL}/chat/completions",
    "-H", "Content-Type: application/json",
    "-H", f"Authorization: Bearer {API_KEY}",
    "-d", json.dumps(payload, ensure_ascii=False)
]

print("调用 LLM...")
result = subprocess.run(cmd, capture_output=True, text=True, timeout=65)
resp = json.loads(result.stdout)

if "choices" in resp and resp["choices"]:
    content = resp["choices"][0]["message"]["content"].strip()
    print(f"收到响应: {len(content)} 字符")
    
    # 提取 JSON
    import re
    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if json_match:
        results = json.loads(json_match.group(0))
        print(f"解析到 {len(results)} 条结果")
        
        ok_count = sum(1 for r in results if r.get("status") == "ok")
        fix_count = sum(1 for r in results if r.get("status") == "fix")
        print(f"通过: {ok_count}, 需修正: {fix_count}")
        
        # 保存结果
        with open("self_check_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # 生成报告
        report = f"# LLM 自检报告\n\n总句子对: {len(sents)}\n通过: {ok_count}\n需修正: {fix_count}\n\n"
        for r in results:
            if r.get("status") == "fix":
                report += f"Pair {r['idx']}: {r.get('reason', '')}\n"
                report += f"  EN: {r.get('corrected_en', '')[:100]}\n"
                report += f"  ZH: {r.get('corrected_zh', '')[:100]}\n\n"
        
        with open("self_check_report.txt", "w", encoding="utf-8") as f:
            f.write(report)
        print("报告已保存到 self_check_report.txt")
    else:
        print("无法解析 JSON 响应")
        print(content[:500])
else:
    print("API 返回错误:")
    print(json.dumps(resp, indent=2, ensure_ascii=False))
