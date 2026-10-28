import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings

class LocalDenseEmbedder:
    """
    Deterministic, high-performance dense embedding generator.
    Produces L2-normalized 128-dimensional dense vectors using word and bigram TF-IDF with English stop words.
    Zero external network dependencies; guaranteed to run offline and in sandboxed environments.
    """
    def __init__(self, dim: int = 128):
        self.dim = dim
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),
            max_features=self.dim,
            sublinear_tf=True
        )
        self._fitted = False

    def fit(self, corpus: List[str]):
        if not corpus:
            corpus = ["python programming basics variables functions loops", "excel formulas lookups references sum average", "cloud computing virtualization containers storage iam"]
        self.vectorizer.fit(corpus)
        self._fitted = True

    def has_matching_terms(self, text: str) -> bool:
        if not self._fitted:
            return False
        sparse_vec = self.vectorizer.transform([text])
        return sparse_vec.nnz > 0

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not self._fitted:
            self.fit(texts)
        matrix = self.vectorizer.transform(texts).toarray()
        n_samples, n_features = matrix.shape
        if n_features < self.dim:
            padding = np.zeros((n_samples, self.dim - n_features))
            dense = np.hstack([matrix, padding])
        else:
            dense = matrix[:, :self.dim]

        # L2-normalize vectors (if all zeros, leave as zero vector)
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = (dense / norms).astype(float)
        return normalized.tolist()

