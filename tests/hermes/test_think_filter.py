"""Phase 4 单元测试：流式思考标签过滤（<think>/<lumina_think>/<REASONING_SCRATCHPAD）。"""

from __future__ import annotations

import pytest

from services.hermes_adapter import _StreamThinkFilter


def _run(chunks: list[str]) -> str:
    f = _StreamThinkFilter()
    return "".join(f.feed(c) for c in chunks) + f.flush()


@pytest.mark.parametrize(
    "chunks,expected",
    [
        (["你好，世界"], "你好，世界"),
        (["<think>内部推理</think>正式回复"], "正式回复"),
        (["前缀<lumina_think>模型在想", "乱七八糟</lumina_think>后缀"], "前缀后缀"),
        (["<REASONING_SCRATCHPAD>草稿</REASONING_SCRATCHPAD>答案"], "答案"),
        # 跨 delta 拆分的标签
        (["abc<lum", "ina_th", "ink>secret</lumin", "a_think>def"], "abcdef"),
        (["a<th", "ink>x</think>b"], "ab"),
        # 未闭合的思考块：flush 时丢弃
        (["可见<think>未闭合内容"], "可见"),
        # 非思考标签原样保留
        (["价格 <100> 元"], "价格 <100> 元"),
        # 无匹配关闭标签：直接丢弃
        (["x</think>y"], "xy"),
    ],
)
def test_think_filter(chunks, expected):
    assert _run(chunks) == expected
