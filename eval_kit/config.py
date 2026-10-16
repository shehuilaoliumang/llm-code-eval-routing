"""配置加载：models.yaml（模型档案数据层）与 eval.yaml（评测口径层）。"""

import yaml


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ModelRegistry:
    """模型档案访问器。"""

    def __init__(self, models_cfg):
        self.cfg = models_cfg
        self.platforms = models_cfg["platforms"]
        self.models = models_cfg["models"]

    def get(self, model_id):
        if model_id not in self.models:
            raise KeyError(f"模型不在档案中: {model_id}（可选: {list(self.models)}）")
        return self.models[model_id]

    def platform_of(self, model_id):
        return self.get(model_id)["platform"]

    def platform_cfg(self, platform):
        return self.platforms[platform]

    def candidates(self):
        return [m for m, c in self.models.items() if c.get("role") == "candidate"]

    def by_role(self, role):
        return [m for m, c in self.models.items() if c.get("role") == role]

    def judge_model(self):
        roles = self.by_role("judge_default")
        return roles[0] if roles else self.by_role("judge")[0]

    def cross_check_model(self):
        roles = self.by_role("judge")
        return roles[0] if roles else None


class EvalConfig:
    """评测口径访问器。"""

    def __init__(self, eval_cfg):
        self.cfg = eval_cfg
        self.generation = eval_cfg["generation"]
        self.judge = eval_cfg["judge"]
        self.scoring = eval_cfg["scoring"]
        self.retry = eval_cfg["retry"]
        self.system_prompt = eval_cfg["system_prompt"]

    def pass_line(self, difficulty):
        return self.scoring["pass_line"][difficulty]
