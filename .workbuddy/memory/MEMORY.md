# 项目长期笔记 — LLM代码生成能力评估与智能路由研究

## 目标
量化评估火山方舟 + 阿里云百炼 8 款模型的代码生成能力，建立「任务难度 → 模型档位 → 性价比」映射，产出智能路由方案。

## 硬性约定（必须遵守）
1. **任何花钱的运行必须先经用户确认**：评测、裁判、测试集构建等一切产生真实 API 成本的操作，启动前必须先得到用户明确同意；未经确认不得自行启动。免费/本地操作（单元测试、干跑、读文件、生成静态 HTML）无需确认。
2. **密钥安全**：API Key 只放 `.env.local`（`.gitignore` 拦截），严禁硬编码、提交 git、写入日志或外泄到聊天。
3. **方舟模型 ID 用 models.list 原文**（连字符格式，如 `doubao-seed-2-1-pro-260915`），禁止手工转录成点号格式（会报 NotFound）。

## 预算现状（2026-10-17）
- 火山方舟 50 元 · 阿里云百炼 20 元 · DeepSeek 官方 10 元（合计约 80 元）

## 裁判口径（2026-10-17 定）
- 默认全量裁判走 **DeepSeek 官方 API**（`deepseek-v4.1-flash-official` = 官方模型名 `deepseek-flash`）
- 10% 交叉验证：官方 `deepseek-v4-pro-official` 优先 + 方舟托管 `deepseek-v4-pro` 作一致性参照

## 关键实测结论
- 双平台模型默认开启思考链，必须显式关闭（方舟 `thinking:{type:disabled}` / 百炼 `chat_template_kwargs.enable_thinking:false`），否则 max_tokens 被无视、输出膨胀 3~10 倍。
- 48 题测试集已定稿：L1~L4 各 12 题、258 用例、入口名全局唯一、dev/holdout 各 24。
- 评测执行器支持受控并发（`run_eval.py --workers`，默认 6）。

## 交付物位置
- 任务集：`data/tasks/tasks_v2.json`
- 结果：`data/results/results_*.jsonl`（gitignore 拦截）
- 仪表盘（数据版）：`report/dashboard.html`
- 路由方法展示页（先验版）：`report/routing-model.html`
- 计划书：`LLM代码生成能力评估与智能路由研究 项目计划书.md`（唯一主文档）
