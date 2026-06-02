"""
skills/
───────
Claw Code Offline – Python skills layer.

Available skills
----------------
connectivity  : online/offline detection + web search fallback
rag_skill     : local vector-store RAG (ChromaDB + sentence-transformers)
tts_skill     : offline text-to-speech (pyttsx3)
sandbox_skill : isolated code execution (Docker)

Quick example
-------------
    from skills import connectivity, RagSkill, TtsSkill, SandboxSkill

    # 1 – Check connectivity and search
    if connectivity.is_online():
        hits = connectivity.web_search("claw code ollama setup")
    else:
        rag = RagSkill()
        rag.ingest()
        hits = rag.search("ollama setup")

    # 2 – Speak a result
    tts = TtsSkill()
    tts.speak(hits[0]["text"] if hits else "No results found.")

    # 3 – Run untrusted code safely
    sb = SandboxSkill()
    result = sb.run_python("print(sum(range(100)))")
    print(result.stdout)   # 4950
"""

from skills.connectivity import fetch_page, is_online, search_or_rag, web_search
from skills.rag_skill import RagSkill
from skills.sandbox_skill import SandboxResult, SandboxSkill
from skills.tts_skill import TtsSkill

__all__ = [
    # connectivity
    "is_online",
    "web_search",
    "fetch_page",
    "search_or_rag",
    # classes
    "RagSkill",
    "TtsSkill",
    "SandboxSkill",
    "SandboxResult",
]
