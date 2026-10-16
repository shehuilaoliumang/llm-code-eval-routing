"""模型输出代码提取：处理 markdown 代码围栏与裸代码两种情况。"""

import re

_FENCE_RE = re.compile(r"```(?:python|py|Python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text):
    """从模型输出中提取代码。

    优先取第一个代码围栏块；无围栏时若整体形似代码则取全文。
    """
    if not text:
        return ""
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    if any(kw in stripped for kw in ("def ", "import ", "class ", "print(")):
        return stripped
    return stripped
