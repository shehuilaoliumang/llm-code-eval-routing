# LLM代码生成能力评估与智能路由研究 —— 评测工程

基于《项目计划书》（唯一主文档，见仓库根目录）搭建的**可复现评测套件**。
双平台（火山方舟 / 阿里云百炼）统一接入 · 自动化判分 · 全量数据留存 · 版本 manifest。
研究结论见《研究报告.md》；路由决策系统见 `.workbuddy/skills/code-task-router/`。

## 目录结构

```
├── LLM代码生成能力评估与智能路由研究 项目计划书.md   # 唯一主文档（所有决策记录）
├── 研究报告.md             # 完整方法论 + 结论 + 复现指南（本研究的最终成果）
├── config/
│   ├── models.yaml          # 模型档案（数据层，与路由 Skill 同步，可替换）
│   └── eval.yaml            # 评测口径（参数/提示词/权重/及格线，全模型一致）
├── eval_kit/                # 评测套件包
│   ├── clients.py           #   双平台统一客户端（OpenAI兼容+指数退避重试）
│   ├── pricing.py           #   阶梯计价成本计算
│   ├── sandbox.py           #   沙箱执行（子进程+超时，Windows兼容）
│   ├── scoring.py           #   语法检查+单元测试+质量总分合成
│   ├── judge.py             #   LLM-as-Judge 裁判
│   ├── code_extract.py      #   模型输出代码提取（围栏/裸代码）
│   ├── recorder.py          #   JSONL 全量记录
│   ├── manifest.py          #   可复现 manifest（快照/提示词哈希/参数）
│   ├── runner.py            #   评测执行器（受控并发 --workers）
│   ├── dashboard.py         #   可视化仪表盘生成器
│   └── config.py            #   配置加载
├── data/
│   ├── tasks/tasks_v1.json  # 8题种子集（回归保护用）
│   ├── tasks/tasks_v2.json  # 48题正式任务集（区分度不足，已被 v3 取代）
│   ├── tasks/tasks_v3.json  # 48题升级任务集（区分度达标，当前默认）
│   └── results/             # 评测输出（JSONL，gitignore 拦截）
├── manifests/               # 版本 manifest
├── assets/chart.umd.min.js  # 图表库（本地化，仪表盘离线可用）
├── report/                  # 产物：dashboard.html（数据仪表盘）、routing-model.html（方法论展示）
├── tests/                   # 本地单元测试（21项，无需API key）
├── build_tasks.py           # 48题构建器（LLM 编辑 + 三道质量门）
├── fill_tasks.py            # 补齐缺失题（人工编辑通道，共用同一套质量门）
├── revise_tasks.py          # 质量审计后的修正（去重/去退化/消重名）
├── upgrade_tasks.py         # L1 题目升级（v2→v3 第一步）
├── upgrade23.py             # L2/L3 题目升级
├── upgrade_l4.py            # L4 题目升级
├── run_eval.py              # 评测 CLI 入口
├── make_dashboard.py        # 仪表盘 CLI 入口
├── replay_route.py          # 离线回放实验（E1~E3 + M1~M7 指标 + 敏感性分析，零成本）
├── router_agent.py          # 多模型路由原型（母/子 Agent 运行时，复用 eval_kit）
├── check_volcengine.py      # 方舟 Key/模型可用性核实脚本
├── check_aliyun.py          # 百炼 Key/模型可用性核实脚本
├── tools/verify_dashboard.js # 仪表盘渲染 JS 回归验证（Node 执行）
├── .env.example             # API Key 环境变量模板
└── requirements.txt
```

## 快速开始

```bash
# 1. 安装依赖（已装入受管 venv；全新环境：pip install -r requirements.txt）
pip install -r requirements.txt

# 2. 配置 API Key（环境变量，切勿硬编码/提交git）
export VOLCENGINE_API_KEY=...    # 火山方舟
export DASHSCOPE_API_KEY=...     # 阿里云百炼
export DEEPSEEK_API_KEY=...      # DeepSeek 官方（裁判用）

# 3. 本地自检（无需 key）
python -m unittest discover -s tests -v

# 4. 干跑（MockClient，验证全链路）
python run_eval.py --dry-run --limit 2 --no-judge

# 5. 全量评测（48题 × 8模型 × 3次，默认 tasks_v3.json）
python run_eval.py --tag v3 --workers 6

# 6. 生成/更新 manifest
python run_eval.py --manifest-only --tag v3 --tasks data/tasks/tasks_v3.json

# 7. 生成可视化仪表盘（自包含 HTML，双击浏览器打开，无需服务器/联网）
python make_dashboard.py --tag v3
```

## 可视化窗口（最终产品形态）

评测结果不只在终端看——`make_dashboard.py` 生成**自包含单文件 HTML 仪表盘**（数据与图表库全部内联，`file://` 直接打开）：

