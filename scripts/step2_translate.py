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
import numpy as np
from sentence_transformers import SentenceTransformer
from scipy.optimize import linear_sum_assignment

from datetime import datetime



# 阿里云翻译函数（仅标题翻译用）

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

        """判断是否为头部元信息行（日期、地点、语言说明、译注等）"""

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

    # 跳过头部元信息，找到正文起点（第一个非元信息的英文段）

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

    """解析 EN/ZH 合并在同一段落的格式（1978年早期讲话）。"""

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



# 英文关键词 → 中文对应词典（用于在中文句里定位）

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



    # Step 1: 找最匹配的 sahaja 段落（英文段关键词重叠最多）

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




# 跨语言语义模型（sentence-transformers，用于顺序贪婪匹配）
try:
    _align_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
except:
    _align_model = None

def _calc_similarity(en_text, zh_text):
    """计算一句英文和一段中文的语义相似度（0~1）"""
    if _align_model is None or not en_text or not zh_text:
        return 0
    ev = _align_model.encode([en_text], normalize_embeddings=True, show_progress_bar=False)
    zv = _align_model.encode([zh_text], normalize_embeddings=True, show_progress_bar=False)
    from sentence_transformers.util import cos_sim
    sim = float(cos_sim(ev, zv)[0][0])
    return max(0, min(1, sim))

def do_alignment_and_audit():
    """句级对齐：段落锚定→顺序贪婪匹配（不能跳句，不能改句）"""
    global pairs, title_cn
    amruta_sents = split_sentences(content)
    if not amruta_sents:
        return
    stopwords = {'that','this','with','have','your','from','they','them',
                 'will','what','when','into','been','were','also','just',
                 'more','than','then','there','their','which','still','only',
                 'such','very','even','does','dont','cant','wont','should'}
    def best_para_for_sent(en_s, sahaja_pairs_list):
        kws = set(re.findall(r'\b[a-z]{4,}\b', en_s.lower())) - stopwords
        best_sc, best_pi = 0, 0
        for pi, (ep, zp) in enumerate(sahaja_pairs_list):
            if not zp.strip(): continue
            ep_words = set(re.findall(r'\b[a-z]{4,}\b', ep.lower())) - stopwords
            if not ep_words: continue
            sc = len(kws & ep_words) / max(len(kws), 1) if kws else 0
            if sc > best_sc:
                best_sc, best_pi = sc, pi
        return best_pi
    # 段落锚定
    first_pi = best_para_for_sent(amruta_sents[0], pairs)
    last_pi  = best_para_for_sent(amruta_sents[-1], pairs)
    if last_pi < first_pi: last_pi = first_pi
    if first_pi < 2: first_pi = 2
    # 用语义模型扩展 last_pi：往后检查每个段落是否与amruta末句相关
    last_sent = amruta_sents[-1]
    expand_pi = last_pi
    skip_count = 0
    for pi in range(last_pi + 1, min(last_pi + 30, len(pairs))):
        zp = pairs[pi][1]
        if not zp.strip():
            skip_count += 1
            if skip_count >= 3: break
            continue
        sim = _calc_similarity(last_sent, zp)
        if sim >= 0.3:
            expand_pi = pi
            skip_count = 0
        else:
            skip_count += 1
            if skip_count >= 3: break
    last_pi = expand_pi
    print(f"[translate_article] 锚定范围语义扩展: [{first_pi}~{last_pi}]")
    # 从锚定范围切中文子句
    zh_pool = []
    for pi in range(first_pi, min(last_pi + 1, len(pairs))):
        for zs in re.split(r'[\u3002\uff01\uff1f\uff0c]', pairs[pi][1]):
            zs = zs.strip()
            if len(zs) >= 4:
                zh_pool.append(zs)
    if not zh_pool:
        pairs = [[s, ''] for s in amruta_sents]
        print("[translate_article] IMA中文池为空")
        return
    # 顺序贪婪匹配：每句英文吃连续的N个中文字句
    # 规则：从当前指针开始，合并子句，算相似度
    # 加入下一个子句后相似度下降则停止，上升则继续
    cursor = 0
    aligned = []
    for i, sent in enumerate(amruta_sents):
        if cursor >= len(zh_pool):
            aligned.append([sent, ''])
            continue
        # 初始过滤：跳过问句、过短(<8字)、语义太低的子句
        while cursor < len(zh_pool):
            zs = zh_pool[cursor]
            if len(zs) < 4 or re.search(r'[呢吗]$', zs):
                cursor += 1; continue
            en_kw = [w.strip('.,!?"\'-()').lower() for w in sent.split() if len(w.strip('.,!?"\'-()')) > 2]
            dict_hits = sum(1 for kw in en_kw if kw in EN_ZH_DICT and EN_ZH_DICT[kw] in zs)
            if dict_hits == 0 and len([k for k in en_kw if k in EN_ZH_DICT]) >= 2:
                cursor += 1; continue
            sim = _calc_similarity(sent, zs)
            if sim < 0.3:
                cursor += 1; continue
            break
        if cursor >= len(zh_pool):
            aligned.append([sent, '']); continue
        # 双模型对比：子句与当前句和下一句比，决定归属
        merged = zh_pool[cursor]
        cursor += 1
        print(f"  [{i+1}] 初始子句{cursor}: sim=?.??? | {merged[:20]}")
        while cursor < len(zh_pool):
            zs = zh_pool[cursor]
            sim_cur = _calc_similarity(sent, zs)
            if i < len(amruta_sents) - 1:
                sim_nxt = _calc_similarity(amruta_sents[i+1], zs)
                if sim_cur < sim_nxt:
                    print(f"      子句{cursor+1}: cur={sim_cur:.3f} < nxt={sim_nxt:.3f} → 留到下一句")
                    break
                else:
                    print(f"      子句{cursor+1}: cur={sim_cur:.3f} >= nxt={sim_nxt:.3f} → 合并")
            merged = merged + "，" + zs
            cursor += 1
        aligned.append([sent, merged])
    pairs = aligned
    cn_count = sum(1 for _, zh in pairs if zh.strip())
    print(f"[translate_article] 锚定[{first_pi}~{last_pi}]，贪婪匹配: {len(pairs)}句，{cn_count}句有中文")

