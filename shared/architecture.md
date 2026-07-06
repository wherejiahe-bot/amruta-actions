# amruta-daily-push 架构方案

## 数据流
```
amruta.today API → step1_fetch.py → article_raw.json
    ↓
sahaja live talks (F:\霎哈嘉瑜伽\sahaja live talks) → step2_translate.py
    ↓
句级对齐 → pairs.json + email_body.html
    ↓
step3_push.py → 本地 HTML 存档
    ↓
step4_email.py → QQ 邮箱 SMTP 发送
    ↓
审核报告 → 飞书交付
```

## 模块说明

### Step 1: Fetch (`step1_fetch.py`)
- 从 amruta.today WordPress API 抓取当日英文文章
- 输入：日期（UTC+8）
- 输出：`article_raw.json`（date/title/content/link）

### Step 2: Translate (`step2_translate.py`)
- 搜索 `F:\\霎哈嘉瑜伽\\sahaja live talks` 目录找官方中文翻译
- 支持三种文档格式：interleaved（交替）、inline（同行）、separated（分离）
- 句级对齐：用 Agnes AI 大模型对齐英文句和中文句
- **英中句级对齐规则**：每对英中关系只能是以下三种之一：
  - 一对一（一句英文 ↔ 一句中文）
  - 多对一（几句英文 → 一句中文）
  - 一对多（一句英文 → 几句中文）
  - 禁止多对多模糊对应（一大坨英文 + 一大坨中文混在一起）
- **英文原文保真规则**：邮件中的英文部分必须**完全等于**从 amruta.today 抓取的原文，禁止任何修改：
  - 不增多 — 不能添加原文没有的英文内容（包括 LLM 扩写、重复段落、多余句子）
  - 不删减 — 不能删除原文的任何部分
  - 不修改 — 不能修改原文的任何一个字、标点、换行
- 降级：sahaja live talks 无翻译时回退阿里云机器翻译
- 输出：`pairs.json`（中英对齐对）+ `email_body.html`

### Step 3: Push (`step3_push.py`)
- 生成本地 HTML 存档
- 更新 `amruta-daily-archive-clone/daily/YYYY-MM-DD.html`
- 更新 `index.html` 文章列表

### Step 4: Email (`step4_email.py`)
- 通过 QQ SMTP 发送中英对照邮件
- 邮件底部：两个链接 + 翻译来源说明 + 审核报告表格

### Step 3.5: Audit (`step3_5_audit_email.py`)
- 审核 pipeline 输出质量
- 检查翻译来源、段落匹配、链接顺序
- 输出审核报告到 `/tmp/audit_report.md`

## 本地执行
```bash
cd G:\Workspace\amruta-daily-push\amruta-actions-clone
python3 scripts/run_workflow.py --step fetch --date YYYY-MM-DD
python3 scripts/run_workflow.py --step translate
python3 scripts/run_workflow.py --step push
python3 scripts/run_workflow.py --step email
# 完整 pipeline
python3 scripts/run_workflow.py
```

## 编排方式
- **强制**：执行本项目必须先加载 `multi-agent-team` skill（`skill_view(name='multi-agent-team')`）
- 由 multi-agent-team skill 在 Hermes 本地编排
- Manager → Analyst → Executor → QA 角色链
- 每步产出先给主人确认 → 再进下一步
- 审核报告通过飞书直接可见

## 关键配置
| 配置项 | 值 |
|--------|------|
| 中文来源 | `F:\霎哈嘉瑜伽\sahaja live talks` |
| LLM 模型 | agnes-2.0-flash（API Hub） |
| 机器翻译 | 阿里云（降级） |
| 邮件发送 | QQ SMTP |
| 存档路径 | `amruta-daily-archive-clone/daily/` |
| 凭证文件 | `C:\Users\chenj\OneDrive\Felix\2AI key\2AI-keys-combined.md` |
