#!/usr/bin/env python3
"""生成 email_body.html"""
import json

# 读取对齐结果
with open("align_result.json", "r", encoding="utf-8") as f:
    align = json.load(f)

# 读取 LLM 结果
with open("llm_result.json", "r", encoding="utf-8") as f:
    result = json.load(f)

title_cn = result.get("title_cn", "优先级")
title_en = "Fixing up priorities"
date_str = "1981-07-05"
sahaja_link = "https://www.sahaja.live/1981-0705-detachment-and-sharing-puja-in-cambridge/"
pairs = align["pairs"]

html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>{title_en}</title>
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
<h1>{title_en}</h1>
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

print(f"✅ email_body.html 已生成")
print(f"标题: {title_cn}")
print(f"日期: {date_str}")
print(f"句子对数: {sum(len(p['sentences']) for p in pairs)}")
