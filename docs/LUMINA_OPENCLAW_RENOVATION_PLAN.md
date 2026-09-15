# Lumina OpenClaw 改造计划（历史参考版）

> 版本：v2.0
> 日期：2026-07-04
> 状态：**已放弃，仅作为历史参考保留**
> 当前执行方案：`docs/LUMINA_HYBRID_RENOVATION_PLAN.md`
> 决策文档：`docs/LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md`

---

## 一、为什么放弃 OpenClaw 深度集成？

经过评估，OpenClaw 深度集成方案被放弃，原因如下：

| 问题 | 说明 |
|------|------|
| 跨语言成本高 | OpenClaw 是 TypeScript/Node.js，Lumina 是 Python/FastAPI，需要复杂的桥接层 |
| 接口兼容性差 | 需要前端改用 WebSocket/新的 SSE 协议，违反"对外接口不变"红线 |
| 见效太慢 | 基础架构改造就需要 4-6 周，无法快速解决 P0 问题 |
| 改造成本高 | 需要新增 Node.js 容器、网关、MCP 封装、双栈维护 |
| 业务匹配度低 | Lumina 的核心需求是 AI 营销助手，不是多通道即时通讯网关 |
| 历史包袱轻 | Lumina 实际上没有真正使用 OpenClaw，vendor 中只是一个薄壳 |

**结论**：OpenClaw 的能力很强，但不适合作为 Lumina 当前改造的主要底座。

---

## 二、现有 OpenClaw 扩展的处理方式

### 2.1 现状

当前 `vendor/openclaw/extensions/lumina-ai-marketing/index.ts` 注册了一个简单的工具：

```typescript
// 该扩展仅做 HTTP 转发到 Python 的 /api/v1/marketing/hub
const plugin = {
  id: "lumina-ai-marketing",
  register(api) {
    api.registerTool({
      id: "marketing_intelligence_hub",
      execute: executeMarketingHub,
    });
  },
};
```

### 2.2 处理方式

| 决策 | 说明 |
|------|------|
| **保留** | 不删除，作为历史兼容 |
| **不扩展** | 不再新增 OpenClaw 工具或功能 |
| **不启动服务** | Docker Compose 中不启动 OpenClaw 容器 |
| **文档化** | 本文件标记为历史参考 |

### 2.3 为什么保留？

1. 防止已有用户/配置依赖该扩展
2. 避免无意义的代码删除风险
3. 作为未来可能对接其他 OpenClaw 生态的后门（不承诺）

---

## 三、原 OpenClaw 方案概述（历史内容）

> 以下内容保留原始思路，供参考。

### 3.1 原定目标

1. 将 OpenClaw 作为 Lumina 的核心底座
2. 复用 OpenClaw 的向量记忆、子代理、流式推理能力
3. 通过 MCP/WebSocket 让 Python 后端调用 OpenClaw

### 3.2 原定架构

```
前端
  │
  ▼
OpenClaw Gateway (Node.js)
  │
  ├─→ MCP Server (Node.js)
  │      │
  │      ▼
  │   Python FastAPI (现有)
  │
  └─→ 向量记忆 / 子代理 / LLM 路由
```

### 3.3 原定阶段

| 阶段 | 周期 | 内容 |
|------|------|------|
| 阶段 1 | 4-6 周 | 集成 OpenClaw Gateway + MCP |
| 阶段 2 | 3-4 周 | 向量记忆 + 工作流 |
| 阶段 3 | 2-3 周 | 多平台 + 自学习 |

---

## 四、转向混合方案后的对比

| 维度 | 原 OpenClaw 方案 | 当前混合方案 |
|------|------------------|--------------|
| 语言栈 | TypeScript + Python | Python 单栈 |
| 容器数 | 2+ | 1 |
| 对外接口 | 需改动 | 100% 不变 |
| P0 见效时间 | 6-8 周 | 2-3 周 |
| 回滚难度 | 高 | 低 |
| 长期 Agent 能力 | 强 | 强（Hermes） |
| 多平台网关 | 强 | 强（Hermes） |

---

## 五、经验教训

1. **不要被已有代码绑架**：Lumina 把 OpenClaw 放在 vendor 中，但几乎没使用，不应因此强行选择它
2. **语言栈一致性很重要**：跨语言集成会显著增加成本和风险
3. **接口稳定性是红线**：任何让用户前端改动的方案都要高度谨慎
4. **先解决业务问题再谈架构**：P0 问题需要快速见效，不能等底层重构完成
5. **选择最适合的，而不是最强大的**：OpenClaw 强在网关，Lumina 更需要 Agent 和记忆

---

## 六、相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| **混合改造计划（最终版）** | `docs/LUMINA_HYBRID_RENOVATION_PLAN.md` | 当前执行方案 |
| 业务真源 | `docs/LUMINA_BUSINESS_SOURCE_OF_TRUTH.md` | 决策约束 |
| 底座对比与决策 | `docs/LUMINA_RENOVATION_BASE_COMPARISON_AND_PLAN.md` | 方案对比 |
| 效果评估 | `docs/LUMINA_RENOVATION_EFFECTIVENESS_ASSESSMENT.md` | 效果评估 |
| Docker 影响分析 | `docs/LUMINA_DOCKER_FUNCTION_IMPACT_ANALYSIS.md` | 部署影响 |

---

> **注意：本文档不再维护，任何新的改造工作都应参考 `docs/LUMINA_HYBRID_RENOVATION_PLAN.md`。**
