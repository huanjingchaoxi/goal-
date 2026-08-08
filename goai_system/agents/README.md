# GOAI 智能体模块说明

本目录包含 GOAI 无界应用赛道「AI+工业制造」项目的所有 Agent 实现。

## Agent 列表

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| `anomaly_screening_agent` | 异常事件初筛 | 传感器事件 | 筛选决策（通过/过滤） |
| `fault_diagnosis_agent` | 故障诊断（RAG 增强） | 异常事件 | 诊断报告（含故障类型、置信度） |
| `maintenance_plan_agent` | 维修方案生成 | 诊断报告 | 维修方案（步骤、工具、备件、风险） |
| `maintenance_dispatch_agent` | 维修工单派发 | 维修方案 | 工单（含优先级、负责人） |
| `knowledge_update_agent` | 知识库沉淀 | 工单及反馈 | 知识条目更新 |
| `llm_client` | 大模型客户端（DeepSeek / Ollama） | Prompt | JSON 响应 |

---

# MaintenancePlanAgent

## 1. 职责定位

`MaintenancePlanAgent` 是维修链路的最后输出端，负责将上游 `fault_diagnosis_agent` 的诊断结论，转化为一线维修人员可直接执行的结构化维修方案，包含：

- 具体操作步骤
- 所需工具清单
- 所需备件清单
- 风险等级评估
- 安全操作提示

## 2. 输入格式（`diagnosis` 字典）

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `tool_id` | str | 否 | 刀具编号 | `"T001"` |
| `fault_type` | str | 是 | 故障类型（支持 8 种内置类型） | `"刀具磨损"` |
| `severity` | str | 否 | 严重程度 | `"high"` / `"medium"` / `"low"` |
| `confidence` | float | 否 | 置信度 0-1 | `0.85` |
| `conclusion` | str | 否 | 诊断结论 | `"VB值0.32mm，超出阈值"` |
| `recommended_action` | str | 否 | 推荐操作 | `"replace"` / `"inspect"` / `"adjust"` |
| `diagnosis_id` | str | 否 | 关联诊断 ID | `"diag_20260808_001"` |

### 输入示例

```python
diagnosis = {
    "tool_id": "T001",
    "fault_type": "刀具磨损",
    "severity": "high",
    "confidence": 0.85,
    "conclusion": "VB值0.32mm，超出阈值0.3mm，建议更换刀具",
    "recommended_action": "replace",
    "diagnosis_id": "diag_20260808_001"
}
```

## 3. 输出格式（维修方案字典）

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `plan_id` | str | 方案唯一标识 | `"plan_20260808_120000"` |
| `diagnosis_id` | str | 关联的诊断 ID | `"diag_20260808_001"` |
| `tool_id` | str | 刀具编号 | `"T001"` |
| `fault_type` | str | 故障类型 | `"刀具磨损"` |
| `severity` | str | 严重程度 | `"high"` |
| `steps` | List[str] | 维修操作步骤列表（5-8 步） | `["停机并拆卸刀具...", ...]` |
| `required_tools` | List[str] | 所需工具清单 | `["千分尺", "扭矩扳手"]` |
| `required_parts` | List[str] | 所需备件清单 | `["备用刀片(型号匹配)"]` |
| `estimated_time_min` | int | 预估维修时间（分钟） | `30` |
| `risk_level` | str | 风险等级 | `"low"` / `"medium"` / `"high"` |
| `safety_notes` | str | 安全操作提示 | `"更换刀具前确保设备完全停机..."` |
| `created_at` | str | 方案生成时间（ISO 8601） | `"2026-08-08T12:00:00Z"` |

### 输出示例

```python
{
    "plan_id": "plan_20260808_120000",
    "diagnosis_id": "diag_20260808_001",
    "tool_id": "T001",
    "fault_type": "刀具磨损",
    "severity": "high",
    "steps": [
        "停机并拆卸刀具，检查刀片磨损情况",
        "使用千分尺测量后刀面磨损带宽度 (VB 值)",
        "若 VB 值超过 0.3mm（依据 ISO 3685），更换新刀片",
        "安装新刀片后，以 50% 切削用量进行试切",
        "测量试切件尺寸，确认加工精度达标"
    ],
    "required_tools": ["千分尺", "扭矩扳手", "拆卸工具"],
    "required_parts": ["备用刀片 (型号匹配)"],
    "estimated_time_min": 30,
    "risk_level": "medium",
    "safety_notes": "更换刀具前确保设备完全停机并上锁挂牌",
    "created_at": "2026-08-08T12:00:00Z"
}
```

## 4. 工作模式（三级智能降级）

`generate_plan()` 方法按以下优先级依次尝试，确保系统在任何情况下都能输出可用方案：

| 优先级 | 模式 | 说明 | 适用场景 |
|--------|------|------|----------|
| 1 | 知识库 + LLM | 从 ChromaDB 检索 Sandvik 手册等专业文档，结合大模型生成方案 | LLM 可用 + 知识库已构建（最专业） |
| 2 | 纯 LLM | 仅使用大模型推理 | LLM 可用（无知识库或检索失败） |
| 3 | 规则引擎 | 内置 8 种故障类型模板，无需网络 | LLM 不可用或超时（最稳定） |

## 5. 内置故障类型（规则引擎完整列表）

规则引擎覆盖 8 种常见刀具失效模式，每种均预设了步骤、工具、备件、时间和风险：

