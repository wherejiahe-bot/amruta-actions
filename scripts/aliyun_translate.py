"""阿里云翻译工具 - 用于批量翻译英文单词"""
import json, hashlib, hmac, base64, time, urllib.parse, urllib.request, uuid, ssl, os

ctx = ssl.create_default_context()

def aliyun_translate(text, access_key_id, access_key_secret):
    """调用阿里云翻译，返回翻译结果"""
    def sign(params, secret):
        sorted_keys = sorted(params.keys())
        canonicalized = '&'.join(f'{urllib.parse.quote(k, safe="")}={urllib.parse.quote(params[k], safe="")}' for k in sorted_keys)
        string_to_sign = 'POST&%2F&' + urllib.parse.quote(canonicalized, safe='')
        signature = base64.b64encode(hmac.new((secret + '&').encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()).decode('utf-8')
        return signature

    params = {
        'Action': 'TranslateGeneral',
        'Version': '2018-10-12',
        'RegionId': 'cn-hangzhou',
        'FormatType': 'text',
        'SourceLanguage': 'en',
        'TargetLanguage': 'zh',
        'SourceText': text,
        'AccessKeyId': access_key_id,
        'Timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'SignatureMethod': 'HMAC-SHA1',
        'SignatureVersion': '1.0',
        'SignatureNonce': str(uuid.uuid4()),
        'Format': 'JSON',
    }
    params['Signature'] = sign(params, access_key_secret)

    body = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request('https://mt.cn-hangzhou.aliyuncs.com/', data=body, method='POST',
        headers={'Content-Type': 'application/x-www-form-urlencoded'})
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    result = json.loads(resp.read().decode('utf-8'))
    if result.get('Code') == '200':
        return result.get('Data', {}).get('Translated', '')
    return ''

def extract_words(pairs):
    """从pairs中提取所有独特的英文单词（纯字母，长度>=2），支持多种pair格式"""
    import re
    words = set()
    for item in pairs:
        en = ""
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            en = item[0]  # [en, zh] 或 [en, zh, ...]
        elif isinstance(item, dict):
            en = item.get("en", item.get("english", ""))  # {"en": ..., "zh": ...}
        elif isinstance(item, str):
            en = item  # 纯字符串
        if not en:
            continue
        for w in re.findall(r'\b[A-Za-z]{2,}\b', str(en)):
            w_lower = w.lower()
            if len(w_lower) >= 2:
                words.add(w_lower)
    return sorted(words)

def build_word_map(words, access_key_id, access_key_secret, max_workers=20):
    """并行翻译所有单词，返回 {word: translation} 字典"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    word_map = {}
    total = len(words)
    lock = threading.Lock()
    counter = [0]  # 用列表存计数器以便闭包修改

    def translate_one(w):
        try:
            t = aliyun_translate(w, access_key_id, access_key_secret)
            if t and t.lower() != w.lower():
                return w, t
        except Exception as e:
            print(f"[translate] 翻译失败 [{w}]: {e}")
        return w, None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(translate_one, w): w for w in words}
        for f in as_completed(futures):
            w, t = f.result()
            if t:
                word_map[w] = t
            with lock:
                counter[0] += 1
                if counter[0] % 10 == 0 or counter[0] == total:
                    print(f"[translate] 阿里云翻译进度: {counter[0]}/{total}")

    print(f"[translate] 翻译完成: {len(word_map)}/{total} 个单词")
    return word_map

if __name__ == '__main__':
    # 测试
    words = ['liberation', 'freedom', 'shouldering', 'responsibility']
    key_id = os.environ.get('ALIYUN_ACCESS_KEY_ID', '')
    key_secret = os.environ.get('ALIYUN_ACCESS_KEY_SECRET', '')
    if key_id and key_secret:
        result = build_word_map(words, key_id, key_secret)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("请设置 ALIYUN_ACCESS_KEY_ID 和 ALIYUN_ACCESS_KEY_SECRET 环境变量")
