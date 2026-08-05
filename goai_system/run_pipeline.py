"""
GOAI 一键流水线: Step1 预处理 -> Step2 事件流 -> Step3 知识库 -> Step4-5 Agent链
=============================================================================
用法: python run_pipeline.py [--max-events N]
"""
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def step1():
    print("\n[Step1] 数据预处理 + 特征工程")
    out = BASE_DIR / "data" / "processed" / "cut_features.csv"
    if out.exists():
        print(f"  已存在: {out}，跳过（删除文件可重新生成）")
        return
    sys.path.insert(0, str(BASE_DIR / "data" / "processed"))
    import preprocess_phm2010
    preprocess_phm2010.process_phm2010()


def step2():
    print("\n[Step2] 异常事件流模拟器")
    sys.path.insert(0, str(BASE_DIR / "simulator"))
    import event_generator
    sim = event_generator.EventSimulator()
    sim.generate_stream()


def step3():
    print("\n[Step3] 知识库构建")
    sys.path.insert(0, str(BASE_DIR / "knowledge_base"))
    import build_kb
    build_kb.build_kb()


def step4_5(max_events=None):
    print("\n[Step4-5] 四Agent链 + LangGraph 端到端")
    from agents.workflow import run_batch, build_graph
    app, agents = build_graph()
    print(f"  LLM: {'✅ DeepSeek' if agents['llm'].available else '⚠️ 规则兜底'} "
          f"({agents['llm'].model})")
    results = run_batch(max_events=max_events)
    n = len(results)
    n_diag = sum(1 for r in results if r.get("diagnosis"))
    n_wo = sum(1 for r in results if r.get("work_order"))
    n_kn = sum(1 for r in results if r.get("knowledge_entry"))
    n_approve = sum(1 for r in results
                    if r.get("work_order", {}).get("required_approval"))
    print(f"\n  ==== 流水线结果汇总 ====")
    print(f"  处理事件: {n}")
    print(f"  通过研判并诊断: {n_diag}")
    print(f"  生成工单: {n_wo}（其中需审批 {n_approve}）")
    print(f"  知识沉淀: {n_kn}")
    return results


if __name__ == "__main__":
    max_events = None
    if "--max-events" in sys.argv:
        max_events = int(sys.argv[sys.argv.index("--max-events") + 1])
    t0 = time.time()
    step1()
    step2()
    step3()
    results = step4_5(max_events=max_events)
    print(f"\n总耗时: {time.time() - t0:.1f}s")