class CourseRAGService:
    """
    Chroma-backed RAG service for course lessons.
    Indexes demo course modules, generates dense embeddings, and performs
    course-scoped semantic chunk retrieval.
    """
    _client: Optional[chromadb.PersistentClient] = None
    _collection: Optional[Any] = None
    _embedder: Optional[LocalDenseEmbedder] = None
    _is_indexed: bool = False

    COLLECTION_NAME = "course_lessons_rag"
    RELEVANCE_THRESHOLD = 0.20  # Minimum cosine similarity to consider grounded

    @classmethod
    def get_chroma_client(cls) -> chromadb.PersistentClient:
        if cls._client is None:
            chroma_dir = os.path.join(settings.DATA_DIR, "chroma_db")
            os.makedirs(chroma_dir, exist_ok=True)
            cls._client = chromadb.PersistentClient(path=chroma_dir)
        return cls._client

    @classmethod
    def get_collection(cls):
        if cls._collection is None:
            client = cls.get_chroma_client()
            cls._collection = client.get_or_create_collection(
                name=cls.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        return cls._collection

    @classmethod
    def build_index(cls, lessons_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Parses lessons_and_quizzes.json, chunks all lessons, generates embeddings,
        and stores them idempotently in Chroma.
        """
        if lessons_file is None:
            lessons_file = os.path.join(settings.DATA_DIR, "lessons_and_quizzes.json")

        if not os.path.exists(lessons_file):
            return {"indexed_chunks": 0, "status": "file_not_found"}

        with open(lessons_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        chunks: List[Dict[str, Any]] = []

        for cid, cinfo in data.items():
            ctitle = cinfo.get("title") or cid
            modules = cinfo.get("modules", [])

            if modules:
                for mod in modules:
                    mid = mod.get("module_id", "")
                    mtitle = mod.get("title", "")
                    for lesson in mod.get("lessons", []):
                        lid = lesson.get("lesson_id", "")
                        ltitle = lesson.get("title", "")
                        explanation = lesson.get("explanation") or lesson.get("content", "")
                        practical_example = lesson.get("practical_example", "")
                        takeaways = lesson.get("key_takeaways", [])
                        takeaways_str = "\n".join([f"- {t}" for t in takeaways]) if isinstance(takeaways, list) else str(takeaways)
                        exercise = lesson.get("exercise", "")

                        src_ref = f"{ctitle} - {mtitle}: {ltitle}"

                        # Chunk 1: Explanation
                        if explanation:
                            chunks.append({
                                "id": f"CHUNK-{cid}-{lid}-EXPL",
                                "document": f"Course: {ctitle}\nModule: {mtitle}\nLesson: {ltitle}\n\nConcept Explanation:\n{explanation}",
                                "metadata": {
                                    "course_id": cid,
                                    "course_title": ctitle,
                                    "module_id": mid,
                                    "module_title": mtitle,
                                    "lesson_id": lid,
                                    "lesson_title": ltitle,
                                    "chunk_type": "explanation",
                                    "source_reference": src_ref
                                }
                            })

                        # Chunk 2: Practical Example
                        if practical_example:
                            chunks.append({
                                "id": f"CHUNK-{cid}-{lid}-EXMP",
                                "document": f"Course: {ctitle}\nModule: {mtitle}\nLesson: {ltitle}\n\nPractical Example & Application:\n{practical_example}",
                                "metadata": {
                                    "course_id": cid,
                                    "course_title": ctitle,
                                    "module_id": mid,
                                    "module_title": mtitle,
                                    "lesson_id": lid,
                                    "lesson_title": ltitle,
                                    "chunk_type": "practical_example",
                                    "source_reference": src_ref
                                }
                            })

                        # Chunk 3: Key Takeaways & Exercise
                        if takeaways_str or exercise:
                            chunks.append({
                                "id": f"CHUNK-{cid}-{lid}-EXRC",
                                "document": f"Course: {ctitle}\nModule: {mtitle}\nLesson: {ltitle}\n\nKey Takeaways:\n{takeaways_str}\n\nHands-on Exercise:\n{exercise}",
                                "metadata": {
                                    "course_id": cid,
                                    "course_title": ctitle,
                                    "module_id": mid,
                                    "module_title": mtitle,
                                    "lesson_id": lid,
                                    "lesson_title": ltitle,
                                    "chunk_type": "exercise",
                                    "source_reference": src_ref
                                }
                            })

            else:
                for lesson in cinfo.get("lessons", []):
                    lid = lesson.get("lesson_id", "")
                    ltitle = lesson.get("title", "")
                    content = lesson.get("content", "")
                    src_ref = f"{ctitle} - {ltitle}"
                    chunks.append({
                        "id": f"CHUNK-{cid}-{lid}-BASE",
                        "document": f"Course: {ctitle}\nLesson: {ltitle}\n\nContent:\n{content}",
                        "metadata": {
                            "course_id": cid,
                            "course_title": ctitle,
                            "module_id": "",
                            "module_title": "",
                            "lesson_id": lid,
                            "lesson_title": ltitle,
                            "chunk_type": "content",
                            "source_reference": src_ref
                        }
                    })

        if not chunks:
            return {"indexed_chunks": 0, "status": "empty"}

        all_docs = [c["document"] for c in chunks]
        cls._embedder = LocalDenseEmbedder(dim=128)
        cls._embedder.fit(all_docs)
        embeddings = cls._embedder.embed_texts(all_docs)

        collection = cls.get_collection()
        ids = [c["id"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        collection.upsert(
            ids=ids,
            documents=all_docs,
            metadatas=metadatas,
            embeddings=embeddings
        )

        cls._is_indexed = True
        return {
            "indexed_chunks": len(chunks),
            "total_courses": len(data),
            "status": "success"
        }

    @classmethod
    def search(
        cls,
        query: str,
        course_id: Optional[str] = None,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Retrieves relevant course lesson chunks for a learner question.
        Returns citations, retrieved text, and a boolean indicating whether
        grounded content was found above the relevance threshold.
        """
        if not cls._is_indexed or cls._embedder is None:
            cls.build_index()

        query_clean = query.strip()
        if not query_clean:
            return {"found": False, "citations": [], "evidence_text": "", "chunks": []}

        # Check if query has any matching vocabulary terms
        if not cls._embedder.has_matching_terms(query_clean):
            return {
                "found": False,
                "citations": [],
                "evidence_text": "",
                "chunks": [],
                "message": "No matching terms found in course material."
            }

        # Embed query
        query_embedding = cls._embedder.embed_texts([query_clean])[0]

        # Check if vector is zero
        if all(v == 0.0 for v in query_embedding):
            return {
                "found": False,
                "citations": [],
                "evidence_text": "",
                "chunks": [],
                "message": "Query contains no indexable course keywords."
            }

        collection = cls.get_collection()
        where_filter = {"course_id": course_id} if course_id else None

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 2, 10),
                where=where_filter
            )
        except Exception as e:
            return {
                "found": False,
                "error": f"Vector database query error: {str(e)}",
                "citations": [],
                "evidence_text": "",
                "chunks": []
            }

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        citations = []
        evidence_parts = []
        matching_chunks = []
        seen_lessons = set()

        for doc_text, meta, dist in zip(docs, metas, distances):
            similarity = 1.0 - float(dist)

            if similarity < cls.RELEVANCE_THRESHOLD:
                continue

            lesson_key = f"{meta.get('course_id')}:{meta.get('lesson_id')}"
            if lesson_key not in seen_lessons:
                seen_lessons.add(lesson_key)
                citations.append({
                    "course_id": meta.get("course_id", ""),
                    "course_title": meta.get("course_title", ""),
                    "module_title": meta.get("module_title", ""),
                    "lesson_id": meta.get("lesson_id", ""),
                    "lesson_title": meta.get("lesson_title", ""),
                    "source_reference": meta.get("source_reference", ""),
                    "score": round(similarity, 3)
                })

            evidence_parts.append(f"[{meta.get('source_reference')}]\n{doc_text}")
            matching_chunks.append({
                "text": doc_text,
                "metadata": meta,
                "similarity": similarity
            })

            if len(matching_chunks) >= top_k:
                break

        found = len(matching_chunks) > 0

        return {
            "found": found,
            "citations": citations,
            "evidence_text": "\n\n---\n\n".join(evidence_parts),
            "chunks": matching_chunks
        }
