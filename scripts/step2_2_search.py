#!/usr/bin/env python3
"""
Step2.2: 搜索 F盘文档
用日期搜索 F盘文件夹，找到匹配的中文文档
"""
import json
import os

# 读取 Step2.1 的状态
with open(".step2_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)

date_str = state["date_str"]
print(f"=== Step2.2: 搜索 F盘文档 ===")
print(f"日期: {date_str}")

# 搜索 F盘文档
doc_name = f"{date_str}*.md"
search_cmd = f'find "F:/霎哈嘉瑜伽/sahaja live talks/" -name "{doc_name}"'
result = os.popen(search_cmd).read().strip()

if not result:
    print(f"  ❌ 未找到文档")
    print(f"  请检查日期是否正确")
    exit(1)

found_doc = result.split('\n')[0]
print(f"  ✅ 找到: {os.path.basename(found_doc)}")

# 保存到状态文件
state["found_doc"] = found_doc
with open(".step2_state.json", "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)

print(f"\n✅ Step2.2 完成。")
print(f"确认无误后，执行 Step2.3")
