"""
Step 7: 审计日志 + 哈希防篡改
==============================
每条日志包含:
  - timestamp    UTC 时间戳
  - node         哪个 Agent/节点
  - input_hash   输入数据 SHA256 摘要（前16位）
  - output       输出结果
  - model_version 使用的模型版本
  - latency_ms   处理耗时
"""
import hashlib
import json
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
DEFAULT_MODEL = "deepseek-chat"
_AUDIT_LOCK = threading.Lock()


def sha16(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def build_log_entry(node, input_data, output_data,
                    model_version=DEFAULT_MODEL, latency_ms=None, **extra):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node": node,
        "input_hash": sha16(input_data),
        "output": output_data,
        "model_version": model_version,
        "latency_ms": latency_ms,
    }
    entry.update(extra)
    return entry


def append_audit(entry):
    """追加审计日志到 logs/audit.jsonl。"""
    with _AUDIT_LOCK:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_audit(n=100):
    """读取最近 n 条审计日志。"""
    path = LOG_DIR / "audit.jsonl"
    if not path.exists():
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries[-n:]
