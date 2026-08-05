# 刀锋智维 · 数控刀具多智能体运维系统

GOAI 无界应用大赛（AI+工业制造赛道）项目：面向数控机床刀具磨损的多智能体运维系统，
覆盖 **异常发现 → 故障诊断 → 维修调度 → 知识沉淀** 完整闭环。

## 快速开始

```bash
# 1. 环境（conda）
conda activate langgraph_env
pip install -r requirements.txt

# 2. 按顺序执行
python data/processed/preprocess_phm2010.py   # Step1 特征工程 (约10分钟, 17GB原始数据)
python simulator/event_generator.py           # Step2 异常事件流
python knowledge_base/build_kb.py             # Step3 知识库
python agents/workflow.py                     # Step5 LangGraph 端到端

# 3. UI
cd ui && streamlit run app.py                 # Step6
```

## 目录结构
```
goai_system/
  data/processed/     Step1: cut_features.csv + scaler.pkl
  simulator/          Step2: event_stream.jsonl + ground_truth.jsonl
  knowledge_base/     Step3: raw_docs + chunks.jsonl + TF-IDF/FAISS 检索
  agents/             Step4-5: 四 Agent + LangGraph 编排 + 审计
  ui/                 Step6: Streamlit 界面
  logs/               Step7: audit.jsonl
```

## 数据契约
- **异常事件** `evt_*`: event_id, timestamp, tool_id, cut_no, anomaly_type, severity, features_summary, confidence
- **诊断报告** `diag_*`: conclusion, confidence, evidence[](带source), recommended_action, rul_estimate_hours
- **工单** `wo_*`: priority, risk_level, action, estimated_downtime_min, required_approval, status
- **知识条目** `kn_*`: symptom, root_cause, action, effect

## 关键技术点
- **数据**: PHM2010 铣削数据集，6刀×315刀路×7通道（Fx,Fy,Fz,Vx,Vy,Vz,AE_rms）
  其中 c1/c4/c6 有 VB 磨损真值，c2/c3/c5 无标注（测试刀）
- **特征**: 42维时域特征（7通道×6统计量）+ 磨损阶段标注
- **RAG**: sklearn TF-IDF 检索（faiss 可选），幻觉防御校验证据 source
- **LLM**: DeepSeek API（`deepseek-chat`），无 Key 自动降级为规则引擎
- **编排**: LangGraph 状态机，含人工审批分支

## 文档
- 技术执行手册: `../GOAI技术执行手册.md`
- 执行进度跟踪: `../GOAI_执行进度.md`
