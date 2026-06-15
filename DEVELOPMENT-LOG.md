# amruta-actions 开发日志

记录项目关键开发节点、决策过程和踩坑经验。

---

## 2026-06-11：首次搭建 GitHub Actions 自动化

### 背景
之前 6月6日做的 `push_article.js` 是本地推送脚本，每次需要手动运行。6月11日正式搬到 GitHub Actions 实现全自动流水线。

### 创建仓库与部署
- 创建 public 仓库 `wherejiahe-bot/amruta-actions`
- 上传文件：`scripts/` 目录含 step1~step4 脚本、`coordinator.py`、`step2.py`
- 配置 `daily-push.yml` workflow，cron: `0 20 * * *`（UTC 20:00 = 北京时间 04:00）
- 配置 GitHub Secrets：`AMRUTA_GITHUB_TOKEN`, `SMTP_USER`, `SMTP_PASS`, `SAHAJA_EMAIL`, `SAHAJA_PASSWORD`, `IMA_CLIENT_ID`, `IMA_API_KEY`, `IMA_KB_ID`

### 四段式 Workflow
1. **step1_fetch** — 从 amruta.today 抓取英文摘录
2. **step2_translate** — IMA 知识库搜索中文对照 + 句级对齐 + 审核修正
3. **step3_push** — 生成 HTML 推送到 amruta-daily-archive
4. **step4_email** — 通过 QQ 邮箱发送中英对照邮件

### 首次排错（14:00-14:17）
- coordinator.py 有 3 个 `def run()` 会互相覆盖，不适合直接运行
- 改用 workflow 内联脚本替代
- 本地 skill `amruta-daily-push` 的 `push_article.js` 同步更新

### IMA API 集成
- 使用 `ima_openapi_client`（Python）搜索 sahaja.live 中文翻译
- 找到 IMA KB "sahaj"，搜索 sahaja.live talk 获取中英对照
- 中文文档作为官方翻译源，英文来自 amruta.today

### 全流程跑通
- ✅ 完整流程跑通：fetch → 搜索中文 → 对齐 → push 8对双语到 GitHub → 发邮件
- ✅ 验证：amruta-daily-archive 已有 2026-06-11.html，含中英文、标题、单词本功能

### 排错笔记（14:00后）
- GitHub Actions cron 从未成功触发（历史遗留问题）
- 依赖手动运行 workflow 测试
- 计划结合本地 LLM 增强自动化智能

---

## 2026-06-12：句级对齐算法重构（14次迭代）

### 目标
修复 amruta-daily-push 的中英文句级对齐问题，确保中文翻译全部来自 IMA 知识库官方翻译。

### 迭代历程（早上 7 点 ~ 凌晨 2 点）

| 迭代 | 方案 | 结果 |
|------|------|------|
| 1 | 比例切割 + 标点边界 | 锚定偏移，中文切到元信息 |
| 2 | 阿里云桥接 IMA（阈值匹配） | 阈值太低，元信息污染 |
| 3 | 匈牙利算法 | 19句全有中文，但配对不够精确 |
| 4 | 顺序贪婪合并 | 中文不够分，后面8句空白 |
| 5 | 贪婪合并 + 允许下降 0.05 | 效果不佳 |
| 6 | 双模型对比 | 每句只拿1个子句，中文不够 |
| 7 | Qwen API | API 401/返回空 |
| 8 | 退回匈牙利 | 稳定但不够精确 |
| 9 | 阿里云模板 + 顺序贴 | run failed（代码缺失） |
| 10 | 阿里云直接翻译 | 最简方案，先确保能跑通 |
| 11 | BGE + 阿里云桥接 | 19句全有中文，质量高，但部分句用了阿里云翻译 |
| 12 | BGE找头 + 顺序贴（IMA only） | 最终方案，中文全部来自 IMA |

### 最终方案（第14次）
- **模型**：BAAI/bge-small-zh-v1.5（33MB，中文优化）
- **流程**：段落锚定 → IMA中文按句号切分（不按逗号）→ BGE 英-中匹配 → >=0.4 用 IMA，<0.4 用阿里云
- **最小长度**：>=2 个字（不再过滤6字句子）
- **标题**：阿里云翻译 title_en
- **日期**：date_str（YYYY-MM-DD）
- **底部链接**：sahaja_link 优先
- **后处理**：修正"左翼还是右翼"→"偏左或偏右"

### 推送到 GitHub Actions（23:40）
- 将最终方案推送到 `wherejiahe-bot/amruta-actions`
- **step2_translate.py 更新**：
  - `do_alignment_and_audit()`：IMA中文按句号切分
  - BGE 阈值：0.3 → 0.4
  - 最小中文长度：4字 → 2字
- **两阶段 IMA 搜索**（主人要求）：
  - Phase 1：以 `日期 + 标题[:60]` 搜索
  - Phase 2：Phase 1 为空时，用 `正文内容[:200]` 重搜
- **workflow 依赖**：去掉 `scipy`（最终方案只用 numpy）

