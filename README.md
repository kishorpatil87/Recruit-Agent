# 🎯 RecruitAI — AI Recruitment Agent

Production-grade AI recruitment pipeline. Upload resumes, define a job description, and get a ranked leaderboard with AI scores, gap analysis, and interview questions.

**Powered by:** Ollama (100% local, zero cost) · LangGraph · scikit-learn · FastAPI

---

## ⚡ Quick Start (4 steps)

### 1. Install Ollama
Download and install from: **https://ollama.com/download**

### 2. Pull the model
```bash
ollama pull mistral:7b-instruct-q4_K_M
```

### 3. Install Python dependencies
```bash
py -3.11 -m pip install -r requirements.txt
```

### 4. Start the server
```bash
py -3.11 main.py
```
Then open **http://localhost:8080** in your browser.

> **Note:** Ollama must be running (`ollama serve`) before starting RecruitAI.

---

## 🖥️ Web Interface

| Feature | Description |
|---------|-------------|
| **Job Description** | Paste job title, company, full JD text |
| **Skills tags** | Add required + preferred skills with tag input |
| **Resume upload** | Drag-and-drop multiple files (PDF, DOCX, TXT) |
| **Role level** | Junior / Mid / Senior / Lead (adjusts scoring weights) |
| **Live processing** | Animated 5-step progress while AI evaluates |
| **Ranked table** | Click any row to expand — scores, gaps, interview Qs |
| **Export** | Download as JSON or CSV |

---

## 🤖 LLM Setup

| LLM | Cost | RAM Required | Setup |
|-----|------|-------------|-------|
| **Ollama (Mistral 7B Q4)** ✅ | **Free** | ~5.5 GB | `ollama pull mistral:7b-instruct-q4_K_M` |

No API keys needed! Runs entirely on your machine.

### Alternative models (edit `.env`):
```bash
# For more RAM (16GB+):
ollama pull llama3.1:8b-instruct-q4_K_M

# For less RAM (4GB):
ollama pull phi3:mini
```

---

## 📊 Scoring Rubric (100 points)

| Dimension | Max | Description |
|-----------|-----|-------------|
| JD Match | 25 | Skills overlap, domain fit, keyword match |
| Education | 10 | Degree relevance, institution quality, GPA |
| Technical Skills | 15 | Depth & breadth, relevance to JD |
| Project Quality | 10 | Techstack alignment, complexity, impact |
| Experience | 15 | Years and relevance vs JD requirement |
| GitHub Activity | 15 | Repos, commits, streak, language match |
| LinkedIn Presence | 10 | Headline, title match, tenure |

---

## 🔌 REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check + Ollama status |
| `/api/v1/evaluate` | POST | Upload resumes + JD → ranked leaderboard |
| `/api/v1/report/{run_id}` | GET | Download JSON/CSV/Markdown |
| `/api/docs` | GET | Swagger UI |

### Example API call
```bash
curl -X POST http://localhost:8080/api/v1/evaluate \
  -F "jd_title=Senior Python Engineer" \
  -F "jd_text=We need a Python expert with FastAPI..." \
  -F "required_skills=Python,FastAPI,PostgreSQL" \
  -F "role_level=senior" \
  -F "resumes=@cv1.pdf" \
  -F "resumes=@cv2.pdf"
```

---

## 🏗️ Architecture

```
Frontend (HTML/CSS/JS)
       │
FastAPI (/api/v1/evaluate)
       │
LangGraph Pipeline:
  1. Ingest    — PyMuPDF + regex resume parsing
  2. Enrich    — GitHub API + LinkedIn (optional) + caching
  3. Score     — Ollama Mistral 7B · 100-pt rubric per candidate
  4. Rank      — Deterministic sort by total score
  5. Output    — JSON + CSV + Markdown reports

Agents: Analyst · Evaluator · Orchestrator
        All run on local Ollama (zero API cost)
```

---

## ⚙️ Optional Integrations

| Integration | Env Var | Benefit |
|-------------|---------|---------|
| GitHub token | `GITHUB_TOKEN` | 5000 req/hr vs 60 req/hr unauthenticated |
| Proxycurl | `PROXYCURL_API_KEY` | Accurate LinkedIn data |

All optional — the agent works without them (lower enrichment quality).

---

## 🧠 Performance Tips (8GB RAM)

- **Use Q4 quantized models** — `mistral:7b-instruct-q4_K_M` uses ~5.5 GB
- **Keep `OLLAMA_NUM_CTX=4096`** — smaller context = less RAM
- **Close other apps** while running evaluations
- **Process resumes sequentially** — concurrency is set to 1 by default
- If inference is slow, try `phi3:mini` (~2.3 GB, faster but lower quality)
