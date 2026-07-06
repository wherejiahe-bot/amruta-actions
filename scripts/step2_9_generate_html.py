#!/usr/bin/env python3
"""
Step2.9: 生成 HTML
"""
import json
import re

# 读取状态
with open(".step2_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)

en_title = state["en_title"]
title_cn = state["title_cn"]
date_str = state["date_str"]
sahaja_link = state["sahaja_link"]
pairs = state["pairs"]

print(f"=== Step2.9: 生成 HTML ===")
print(f"标题: {en_title}")
print(f"中文标题: {title_cn}")
print(f"日期: {date_str}")

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

for pair in pairs:
    for sent in pair["sentences"]:
        html += f'<p class="en-text">{sent["en"]}</p>\n'
        html += f'<p class="zh-text">{sent["zh"]}</p>\n'

html += f"""<hr>
<p><a href="https://amruta.today/">https://amruta.today/</a></p>
<p><a href="{sahaja_link}">{sahaja_link}</a></p>
</body>
</html>
"""

with open("email_body.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"  ✅ email_body.html 已生成")
print(f"\n✅ Step2.9 完成。请检查 email_body.html 的内容。")
print(f"确认无误后，执行 Step3")