# ================================================================== #

# IMA 知识库备用（登录失败时使用）

# ================================================================== #

if not pairs:

    IMA_CLIENT_ID = os.environ.get("IMA_CLIENT_ID", "")

    IMA_API_KEY = os.environ.get("IMA_API_KEY", "")

    IMA_KB_ID = os.environ.get("IMA_KB_ID", "XbbHhqibvE1vxMvwq4uzEF3dyxcQhSgOBCdi9gIAWWI=")



    if IMA_CLIENT_ID and IMA_API_KEY:

        print(f"[translate_article] 尝试从 IMA 知识库搜索 {date_str} 的中文翻译...")

        ima_headers = {

            "ima-openapi-clientid": IMA_CLIENT_ID,

            "ima-openapi-apikey": IMA_API_KEY,

            "Content-Type": "application/json"

        }



        # 搜索 sajaha live talks 文件夹

        ima_search_url = "https://ima.qq.com/openapi/wiki/v1/search_knowledge"

        search_body = json.dumps({

            "query": date_str,

            "cursor": "",

            "knowledge_base_id": IMA_KB_ID

        }).encode()



        try:

            # 先直接测试 API 连通性

            print(f"[translate_article] IMA KB: {IMA_KB_ID}, query: {date_str}")

            req = urllib.request.Request(ima_search_url, data=search_body, headers=ima_headers, method="POST")

            resp = urllib.request.urlopen(req, timeout=15)

            resp_text = resp.read().decode("utf-8")

            print(f"[translate_article] IMA 响应长度: {len(resp_text)} 字符")

            search_result = json.loads(resp_text)



            # 打印原始响应前 200 字符用于调试

            print(f"[translate_article] IMA 原始响应: {resp_text[:200]}")



            code = search_result.get("code", -1)

            if code == 0:

                data_field = search_result.get("data", {})

                # IMA API 可能用 searched_knowledge_list 或 info_list

                info_list = data_field.get("info_list") or data_field.get("searched_knowledge_list", [])

                if not info_list and isinstance(search_result, dict):

                    # 有时候直接返回 searched_knowledge_list 在顶层

                    info_list = search_result.get("searched_knowledge_list", [])

                print(f"[translate_article] IMA 搜索到 {len(info_list)} 条结果")



                # 找 "sahaja live talks" 文件夹中的中文翻译 MD 文件

                target_media_id = None

                target_title = ""

                for item in info_list:

                    title = item.get("title", "")

                    knowledge_node = item.get("knowledge", item)  # 可能嵌套在 knowledge 字段下

                    mid = knowledge_node.get("media_id", item.get("media_id", ""))

                    # 优先找中英对照的 MD 文件（标题含中文的）

                    if any('\u4e00' <= c <= '\u9fff' for c in title):

                        target_media_id = mid

                        target_title = title

                        print(f"[translate_article] IMA 找到中文文件: {title} (media_id: {mid[:30]}...)")

                        break



                if not target_media_id:

                    # 没有中文标题，取第一个 MD 文件

                    for item in info_list:

                        knowledge_node = item.get("knowledge", item)

                        mid = knowledge_node.get("media_id", item.get("media_id", ""))

                        if mid.startswith("markdown_"):

                            target_media_id = mid

                            target_title = knowledge_node.get("title", item.get("title", ""))

                            print(f"[translate_article] IMA 取第一个 MD 文件: {target_title}")

                            break



                if target_media_id:

                    # 获取文件下载链接

                    media_info_body = json.dumps({"media_id": target_media_id}).encode()

                    req2 = urllib.request.Request(

                        "https://ima.qq.com/openapi/wiki/v1/get_media_info",

                        data=media_info_body, headers=ima_headers, method="POST")

                    resp2 = urllib.request.urlopen(req2, timeout=15)

                    media_info = json.loads(resp2.read().decode("utf-8"))



                    if media_info.get("code") == 0:

                        url_info = media_info.get("data", {}).get("url_info", {})

                        file_url = url_info.get("url", "")

                        file_headers = url_info.get("headers", {})



                        if file_url:

                            print(f"[translate_article] IMA 下载文件: {file_url[:60]}...")

                            file_req = urllib.request.Request(file_url, headers=file_headers)

                            file_resp = urllib.request.urlopen(file_req, timeout=30)

                            md_content = file_resp.read().decode("utf-8", errors="replace")



                            # 从 YAML frontmatter 提取 source 和中文标题

                            source_m = re.search(r'^source:\s*(.+)$', md_content, re.MULTILINE)

                            if source_m:

                                real_source = source_m.group(1).strip().strip('"').strip("'")

                                sahaja_link = real_source

                                print(f"[translate_article] IMA source: {real_source}")

                            else:

                                sahaja_link = f"https://www.sahaja.live/?p={target_media_id.split('_')[-1][:10]}"



                            # 从 YAML frontmatter 提取中文标题

                            title_m = re.search(r'^title:\s*["\']?(?:\d{4}-\d{2}-\d{2}\s*)?(.+?)["\']?\s*$', md_content, re.MULTILINE)

                            if title_m:

                                ima_title_cn = title_m.group(1).strip().rstrip('.md')

                                if any('\u4e00' <= c <= '\u9fff' for c in ima_title_cn):

                                    title_cn = ima_title_cn

                                    print(f"[translate_article] IMA 中文标题: {title_cn}")



                            # 解析 YAML frontmatter 和正文

                            if md_content.startswith("---"):

                                parts = md_content.split("---", 2)

                                if len(parts) >= 3:

                                    md_body = parts[2].strip()

                                else:

                                    md_body = md_content

                            else:

                                md_body = md_content



                            # 统一换行符（COS下载的文件可能是 \r\n）

                            md_body = md_body.replace('\r\n', '\n')



                            # 用原有的解析器处理正文

                            print(f"[translate_article] MD 正文前200字: {md_body[:200].replace(chr(10),' ')}")

                            candidate = parse_sahaja_full_text(md_body)

                            if not has_chinese(candidate):

                                # 尝试 EN/ZH 合并段落格式（1978年早期讲话）

                                print("[translate_article] 尝试合并段落解析器...")

                                candidate = parse_merged_text(md_body)

                            if has_chinese(candidate):

                                pairs = candidate

                                # sahaja_link 已在上面从 frontmatter 中提取，不再覆盖

                                extracted = extract_title_cn_from_pairs(pairs, title_en)

                                if extracted:

                                    if len(extracted) > 15:

                                        # 先尝试按关键词取最短子句

                                        kws = [w.lower() for w in re.findall(r'\b[a-z]{4,}\b', title_en) if w.lower() not in {'the','for','and','that','this','with','from','they','will','what','when','were','also','more','than','then','there','their','which','still','only','about','been'}]

                                        best_part = ""

                                        for part in re.split(r'[，。；？]', extracted):

                                            part = part.strip()

                                            if not part: continue

                                            if all(kw in part for kw in kws):

                                                best_part = part

                                        if not best_part:

                                            parts2 = [p.strip() for p in re.split(r'[，。；？]', extracted) if p.strip()]

                                            if parts2:

                                                best_part = parts2[-1]

                                        # 如果关键词截取后还是太长，调用阿里云翻译英文标题

                                        if len(best_part) > 15:

                                            translated = aliyun_translate_title(title_en)

                                            if translated and len(translated) <= 15:

                                                title_cn = translated

                                                print(f"[translate_article] 标题阿里云翻译: {title_cn}")

                                            elif best_part:

                                                title_cn = best_part

                                            else:

                                                title_cn = extracted

                                        elif best_part:

                                            title_cn = best_part

                                        else:

                                            title_cn = extracted

                                    else:

                                        title_cn = extracted

                                    print(f"[translate_article] 标题译文: {title_cn}")

                                print(f"[translate_article] ✅ IMA 命中，段落级配对: {len(pairs)}")

                                # 句级对齐 + 审核修正

                                do_alignment_and_audit()

                            else:

                                print(f"[translate_article] IMA 文件无中文配对吧")



        except Exception as e:

            print(f"[translate_article] IMA 搜索失败: {e}")



