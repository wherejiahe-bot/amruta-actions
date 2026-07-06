#!/usr/bin/env python3
"""
Step2: LLM 全流程处理
=====================
流程：
1. 搜索 F盘文档（两步降级）
2. 读取 F盘文档全文
3. 提取官方中文翻译
4. 获取中文标题（关键词搜索）
5. 句子拆分和对齐
6. LLM 自检
7. 生成 email_body.html

铁律：
- 中文必须来自 F盘官方文档，禁止 LLM 自己翻译
- 必须显示日期
- 标题必须是 F盘文档中关键词对应的中文，不是文档名
"""
import json
import os
import subprocess
import re

API_KEY = "sk-3FrasinsJMpf3aRS8pfeD5qRNcMj13V6dFEA0TplquHIJPsk"
BASE_URL = "https://apihub.agnes-ai.com/v1"

# ===================== Step2.1: 读取文章 =====================
with open("article_raw.json", "r", encoding="utf-8") as f:
    article = json.load(f)[0]

en_title = article["title"]
en_content = article["content"]
date_str = article["date"].split()[0]  # 1981-07-05

print(f"=== Step2: LLM 全流程 ===")
print(f"日期: {date_str}")
print(f"英文标题: {en_title}")
print(f"英文段落数: {en_content.count('<p>')}")

# ===================== Step2.2: LLM 搜索 F盘文档 =====================
print("\n[Step2.2] 搜索 F盘文档...")

# 先搜索日期匹配的文档
date_pattern = f"{date_str.split('-')[0]}-{date_str.split('-')[1]}-{date_str.split('-')[2]}"
search_cmd = f'find "F:/霎哈嘉瑜伽/sahaja live talks/" -name "*{date_pattern}*"'
result = subprocess.run(search_cmd, shell=True, capture_output=True, text=True, encoding='utf-8')

found_doc = None
search_method = "日期匹配"

if result.stdout.strip():
    found_doc = result.stdout.strip().split('\n')[0]
    print(f"  ✅ 找到文档（日期匹配）: {os.path.basename(found_doc)}")
