"""
Step 2: 异常事件流模拟器
========================
输入: data/processed/cut_features.csv (含 vx_rms, ae_rms_kurtosis, vb_mm, wear_stage 等特征)
输出:
  - simulator/event_stream.jsonl : 异常事件流（供 Agent 消费）
  - simulator/ground_truth.jsonl : 真实 VB 值（仅用于自测，不暴露给 Agent）

事件类型:
  - vibration_drift          : 振动 RMS 超 2σ → 主轴动平衡检查
  - ae_impact                : 声发射峭度 > 3.5 → 刀刃检查
  - force_trend_anomaly      : 切削力趋势偏离 → 进给校准 (5% 随机注入)
  - wear_approaching_limit   : VB > 0.25mm → 显微镜测磨损
  - false_positive_injected  : 10% 概率注入的测试误报 → 考验异常研判 Agent
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
FEATURES_PATH = BASE_DIR / "data" / "processed" / "cut_features.csv"
OUT_DIR = Path(__file__).resolve().parent

RANDOM_SEED = 42


class EventSimulator:
    def __init__(self, features_path=FEATURES_PATH, seed=RANDOM_SEED):
        self.df = pd.read_csv(features_path)
        self.rng = random.Random(seed)
        np.random.seed(seed)
        self.tool_stats = self._compute_tool_stats()
        self.event_counter = 0
        self.current_time = datetime(2026, 8, 5, 8, 0, 0)

    def _compute_tool_stats(self):
        stats = {}
        for tool_id, group in self.df.groupby("tool_id"):
            stats[tool_id] = {
                "rms_vx_mean": group["vx_rms"].mean(),
                "rms_vx_std": group["vx_rms"].std(),
                "ae_kurtosis_mean": group["ae_rms_kurtosis"].mean(),
                "ae_kurtosis_std": group["ae_rms_kurtosis"].std(),
            }
        return stats

    def _emit_event(self, tool_id, cut_no, anomaly_type, severity, features_summary, confidence):
        self.event_counter += 1
        self.current_time += timedelta(minutes=self.rng.randint(5, 15))
        event = {
            "event_id": f"evt_{self.current_time.strftime('%Y%m%d_%H%M%S')}_{self.event_counter:03d}",
            "timestamp": self.current_time.isoformat() + "Z",
            "tool_id": tool_id,
            "cut_no": int(cut_no),
            "anomaly_type": anomaly_type,
            "severity": severity,
            "features_summary": features_summary,
            "confidence": confidence,
            "suggested_check": self._suggest_check(anomaly_type),
        }
        return event

    def _suggest_check(self, anomaly_type):
        mapping = {
            "vibration_drift": "spindle_balance",
            "ae_impact": "tool_edge_inspection",
            "force_trend_anomaly": "feed_rate_calibration",
            "wear_approaching_limit": "microscope_vb_measurement",
            "false_positive_injected": "routine_check",
        }
        return mapping.get(anomaly_type, "general_inspection")

    def generate_stream(self, output_path="event_stream.jsonl", gt_path="ground_truth.jsonl"):
        events, ground_truths = [], []
        for _, row in self.df.iterrows():
            tool_id = row["tool_id"]
            cut_no = row["cut_no"]
            stats = self.tool_stats[tool_id]
            emitted = False

            # 1) 振动漂移: 振动 RMS 超均值+2σ
            if row["vx_rms"] > stats["rms_vx_mean"] + 2 * stats["rms_vx_std"]:
                events.append(self._emit_event(
                    tool_id, cut_no, "vibration_drift", "medium",
                    {"rms_vx": round(float(row["vx_rms"]), 3)}, 0.87))
                emitted = True

            # 2) 声发射冲击: 峭度 > 3.5
            if row["ae_rms_kurtosis"] > 3.5:
                events.append(self._emit_event(
                    tool_id, cut_no, "ae_impact", "high",
                    {"kurtosis_ae": round(float(row["ae_rms_kurtosis"]), 3)}, 0.92))
                emitted = True

            # 3) 接近寿命终点: 急剧磨损阶段 (wear_stage==2, VB>=0.2mm)
            #    注: PHM2010 标注刀 VB 最大约 0.22mm，故用阶段判定而非 0.25mm 阈值
            if row["wear_stage"] == 2:
                events.append(self._emit_event(
                    tool_id, cut_no, "wear_approaching_limit", "high",
                    {"vb_estimate_mm": round(float(row["vb_mm"]), 3)}, 0.95))
                emitted = True

            # 4) 切削力趋势偏离: 随机 5% 注入
            if self.rng.random() < 0.05:
                events.append(self._emit_event(
                    tool_id, cut_no, "force_trend_anomaly", "medium",
                    {"fz_mean_deviation": round(float(self.rng.uniform(0.05, 0.3)), 3)}, 0.70))
                emitted = True

            # 5) 测试误报注入: 10% 概率 (置信度低, 检验异常研判 Agent 过滤能力)
            if self.rng.random() < 0.10:
                events.append(self._emit_event(
                    tool_id, cut_no, "false_positive_injected", "low",
                    {"random_feature": round(self.rng.random(), 3)}, 0.45))
                emitted = True

            ground_truths.append({
                "tool_id": tool_id,
                "cut_no": int(cut_no),
                "vb_mm": round(float(row["vb_mm"]), 4),
                "wear_stage": int(row["wear_stage"]),
                "event_emitted": emitted,
            })

        with open(OUT_DIR / output_path, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(OUT_DIR / gt_path, "w", encoding="utf-8") as f:
            for gt in ground_truths:
                f.write(json.dumps(gt, ensure_ascii=False) + "\n")

        # 统计
        n_evt = len(events)
        n_cut = len(ground_truths)
        n_trigger = sum(1 for g in ground_truths if g["event_emitted"])
        by_type = {}
        for e in events:
            by_type[e["anomaly_type"]] = by_type.get(e["anomaly_type"], 0) + 1

        print(f"生成 {n_evt} 个异常事件, {n_cut} 个 ground truth")
        print(f"触发异常事件的 cut 占比: {n_trigger}/{n_cut} = {100*n_trigger/n_cut:.1f}%")
        print(f"事件类型分布: {by_type}")
        return events


if __name__ == "__main__":
    sim = EventSimulator()
    sim.generate_stream()
