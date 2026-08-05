"""
Step 4.1: 异常研判 Agent
========================
职责: 判断异常事件是否值得进入故障诊断流程
  - 硬规则过滤: 置信度 < 0.5 或 注入的测试误报 -> filter
  - 复杂场景: 调用 LLM 综合研判
输出: {"decision": "pass"|"filter", "reason": ..., "confidence": ...}
"""
import json


class AnomalyScreeningAgent:
    def __init__(self, llm_client):
        self.llm = llm_client

    def screen(self, event):
        # ---- 硬规则层（不依赖 LLM）----
        if event.get("confidence", 1.0) < 0.5:
            return {"decision": "filter",
                    "reason": f"置信度 {event.get('confidence')} 低于阈值 0.5",
                    "confidence": 0.1}

        if event.get("anomaly_type") == "false_positive_injected":
            return {"decision": "filter",
                    "reason": "系统注入的测试误报，直接过滤",
                    "confidence": 0.05}

        # ---- LLM 层（复杂场景，规则无法确定时）----
        prompt = (
            "你是工业异常研判专家。请判断以下刀具监测异常事件是否值得进一步诊断。\n\n"
            f"事件类型: {event.get('anomaly_type')}\n"
            f"严重程度: {event.get('severity')}\n"
            f"特征摘要: {json.dumps(event.get('features_summary', {}), ensure_ascii=False)}\n"
            f"置信度: {event.get('confidence')}\n\n"
            '请只输出 JSON: {"decision": "pass" 或 "filter", "reason": "简要理由"}'
        )
        resp = self.llm.chat_json(prompt, max_tokens=300)
        if resp and resp.get("decision") in ("pass", "filter"):
            return {"decision": resp["decision"],
                    "reason": resp.get("reason", "LLM研判"),
                    "confidence": event.get("confidence", 0.5)}

        # ---- 规则兜底（LLM 不可用或解析失败）----
        # 高严重度且高置信度 -> 通过
        sev_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
        sev_score = sev_map.get(event.get("severity", "low"), 0.5)
        if event.get("confidence", 0.5) > 0.7 and sev_score >= 0.6:
            return {"decision": "pass",
                    "reason": "高严重度高置信度，通过初步筛查",
                    "confidence": event.get("confidence", 0.5)}
        return {"decision": "filter",
                "reason": "置信度/严重度不足，规则兜底过滤",
                "confidence": 0.3}
