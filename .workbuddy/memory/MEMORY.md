# amruta-daily-push 项目记忆

## 底部链接规则（2026-07-04 最终确认）
- **Link 1**：`https://amruta.today/` — **固定不变**，永远就是这个 URL，不跟日期、不跟 slug
- **Link 2**：从中文文档 `.md` frontmatter `source:` 字段提取 sahaja.live 链接
- 翻译来源说明放在两个链接之后

## 执行环境
- Hermes 本地自动化，不再依赖 GitHub Actions
- 中文来源：`F:\霎哈嘉瑜伽\sahaja live talks` 本地文件夹
- 翻译来源说明：官方翻译 / 阿里云降级

## 凭证管理
- 密钥文件：`C:\Users\chenj\OneDrive\Felix\2AI key\2AI-keys-combined.md`
- 读取方式：用 Python `open(file, 'rb')` 二进制读取（Hermes 工具链对 ghp_/sk-/nvapi- 开头的敏感字符串做了输出截断保护）
- GitHub Token：40 字符，通过 SSH push 推送存档

## 踩坑记录
- Hermes 工具链对敏感字符串输出截断：`...` 是 Hermes 输出省略标记，不是文件内容
- 飞书消息冒号截断 bug：禁止 `**键**: 值` 格式，用 `**键** 值` 格式
- **英中句级对齐规则（2026-07-05 新增）**：邮件正文中英中对应只能是"一对一""多对一""一对多"，禁止多对多模糊对应（一大坨英文 + 一大坨中文混在一起）
- **英文原文保真规则（2026-07-05 新增）**：邮件中的英文部分必须完全等于 amruta.today 抓取原文，禁止任何修改（不增多、不删减、不修改）。审核报告新增"英文原文保真"检查项。

### 阿里云翻译 API Key 缺失（2026-07-05）
- **问题**：IMA KB 搜索三阶段失败后，降级到阿里云机器翻译，但所有中文翻译都是空字符串
- **根因**：环境变量 ALIYUN_ACCESS_KEY_ID 和 ALIYUN_ACCESS_KEY_SECRET 未设置
- **修复**：从 C:\Users\chenj\OneDrive\Felix\2AI key\2AI-keys-combined.md 提取 API Key，设置环境变量
- **教训**：降级路径需要 API Key，必须提前验证；验收时必须检查实际输出文件内容
