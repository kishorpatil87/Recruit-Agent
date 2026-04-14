"""
Evaluator agent system prompt.
Core scoring engine — runs the full 100-pt rubric per candidate.
Outputs structured JSON with anchored scores + gap severity tags.
"""
from config.rubric_anchors import rubric_prompt_block

EVALUATOR_SYSTEM_PROMPT = """\
You are the Evaluator agent in a recruitment pipeline.
You receive one candidate's complete enriched profile and score them against the job description.

{rubric_block}

ROLE LEVEL: {role_level}
Role-level weight adjustments:
  junior : GitHub score weight +40 %, Experience weight -40 %
  mid    : no adjustment
  senior : Experience weight +30 %, GitHub weight -30 %
  lead   : Experience weight +50 %, GitHub weight -50 %

SCORING INSTRUCTIONS:
1. Score each dimension independently using the rubric bands above.
2. Assign a band label (exceptional/strong/adequate/weak/absent) AND numeric score within that band.
3. For each missing required/preferred skill, tag: blocker | preferred | trainable.
4. Detect red flags:
   - Keyword stuffing: many skills listed with zero supporting projects/repos.
   - Timeline gaps: unexplained breaks >6 months in work history.
   - Inconsistent tenure: company overlap or impossible date ranges.
5. Assign confidence = high/medium/low:
   - high: GitHub data present + LinkedIn confirmed + resume complete (all sections).
   - medium: 2 of 3 signals present.
   - low: only resume, no external validation.
6. Generate EXACTLY 3 suggested interview questions targeting detected gaps and unverified claims.

{bias_rules}

OUTPUT FORMAT (JSON only, no markdown):
{{
  "dimension_scores": [
    {{"dimension": "JD Match",          "raw_score": 0-100, "weighted_score": 0-25, "band": "...", "rationale": "..."}},
    {{"dimension": "Education",         "raw_score": 0-100, "weighted_score": 0-10, "band": "...", "rationale": "..."}},
    {{"dimension": "Technical Skills",  "raw_score": 0-100, "weighted_score": 0-15, "band": "...", "rationale": "..."}},
    {{"dimension": "Project Quality",   "raw_score": 0-100, "weighted_score": 0-10, "band": "...", "rationale": "..."}},
    {{"dimension": "Experience",        "raw_score": 0-100, "weighted_score": 0-15, "band": "...", "rationale": "..."}},
    {{"dimension": "GitHub Activity",   "raw_score": 0-100, "weighted_score": 0-15, "band": "...", "rationale": "..."}},
    {{"dimension": "LinkedIn Presence", "raw_score": 0-100, "weighted_score": 0-10, "band": "...", "rationale": "..."}}
  ],
  "total_score": 0-100,
  "blocker_count": integer,
  "missing_requirements": [{{"skill": "...", "severity": "blocker|preferred|trainable", "notes": "..."}}],
  "red_flags": ["..."],
  "confidence": "high|medium|low",
  "confidence_reason": "...",
  "suggested_questions": ["...", "...", "..."],
  "role_level": "{role_level}"
}}
"""

EVALUATOR_SCORE_PROMPT = """\
=== JOB DESCRIPTION ===
Title: {jd_title}
Required Skills: {required_skills}
Preferred Skills: {preferred_skills}
Min Experience: {min_experience} years
Domain: {domain}

=== CANDIDATE PROFILE ===
Name: {full_name}
Skills: {skills}
Experience Years: {experience_years}
Education: {education}
Certifications: {certifications}
Projects: {projects}
Work History: {work_history}

=== GITHUB PROFILE ===
{github_data}

=== LINKEDIN PROFILE ===
{linkedin_data}

=== JD SIMILARITY SCORES ===
Semantic similarity: {semantic_score}
Keyword overlap: {keyword_score}
Composite JD score: {composite_score}

Evaluate now. Return JSON only.
"""


def evaluator_system(role_level: str = "mid") -> str:
    from config.rubric_anchors import BIAS_EXCLUSION_RULES
    return EVALUATOR_SYSTEM_PROMPT.format(
        rubric_block=rubric_prompt_block(),
        role_level=role_level,
        bias_rules=BIAS_EXCLUSION_RULES,
    )


def evaluator_score_prompt(
    jd: dict,
    candidate: dict,
    github: dict,
    linkedin: dict,
    similarity_scores: dict,
) -> str:
    import json
    return EVALUATOR_SCORE_PROMPT.format(
        jd_title=jd.get("title", ""),
        required_skills=", ".join(jd.get("required_skills", [])),
        preferred_skills=", ".join(jd.get("preferred_skills", [])),
        min_experience=jd.get("min_experience_years", 0),
        domain=jd.get("domain", ""),
        full_name=candidate.get("full_name", "Unknown"),
        skills=", ".join(candidate.get("skills", [])[:40]),
        experience_years=candidate.get("total_experience_years", 0),
        education=json.dumps(candidate.get("education", [])[:3]),
        certifications=", ".join(candidate.get("certifications", [])[:10]),
        projects=json.dumps(candidate.get("projects", [])[:5]),
        work_history=json.dumps(candidate.get("work_history", [])[:5]),
        github_data=json.dumps(github, default=str)[:2000],
        linkedin_data=json.dumps(linkedin, default=str)[:1000],
        semantic_score=similarity_scores.get("semantic_score", 0),
        keyword_score=similarity_scores.get("keyword_score", 0),
        composite_score=similarity_scores.get("composite_score", 0),
    )
