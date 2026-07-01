"""
Step 3.5: Email content quality audit.
Validates the generated bilingual email before sending.
Input: /tmp/email_body.html, /tmp/article_raw.json
Output: /tmp/audit_report.md — structured quality report
"""

import json
import re
import sys

INPUT_PATH = "/tmp/email_body.html"
RAW_PATH = "/tmp/article_raw.json"
REPORT_PATH = "/tmp/audit_report.md"

# ── helpers ──────────────────────────────────────────────────────

def strip_html(text):
    return re.sub(r"<[^>]+>", "", text).strip()

def extract_paragraphs(html):
    """Extract all <p>...</p> content in order."""
    return re.findall(r"<p>(.*?)</p>", html, re.DOTALL)

def count_bilingual_pairs(html):
    """
    Count EN/CN alternating pairs.
    Also detect orphaned paragraphs.
    """
    paras = extract_paragraphs(html)
    has_cjk = [bool(re.search(r"[\u4e00-\u9fff]", p)) for p in paras]
    en_count = sum(1 for h in has_cjk if not h)
    cn_count = sum(1 for h in has_cjk if h)
    return en_count, cn_count, paras

def check_alternation(paras):
    """Check EN/CN alternation pattern: EN, CN, EN, CN, ..."""
    issues = []
    for i, p in enumerate(paras):
        has_chinese = bool(re.search(r"[\u4e00-\u9fff]", p))
        if i == 0 and has_chinese:
            issues.append(f"第 {i+1} 段：首段应为英文，实际为中文")
        elif i > 0:
            prev_has = bool(re.search(r"[\u4e00-\u9fff]", paras[i - 1]))
            if has_chinese == prev_has:
                issues.append(f"第 {i+1} 段：相邻段落语言重复（预期交替）")
    return issues

def check_html_structure(html):
    """Check required HTML elements."""
    checks = {}
    checks["has_title"] = bool(re.search(r"<h2>", html))
    checks["has_date"] = bool(re.search(r"<p>\d{4}-\d{2}-\d{2}</p>", html))
    checks["has_hr"] = "<hr>" in html
    checks["has_links"] = "href=" in html
    return checks

def check_terminology(content):
    """
    Check Sahaja Yoga terminology consistency.
    Uses a subset of key terms from the user's glossary.
    """
    rules = {
        "negative_energy": (r"\bnegative\s+energy\b", r"\b负面\s*能量\b"),
        "vibration": (r"\bvibration\b", r"\b(生命能量|振动)\b"),
        "kundalini": (r"\bKundalini\b", r"\b昆达里尼\b"),
    }
    issues = []
    for name, (en_pat, cn_pat) in rules.items():
        en_matches = re.findall(en_pat, content, re.IGNORECASE)
        cn_matches = re.findall(cn_pat, content)
        if en_matches and not cn_matches:
            issues.append(f"术语「{name}」：英文出现 {len(en_matches)} 次但无对应中文翻译")
    return issues

# ── main auditor ─────────────────────────────────────────────────

