"""
Step 4.4: 知识沉淀 Agent
========================
职责: 将已闭环的维修案例沉淀为知识条目并回写知识库（增量追加）
输出: 知识条目（符合数据契约 3.4）
"""
import json
from datetime import datetime, timezone


class KnowledgeUpdateAgent:
    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def update(self, work_order, human_feedback=None):
        diagnosis = work_order.get("diagnosis", {})
        symptom = work_order.get("symptom") or diagnosis.get("conclusion", "待补充")
        root_cause = work_order.get("root_cause", "待补充")
        action = work_order.get("action", "inspect")
        effect = (human_feedback or {}).get("effect", "待人工补充")

        entry = {
            "knowledge_id": f"kn_{work_order.get('work_order_id', 'wo_unknown')}",
            "work_order_id": work_order.get("work_order_id"),
            "symptom": symptom,
            "root_cause": root_cause,
            "action": action,
            "effect": effect,
            "source_wo": work_order.get("work_order_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 回写知识库（增量追加一条 case 知识）
        text = (f"故障现象：{symptom}。根因：{root_cause}。"
                f"处置：{action}。效果：{effect}。")
        if self.kb is not None:
            try:
                self.kb.add_knowledge(
                    text=text,
                    source=f"wo_{work_order.get('work_order_id', 'unknown')}",
                    category="case",
                    persist=True,
                )
                entry["knowledge_base_updated"] = True
            except Exception as e:
                entry["knowledge_base_updated"] = False
                entry["kb_error"] = str(e)
        return entry
