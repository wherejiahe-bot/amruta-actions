"""

Step 2: Login to sahaja.live, search for Chinese translation.

DIRECTLY adapted from the original Amruta Daily Push Coordinator.py (2nd run()).

Changes from original:

  - /workspace/ -> /tmp/

  - hardcoded credentials -> os.environ.get()

  - return -> file writes

Reads /tmp/article_raw.json, outputs /tmp/pairs.json, /tmp/email_body.html, /tmp/sahaja_link.txt

"""

import json, re, os, urllib.request, urllib.parse, hashlib, hmac, base64, time, uuid
import warnings
warnings.filterwarnings("ignore")
from datetime import datetime



# 阿里云翻译函数（仅标题翻译用)

def aliyun_translate_title(text):

    ak_id = os.environ.get("ALIYUN_ACCESS_KEY_ID", "")

    ak_secret = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")

    if not ak_id or not ak_secret:

        return ""

    def sign(params, secret):

        sorted_keys = sorted(params.keys())

        canonicalized = '&'.join(f'{urllib.parse.quote(k, safe="")}={urllib.parse.quote(params[k], safe="")}' for k in sorted_keys)

        string_to_sign = 'POST&%2F&' + urllib.parse.quote(canonicalized, safe='')

        sig = base64.b64encode(hmac.new((secret + '&').encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()).decode('utf-8')

        return sig

    try:

        params = {

            'Action': 'TranslateGeneral', 'Version': '2018-10-12', 'RegionId': 'cn-hangzhou',

            'FormatType': 'text', 'SourceLanguage': 'en', 'TargetLanguage': 'zh',

            'SourceText': text, 'AccessKeyId': ak_id,

            'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),

            'SignatureMethod': 'HMAC-SHA1', 'SignatureVersion': '1.0',

            'SignatureNonce': str(uuid.uuid4()), 'Format': 'JSON',

        }

        params['Signature'] = sign(params, ak_secret)

        body = urllib.parse.urlencode(params).encode('utf-8')

        req = urllib.request.Request('https://mt.cn-hangzhou.aliyuncs.com/', data=body, method='POST',

            headers={'Content-Type': 'application/x-www-form-urlencoded'})

        resp = urllib.request.urlopen(req, timeout=10)

        result = json.loads(resp.read().decode('utf-8'))

        if result.get('Code') == '200':

            return result.get('Data', {}).get('Translated', '')

    except:

        pass

    return ""



def polish_title(zh):

    zh = zh.replace('承担起', '肩负起').replace('承担', '肩负')

    zh = re.sub(r'(来起作用的|起作用的|来发挥作用的)$', '', zh).strip()

    zh = re.sub(r'^(通过你们|通过我们|通过|在于|由于|因为|当你们|当我们)', '', zh).strip()

    return zh



def extract_title_cn_from_pairs(pairs_list, en_title):

    keywords = [w.strip('.,!?"\'-()').lower() for w in en_title.split() if len(w.strip('.,!?"\'-()')) > 2]

    if not keywords:

        return None

    for en, zh in pairs_list:

        if not zh.strip():

            continue

        en_lower = en.lower()

        if all(kw in en_lower for kw in keywords):

            en_sents = re.split(r'[.,]', en)

            zh_sents = re.split(r'[，。]', zh)

            for i, es in enumerate(en_sents):

                es_lower = es.lower()

                if all(kw in es_lower for kw in keywords):

                    ratio = i / max(len(en_sents) - 1, 1)

                    zh_idx = round(ratio * (len(zh_sents) - 1))

                    zh_part = zh_sents[zh_idx].strip() if zh_idx < len(zh_sents) else ""

                    if len(zh_part) > 4:

                        return polish_title(zh_part)

            for part in re.split(r'[，。；]', zh):

                part = part.strip()

                if 4 < len(part) <= 20:

                    return polish_title(part)

    return None



with open("/tmp/article_raw.json", encoding="utf-8") as f:

    article = json.load(f)



date_str = article["date"]

title_en = article["title"]

content  = article["content"]

link     = article.get("link", "")



sahaja_link = None

pairs = []

title_cn = title_en  # 先设 fallback，找到 pairs 后再更新



def parse_sahaja_full_text(full_text):

    """解析 sahaja.live 中英交替段落，返回 [(en, zh), ...] pairs"""

    def is_zh_block(text):

        cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')

        return cn >= 3



    blocks = [b.strip() for b in re.split(r'\n{2,}', full_text) if b.strip()]



    def is_meta_block(b):

        """判断是否为头部元信息行（日期、地点、语言说明、译注等)"""

        if is_zh_block(b):

            return True

        if re.match(r'^\d{1,2}\s+\w+\s+\d{4}', b):  # "11 June 1989"

            return True

        if re.search(r'\d{4}年', b):  # 含中文年份

            return True

        if any(kw in b for kw in ['Talk Language', 'Transcript', 'VERIFIED', 'NEEDED',

                                   '以下翻译', '供大家参考', 'subtitles', 'Subtitles']):

            return True

        # 纯地名行：含括号国家名，无动词

        if (re.search(r'\((?:United States|USA|UK|India|France|Italy|Australia|Germany|Spain)\)', b)

                and not re.search(r'\b(is|are|was|were|have|has|will|can|should|must|know|think|feel|decide|come|go)\b', b, re.I)):

            return True

        # 元信息重复行：含年份数字 + 地名关键词且无动词

        if (re.search(r'\b(19|20)\d{2}\b', b)

                and re.search(r'\b(USA|UK|India|France|Italy|Australia|Camp|Puja)\b', b)

                and not re.search(r'\b(is|are|was|were|have|has|will|can|should|must|know|think|feel|decide)\b', b, re.I)):

            return True

        return False



    result = []

    i = 0

    # 跳过头部元信息，找到正文起点（第一个非元信息的英文段)

    while i < len(blocks):

        b = blocks[i]

        if not is_meta_block(b) and len(b) > 40 and re.search(r'[A-Z][a-z]', b):

            break

        i += 1



    while i < len(blocks):

        en_block = blocks[i]

        if is_zh_block(en_block):

            i += 1

            continue

        if i + 1 < len(blocks) and is_zh_block(blocks[i + 1]):

            zh_block = blocks[i + 1]

            result.append([en_block, zh_block])

            i += 2

        else:

            result.append([en_block, ""])

            i += 1



    return result



def parse_merged_text(full_text):

    """解析 EN/ZH 合并在同一段落的格式（1978年早期讲话)。"""

    blocks = [b.strip() for b in re.split(r'\n{2,}', full_text) if b.strip()]

    result = []

    start = 0

    for i, b in enumerate(blocks):

        cn = sum(1 for c in b if '\u4e00' <= c <= '\u9fff')

        if cn == 0 and len(b) > 40 and re.search(r'[A-Z][a-z]', b):

            start = i

            break

    for block in blocks[start:]:

        cn = sum(1 for c in block if '\u4e00' <= c <= '\u9fff')

        if cn == 0:

            result.append([block, ''])

            continue

        m = re.split(r'(?<=[.!?])\s*(?=[\u4e00-\u9fff])', block, maxsplit=1)

        if len(m) >= 2:

            en_part, zh_part = m[0].strip(), m[1].strip()

            if en_part and zh_part:

                result.append([en_part, zh_part])

                continue

        for i, c in enumerate(block):

            if '\u4e00' <= c <= '\u9fff':

                result.append([block[:i].strip(), block[i:].strip()])

                break

    return result



def has_chinese(pairs_list):

    return any(zh.strip() for _, zh in pairs_list)



# ================================================================== #

# 句级对齐：用 amruta 英文句在 sahaja pairs 段落中匹配中文句

# ================================================================== #

def split_sentences(text):

    """按句号/问号/感叹号+空格+大写字母拆分英文句"""

    sents = re.split(r'(?<=[.!?])\s+(?=[A-Z"\'(])', text.strip())

    return [s.strip() for s in sents if len(s.strip()) > 10]



def sentence_similarity(s1, s2):

    """计算两个英文句的词重叠率"""

    w1 = set(re.findall(r'\b\w{4,}\b', s1.lower()))

    w2 = set(re.findall(r'\b\w{4,}\b', s2.lower()))

    if not w1 or not w2:

        return 0

    return len(w1 & w2) / min(len(w1), len(w2))



# 英文关键词 → 中文对应词典（用于在中文句里定位)

EN_ZH_DICT = {

    'advertisement': '广告', 'photographs': '照片', 'photograph': '照片',

    'responsibility': '责任', 'shouldering': '承担', 'spread': '传播',

    'establish': '体系', 'shoulders': '肩膀', 'strong': '坚强',

    'hanging': '飘荡', 'aeroplane': '飞机', 'freedom': '自由',

    'liberation': '解脱', 'binding': '束缚', 'attached': '依恋',

    'grow': '成长', 'personality': '个性', 'impressed': '打动',

    'vicious': '恶性', 'circle': '循环', 'build': '建设',

    'deep': '深入', 'dynamic': '活力', 'great': '伟大',

    'transitory': '短暂', 'eternal': '永恒', 'detached': '解脱',

    'subtler': '微妙', 'light': '光明', 'purpose': '目的',

    'watch': '观察', 'subtle': '微妙', 'tagging': '拖累',

    'dwarfy': '渺小', 'limited': '有限',

    'carry': '承担', 'carrying': '承担',

    'fuel': '油', 'fly': '飞', 'flying': '飞',

    'inside': '内心', 'outside': '外在',

    'hand': '辅相成', 'amazed': '惊讶',

    'involved': '陷入', 'seeking': '寻求',

    'free': '自由', 'using': '利用',

    'grow': '成长', 'growing': '成长', 'growth': '成长',

    'rationality': '理性', 'rational': '理性',

    'reason': '理由', 'wisdom': '智慧',

    'emotional': '情感', 'emotion': '情感', 'emotionality': '情感',

    'balance': '平衡', 'centre': '中心', 'central': '中心',

    'heart': '心', 'mind': '脑',

    'understand': '理解', 'understanding': '理解',

    'knowledge': '知识', 'experience': '体验', 'experiencing': '体验',

    'reality': '实相', 'truth': '真理',

    'progress': '进步', 'limitation': '局限', 'limited': '有限',

    'beyond': '超越', 'transcend': '超越',

    'consciousness': '意识', 'awareness': '觉知',

    'joy': '喜乐', 'bliss': '极乐',

    'sahaja': '霎哈嘉', 'yoga': '瑜伽',

    'meditation': '冥想', 'thoughtless': '无思虑',

    'vibration': '生命能量', 'vibrations': '生命能量',

    'chakra': '轮穴', 'kundalini': '灵量',

    'realisation': '自觉', 'self-realisation': '自觉',

    'enlighten': '开悟', 'awaken': '觉醒',

}



def en_sent_to_zh_keywords(en_sent):

    """把英文句的关键词翻成中文，用于在中文句里匹配"""

    words = re.findall(r'\b[a-z]{4,}\b', en_sent.lower())

    zh_kws = []

    for w in words:

        if w in EN_ZH_DICT:

            zh_kws.append(EN_ZH_DICT[w])

    return zh_kws



def find_zh_for_en_sent(en_sent, sahaja_pairs, used_zh=None):

    """

    对每句 amruta 英文：

    1. 在 sahaja 段级 pairs 英文里找最匹配的段落

    2. 把英文句关键词翻成中文，在中文段的子句里找命中最多的那句

    """

    stopwords = {'that','this','with','have','your','from','they','them',

                 'will','what','when','into','been','were','also','just',

                 'more','than','then','there','their','which','still','only',

                 'such','very','even','does','dont','cant','wont','should'}

    en_keywords = set(re.findall(r'\b[a-z]{4,}\b', en_sent.lower())) - stopwords



    if not en_keywords:

        return ""



    # Step 1: 找最匹配的 sahaja 段落（英文段关键词重叠最多)

    best_score = 0

    best_zh_para = ""

    best_en_para = ""

    for en_para, zh_para in sahaja_pairs:

        if not zh_para.strip():

            continue

        para_words = set(re.findall(r'\b[a-z]{4,}\b', en_para.lower())) - stopwords

        score = len(en_keywords & para_words) / max(len(en_keywords), 1)

        if score > best_score:

            best_score = score

            best_zh_para = zh_para

            best_en_para = en_para



    if best_score < 0.2 or not best_zh_para:

        return ""



    # Step 2: 把英文句关键词翻成中文

    zh_kws = en_sent_to_zh_keywords(en_sent)



    # Step 3: 中文段按句拆分，找命中中文关键词最多的子句

    zh_sents = [s.strip() for s in re.split(r'[。！？]', best_zh_para) if len(s.strip()) > 3]

    if not zh_sents:

        return best_zh_para



    if zh_kws:

        best_zh_score = -1

        best_zh_sent = zh_sents[0]

        for zs in zh_sents:

            if used_zh and zs in used_zh:

                continue  # 跳过已用过的句子

            sc = sum(1 for kw in zh_kws if kw in zs)

            if sc > best_zh_score:

                best_zh_score = sc

                best_zh_sent = zs

        return best_zh_sent



    # 没有中文关键词时，按位置比例映射

    en_sents_in_para = split_sentences(best_en_para)

    sent_idx = 0

    best_sub = 0

    for idx, es in enumerate(en_sents_in_para):

        es_words = set(re.findall(r'\b[a-z]{4,}\b', es.lower())) - stopwords

        sc = len(en_keywords & es_words) / max(len(en_keywords), 1)

        if sc > best_sub:

            best_sub = sc

            sent_idx = idx

    ratio = sent_idx / max(len(en_sents_in_para) - 1, 1)

    zh_idx = round(ratio * (len(zh_sents) - 1))

    return zh_sents[min(zh_idx, len(zh_sents) - 1)]





import numpy as np
from sentence_transformers import SentenceTransformer
try:
    _bg = SentenceTransformer("BAAI/bge-small-zh-v1.5")
except:
    _bg = None

def do_alignment_and_audit():
    """BGE整段中文匹配，不切子句"""
    global pairs, title_cn
    amruta_sents = split_sentences(content)
    if not amruta_sents: return
    stopwords = {"that","this","with","have","your","from","they","them","will","what","when","into","been","were","also","just","more","than","then","there","their","which","still","only","such","very","even","does","dont","cant","wont","should"}
    def best_para_for_sent(en_s, lst):
        kws = set(re.findall(r"[a-z]{4,}", en_s.lower())) - stopwords
        best_sc, best_pi = 0, 0
        for pi, (ep, zp) in enumerate(lst):
            if not zp.strip(): continue
            epw = set(re.findall(r"[a-z]{4,}", ep.lower())) - stopwords
            if not epw: continue
            sc = len(kws & epw) / max(len(kws), 1) if kws else 0
            if sc > best_sc: best_sc, best_pi = sc, pi
        return best_pi
    first_pi = max(best_para_for_sent(amruta_sents[0], pairs), 2)
    last_pi = best_para_for_sent(amruta_sents[-1], pairs)
    if last_pi < first_pi: last_pi = first_pi
    for pi in range(last_pi+1, min(last_pi+15, len(pairs))):
        if pairs[pi][1].strip(): last_pi = pi
    print(f"[translate] 锚定[{first_pi}~{last_pi}]")
    # 直接用整段中文（不切子句)，跳过空段
    zh_sents = []
    para_indices = []
    for pi in range(first_pi, min(last_pi+1, len(pairs))):
        zp = pairs[pi][1].strip()
        if len(zp) >= 4:
            zh_sents.append(zp)
            para_indices.append(pi)
    if not zh_sents: pairs = [[s,""] for s in amruta_sents]; return
    # BGE英-中匹配：每句英文找最佳IMA整段
    used = set()
    aligned = []
    if _bg is not None:
        en_vecs = _bg.encode(amruta_sents, normalize_embeddings=True, show_progress_bar=False)
        zh_vecs = _bg.encode(zh_sents, normalize_embeddings=True, show_progress_bar=False)
    for i, sent in enumerate(amruta_sents):
        aliyun_zh = aliyun_translate_title(sent)
        if _bg is not None:
            best_sc, best_zp, best_pi = -1, "", -1
            for pi in range(len(zh_sents)):
                if pi in used: continue
                sc = float(np.dot(en_vecs[i], zh_vecs[pi]))
                if sc > best_sc: best_sc, best_zp, best_pi = sc, zh_sents[pi], pi
            if best_pi >= 0 and best_sc >= 0.3:
                aligned.append([sent, best_zp])
                used.add(best_pi)
            else: aligned.append([sent, aliyun_zh or ""])
        else: aligned.append([sent, aliyun_zh or ""])
    pairs = [list(p) for p in aligned]
    # 后处理
    for idx in range(len(pairs)):
        zh = pairs[idx][1]
        zh = zh.replace("左翼还是右翼", "偏左或偏右")
        zh = zh.replace("左翼或右翼", "偏左或偏右")
        pairs[idx][1] = zh
    cn = sum(1 for _,z in pairs if z.strip())
    print(f"[translate] 完成: {len(pairs)}句, {cn}句有中文")
# ============ Aliyun translation + HTML build ============ #
if pairs:
    do_alignment_and_audit()
else:
    amruta_sents = split_sentences(content)
    if amruta_sents:
        aligned = []
        for s in amruta_sents:
            zh = aliyun_translate_title(s)
            aligned.append([s, zh or ""])
        pairs = [list(p) for p in aligned]
        print(f"[translate_article] Aliyun done: {len(pairs)} sentences")

# ============ IMA backup ============ #
if not pairs:
    cid = os.environ.get("IMA_CLIENT_ID", "")
    aik = os.environ.get("IMA_API_KEY", "")
    if cid and aik:
        print(f"[translate_article] Searching IMA for {date_str}...")

# ============ Fallback ============ #
if not pairs:
    paras = [p.strip() for p in content.split(chr(10)) if p.strip()]
    pairs = [[p, ""] for p in paras]
    print(f"[translate_article] No Chinese, EN only: {len(pairs)} paras")

# ============ 标题翻译 + D Link ============ #
if title_cn == title_en or not any("一" <= c <= "鿿" for c in title_cn):
    t = aliyun_translate_title(title_en)
    if t: title_cn = t
final_link = sahaja_link or link
# ============ HTML ============ #
lines = []
for en, zh in pairs:
    en = str(en).strip() if en else ""
    zh = str(zh).strip() if zh else ""
    if not en and not zh: continue
    if en and zh:
        lines.append("<p style=\"color:#888;font-size:0.85em;margin:0 0 2px 0;\">" + en + "</p><p style=\"margin:0 0 14px 0;\">" + zh + "</p>")
    elif en:
        lines.append("<p style=\"color:#888;font-size:0.85em;margin:0 0 14px 0;\">" + en + "</p>")
pair_html = chr(10).join(lines)
try:
    from datetime import datetime as dt2
    dt = dt2.strptime(date_str, "%Y-%m-%d")
    dd = date_str
except: dd = date_str
link = sahaja_link or link
html = "<!DOCTYPE html><html><head><meta charset=utf-8><meta name=viewport content=width=device-width,initial-scale=1></head><body style=font-family:Helvetica Neue,Arial,sans-serif;max-width:680px;margin:0 auto;padding:24px 16px;color:#222;line-height:1.7;>"
html += "<h2 style=margin:0 0 4px 0;font-size:1.25em;font-weight:700;>" + str(title_cn) + "</h2>"
html += "<p style=color:#888;font-size:0.85em;margin:0 0 4px 0;font-style:italic;>" + str(title_en) + "</p>"
html += "<p style=color:#aaa;font-size:0.8em;margin:0 0 24px 0;>" + dd + "</p>"
html += "<hr style=border:none;border-top:1px solid #eee;margin:0 0 24px 0;>"
html += pair_html
html += "<hr style=border:none;border-top:1px solid #eee;margin:24px 0 16px 0;>"
html += "<p style=color:#aaa;font-size:0.8em;margin:0;word-break:break-all;><a href=https://amruta.today/ style=color:#aaa;>https://amruta.today/</a><br><br><a href=" + link + " style=color:#aaa;>" + link + "</a></p>"
html += "</body></html>"

with open("/tmp/pairs.json", "w", encoding="utf-8") as f:
    json.dump(pairs, f, ensure_ascii=False, indent=2)
with open("/tmp/email_body.html", "w", encoding="utf-8") as f:
    f.write(html)
with open("/tmp/sahaja_link.txt", "w", encoding="utf-8") as f:
    f.write(link or "")
print(f"[translate_article] HTML done, {len(pairs)} pairs")
