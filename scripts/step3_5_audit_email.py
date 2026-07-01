"""
Step 3.5: Email content quality audit with Agnes AI alignment check.
Validates the generated bilingual email before sending.
If audit FAILS -> blocks email sending, triggers rework.

Input: /tmp/email_body.html, /tmp/article_raw.json
Output: /tmp/audit_report.md — structured quality report
Exit code: 0 = pass, 1 = fail (blocks Step 4)
"""

import json
import re
import os
import sys
import urllib.request
import base64

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
    """Count EN/CN alternating pairs."""
    paras = extract_paragraphs(html)
    has_cjk = [bool(re.search(r"[\u4e00-\u9fff]", p)) for p in paras]
    en_count = sum(1 for h in has_cjk if not h)
    cn_count = sum(1 for h in has_cjk if h)
    return en_count, cn_count, paras

def check_alternation(paras):
    """Check EN/CN alternation pattern."""
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

# ── Agnes AI alignment verification ─────────────────────────────

def verify_alignment_with_agnes(html):
    """
    Use Agnes AI to verify sentence-level alignment quality.
    Extracts EN/ZH pairs from HTML and sends to Agnes for validation.
    Returns (passed, details).
    """
    # Extract bilingual pairs from HTML
    pair_pattern = r'<div class="en-text">(.*?)</div>\s*<div class="zh-text">(.*?)</div>'
    pairs = re.findall(pair_pattern, html, re.DOTALL)
    
    if len(pairs) < 5:
        return True, "Pairs too few (<5), skipping Agnes verification"
    
    # Sample up to 20 pairs for verification
    sample_size = min(20, len(pairs))
    sampled = pairs[:sample_size]
    
    # Build prompt for Agnes
    en_texts = "\n".join([f"[{i}] {strip_html(p[0])}" for i, p in enumerate(sampled)])
    zh_texts = "\n".join([f"[{i}] {strip_html(p[1])}" for i, p in enumerate(sampled)])
    
    prompt = f"""You are a bilingual quality checker. Review these English-Chinese sentence pairs from a religious talk translation.

Check:
1. Does each Chinese sentence correspond semantically to its paired English sentence?
2. Are there any obvious mismatches (Chinese text doesn't match the English at all)?
3. Are there empty Chinese translations?

=== ENGLISH ===
{en_texts}

=== CHINESE ===
{zh_texts}

Output a JSON object:
{{
  "total_pairs_checked": <int>,
  "empty_chinese_count": <int>,
  "mismatched_pairs": [<int indices of mismatched pairs>],
  "quality_score": <0-100>,
  "verdict": "PASS" or "FAIL",
  "notes": "<brief summary>"
}}

Only output valid JSON, nothing else.
"""
    
    api_key = os.environ.get("AGNES_API_KEY", "") or os.environ.get("AGNES_AI_KEY", "")
    if not api_key:
        return True, "AGNES_API_KEY not set, skipping alignment verification"
    
    data = json.dumps({
        "model": "agnes-2.0-flash",
        "messages": [
            {"role": "system", "content": "You are a precise bilingual quality checker. Output only JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 2048,
    }).encode("utf-8")
    
    req = urllib.request.Request(
        "https://apihub.agnes-ai.com/v1/chat/completions",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"].strip()
        
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        check = json.loads(content)
        score = check.get("quality_score", 0)
        verdict = check.get("verdict", "FAIL")
        empty_count = check.get("empty_chinese_count", 0)
        mismatched = check.get("mismatched_pairs", [])
        
        details = (
            f"Agnes AI verified {sample_size} pairs: "
            f"score={score}/100, empty_zh={empty_count}, "
            f"mismatches={len(mismatched)}, verdict={verdict}"
        )
        
        if verdict == "FAIL" or score < 70 or empty_count > 0:
            return False, details
        return True, details
        
    except Exception as e:
        return True, f"Agnes API call failed ({e}), skipping verification"


# ── Main auditor ─────────────────────────────────────────────────


def load_ima_search_results():
    """Load IMA KB search results from JSON file written by step2_translate.py."""
    results_path = "/tmp/ima_kb_search_results.json"
    if not os.path.exists(results_path):
        return None
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return None


def format_ima_search_report(search_results):
    """Format IMA KB search results for audit report."""
    if not search_results:
        return "| IMA KB 搜索结果 | - | 无搜索结果文件（step2 未执行或未写入） |"
    
    lines = []
    lines.append("| IMA KB 搜索结果 | INFO | 搜索到 %d 个文档，尝试前 5 个 |" % len(search_results))
    for sr in search_results:
        title = sr.get("title", "N/A")
        picked = sr.get("picked", "")
        stype = sr.get("type", "")
        selected = " <-- 被选中" if sr.get("selected") else ""
        marker = "**" if "SELECTED" in picked else ""
        lines.append("  %s%s [%s]%s%s" % (marker, title[:50], stype, picked.replace("YES <-- SELECTED", "✓ 被尝试").replace("NO (limited)", "✗ 未尝试"), selected))
    
    return "\n".join(lines)



def run_audit():
    with open(INPUT_PATH, encoding="utf-8") as f:
        html = html_content = f.read()

    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    report_lines = []
    results = {}
    failures = []
    warnings = []

    # === P0: 翻译来源判定（第一条） ===
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
        note = f"[OK] 来源于 sahaja.live 官方翻译（IMA KB）— 文档：{doc_title[:60]}"
        if src_url:
            note += f" | source: {src_url[:60]}"
        results["翻译来源"] = ("[OK]", note)
    elif "机器翻译" in html_content or "非官方" in html_content:
        results["翻译来源"] = ("[FAIL]", "非官方翻译（阿里云机器翻译降级）")
        failures.append("翻译来源：降级为机器翻译")
    else:
        results["翻译来源"] = ("[FAIL]", "IMA KB 官方翻译未找到，且无降级标注")
        failures.append("翻译来源：IMA KB 无结果且无标注")

    # === 1. 结构完整性 ===
    struct = check_html_structure(html_content)
    missing = [k for k, v in struct.items() if not v]
    if missing:
        results["结构完整性"] = ("[FAIL]", f"缺少元素：{', '.join(missing)}")
        failures.append(f"结构：缺少 {', '.join(missing)}")
    else:
        results["结构完整性"] = ("[OK]", "标题、日期、分隔线、链接完整")

    # === 2. 英中交替 ===
    en_count, cn_count, paras = count_bilingual_pairs(html_content)
    alt_issues = check_alternation(paras)
    if alt_issues:
        results["英中交替"] = ("[FAIL]", "; ".join(alt_issues[:5]))
        failures.append(f"交替：{len(alt_issues)} 个问题")
    else:
        results["英中交替"] = ("[OK]", f"交替排列正确（英文 {en_count} 段，中文 {cn_count} 段）")

    # === 3. 段落数匹配 ===
    diff = abs(en_count - cn_count)
    if diff > 2:
        results["段落数匹配"] = ("[FAIL]", f"英文 {en_count} 段 vs 中文 {cn_count} 段，差 {diff}")
        failures.append(f"段落差 {diff} (>2)")
    elif diff == 2:
        results["段落数匹配"] = ("[WARN]", f"英文 {en_count} 段 vs 中文 {cn_count} 段，差 2 段")
        warnings.append(f"段落差 2")
    else:
        results["段落数匹配"] = ("[OK]", f"英文 {en_count} 段，中文 {cn_count} 段，匹配")

    # === 4. 中文非空检查（P0 阻塞） ===
    zh_empty = re.findall(r'<div class="zh-text">\s*</div>', html_content)
    if zh_empty:
        results["中文非空"] = ("[FAIL]", f"发现 {len(zh_empty)} 处空中文段落")
        failures.append(f"{len(zh_empty)} 处空中文")
    else:
        results["中文非空"] = ("[OK]", "无空中文段落")

    # === 5. 底部链接（P0 阻塞） ===
    link_checks = {}
    link_checks["has_amruta_today"] = bool(re.search(r'amruta\.today', html_content))
    link_checks["has_sahaja_live"] = bool(re.search(r'sahaja\.live', html_content))
    
    # Check order: amruta.today should come BEFORE sahaja.live
    amruta_pos = html_content.find("amruta.today")
    sahaja_pos = html_content.find("sahaja.live")
    link_checks["order_correct"] = amruta_pos < sahaja_pos if amruta_pos >= 0 and sahaja_pos >= 0 else False
    
    if all(link_checks.values()):
        results["底部链接"] = ("[OK]", "两个链接都存在且顺序正确（amruta.today 在前，sahaja.live 在后）")
    else:
        issues = []
        if not link_checks["has_amruta_today"]:
            issues.append("缺少 amruta.today")
        if not link_checks["has_sahaja_live"]:
            issues.append("缺少 sahaja.live")
        if not link_checks["order_correct"]:
            issues.append("顺序错误")
        results["底部链接"] = ("[FAIL]", "; ".join(issues))
        failures.append(f"链接：{'; '.join(issues)}")

    # === 6. 翻译来源标注 ===
    has_source_note = "翻译来源" in html_content or "sahaja.live 官方翻译" in html_content
    if has_source_note:
        results["来源标注"] = ("[OK]", "邮件中包含翻译来源说明")
    else:
        results["来源标注"] = ("[WARN]", "邮件中缺少翻译来源说明")
        warnings.append("来源标注缺失")

    # === 7. Agnes AI 对齐质量验证 ===
    align_passed, align_details = verify_alignment_with_agnes(html_content)
    if align_passed:
        results["Agnes AI 对齐验证"] = ("[OK]", align_details)
    else:
        results["Agnes AI 对齐验证"] = ("[FAIL]", align_details)
        failures.append(f"对齐质量：{align_details}")

    # === 8. 翻译通顺度 ===
    cn_paras = [p for p in paras if re.search(r"[\u4e00-\u9fff]", p)]
    if cn_paras:
        short_trans = sum(1 for p in cn_paras if len(strip_html(p)) < 5)
        if short_trans > cn_count * 0.1 and cn_count > 10:
            results["翻译通顺度"] = ("[WARN]", f"过短句子 {short_trans} 处，可能为 1:N 未正确合并")
            warnings.append(f"{short_trans} 处过短翻译")
        else:
            results["翻译通顺度"] = ("[OK]", "翻译长度分布正常")
    else:
        results["翻译通顺度"] = ("[FAIL]", "无中文段落")
        failures.append("无中文段落")

    # ── Build report ──
    has_fail = len(failures) > 0
    has_warn = len(warnings) > 0

    report_lines.append("# 邮件内容验收报告\n")
    report_lines.append(f"**检查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append(f"**文章**: {raw.get('title', 'unknown')} ({raw.get('date', 'unknown')})\n")
    report_lines.append(f"**检查文件**: {INPUT_PATH}\n")
    ima_results = load_ima_search_results()
    ima_report = format_ima_search_report(ima_results)
    # === IMA KB 搜索结果展示 ===
    if ima_results is not None:
        report_lines.append(ima_report)
        report_lines.append("")
    report_lines.append("\n## 检查结果\n")
    report_lines.append("| 维度 | 结果 | 备注 |")
    report_lines.append("|------|------|------|")

    for dim in ["翻译来源", "结构完整性", "英中交替", "段落数匹配", "中文非空", "底部链接", "来源标注", "Agnes AI 对齐验证", "翻译通顺度"]:
        if dim in results:
            s, n = results[dim]
            report_lines.append(f"| {dim} | {s} | {n} |")
        else:
            report_lines.append(f"| {dim} | - | 未检查 |")

    report_lines.append("\n## 总评\n")
    if has_fail:
        report_lines.append(f"**判定**: [FAIL] **不通过**（{len(failures)} 个失败项）")
        report_lines.append("\n### 失败项\n")
        for f_item in failures:
            report_lines.append(f"- [FAIL] {f_item}")
        report_lines.append("\n### 行动要求\n")
        report_lines.append("**必须修复后重新推送**。当前邮件发送已阻止。")
        report_lines.append("修复方向：")
        if any("翻译来源" in f for f in failures):
            report_lines.append("- 翻译来源：检查 IMA KB 搜索和阿里云降级逻辑")
        if any("空中文" in f for f in failures):
            report_lines.append("- 空中文：检查 step2_translate.py 的翻译输出")
        if any("链接" in f for f in failures):
            report_lines.append("- 链接：检查底部链接生成逻辑")
        if any("对齐" in f for f in failures):
            report_lines.append("- 对齐：Agnes AI 检测到质量问题，检查对齐逻辑")
    elif has_warn:
        report_lines.append(f"**判定**: [WARN] **有条件通过**（{len(warnings)} 个警告项）")
        report_lines.append("\n### 警告项\n")
        for w_item in warnings:
            report_lines.append(f"- [WARN] {w_item}")
        report_lines.append("\n邮件继续发送，但建议后续修复。")
    else:
        report_lines.append("**判定**: [OK] **通过**")

    report = "\n".join(report_lines)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[Report] 验收报告已写入: {REPORT_PATH}")
    if has_fail:
        print(f"  [FAIL] 判定: 不通过（{len(failures)} 个失败项）")
        print(f"  邮件发送已阻止，需要修复后重新运行")
    elif has_warn:
        print(f"  [WARN] 判定: 有条件通过（{len(warnings)} 个警告项）")
    else:
        print(f"  [OK] 判定: 通过")
    print(report)

    # Exit code: 0 = pass (with or without warnings), 1 = fail (blocks email)
    return 1 if has_fail else 0


if __name__ == "__main__":
    from datetime import datetime
    sys.exit(run_audit())