### 00:06 — 第一次调试
- IMA 返回 0 结果（1978 年 talk 不在 IMA 库里）

### 00:17 — 第二次调试
- 同样 0 结果（Phase 1 body-first-sentence 策略）

### 00:27 — 最终搜索方案
- Phase 1 改为按 `date_str` 搜索（如 `1978-06-12`）
- 主人确认方案，已触发 workflow 测试

### 00:41 — IMA 知识库配置大修（5个根因全部修复）
- 主人提供了新凭据（Client ID + API Key），旧凭据已过期
- 通过 `search_knowledge_base` 找到正确 KB：**sahaj**（8166文件，创建者：长庚）
- **修复列表**：
  1. ✅ 凭据过期 → 更新 GitHub Secrets
  2. ✅ KB_ID 错误（旧 `XbbHh...` → 新 `sEgPPE...`）
  3. ✅ 参数名错误（`kb_id` → `knowledge_base_id`）
  4. ✅ 返回字段错误（`documents` → `info_list`）
  5. ✅ 媒体 ID 字段（`kb_file_id` → `media_id`）
- 触发最新 workflow 等待验证

### 02:25 — IMA 中文文档成功用于邮件
- BGE 对齐完成：13句英文 → 13句中文（全部匹配上）
- 底部链接原为 COS 下载链接，已修复为 amruta.today 链接兜底
- 创建 `api-integration-debug` skill 沉淀调试经验

---

## 关键经验沉淀

### 1. IMA API 调用规范
- Header 名：`ima-openapi-clientid` 和 `ima-openapi-apikey`
- 搜索参数：`knowledge_base_id`（不是 `kb_id`）
- 返回字段：`data.info_list`（不是 `data.documents`）
- 媒体 ID：`media_id`（不是 `kb_file_id`）
- 获取文件：`get_media_info` 返回 url + headers → 下载
- 文件内容 `\r\n`（CRLF）换行符，需先 `replace('\r\n', '\n')` 再解析

### 2. BGE 对齐阈值
- 阈值 0.4 是精度和召回率的平衡点
- 低于 0.4 的用阿里云翻译兜底
- 按句号切分（不按逗号）避免子句碎片化

### 3. 凭据管理
- IMA 凭据会过期，需定期检查
- 首次使用时应验证凭据有效性（先跑一次 `search_knowledge_base` 测试）

---

_最后更新：2026-06-15 00:00_\n\n---\n\n# 今日 amruta 每日推送 对话记录 (2026-06-16)\n### amruta-fix-loop 技能更新（2026-06-16）
- 在 SKILL.md 中加入循环检查 6 月 15 日至 12 日的验证逻辑。
- 新增伪代码描述：在每次 workflow 成功后向前检查前一天，直到 6 月 12 日全部通过后自动暂停 automation（status->PAUSED）。
- 为后续实现提供实现思路和 pause_automation

---

# 今日 amruta 每日推送 对话记录 (2026-06-16)
### amruta-fix-loop 技能更新（2026-06-16）
- 在 SKILL.md 中加入循环检查 6 月 15 日至 12 日的验证逻辑。
- 新增伪代码描述：在每次 workflow 成功后向前检查前一天，直到 6 月 12 日全部通过后自动暂停 automation（status->PAUSED）。
- 为后续实现提供实现思路和 pause_automation


---

## amruta-fix-loop 修复 (2026-06-15 20:43 UTC)

### 发现
- 6-14, 6-15, 6-16 三篇文章中文标题缺失
- 6-12, 6-13 正常（通过 pairs 匹配获得中文标题）

### 根因（两个 Bug）
1. polish_title 空函数返回 None — translate_title_with_word_map 永远返回 None
2. 标题翻译优先级不合理 — 阿里云应作为主要手段

### 修复
1. step2_translate.py commit 37a7437:
   - polish_title 改为 return zh
   - 标题翻译: 阿里云优先 -> pairs -> 词表
2. 手动修复3篇 missing titles:
   - 6-14 关照真我 / 6-15 犹在思虑的梦境中 / 6-16 领受应许之美
   - 同步 articles.json + daily HTML + index.html

### 已知问题
- 阿里云标题翻译在 GH Actions 不稳定（超时）
- DeepSeek API Key 已失效

---

## amruta-fix-loop 自动检查 (2026-06-16 07:15 UTC)

### 状态
- 最新 workflow run#27579272407: **success** ✅
- 同上次检查（05:44），无新 run

### 健康检查
- articles.json 最近5篇标题全部有中文翻译 ✅
  - 6-12: 理性的理由 / 6-13: 通过测试创造价值 / 6-14: 关照真我 / 6-15: 犹在思虑的梦境中 / 6-16: 接受承诺的美丽
- daily HTML 页面标题正常 ✅
  - 6-16.html: 接受承诺的美丽
- 无新失败，无操作需要

### 已知问题（延续）
- 阿里云标题翻译质量一般（6-16: "接受承诺的美丽" vs 人工"领受应许之美"）
- DeepSeek API Key 已失效
