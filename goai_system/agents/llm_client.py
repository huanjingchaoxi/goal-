"""
DeepSeek LLM 客户端封装
=======================
- 使用 OpenAI 兼容接口调用 DeepSeek（model: deepseek-chat）
- API Key 发现顺序: 环境变量 DEEPSEEK_API_KEY / ANTHROPIC_AUTH_TOKEN
  -> 用户 ~/.claude/settings.json 中的 ANTHROPIC_AUTH_TOKEN
- 无 Key 时 available=False，调用方应使用规则兜底（各 Agent 已内置）
"""
import os
import json
import requests
from pathlib import Path


class LLMClient:
    def __init__(self, provider="deepseek", model="deepseek-chat",
                 base_url="https://api.deepseek.com", api_key=None):
        self.provider = provider
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or self._discover_key()
        self.available = bool(self.api_key)

    @staticmethod
    def _discover_key():
        for var in ("DEEPSEEK_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
            key = os.getenv(var)
            if key:
                return key
        settings = Path.home() / ".claude" / "settings.json"
        if settings.exists():
            try:
                cfg = json.loads(settings.read_text(encoding="utf-8"))
                return cfg.get("env", {}).get("ANTHROPIC_AUTH_TOKEN")
            except Exception:
                pass
        return None

    def chat(self, prompt, temperature=0.3, max_tokens=1500, response_format=None):
        """返回文本；无 Key 或调用失败返回 None。"""
        if not self.available:
            return None
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=90)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[LLMClient] 调用失败: {e}")
            return None

    def chat_json(self, prompt, max_tokens=1500):
        """返回解析后的 JSON dict；失败返回 None。"""
        out = self.chat(prompt, max_tokens=max_tokens,
                        response_format={"type": "json_object"})
        if out is None:
            return None
        try:
            return json.loads(out)
        except Exception:
            return {"raw": out}
