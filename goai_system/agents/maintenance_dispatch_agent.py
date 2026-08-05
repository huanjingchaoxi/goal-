"""
Step 4.3: 维修调度 Agent
========================
职责: 根据诊断报告的置信度与剩余寿命，生成维修工单并定级
输出: 工单（符合数据契约 3.3）
"""
from datetime import datetime, timezone


class MaintenanceDispatchAgent:
    def __init__(self, llm_client=None):
        self.llm = llm_client

    def dispatch(self, diagnosis):
        # 防御: LLM 偶发返回 null，转成安全默认值
        conf = diagnosis.get("confidence")
        conf = conf if isinstance(conf, (int, float)) else 0.5
        rul = diagnosis.get("rul_estimate_hours")
        rul = rul if isinstance(rul, (int, float)) else 24

        if conf > 0.9 and rul < 2:
            risk_level, priority = "high", "critical"
            required_approval = True
        elif conf > 0.7 and rul < 8:
            risk_level, priority = "medium", "high"
            required_approval = True
        else:
            risk_level, priority = "low", "normal"
            required_approval = False

        return {
            "work_order_id": f"wo_{diagnosis.get('diagnosis_id', 'diag_unknown')}",
            "diagnosis_id": diagnosis.get("diagnosis_id"),
            "event_id": diagnosis.get("event_id"),
            "tool_id": diagnosis.get("tool_id", "unknown"),
            "priority": priority,
            "risk_level": risk_level,
            "action": diagnosis.get("recommended_action", "inspect"),
            "estimated_downtime_min": 45 if risk_level == "high" else 30,
            "required_approval": required_approval,
            "status": "pending_approval" if required_approval else "auto_approved",
            "conclusion": diagnosis.get("conclusion", ""),
            "rul_estimate_hours": rul,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
