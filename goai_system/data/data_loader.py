"""
数据加载优化：分块读取 + 特征缓存
"""
import pandas as pd
import numpy as np
from pathlib import Path
from functools import lru_cache
import pickle


DATA_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def load_features_cached(chunk_size: int = 10000):
    """缓存特征数据（首次加载后缓存到内存）"""
    features_path = PROCESSED_DIR / "cut_features.csv"
    
    if not features_path.exists():
        print(f"⚠️ 特征文件不存在: {features_path}")
        return None
    
    # 检查是否有缓存版本（Parquet 格式更快）
    parquet_path = PROCESSED_DIR / "cut_features.parquet"
    if parquet_path.exists():
        try:
            df = pd.read_parquet(parquet_path)
            print(f"✅ 从 Parquet 加载特征数据: {len(df)} 行")
            return df
        except Exception as e:
            print(f"⚠️ Parquet 加载失败: {e}")
    
    # 分块加载 CSV
    print(f"⏳ 分块加载 CSV: {features_path}")
    chunks = []
    total_rows = 0
    for chunk in pd.read_csv(features_path, chunksize=chunk_size):
        chunks.append(chunk)
        total_rows += len(chunk)
        print(f"   已加载 {total_rows} 行...")
    
    if not chunks:
        print("❌ 未加载到任何数据")
        return None
    
    df = pd.concat(chunks, ignore_index=True)
    
    # 保存为 Parquet 加速后续加载
    try:
        df.to_parquet(parquet_path, index=False)
        print(f"✅ 已保存 Parquet 缓存: {parquet_path}")
    except Exception as e:
        print(f"⚠️ Parquet 保存失败: {e}")
    
    print(f"✅ 加载完成: {len(df)} 行")
    return df


def get_feature_summary(tool_id: str) -> dict:
    """获取刀具特征摘要（用于模拟器）"""
    df = load_features_cached()
    if df is None:
        return {}
    
    tool_data = df[df["tool_id"] == tool_id]
    if tool_data.empty:
        return {}
    
    return {
        "mean_fx": float(tool_data["Fx"].mean()),
        "std_fx": float(tool_data["Fx"].std()),
        "mean_fy": float(tool_data["Fy"].mean()),
        "std_fy": float(tool_data["Fy"].std()),
        "mean_fz": float(tool_data["Fz"].mean()),
        "std_fz": float(tool_data["Fz"].std()),
        "max_vb": float(tool_data["vb_mm"].max()),
        "count": len(tool_data)
    }


def clear_data_cache():
    """清空数据缓存"""
    load_features_cached.cache_clear()
    parquet_path = PROCESSED_DIR / "cut_features.parquet"
    if parquet_path.exists():
        parquet_path.unlink()
    print("✅ 数据缓存已清空")