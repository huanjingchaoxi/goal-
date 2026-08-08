"""
Step 4.2: 维修方案 Agent
========================
职责: 根据故障诊断结果，生成具体的维修操作步骤、所需工具、备件清单及风险提示
输出: 维修方案（符合数据契约 4.2）
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# ========== 知识库模块（懒加载） ==========
_kb_vectorstore = None

def get_kb_vectorstore():
    """懒加载知识库"""
    global _kb_vectorstore
    if _kb_vectorstore is None:
        try:
            from langchain_community.vectorstores import Chroma
            from langchain_community.embeddings import HuggingFaceEmbeddings
            import os
            kb_path = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={
                  "device": "cpu",
                  "local_files_only": True   # 强制使用本地缓存，不联网
                 },
                encode_kwargs={"normalize_embeddings": True}
            )
            _kb_vectorstore = Chroma(
                persist_directory=kb_path,
                embedding_function=embeddings
            )
        except Exception as e:
            print(f"⚠️ 知识库加载失败: {e}")
            _kb_vectorstore = None
    return _kb_vectorstore

def search_knowledge(query: str, k: int = 3):
    """从知识库检索相关片段"""
    vectorstore = get_kb_vectorstore()
    if vectorstore is None:
        return []
    docs = vectorstore.similarity_search(query, k=k)
    return [doc.page_content for doc in docs]
# ========== 知识库模块结束 ==========


class MaintenancePlanAgent:
    def __init__(self, llm_client=None):
        self.llm = llm_client

    def generate_plan(self, diagnosis: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据诊断结果生成维修方案
        优先级：LLM + 知识库 → 规则引擎
        """
        fault_type = diagnosis.get("fault_type", "未知故障")
        severity = diagnosis.get("severity", "medium")
        confidence = diagnosis.get("confidence", 0.5)
        conclusion = diagnosis.get("conclusion", "")
        recommended_action = diagnosis.get("recommended_action", "inspect")

        # ===== 🆕 新增：先从知识库检索相关内容 =====
        kb_results = search_knowledge(fault_type, k=2)
        if kb_results:
            diagnosis["_kb_context"] = "\n\n".join(kb_results)
            # 尝试用 LLM + 知识库生成
            if self.llm and self.llm.available:
                llm_plan = self._generate_with_llm_and_kb(diagnosis, kb_results)
                if llm_plan:
                    return self._build_response(diagnosis, llm_plan)

        # ===== 原有逻辑：直接调用 LLM（不用知识库）=====
        if self.llm and self.llm.available:
            llm_plan = self._generate_with_llm(diagnosis)
            if llm_plan:
                return self._build_response(diagnosis, llm_plan)

        # ===== 规则兜底 =====
        return self._generate_by_rules(diagnosis)

    # ===== 🆕 新增：基于知识库的 LLM 生成 =====
    def _generate_with_llm_and_kb(self, diagnosis: Dict[str, Any], kb_results: List[str]) -> Optional[Dict[str, Any]]:
        """基于知识库检索结果调用 LLM 生成维修方案"""
        if not self.llm or not self.llm.available:
            return None
        
        context = "\n\n".join(kb_results)
        prompt = f"""你是一位资深的数控机床维修工程师。请基于以下知识库内容和诊断信息，生成专业的维修方案。

【知识库参考】（来源：Sandvik 铣削技术指南）
{context}

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

    # ===== 原有方法保持不变 =====
    def _generate_with_llm(self, diagnosis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """调用 LLM 生成维修方案（无知识库）"""
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