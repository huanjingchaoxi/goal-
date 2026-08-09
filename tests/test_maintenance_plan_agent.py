"""
单元测试：MaintenancePlanAgent
测试 generate_plan 方法在各种输入下的表现
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from goai_system.agents.maintenance_plan_agent import MaintenancePlanAgent


class TestMaintenancePlanAgent:
    """MaintenancePlanAgent 单元测试"""

    def setup_method(self):
        """每个测试方法执行前创建 Agent 实例"""
        self.agent = MaintenancePlanAgent()

    # ========== 测试 8 种内置故障类型 ==========
    def test_all_builtin_fault_types(self):
        """测试所有 8 种内置故障类型都能正常返回"""
        fault_types = [
            "刀具磨损", "刀具崩刃", "刀具涂层脱落",
            "积屑瘤", "热裂纹", "缺口磨损", "塑性变形", "月牙洼磨损"
        ]
        
        for ft in fault_types:
            diagnosis = {
                "fault_type": ft,
                "severity": "medium",
                "conclusion": f"测试结论: {ft}"
            }
            result = self.agent.generate_plan(diagnosis)
            
            # 断言：返回结果包含必要字段
            assert result is not None
            assert "plan_id" in result
            assert "steps" in result
            assert "required_tools" in result
            assert "required_parts" in result
            assert "risk_level" in result
            assert "safety_notes" in result
            
            # 断言：步骤列表不为空
            assert len(result["steps"]) > 0

    def test_unknown_fault_type(self):
        """测试未知故障类型应返回默认模板"""
        diagnosis = {
            "fault_type": "未知故障类型XYZ",
            "severity": "high"
        }
        result = self.agent.generate_plan(diagnosis)
        
        # 断言：返回默认模板（检查步骤中是否包含"标准工具包"）
        assert result["required_tools"] == ["标准工具包"]
        assert result["fault_type"] == "未知故障类型XYZ"

    # ========== 测试 severity 对 risk_level 的影响 ==========
    def test_severity_affects_risk_level(self):
        """测试 severity 参数正确影响 risk_level"""
        # high severity
        diagnosis = {"fault_type": "刀具磨损", "severity": "high"}
        result = self.agent.generate_plan(diagnosis)
        assert result["risk_level"] == "medium"  # 刀具磨损 high → medium
        
        # low severity
        diagnosis = {"fault_type": "刀具磨损", "severity": "low"}
        result = self.agent.generate_plan(diagnosis)
        assert result["risk_level"] == "low"

    # ========== 测试缺失字段 ==========
    def test_missing_fault_type(self):
        """测试缺少 fault_type 字段时的兜底行为"""
        diagnosis = {"severity": "high"}
        result = self.agent.generate_plan(diagnosis)
        
        # 断言：应使用默认模板
        assert result["fault_type"] == "未知故障"
        assert result["required_tools"] == ["标准工具包"]

    def test_empty_diagnosis(self):
        """测试空诊断输入"""
        diagnosis = {}
        result = self.agent.generate_plan(diagnosis)
        
        # 断言：应使用默认模板
        assert result["fault_type"] == "未知故障"
        assert "plan_id" in result

    # ========== 测试输出格式 ==========
    def test_output_format(self):
        """测试输出格式是否符合数据契约"""
        diagnosis = {
            "fault_type": "刀具崩刃",
            "severity": "high",
            "tool_id": "T001",
            "diagnosis_id": "diag_test_001"
        }
        result = self.agent.generate_plan(diagnosis)
        
        # 断言：所有必要字段存在且类型正确
        assert isinstance(result["plan_id"], str)
        assert isinstance(result["steps"], list)
        assert isinstance(result["required_tools"], list)
        assert isinstance(result["required_parts"], list)
        assert isinstance(result["estimated_time_min"], int)
        assert result["risk_level"] in ["low", "medium", "high"]
        assert result["severity"] == "high"
        assert result["tool_id"] == "T001"
        assert result["diagnosis_id"] == "diag_test_001"

    # ========== 测试特定故障类型的输出 ==========
    def test_specific_fault_types_output(self):
        """测试特定故障类型返回的步骤包含关键词"""
        test_cases = [
            ("刀具磨损", "VB值"),
            ("刀具崩刃", "停机"),
            ("积屑瘤", "切削速度"),
            ("热裂纹", "冷却"),
            ("月牙洼磨损", "涂层"),
        ]
        
        for fault_type, keyword in test_cases:
            diagnosis = {"fault_type": fault_type}
            result = self.agent.generate_plan(diagnosis)
            # 合并所有步骤为一个字符串
            steps_text = " ".join(result["steps"])
            assert keyword in steps_text, f"故障类型 '{fault_type}' 的步骤中未包含关键词 '{keyword}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])