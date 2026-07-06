#!/usr/bin/env python3
"""解析 F盘文档，提取中英交替段落"""
import re

doc_path = r"F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md"
with open(doc_path, "r", encoding="utf-8") as f:
    content = f.read()

# 去掉 frontmatter
content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

# 按两个换行分割（段落）
blocks = [b.strip() for b in content.split('\n\n') if b.strip()]

# 交替段落：奇数英文，偶数中文
en_paras = []
zh_paras = []

for i, b in enumerate(blocks):
    cn_count = sum(1 for c in b if '\u4e00' <= c <= '\u9fff')
    en_count = sum(1 for c in b if c.isalpha() and ord(c) < 128)
    
    if cn_count > en_count:
        zh_paras.append(b)
    elif en_count > cn_count:
        en_paras.append(b)

print(f"英文段落数: {len(en_paras)}")
print(f"中文段落数: {len(zh_paras)}")

# 保存
import json
result = {
    "en_paras": en_paras,
    "zh_paras": zh_paras,
    "count_en": len(en_paras),
    "count_zh": len(zh_paras)
}

with open("tmp/official_paras.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("✅ 官方段落已保存到 tmp/official_paras.json")
