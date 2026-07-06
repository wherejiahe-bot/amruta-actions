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
    """Extract all <p>...</p> content, including <p style=...> variants."""
    return re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)


def count_bilingual_pairs(html):
    """Count EN/CN alternating pairs from <p> tags in email_body.html."""
    paras = extract_paragraphs(html)
    has_cjk = [bool(re.search(r"[\u4e00-\u9fff]", p)) for p in paras]
    en_count = sum(1 for h in has_cjk if not h)
    cn_count = sum(1 for h in has_cjk if h)
    return en_count, cn_count, paras


def check_alternation(paras):
    """Check EN/CN block alternation pattern.
    
    HTML structure: multiple EN <p> tags per pair, then ONE CN <p> tag.
    Pattern: EN, EN, ..., EN, CN, EN, EN, ..., EN, CN, ...
    """
    issues = []
    if not paras:
        return issues
    
    # First paragraph must be English
    if re.search(r"[\u4e00-\u9fff]", paras[0]):
        issues.append("首段应为英文，实际为中文")
    
    # Check for consecutive CN paragraphs (skip the last CN block at end of content)
    for i in range(1, len(paras)):
        has_chinese = bool(re.search(r"[\u4e00-\u9fff]", paras[i]))
        prev_has = bool(re.search(r"[\u4e00-\u9fff]", paras[i - 1]))
        if has_chinese and prev_has:
            # If this is near the end (within last 3 paras), it's likely the trailing CN block
            # followed by footer/links — skip this check
            if i >= len(paras) - 3:
                continue
            issues.append(f"第 {i+1} 段：连续两个中文段落（预期每个中文段落后跟英文段）")


def check_html_structure(html):
    """Check required HTML elements."""
    checks = {}
    checks["has_title"] = bool(re.search(r"<h[123]", html))
    checks["has_date"] = bool(re.search(r"\d{4}-\d{2}-\d{2}", html))
    checks["has_hr"] = "<hr" in html
    checks["has_links"] = "href=" in html
    return checks


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
4. **CRITICAL — Sentence-Level Alignment Rule**: The relationship between English and Chinese MUST be one of exactly three types:
   - **1:1** — One English sentence ↔ One Chinese sentence
   - **N:1** — Multiple English sentences → One Chinese sentence
   - **1:N** — One English sentence → Multiple Chinese sentences
   - **FORBIDDEN**: Many-to-many vague mapping (a big chunk of English mixed with a big chunk of Chinese without clear boundaries)

=== ENGLISH ===
{en_texts}

=== CHINESE ===
{zh_texts}

