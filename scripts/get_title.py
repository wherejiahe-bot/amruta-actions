#!/usr/bin/env python3
"""获取中文标题"""
import re

doc_path = r"F:\霎哈嘉瑜伽\sahaja live talks\1981-07-05 导师普祭.md"
with open(doc_path, "r", encoding="utf-8") as f:
    doc = f.read()

en_title = "Fixing up priorities"

# 提取关键词
keywords = re.findall(r'\b(\w+)\b', en_title.lower())
print(f"英文标题关键词: {keywords}")

# 在文档中搜索每个关键词
for kw in keywords:
    idx = doc.find(kw)
    if idx >= 0:
        print(f"找到关键词 '{kw}':")
        print(doc[max(0,idx-30):idx+30])
    else:
        print(f"未找到关键词 '{kw}'")

# 搜索中文对应词
for term in ["优先级", "优先", "重要"]:
    idx = doc.find(term)
    if idx >= 0:
        print(f"\n找到中文 '{term}':")
        print(doc[max(0,idx-30):idx+30])
