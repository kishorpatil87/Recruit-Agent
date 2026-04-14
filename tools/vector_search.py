"""
Vector similarity using scikit-learn TF-IDF (no heavy ML downloads required).
Optional: sentence-transformers for semantic search if installed.
"""
from __future__ import annotations

import structlog
import numpy as np

log = structlog.get_logger(__name__)


def _tfidf_cosine(text_a: str, text_b: str) -> float:
    """Fast TF-IDF cosine similarity — no GPU, no big model downloads."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

        vect = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        tfidf = vect.fit_transform([text_a, text_b])
        score = float(sk_cosine(tfidf[0], tfidf[1])[0][0])
        return round(max(0.0, min(1.0, score)), 4)
    except Exception as e:
        log.warning("TF-IDF similarity failed", error=str(e))
        return 0.0


def _semantic_cosine(text_a: str, text_b: str) -> float:
    """Semantic cosine via sentence-transformers (optional — better quality)."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer("all-MiniLM-L6-v2")
        vecs = model.encode([text_a, text_b], normalize_embeddings=True)
        return float(np.dot(vecs[0], vecs[1]))
    except ImportError:
        return _tfidf_cosine(text_a, text_b)
    except Exception as e:
        log.warning("Semantic similarity failed", error=str(e))
        return 0.0


_semantic_available: bool | None = None


def _check_semantic() -> bool:
    global _semantic_available
    if _semantic_available is None:
        try:
            import sentence_transformers  # noqa
            _semantic_available = True
        except ImportError:
            _semantic_available = False
    return _semantic_available


def compute_semantic_score(jd_text: str, resume_text: str) -> float:
    if _check_semantic():
        return _semantic_cosine(jd_text, resume_text)
    return _tfidf_cosine(jd_text, resume_text)


def compute_keyword_overlap(jd_skills: list[str], resume_text: str) -> float:
    if not jd_skills:
        return 0.0
    resume_lower = resume_text.lower()
    hits = sum(1 for s in jd_skills if s.lower() in resume_lower)
    return round(hits / len(jd_skills), 4)


def composite_jd_score(
    jd_text: str,
    jd_skills: list[str],
    resume_text: str,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> dict[str, float]:
    semantic = compute_semantic_score(jd_text, resume_text)
    keyword = compute_keyword_overlap(jd_skills, resume_text)
    composite = semantic_weight * semantic + keyword_weight * keyword
    return {
        "semantic_score": round(semantic, 4),
        "keyword_score": round(keyword, 4),
        "composite_score": round(composite, 4),
    }
