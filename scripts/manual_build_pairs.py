"""
手动构建今日文章的中英对照 pairs + 邮件 HTML
用于本地验证推流流程，绕过 IMA / NVIDIA API 依赖
"""
import json, re, os

# ======== 1. 读 article_raw.json (step1 输出) ========
article_path = "/tmp/article_raw.json"
if os.path.exists(article_path):
    with open(article_path, encoding="utf-8") as f:
        article = json.load(f)
    title_en = article["title"]
    content_en = article["content"]
    date_str = article["date"]
    link = article.get("link", "")
    print(f"[OK] 已从 {article_path} 读取文章：{date_str} - {title_en}")
else:
    # 手动指定（如果 step1 还没跑）
    title_en = "Queen Victoria"
    date_str = "1995-06-25"
    content_en = """Love should be pure. If you have love for someone you won't see bad points of the other person, never. You will always see the good points of that person, always support that person. Sometimes I'm faced with such problems that there are people who are to be told, so I prepare myself first. Before the mirror - "I'll stand up and say like this, I'll say like this, I'll say like this". When the person comes in, half of it is lost. When I'm talking about 25% of this gets lost, whatever, 25% I have left, I tried it. It's very easy to give up that than to keep it, very easy. It is better if you practice that, I'm sure. So little, little things you can suggest to them.
Like yesterday, you know what a nice present the English Sahaja Yogis gave me, was a beautiful miniature of Royal Albert Hall. Can you imagine, beautiful. With handwork on that, beautifully done, so beautifully done. It really, it was so from the heart, because I loved this hall somehow, since long. And shows the Queen Victoria, for whom I have such tremendous respect. Like she built it in the name of her husband. This kind of thing shows such a deep reverence for her husband, love for her husband, and she remained like a widow, when he died, throughout. She didn't attend any functions, nothing. Like an Indian, we don't, the women. And she enjoyed her widowhood. She was all the time with it and she did so many good things after that. She's the one who created all this terracotta patterns you see around. She, in the seclusion she became extremely creative. But she was a deep person, and I think her example should be a good example for the, especially, the women of this country. It is very, very much a personality, which is respected, especially in India, very much. You know in a riot there was a statue of her, her nose - somebody had cut - and all the newspapers and everything and everyone went with the banners "who cut the nose, how dare you, how dare you do that" and they saw to it that it was put back. See, she's a woman who is adored by a country, which was under her domination, in a way. But this is what is the personality of a woman."""
    link = "https://www.amruta.org/1995/06/25/picnic-at-richmond-park-1995/"
    print(f"[手动] 使用硬编码文章数据")

# ======== 2. 中英对照翻译 === (从本地文件提取) ========
# 本地文件的内容对应关系：
# API 内容 = 原文倒数两段 (Love should be pure... 到 ...personality of a woman)
# 对应的中文是：

en_paragraphs = [
    """Love should be pure. If you have love for someone you won't see bad points of the other person, never. You will always see the good points of that person, always support that person. Sometimes I'm faced with such problems that there are people who are to be told, so I prepare myself first. Before the mirror - "I'll stand up and say like this, I'll say like this, I'll say like this". When the person comes in, half of it is lost. When I'm talking about 25% of this gets lost, whatever, 25% I have left, I tried it. It's very easy to give up that than to keep it, very easy. It is better if you practice that, I'm sure. So little, little things you can suggest to them.""",

    """Like yesterday, you know what a nice present the English Sahaja Yogis gave me, was a beautiful miniature of Royal Albert Hall. Can you imagine, beautiful. With handwork on that, beautifully done, so beautifully done. It really, it was so from the heart, because I loved this hall somehow, since long. And shows the Queen Victoria, for whom I have such tremendous respect. Like she built it in the name of her husband. This kind of thing shows such a deep reverence for her husband, love for her husband, and she remained like a widow, when he died, throughout. She didn't attend any functions, nothing. Like an Indian, we don't, the women. And she enjoyed her widowhood. She was all the time with it and she did so many good things after that. She's the one who created all this terracotta patterns you see around. She, in the seclusion she became extremely creative. But she was a deep person, and I think her example should be a good example for the, especially, the women of this country. It is very, very much a personality, which is respected, especially in India, very much. You know in a riot there was a statue of her, her nose - somebody had cut - and all the newspapers and everything and everyone went with the banners "who cut the nose, how dare you, how dare you do that" and they saw to it that it was put back. See, she's a woman who is adored by a country, which was under her domination, in a way. But this is what is the personality of a woman."""
]

