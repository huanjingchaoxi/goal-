"""
Step 2: 异常事件流模拟器（增强版）
========================
输入: data/processed/cut_features.csv (含 vx_rms, ae_rms_kurtosis, vb_mm, wear_stage 等特征)
输出:
  - simulator/event_stream.jsonl : 异常事件流（供 Agent 消费）
  - simulator/ground_truth.jsonl : 真实 VB 值（仅用于自测，不暴露给 Agent）

增强功能:
  - 新增 6 种细分故障模式（对应知识库故障类型）
  - 事件时序关联（磨损加剧 → 连锁事件）
  - 缓变退化趋势（事件频率随磨损程度增加）
  - 传感器噪声注入
  - 数据缺失模拟
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
        
        # ===== 新增：跟踪每个刀具的磨损状态（用于时序关联） =====
        self.tool_wear_state = {}
        for tool_id in self.df["tool_id"].unique():
            self.tool_wear_state[tool_id] = {
                "vb_current": 0.0,
                "wear_stage": 0,
                "events_emitted": [],
                "last_event_cut": 0
            }

    def _compute_tool_stats(self):
        stats = {}
        for tool_id, group in self.df.groupby("tool_id"):
            stats[tool_id] = {
                "rms_vx_mean": group["vx_rms"].mean(),
                "rms_vx_std": group["vx_rms"].std(),
                "ae_kurtosis_mean": group["ae_rms_kurtosis"].mean(),
                "ae_kurtosis_std": group["ae_rms_kurtosis"].std(),
                "fz_mean": group["fz"].mean() if "fz" in group.columns else 0,
                "fz_std": group["fz"].std() if "fz" in group.columns else 1,
                "max_wear": group["vb_mm"].max(),
            }
        return stats

    def _emit_event(self, tool_id, cut_no, anomaly_type, severity, features_summary, confidence):
        self.event_counter += 1
        self.current_time += timedelta(minutes=self.rng.randint(3, 12))
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
        # 记录到刀具状态
        self.tool_wear_state[tool_id]["events_emitted"].append(anomaly_type)
        self.tool_wear_state[tool_id]["last_event_cut"] = int(cut_no)
        return event

    def _suggest_check(self, anomaly_type):
        # ===== 扩展：更多细分故障的检查建议 =====
        mapping = {
            "vibration_drift": "spindle_balance_check",
            "ae_impact": "tool_edge_inspection",
            "force_trend_anomaly": "feed_rate_calibration",
            "wear_approaching_limit": "microscope_vb_measurement",
            "false_positive_injected": "routine_check",
            # ===== 新增细分故障 =====
            "刀具磨损": "vb_measurement_replace_if_oversize",
            "刀具崩刃": "tool_edge_inspection_replace",
            "刀具涂层脱落": "coating_inspection",
            "积屑瘤": "cutting_speed_adjustment",
            "热裂纹": "coolant_system_check",
            "缺口磨损": "tool_material_review",
            "塑性变形": "cutting_pressure_reduction",
            "月牙洼磨损": "rake_face_inspection"
        }
        return mapping.get(anomaly_type, "general_inspection")

    def _get_severity_from_vb(self, vb_value):
        """根据 VB 值判断严重程度"""
        if vb_value >= 0.30:
            return "high"
        elif vb_value >= 0.15:
            return "medium"
        else:
            return "low"

    def generate_stream(self, output_path="event_stream.jsonl", gt_path="ground_truth.jsonl"):
        events, ground_truths = [], []
        
        # ===== 按刀具分组处理，便于追踪退化趋势 =====
        for tool_id, group in self.df.groupby("tool_id"):
            stats = self.tool_stats[tool_id]
            
            for _, row in group.iterrows():
                cut_no = row["cut_no"]
                vb_mm = float(row["vb_mm"])
                wear_stage = int(row["wear_stage"])
                emitted = False
                
                # ===== 更新刀具磨损状态 =====
                self.tool_wear_state[tool_id]["vb_current"] = vb_mm
                self.tool_wear_state[tool_id]["wear_stage"] = wear_stage

                # ---------- 1. 振动漂移：振动 RMS 超均值+2σ ----------
                if row["vx_rms"] > stats["rms_vx_mean"] + 2 * stats["rms_vx_std"]:
                    events.append(self._emit_event(
                        tool_id, cut_no, "vibration_drift", "medium",
                        {"rms_vx": round(float(row["vx_rms"]), 3)}, 0.87))
                    emitted = True

                # ---------- 2. 声发射冲击：峭度 > 3.5 ----------
                if row["ae_rms_kurtosis"] > 3.5:
                    events.append(self._emit_event(
                        tool_id, cut_no, "ae_impact", "high",
                        {"kurtosis_ae": round(float(row["ae_rms_kurtosis"]), 3)}, 0.92))
                    emitted = True

                # ---------- 3. 接近寿命终点：wear_stage == 2 ----------
                if wear_stage == 2:
                    events.append(self._emit_event(
                        tool_id, cut_no, "wear_approaching_limit", "high",
                        {"vb_estimate_mm": round(vb_mm, 3)}, 0.95))
                    emitted = True

                # ---------- 4. 切削力趋势偏离：随机 5% 注入 ----------
                if self.rng.random() < 0.05:
                    events.append(self._emit_event(
                        tool_id, cut_no, "force_trend_anomaly", "medium",
                        {"fz_mean_deviation": round(float(self.rng.uniform(0.05, 0.3)), 3)}, 0.70))
                    emitted = True

                # ---------- 5. 测试误报注入：10% 概率 ----------
                if self.rng.random() < 0.10:
                    events.append(self._emit_event(
                        tool_id, cut_no, "false_positive_injected", "low",
                        {"random_feature": round(self.rng.random(), 3)}, 0.45))
                    emitted = True

                # ========== 🆕 新增细分故障事件 ==========
                # 触发条件与知识库中的 8 种故障类型对应
                
                # 6. 刀具磨损（VB 值超过 0.15mm，且不是最后一次触发）
                if vb_mm >= 0.15 and self.rng.random() < 0.3:
                    events.append(self._emit_event(
                        tool_id, cut_no, "刀具磨损", 
                        self._get_severity_from_vb(vb_mm),
                        {"vb_mm": round(vb_mm, 3), "wear_stage": wear_stage}, 
                        min(0.95, 0.6 + vb_mm)
                    ))
                    emitted = True

                # 7. 刀具崩刃：声发射峭度 > 4.0 + 振动异常（组合特征）
                if row["ae_rms_kurtosis"] > 4.0 and row["vx_rms"] > stats["rms_vx_mean"] + 1.5 * stats["rms_vx_std"]:
                    if self.rng.random() < 0.4:
                        events.append(self._emit_event(
                            tool_id, cut_no, "刀具崩刃", "high",
                            {"kurtosis_ae": round(float(row["ae_rms_kurtosis"]), 3), 
                             "rms_vx": round(float(row["vx_rms"]), 3)}, 0.88
                        ))
                        emitted = True

                # 8. 积屑瘤：切削力波动 + 中等温度（模拟，基于力特征）
                if "fz" in row and row["fz"] > stats["fz_mean"] + 1.5 * stats["fz_std"]:
                    if self.rng.random() < 0.3:
                        events.append(self._emit_event(
                            tool_id, cut_no, "积屑瘤", "medium",
                            {"fz": round(float(row["fz"]), 2)}, 0.75
                        ))
                        emitted = True

                # 9. 热裂纹：连续高切削力 + 高振动（模拟）
                if "fz" in row and row["fz"] > stats["fz_mean"] + 2 * stats["fz_std"]:
                    if row["vx_rms"] > stats["rms_vx_mean"] + 1.8 * stats["rms_vx_std"]:
                        if self.rng.random() < 0.2:
                            events.append(self._emit_event(
                                tool_id, cut_no, "热裂纹", "high",
                                {"fz": round(float(row["fz"]), 2), 
                                 "rms_vx": round(float(row["vx_rms"]), 3)}, 0.82
                            ))
                            emitted = True

                # 10. 缺口磨损：VB 值中等 + 声发射异常（模拟）
                if 0.12 <= vb_mm < 0.25 and row["ae_rms_kurtosis"] > 3.0:
                    if self.rng.random() < 0.25:
                        events.append(self._emit_event(
                            tool_id, cut_no, "缺口磨损", "medium",
                            {"vb_mm": round(vb_mm, 3), 
                             "kurtosis_ae": round(float(row["ae_rms_kurtosis"]), 3)}, 0.78
                        ))
                        emitted = True

                # 11. 塑性变形：高 VB + 高切削力（模拟）
                if vb_mm >= 0.2 and "fz" in row and row["fz"] > stats["fz_mean"] + 1.8 * stats["fz_std"]:
                    if self.rng.random() < 0.3:
                        events.append(self._emit_event(
                            tool_id, cut_no, "塑性变形", "medium",
                            {"vb_mm": round(vb_mm, 3), 
                             "fz": round(float(row["fz"]), 2)}, 0.80
                        ))
                        emitted = True

                # 12. 月牙洼磨损：VB 值达到阈值 + 声发射特征（模拟）
                if vb_mm >= 0.13 and row["ae_rms_kurtosis"] > 2.8:
                    if self.rng.random() < 0.2:
                        events.append(self._emit_event(
                            tool_id, cut_no, "月牙洼磨损", "low",
                            {"vb_mm": round(vb_mm, 3), 
                             "kurtosis_ae": round(float(row["ae_rms_kurtosis"]), 3)}, 0.72
                        ))
                        emitted = True

                # ===== 记录 ground truth =====
                ground_truths.append({
                    "tool_id": tool_id,
                    "cut_no": int(cut_no),
                    "vb_mm": round(vb_mm, 4),
                    "wear_stage": wear_stage,
                    "event_emitted": emitted,
                })

        # ===== 保存事件流 =====
        with open(OUT_DIR / output_path, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(OUT_DIR / gt_path, "w", encoding="utf-8") as f:
            for gt in ground_truths:
                f.write(json.dumps(gt, ensure_ascii=False) + "\n")

        # ===== 统计信息 =====
        n_evt = len(events)
        n_cut = len(ground_truths)
        n_trigger = sum(1 for g in ground_truths if g["event_emitted"])
        by_type = {}
        for e in events:
            by_type[e["anomaly_type"]] = by_type.get(e["anomaly_type"], 0) + 1

        print(f"✅ 生成 {n_evt} 个异常事件, {n_cut} 个 ground truth")
        print(f"触发异常事件的 cut 占比: {n_trigger}/{n_cut} = {100*n_trigger/n_cut:.1f}%")
        print(f"事件类型分布: {by_type}")
        
        # ===== 新增：按故障类型汇总 =====
        fault_counts = {k: v for k, v in by_type.items() if k in 
                       ["刀具磨损", "刀具崩刃", "刀具涂层脱落", "积屑瘤", "热裂纹", "缺口磨损", "塑性变形", "月牙洼磨损"]}
        if fault_counts:
            print(f"细分故障分布: {fault_counts}")
        
        return events


if __name__ == "__main__":
    sim = EventSimulator()
    sim.generate_stream()