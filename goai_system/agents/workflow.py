"""
Step 5: LangGraph 编排
======================
五 Agent 链: 异常研判 -> 故障诊断(RAG) -> 维修方案生成 -> 维修调度 -> 知识沉淀
流程:
  screening --(filter)--> END
  screening --(pass)----> diagnose -> plan -> dispatch
  dispatch --(required_approval)--> approval(模拟人工审批) -> knowledge
  dispatch --(auto_approved)-----> knowledge -> END
运行:
  单事件: run_one(event)
  批量: run_batch(events) -> 遍历 event_stream.jsonl
"""
import json
import sys
from datetime import datetime, timezone
from typing import TypedDict, Optional, Literal
from pathlib import Path

# 确保 goai_system 在 sys.path（支持从任意目录运行）
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from langgraph.graph import StateGraph, END

from agents.llm_client import LLMClient
from agents.maintenance_plan_agent import MaintenancePlanAgent
from agents.anomaly_screening_agent import AnomalyScreeningAgent
from agents.fault_diagnosis_agent import FaultDiagnosisAgent
from agents.maintenance_dispatch_agent import MaintenanceDispatchAgent
from agents.knowledge_update_agent import KnowledgeUpdateAgent
from agents.audit import build_log_entry, append_audit, DEFAULT_MODEL

KB_BASE = BASE_DIR / "knowledge_base"


class AgentState(TypedDict):
    event: dict
    screening_result: Optional[dict]
    diagnosis: Optional[dict]          # 故障诊断结果
    plan_result: Optional[dict]         # 维修方案结果（你的 Agent 输出）
    work_order: Optional[dict]
    human_approval: Optional[str]
    knowledge_entry: Optional[dict]
    log: list


def _make_agents():
    llm = LLMClient()
    from knowledge_base.kb import KnowledgeBase
    kb = KnowledgeBase(chunks_path=KB_BASE / "chunks.jsonl",
                       vec_path=KB_BASE / "vectorizer.pkl")
    return {
        "screening": AnomalyScreeningAgent(llm),
        "diagnosis": FaultDiagnosisAgent(llm, kb),
        "plan": MaintenancePlanAgent(llm),           # 你的 Agent
        "dispatch": MaintenanceDispatchAgent(llm),
        "knowledge": KnowledgeUpdateAgent(kb),
        "llm": llm,
    }


