"""
Step 4.2: 维修方案 Agent
========================
职责: 根据故障诊断结果，生成具体的维修操作步骤、所需工具、备件清单及风险提示
输出: 维修方案（符合数据契约 4.2）
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json
import re
import requests

# ========== Ollama 客户端（本地 LLM） ==========
class OllamaClient:
    def __init__(self, model="qwen2.5:7b"):
        self.model = model
        self.base_url = "http://localhost:11434/api/chat"
        self.available = True
    
    def chat_json(self, prompt, max_tokens=1000):
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3}
        }
        resp = requests.post(self.base_url, json=payload, timeout=120)
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        try:
            return json.loads(content)
        except:
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError("无法解析 LLM 返回的 JSON")

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
                model_kwargs={"device": "cpu"},
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
        优先级：知识库 + LLM → 纯 LLM → 规则引擎
        """
        fault_type = diagnosis.get("fault_type", "未知故障")
        severity = diagnosis.get("severity", "medium")
        confidence = diagnosis.get("confidence", 0.5)
        conclusion = diagnosis.get("conclusion", "")
        recommended_action = diagnosis.get("recommended_action", "inspect")

        # ===== 先从知识库检索相关内容 =====
        kb_results = search_knowledge(fault_type, k=2)
        if kb_results:
            diagnosis["_kb_context"] = "\n\n".join(kb_results)
            # 尝试用 LLM + 知识库生成
            if self.llm and self.llm.available:
                llm_plan = self._generate_with_llm_and_kb(diagnosis, kb_results)
                if llm_plan:
                    return self._build_response(diagnosis, llm_plan)

        # ===== 直接调用 LLM（不用知识库）=====
        if self.llm and self.llm.available:
            llm_plan = self._generate_with_llm(diagnosis)
            if llm_plan:
                return self._build_response(diagnosis, llm_plan)

        # ===== 规则兜底 =====
        return self._generate_by_rules(diagnosis)

    # ===== 基于知识库的 LLM 生成 =====
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

    # ===== 纯 LLM 生成（无知识库） =====
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

    # ===== 规则引擎（8 种故障类型） =====
    def _generate_by_rules(self, diagnosis: Dict[str, Any]) -> Dict[str, Any]:
        """规则兜底：根据故障类型生成方案"""
        fault_type = diagnosis.get("fault_type", "未知故障")
        severity = diagnosis.get("severity", "medium")
        tool_id = diagnosis.get("tool_id", "unknown")
        diagnosis_id = diagnosis.get("diagnosis_id", f"diag_{datetime.now().strftime('%Y%m%d%H%M%S')}")

        templates = {
            # --- 原有 3 种 ---
            "刀具磨损": {
                "steps": [
                    "停机并拆卸刀具，检查刀片磨损情况",
                    "使用千分尺测量后刀面磨损带宽度 (VB 值)",
                    "若 VB 值超过 0.3mm（依据 ISO 3685），更换新刀片",
                    "安装新刀片后，以 50% 切削用量进行试切",
                    "测量试切件尺寸，确认加工精度达标"
                ],
                "tools": ["千分尺", "扭矩扳手", "拆卸工具"],
                "parts": ["备用刀片 (型号匹配)"],
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
                "parts": ["新刀具 (同型号)"],
                "time": 45,
                "risk": "high",
                "safety": "崩刃可能产生飞溅碎片，操作前必须佩戴防护眼镜"
            },
            "刀具涂层脱落": {
                "steps": [
                    "停机检查刀具涂层脱落面积和位置",
                    "若脱落面积小于 30%，可继续使用并加强监测",
                    "若脱落面积大于 30%，建议更换刀具",
                    "检查切削液浓度和流量是否正常",
                    "适当提高切削速度以减少切削力"
                ],
                "tools": ["放大镜", "切削液浓度计"],
                "parts": ["备用涂层刀具"],
                "time": 20,
                "risk": "low",
                "safety": "注意切削液飞溅，保持防护门关闭"
            },

            # --- 🆕 新增 5 种 ---
            "积屑瘤": {
                "steps": [
                    "检查切削区温度，若温度偏低则提高切削速度 (vc)",
                    "更换为更合适的刀片几何 (推荐正几何)",
                    "确认切削液使用方式：建议使用油雾或完全关闭切削液",
                    "检查工件材料粘性，若为低碳钢或不锈钢，可考虑更换刀片材质",
                    "试切并观察切屑形态，确认积屑瘤是否消除"
                ],
                "tools": ["放大镜", "红外测温仪", "切削液喷枪"],
                "parts": ["正几何刀片", "金属陶瓷刀片"],
                "time": 20,
                "risk": "low",
                "safety": "提高切削速度时注意逐步增加，避免突然变化导致刀具损坏"
            },
            "热裂纹": {
                "steps": [
                    "检查切削液供应是否稳定，确保大量供应或完全停止",
                    "选择抗热冲击性更好的刀片材质 (韧性更高)",
                    "调整切削参数，避免断续加工或减小进给量",
                    "检查刀具散热情况，必要时更换为带内冷通道的刀具",
                    "观察裂纹是否扩展，若严重则更换刀具"
                ],
                "tools": ["放大镜", "温度计", "内冷刀柄"],
                "parts": ["韧性更好的硬质合金刀片", "内冷铣刀"],
                "time": 25,
                "risk": "medium",
                "safety": "热裂纹可能导致刀片断裂，操作前确保防护门关闭"
            },
            "缺口磨损": {
                "steps": [
                    "降低切削速度 (vc) 以减少切削热",
                    "选择更韧的刀片材质 (如 YG8 或 GC4040)",
                    "采用更强的刀片几何 (如 45° 主偏角)",
                    "若条件允许，改用圆刀片铣刀",
                    "调整切削深度 (ap) 采用变切深技术以延缓磨损"
                ],
                "tools": ["千分尺", "放大镜", "切削参数手册"],
                "parts": ["韧性更好的刀片", "圆刀片铣刀"],
                "time": 30,
                "risk": "medium",
                "safety": "加工硬化材料时注意刀具进给，避免过深切槽"
            },
            "塑性变形": {
                "steps": [
                    "选择更耐磨 (更硬) 的刀片材质 (如 YG3X 或 GC1025)",
                    "降低切削速度 (vc) 和进给量 (fz)",
                    "检查切削液是否充分，确保冷却效果",
                    "观察刀片是否有挤压痕迹，若严重则更换刀片",
                    "调整切削深度，避免过大的切削力"
                ],
                "tools": ["千分尺", "硬度计", "切削液喷嘴"],
                "parts": ["高硬度耐磨刀片"],
                "time": 20,
                "risk": "medium",
                "safety": "塑性变形可能导致刀片断裂，注意观察切削力变化"
            },
            "月牙洼磨损": {
                "steps": [
                    "选择 Al₂O₃ 涂层刀片以抵抗扩散磨损",
                    "采用正几何刀片，减小前刀面与切屑的接触面积",
                    "适当降低转速 (n) 以降低切削温度，然后调整进给",
                    "检查切屑颜色，若发蓝则需降低切削速度",
                    "定期检查前刀面磨损情况，及时换刀"
                ],
                "tools": ["显微镜", "表面粗糙度仪"],
                "parts": ["Al₂O₃ 涂层刀片", "正几何刀片"],
                "time": 25,
                "risk": "low",
                "safety": "月牙洼磨损可能削弱切削刃，注意观察表面质量"
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


# ========== 独立测试入口 ==========
if __name__ == "__main__":
    print("=" * 60)
    print("测试：维修方案 Agent（规则引擎模式）")
    print("=" * 60)

    agent = MaintenancePlanAgent()

    # 测试所有 8 种故障类型
    test_faults = ["刀具磨损", "刀具崩刃", "刀具涂层脱落", "积屑瘤", "热裂纹", "缺口磨损", "塑性变形", "月牙洼磨损"]

    for ft in test_faults:
        diagnosis = {
            'fault_type': ft,
            'severity': 'medium',
            'conclusion': f'测试诊断结论: {ft}'
        }
        result = agent.generate_plan(diagnosis)
        print(f"\n【{ft}】")
        print(f"  风险: {result['risk_level']}, 预估时间: {result['estimated_time_min']} 分钟")
        print(f"  步骤 1: {result['steps'][0]}")
        print(f"  工具: {', '.join(result['required_tools'])}")