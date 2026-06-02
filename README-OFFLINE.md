# Claw Code – Offline / Ollama Mode

> Run the full Claw Code agent **100 % locally** – no Anthropic key, no cloud,
> no internet required.

---

## What changed from upstream

| Area | Change |
|---|---|
| `rust/crates/api/src/providers/mod.rs` | Added `ProviderKind::Ollama`, Ollama model registry entries, `ollama_is_available()` probe, auto-detection logic |
| `rust/crates/api/src/providers/openai_compat.rs` | Added `DEFAULT_OLLAMA_BASE_URL`, `OLLAMA_DUMMY_API_KEY`, `OpenAiCompatConfig::ollama()` |
| `skills/connectivity.py` | Online/offline detection + DuckDuckGo web search fallback |
| `skills/rag_skill.py` | Local ChromaDB RAG over `.txt`/`.md` knowledge files |
| `skills/tts_skill.py` | Offline text-to-speech via pyttsx3 (espeak backend) |
| `skills/sandbox_skill.py` | Isolated code execution via `docker run --rm` |
| `ollama-config.json` | Example config to drop into `~/.claw.json` |

---

## 1 – Prerequisites

```bash
# Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Python 3.10+
python --version

# Docker (for sandbox skill)
# https://docs.docker.com/engine/install/

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
```

---

## 2 – Pull local models

```bash
# Primary coding model (~400 MB, runs on CPU)
ollama pull qwen2.5-coder:0.5b

# General-purpose (recommended upgrade)
ollama pull gemma2:2b

# Ultra-fast tiny model for simple tasks
ollama pull smollm:135m
```

Verify Ollama is running:

```bash
ollama list
curl http://localhost:11434/v1/models   # should return JSON
```

---

## 3 – Configure Claw Code

Copy the bundled config to your home directory:

```bash
cp ollama-config.json ~/.claw.json
```

Or set environment variables instead:

```bash
export OLLAMA_BASE_URL="http://localhost:11434/v1"
export OLLAMA_API_KEY="ollama"   # any non-empty string works
```

To use the coding model for all requests:

```bash
# in ~/.claw.json
{ "model": "qwen2.5-coder:0.5b" }

# or pass on the CLI
claw --model qwen2.5-coder:0.5b "refactor this file"
```

---

## 4 – Build Claw Code (Rust)

```bash
cd rust
cargo build --release
# binary at: rust/target/release/claw
```

---

## 5 – Install Python skills

```bash
# Core (required for all skills)
pip install pyttsx3

# RAG skill
pip install chromadb sentence-transformers

# Web search fallback (online mode)
pip install duckduckgo-search

# Linux TTS backend
sudo apt install espeak espeak-ng libespeak-dev   # Debian/Ubuntu
```

---

## 6 – Using the Skills from Python

### RAG – index your knowledge base

```python
from skills.rag_skill import RagSkill

# Put .txt / .md files in ./knowledge/
rag = RagSkill(knowledge_dir="./knowledge")
rag.ingest()                              # index all files (idempotent)

results = rag.search("how to handle async errors in Python")
for r in results:
    print(f"[{r['score']}] {r['source']}\n{r['text']}\n")
```

### Connectivity – auto web-search or RAG

```python
from skills.connectivity import search_or_rag
from skills.rag_skill import RagSkill

rag = RagSkill()
rag.ingest()

# Automatically uses web search when online, RAG when offline
hits = search_or_rag("Python memory leak debugging", rag_fn=rag.search)
```

### TTS – speak agent output

```python
from skills.tts_skill import TtsSkill

tts = TtsSkill(rate=160)
tts.speak("Build succeeded. 0 errors, 2 warnings.")

# List available voices
for v in tts.list_voices():
    print(v)

# Save to file
tts.save("Task complete.", path="done.wav")
```

### Sandbox – run untrusted code safely

```python
from skills.sandbox_skill import SandboxSkill

sb = SandboxSkill(network="none", memory="128m", timeout=15)

# Python
r = sb.run_python("import math; print(math.pi)")
print(r.stdout)         # 3.141592653589793
print(r.success)        # True

# Bash
r = sb.run_bash("echo $((2**10))")
print(r.stdout)         # 1024

# Node.js
r = sb.run_code("node -e 'console.log(process.version)'", image="node:20-alpine")
```

---

## 7 – Model selection guide

| Task | Recommended model | Flag |
|---|---|---|
| Code editing / generation | `qwen2.5-coder:0.5b` | default |
| General Q&A | `gemma2:2b` | `--model gemma2:2b` |
| Ultra-fast completions | `smollm:135m` | `--model smollm:135m` |
| Larger context / quality | `qwen2.5-coder:1.5b` | `--model qwen2.5-coder:1.5b` |

---

## 8 – Offline vs Online behaviour

```
Internet available?
       │
       ├─ YES → web_search via DuckDuckGo (no key needed)
       │          + full Claw Code tool use
       │
       └─ NO  → local RAG over ./knowledge/
                  + TTS announcements
                  + Sandbox execution
                  (all core agent tools still work)
```

The connectivity check (`skills/connectivity.py`) is a lightweight TCP
probe to `1.1.1.1:53` – it adds < 2 ms latency and causes no network
traffic when offline.

---

## 9 – Troubleshooting

**Ollama not detected**
```bash
ollama serve          # start the daemon if it isn't running
curl localhost:11434  # should print Ollama version
```

**"no voices found" (TTS)**
```bash
sudo apt install espeak-ng   # install system TTS engine
python -c "import pyttsx3; e=pyttsx3.init(); print(e.getProperty('voices'))"
```

**Docker sandbox errors**
```bash
docker info           # check daemon is running
docker pull python:3.12-slim   # pre-pull default image
```

**ChromaDB import error**
```bash
pip install --upgrade chromadb sentence-transformers
```

---

## Licence

Same as upstream Claw Code (see `LICENSE`).  
Skill additions © 2026 – MIT.
