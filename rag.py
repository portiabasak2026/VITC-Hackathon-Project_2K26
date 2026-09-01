"""
Ledger — Semantic Search and Regulatory Document Retrieval Engine.
Provides grounded RAG queries across regulatory disclosures and corporate filings.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DISCLOSURE_CORPUS = [
    {
        "ticker": "AAPL",
        "title": "Item 1A. Risk Factors (FY2025 Form 10-K)",
        "source": "SEC EDGAR / Apple Inc. Annual Report",
        "content": (
            "Global supply chain dependencies, semiconductor fabrication bottlenecks, "
            "and antitrust regulatory investigations across international app distribution "
            "platforms represent key headwinds. Services gross margins continue to expand "
            "driven by enterprise subscription and cloud infrastructure adoption."
        ),
    },
    {
        "ticker": "TSLA",
        "title": "Item 7. MD&A — Automotive Gross Margin & Autonomy (Form 10-Q)",
        "source": "SEC EDGAR / Tesla Inc. Quarterly Filing",
        "content": (
            "Automotive regulatory credits and vehicle average selling price (ASP) adjustments "
            "impact automotive gross margin excluding regulatory credits. Capital expenditure "
            "guidance reflects expanded investments in Full Self-Driving supercomputing "
            "clusters and next-generation energy storage deployment."
        ),
    },
    {
        "ticker": "NVDA",
        "title": "Item 1. Business & Data Center Revenue Drivers (Form 10-K)",
        "source": "SEC EDGAR / NVIDIA Corporation Annual Filing",
        "content": (
            "Data Center platform revenues remain driven by accelerated computing infrastructure, "
            "hyperscale cloud demand, and generative AI foundational model deployments. "
            "Geopolitical export control regulations regarding advanced node shipments "
            "remain an active operational constraint."
        ),
    },
    {
        "ticker": "GLOBAL",
        "title": "SEBI / RBI Prudential Guidelines on Market Volatility",
        "source": "Regulatory Disclosures & Prudential Framework",
        "content": (
            "Equities exhibiting annualized volatility above standard sector deviation thresholds "
            "require conservative risk-weighting across retail customer allocation strategies."
        ),
    },
]


class SemanticRetriever:

    def __init__(self, corpus=DISCLOSURE_CORPUS):
        self.corpus = corpus
        self.documents = [f"{doc['ticker']} {doc['title']}: {doc['content']}" for doc in self.corpus]
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix = self.vectorizer.fit_transform(self.documents)

    def retrieve(self, query: str, ticker: str = None, top_k: int = 2):
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        ranked_indices = scores.argsort()[::-1]
        results = []

        for idx in ranked_indices:
            doc = self.corpus[idx]
            if ticker and doc["ticker"] not in (ticker.upper(), "GLOBAL"):
                continue
            if scores[idx] > 0.05 or len(results) == 0:
                results.append({
                    "title": doc["title"],
                    "source": doc["source"],
                    "content": doc["content"],
                    "score": round(float(scores[idx]), 3),
                })
            if len(results) >= top_k:
                break

        return results