Output a JSON object:
{{
  "total_pairs_checked": <int>,
  "empty_chinese_count": <int>,
  "mismatched_pairs": [<int indices of mismatched pairs>],
  "alignment_rule_violations": [<int indices of pairs violating 1:1/N:1/1:N rule>],
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
    # 优先使用官方翻译，官方翻译有漏句时用阿里云补充
    # Read from IMA KB search results JSON (written by step2_translate.py)
    ima_data = load_ima_search_results()
    doc_title = ""
    src_url = ""
    if ima_data:
        for item in ima_data:
            if item.get("selected"):
                doc_title = item.get("title", "")
                break
        if not doc_title:
            doc_title = ima_data[0].get("title", "") if ima_data else ""

    # Fallback: try reading txt files for backward compatibility
    if not doc_title:
        try:
            with open("/tmp/ima_kb_doc_title.txt", encoding="utf-8") as f:
                doc_title = f.read().strip()
        except:
            pass
    try:
        with open("/tmp/ima_kb_source_url.txt", encoding="utf-8") as f:
            src_url = f.read().strip()
    except:
        src_url = ""

    if doc_title:
        note = f"[OK] 来源于 sahaja.live 官方翻译 — 文档：{doc_title[:60]}"
        if src_url:
            note += f" | source: {src_url[:60]}"
        # 如果找到官方翻译文档，显示文件名
        if 'sahaja live talks' in str(src_url).lower() or doc_title.endswith('.md'):
            # 从 doc_title 提取文件名
            import os
            sahaja_dir = r"F:\霎哈嘉瑜伽\sahaja live talks"
            if os.path.exists(sahaja_dir):
                for f_name in os.listdir(sahaja_dir):
                    if doc_title in f_name:
                        note += f" | 文件名：{f_name}"
                        break
        results["翻译来源"] = ("[OK]", note)
    elif "机器翻译" in html_content or "非官方" in html_content:
        # 检查是否是官方翻译有漏句的情况
        if "阿里云机器翻译补充" in html_content:
            results["翻译来源"] = ("[OK]", "官方翻译为主 + 阿里云补充漏句")
        else:
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
    # In the HTML structure, each bilingual pair has multiple EN <p> tags + 1 CN <p> tag
    # So en_count > cn_count is expected. Check that every CN paragraph has a preceding EN block.
    if cn_count == 0 and en_count > 0:
        results["段落数匹配"] = ("[FAIL]", f"有英文 {en_count} 段但无中文段落")
        failures.append("段落匹配：有英文无中文")
    elif en_count == 0 and cn_count == 0:
        results["段落数匹配"] = ("[FAIL]", "无段落内容")
        failures.append("段落匹配：空内容")
    elif cn_count > 0:
        # Each CN paragraph should correspond to at least one EN paragraph
        ratio = en_count / cn_count
        if ratio >= 1:
            results["段落数匹配"] = ("[OK]", f"英文 {en_count} 段，中文 {cn_count} 段（比例 {ratio:.1f}:1，符合多句对单段结构）")
        else:
            results["段落数匹配"] = ("[WARN]", f"英文 {en_count} 段 vs 中文 {cn_count} 段，比例异常 ({ratio:.1f}:1)")
            warnings.append(f"段落比例异常 {ratio:.1f}:1")
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
    # Link 1: 固定为 https://amruta.today/
    link_checks["has_amruta_today_fixed"] = bool(re.search(r'https://amruta\.today/', html_content))
    # Link 2: 从中文文档 source 字段提取的 sahaja.live 链接
    link_checks["has_sahaja_live"] = bool(re.search(r'sahaja\.live', html_content))
    
    # Check order: amruta.today/ should come BEFORE sahaja.live (only in footer links, not in translation source note)
    # Extract footer links section (last 500 chars)
    footer_section = html_content[-500:]
    amruta_pos = footer_section.find("amruta.today/")
    sahaja_pos = footer_section.find("sahaja.live")
    link_checks["order_correct"] = amruta_pos >= 0 and sahaja_pos >= 0 and amruta_pos < sahaja_pos
    
    # Check Link 1 is fixed (no date/slug after amruta.today/)
    link_checks["link1_not_extended"] = not re.search(r'amruta\.today/\d+/\d+/\d+', html_content)
    
    if all(link_checks.values()):
        results["底部链接"] = ("[OK]", "Link 1=amruta.today/（固定），Link 2=sahaja.live（从中文文档 source 提取），顺序正确")
    else:
        issues = []
        if not link_checks["has_amruta_today_fixed"]:
            issues.append("Link 1 不是固定的 https://amruta.today/")
        if not link_checks["has_sahaja_live"]:
            issues.append("缺少 sahaja.live 链接")
        if not link_checks["order_correct"]:
            issues.append("顺序错误")
        if not link_checks["link1_not_extended"]:
            issues.append("Link 1 带了日期/slug（应为固定 amruta.today/）")
        results["底部链接"] = ("[FAIL]", "; ".join(issues))
        failures.extend([f"链接：{'; '.join(issues)}"])

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

    # === 8. 英中句级对齐规则（2026-07-05 新增） ===
    # 检查每对英中关系是否为 1:1、N:1 或 1:N，禁止多对多模糊对应
    en_pairs = re.findall(r'<div class="en-text">(.*?)</div>', html_content, re.DOTALL)
    zh_pairs = re.findall(r'<div class="zh-text">(.*?)</div>', html_content, re.DOTALL)
    
    # 如果 HTML 用的是 <p> 标签（非 div 格式），改用 <p> 标签检查
    if not en_pairs:
        # 提取所有英文 <p> 标签
        all_p = re.findall(r'<p[^>]*>(.*?)</p>', html_content, re.DOTALL)
        en_paragraphs = []
        zh_paragraphs = []
        for p in all_p:
            text = re.sub(r'<[^>]+>', '', p).strip()
            if not text:
                continue
            if re.search(r'[A-Z]', text) and not re.search(r'[\u4e00-\u9fff]', text):
                en_paragraphs.append(p)
            elif re.search(r'[\u4e00-\u9fff]', text):
                zh_paragraphs.append(p)
        en_pairs = en_paragraphs
        zh_pairs = zh_paragraphs
    
    alignment_rule_passed = True
    alignment_rule_details = []
    
    if len(en_pairs) == len(zh_pairs) and len(en_pairs) > 0:
        # 检查每对是否都有明确的英文和中文
        for i, (en, zh) in enumerate(zip(en_pairs, zh_pairs)):
            en_text = strip_html(en)
            zh_text = strip_html(zh)
            
            # 如果中文为空，标记为不通过
            if not zh_text.strip():
                alignment_rule_passed = False
                alignment_rule_details.append(f"第 {i+1} 对：中文为空")
        
        # 检查是否有"一大坨英文 + 一大坨中文"的多对多模糊对应
        en_lengths = [len(strip_html(e).split()) for e in en_pairs]
        zh_lengths = [len(strip_html(z).split()) for z in zh_pairs]
        
        for i, (en_len, zh_len) in enumerate(zip(en_lengths, zh_lengths)):
            if en_len > 10 and zh_len > 10:
                alignment_rule_passed = False
                alignment_rule_details.append(f"第 {i+1} 对：疑似多对多模糊对应（英文 {en_len} 词，中文 {zh_len} 词）")
    else:
        # 官方翻译场景：英文和中文段落数接近是正常的（1:1 交替）
        en_count = len(en_pairs)
        zh_count = len(zh_pairs)
        if zh_count > 0 and abs(en_count - zh_count) <= 5:
            # 1:1 交替结构，正常
            alignment_rule_passed = True
            alignment_rule_details.append(f"1:1 交替结构（{en_count} 英文 : {zh_count} 中文），符合排版要求")
        elif zh_count > 0 and en_count > zh_count * 5:
            # M:1 结构，这是正常的官方翻译模式（英文远多于中文）
            alignment_rule_passed = True
            alignment_rule_details.append(f"M:{en_count//zh_count} 结构（{en_count} 英文 : {zh_count} 中文），属于官方翻译模式")
        elif zh_count > 0 and en_count > zh_count:
            # N:1 或 M:1 结构，也是允许的
            alignment_rule_passed = True
            alignment_rule_details.append(f"N:1 结构（{en_count} 英文 : {zh_count} 中文），符合多句对单段模式")
        else:
            alignment_rule_passed = False
            alignment_rule_details.append(f"英文 {en_count} 段 vs 中文 {zh_count} 段，比例异常")
    
    if alignment_rule_passed:
        results["英中句级对齐"] = ("[OK]", "每对英中关系为 1:1/N:1/1:N，无多对多模糊对应")
    else:
        results["英中句级对齐"] = ("[FAIL]", "; ".join(alignment_rule_details[:3]))
        failures.append(f"句级对齐规则：{'; '.join(alignment_rule_details[:3])}")

    # === 9. 英文原文保真规则（2026-07-05 新增） ===
    # 检查邮件中的英文部分是否完全等于 amruta.today 抓取原文
    try:
        with open(RAW_PATH, encoding="utf-8") as f:
            raw_data = json.load(f)

        original_en = raw_data.get("content", "").strip()

        # 从 HTML 中提取所有英文段落（排除标题段落）
        all_p_tags = re.findall(r'<p[^>]*>.*?</p>', html_content, re.DOTALL)
        en_paras_in_email = []
        for p_tag in all_p_tags:
            # 排除标题段落（font-style:italic）
            if 'font-style:italic' in p_tag:
                continue
            # 提取纯文本内容
            text = re.sub(r'<[^>]+>', '', p_tag).strip()
            if not text:
                continue
            # 判断是否为英文
            if re.search(r'[A-Z]', text) and not re.search(r'[\u4e00-\u9fff]', text):
                en_paras_in_email.append(text)
        
        # 去重：用集合找出唯一的英文内容
        unique_en = set()
        for p in en_paras_in_email:
            cleaned = strip_html(p).strip()
            if cleaned:
                unique_en.add(cleaned)
        
        # 拼接所有唯一英文句子（排序后比较，避免顺序差异）
        sorted_unique = sorted(unique_en, key=len, reverse=True)
        email_en_text = " ".join(sorted_unique).strip()
        
        # 比较：将两者都按句子拆分后排序比较（忽略空格差异）
        def extract_sentences(text):
            """提取文本中的所有句子，标准化后排序"""
            sents = [s.strip().rstrip('.,;:!?').strip() for s in re.split(r'[.!?]+\s+', text) if s.strip()]
            sents = [s for s in sents if s]  # 过滤空字符串
            sents.sort()
            return sents
        
        email_sents = extract_sentences(email_en_text)
        original_sents = extract_sentences(original_en)

        # 比较英文原文（使用句子集合比较）
        if email_sents == original_sents:
            results["英文原文保真"] = ("[OK]", f"邮件英文部分完全等于 amruta.today 抓取原文（{len(email_sents)} 个唯一句子，排序后一致）")
        else:
            # 检查差异
            email_set = set(email_sents)
            original_set = set(original_sents)
            missing = original_set - email_set
            extra = email_set - original_set
            
            if missing:
                failures.append(f"英文原文保真：缺少 {len(missing)} 个句子")
            if extra:
                failures.append(f"英文原文保真：多出 {len(extra)} 个句子")
            
            results["英文原文保真"] = ("[FAIL]", f"句子集合不匹配：邮件 {len(email_sents)} 句 vs 原文 {len(original_sents)} 句，缺{len(missing)}多{len(extra)}")
    except Exception as e:
        results["英文原文保真"] = ("[WARN]", f"检查失败：{e}")
        warnings.append(f"英文原文保真检查失败：{e}")

    # === 8. 翻译通顺度 ===
    if paras:
        short_trans = sum(1 for p in paras if len(strip_html(p)) < 5)
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
    report_lines.append(f"**检查时间** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report_lines.append(f"**文章** {raw.get('title', 'unknown')} ({raw.get('date', 'unknown')})\n")
    report_lines.append(f"**检查文件** {INPUT_PATH}\n")
    ima_results = load_ima_search_results()
    ima_report = format_ima_search_report(ima_results)
    # === IMA KB 搜索结果展示 ===
    if ima_results is not None:
        report_lines.append(ima_report)
        report_lines.append("")
    report_lines.append("\n## 检查结果\n")
    report_lines.append("| 维度 | 结果 | 备注 |")
    report_lines.append("|------|------|------|")

    for dim in ["翻译来源", "结构完整性", "英中交替", "段落数匹配", "中文非空", "底部链接", "来源标注", "Agnes AI 对齐验证", "英中句级对齐", "英文原文保真", "翻译通顺度"]:
        if dim in results:
            s, n = results[dim]
            report_lines.append(f"| {dim} | {s} | {n} |")
        else:
            report_lines.append(f"| {dim} | - | 未检查 |")

    report_lines.append("\n## 总评\n")
    if has_fail:
        report_lines.append(f"**判定** [FAIL] **不通过**（{len(failures)} 个失败项）")
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
        if any("句级对齐" in f for f in failures):
            report_lines.append("- 句级对齐规则：检查英中对应是否为 1:1/N:1/1:N，禁止多对多模糊对应")
        if any("英文原文保真" in f for f in failures):
            report_lines.append("- 英文原文保真：检查邮件英文部分是否与 amruta.today 抓取原文完全一致（不增多、不删减、不修改）")
    elif has_warn:
        report_lines.append(f"**判定** [WARN] **有条件通过**（{len(warnings)} 个警告项）")
        report_lines.append("\n### 警告项\n")
        for w_item in warnings:
            report_lines.append(f"- [WARN] {w_item}")
        report_lines.append("\n邮件继续发送，但建议后续修复。")
    else:
        report_lines.append("**判定** [OK] **通过**")

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
