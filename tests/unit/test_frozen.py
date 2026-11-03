"""Byte-for-byte pins on the text the eval caches and the index are keyed on.

The saved eval answers are reused only while the system prompt, the baseline prompt, the
rubric and the source names (the catalog a refusal lists) stay the same, and the source names
are also stored with every indexed chunk. A change to any of them re-asks and re-judges the
whole golden set, which costs money, or forces a re-index. If you mean to change one, update
its hash here in the same commit.
"""

import hashlib
import json

from rag_stack.agent.prompts import ABSTAIN
from rag_stack.config import Settings

PACK = Settings().pack


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_prompts_are_unchanged():
    assert [sha(PACK.system_prompt), sha(PACK.baseline_prompt), sha(ABSTAIN)] == [
        "bf0e607e37d2ad3c57697a315c580f91fb860cdc9fb40ef1b2e9421e9e26eb0f",
        "1db58a9ac6605a9d7062592cc3fec70b1d98ec6da71d0f25a6e1c5268fc36fdc",
        "dc672f7828d1ce8e878071f7d6e3deae619173f8fcc9923c6a28b1a82a00c8c7",
    ]


def test_judge_rubric_is_unchanged():
    assert sha(PACK.evals.rubric.read_text()) == (
        "024866d6ee9c0d47a65e0994e23726661d96d5fc5c2434c45114031dc9cdc3e9"
    )


def test_answer_labels_are_unchanged():
    assert sha(json.dumps(PACK.labels, sort_keys=True, ensure_ascii=False)) == (
        "9a0b5726ed7883e625cc174e4f05cdde9488fa2301b5bdbcac381e93e6369eba"
    )


def test_source_names_are_unchanged():
    assert {k: v.name for k, v in PACK.sources.items()} == {
        "atlas": "MITRE ATLAS",
        "owasp-llm-2026": "OWASP Top 10 for LLM Applications 2026",
        "owasp-agentic-2026": "OWASP Top 10 for Agentic Applications 2026",
        "eu-ai-act": "EU AI Act (Regulation (EU) 2024/1689)",
        "ki-mig": "KI-MIG (KI-Marktüberwachungs- und Innovationsförderungsgesetz)",
        "vulns": "Vulnerabilities (CISA KEV, GitHub Advisory Database, NVD, EPSS)",
        "attack": "MITRE ATT&CK",
        "capec": "MITRE CAPEC",
        "cwe": "MITRE CWE",
        "d3fend": "MITRE D3FEND",
    }