# ================================================================== #

# 最终 fallback：只显示英文

# ================================================================== #

if not pairs:

    content_paras = [p.strip() for p in content.split('\n') if p.strip()]

    pairs = [[p, ""] for p in content_paras]

    print(f"[translate_article] ⚠️ 无中文翻译，仅显示英文，段落数: {len(pairs)}")



# ================================================================== #

# 构建 HTML 邮件

# ================================================================== #

pair_html_lines = []

for en, zh in pairs:

    en = str(en).strip() if en else ""

    zh = str(zh).strip() if zh else ""

    if not en and not zh:

        continue

    if en and zh:

        pair_html_lines.append(

            f'<p style="color:#888;font-size:0.85em;margin:0 0 2px 0;">{en}</p>'            f'<p style="margin:0 0 14px 0;">{zh}</p>'        )

    elif en:

        pair_html_lines.append(

            f'<p style="color:#888;font-size:0.85em;margin:0 0 14px 0;">{en}</p>'        )

    elif zh:

        pair_html_lines.append(f'<p style="margin:0 0 14px 0;">{zh}</p>')



pair_html = "\n".join(pair_html_lines)



try:

    dt = datetime.strptime(date_str, "%Y-%m-%d")

    date_display = dt.strftime("%Y年%-m月%-d日")