- **汇总卡片**：记录数 / 模型数 / 题目数 / 总成本 / 平均综合分
- **分难度综合质量分**（分组柱状图，全模型对比）
- **成本-质量散点图**（性价比全景，越靠左上越优——路由决策的直接依据）
- **单元测试通过率 / 平均耗时**（客观指标与时延维度）
- **裁判一致性**（默认裁判 vs 交叉验证的评分差异）
- **模型汇总表 / 分难度达标率热力表 / 明细记录**（全量 1152 条，支持按难度/题型/模型/平台/划分筛选 + 17 维排序）
- 浅色主题、中文界面、响应式；`report/routing-model.html` 为配套的方法论展示页

## 密钥安全规范（重要）

- API Key **只放 `.env.local`**（密钥文件；`.gitignore` 的 `.env.*` 规则拦截；代码与脚本一律从环境变量读取）
- git 全历史已扫描确认无 Key 泄露；提交前可用 `git log --all -p | grep` 复查
- **切勿**把 Key 写进代码、提交到 git、或粘贴到聊天/截图；项目结束后建议在控制台轮换
- `.env.example` 仅为占位模板

## 评测口径（全模型完全一致，见 config/eval.yaml）

- 系统提示词统一（资深Python工程师，只输出代码）；`temperature=0.2`、`top_p=0.9`、`max_tokens=4096`、关闭思考模式
- 每题每模型运行 3 次；单次超时 30s 记失败
- 质量总分 `S_quality = 0.10×语法 + 0.45×功能(单测) + 0.20×规范 + 0.25×健壮(裁判)`
- 及格线 L1~L4 统一 = **85**（对齐实测质量分布的自然断裂点）
- 成本按**阶梯计价**（输入长度查档），单次成本精确到分
- 裁判默认 **DeepSeek 官方 `deepseek-v4-pro`** 全量 + 方舟托管 `deepseek-v4-pro-ga` 10% 交叉验证
- **思考链必须显式关闭**（2026-10-17 实测）：双平台默认开启，不关时 `max_tokens` 被无视、输出膨胀 3~10 倍。方舟传 `thinking:{"type":"disabled"}`，百炼传 `chat_template_kwargs.enable_thinking=false`

## 数据 schema

每次生成两条 JSONL 记录：`generation`（生成+自动判分）与 `scored`（+裁判分+综合分+是否及格）。
字段：`task_id / difficulty / platform / model / model_version(快照) / run / syntax_score /
functional_score / style_score / robustness_score / quality_total / passed / input_tokens /
output_tokens / input_tier / cost_yuan / latency_seconds / code / test_details`。

## 当前状态

- [x] 工程骨架 + 双平台客户端 + 自动判分 + 沙箱 + 裁判 + manifest（21项本地测试通过）
- [x] 8 题种子任务集（参考实现全部通过各自测试，回归保护）
- [x] **双平台 Key 验证 + 控制台核实完成**：8 款候选模型定稿、价格经官方来源核实
- [x] **第 1 笔试跑完成**：全链路验证通过；裁判三链路冒烟一致
- [x] **48 题测试集 v1 定稿**（L1~L4 各 12 题，258 用例，48/48 过质量门）
- [x] **全量评测 v2 完成**（1152 次）：发现质量维度区分度不足（全量功能分 std=5.94）
- [x] **评测口径升级 v1.2**：裁判 Flash→Pro + 权重重设（syntax 降权、robustness 升权）+ 题目升级
- [x] **48 题升级 v3**（38 题重写 + 10 题保留）：引入性能约束/密集边界/非平凡算法，48/48 过门
- [x] **全量评测 v3 完成**（1152 生成 + 1152 裁判，0 错误）：区分度恢复（std 5.94→15.03，L4=21.72）
- [x] **及格线校准至 85**：拦住 L4 掉队的 coder-flash（78），保留功能正确的便宜模型
- [x] **核心结论产出**：L1~L3 首选 `qwen3.7-flash`（性价比碾压），L4 需旗舰兜底；分级路由比全程旗舰省约 71%
- [x] 路由 Skill 数据层升级为实测版 + 研究报告撰写完成
- [x] **路由验证与假设检验**：离线回放实验（E1~E3）+ M1~M7 指标 + H1~H5 假设验证 + 敏感性分析（`replay_route.py`，零成本；结论：实测规则省 53%~62%、非劣效成立、H2/H3/H5 被证伪）
- [x] **路由原型**：`router_agent.py`（母/子 Agent 运行时，复用 eval_kit，干跑通过；真实运行需 API 确认）

## 许可证

本项目采用 [MIT License](LICENSE)。你可以自由使用、修改、分发，但需保留版权声明。

> 注：`data/tasks/` 下的测试集与 `data/results/` 下的评测原始数据随代码一并开源，便于复现研究结论；API Key 等敏感信息仅存于本地 `.env.local`，未纳入仓库。