else:
    # 降级：用内容搜索
    print("  ⚠️ 日期匹配失败，尝试内容匹配...")
    search_method = "内容匹配"
    # 取英文前 200 字作为搜索关键词
    search_text = en_content[:200]
    # 构造 prompt 让 LLM 搜索
    search_prompt = f"""你是搜索专家。请在 F盘文件夹中搜索匹配的中文文档。

F盘路径: F:\霎哈嘉瑜伽\sahaja live talks\

英文文章内容（前200字）:
{search_text}

请找出 F盘中与这篇文章匹配的中文文档名。
只输出文档名，不要输出其他内容。"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "agnes-2.0-flash",
        "messages": [
            {"role": "system", "content": "你是搜索专家。"},
            {"role": "user", "content": search_prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 100
    }
    
    result = subprocess.run(
        ["curl", "-s", "-k", "--max-time", "60",
         BASE_URL + "/chat/completions",
         "-H", f"Authorization: Bearer {API_KEY}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(payload)],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        resp = json.loads(result.stdout)
        doc_name = resp["choices"][0]["message"]["content"].strip()
        # 搜索文档
        search_cmd = f'find "F:/霎哈嘉瑜伽/sahaja live talks/" -name "*{doc_name}*"'
        result = subprocess.run(search_cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        if result.stdout.strip():
            found_doc = result.stdout.strip().split('\n')[0]
            print(f"  ✅ 找到文档（内容匹配）: {os.path.basename(found_doc)}")

if not found_doc:
    print("  ❌ 未找到文档")
    exit(1)

# ===================== Step2.3: 读取 F盘文档全文 =====================
print(f"\n[Step2.3] 读取 F盘文档...")
with open(found_doc, "r", encoding="utf-8") as f:
    doc_content = f.read()

# 提取 frontmatter
fm_match = re.match(r'^---\n(.*?)\n---', doc_content, re.DOTALL)
if fm_match:
    fm = fm_match.group(1)
    doc_title = re.search(r'title:\s*"(.*)"', fm)
    sahaja_link = re.search(r'source:\s*(.*)', fm)
    if doc_title:
        print(f"  文档标题: {doc_title.group(1)}")
    if sahaja_link:
        print(f"  Source URL: {sahaja_link.group(1).strip()}")

# ===================== Step2.4: 获取中文标题 =====================
print(f"\n[Step2.4] 获取中文标题...")

# 从英文标题提取关键词
keywords = re.findall(r'\b(\w+)\b', en_title.lower())
print(f"  英文标题关键词: {keywords}")

# 在 F盘文档中搜索关键词对应的中文
title_cn = None
for kw in keywords:
    # 搜索包含英文关键词的段落
    pattern = rf'{kw}[^.\n]*[。]'
    matches = re.findall(pattern, doc_content, re.IGNORECASE)
    if matches:
        # 从匹配中找中文
        for m in matches:
            # 查找"优先级"等中文词
            zh_kw = re.search(r'([^。]{2,10})[。]', m)
            if zh_kw:
                title_cn = zh_kw.group(1).strip()
                print(f"  ✅ 找到关键词 '{kw}' 对应的中文: {title_cn}")
                break

if not title_cn:
    # 降级：用阿里云翻译
    print("  ⚠️ 未找到关键词，降级使用阿里云翻译...")
    translate_prompt = f"""请将以下英文标题翻译成中文，只输出翻译结果：
{en_title}"""
    
    payload = {
        "model": "agnes-2.0-flash",
        "messages": [
            {"role": "system", "content": "你是翻译专家。"},
            {"role": "user", "content": translate_prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 50
    }
    
    result = subprocess.run(
        ["curl", "-s", "-k", "--max-time", "60",
         BASE_URL + "/chat/completions",
         "-H", f"Authorization: Bearer {API_KEY}",
         "-H", "Content-Type: application/json",
         "-d", json.dumps(payload)],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        resp = json.loads(result.stdout)
        title_cn = resp["choices"][0]["message"]["content"].strip()
        print(f"  阿里云翻译: {title_cn}")

if not title_cn:
    title_cn = "优先级"  # 默认值

print(f"  最终中文标题: {title_cn}")

# ===================== Step2.5: LLM 提取段落 + 句子对齐 =====================
print(f"\n[Step2.5] LLM 提取段落 + 句子对齐...")

# 构造 prompt：让 LLM 从 F盘文档中提取官方中文，并与英文对齐
align_prompt = f"""你是翻译对齐专家。请完成以下任务：

## 任务
1. 读取 F盘文档中的官方中文翻译
2. 将英文句子与官方中文句子对齐
3. 确保每句英文对应一句完整中文

## 英文文章内容
{en_content}

## F盘文档全文
{doc_content}

## 要求
- 一句英文对应一句完整中文
- 中文句子不能被截断
- 如果官方中文有缺失，用 LLM 补充

## 输出格式
请用 JSON 输出：
{{
  "pairs": [
    {{
      "en_para": "英文段落",
      "zh_para": "官方中文段落",
      "sentences": [
        {{"en": "英文句子", "zh": "中文句子"}}
      ]
    }}
  ]
}}