| 序号 | 故障类型 | 风险默认 | 预估时间 | 核心解决方案 |
|------|---------|---------|---------|-------------|
| 1 | 刀具磨损 | low/medium | 30 min | 测量 VB 值，按 ISO 3685 判定是否更换 |
| 2 | 刀具崩刃 | high | 45 min | 立即停机，更换刀具，检查主轴 |
| 3 | 刀具涂层脱落 | low | 20 min | 检查脱落面积，更换涂层刀具 |
| 4 | 积屑瘤 (BUE) | low | 20 min | 提高切削速度，更换正几何刀片 |
| 5 | 热裂纹 | medium | 25 min | 调整冷却方式，选择抗热冲击材质 |
| 6 | 缺口磨损 | medium | 30 min | 降低切削速度，选择更韧材质 |
| 7 | 塑性变形 | medium | 20 min | 选择更硬材质，降低切削参数 |
| 8 | 月牙洼磨损 | low | 25 min | 选择 Al₂O₃ 涂层刀片，降低转速 |

## 6. 知识库（RAG 增强）

Agent 依赖 `goai_system/knowledge_base/` 下的专业文档进行检索增强。当前知识库包含 4 份核心文档：

| 文件名 | 内容 | 字符数 |
|--------|------|--------|
| `Sandvik_铣削故障排除_结构化.md` | Sandvik 官方铣削故障排除指南（振动、切屑、表面质量、磨损等） | ~3,655 |
| `ISO_3685_刀具寿命测试标准_摘要.md` | 国际标准刀具寿命测试程序与 VB 值判定标准 | ~1,532 |
| `不锈钢铣削切削参数指南.md` | 不锈钢铣削的推荐切削速度、进给量、刀具材料 | ~2,006 |
| `硬质合金刀具牌号选择指南.md` | YG/YG3X/YG8 等牌号参数及选型原则 | ~2,789 |

### 知识库构建命令

```bash
python build_kb.py   # 重新构建向量索引（ChromaDB）
```

## 7. 大模型支持

| 后端 | 模型 | 运行方式 | 使用场景 |
|------|------|---------|----------|
| Ollama（推荐） | `qwen2.5:7b` / `llama3.2:3b` | 本地推理，无需联网 | 离线环境、稳定演示 |
| DeepSeek API | `deepseek-chat` | 云端 API，需要网络 | 追求最佳效果 |

Agent 通过 `llm_client` 参数注入大模型客户端，不依赖具体实现。

## 8. 与工作流的集成

`MaintenancePlanAgent` 已集成到 `workflow.py` 的 LangGraph 五 Agent 链中：

```text
异常事件 → 异常研判 → 故障诊断 → 维修方案生成 → 工单派发 → 知识沉淀
                                    ↑
                              你的 Agent
```

## 9. 使用示例

### 9.1 仅使用规则引擎（无需 LLM）

```python
from agents.maintenance_plan_agent import MaintenancePlanAgent

agent = MaintenancePlanAgent()

diagnosis = {
    "fault_type": "热裂纹",
    "severity": "medium",
    "conclusion": "刀片出现垂直于切削刃的热裂纹"
}

result = agent.generate_plan(diagnosis)
print(result["steps"])
```

### 9.2 使用本地 Ollama（完整模式）

```python
from agents.maintenance_plan_agent import MaintenancePlanAgent, OllamaClient

llm = OllamaClient(model="qwen2.5:7b")
agent = MaintenancePlanAgent(llm_client=llm)

diagnosis = {
    "tool_id": "T001",
    "fault_type": "刀具磨损",
    "severity": "high",
    "conclusion": "VB值0.32mm，超出阈值0.3mm"
}

result = agent.generate_plan(diagnosis)
print(f"风险等级: {result['risk_level']}")
print(f"预估时间: {result['estimated_time_min']} 分钟")
for step in result["steps"]:
    print(f"  - {step}")
```

### 9.3 在工作流中调用

```python
# workflow.py 中已集成，不需要手动调用
# 工作流会自动执行 plan_node
```

## 10. 依赖与安装

### Python 依赖

```bash
pip install langchain langchain-community chromadb sentence-transformers
```

### 本地大模型（Ollama）

从 [ollama.com](https://ollama.com) 下载安装后执行：

```bash
ollama pull qwen2.5:7b
```

### 向量化模型

首次运行时会自动下载 `sentence-transformers/all-MiniLM-L6-v2`（约 80 MB）。

## 11. 故障类型扩展指南

如需新增故障类型，在 `_generate_by_rules()` 方法的 `templates` 字典中添加条目：

```python
templates = {
    # ... 已有类型 ...
    "新故障名称": {
        "steps": ["步骤1", "步骤2", "步骤3"],
        "tools": ["工具1", "工具2"],
        "parts": ["备件1"],
        "time": 30,
        "risk": "medium",
        "safety": "安全提示"
    }
}
```

## 12. 其他 Agent 简要说明

## anomaly_screening_agent

- **职责**：对传感器事件进行初步筛选，过滤误报
- **输入**：事件流中的单条事件
- **输出**：`{"decision": "pass"}` 或 `{"decision": "filter"}`

## fault_diagnosis_agent

- **职责**：基于 RAG 知识库进行故障诊断
- **输入**：通过筛选的事件
- **输出**：诊断报告（含故障类型、置信度、结论）

## maintenance_dispatch_agent

- **职责**：根据维修方案生成派工单
- **输入**：维修方案
- **输出**：工单（含优先级、负责部门、状态）

## knowledge_update_agent

- **职责**：将维修案例沉淀到知识库
- **输入**：工单及反馈
- **输出**：知识条目 ID

---

**最后更新**：2026-08-08  
```