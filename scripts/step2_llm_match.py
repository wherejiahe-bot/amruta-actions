"""
step2_llm_match.py — LLM-A: 段落匹配（Paragraph Matching）

输入: english_paragraphs (list[str]), chinese_document (str)
输出: list[dict] [{"en_idx": int, "zh_idx": int|None}, ...]

职责:
  给定 N 个英文段落和一篇完整的中文文档（包含交替的 EN/ZH 段落），
  输出哪些英文段落对应哪些中文段落。

失败回退: 位置对齐（按序号一一配对）
"""

import json
import re

from step2_llm_utils import call_llm_with_retry, call_llm_batch

SYSTEM_PROMPT = (
    "You are a precise bilingual document alignment specialist. Your task is to match "
    "English paragraphs with their corresponding Chinese paragraphs in a bilingual talk "
    "by Shri Mataji (Sahaja Yoga).\n"
    "\n"
    "RULES:\n"
    "1. You will receive a list of English paragraphs (from amruta.today) and a complete "
    "Chinese document (from official Sahaja.live translations).\n"
    "2. Match each English paragraph to exactly ONE Chinese paragraph by semantic similarity.\n"
    "3. The Chinese document contains alternating English and Chinese paragraphs. You must "
    "identify only the Chinese paragraphs.\n"
    "4. Some English paragraphs may not have a matching Chinese paragraph (return null for zh_idx).\n"
    "5. Do NOT reorder paragraphs. Preserve the original order.\n"
    "6. Output ONLY valid JSON. No explanations, no markdown fences.\n"
    "7. Be conservative: if you cannot confidently match a paragraph, return null."
)


def extract_chinese_paragraphs(doc: str) -> list[str]:
    """
    从完整文档中提取纯中文段落。

    判断标准：
    - 中文字符数 > 英文字母数 且 中文字符数 >= 3
    - 跳过元信息行（日期、Talk Language、译注等）
    """
    blocks = [b.strip() for b in re.split(r'\n{2,}', doc) if b.strip()]
    chinese_blocks = []

    for block in blocks:
        cn_count = sum(1 for c in block if '\u4e00' <= c <= '\u9fff')
        en_count = sum(1 for c in block if c.isalpha() and ord(c) < 128)

        # 跳过元信息
        if re.match(r'^\d{1,2}\s+\w+\s+\d{4}', block):
            continue
        if re.search(r'\d{4}年', block):
            continue
        if any(kw in block for kw in ['Talk Language', 'Transcript', 'VERIFIED', 'NEEDED',
                                       '以下翻译', '供大家参考', 'subtitles', 'Subtitles']):
            continue

        if cn_count > en_count and cn_count >= 3:
            chinese_blocks.append(block)

    return chinese_blocks


def build_match_prompt(english_paragraphs: list[str], chinese_paragraphs: list[str],
                       batch_offset: int = 0) -> str:
    """构建 LLM-A 的用户 prompt。"""
    en_list = "\n".join(
        f"[{i + batch_offset}] {p}" for i, p in enumerate(english_paragraphs)
    )
    zh_list = "\n".join(
        f"[{i}] {p}" for i, p in enumerate(chinese_paragraphs)
    )

    return (
        f"## ENGLISH PARAGRAPHS (from amruta.today)\n\n"
        f"{en_list}\n\n"
        f"## CHINESE DOCUMENT (complete, from Sahaja.live)\n\n"
        f"{zh_list}\n\n"
        f"## INSTRUCTIONS\n\n"
        f"Match each English paragraph to the most semantically similar Chinese paragraph.\n"
        f"Return a JSON array where each element is:\n"
        f"{{\"en_idx\": <0-based index>, \"zh_idx\": <0-based index of Chinese paragraph, or null>}}\n"
        f"Sort by en_idx ascending."
    )


def parse_match_result(raw_result, batch_offset: int = 0) -> list[dict]:
    """
    解析 LLM 返回的 JSON 匹配结果。

    输入可能是：
    - list of [en_idx, zh_idx] (旧格式)
    - list of {"en_idx": ..., "zh_idx": ...} (新格式)
    """
    if not isinstance(raw_result, list):
        return []

    matches = []
    for item in raw_result:
        if isinstance(item, dict):
            en_idx = item.get("en_idx")
            zh_idx = item.get("zh_idx")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            en_idx = item[0]
            zh_idx = item[1]
        else:
            continue

        if en_idx is not None:
            en_idx = int(en_idx) + batch_offset
            if zh_idx is not None:
                zh_idx = int(zh_idx)
            matches.append({"en_idx": en_idx, "zh_idx": zh_idx})

    return matches


def fallback_positional_match(en_count: int, zh_count: int) -> list[dict]:
    """位置对齐回退：按序号一一配对。"""
    matches = []
    for i in range(en_count):
        zh_idx = i if i < zh_count else None
        matches.append({"en_idx": i, "zh_idx": zh_idx})
    return matches


def match_paragraphs(english_paragraphs: list[str], chinese_document: str) -> list[dict]:
    """
    主入口：LLM-A 段落匹配。

    Args:
        english_paragraphs: 来自 amruta.today 的英文段落列表
        chinese_document: 来自 F盘/IMA/阿里云的完整中文文档

    Returns:
        [{"en_idx": int, "zh_idx": int|None}, ...]
    """
    if not english_paragraphs or not chinese_document:
        print("[llm_match] Empty input, returning empty matches")
        return []

    # 1. 提取中文段落
    zh_paragraphs = extract_chinese_paragraphs(chinese_document)
    print(f"[llm_match] Extracted {len(zh_paragraphs)} Chinese paragraphs from document")

    if not zh_paragraphs:
        print("[llm_match] No Chinese paragraphs found, using positional fallback")
        return fallback_positional_match(len(english_paragraphs), 0)

    # 2. 按 20 段一组分批
    batch_size = 20
    batches = [
        english_paragraphs[i:i + batch_size]
        for i in range(0, len(english_paragraphs), batch_size)
    ]

    all_matches = []
    for batch_idx, batch in enumerate(batches):
        offset = batch_idx * batch_size

        def prompt_builder(_batch=batch, _offset=offset):
            user_prompt = build_match_prompt(_batch, zh_paragraphs, _offset)
            return {
                "model": "agnes-2.0-flash",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 4096,
            }

        print(f"[llm_match] Batch {batch_idx + 1}/{len(batches)}: "
              f"matching {len(batch)} English paragraphs "
              f"(offset={offset}, {len(zh_paragraphs)} Chinese paragraphs)")

        result = call_llm_with_retry(
            prompt_builder,
            max_tokens=4096,
            timeout=60,
        )

        if result:
            parsed = parse_match_result(result, offset)
            all_matches.extend(parsed)
            print(f"[llm_match]   Got {len(parsed)} matches")
        else:
            print(f"[llm_match]   LLM call failed, using positional fallback for this batch")
            for i in range(len(batch)):
                en_global_idx = offset + i
                zh_idx = en_global_idx if en_global_idx < len(zh_paragraphs) else None
                all_matches.append({"en_idx": en_global_idx, "zh_idx": zh_idx})

    # 3. 按 en_idx 排序
    all_matches.sort(key=lambda m: m["en_idx"])

    print(f"[llm_match] Total matches: {len(all_matches)} "
          f"({sum(1 for m in all_matches if m['zh_idx'] is not None)} matched, "
          f"{sum(1 for m in all_matches if m['zh_idx'] is None)} unmatched)")

    return all_matches