except Exception:

    date_display = date_str



final_link = sahaja_link or link



email_html = f"""<!DOCTYPE html>

<html>

<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>

<body style="font-family:'Helvetica Neue',Arial,sans-serif;max-width:680px;margin:0 auto;padding:24px 16px;color:#222;line-height:1.7;">



<h2 style="margin:0 0 4px 0;font-size:1.25em;font-weight:700;">{title_cn}</h2>

<p style="color:#888;font-size:0.85em;margin:0 0 4px 0;font-style:italic;">{title_en}</p>

<p style="color:#aaa;font-size:0.8em;margin:0 0 24px 0;">{date_display}</p>



<hr style="border:none;border-top:1px solid #eee;margin:0 0 24px 0;">



{pair_html}



<hr style="border:none;border-top:1px solid #eee;margin:24px 0 16px 0;">

<p style="color:#aaa;font-size:0.8em;margin:0;word-break:break-all;">

  <a href="https://amruta.today/" style="color:#aaa;">https://amruta.today/</a>

  <br>

  <br>

  <a href="{final_link}" style="color:#aaa;">{final_link}</a>

</p>



</body>

</html>"""



with open("/tmp/pairs.json", "w", encoding="utf-8") as f:

    json.dump(pairs, f, ensure_ascii=False, indent=2)



with open("/tmp/email_body.html", "w", encoding="utf-8") as f:

    f.write(email_html)



with open("/tmp/sahaja_link.txt", "w", encoding="utf-8") as f:

    f.write(final_link or "")



print(f"[translate_article] ✅ HTML 邮件构建完成，配对数: {len(pairs)}")
