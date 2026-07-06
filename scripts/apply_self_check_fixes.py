#!/usr/bin/env python3
"""应用 LLM 自检修正结果"""
import json
import sys

# 读取修正结果
with open("self_check_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

# 读取原始 pairs
with open("pairs.json", "r", encoding="utf-8") as f:
    pairs = json.load(f)

# 构建索引映射
idx_map = {}
for i, item in enumerate(pairs):
    for j, s in enumerate(item.get("sentences", [])):
        idx_map[len(idx_map)] = (i, j)

# 应用修正
fix_count = 0
for result in results:
    idx = result.get("idx")
    if idx in idx_map and result.get("status") == "fix":
        pair_idx, sent_idx = idx_map[idx]
        pairs[pair_idx]["sentences"][sent_idx]["zh"] = result.get("corrected_zh", "")
        pairs[pair_idx]["sentences"][sent_idx]["en"] = result.get("corrected_en", "")
        fix_count += 1
        print(f"修正 Pair {idx}: {result.get('reason', '')[:80]}")

# 保存修正后的 pairs
with open("pairs.json", "w", encoding="utf-8") as f:
    json.dump(pairs, f, ensure_ascii=False, indent=2)

print(f"\n已应用 {fix_count} 个修正")