zh_paragraphs = [
    """爱应当是纯粹的。如果你真心爱一个人，你就绝不会看到对方的缺点，永远不会。你只会始终看到那个人的优点，并始终支持他。有时候我会遇到这样的难题：有些话必须对某些人说清楚，于是我先做好准备。站在镜子前练习："我要站起来这样说，我要这样说，我要这样说。"可当那个人一出现，一半的勇气就消失了；等我开口说话时，又损失了其中的四分之一。不管怎样，最后只剩下四分之一的力量，我也努力尝试过了。要放弃这份爱，远比坚持它容易得多，真的非常容易。我确信，如果你能在这方面多加练习，情况会更好。你可以给他们一些小小的、细微的建议。""",

    """就像昨天那样，你们知道英国的霎哈嘉瑜伽士送给我一份多么美好的礼物——一座皇家阿尔伯特音乐厅（Royal Albert Hall）的精美微缩模型。你能想象吗？实在太美了。上面的手工雕刻做得极其精致，真是美极了。这份礼物真的发自内心，因为我长久以来一直喜爱这座音乐厅。
模型上还展现了维多利亚女王（Queen Victoria）的形象，我对她怀有极大的敬意。她以丈夫的名字建造了这座音乐厅，这种举动体现出她对丈夫多么深切的崇敬与爱意。丈夫去世后，她终身守寡，从未再参加任何社交活动，什么场合都不出席。这就像印度的女性一样——我们印度的女性不会那样做。而她却安然享受自己的寡居生活，始终沉浸其中，并在此后做了许多善事。
你们现在四处看到的那些赤陶（terracotta）图案，就是她所开创的。她在隐居中变得极具创造力。她是个内心深沉的人，我认为她的榜样尤其值得这个国家的女性效仿。
她的品格深受敬重，尤其在印度更是如此。你们知道吗？有一次暴乱中，她的雕像被人割掉了鼻子，结果所有报纸、所有人纷纷举着标语上街抗议："是谁割了她的鼻子？你怎么敢？你怎么敢做出这种事！"他们坚持要求把鼻子重新装回去。
要知道，她是一位深受爱戴的女性——而这份爱戴，竟来自一个曾经被她统治的国家。而这，才真正体现了一位女性的人格力量。"""
]

# ======== 3. 构建扁平 pairs ========
# 用简单的句级切割（按换行/句号/问号分割）
import re as _re

def split_sentences(text):
    """简单分句"""
    # 先按换行分段落
    paras = text.strip().split('\n')
    # 再按标点分句
    result = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        # 按句号、问号、感叹号分割
        sents = _re.split(r'(?<=[.?!])\s+', p)
        for s in sents:
            s = s.strip()
            if s:
                result.append(s)
    return result

def split_zh(text):
    """简单中文分句"""
    paras = text.strip().split('\n')
    result = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        sents = _re.split(r'(?<=[。？！])\s*', p)
        for s in sents:
            s = s.strip()
            if s:
                result.append(s)
    return result

# 每段内部做句级对齐（段落级：一段英文对一段中文）
pairs_flat = []
for en_para, zh_para in zip(en_paragraphs, zh_paragraphs):
    pairs_flat.append([en_para, zh_para])

print(f"[OK] 生成了 {len(pairs_flat)} 个段落对")

