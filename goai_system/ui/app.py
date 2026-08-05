"""
Step 6: Streamlit UI —— 刀锋智维 数控刀具多智能体运维系统
=========================================================
启动: cd ui && streamlit run app.py
功能:
  - 左栏: 异常事件流列表（来自 simulator/event_stream.jsonl）
  - 中栏: 选中事件的 Agent 处理过程（研判/诊断/调度/审批/知识）
  - 右栏: 诊断报告 + 维修工单（高风险工单可人工审批）
  - 底部: 审计日志
"""
import json
import sys
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

st.set_page_config(page_title="刀锋智维", layout="wide")
st.title("🛠 刀锋智维 · 数控刀具多智能体运维系统")


@st.cache_data(show_spinner="加载异常事件流...")
def load_events():
    stream = BASE_DIR / "simulator" / "event_stream.jsonl"
    if not stream.exists():
        return []
    with open(stream, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@st.cache_resource
def get_app():
    from agents.workflow import build_graph, run_one, initial_state
    app, agents = build_graph()
    return app, agents


def main():
    events = load_events()
    if not events:
        st.error("未找到事件流，请先运行 Step 1/2 生成 event_stream.jsonl")
        return

    app, agents = get_app()
    from agents.workflow import run_one
    with st.sidebar:
        st.header("事件流")
        st.caption(f"共 {len(events)} 个事件 · LLM: "
                   f"{'✅ 可用' if agents['llm'].available else '⚠️ 规则兜底'} "
                   f"({agents['llm'].model})")
        labels = [f"{i+1:03d} [{e['severity']}] {e['anomaly_type']} · {e['tool_id']}"
                  for i, e in enumerate(events)]
        sel = st.selectbox("选择事件", range(len(events)), format_func=lambda i: labels[i])
        st.divider()
        st.caption("审计日志:")
        if st.button("刷新日志"):
            st.cache_data.clear()

    event = events[sel]

    # 运行工作流（事件未处理过才跑）
    key = f"result_{event['event_id']}"
    if key not in st.session_state:
        with st.spinner("Agent 链处理中..."):
            st.session_state[key] = run_one(event, app)
    result = st.session_state[key]

    col1, col2, col3 = st.columns([1, 1.3, 1.3])

    with col1:
        st.subheader("📡 事件详情")
        st.json(event)

    with col2:
        st.subheader("🤖 Agent 处理过程")
        for step in result.get("log", []):
            node = step["node"]
            out = step["output"]
            icons = {"screening": "🔍", "diagnosis": "🩺", "dispatch": "📋",
                     "approval": "👤", "knowledge": "📚"}
            st.markdown(f"**{icons.get(node, '•')} {node}**")
            if node == "screening":
                st.code(json.dumps(out, ensure_ascii=False, indent=2))
            elif node == "diagnosis":
                st.code(json.dumps({k: out[k] for k in
                                    ("conclusion", "confidence", "recommended_action",
                                     "rul_estimate_hours") if k in out},
                                   ensure_ascii=False, indent=2))
            elif node == "dispatch":
                wo = out
                st.code(json.dumps({k: wo[k] for k in
                                    ("work_order_id", "priority", "risk_level",
                                     "action", "status", "estimated_downtime_min")},
                                   ensure_ascii=False, indent=2))
            else:
                st.caption(json.dumps(out, ensure_ascii=False)[:200])

    with col3:
        st.subheader("📋 诊断报告 & 工单")
        diagnosis = result.get("diagnosis")
        wo = result.get("work_order")
        if diagnosis:
            with st.container(border=True):
                st.markdown(f"**结论**: {diagnosis.get('conclusion')}")
                st.markdown(f"**置信度**: {diagnosis.get('confidence')} "
                            f"· **RUL**: {diagnosis.get('rul_estimate_hours')} h")
                st.markdown("**证据**")
                for ev in diagnosis.get("evidence", []):
                    src = ev.get("source", "?")
                    st.markdown(f"- ({ev.get('type')}/{src}) {ev.get('desc')[:90]}")
        if wo:
            with st.container(border=True):
                st.markdown(f"**工单 {wo.get('work_order_id')}**")
                st.markdown(f"- 风险等级: `{wo.get('risk_level')}` · 优先级: `{wo.get('priority')}`")
                st.markdown(f"- 建议动作: {wo.get('action')} · 停机约 {wo.get('estimated_downtime_min')} min")
                st.markdown(f"- 状态: {wo.get('status')}")
                if wo.get("required_approval") and wo.get("status") == "pending_approval":
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ 批准执行", key=f"ap_{event['event_id']}"):
                            st.session_state[key]["human_approval"] = "approved"
                            st.session_state[key] = run_one(event, app)
                            st.rerun()
                    with c2:
                        if st.button("❌ 驳回", key=f"rj_{event['event_id']}"):
                            st.session_state[key]["human_approval"] = "rejected"
                            st.session_state[key] = run_one(event, app)
                            st.rerun()
        if result.get("knowledge_entry"):
            st.info(f"📚 知识沉淀: {result['knowledge_entry'].get('knowledge_id')}")

    st.divider()
    st.subheader("🧾 审计日志（最近 20 条）")
    from agents.audit import read_audit
    logs = read_audit(20)
    if logs:
        st.dataframe([{
            "node": l["node"], "input_hash": l["input_hash"],
            "latency_ms": l.get("latency_ms"),
            "timestamp": l["timestamp"][:19],
        } for l in logs])


if __name__ == "__main__":
    main()
