"""
Rubric anchor definitions — 100-point scoring scale.
7 dimensions: JD Match, Education, Technical Skills, Project Quality,
Experience, GitHub Activity, LinkedIn Presence.
Each dimension has explicit band descriptors so scores don't drift
across runs or agents.  Evaluator LLM receives these verbatim.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ScoreBand = Literal["exceptional", "strong", "adequate", "weak", "absent"]
GapSeverity = Literal["blocker", "preferred", "trainable"]


@dataclass(frozen=True)
class BandAnchor:
    band: ScoreBand
    score_range: tuple[int, int]
    descriptor: str


@dataclass(frozen=True)
class RubricDimension:
    name: str
    max_points: int
    weight_key: str          # matches Settings.weights key
    bands: list[BandAnchor] = field(default_factory=list)


# ─── Band Anchors per dimension ──────────────────────────────────────────────

_JD_BANDS: list[BandAnchor] = [
    BandAnchor("exceptional", (90, 100),
               "Candidate meets or exceeds every required skill and has bonus preferred skills. "
               "Keyword overlap >90 %, semantic similarity >0.90."),
    BandAnchor("strong",      (75, 89),
               "Meets all required skills; 1-2 preferred skills missing. "
               "Keyword overlap 70-90 %, semantic similarity 0.75-0.89."),
    BandAnchor("adequate",    (50, 74),
               "Meets core required skills but has notable gaps in preferred skills. "
               "Keyword overlap 40-69 %."),
    BandAnchor("weak",        (25, 49),
               "Several required skills absent or unverified. "
               "Keyword overlap <40 %."),
    BandAnchor("absent",      (0, 24),
               "Major required skills missing; severe mismatch."),
]

_EDUCATION_BANDS: list[BandAnchor] = [
    BandAnchor("exceptional", (90, 100),
               "Advanced degree (Masters/PhD) in a directly relevant field, "
               "high GPA/percentage (>85%), from a reputable institution."),
    BandAnchor("strong",      (75, 89),
               "Bachelors or Masters in a relevant field, good GPA/percentage (70-85%), "
               "from a solid institution."),
    BandAnchor("adequate",    (50, 74),
               "Degree in a related field (not directly relevant), acceptable percentage, "
               "or relevant degree from a lesser-known institution."),
    BandAnchor("weak",        (25, 49),
               "Degree in an unrelated field, low percentage, or only associate/diploma level."),
    BandAnchor("absent",      (0, 24),
               "No degree information provided, or irrelevant education background."),
]

_TECHNICAL_SKILLS_BANDS: list[BandAnchor] = [
    BandAnchor("exceptional", (90, 100),
               "Deep expertise in required tech stack, broad skill coverage, "
               "advanced tools/frameworks proficiency, evidence of using them in projects/work."),
    BandAnchor("strong",      (75, 89),
               "Strong alignment with required skills, good breadth, "
               "most preferred skills present, evidence of practical usage."),
    BandAnchor("adequate",    (50, 74),
               "Has core required skills but lacks depth or breadth, "
               "some preferred skills missing, limited evidence of advanced usage."),
    BandAnchor("weak",        (25, 49),
               "Few required skills present, narrow skill set, "
               "mostly basic/common skills without specialization."),
    BandAnchor("absent",      (0, 24),
               "Critical required skills missing entirely, skill set does not align with JD."),
]

_PROJECT_QUALITY_BANDS: list[BandAnchor] = [
    BandAnchor("exceptional", (90, 100),
               "Projects use tech stack aligned with JD, show high complexity, "
               "real-world impact/deployment, well-described with measurable outcomes."),
    BandAnchor("strong",      (75, 89),
               "Projects partially align with JD tech stack, good complexity, "
               "some real-world application, adequately described."),
    BandAnchor("adequate",    (50, 74),
               "Projects exist but tech stack partially relevant, moderate complexity, "
               "mostly academic/personal projects."),
    BandAnchor("weak",        (25, 49),
               "Few projects, irrelevant tech stack, low complexity, "
               "poorly described or trivial."),
    BandAnchor("absent",      (0, 24),
               "No projects listed or projects completely irrelevant to JD."),
]

_EXPERIENCE_BANDS: list[BandAnchor] = [
    BandAnchor("exceptional", (90, 100),
               "Years of experience exceeds JD requirement by >2 years; "
               "consistent tenure at senior/relevant companies, clear career growth."),
    BandAnchor("strong",      (75, 89),
               "Meets JD requirement; roles clearly relevant, good tenure."),
    BandAnchor("adequate",    (50, 74),
               "Slightly below requirement (≤1 year gap) OR roles partially relevant."),
    BandAnchor("weak",        (25, 49),
               "Significant experience gap (>1 year) or frequent unexplained gaps."),
    BandAnchor("absent",      (0, 24),
               "No verifiable experience in the required domain."),
]

_GITHUB_BANDS: list[BandAnchor] = [
    BandAnchor("exceptional", (90, 100),
               ">50 public repos, daily contribution streak >60 days, top language matches JD, "
               "pinned repos highly relevant, active PRs/issues."),
    BandAnchor("strong",      (75, 89),
               "20-50 repos, streak 30-60 days, language alignment moderate-strong."),
    BandAnchor("adequate",    (50, 74),
               "5-19 repos, some activity, language partially aligned."),
    BandAnchor("weak",        (25, 49),
               "<5 repos or near-zero activity, language mismatch."),
    BandAnchor("absent",      (0, 24),
               "No GitHub profile, or profile exists but zero contribution data."),
]

_LINKEDIN_BANDS: list[BandAnchor] = [
    BandAnchor("exceptional", (90, 100),
               "Profile exists, headline directly matches target role, "
               "tenure at relevant companies, strong endorsements."),
    BandAnchor("strong",      (75, 89),
               "Profile exists, headline partially matches, relevant tenure."),
    BandAnchor("adequate",    (50, 74),
               "Profile exists but headline/title vague or in different domain."),
    BandAnchor("weak",        (25, 49),
               "Profile found but minimal information."),
    BandAnchor("absent",      (0, 24),
               "No LinkedIn profile found or URL invalid."),
]


# ─── Full rubric ─────────────────────────────────────────────────────────────

RUBRIC: list[RubricDimension] = [
    RubricDimension(
        name="JD Match",
        max_points=25,
        weight_key="jd_match",
        bands=_JD_BANDS,
    ),
    RubricDimension(
        name="Education",
        max_points=10,
        weight_key="education",
        bands=_EDUCATION_BANDS,
    ),
    RubricDimension(
        name="Technical Skills",
        max_points=15,
        weight_key="technical_skills",
        bands=_TECHNICAL_SKILLS_BANDS,
    ),
    RubricDimension(
        name="Project Quality",
        max_points=10,
        weight_key="project_quality",
        bands=_PROJECT_QUALITY_BANDS,
    ),
    RubricDimension(
        name="Experience",
        max_points=15,
        weight_key="experience",
        bands=_EXPERIENCE_BANDS,
    ),
    RubricDimension(
        name="GitHub Activity",
        max_points=15,
        weight_key="github",
        bands=_GITHUB_BANDS,
    ),
    RubricDimension(
        name="LinkedIn Presence",
        max_points=10,
        weight_key="linkedin",
        bands=_LINKEDIN_BANDS,
    ),
]

TOTAL_POINTS = sum(d.max_points for d in RUBRIC)  # always 100


# ─── Gap severity tags ────────────────────────────────────────────────────────

def classify_gap_severity(skill: str, is_required: bool, candidate_has: bool) -> GapSeverity | None:
    """Classify whether a missing skill is a blocker, preferred gap, or trainable."""
    if candidate_has:
        return None
    if is_required:
        return "blocker"
    # Heuristic: skills marked preferred in JD → preferred; others → trainable
    return "preferred"


# ─── Bias exclusion list ─────────────────────────────────────────────────────

BIAS_EXCLUSION_FIELDS = frozenset({
    "name",
    "gender",
    "age",
    "nationality",
    "photo",
    "marital_status",
    "institution_prestige",
    "career_gap_penalty",
})

BIAS_EXCLUSION_RULES = """
STRICT BIAS EXCLUSION RULES (apply to every evaluation):
1. Do NOT infer gender, ethnicity, or nationality from name.
2. Do NOT penalise career gaps without explicit context (e.g. layoff notice, parental leave).
3. Do NOT score institution prestige — only skill and experience evidence.
4. Do NOT reward or penalize based on photo, age, or marital status.
5. Score only verifiable evidence from resume text and external API data.
"""


# ─── Rubric as formatted prompt string ───────────────────────────────────────

def rubric_prompt_block() -> str:
    lines = ["=== SCORING RUBRIC (100 points total) ===\n"]
    for dim in RUBRIC:
        lines.append(f"## {dim.name} — max {dim.max_points} pts")
        for band in dim.bands:
            lo, hi = band.score_range
            pct_lo = int(lo * dim.max_points / 100)
            pct_hi = int(hi * dim.max_points / 100)
            lines.append(f"  [{pct_lo}–{pct_hi} pts] {band.band.upper()}: {band.descriptor}")
        lines.append("")
    lines.append(BIAS_EXCLUSION_RULES)
    return "\n".join(lines)
