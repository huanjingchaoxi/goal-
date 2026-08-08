"""
Step 4.2: 故障诊断 Agent（带 RAG + 幻觉防御）
==============================================
职责: 基于知识库检索结果 + 事件特征，生成诊断报告
  - 从知识库检索 top_k 相关条款
  - LLM 生成结构化诊断报告（严格 JSON）
  - 幻觉防御: evidence 的 source 必须在检索结果中
输出: diagnosis 报告（符合数据契约 3.2）
"""
import json
from datetime import datetime, timezone
from agents.text_utils import normalize_llm_text


class FaultDiagnosisAgent:
    def __init__(self, llm_client, knowledge_base):
        self.llm = llm_client
        self.kb = knowledge_base

    def _retrieve(self, event, top_k=3):
        query = f"{event.get('anomaly_type')} {json.dumps(event.get('features_summary', {}), ensure_ascii=False)}"
        try:
            return self.kb.retrieve(query, top_k=top_k)
        except Exception:
            return []

    def _hallucination_guard(self, report, retrieved):
        """幻觉防御: 剔除不在检索结果中的证据来源。"""
        valid = {r["source"] for r in retrieved}
        kept = []
        for ev in report.get("evidence", []):
            src = ev.get("source")
            if src and src not in valid:
                # 来源不在检索结果中 -> 该证据不可信，剔除并记录
                ev["dropped"] = True
                ev["reason"] = "source 不在检索结果中（幻觉防御）"
                continue
            kept.append(ev)
        report["evidence"] = kept
        return report

    def diagnose(self, event):
        retrieved = self._retrieve(event)
        context = "\n".join(f"[{r['source']}] {r['text']}" for r in retrieved)

        prompt = (
            "你是数控刀具故障诊断专家。基于以下知识库检索结果与异常事件，生成诊断报告。\n\n"
            f"异常事件: {json.dumps(event, ensure_ascii=False)}\n\n"
            f"知识库检索结果:\n{context if context else '(无检索结果)'}\n\n"
            "要求:\n"
            "1. 结论必须基于检索结果中的标准条款\n"
            "2. 每条证据必须标注来源（source 字段，只能取自上述检索结果的 [source] 标记）\n"
            "3. 如果检索结果不足以支撑结论，明确说明'证据不足'\n"
            "4. 输出严格 JSON 格式，不要输出其他内容\n"
            "5. conclusion 与 recommended_action 使用简洁文本；如需列出操作步骤，只允许单层编号（1. 2. 3.），禁止 1.1、2.1 等多层编号\n\n"
            '输出格式:\n'
            '{"conclusion": "诊断结论", "confidence": 0.0-1.0, '
            '"evidence": [{"type": "signal|standard|case", "desc": "...", "source": "..."}], '
            '"recommended_action": "...", "rul_estimate_hours": float}'
        )
        report = self.llm.chat_json(prompt, max_tokens=1000)
        if report and isinstance(report, dict) and report.get("conclusion"):
            # 规范化 LLM 自由文本：消除 1.1. 多层编号、重复标点等
            report["conclusion"] = normalize_llm_text(report["conclusion"])
            report["recommended_action"] = normalize_llm_text(
                report.get("recommended_action", ""))
            for ev in report.get("evidence", []):
                if isinstance(ev, dict) and ev.get("desc"):
                    ev["desc"] = normalize_llm_text(ev["desc"])
            report = self._hallucination_guard(report, retrieved)
            report["diagnosis_id"] = f"diag_{event.get('event_id', 'unknown')}"
            report["event_id"] = event.get("event_id")
            report["tool_id"] = event.get("tool_id")
            report["timestamp"] = datetime.now(timezone.utc).isoformat()
            return report

        # ---- 规则兜底（LLM 不可用）----
        atype = event.get("anomaly_type", "unknown")
        conclusion_map = {
            "vibration_drift": "振动漂移异常，疑为刀具后刀面磨损加剧或主轴动平衡问题",
            "ae_impact": "声发射冲击事件，疑为刃口崩刃或涂层脱落",
            "force_trend_anomaly": "切削力趋势偏离，疑为进给系统或刀具状态变化",
            "wear_approaching_limit": "刀具磨损接近寿命终点，建议立即安排换刀",
        }
        conclusion = conclusion_map.get(atype, "刀具异常，建议检查")
        evidence = []
        for r in retrieved[:3]:
            evidence.append({"type": r["category"], "desc": r["text"][:80], "source": r["source"]})
        if not evidence:
            evidence = [{"type": "signal",
                         "desc": f"检测到{atype}，特征摘要 {json.dumps(event.get('features_summary', {}), ensure_ascii=False)}"}]
        return {
            "diagnosis_id": f"diag_{event.get('event_id', 'unknown')}",
            "event_id": event.get("event_id"),
            "tool_id": event.get("tool_id"),
            "conclusion": conclusion,
            "confidence": event.get("confidence", 0.7),
            "evidence": evidence,
            "recommended_action": "schedule_tool_change" if atype in (
                "wear_approaching_limit", "vibration_drift") else "inspect",
            "rul_estimate_hours": 4.0 if atype == "wear_approaching_limit" else 12.0,
            "fallback": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
