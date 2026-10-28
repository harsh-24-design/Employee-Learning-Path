import os
import re
import math
from typing import Dict, Any, List
from collections import Counter
from app.repositories.mongo_repository import repository

class SimpleBM25:
    """
    Lightweight, self-contained implementation of BM25Okapi algorithm.
    Avoids external dependencies while providing accurate ranking.
    """
    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths = [len(doc) for doc in corpus]
        self.avg_doc_len = sum(self.doc_lengths) / (self.corpus_size or 1)
        self.doc_freqs: List[Counter] = [Counter(doc) for doc in corpus]
        
        # Calculate inverted document frequency (IDF) for words
        self.idf: Dict[str, float] = {}
        df = Counter()
        for doc in corpus:
            df.update(set(doc))
        for word, freq in df.items():
            self.idf[word] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query: List[str]) -> List[float]:
        scores = [0.0] * self.corpus_size
        for term in query:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]
            for idx in range(self.corpus_size):
                term_freq = self.doc_freqs[idx][term]
                if term_freq == 0:
                    continue
                doc_len = self.doc_lengths[idx]
                numerator = term_freq * (self.k1 + 1)
                denominator = term_freq + self.k1 * (1 - self.b + self.b * (doc_len / (self.avg_doc_len or 1)))
                scores[idx] += idf_val * (numerator / denominator)
        return scores

class PolicyRAGService:
    """
    RAG Retrieval Service for corporate learning policy documents.
    Provides evidence passages and citations for policy questions (FR-08, FR-10).
    """
    _chunks: List[Dict[str, Any]] = []
    _bm25: SimpleBM25 = None

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    @classmethod
    def build_index(cls):
        policy_doc = repository.find_one("policies", {"document_name": "learning_policy.pdf"})
        raw_text = policy_doc.get("content", "") if policy_doc else ""

        if not raw_text:
            raw_text = """
            Enterprise Learning & Development Policy:
            Section 1: Annual Learning Budget Cap
            All employees are allocated an annual training budget of $500 USD for approved external or internal paid courses.
            Courses priced at $0 are fully covered with no deduction from the annual allowance.
            
            Section 2: Study Availability and Weekly Limits
            Employees may allocate up to 10 hours per week of study time during working hours, subject to manager approval.
            Courses requiring light intensity or 3 or fewer hours per week are classified as Extended Timeline plans.
            
            Section 3: Certification and Career Disclaimers
            Completion of any internal learning track, workshop, or catalogue course does NOT guarantee promotion, salary raise, bonus, or specific job title reclassification.
            Official skill levels are updated exclusively through standardized practical assessments and rubric evaluation.
            
            Section 4: Prerequisites and Course Sequence
            Employees must complete all foundation prerequisites before enrolling in intermediate or advanced courses.
            Direct testing out of prerequisites requires a verified assessment score of 80% or above.
            """

        # Split text into paragraphs
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 30]
        cls._chunks = []
        tokenized_corpus = []

        for idx, para in enumerate(paragraphs):
            lines = para.split("\n")
            title = lines[0].strip() if lines else f"Policy Clause #{idx+1}"
            chunk = {
                "chunk_id": f"POL-CHUNK-{idx+1}",
                "source": "learning_policy.pdf",
                "title": title,
                "text": para
            }
            cls._chunks.append(chunk)
            tokenized_corpus.append(cls._tokenize(para))

        if tokenized_corpus:
            cls._bm25 = SimpleBM25(tokenized_corpus)

    @classmethod
    def search_policy(cls, query: str, top_k: int = 2) -> Dict[str, Any]:
        if not cls._chunks or cls._bm25 is None:
            cls.build_index()

        query_tokens = cls._tokenize(query)
        if not query_tokens or cls._bm25 is None:
            return {"citations": [], "evidence_text": ""}

        scores = cls._bm25.get_scores(query_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        citations = []
        evidence_parts = []
        for idx in top_indices:
            if scores[idx] > 0.1:  # Relevance threshold
                chunk = cls._chunks[idx]
                citations.append({
                    "chunk_id": chunk["chunk_id"],
                    "document": chunk["source"],
                    "section": chunk["title"],
                    "score": round(float(scores[idx]), 3)
                })
                evidence_parts.append(f"[{chunk['title']}]\n{chunk['text']}")

        return {
            "citations": citations,
            "evidence_text": "\n\n".join(evidence_parts) if evidence_parts else ""
        }
