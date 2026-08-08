"""
Step 3: FAISS/TF-IDF 知识库检索接口封装
========================================
检索核心：sklearn TF-IDF + 余弦相似度（零额外依赖，Py3.10 即装即用）
可选升级：若安装 faiss，可构建 IndexFlatIP 实现同等向量检索（本项目默认 TF-IDF）

文件：
  - knowledge_base/chunks.jsonl    : 切分后的 chunk 元数据
  - knowledge_base/vectorizer.pkl  : TfidfVectorizer（已训练）
  - knowledge_base/faiss_index.bin : FAISS 索引（可选）
"""
import json
import pickle
import hashlib
import sys
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
CHUNKS_PATH = BASE_DIR / "chunks.jsonl"
VEC_PATH = BASE_DIR / "vectorizer.pkl"
FAISS_PATH = BASE_DIR / "faiss_index.bin"


class KnowledgeBase:
    """基于 TF-IDF 的工业知识库，提供检索与追加能力。"""

    def __init__(self, chunks_path=CHUNKS_PATH, vec_path=VEC_PATH,
                 faiss_path=FAISS_PATH, retriever="auto"):
        self.chunks = self._load_chunks(chunks_path)
        self.vectorizer = self._load_pickle(vec_path)
        self.faiss_index = None
        self.dim = None
        if self.vectorizer is not None and self.chunks:
            self.matrix = self.vectorizer.transform([c["text"] for c in self.chunks]).tocsr()
            self.dim = self.matrix.shape[1]
            # 可选: 构建 FAISS 索引
            if retriever in ("faiss", "auto"):
                try:
                    import faiss
                    X = self.matrix.toarray().astype("float32")
                    faiss.normalize_L2(X)
                    index = faiss.IndexFlatIP(self.dim)
                    index.add(X)
                    self.faiss_index = index
                    self._faiss_ok = True
                except Exception:
                    self._faiss_ok = False
            else:
                self._faiss_ok = False

    @staticmethod
    def _load_chunks(path):
        if not Path(path).exists():
            return []
        chunks = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    chunks.append(json.loads(line))
        return chunks

    @staticmethod
    def _load_pickle(path):
        if not Path(path).exists():
            return None
        if str(BASE_DIR) not in sys.path:
            sys.path.insert(0, str(BASE_DIR))
        with open(path, "rb") as f:
            return pickle.load(f)

    def is_ready(self):
        return self.vectorizer is not None and len(self.chunks) > 0

    def retrieve(self, query, top_k=3):
        """返回 [{text, source, category, score}]，按相关性降序。"""
        if not self.is_ready():
            return []
        qvec = self.vectorizer.transform([query]).toarray().astype("float32")

        if self._faiss_ok and self.faiss_index is not None:
            import faiss
            faiss.normalize_L2(qvec)
            scores, idxs = self.faiss_index.search(qvec, min(top_k, len(self.chunks)))
            results = []
            for s, i in zip(scores[0], idxs[0]):
                if i >= 0 and i < len(self.chunks):
                    r = dict(self.chunks[i])
                    r["score"] = float(s)
                    results.append(r)
            return results

        # 降级: sklearn 余弦相似度
        sims = (self.matrix @ qvec.T).toarray().ravel()
        top_idx = np.argsort(sims)[::-1][:top_k]
        results = []
        for i in top_idx:
            r = dict(self.chunks[i])
            r["score"] = float(sims[i])
            results.append(r)
        return results

    def add_knowledge(self, text, source="user_feedback", category="case", persist=True):
        """追加一条知识（知识沉淀 Agent 用），并增量更新矩阵/索引。"""
        chunk = {
            "text": text,
            "source": source,
            "category": category,
            "kid": hashlib.md5(text.encode("utf-8")).hexdigest()[:10],
        }
        self.chunks.append(chunk)
        # 重新计算矩阵（chunk 量级小，全量重建可接受）
        self.matrix = self.vectorizer.transform([c["text"] for c in self.chunks]).tocsr()
        self.dim = self.matrix.shape[1]
        if self._faiss_ok:
            try:
                import faiss
                X = self.matrix.toarray().astype("float32")
                faiss.normalize_L2(X)
                index = faiss.IndexFlatIP(self.dim)
                index.add(X)
                self.faiss_index = index
                faiss.write_index(index, str(FAISS_PATH))
            except Exception:
                pass
        if persist:
            with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
                for c in self.chunks:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
        return chunk

    def count(self):
        return len(self.chunks)


if __name__ == "__main__":
    kb = KnowledgeBase()
    print(f"知识库就绪: {kb.count()} chunks, retriever={'FAISS' if kb._faiss_ok else 'TF-IDF'}")
    for q in ["刀具磨损寿命判据 VB 0.3mm", "声发射峭度 崩刃", "积屑瘤 表面粗糙度"]:
        print(f"\n查询: {q}")
        for r in kb.retrieve(q, top_k=3):
            print(f"  [{r['score']:.3f}] ({r['category']}/{r['source']}) {r['text'][:60]}...")