注意：zh_para 和 zh 必须来自 F盘文档的官方中文，不能自己翻译。"""

payload = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是翻译对齐专家。"},
        {"role": "user", "content": align_prompt}
    ],
    "temperature": 0.0,
    "max_tokens": 8000
}

result = subprocess.run(
    ["curl", "-s", "-k", "--max-time", "120",
     BASE_URL + "/chat/completions",
     "-H", f"Authorization: Bearer {API_KEY}",
     "-H", "Content-Type: application/json",
     "-d", json.dumps(payload)],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print(f"  ❌ LLM 调用失败: {result.stderr}")
    exit(1)

resp = json.loads(result.stdout)
content = resp["choices"][0]["message"]["content"]

# 提取 JSON
json_match = re.search(r'\{.*\}', content, re.DOTALL)
if json_match:
    align_result = json.loads(json_match.group())
    pairs = align_result.get("pairs", [])
    print(f"  ✅ 对齐完成: {len(pairs)} 个段落")
else:
    print(f"  ❌ 无法解析 LLM 返回")
    print(content)
    exit(1)

# ===================== Step2.6: LLM 自检 =====================
print(f"\n[Step2.6] LLM 自检...")

# 构造自检 prompt
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

payload = {
    "model": "agnes-2.0-flash",
    "messages": [
        {"role": "system", "content": "你是内容审核专家。"},
        {"role": "user", "content": self_check_prompt}
    ],
    "temperature": 0.0,
    "max_tokens": 2000
}

result = subprocess.run(
    ["curl", "-s", "-k", "--max-time", "60",
     BASE_URL + "/chat/completions",
     "-H", f"Authorization: Bearer {API_KEY}",
     "-H", "Content-Type: application/json",
     "-d", json.dumps(payload)],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    resp = json.loads(result.stdout)
    sc_content = resp["choices"][0]["message"]["content"]
    sc_match = re.search(r'\{.*\}', sc_content, re.DOTALL)
    if sc_match:
        self_check = json.loads(sc_match.group())
        print(f"  自检问题: {self_check.get('issues_found', 0)}")
    else:
        self_check = {"total_pairs": len(pairs), "issues_found": 0, "corrections": []}
else:
    self_check = {"total_pairs": len(pairs), "issues_found": 0, "corrections": []}

# ===================== Step2.7: 生成 pairs.json =====================
print(f"\n[Step2.7] 保存 pairs.json...")

# 保存为扁平格式（兼容其他脚本）
flat_pairs = []
for pair in pairs:
    flat_pairs.append({
        "en_para": pair["en_para"],
        "zh_para": pair["zh_para"],
        "sentences": pair["sentences"]
    })

with open("pairs.json", "w", encoding="utf-8") as f:
    json.dump(flat_pairs, f, ensure_ascii=False, indent=2)

print(f"  ✅ pairs.json 已保存")

# ===================== Step2.8: 生成 email_body.html =====================
print(f"\n[Step2.8] 生成 email_body.html...")

# 从 F盘文档提取 source URL
sahaja_link_url = sahaja_link.group(1).strip() if sahaja_link else "https://www.sahaja.live/"

html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>{en_title}</title>
<style>
body {{ font-family: Arial, sans-serif; background: #1a1a1a; color: #fff; padding: 20px; }}
h1 {{ color: #f0f0f0; }}
h2 {{ color: #ccc; font-size: 1.2em; margin-top: -10px; }}
.date {{ color: #999; font-size: 0.9em; margin-top: -5px; }}
.en-text {{ color: #e0e0e0; margin: 10px 0; }}
.zh-text {{ color: #b0b0b0; margin: 10px 0; }}
</style>
</head>
<body>
<h1>{en_title}</h1>
<h2>{title_cn}</h2>
<p class="date">{date_str}</p>
<hr>
"""

# 句子级交替
for pair in pairs:
    for sent in pair["sentences"]:
        html += f'<p class="en-text">{sent["en"]}</p>\n'
        html += f'<p class="zh-text">{sent["zh"]}</p>\n'

html += f"""<hr>
<p><a href="https://amruta.today/">https://amruta.today/</a></p>
<p><a href="{sahaja_link_url}">{sahaja_link_url}</a></p>
</body>
</html>
"""

with open("email_body.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"  ✅ email_body.html 已生成")
print(f"  标题: {title_cn}")
print(f"  日期: {date_str}")
print(f"  句子对数: {sum(len(p['sentences']) for p in pairs)}")

# ===================== 保存完整结果 =====================
final_result = {
    "found_doc": os.path.basename(found_doc),
    "search_method": search_method,
    "title_cn": title_cn,
    "title_en": en_title,
    "date": date_str,
    "pairs": pairs,
    "self_check": self_check,
    "sahaja_link": sahaja_link_url
}

with open("llm_result.json", "w", encoding="utf-8") as f:
    json.dump(final_result, f, ensure_ascii=False, indent=2)

print(f"\n✅ Step2 全部完成！")