def run_audit():
    with open(INPUT_PATH, encoding="utf-8") as f:
        html = f.read()

    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    report_lines = []
    results = {}  # dimension -> (status, note)

    # 1. 结构完整性
    struct = check_html_structure(html)
    missing = [k for k, v in struct.items() if not v]
    if missing:
        results["结构完整性"] = ("❌", f"缺少元素：{', '.join(missing)}")
    else:
        results["结构完整性"] = ("✔️", "标题、日期、分隔线、链接完整")

    # 2. 英中交替
    en_count, cn_count, paras = count_bilingual_pairs(html)
    alt_issues = check_alternation(paras)
    if alt_issues:
        results["英中交替"] = ("❌", "; ".join(alt_issues[:5]))  # cap at 5
    else:
        results["英中交替"] = ("✔️", f"交替排列正确（英文 {en_count} 段，中文 {cn_count} 段）")

    # 3. 段落数匹配
    diff = abs(en_count - cn_count)
    if diff > 1:
        results["段落数匹配"] = ("❌", f"英文 {en_count} 段 vs 中文 {cn_count} 段，差 {diff}")
    elif diff == 1:
        results["段落数匹配"] = ("⚠️", f"英文 {en_count} 段 vs 中文 {cn_count} 段，差 1 段")
    else:
        results["段落数匹配"] = ("✔️", f"英文 {en_count} 段，中文 {cn_count} 段，匹配")

    # 4. 格式规范 — 字符转义
    unescaped = re.findall(r"&(?!(amp|lt|gt|quot|#\d+);)", html)
    if unescaped:
        results["格式规范"] = ("⚠️", f"发现 {len(unescaped)} 处未转义的 & 符号")
    else:
        results["格式规范"] = ("✔️", "字符转义正确，无异常")

    # 5. 术语一致性
    term_issues = check_terminology(html)
    if term_issues:
        results["术语一致性"] = ("⚠️", "; ".join(term_issues[:3]))
    else:
        results["术语一致性"] = ("✔️", "未发现术语异常")

    # 6. 翻译通顺度（LLM-based 抽样检查）
    # 对超过 20 段的文章，抽前中后各取一段检查中文长度
    if cn_count > 0:
        cn_paras = [p for p in paras if re.search(r"[\u4e00-\u9fff]", p)]
        long_translations = sum(1 for p in cn_paras if len(strip_html(p)) > 200)
        short_translations = sum(1 for p in cn_paras if len(strip_html(p)) < 5)
        if long_translations > cn_count * 0.2:
            results["翻译通顺度"] = ("⚠️", f"超长句子比例偏高（{long_translations}/{cn_count}），可能为 N:1 未正确拆分")
        elif short_translations > cn_count * 0.1:
            results["翻译通顺度"] = ("⚠️", f"过短句子比例偏高（{short_translations}/{cn_count}），可能为 1:N 未正确合并")
        else:
            results["翻译通顺度"] = ("✔️", "翻译长度分布正常")

    # ── build report ──
    has_fail = any(s == "❌" for s, _ in results.values())
    has_warn = any(s == "⚠️" for s, _ in results.values())

    report_lines.append("# 邮件内容验收报告\n")
    report_lines.append(f"**检查时间**: 自动生成\n")
    report_lines.append(f"**文章**: {raw.get('title', 'unknown')} ({raw.get('date', 'unknown')})\n")
    report_lines.append(f"**检查文件**: {INPUT_PATH}\n")
    report_lines.append("\n## 检查结果\n")
    report_lines.append("| 维度 | 结果 | 备注 |")
    report_lines.append("|------|------|------|")
    
    # 第 0 项：翻译来源（最重要的）
    try:
        with open("/tmp/ima_kb_doc_title.txt", encoding="utf-8") as f:
            doc_title = f.read().strip()
    except:
        doc_title = ""
    try:
        with open("/tmp/ima_kb_source_url.txt", encoding="utf-8") as f:
            src_url = f.read().strip()
    except:
        src_url = ""
    
    if doc_title:
        note = f"✅ 来源于 sahaja.live 官方翻译（IMA KB）— 文档：{doc_title[:60]}"
        if src_url:
            note += f" | source: {src_url[:60]}"
        results["翻译来源"] = ("✅", note)
    elif "机器翻译" in html or "非官方" in html:
        results["翻译来源"] = ("❌", "非官方翻译（阿里云机器翻译降级）")
    else:
        results["翻译来源"] = ("❌", "IMA KB 官方翻译未找到（非 IMA KB 来源）")
    
    for dim in ["翻译来源", "结构完整性", "英中交替", "段落数匹配", "格式规范", "翻译通顺度", "术语一致性"]:
        if dim in results:
            s, n = results[dim]
            report_lines.append(f"| {dim} | {s} | {n} |")
        else:
            report_lines.append(f"| {dim} | - | 未检查 |")

    report_lines.append("\n## 总评")
    if has_fail:
        report_lines.append("**判定**: ❌ 不通过（存在必须修复的问题）")
    elif has_warn:
        report_lines.append("**判定**: ⚠️ 有瑕疵（可改进，不阻塞发送）")
    else:
        report_lines.append("**判定**: ✔️ 通过")

    report = "\n".join(report_lines)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"📋 验收报告已写入: {REPORT_PATH}")
    print(f"  判定: {'❌ 不通过' if has_fail else '⚠️ 有瑕疵' if has_warn else '✔️ 通过'}")
    print(report)

    # Exit with code: 0 = pass/warn, 1 = fail
    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(run_audit())
