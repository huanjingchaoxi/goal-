"""
生成 Demo 材料包
================
输出（output/ 目录）:
  - demo/wear_curves.png          : 磨损曲线（c1/c4/c6 三阶段）
  - demo/wear_stage_dist.png      : 磨损阶段分布
  - demo/event_dist.png           : 异常事件类型分布
  - demo/pipeline_summary.png     : 流水线结果汇总（含工单审批）
  - demo/demo_report.html         : 静态 Demo 报告（可离线打开）
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Windows 中文字体
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "demo"
OUT.mkdir(parents=True, exist_ok=True)

TOOL_COLORS = {"c1": "#d62728", "c4": "#1f77b4", "c6": "#2ca02c"}


def fig_wear_curves():
    df = pd.read_csv(BASE / "data/processed/cut_features.csv")
    labeled = df[df["wear_stage"] >= 0]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for tool in ["c1", "c4", "c6"]:
        sub = labeled[labeled["tool_id"] == tool].sort_values("cut_no")
        ax.plot(sub["cut_no"], sub["vb_mm"] * 1000, color=TOOL_COLORS[tool],
                label=tool, linewidth=1.8)
    ax.axhline(200, color="red", linestyle="--", alpha=0.7, label="急剧磨损阈值 (0.2mm)")
    ax.set_xlabel("切削行程 cut 序号")
    ax.set_ylabel("后刀面磨损 VB (μm)")
    ax.set_title("刀具磨损曲线（c1/c4/c6 标注刀）— 初期/正常/急剧三阶段")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "wear_curves.png", dpi=150)
    plt.close(fig)


def fig_wear_stage_dist():
    df = pd.read_csv(BASE / "data/processed/cut_features.csv")
    stages = df[df["wear_stage"] >= 0]["wear_stage"]
    counts = [int((stages == i).sum()) for i in (0, 1, 2)]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(["初期\n(VB<0.05mm)", "正常\n(0.05~0.2mm)", "急剧\n(VB>=0.2mm)"],
                  counts, color=["#4caf50", "#ff9800", "#f44336"])
    for b, c in zip(bars, counts):
        ax.text(b.get_x() + b.get_width() / 2, c + 3, str(c), ha="center")
    ax.set_title("磨损阶段分布（标注刀 c1/c4/c6）")
    ax.set_ylabel("cut 数量")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "wear_stage_dist.png", dpi=150)
    plt.close(fig)


def fig_event_dist():
    events = []
    with open(BASE / "simulator/event_stream.jsonl", encoding="utf-8") as f:
        events = [json.loads(l) for l in f if l.strip()]
    from collections import Counter
    cnt = Counter(e["anomaly_type"] for e in events)
    labels_cn = {
        "vibration_drift": "振动漂移",
        "ae_impact": "声发射冲击",
        "force_trend_anomaly": "切削力趋势偏离",
        "wear_approaching_limit": "磨损接近极限",
        "false_positive_injected": "测试误报注入",
    }
    keys = [k for k in cnt.keys()]
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar([labels_cn.get(k, k) for k in keys], [cnt[k] for k in keys],
                  color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#999999"])
    for b, k in zip(bars, keys):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2, str(cnt[k]), ha="center")
    ax.set_title("异常事件类型分布（共 %d 个事件）" % len(events))
    ax.set_ylabel("事件数量")
    plt.xticks(rotation=15)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "event_dist.png", dpi=150)
    plt.close(fig)


def fig_pipeline_summary():
    summary_path = BASE / "output/pipeline_summary.json"
    if not summary_path.exists():
        return
    s = json.loads(summary_path.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # 左: 筛选 vs 诊断
    ax = axes[0]
    ax.bar(["通过研判", "过滤"], [s["screening_pass"], s["screening_filter"]],
           color=["#4caf50", "#9e9e9e"])
    for i, v in enumerate([s["screening_pass"], s["screening_filter"]]):
        ax.text(i, v + 3, str(v), ha="center")
    ax.set_title("异常研判 Agent 决策")
    ax.set_ylabel("事件数")
    ax.grid(axis="y", alpha=0.3)

    # 右: 工单审批
    ax = axes[1]
    ax.bar(["需人工审批", "自动批准"],
           [s["work_orders_need_approval"], s["work_orders_auto_approved"]],
           color=["#f44336", "#4caf50"])
    for i, v in enumerate([s["work_orders_need_approval"], s["work_orders_auto_approved"]]):
        ax.text(i, v + 2, str(v), ha="center")
    ax.set_title("维修工单审批情况（共 %d）" % s["work_orders"])
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "pipeline_summary.png", dpi=150)
    plt.close(fig)


def build_html_report():
    results_path = BASE / "output/pipeline_results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    summary = json.loads((BASE / "output/pipeline_summary.json").read_text(encoding="utf-8"))

    # 取 5 个样例结果展示
    samples = [r for r in results if r.get("diagnosis")][:5]
    sample_html = ""
    for r in samples:
        ev = r["event"]
        d = r.get("diagnosis", {})
        wo = r.get("work_order", {})
        ev_html = (f"<b>{ev.get('anomaly_type')}</b> · {ev.get('tool_id')} "
                   f"cut{ev.get('cut_no')} · 置信度 {ev.get('confidence')}")
        diag_html = f"<i>{d.get('conclusion', '-')}</i>（置信度 {d.get('confidence')}，RUL {d.get('rul_estimate_hours')}h）"
        wo_html = f"风险 {wo.get('risk_level')} / {wo.get('status')}"
        sample_html += f"""<div class="card">
            <div class="ev">{ev_html}</div>
            <div class="diag">🩺 {diag_html}</div>
            <div class="wo">📋 {wo_html}</div></div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>刀锋智维 · GOAI Demo 报告</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 960px; margin: 24px auto; padding: 0 16px; color: #222; }}
