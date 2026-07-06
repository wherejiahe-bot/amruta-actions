#!/usr/bin/env python3
"""段落匹配：将 amruta.today 英文段落与 F盘官方中文段落匹配"""
import json
import re

# 读取 amruta.today 英文
with open("article_raw.json", "r", encoding="utf-8") as f:
    article = json.load(f)[0]

en_content = article["content"]
en_paragraphs = re.findall(r'<p>(.*?)</p>', en_content, re.DOTALL)
print(f"amruta.today 英文段落数: {len(en_paragraphs)}")

# 读取 F盘官方中文
with open("tmp/official_paras.json", "r", encoding="utf-8") as f:
    official = json.load(f)

zh_paragraphs = official["zh_paras"]
print(f"F盘官方中文段落数: {len(zh_paragraphs)}")

# 按相似度匹配
# 取每段前 50 字做比较
def similarity(a, b):
    a_words = set(a[:50].split())
    b_words = set(b[:50].split())
    if not a_words or not b_words:
        return 0
    return len(a_words & b_words) / len(a_words | b_words)

# 匹配：英文段落按内容找对应的中文段落
matches = []
used_zh = set()

for i, en_p in enumerate(en_paragraphs):
    best_j = -1
    best_score = 0
    
    for j, zh_p in enumerate(zh_paragraphs):
        if j in used_zh:
            continue
        score = similarity(en_p, zh_p)
        if score > best_score:
            best_score = score
            best_j = j
    
    if best_j >= 0 and best_score > 0.1:
        matches.append({
            "en_idx": i,
            "zh_idx": best_j,
            "en": en_p.replace("<p>", "").replace("</p>", ""),
            "zh": zh_paragraphs[best_j]
        })
        used_zh.add(best_j)

print(f"\n匹配成功: {len(matches)} 对")
for m in matches[:3]:
    print(f"  EN[{m['en_idx']}] <-> ZH[{m['zh_idx']}] (score: {similarity(m['en'], m['zh']):.2f})")

# 保存
with open("tmp/matches.json", "w", encoding="utf-8") as f:
    json.dump(matches, f, ensure_ascii=False, indent=2)
