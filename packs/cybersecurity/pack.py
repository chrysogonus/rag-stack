"""The cybersecurity pack's code: its ID formats, and the laws a question can name."""

from rag_stack.ingestion.registry import EU_ACTS, GERMAN_LAWS
from rag_stack.retrieval.ids import detect_ids

__all__ = ["detect_ids", "scoped"]

# A law a question names ("under the KI-MIG") is also searched on its own: its text can lose to
# another source's (the KI-MIG is German only, the AI Act's English articles outrank it).
scoped = {source: rf"\b(?:{names})" for source, (_, names) in {**EU_ACTS, **GERMAN_LAWS}.items()}
