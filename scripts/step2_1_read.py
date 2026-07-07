#!/usr/bin/env python3
"""
Step2.1: 读取文章
从 article_raw.json 读取英文标题、英文内容、日期
"""
import json
import os

# 读取文章
with open("article_raw.json", "r", encoding="utf-8") as f:
    article = json.load(f)

en_title = article["title"]
en_content = article["content"]
date_str = article["date"].split()[0]

print(f"=== Step2.1: 读取文章 ===")
print(f"日期: {date_str}")
print(f"英文标题: {en_title}")
print(f"英文内容长度: {len(en_content)} 字符")

# 保存到状态文件供后续步骤使用
state = {
    "en_title": en_title,
    "en_content": en_content,
    "date_str": date_str
}

with open(".step2_state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f"\n✅ Step2.1 完成。请检查上面的输出是否正确。")
print(f"确认无误后，执行 Step2.2")
