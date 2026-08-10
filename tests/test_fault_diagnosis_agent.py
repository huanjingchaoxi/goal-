"""单元测试：FaultDiagnosisAgent 的 fault_type 链路（维修方案 Agent 依赖此字段）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from goai_system.agents.fault_diagnosis_agent import (
    FaultDiagnosisAgent,
    ANOMALY_TO_FAULT,
    KNOWN_FAULT_TYPES,
)


class _NoLLM:
    """模拟不可用的 LLM 客户端，走规则兜底路径。"""

    available = False

    def chat_json(self, prompt, max_tokens=1000):
        return None


class TestFaultTypeMapping:
    def setup_method(self):
        self.agent = FaultDiagnosisAgent(_NoLLM(), None)

    def test_chinese_anomaly_maps_to_fault_type(self):
        for atype in [
            "刀具磨损", "刀具崩刃", "刀具涂层脱落", "积屑瘤",
            "热裂纹", "缺口磨损", "塑性变形", "月牙洼磨损",
        ]:
            report = self.agent.diagnose({
                "event_id": f"e_{atype}", "anomaly_type": atype,
                "severity": "high", "confidence": 0.9,
            })
            assert report["fault_type"] == atype, atype

    def test_english_anomaly_maps_to_fault_type(self):
        cases = {
            "vibration_drift": "刀具磨损",
            "ae_impact": "刀具崩刃",
            "force_trend_anomaly": "积屑瘤",
            "wear_approaching_limit": "刀具磨损",
        }
        for atype, expected in cases.items():
            report = self.agent.diagnose({
                "event_id": "e1", "anomaly_type": atype,
                "severity": "high", "confidence": 0.9,
            })
            assert report["fault_type"] == expected, atype

    def test_unknown_anomaly_falls_back(self):
        report = self.agent.diagnose({
            "event_id": "e1", "anomaly_type": "weird_thing",
            "severity": "high", "confidence": 0.9,
        })
        assert report["fault_type"] in KNOWN_FAULT_TYPES | {"未知故障"}

    def test_mapping_has_all_known_types(self):
        assert KNOWN_FAULT_TYPES <= set(ANOMALY_TO_FAULT)


if __name__ == "__main__":
    t = TestFaultTypeMapping()
    for name in dir(t):
        if name.startswith("test_"):
            t.setup_method()
            getattr(t, name)()
            print(f"✅ {name}")
