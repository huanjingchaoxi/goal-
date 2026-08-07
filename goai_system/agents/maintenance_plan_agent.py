"""
Step 4.2: 维修方案 Agent
========================
职责: 根据故障诊断结果，生成具体的维修操作步骤、所需工具、备件清单及风险提示
输出: 维修方案（符合数据契约 4.2）
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any


class MaintenancePlanAgent:
    def __init__(self, llm_client=None):
        self.llm = llm_client

    def generate_plan(self, diagnosis: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据诊断结果生成维修方案

        Args:
            diagnosis: 诊断结果字典，包含:
                - tool_id: 刀具编号
                - fault_type: 故障类型
                - confidence: 置信度 (0-1)
                - severity: 严重程度 (low/medium/high)
                - diagnosis_id: 诊断ID
                - event_id: 事件ID
                - recommended_action: 推荐操作
                - conclusion: 诊断结论

        Returns:
            维修方案字典:
                - plan_id: 方案ID
                - diagnosis_id: 关联的诊断ID
                - tool_id: 刀具编号
                - fault_type: 故障类型
                - severity: 严重程度
                - steps: 维修步骤列表
                - required_tools: 所需工具列表
                - required_parts: 所需备件列表
                - estimated_time_min: 预估维修时间(分钟)
                - risk_level: 风险等级 (low/medium/high)
                - safety_notes: 安全注意事项
                - created_at: 创建时间
        """
        fault_type = diagnosis.get("fault_type", "未知故障")
        severity = diagnosis.get("severity", "medium")
        confidence = diagnosis.get("confidence", 0.5)
        conclusion = diagnosis.get("conclusion", "")
        recommended_action = diagnosis.get("recommended_action", "inspect")

        # 尝试用 LLM 生成更详细的方案
        llm_plan = None
        if self.llm and self.llm.available:
            llm_plan = self._generate_with_llm(diagnosis)

        if llm_plan:
            return self._build_response(diagnosis, llm_plan)

        # 规则兜底：根据故障类型和严重程度生成方案
        return self._generate_by_rules(diagnosis)

    def _generate_with_llm(self, diagnosis: Dict[str, Any]) -> Optional[str]:
        """调用 LLM 生成维修方案"""
        prompt = f"""你是一位资深的数控机床维修工程师。请根据以下诊断信息，生成一份专业的维修方案。

【诊断信息】
- 刀具编号: {diagnosis.get('tool_id', '未知')}
- 故障类型: {diagnosis.get('fault_type', '未知')}
- 严重程度: {diagnosis.get('severity', 'medium')}
- 置信度: {diagnosis.get('confidence', 0.5)}
- 诊断结论: {diagnosis.get('conclusion', '')}
- 推荐操作: {diagnosis.get('recommended_action', 'inspect')}

请按以下 JSON 格式输出（不要输出其他内容）：
{{
    "steps": ["步骤1", "步骤2", ...],
    "required_tools": ["工具1", "工具2", ...],
    "required_parts": ["备件1", "备件2", ...],
    "estimated_time_min": 30,
    "risk_level": "low/medium/high",
    "safety_notes": "安全注意事项"
}}"""
        return self.llm.chat_json(prompt)

    def _generate_by_rules(self, diagnosis: Dict[str, Any]) -> Dict[str, Any]:
        """规则兜底：根据故障类型生成方案"""
        fault_type = diagnosis.get("fault_type", "未知故障")
        severity = diagnosis.get("severity", "medium")
        tool_id = diagnosis.get("tool_id", "unknown")
        diagnosis_id = diagnosis.get("diagnosis_id", f"diag_{datetime.now().strftime('%Y%m%d%H%M%S')}")

        # 根据故障类型定义维修方案模板
        templates = {
            "刀具磨损": {
                "steps": [
                    "停机并拆卸刀具，检查刀片磨损情况",
                    "使用千分尺测量后刀面磨损带宽度(VB值)",
                    "若VB值超过0.3mm，更换新刀片",
                    "安装新刀片后，以50%切削用量进行试切",
                    "测量试切件尺寸，确认加工精度达标"
                ],
                "tools": ["千分尺", "扭矩扳手", "拆卸工具"],
                "parts": ["备用刀片(型号匹配)"],
                "time": 30,
                "risk": "medium" if severity == "high" else "low",
                "safety": "更换刀具前确保设备完全停机并上锁挂牌"
            },
            "刀具崩刃": {
                "steps": [
                    "立即停机，检查刀具是否完全断裂",
                    "清理切削区域内的碎片和切屑",
                    "检查工件表面是否有划伤或崩损",
                    "更换新刀具，检查刀柄和主轴锥孔是否有损伤",
                    "调整切削参数，适当降低进给量和切削深度"
                ],
                "tools": ["内六角扳手", "清洁刷", "放大镜"],
                "parts": ["新刀具(同型号)"],
                "time": 45,
                "risk": "high",
                "safety": "崩刃可能产生飞溅碎片，操作前必须佩戴防护眼镜"
            },
            "刀具涂层脱落": {
                "steps": [
                    "停机检查刀具涂层脱落面积和位置",
                    "若脱落面积小于30%，可继续使用并加强监测",
                    "若脱落面积大于30%，建议更换刀具",
                    "检查切削液浓度和流量是否正常",
                    "适当提高切削速度以减少切削力"
                ],
                "tools": ["放大镜", "切削液浓度计"],
                "parts": ["备用涂层刀具"],
                "time": 20,
                "risk": "low",
                "safety": "注意切削液飞溅，保持防护门关闭"
            }
        }

        template = templates.get(fault_type, {
            "steps": [
                "停机检查刀具状态",
                "根据诊断结论进行针对性处理",
                f"执行推荐操作: {diagnosis.get('recommended_action', 'inspect')}",
                "确认问题解决后恢复生产"
            ],
            "tools": ["标准工具包"],
            "parts": [],
            "time": 30,
            "risk": "medium",
            "safety": "操作前请参考设备操作手册"
        })

        return {
            "plan_id": f"plan_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "diagnosis_id": diagnosis_id,
            "tool_id": tool_id,
            "fault_type": fault_type,
            "severity": severity,
            "steps": template["steps"],
            "required_tools": template["tools"],
            "required_parts": template["parts"],
            "estimated_time_min": template["time"],
            "risk_level": template["risk"],
            "safety_notes": template["safety"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

    def _build_response(self, diagnosis: Dict[str, Any], llm_result: Dict[str, Any]) -> Dict[str, Any]:
        """构建标准响应格式"""
        return {
            "plan_id": f"plan_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "diagnosis_id": diagnosis.get("diagnosis_id", f"diag_{datetime.now().strftime('%Y%m%d%H%M%S')}"),
            "tool_id": diagnosis.get("tool_id", "unknown"),
            "fault_type": diagnosis.get("fault_type", "未知故障"),
            "severity": diagnosis.get("severity", "medium"),
            "steps": llm_result.get("steps", ["检查刀具状态", "执行维修操作", "验证修复效果"]),
            "required_tools": llm_result.get("required_tools", []),
            "required_parts": llm_result.get("required_parts", []),
            "estimated_time_min": llm_result.get("estimated_time_min", 30),
            "risk_level": llm_result.get("risk_level", "medium"),
            "safety_notes": llm_result.get("safety_notes", "操作前请参考设备操作手册"),
            "created_at": datetime.now(timezone.utc).isoformat()
        }