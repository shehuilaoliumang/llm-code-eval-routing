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
│   └── config.py            #   配置加载
├── data/
│   ├── tasks/tasks_v1.json  # 任务集（当前8题种子；完整48题阶段一构建）
│   └── results/             # 评测输出（JSONL）
├── manifests/               # 版本 manifest
├── tests/                   # 本地单元测试（17项，无需API key）
├── run_eval.py              # CLI 入口
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
```

## 评测口径（全模型完全一致，见 config/eval.yaml）

- 系统提示词统一（资深Python工程师，只输出代码）；`temperature=0.2`、`top_p=0.9`、`max_tokens=4096`、关闭思考模式
- 每题每模型运行 3 次；单次超时 30s 记失败
- 质量总分 `S_quality = 0.30×语法 + 0.40×功能(单测) + 0.20×规范 + 0.10×健壮(裁判)`
- 及格线 L1/L2=60、L3=65、L4=70
- 成本按**阶梯计价**（输入长度查档），单次成本精确到分
- 裁判默认 `deepseek-v4-flash` 全量 + `deepseek-v4-pro` 10% 交叉验证（成本控制默认启用）

## 数据 schema（附录B）

每次生成一条 JSONL 记录：`task_id / difficulty / platform / model / model_version(快照) / run /
syntax_score / functional_score / style_score / robustness_score / quality_total / passed /
input_tokens / output_tokens / input_tier / cost_yuan / latency_seconds / code / test_details`。

## 当前状态

- [x] 工程骨架 + 双平台客户端 + 自动判分 + 沙箱 + 裁判 + manifest（17项本地测试通过）
- [x] 8 题种子任务集（参考实现全部通过各自测试，回归保护）
- [ ] 控制台核实 3 项（turbo/seed-code 状态、evolving/lite/v4.1-flash 价格、qwen3-coder-plus 价格限流）
- [ ] 完整 48 题测试集（公开基准改编为主）
- [ ] key 到位后试跑 → 决策门 → 全量评测
