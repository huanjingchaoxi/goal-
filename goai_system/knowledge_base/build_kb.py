"""
Step 3: 知识库构建（原始文档 -> chunk -> TF-IDF/FAISS 索引）
============================================================
输入: knowledge_base/raw_docs/ 下所有 .txt / .md / .json 文档
输出:
  - knowledge_base/chunks.jsonl    : chunk 元数据（含 source, category）
  - knowledge_base/vectorizer.pkl  : 已训练 TfidfVectorizer
  - knowledge_base/faiss_index.bin : FAISS 索引（若 faiss 可用）
"""
import json
import pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer

BASE_DIR = Path(__file__).resolve().parent
RAW_DOCS_DIR = BASE_DIR / "raw_docs"

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


def split_long_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """长文本滑窗切分。"""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        if start + size >= len(text):
            break
        start += size - overlap
    return chunks


def load_documents(raw_docs_dir):
    """遍历 raw_docs（含子目录），返回 [(text, source, category)]。"""
    docs = []
    for path in sorted(raw_docs_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(raw_docs_dir)
        category = "standard" if rel.parts[0] in ("iso_8688.txt", "iso_3685.txt") else "reference"
        category = "reference" if path.suffix in (".md",) else category

        if path.suffix == ".json":
            # 结构化数据: FMEA / 案例
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
            for it in items:
                if "symptom" in it and "root_cause" in it:
                    text = (f"故障现象：{it.get('symptom')}。根因：{it.get('root_cause')}。"
                            f"处置：{it.get('action')}。效果：{it.get('effect')}。")
                    docs.append((text, f"case_{it.get('id')}", "case"))
                elif "failure_mode" in it:
                    text = (f"失效模式：{it.get('failure_mode')}。影响：{it.get('effect')}。"
                            f"原因：{it.get('cause')}。检测：{it.get('detection_method')}。"
                            f"建议措施：{it.get('recommended_action')}。RPN={it.get('rpn')}。")
                    docs.append((text, f"fmea_{it.get('id')}", "standard"))
            continue

        # 文本文件 (.txt / .md)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]
        for para in paras:
            for sub in split_long_text(para):
                docs.append((sub, path.stem, category))
    return docs


def build_kb():
    docs = load_documents(RAW_DOCS_DIR)
    if not docs:
        raise RuntimeError("raw_docs 为空，请先准备文档。")

    texts, sources, cats = zip(*docs)
    vectorizer = TfidfVectorizer(token_pattern=r"\w+", min_df=1, sublinear_tf=True)
    vectorizer.fit(texts)

    # 写入 chunks.jsonl
    with open(BASE_DIR / "chunks.jsonl", "w", encoding="utf-8") as f:
        for text, src, cat in zip(texts, sources, cats):
            f.write(json.dumps({"text": text, "source": src, "category": cat},
                               ensure_ascii=False) + "\n")
    # 保存 vectorizer
    with open(BASE_DIR / "vectorizer.pkl", "wb") as f:
        pickle.dump(vectorizer, f)

    # 构建 FAISS 索引（可选）
    faiss_ok = False
    try:
        import faiss
        import numpy as np
        X = vectorizer.transform(texts).toarray().astype("float32")
        faiss.normalize_L2(X)
        index = faiss.IndexFlatIP(X.shape[1])
        index.add(X)
        faiss.write_index(index, str(BASE_DIR / "faiss_index.bin"))
        faiss_ok = True
    except Exception as e:
        print(f"[提示] FAISS 索引未构建: {e}（使用 sklearn TF-IDF 检索即可）")

    print(f"知识库构建完成: {len(docs)} chunks, 类别分布:")
    from collections import Counter
    for cat, n in Counter(cats).items():
        print(f"  {cat}: {n}")
    print(f"FAISS: {'已构建' if faiss_ok else '跳过'}")
    return len(docs)


if __name__ == "__main__":
    n = build_kb()
    # 自测检索
    from kb import KnowledgeBase
    kb = KnowledgeBase()
    print(f"\n[自测] 检索 'VB 0.3mm 刀具寿命判据':")
    for r in kb.retrieve("VB 0.3mm 刀具寿命判据", top_k=3):
        print(f"  [{r['score']:.3f}] ({r['category']}/{r['source']}) {r['text'][:70]}...")
