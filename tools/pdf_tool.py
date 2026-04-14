"""
PDF / DOCX / TXT resume parser.
Uses PyMuPDF for primary PDF extraction with pdfplumber as fallback.
Includes specific logic to extract hidden hyperlinks (URI actions).
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

# ─── Import guards ────────────────────────────────────────────────────────────
try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

try:
    from docx import Document as DocxDocument
    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False


# ─── Text & Link extraction ───────────────────────────────────────────────────

def extract_text_from_pdf(path: str) -> str:
    """
    Extract text AND hyperlinks from PDF.
    Many resumes use 'LinkedIn' or 'GitHub' as display text for a hidden hyperlink.
    """
    text = ""
    links = []
    
    if _HAS_FITZ:
        try:
            doc = fitz.open(path)
            pages = []
            for page in doc:
                # 1. Extract visible text blocks
                blocks = page.get_text("blocks")
                blocks.sort(key=lambda b: (b[1], b[0]))
                pages.append("\n".join(b[4].strip() for b in blocks if b[4].strip()))
                
                # 2. Extract hidden hyperlinks (URIs)
                for link in page.get_links():
                    if link.get("kind") == fitz.LINK_URI:
                        uri = link.get("uri", "")
                        if uri:
                            links.append(uri)
            
            text = "\n\n".join(pages)
            # Append links to the end of text so regex extractors can find them
            if links:
                text += "\n\n--- EXTRACTED LINKS ---\n" + "\n".join(list(set(links)))
            
            doc.close()
        except Exception as e:
            log.warning("PyMuPDF failed, falling back to pdfplumber", error=str(e))

    if not text.strip() and _HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(path) as pdf:
                text = "\n\n".join(
                    page.extract_text(layout=True) or "" for page in pdf.pages
                )
        except Exception as e:
            log.error("pdfplumber also failed", error=str(e))

    return text.strip()


def extract_text_from_docx(path: str) -> str:
    """Extract text from DOCX, including targets of hidden hyperlinks."""
    if not _HAS_DOCX:
        raise ImportError("python-docx not installed")
    doc = DocxDocument(path)
    text_parts = []
    links = []

    # Relationships map (rId -> Target URL)
    rels = doc.part.rels

    for p in doc.paragraphs:
        text_parts.append(p.text)
        
        # Search for hyperlinks in the XML of this paragraph
        # (This is more robust for 'LinkedIn | GitHub' where the link is on the word)
        from docx.oxml.ns import qn
        hyperlink_nodes = p._element.xpath(".//w:hyperlink")
        for node in hyperlink_nodes:
            rId = node.get(qn("r:id"))
            if rId and rId in rels:
                url = rels[rId].target_ref
                if url.startswith("http"):
                    links.append(url)

    text = "\n".join(t for t in text_parts if t.strip())
    if links:
        text += "\n\n--- EXTRACTED LINKS ---\n" + "\n".join(list(set(links)))
    
    return text.strip()


def extract_text_from_txt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def extract_text(path: str) -> str:
    """Dispatch to the right extractor based on file extension."""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    elif suffix in (".docx", ".doc"):
        return extract_text_from_docx(path)
    elif suffix == ".txt":
        return extract_text_from_txt(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


# ─── Regex field extractors ───────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,5}[\s\-]?\d{4,6}"
)
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9\-_]+)", re.IGNORECASE)
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in/)?([A-Za-z0-9\-_%]+)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")

_SECTION_HEADERS = {
    "skills":          re.compile(r"^\s*(?:technical\s+)?skills?\s*:?\s*$", re.IGNORECASE | re.MULTILINE),
    "experience":      re.compile(r"^\s*(?:work\s+)?experience\s*:?\s*$", re.IGNORECASE | re.MULTILINE),
    "education":       re.compile(r"^\s*education\s*:?\s*$", re.IGNORECASE | re.MULTILINE),
    "certifications":  re.compile(r"^\s*certifications?\s*:?\s*$", re.IGNORECASE | re.MULTILINE),
    "projects":        re.compile(r"^\s*projects?\s*:?\s*$", re.IGNORECASE | re.MULTILINE),
}


def _extract_email(text: str) -> str:
    m = _EMAIL_RE.search(text)
    return m.group(0) if m else ""


def _extract_phone(text: str) -> str:
    m = _PHONE_RE.search(text)
    return m.group(0).strip() if m else ""


def _extract_github_url(text: str) -> str:
    m = _GITHUB_RE.search(text)
    if m:
        user = m.group(1).rstrip("/")
        # Skip common words that might look like users if we grabbed wrong thing
        if user.lower() in ("search", "explore", "trending", "pricing", "marketplace"):
            return ""
        return f"https://github.com/{user}"
    return ""


def _extract_linkedin_url(text: str) -> str:
    m = _LINKEDIN_RE.search(text)
    if m:
        user = m.group(1).rstrip("/")
        if user.lower() in ("share", "feed", "jobs", "messaging", "notifications"):
            return ""
        return f"https://www.linkedin.com/in/{user}"
    return ""


def _extract_name_heuristic(text: str) -> str:
    """Take the first non-empty line that looks like a name."""
    lines = text.splitlines()
    # Try the very first non-empty line first
    for line in lines[:5]:
        line = line.strip()
        if not line or _URL_RE.search(line) or _EMAIL_RE.search(line) or "@" in line:
            continue
        # Names are usually 2-3 words.
        words = line.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() or not w.isalpha() for w in words):
            clean_name = line.strip("|").strip()
            if not any(c.isdigit() for c in clean_name):
                return clean_name
    return ""


def _extract_section(text: str, header_pattern: re.Pattern) -> str:
    """Return text between a section header and the next section header."""
    all_headers = list(_SECTION_HEADERS.values())
    m = header_pattern.search(text)
    if not m:
        return ""
    start = m.end()
    end = len(text)
    for hp in all_headers:
        if hp.pattern == header_pattern.pattern:
            continue
        nxt = hp.search(text, start)
        if nxt and nxt.start() < end:
            end = nxt.start()
    return text[start:end].strip()


def _parse_skills(text: str) -> list[str]:
    skills_text = _extract_section(text, _SECTION_HEADERS["skills"])
    if not skills_text:
        return []
    raw = re.split(r"[,|\n;•▪●\-\*]+", skills_text)
    skills = []
    for s in raw:
        s = s.strip().strip("()[]")
        if 2 < len(s) < 60 and not s.lower().startswith("skill"):
            skills.append(s)
    return list(dict.fromkeys(skills))


def _parse_experience_years(text: str) -> float:
    explicit = re.search(
        r"(\d+(?:\.\d+)?)\s*\+?\s*years?\s+(?:of\s+)?(?:experience|exp)", text, re.IGNORECASE
    )
    if explicit:
        return float(explicit.group(1))

    # Date range accumulation
    import datetime
    months_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    date_range_re = re.compile(
        r"(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})"
        r"\s*[–\-—to]+\s*"
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|Present|Current|Now)",
        re.IGNORECASE,
    )
    total_months = 0
    now = datetime.datetime.utcnow()

    for m in date_range_re.finditer(text):
        try:
            start_str, end_str = m.group(1).strip(), m.group(2).strip()
            start_parts = start_str.split()
            s_month, s_year = months_map.get(start_parts[0][:3].lower(), 1), int(start_parts[1])
            if end_str.lower() in ("present", "current", "now"):
                e_month, e_year = now.month, now.year
            else:
                end_parts = end_str.split()
                e_month, e_year = months_map.get(end_parts[0][:3].lower(), 1), int(end_parts[1])
            total_months += max(0, (e_year - s_year) * 12 + (e_month - s_month))
        except Exception:
            continue
    return round(total_months / 12, 1) if total_months > 0 else 0.0


def _parse_education(text: str) -> list[dict]:
    edu_text = _extract_section(text, _SECTION_HEADERS["education"])
    if not edu_text:
        edu_text = text  # fallback to full text
    results = []
    degree_re = re.compile(
        r"(?P<degree>B\.?(?:Tech|E|Sc|A)|M\.?(?:Tech|E|Sc|A|S)|MBA|PhD|Bachelor|Master|Associate)[^,\n]*"
        r"(?:[,\s]+(?P<institution>[A-Z][^,\n]+))?",
        re.IGNORECASE,
    )
    year_re = re.compile(r"\b(19|20)\d{2}\b")
    gpa_re = re.compile(r"(?:CGPA|GPA|CPI)\s*[:\-]?\s*(\d+\.?\d*)", re.IGNORECASE)
    pct_re = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*%", re.IGNORECASE)

    for m in degree_re.finditer(edu_text):
        entry = {"degree": m.group("degree").strip(), "institution": (m.group("institution") or "").strip()}
        context = edu_text[max(0, m.start() - 20):min(len(edu_text), m.end() + 120)]
        years = year_re.findall(context)
        if years:
            entry["year"] = years[-1]
        gpa_m = gpa_re.search(context)
        if gpa_m:
            entry["gpa"] = gpa_m.group(1)
        else:
            pct_m = pct_re.search(context)
            if pct_m:
                val = float(pct_m.group(1))
                if 30 <= val <= 100:
                    entry["percentage"] = str(val)
        results.append(entry)
    return results


def _parse_certifications(text: str) -> list[str]:
    cert_text = _extract_section(text, _SECTION_HEADERS["certifications"]) or text
    certs = []
    cert_re = re.compile(
        r"(?:AWS|Google Cloud|GCP|Azure|PMP|CPA|CFA|CKA|CKAD|CISSP|CEH|NVIDIA|"
        r"Certified[A-Za-z\s]+|Coursera[^\n,]+|Udemy[^\n,]+)",
        re.IGNORECASE,
    )
    for m in cert_re.finditer(cert_text):
        c = m.group(0).strip()
        if 5 < len(c) < 100: certs.append(c)
    return list(dict.fromkeys(certs))


# Common tech keywords for project techstack detection
_TECH_KEYWORDS = re.compile(
    r"\b(?:Python|Java|JavaScript|TypeScript|React|Angular|Vue|Node\.?js|Express|"
    r"Django|Flask|FastAPI|Spring|Docker|Kubernetes|AWS|GCP|Azure|MongoDB|MySQL|"
    r"PostgreSQL|Redis|Kafka|TensorFlow|PyTorch|Scikit|BERT|GPT|LLM|FAISS|"
    r"LangChain|Streamlit|Power\s?BI|Tableau|MLflow|CI/CD|Git|Linux|SQL|"
    r"Next\.?js|Tailwind|GraphQL|REST|gRPC|S3|EC2|Lambda|Spark|Hadoop|"
    r"Pandas|NumPy|Matplotlib|OpenCV|NLP|CNN|RNN|LSTM|Transformer)\b",
    re.IGNORECASE,
)


def _parse_projects(text: str) -> list[dict]:
    proj_text = _extract_section(text, _SECTION_HEADERS["projects"])
    projects = []
    current_name = ""
    current_lines = []

    for line in proj_text.splitlines():
        stripped = line.strip().lstrip("•●▪-*").strip()
        if not stripped or len(stripped) < 5:
            continue
        # Heuristic: project title lines are shorter, often have parentheses with dates
        is_title = (len(stripped) < 80 and not stripped.startswith("•") and
                    (re.search(r"\(\w+\s*\d{4}\)", stripped) or
                     (len(stripped.split()) <= 10 and any(c.isupper() for c in stripped[:3]))))
        if is_title and current_lines:
            desc = " ".join(current_lines)
            techs = list(set(_TECH_KEYWORDS.findall(desc + " " + current_name)))
            projects.append({"name": current_name, "description": desc, "techstack": techs})
            current_name = stripped
            current_lines = []
        elif is_title:
            current_name = stripped
        else:
            current_lines.append(stripped)

    # Last project
    if current_name or current_lines:
        desc = " ".join(current_lines)
        techs = list(set(_TECH_KEYWORDS.findall(desc + " " + (current_name or ""))))
        projects.append({
            "name": current_name or desc[:60],
            "description": desc,
            "techstack": techs,
        })

    # Fallback: if no structured projects found, treat each line as a project
    if not projects:
        for line in proj_text.splitlines():
            line = line.strip().lstrip("•●▪-*")
            if line and len(line) > 10:
                techs = list(set(_TECH_KEYWORDS.findall(line)))
                projects.append({"description": line, "techstack": techs})

    return projects[:10]


# ─── Public API ───────────────────────────────────────────────────────────────

def parse_resume(path: str, candidate_id: str | None = None) -> dict:
    """Parse a resume file and return a dict matching ParsedResume schema."""
    candidate_id = candidate_id or str(uuid.uuid4())
    text = extract_text(path)

    result = {
        "candidate_id": candidate_id,
        "raw_path": str(Path(path).resolve()),
        "raw_text": text,
        "full_name": _extract_name_heuristic(text),
        "email": _extract_email(text),
        "phone": _extract_phone(text),
        "github_url": _extract_github_url(text),
        "linkedin_url": _extract_linkedin_url(text),
        "skills": _parse_skills(text),
        "total_experience_years": _parse_experience_years(text),
        "education": _parse_education(text),
        "certifications": _parse_certifications(text),
        "projects": _parse_projects(text),
        "work_history": [],
    }

    log.info("Resume parsed", name=result["full_name"], github=bool(result["github_url"]))
    return result
