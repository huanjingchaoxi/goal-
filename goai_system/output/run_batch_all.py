"""
批量跑全量事件流，输出汇总与结果文件（供 Demo/UI/论文使用）
============================================================
用法: python output/run_batch_all.py [--max-events N]
输出:
  - output/pipeline_results.json : 所有事件的完整处理结果
  - output/pipeline_summary.json : 汇总统计
"""
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agents.workflow import run_batch, build_graph


def main(max_events=None):
    app, agents = build_graph()
    print(f"LLM: {'✅ DeepSeek' if agents['llm'].available else '⚠️ 规则兜底'} ({agents['llm'].model})")

    t0 = time.time()
    results = run_batch(max_events=max_events)
    elapsed = time.time() - t0

    # 汇总（防御 None 值）
    n = len(results)
    n_pass = sum(1 for r in results if (r.get("screening_result") or {}).get("decision") == "pass")
    n_filter = sum(1 for r in results if (r.get("screening_result") or {}).get("decision") == "filter")
    n_diag = sum(1 for r in results if r.get("diagnosis"))
    n_wo = sum(1 for r in results if r.get("work_order"))
    n_wo_approve = sum(1 for r in results if (r.get("work_order") or {}).get("required_approval"))
    n_wo_auto = sum(1 for r in results if (r.get("work_order") or {}).get("status") == "auto_approved")
    n_kn = sum(1 for r in results if r.get("knowledge_entry"))

    summary = {
        "events_processed": n,
        "screening_pass": n_pass,
        "screening_filter": n_filter,
        "diagnosed": n_diag,
        "work_orders": n_wo,
        "work_orders_need_approval": n_wo_approve,
        "work_orders_auto_approved": n_wo_auto,
        "knowledge_entries": n_kn,
        "elapsed_sec": round(elapsed, 1),
        "llm_available": agents["llm"].available,
        "model": agents["llm"].model,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    out_dir = Path(__file__).resolve().parent
    with open(out_dir / "pipeline_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(out_dir / "pipeline_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n===== 流水线全量汇总 =====")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\n结果已保存: {out_dir / 'pipeline_results.json'}")
    return summary


if __name__ == "__main__":
    max_events = None
    if "--max-events" in sys.argv:
        max_events = int(sys.argv[sys.argv.index("--max-events") + 1])
    main(max_events=max_events)