def build_graph():
    agents = _make_agents()

    def screening_node(state: AgentState):
        t0 = datetime.now()
        result = agents["screening"].screen(state["event"])
        append_audit(build_log_entry(
            "screening", state["event"], result,
            latency_ms=(datetime.now() - t0).total_seconds() * 1000))
        state["screening_result"] = result
        state["log"].append({"node": "screening", "output": result})
        return state

    def diagnosis_node(state: AgentState):
        t0 = datetime.now()
        report = agents["diagnosis"].diagnose(state["event"])
        append_audit(build_log_entry(
            "diagnosis", state["event"], report,
            latency_ms=(datetime.now() - t0).total_seconds() * 1000))
        state["diagnosis"] = report
        state["log"].append({"node": "diagnosis", "output": report})
        return state

    def plan_node(state: AgentState):
        """Step 4.2: 维修方案生成（你的 Agent）"""
        t0 = datetime.now()
        diagnosis = state.get("diagnosis", {})
        plan_result = agents["plan"].generate_plan(diagnosis)
        append_audit(build_log_entry(
            "plan", diagnosis, plan_result,
            latency_ms=(datetime.now() - t0).total_seconds() * 1000))
        state["plan_result"] = plan_result
        state["log"].append({"node": "plan", "output": plan_result})
        return state

    def dispatch_node(state: AgentState):
        t0 = datetime.now()
        wo = agents["dispatch"].dispatch(state["diagnosis"])
        append_audit(build_log_entry(
            "dispatch", state["diagnosis"], wo,
            latency_ms=(datetime.now() - t0).total_seconds() * 1000))
        state["work_order"] = wo
        state["log"].append({"node": "dispatch", "output": wo})
        return state

    def approval_node(state: AgentState):
        """模拟人工审批: 默认自动批准（UI 可注入 human_approval）。"""
        decision = state.get("human_approval") or "approved"
        entry = build_log_entry("approval", state["work_order"],
                                {"decision": decision})
        append_audit(entry)
        state["human_approval"] = decision
        state["log"].append({"node": "approval", "output": decision})
        return state

    def knowledge_node(state: AgentState):
        t0 = datetime.now()
        wo = dict(state["work_order"])
        wo["symptom"] = (state.get("diagnosis") or {}).get("conclusion", "待补充")
        kn = agents["knowledge"].update(wo, human_feedback={"effect": "换刀后恢复正常"})
        append_audit(build_log_entry(
            "knowledge", wo, kn,
            latency_ms=(datetime.now() - t0).total_seconds() * 1000))
        state["knowledge_entry"] = kn
        state["log"].append({"node": "knowledge", "output": kn})
        return state

    # ---------- 路由函数 ----------
    def screening_router(state: AgentState) -> Literal["diagnose", "end"]:
        if state["screening_result"]["decision"] == "filter":
            return "end"
        return "diagnose"      # 指向诊断节点

    def dispatch_router(state: AgentState) -> Literal["approval", "knowledge"]:
        if state["work_order"]["required_approval"]:
            return "approval"
        return "knowledge"

    def approval_router(state: AgentState) -> Literal["knowledge", "end"]:
        if state.get("human_approval") == "approved":
            return "knowledge"
        return "end"

    # ---------- 构建图 ----------
    g = StateGraph(AgentState)
    g.add_node("screening", screening_node)
    g.add_node("diagnose", diagnosis_node)      # 节点名改为 "diagnose"
    g.add_node("plan", plan_node)               # 节点名改为 "plan"
    g.add_node("dispatch", dispatch_node)
    g.add_node("approval", approval_node)
    g.add_node("knowledge", knowledge_node)

    g.set_entry_point("screening")
    g.add_conditional_edges("screening", screening_router, {
        "diagnose": "diagnose",
        "end": END
    })
    g.add_edge("diagnose", "plan")
    g.add_edge("plan", "dispatch")
    g.add_conditional_edges("dispatch", dispatch_router, {
        "approval": "approval",
        "knowledge": "knowledge"
    })
    g.add_conditional_edges("approval", approval_router, {
        "knowledge": "knowledge",
        "end": END
    })
    g.add_edge("knowledge", END)

    return g.compile(), agents


def initial_state(event):
    return {
        "event": event,
        "screening_result": None,
        "diagnosis": None,
        "plan_result": None,      # 补充 plan_result
        "work_order": None,
        "human_approval": None,
        "knowledge_entry": None,
        "log": [],
    }


def run_one(event, app=None):
    if app is None:
        app, _ = build_graph()
    return app.invoke(initial_state(event))


def run_batch(events=None, max_events=None):
    """批量处理事件流，返回结果列表。"""
    if events is None:
        stream_path = BASE_DIR / "simulator" / "event_stream.jsonl"
        events = []
        if stream_path.exists():
            with open(stream_path, "r", encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
    if max_events:
        events = events[:max_events]

    app, _ = build_graph()
    results = []
    for ev in events:
        try:
            res = run_one(ev, app)
            results.append(res)
        except Exception as e:
            print(f"[workflow] 处理 {ev.get('event_id')} 失败: {e}")
    return results


# ========== 并发处理（性能优化） ==========
_process_lock = threading.Lock()


def run_batch_parallel(events, max_workers=4, max_events=None):
    """
    并发批量处理事件（使用线程池）
    
    Args:
        events: 事件列表
        max_workers: 最大并发数
        max_events: 最大处理事件数
    """
    if max_events:
        events = events[:max_events]
    
    app, _ = build_graph()
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_event = {
            executor.submit(run_one, ev, app): ev 
            for ev in events
        }
        
        for future in as_completed(future_to_event):
            ev = future_to_event[future]
            try:
                result = future.result(timeout=120)
                with _process_lock:
                    results.append(result)
            except Exception as e:
                print(f"[并行] 处理 {ev.get('event_id')} 失败: {e}")
    
    return results


if __name__ == "__main__":
    # ... 原有主程序代码保持不变 ...