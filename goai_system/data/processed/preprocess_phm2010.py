"""
Step 1: PHM2010 数据预处理 + 特征工程
=====================================
输入: data/raw/c1~c6/ 下的 PHM2010 原始数据（已从 archive 迁移）
  - data/raw/cN/cN_wear.csv         : cut, flute_1, flute_2, flute_3 (VB 磨损值, 单位 um)
  - data/raw/cN/cN/c_N_XXX.csv      : 每个 cut 的 7 通道时序信号 (Fx,Fy,Fz,Vx,Vy,Vz,AE_rms)
输出: data/processed/cut_features.csv + scaler.pkl

特征: 每通道 6 个时域特征 (mean, std, peak2peak, rms, skewness, kurtosis) x 7 通道 = 42 维
"""
import os
import sys
import pickle
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler
from pathlib import Path

# 原始数据根目录（项目内 data/raw）
RAW_ROOT = Path(__file__).resolve().parents[1] / "raw"
OUT_DIR = Path(__file__).resolve().parent
TOOLS = ["c1", "c2", "c3", "c4", "c5", "c6"]
CHANNELS = ["fx", "fy", "fz", "vx", "vy", "vz", "ae_rms"]

# 磨损阶段阈值 (mm)
STAGE_BOUNDS = {"initial": 0.05, "normal": 0.2}   # <0.05 初期, <0.2 正常, >=0.2 急剧


def label_wear_stage(vb_mm):
    if vb_mm < STAGE_BOUNDS["initial"]:
        return 0
    elif vb_mm < STAGE_BOUNDS["normal"]:
        return 1
    else:
        return 2


def extract_time_features(signal):
    """对单通道信号提取 6 个时域特征。signal: 1-D np.array"""
    n = len(signal)
    if n == 0:
        return {"mean": 0, "std": 0, "peak2peak": 0, "rms": 0, "skewness": 0, "kurtosis": 0}
    return {
        "mean": float(np.mean(signal)),
        "std": float(np.std(signal)),
        "peak2peak": float(np.ptp(signal)),
        "rms": float(np.sqrt(np.mean(signal ** 2))),
        "skewness": float(stats.skew(signal)),
        "kurtosis": float(stats.kurtosis(signal)),
    }


def load_cut_signal(tool_id, cut_no):
    """读取单个 cut 的 7 通道信号，返回 (N,7) ndarray。文件名为 c_{刀号}_{序号}.csv"""
    num = tool_id[1:]  # 'c1' -> '1'
    path = RAW_ROOT / tool_id / tool_id / f"c_{num}_{cut_no:03d}.csv"
    if not path.exists():
        raise FileNotFoundError(f"信号文件不存在: {path}")
    # PHM2010 信号文件无表头，7 列
    return pd.read_csv(path, header=None).values.astype(np.float64)


def load_wear(tool_id):
    """读取该刀具的磨损值表，返回 DataFrame[cut, vb_um, vb_mm]。
    若该刀无磨损标注（PHM2010 中 c2/c3/c5 无 VB 真值），返回 None。"""
    path = RAW_ROOT / tool_id / f"{tool_id}_wear.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    # 三刃取平均，um -> mm
    df["vb_mm"] = df[["flute_1", "flute_2", "flute_3"]].mean(axis=1) / 1000.0
    df = df.rename(columns={"cut": "cut_no"})
    return df


def process_tool(tool_id):
    """处理一把刀，返回特征行列表。无磨损标注的刀（c2/c3/c5）vb_mm=NaN, wear_stage=-1。"""
    wear = load_wear(tool_id)
    # 无磨损表时，从信号文件目录推断 cut 列表
    if wear is None:
        sig_dir = RAW_ROOT / tool_id / tool_id
        cut_list = sorted(int(p.stem.split("_")[-1]) for p in sig_dir.glob(f"c_{tool_id[1:]}_*.csv"))
        wear_iter = [{"cut_no": c, "vb_mm": float("nan")} for c in cut_list]
        labeled = False
    else:
        wear_iter = wear.to_dict("records")
        labeled = True

    rows = []
    for w in wear_iter:
        cut_no = int(w["cut_no"])
        try:
            sig = load_cut_signal(tool_id, cut_no)
        except FileNotFoundError as e:
            print(f"  [跳过] {e}", file=sys.stderr)
            continue
        vb = float(w["vb_mm"])
        features = {"tool_id": tool_id, "cut_no": cut_no,
                    "vb_mm": round(vb, 4),
                    "wear_stage": label_wear_stage(vb) if labeled else -1}
        # 裁剪到 min(实际行数, 全部) —— 信号长度可能不一致，特征统计不受影响
        for i, ch in enumerate(CHANNELS):
            tf = extract_time_features(sig[:, i])
            for k, v in tf.items():
                features[f"{ch}_{k}"] = v
        rows.append(features)
    return rows


def process_phm2010():
    print(f"原始数据目录: {RAW_ROOT}")
    print(f"工具: {TOOLS}")
    all_rows = []
    for tool_id in TOOLS:
        rows = process_tool(tool_id)
        all_rows.extend(rows)
        n_stage0 = sum(1 for r in rows if r["wear_stage"] == 0)
        n_stage1 = sum(1 for r in rows if r["wear_stage"] == 1)
        n_stage2 = sum(1 for r in rows if r["wear_stage"] == 2)
        print(f"  {tool_id}: {len(rows)} cuts  (初期{n_stage0} / 正常{n_stage1} / 急剧{n_stage2})")

    df = pd.DataFrame(all_rows)
    if df.empty:
        raise RuntimeError("没有生成任何特征！请检查 RAW_ROOT 路径。")

    # 标准化数值特征（不含 tool_id/cut_no/vb_mm/wear_stage）
    feature_cols = [c for c in df.columns if c not in ["tool_id", "cut_no", "vb_mm", "wear_stage"]]
    scaler = StandardScaler()
    df_scaled = df.copy()
    df_scaled[feature_cols] = scaler.fit_transform(df[feature_cols])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df_scaled.to_csv(OUT_DIR / "cut_features.csv", index=False)
    with open(OUT_DIR / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    print(f"\n处理完成: {len(df)} 个 cut, {len(feature_cols)} 维特征")
    print(f"输出: {OUT_DIR / 'cut_features.csv'}")
    # 验收: wear_stage 分布
    print("\n[验收] wear_stage 分布:")
    print(df["wear_stage"].value_counts().sort_index().to_string())
    return df


if __name__ == "__main__":
    df = process_phm2010()
