#!/usr/bin/env python3
"""用 amruta.today 英文内容匹配 F盘官方中文"""
import json
import re

# 读取 amruta.today 英文
with open("article_raw.json", "r", encoding="utf-8") as f:
    article = json.load(f)[0]

en_content = article["content"]
en_text = en_content.replace("<p>", " ").replace("</p>", " ")

# 读取 F盘文档
doc_path = r"F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md"
with open(doc_path, "r", encoding="utf-8") as f:
    doc = f.read()

# 去掉 frontmatter
doc = re.sub(r'^---\n.*?\n---\n', '', doc, flags=re.DOTALL)

# 按段落分割
blocks = [b.strip() for b in doc.split('\n\n') if b.strip()]

# 提取中英段落
en_paras = []
zh_paras = []

for b in blocks:
    cn = sum(1 for c in b if '\u4e00' <= c <= '\u9fff')
    en = sum(1 for c in b if c.isalpha() and ord(c) < 128)
    if cn > en:
        zh_paras.append(b)
    elif en > cn:
        en_paras.append(b)

print(f"F盘: 英文 {len(en_paras)} 段, 中文 {len(zh_paras)} 段")

# 用 amruta.today 英文匹配 F盘英文段落
# 取 amruta.today 英文前 100 字作为搜索词
search_text = en_text[:100]

# 找到匹配的 F盘英文段落索引
matched_en_idx = -1
max_sim = 0

for i, ep in enumerate(en_paras):
    sim = len(set(ep[:100].split()) & set(search_text.split()))
    if sim > max_sim:
        max_sim = sim
        matched_en_idx = i

print(f"匹配的 F盘英文段落索引: {matched_en_idx}")

# 如果找到匹配，取对应的中文段落
if matched_en_idx >= 0 and matched_en_idx < len(zh_paras):
    # F盘是交替的，英文索引 i 对应中文索引 i 或 i+1
    zh_idx = matched_en_idx
    if zh_idx >= len(zh_paras):
        zh_idx = len(zh_paras) - 1
    
    matched_zh = zh_paras[zh_idx]
    print(f"匹配的 F盘中文段落: {matched_zh[:100]}...")
    
    # 提取更多中文段落（后续段落）
    final_zh_paras = [matched_zh]
    for j in range(zh_idx + 1, min(zh_idx + 5, len(zh_paras))):
        final_zh_paras.append(zh_paras[j])
    
    print(f"提取 {len(final_zh_paras)} 段官方中文")
    
    # 保存
    with open("tmp/official_zh.json", "w", encoding="utf-8") as f:
        json.dump(final_zh_paras, f, ensure_ascii=False, indent=2)
else:
    print("未找到匹配段落")
    # 降级：取前几段
    with open("tmp/official_zh.json", "w", encoding="utf-8") as f:
        json.dump(zh_paras[:5], f, ensure_ascii=False, indent=2)
