# -*- coding: utf-8 -*-
"""
LLM 输出文本规范化工具
======================
解决 DeepSeek 等 LLM 生成结论时常见的格式问题：
  - 多层编号（"1.1. 步骤" / "1.1、步骤"） -> 自动转为单层连续编号或纯文本
  - 重复标点（"。。"、"..."）
  - Markdown 粗体残留（**xxx**）
统一展示格式，同时避免把带多层编号的文本沉淀进知识库。
"""
import re

_ANY_NUM_RE = re.compile(
    r"^\s*\d{1,2}(?:\.\d{1,2})?(?:[\.、)）]\s*|\s+)(.+)$", re.MULTILINE)
_HIER_NUM_RE = re.compile(
    r"^\s*\d{1,2}\.\d{1,2}[\.、)）]?\s*(.+)$", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _collapse_punct(text):
    text = re.sub(r"。{2,}", "。", text)
    text = re.sub(r"\.{3,}", "。", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _renumber(mode, text):
    """行首编号统一为连续单层编号（1. 2. 3. ...）。"""
    if mode == "plain":
        return _ANY_NUM_RE.sub(r"\1", text)
    matches = list(_ANY_NUM_RE.finditer(text))
    if len(matches) >= 2:
        counter = [0]

        def _repl(m):
            counter[0] += 1
            return f"{counter[0]}. {m.group(1).strip()}"

        return _ANY_NUM_RE.sub(_repl, text)
    # 单行：只去掉层级编号（1.1. 2.1 等），普通单层编号/内联列表保留
    return _HIER_NUM_RE.sub(r"\1", text)


def normalize_llm_text(text, mode="auto"):
    """规范化 LLM 自由文本。

    mode:
      - auto : 多层编号（1.1.）与跳号列表重排为 1. 2. 3.；单行编号去掉编号
      - plain: 一律去掉编号，只保留纯文本
    """
    if not text or not isinstance(text, str):
        return text or ""
    text = _collapse_punct(text)
    text = _BOLD_RE.sub(r"\1", text)
    return _renumber(mode, text)


if __name__ == "__main__":
    samples = [
        "1.1. 关闭机床电源，并挂上“维修中”警示牌。\n1.2. 打开防护门，使用扳手松开刀具夹头。",
        "1、关闭机床电源。\n2、打开防护门。",
        "1. 关闭机床电源\n1. 打开防护门\n1. 取出刀具",
        "建议参考 ISO 8688: 4.2 条款。",
        "**维修步骤**：\n1.1 关闭机床电源\n1.2 打开防护门",
        "1. 立即停机，测量VB值；2. 若VB≥0.2mm则换刀；3. 继续监控。",
    ]
    for s in samples:
        print(repr(s), "->", repr(normalize_llm_text(s)))
