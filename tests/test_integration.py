"""
集成测试：验证工作流功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from goai_system.agents.workflow import run_one, run_batch, build_graph, initial_state


class TestIntegration:
    """集成测试"""

    def test_run_one_exists(self):
        """测试 run_one 函数存在且可调用"""
        assert callable(run_one), "run_one 不是可调用对象"
        # 检查函数签名
        import inspect
        sig = inspect.signature(run_one)
        assert "event" in sig.parameters, "run_one 缺少 event 参数"
        print("✅ run_one 函数存在且签名正确")

    def test_run_batch_exists(self):
        """测试 run_batch 函数存在且可调用"""
        assert callable(run_batch), "run_batch 不是可调用对象"
        import inspect
        sig = inspect.signature(run_batch)
        # 检查是否有 events 或 max_events 参数
        params = list(sig.parameters.keys())
        assert len(params) > 0, "run_batch 没有参数"
        print("✅ run_batch 函数存在")

    def test_build_graph_structure(self):
        """测试 build_graph 返回正确的图结构"""
        app, agents = build_graph()
        # 检查 agents 字典是否包含所有关键 Agent
        expected_agents = ["screening", "diagnosis", "plan", "dispatch", "knowledge"]
        for name in expected_agents:
            assert name in agents, f"缺少 Agent: {name}"
        # 检查编译后的图是否有 invoke 方法
        assert hasattr(app, "invoke"), "编译后的图没有 invoke 方法"
        print("✅ 工作流图结构验证通过")

    def test_initial_state_structure(self):
        """测试 initial_state 返回正确的初始状态"""
        test_event = {"event_id": "test_001", "anomaly_type": "test"}
        state = initial_state(test_event)
        # 检查必要字段
        assert "event" in state
        assert "screening_result" in state
        assert "diagnosis" in state
        assert "plan_result" in state
        assert "work_order" in state
        assert "log" in state
        assert state["event"] == test_event
        print("✅ initial_state 结构正确")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])