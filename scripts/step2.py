# ========== 语义去重（sentence-transformers） ==========
# 规则：
#   1. 用 LaBSE 做句子嵌入，余弦相似度 > THRESHOLD 视为重复
#   2. 如果两个重复句子长度相同 → 去哪个都行（保留第一个）
#   3. 如果长度不同 → 保留较长的，去除较短的
# 不去动前面的对齐、翻译逻辑

import numpy as np
from sentence_transformers import SentenceTransformer as STModel

DEDUP_THRESHOLD = 0.85  # 余弦相似度阈值，>0.85 视为重复
DEDUP_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"  # 轻量级，384维

# 加载模型（缓存已存在，首次下载后不再下载）
print(f"[dedup] Loading model: {DEDUP_MODEL_NAME}...")
try:
    _dedup_model = STModel(DEDUP_MODEL_NAME, device="cpu")  # 用CPU避免GPU依赖
    print(f"[dedup] Model loaded.")
except Exception as e:
    print(f"[dedup] Model load failed ({e}), skipping semantic dedup.")
    _dedup_model = None


def cosine_sim(vec1, vec2):
    """计算两个向量的余弦相似度"""
    a = np.array(vec1)
    b = np.array(vec2)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def semantic_dedup(pairs_list, lang="zh"):
    """
    对指定语言列做语义去重。
    
    Args:
        pairs_list: [(en, zh), ...] 原 pairs
        lang: "zh" 或 "en" — 对哪一列做去重
    
    Returns:
        [(en, zh), ...] 去重后的 pairs
        removed: 被去掉的句子数
    """
    if _dedup_model is None:
        print("[dedup] Model not loaded, skipping.")
        return pairs_list, 0

    # 提取目标语言列
    target_sents = []
    for i, (en, zh) in enumerate(pairs_list):
        text = zh if lang == "zh" else en
        target_sents.append((text.strip(), i))

    # 过滤空句子
    non_empty = [(t, idx) for t, idx in target_sents if t]
    if len(non_empty) < 2:
        return pairs_list, 0

    # 计算所有非空句子的 embedding
    print(f"[dedup] {lang.upper()}: computing embeddings for {len(non_empty)} sentences...")
    texts = [t for t, _ in non_empty]
    embeddings = _dedup_model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

    # 找出重复对
    removed_indices = set()
    dedup_count = 0

    for i in range(len(non_empty)):
        if i in removed_indices:
            continue
        for j in range(i + 1, len(non_empty)):
            if j in removed_indices:
                continue

            orig_i_idx = non_empty[i][1]
            orig_j_idx = non_empty[j][1]

            en_i, zh_i = pairs_list[orig_i_idx]
            en_j, zh_j = pairs_list[orig_j_idx]

            en_text = str(en_i).strip() if lang == "en" else ""
            zh_text = str(zh_i).strip() if lang == "zh" else ""
            en_text2 = str(en_j).strip() if lang == "en" else ""
            zh_text2 = str(zh_j).strip() if lang == "zh" else ""

            # 先检查纯字符串重复（快）
            if lang == "zh":
                text_a, text_b = zh_i, zh_j
            else:
                text_a, text_b = en_i, en_j

            if text_a.strip() == text_b.strip():
                # 纯字符串重复：长度相同任意删除，长度不同删除短的
                len_a = len(text_a.strip())
                len_b = len(text_b.strip())
                if len_a <= len_b:
                    removed_indices.add(orig_i_idx)
                    dedup_count += 1
                    print(f"  [dedup REMOVED] {lang}: '{text_a[:60]}...' (len={len_a}) == '{text_b[:60]}...' (len={len_b})")
                else:
                    removed_indices.add(orig_j_idx)
                    dedup_count += 1
                    print(f"  [dedup REMOVED] {lang}: '{text_b[:60]}...' (len={len_b}) == '{text_a[:60]}...' (len={len_a})")
                continue

            # 语义重复：余弦相似度 > THRESHOLD
            sim = cosine_sim(embeddings[i], embeddings[j])
            if sim > DEDUP_THRESHOLD:
                len_a = len(text_a.strip())
                len_b = len(text_b.strip())
                if len_a <= len_b:
                    removed_indices.add(orig_i_idx)
                    dedup_count += 1
                    print(f"  [dedup REMOVED] {lang}: '{text_a[:60]}...' (len={len_a}, sim={sim:.3f}) ~ '{text_b[:60]}...' (len={len_b})")
                else:
                    removed_indices.add(orig_j_idx)
                    dedup_count += 1
                    print(f"  [dedup REMOVED] {lang}: '{text_b[:60]}...' (len={len_b}, sim={sim:.3f}) ~ '{text_a[:60]}...' (len={len_a})")

    # 构建去重后的结果
    if removed_indices:
        deduped = [pairs_list[i] for i in range(len(pairs_list)) if i not in removed_indices]
        print(f"[dedup] Removed {dedup_count} duplicate {lang} sentence(s). Remaining: {len(deduped)}")
        return deduped, dedup_count
    else:
        print(f"[dedup] No {lang} duplicates found.")
        return pairs_list, 0


# ===== 执行中文去重（主要目标） =====
print(f"\n[dedup] === Starting semantic dedup ===")
pairs, zh_removed = semantic_dedup(pairs, lang="zh")

# ===== 再执行英文去重 =====
pairs, en_removed = semantic_dedup(pairs, lang="en")

print(f"\n[dedup] Summary: ZH removed: {zh_removed}, EN removed: {en_removed}")
print(f"[dedup] Final pairs count: {len(pairs)}")
