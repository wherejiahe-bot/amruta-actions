#!/usr/bin/env python3
"""
Step1: 从 amruta.today 抓取指定日期的文章
只抓取 amruta.today 当天显示的内容，不多不少
用法: python step1_fetch.py <日期>
例: python step1_fetch.py 1981-07-05
"""
import json
import subprocess
import sys
import re

print(f"=== Step1: 从 amruta.today 抓取文章 ===")

if len(sys.argv) < 2:
    print(f"  用法: python step1_fetch.py <日期>")
    print(f"  例: python step1_fetch.py 1981-07-05")
    sys.exit(1)

date_str = sys.argv[1]
print(f"日期: {date_str}")

# 第一步：搜索文章
cmd = f'curl -s "https://amruta.today/wp-json/wp/v2/daily-talks?per_page=100"'
result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

if result.returncode != 0:
    print(f"  ❌ curl 失败: {result.stderr}")
    sys.exit(1)

try:
    articles = json.loads(result.stdout)
except json.JSONDecodeError:
    print(f"  ❌ 响应不是有效的 JSON")
    sys.exit(1)

# 找到匹配日期的文章
article = None
for a in articles:
    if a.get("date", "").startswith(date_str):
        article = a
        break

if not article:
    print(f"  ❌ amruta.today 上没有 {date_str} 的文章")
    sys.exit(1)

# 通过 ID 获取完整内容
article_id = article["id"]
cmd2 = f'curl -s "https://amruta.today/wp-json/wp/v2/daily-talks/{article_id}"'
result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
article = json.loads(result2.stdout)

title = article.get("title", {}).get("rendered", "")
content_html = article.get("content", {}).get("rendered", "")
link = article.get("link", "")
external_link = article.get("acf", {}).get("external_link", "")

# 提取纯文本内容
clean_content = re.sub(r'<[^>]+>', '', content_html).strip()

print(f"  ✅ 抓取成功!")
print(f"  标题: {title}")
print(f"  内容长度: {len(clean_content)} 字符")
print(f"  链接: {link}")

# 保存
output = {
    "date": date_str,
    "title": title,
    "content": clean_content,
    "link": link,
    "source": external_link or link
}

with open("article_raw.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"  ✅ 已保存到 article_raw.json")
