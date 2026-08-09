好的，任务一（`DEPLOY.md` 部署文档）已确认完成。接下来我们进行第二个任务：

---

## 第二个任务：创建 API 文档 `API.md`

在项目根目录（`goal-/`）下创建 `API.md`，以下是完整内容，可直接复制粘贴：

```markdown
# API 接口文档

本文档定义 GOAI 工业制造智能体系统的数据契约和接口规范。

---

## 数据契约

### 1. 事件（Event）

传感器异常事件的原始输入格式。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `event_id` | str | 事件唯一标识 | `"evt_20260808_001"` |
| `tool_id` | str | 刀具编号 | `"T001"` |
| `timestamp` | str | 事件时间（ISO 8601） | `"2026-08-08T12:00:00Z"` |
| `anomaly_type` | str | 异常类型 | `"force_trend_anomaly"` |
| `features` | dict | 传感器特征 | `{"Fx": 120.5, "Fy": 80.3, "Fz": 95.7}` |
| `metadata` | dict | 附加元数据 | `{"cut_id": 42}` |

**示例**：
```json
{
    "event_id": "evt_20260808_001",
    "tool_id": "T001",
    "timestamp": "2026-08-08T12:00:00Z",
    "anomaly_type": "force_trend_anomaly",
    "features": {"Fx": 120.5, "Fy": 80.3, "Fz": 95.7, "Vx": 0.12, "Vy": 0.08, "Vz": 0.15},
    "metadata": {"cut_id": 42}
}
```

---

### 2. 筛选结果（Screening Result）

`anomaly_screening_agent` 的输出。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `decision` | str | 决策结果 | `"pass"` / `"filter"` |
| `confidence` | float | 置信度 | `0.85` |
| `reason` | str | 决策原因 | `"传感器读数异常"` |

**示例**：
```json
{
    "decision": "pass",
    "confidence": 0.85,
    "reason": "切削力趋势异常，置信度高于阈值"
}
```

---

### 3. 诊断报告（Diagnosis Report）

`fault_diagnosis_agent` 的输出。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `diagnosis_id` | str | 诊断唯一标识 | `"diag_20260808_001"` |
| `tool_id` | str | 刀具编号 | `"T001"` |
| `fault_type` | str | 故障类型 | `"刀具磨损"` |
| `confidence` | float | 置信度 0-1 | `0.85` |
| `severity` | str | 严重程度 | `"high"` / `"medium"` / `"low"` |
| `conclusion` | str | 诊断结论 | `"VB值0.32mm，超出阈值"` |
| `recommended_action` | str | 推荐操作 | `"replace"` / `"inspect"` / `"adjust"` |
| `evidence` | List[str] | 诊断依据 | `["传感器数据", "知识库检索"]` |

**示例**：
```json
{
    "diagnosis_id": "diag_20260808_001",
    "tool_id": "T001",
    "fault_type": "刀具磨损",
    "confidence": 0.85,
    "severity": "high",
    "conclusion": "VB值0.32mm，超出阈值0.3mm，建议更换刀具",
    "recommended_action": "replace",
    "evidence": ["切削力趋势异常", "知识库检索到相关故障模式"]
}
```

---

### 4. 维修方案（Maintenance Plan）

`maintenance_plan_agent` 的输出。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `plan_id` | str | 方案唯一标识 | `"plan_20260808_001"` |
| `diagnosis_id` | str | 关联诊断 ID | `"diag_20260808_001"` |
| `tool_id` | str | 刀具编号 | `"T001"` |
| `fault_type` | str | 故障类型 | `"刀具磨损"` |
| `severity` | str | 严重程度 | `"high"` |
| `steps` | List[str] | 维修步骤列表 | `["停机...", "测量..."]` |
| `required_tools` | List[str] | 所需工具 | `["千分尺", "扭矩扳手"]` |
| `required_parts` | List[str] | 所需备件 | `["备用刀片"]` |
| `estimated_time_min` | int | 预估时间（分钟） | `30` |
| `risk_level` | str | 风险等级 | `"low"` / `"medium"` / `"high"` |
| `safety_notes` | str | 安全提示 | `"更换刀具前..."` |
| `created_at` | str | 创建时间 | `"2026-08-08T12:00:00Z"` |

**示例**：
```json
{
    "plan_id": "plan_20260808_001",
    "diagnosis_id": "diag_20260808_001",
    "tool_id": "T001",
    "fault_type": "刀具磨损",
    "severity": "high",
    "steps": [
        "停机并拆卸刀具，检查刀片磨损情况",
        "使用千分尺测量后刀面磨损带宽度 (VB 值)",
        "若 VB 值超过 0.3mm，更换新刀片"
    ],
    "required_tools": ["千分尺", "扭矩扳手", "拆卸工具"],
    "required_parts": ["备用刀片 (型号匹配)"],
    "estimated_time_min": 30,
    "risk_level": "medium",
    "safety_notes": "更换刀具前确保设备完全停机并上锁挂牌",
    "created_at": "2026-08-08T12:00:00Z"
}
```

---

### 5. 工单（Work Order）

`maintenance_dispatch_agent` 的输出。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `work_order_id` | str | 工单唯一标识 | `"WO_20260808_001"` |
| `plan_id` | str | 关联方案 ID | `"plan_20260808_001"` |
| `diagnosis_id` | str | 关联诊断 ID | `"diag_20260808_001"` |
| `assigned_to` | str | 指派人员/部门 | `"维修组-张工"` |
| `priority` | str | 优先级 | `"high"` / `"medium"` / `"low"` |
| `status` | str | 状态 | `"pending"` / `"in_progress"` / `"completed"` |
| `deadline` | str | 截止时间 | `"2026-08-08T18:00:00Z"` |
| `action` | str | 操作类型 | `"replace"` / `"inspect"` / `"adjust"` |
| `risk_level` | str | 风险等级 | `"high"` / `"medium"` / `"low"` |
| `required_approval` | bool | 是否需要审批 | `true` / `false` |

**示例**：
```json
{
    "work_order_id": "WO_20260808_001",
    "plan_id": "plan_20260808_001",
    "diagnosis_id": "diag_20260808_001",
    "assigned_to": "维修组-张工",
    "priority": "high",
    "status": "pending",
    "deadline": "2026-08-08T18:00:00Z",
    "action": "replace",
    "risk_level": "high",
    "required_approval": true
}
```

---

### 6. 知识条目（Knowledge Entry）

`knowledge_update_agent` 的输出。

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `knowledge_id` | str | 知识条目 ID | `"KB_20260808_001"` |
| `work_order_id` | str | 关联工单 ID | `"WO_20260808_001"` |
| `fault_type` | str | 故障类型 | `"刀具磨损"` |
| `solution` | str | 解决方案摘要 | `"更换刀片，调整切削参数"` |
| `effectiveness` | str | 效果评估 | `"换刀后恢复正常"` |
| `created_at` | str | 创建时间 | `"2026-08-08T12:00:00Z"` |

**示例**：
```json
{
    "knowledge_id": "KB_20260808_001",
    "work_order_id": "WO_20260808_001",
    "fault_type": "刀具磨损",
    "solution": "更换磨损刀片，将切削速度降低15%",
    "effectiveness": "换刀后加工表面粗糙度恢复至Ra≤1.6μm",
    "created_at": "2026-08-08T12:00:00Z"
}
```

---

## Agent 调用方式

### 1. Python 直接调用

```python
from agents.maintenance_plan_agent import MaintenancePlanAgent

agent = MaintenancePlanAgent()
diagnosis = {"fault_type": "刀具磨损", "severity": "high"}
result = agent.generate_plan(diagnosis)
```

### 2. LangGraph 工作流调用

```python
from agents.workflow import run_one

event = {"event_id": "evt_001", "anomaly_type": "force_trend_anomaly"}
result = run_one(event)
# result 包含所有 Agent 的输出
```

### 3. HTTP API（通过 Streamlit UI）

```
POST /api/run_pipeline
请求体: {"event": {...}}
响应: {"result": {...}}
```

---

## 错误码说明

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| `E001` | 事件格式无效 | 检查必填字段 |
| `E002` | 诊断失败（LLM 超时） | 降级到规则引擎 |
| `E003` | 知识库检索失败 | 检查 ChromaDB 是否构建 |
| `E004` | 工单派发失败 | 检查部门配置 |
| `E005` | Ollama 服务不可用 | 启动 `ollama serve` |

---

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-09 | 初始版本，定义 6 个核心数据契约 |
```