# ======== 4. 写入 pairs_flat.json ========
with open("/tmp/pairs_flat.json", "w", encoding="utf-8") as f:
    json.dump(pairs_flat, f, ensure_ascii=False, indent=2)
print(f"[OK] 已写入 /tmp/pairs_flat.json")

# ======== 5. 也写入段落级 pairs.json（以便后续兼容）=======
pairs_structured = []
for en_para, zh_para in zip(en_paragraphs, zh_paragraphs):
    en_sents = split_sentences(en_para)
    zh_sents = split_zh(zh_para)
    # 构造段落级结构
    sentences = []
    for s in en_sents:
        sentences.append({"en": s, "zh": ""})
    # 把中文塞给第一句（M:1 模式）
    if zh_sents and sentences:
        sentences[0]["zh"] = " ".join(zh_sents)
    pairs_structured.append({
        "sentences": sentences,
        "en_raw": en_para,
        "zh_raw": zh_para
    })

with open("/tmp/pairs.json", "w", encoding="utf-8") as f:
    json.dump(pairs_structured, f, ensure_ascii=False, indent=2)
print(f"[OK] 已写入 /tmp/pairs.json (段落级, {len(pairs_structured)}段)")

# ======== 6. 生成邮件 HTML ========
source_link = link
sahaja_link = "https://www.sahaja.live/1995-0625-picnic-with-shri-mataji-richmond-park-london-uk/"

# 构建中文标题
title_cn = "维多利亚女王"

html_parts = []
html_parts.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="font-family: 'Noto Sans SC', 'Microsoft YaHei', 'SimSun', sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; background: #fafafa;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.06);">
<tr><td style="padding:0;">
<div style="background: linear-gradient(135deg, #a8d8ea, #aa96da); padding: 30px; text-align:center;">
  <h1 style="color:#fff; margin:0 0 8px; font-size:22px; font-weight:600;">{title_en}</h1>
  <h2 style="color:rgba(255,255,255,0.85); margin:0 0 4px; font-size:16px; font-weight:400;">{title_cn}</h2>
  <p style="color:rgba(255,255,255,0.7); margin:0; font-size:13px;">{date_str}</p>
</div>
""")

# 构造正文——段落级中英对照
for idx, (en_para, zh_para) in enumerate(zip(en_paragraphs, zh_paragraphs)):
    html_parts.append(f"""
<div style="padding:20px 24px; border-bottom:1px solid #eee;">
  <div style="margin-bottom:12px;">
    <p style="color:#333; line-height:1.7; margin:0; font-size:14px;"><strong>EN</strong><br>{en_para}</p>
  </div>
  <div style="background:#f5f5f8; border-radius:8px; padding:12px 16px;">
    <p style="color:#555; line-height:1.7; margin:0; font-size:13px;"><strong>ZH</strong><br>{zh_para}</p>
  </div>
</div>
""")

# 来源链接
html_parts.append(f"""
<div style="padding:16px 24px; background:#fafafa; text-align:center;">
  <p style="color:#888; font-size:12px; margin:0 0 8px;">Source</p>
  <a href="{sahaja_link}" style="color:#666; font-size:12px; text-decoration:none;">{sahaja_link}</a>
  <br>
  <a href="{source_link}" style="color:#666; font-size:12px; text-decoration:none;">{source_link}</a>
</div>
""")

html_parts.append("""
</td></tr></table>
<p style="text-align:center; color:#aaa; font-size:11px; margin-top:16px;">Amruta Daily Push · 每日霎哈嘉文章推送</p>
</body>
</html>""")

html_content = "\n".join(html_parts)
with open("/tmp/email_body.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print(f"[OK] 已写入 /tmp/email_body.html ({len(html_content)} bytes)")

print("\n====== 验证 ======")
print(f"标题 EN: {title_en}")
print(f"标题 ZH: {title_cn}")
print(f"日期: {date_str}")
print(f"段落数: {len(en_paragraphs)}")
print(f"打开发送邮件 HTML 预览内容...")