h1 {{ color: #1565c0; }} h2 {{ color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 6px; }}
.card {{ border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px 16px; margin: 10px 0; }}
.ev {{ font-weight: bold; color: #d32f2f; }} .diag {{ margin-top: 6px; }} .wo {{ margin-top: 4px; color: #555; }}
.stats {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.stat {{ background: #f5f5f5; border-radius: 8px; padding: 12px 18px; }}
.stat b {{ font-size: 22px; color: #1565c0; display: block; }}
img {{ max-width: 100%; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.15); }}
.fig {{ margin: 18px 0; }}
</style></head><body>
<h1>🛠 刀锋智维 · 数控刀具多智能体运维系统</h1>
<p>GOAI 无界应用大赛 · AI+工业制造赛道 — 异常发现 → 故障诊断 → 维修调度 → 知识沉淀</p>

<h2>一、系统总览（全量批处理结果）</h2>
<div class="stats">
  <div class="stat"><b>{summary['events_processed']}</b>事件处理</div>
  <div class="stat"><b>{summary['screening_pass']}</b>通过研判</div>
  <div class="stat"><b>{summary['diagnosed']}</b>故障诊断</div>
  <div class="stat"><b>{summary['work_orders']}</b>维修工单</div>
  <div class="stat"><b>{summary['knowledge_entries']}</b>知识沉淀</div>
</div>

<h2>二、关键图表</h2>
<div class="fig"><img src="wear_curves.png" alt="磨损曲线"></div>
<div class="fig"><img src="event_dist.png" alt="事件分布"></div>
<div class="fig"><img src="pipeline_summary.png" alt="流水线汇总"></div>

<h2>三、诊断样例</h2>
{sample_html}

<h2>四、审计日志（防篡改）</h2>
<p>每个 Agent 节点记录 <code>timestamp / input_hash(SHA256) / output / latency_ms</code>，见 <code>logs/audit.jsonl</code>。</p>
</body></html>"""
    (OUT / "demo_report.html").write_text(html, encoding="utf-8")
    print(f"Demo 报告: {OUT / 'demo_report.html'}")


if __name__ == "__main__":
    fig_wear_curves()
    fig_wear_stage_dist()
    fig_event_dist()
    fig_pipeline_summary()
    build_html_report()
    print("图表已生成:")
    for p in sorted(OUT.glob("*")):
        print(f"  {p.name} ({p.stat().st_size/1024:.0f} KB)")
