# Phase 3 P2 SPEC：ContentPositionMatrix 评分与 ASCII 可视化

> 文档版本：v1.0
> 日期：2026-07-07
> 依据：`docs/specs/phase3_skill_intent_routing_spec.md`

---

## 1. 目标

为 **内容定位矩阵（ContentPositionMatrix）Skill** 实现专业度/娱乐度评分、互动强度计算与 ASCII 矩阵可视化。

---

## 2. 输入边界

### 2.1 Skill 入口

```python
async def run(
    message: str,
    platform: str | None,
    context: dict[str, Any],
    history: list[dict[str, str]],
    mode: str | None = None,
) -> str
```

### 2.2 从 message/context 解析的参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| 内容输入 | string | 是 | 标题 + 正文文本（URL/OCR 结果后续扩展） |
| 垂类 | string | 否 | 美妆/数码/家居/职场/健身... |
| 对标账号内容 | list | 否 | 竞品内容列表，用于识别红海/蓝海 |

---

## 3. 输出边界

### 3.1 评分结果

```python
{
    "professional_score": 6.5,      # 1-10
    "entertainment_score": 7.2,     # 1-10
    "engagement_intensity": 0.08,   # 0-1
    "quadrant": "viral爆款区",       # 知识干货区 / viral爆款区 / 娱乐消遣区 / 日常分享区
    "diagnosis": "...",
    "differentiation_tips": ["...", "...", "..."],
}
```

### 3.2 Skill 输出

Markdown 报告 + ASCII 矩阵图 + 定位诊断 + 差异化建议。

---

## 4. 业务规则

### 4.1 专业度评分（1-10）

基于文本特征：
- 信息密度：正文字数 / 段落数 ≥ 80 得高分
- 专业术语：出现「成分」「测评」「教程」「步骤」「数据」等词
- 数据/案例引用：出现数字、百分比、对比
- 结构清晰度：有序列表、分步骤、小标题

```text
professional_score = min(10, base + info_density + terminology + data_case + structure)
```

### 4.2 娱乐度评分（1-10）

基于文本特征：
- 情绪激发：感叹词、emoji、情绪词（惊讶、共鸣、愤怒、愉悦）
- 叙事张力：冲突/转折/悬念词（但是、竟然、没想到、反转）
- 互动引导：评论区钩子（你怎么看？评论区见）
- 视觉冲击：封面相关描述（对比、前后、大特写）

### 4.3 互动强度

优先使用实际数据；无数据时基于专业度+娱乐度预测：
```text
engagement_intensity = 0.02 + professional_score * 0.005 + entertainment_score * 0.008
```

### 4.4 矩阵象限

| 专业度 | 娱乐度 | 象限 |
|--------|--------|------|
| ≥ 6 | ≥ 6 | viral 爆款区 |
| < 6 | ≥ 6 | 娱乐消遣区 |
| ≥ 6 | < 6 | 知识干货区 |
| < 6 | < 6 | 日常分享区 |

### 4.5 ASCII 矩阵

11×11 网格，坐标 (0-10, 0-10)，当前内容用 `★` 标记。

---

## 5. 安全合规

- 评分算法必须可解释
- 不依赖外部 API 时也能运行
- 用户输入长度限制 5000 字符

---

## 6. 接口兼容性

- 不修改统一接口协议
- Skill 输出保持 Markdown 格式
