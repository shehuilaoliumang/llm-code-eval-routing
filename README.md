# LLM代码生成能力评估与智能路由研究 —— 评测工程

基于《项目计划书》（唯一主文档，见仓库根目录）搭建的**可复现评测套件**。
双平台（火山方舟 / 阿里云百炼）统一接入 · 自动化判分 · 全量数据留存 · 版本 manifest。

## 目录结构

```
├── LLM代码生成能力评估与智能路由研究 项目计划书.md   # 唯一主文档（所有决策记录）
├── config/
│   ├── models.yaml          # 模型档案（数据层，与路由 Skill 同步，可替换）
│   └── eval.yaml            # 评测口径（参数/提示词/及格线，全模型一致）
├── eval_kit/                # 评测套件包
│   ├── clients.py           #   双平台统一客户端（OpenAI兼容+指数退避重试）
│   ├── pricing.py           #   阶梯计价成本计算
│   ├── sandbox.py           #   沙箱执行（子进程+超时，Windows兼容）
│   ├── scoring.py           #   语法检查+单元测试+质量总分合成
│   ├── judge.py             #   LLM-as-Judge 裁判（附录A Prompt）
│   ├── code_extract.py      #   模型输出代码提取（围栏/裸代码）
│   ├── recorder.py          #   JSONL 全量记录（附录B schema）
│   ├── manifest.py          #   可复现 manifest（快照/提示词哈希/参数）
│   ├── runner.py            #   评测执行器
│   ├── dashboard.py         #   可视化仪表盘生成器
│   └── config.py            #   配置加载
├── data/
│   ├── tasks/tasks_v1.json  # 任务集（当前8题种子；完整48题阶段一构建）
│   └── results/             # 评测输出（JSONL，gitignore 拦截）
├── manifests/               # 版本 manifest
├── assets/chart.umd.min.js  # 图表库（本地化，仪表盘离线可用）
├── report/                  # 仪表盘产物（dashboard.html）
├── tests/                   # 本地单元测试（19项，无需API key）
├── run_eval.py              # 评测 CLI 入口
├── make_dashboard.py        # 仪表盘 CLI 入口
├── check_volcengine.py      # 方舟 Key/模型可用性核实脚本
├── check_aliyun.py          # 百炼 Key/模型可用性核实脚本
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

# 3. 本地自检（无需 key）
python -m unittest discover -s tests -v

# 4. 干跑（MockClient，验证全链路）
python run_eval.py --dry-run --limit 2 --no-judge

# 5. 试跑（第1笔预算 ~2元：每模型5题×1次 + 确认免费额度 + 校准token假设）
python run_eval.py --limit 5 --runs 1 --tag pilot

# 6. 全量评测（1152次生成 + 裁判）
python run_eval.py --tag v1

# 7. 生成/更新 manifest
python run_eval.py --manifest-only --tag v1

# 8. 生成可视化仪表盘（自包含 HTML，双击浏览器打开，无需服务器/联网）
python make_dashboard.py                    # 汇总全部结果 → report/dashboard.html
python make_dashboard.py --tag v1           # 只汇总指定 tag
```

## 可视化窗口（最终产品形态）

评测结果不只在终端看——`make_dashboard.py` 生成**自包含单文件 HTML 仪表盘**（数据与图表库全部内联，223KB，`file://` 直接打开）：

- **汇总卡片**：记录数 / 模型数 / 题目数 / 总名义成本 / 平均综合分
- **分难度综合质量分**（分组柱状图，全模型对比）
- **成本-质量散点图**（性价比全景，越靠左上越优——路由决策的直接依据）
- **单元测试通过率 / 平均耗时**（客观指标与时延维度）
- **裁判一致性**（默认裁判 vs 交叉验证的评分差异）
- **模型汇总表 / 分难度达标率热力表 / 明细记录**（含阶梯计价成本）
- 浅色主题、中文界面；后续可经「发布为应用」转为在线链接分享

## 密钥安全规范（重要）

- API Key **只放 `.env.local`**（密钥文件；`.gitignore` 的 `.env.*` 规则拦截；代码与脚本一律从环境变量读取。注：历史 `.env` 因 ACL 修复事故已锁死为不可读，属安全正收益，项目结束统一轮换 Key）
- git 全历史已扫描确认无 Key 泄露（`git log --all -p | grep` 双 Key 零命中）；提交前可用同样命令复查
- **切勿**把 Key 写进代码、提交到 git、或粘贴到聊天/截图；项目结束后建议在两家控制台轮换
- `.env.example` 仅为占位模板；DeepSeek 官方 Key 通道已预置（`DEEPSEEK_API_KEY`，提供后在 `config/models.yaml` 启用）

## 评测口径（全模型完全一致，见 config/eval.yaml）

- 系统提示词统一（资深Python工程师，只输出代码）；`temperature=0.2`、`top_p=0.9`、`max_tokens=4096`、关闭思考模式
- 每题每模型运行 3 次；单次超时 30s 记失败
- 质量总分 `S_quality = 0.30×语法 + 0.40×功能(单测) + 0.20×规范 + 0.10×健壮(裁判)`
- 及格线 L1/L2=60、L3=65、L4=70
- 成本按**阶梯计价**（输入长度查档），单次成本精确到分
- 裁判默认 `deepseek-v4-1-flash` 全量 + `deepseek-v4-pro-ga` 10% 交叉验证（成本控制默认启用）
- **思考链必须显式关闭**（2026-10-17 实测）：双平台默认开启，不关时 `max_tokens` 被无视、输出膨胀 3~10 倍。方舟传 `thinking:{"type":"disabled"}`，百炼传 `chat_template_kwargs.enable_thinking=false`（配置在各模型的 `disable_thinking_body` 字段）

## 数据 schema（附录B）

每次生成两条 JSONL 记录：`generation`（生成+自动判分）与 `scored`（+裁判分+综合分+是否及格）。
字段：`task_id / difficulty / platform / model / model_version(快照) / run / syntax_score /
functional_score / style_score / robustness_score / quality_total / passed / input_tokens /
output_tokens / input_tier / cost_yuan / latency_seconds / code / test_details`。

## 当前状态

- [x] 工程骨架 + 双平台客户端 + 自动判分 + 沙箱 + 裁判 + manifest（19项本地测试通过）
- [x] 8 题种子任务集（参考实现全部通过各自测试，回归保护）
- [x] **双平台 Key 验证 + 控制台核实完成（2026-10-17）**：7 款模型实测可调用、价格全部经官方来源核实、模型矩阵定稿（方舟旗舰 `doubao-seed-2.1-pro-260915` 待控制台开通）
- [x] **第 1 笔试跑完成（67 次真实 API 调用，生成侧名义成本 0.15 元）**：全链路（调用→提取→沙箱→判分→裁判→记录）验证通过；裁判链路（v4.1-flash 全评 + v4-pro 抽验）正常
- [x] **方舟旗舰确认可调用**（2026-10-17：此前 404 系点号/连字符 ID 转录错误，正确 ID 为 `doubao-seed-2-1-pro-260915`；候选模型升至 8 款）
- [x] DeepSeek 官方通道启用（三裁判链路：v4.1-flash 全评 + 方舟 v4-pro + 官方 v4-pro 双交叉验证，冒烟通过）
- [ ] 完整 48 题测试集（LLM 辅助构建中：DeepSeek-V4-Pro 编辑 + 三道质量门）
- [ ] 第 2 笔释放：全量评测（48题 × 8模型 × 3次，预计约 12 元）
