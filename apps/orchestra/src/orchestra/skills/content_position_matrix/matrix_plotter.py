"""定位矩阵 ASCII 可视化。"""

from __future__ import annotations


def classify_quadrant(professional: float, entertainment: float) -> str:
    """根据专业度和娱乐度判断象限。"""
    p_high = professional >= 6
    e_high = entertainment >= 6

    if p_high and e_high:
        return "viral爆款区"
    if not p_high and e_high:
        return "娱乐消遣区"
    if p_high and not e_high:
        return "知识干货区"
    return "日常分享区"


def _intensity_marker(intensity: float) -> str:
    if intensity > 0.10:
        return "🔴"
    if intensity > 0.05:
        return "🟠"
    if intensity > 0.02:
        return "🟡"
    return "⚪"


def render_ascii_matrix(
    professional: float,
    entertainment: float,
    intensity: float = 0.0,
    width: int = 21,
    height: int = 11,
) -> str:
    """渲染 ASCII 矩阵图。"""
    # 坐标映射到 0-(width-1) 和 0-(height-1)
    x = int((professional / 10) * (width - 1))
    y = int((entertainment / 10) * (height - 1))

    lines: list[str] = []
    lines.append("      低专业度 ←————————————————————→ 高专业度")
    lines.append(f"  高  {'+' + '-' * width + '+':^{width + 4}}")

    for row in range(height - 1, -1, -1):
        # 左侧标签只显示中间和两端
        if row == height - 1:
            label = "娱 "
        elif row == height // 2:
            label = "乐 "
        elif row == 0:
            label = "度 "
        else:
            label = "   "

        row_chars: list[str] = ["|"]
        for col in range(width):
            if col == x and row == y:
                row_chars.append("★")
            else:
                row_chars.append(" ")
        row_chars.append("|")
        lines.append(f"{label}{''.join(row_chars)}")

    lines.append(f"  低  {'+' + '-' * width + '+':^{width + 4}}")
    lines.append("")

    quadrant = classify_quadrant(professional, entertainment)
    marker = _intensity_marker(intensity)
    lines.append(f"  当前位置：专业度 {professional:.1f}，娱乐度 {entertainment:.1f}")
    lines.append(f"  所在象限：{quadrant}")
    lines.append(f"  互动强度：{marker} {intensity:.1%}")

    return "\n".join(lines)
