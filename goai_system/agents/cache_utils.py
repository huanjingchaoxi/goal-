"""
缓存工具：LLM 调用缓存 + 特征数据缓存
支持内存缓存 (LRU) 和磁盘缓存 (JSON)
"""
import hashlib
import json
import os
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict, Any

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_key(prompt: str, model: str = "default") -> str:
    """生成缓存键（基于 prompt 和 model）"""
    content = f"{model}:{prompt}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


class LLMCache:
    """LLM 调用缓存（内存 + 磁盘两级）"""
    
    def __init__(self, max_memory_size: int = 100):
        self.max_memory_size = max_memory_size
        self._memory_cache = {}
        self._hit_count = 0
        self._miss_count = 0
    
    def get(self, prompt: str, model: str = "default") -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        key = get_cache_key(prompt, model)
        
        # 1. 检查内存缓存
        if key in self._memory_cache:
            self._hit_count += 1
            return self._memory_cache[key]
        
        # 2. 检查磁盘缓存
        cache_file = CACHE_DIR / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                # 加载到内存缓存
                self._set_memory(key, result)
                self._hit_count += 1
                return result
            except:
                pass
        
        self._miss_count += 1
        return None
    
    def set(self, prompt: str, model: str, result: Dict[str, Any]):
        """保存缓存结果"""
        key = get_cache_key(prompt, model)
        
        # 保存到内存
        self._set_memory(key, result)
        
        # 保存到磁盘
        cache_file = CACHE_DIR / f"{key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def _set_memory(self, key: str, value: Dict[str, Any]):
        """内存缓存（LRU 淘汰）"""
        if len(self._memory_cache) >= self.max_memory_size:
            # 移除最早的一个
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]
        self._memory_cache[key] = value
    
    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hit_count + self._miss_count
        return {
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": self._hit_count / total if total > 0 else 0,
            "memory_size": len(self._memory_cache),
            "disk_files": len(list(CACHE_DIR.glob("*.json")))
        }
    
    def clear(self):
        """清空所有缓存"""
        self._memory_cache.clear()
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
        print("✅ 所有缓存已清空")


# 全局缓存实例
_llm_cache = LLMCache(max_memory_size=100)


def cached_llm_call(llm_client, prompt: str, max_tokens: int = 1000, 
                    use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    带缓存的 LLM 调用
    
    Args:
        llm_client: LLM 客户端（必须有 model 属性）
        prompt: 提示词
        max_tokens: 最大 token 数
        use_cache: 是否使用缓存
    
    Returns:
        LLM 返回的 JSON 结果
    """
    model = getattr(llm_client, 'model', 'default')
    
    if use_cache:
        # 尝试从缓存获取
        cached = _llm_cache.get(prompt, model)
        if cached is not None:
            return cached
    
    # 调用 LLM
    result = llm_client.chat_json(prompt, max_tokens=max_tokens)
    
    if use_cache and result is not None:
        _llm_cache.set(prompt, model, result)
    
    return result


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计（供 UI 调用）"""
    return _llm_cache.stats()