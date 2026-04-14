"""
Question generator prompt — 3 targeted interview questions per candidate.
Derived from detected gaps and unverified claims.
"""

QUESTION_GENERATOR_PROMPT = """\
You are a senior technical interviewer generating targeted interview questions.

Given:
- Job Description requirements
- Candidate's missing skills (with severity)
- Candidate's red flags (potential exaggerations or gaps)
- Candidate's claimed projects and work history

Generate EXACTLY 3 interview questions that:
1. Target the most critical skill gaps (prioritise blockers over preferred).
2. Probe unverified or potentially exaggerated claims.
3. Are open-ended and behavioural (STAR format preferred).
4. Are specific enough that a strong candidate would give a detailed answer.
5. Do NOT ask about protected characteristics.

Return ONLY a JSON array of 3 strings. No numbering. No explanatory text.

=== INPUT ===
Job Title: {jd_title}
Required Skills: {required_skills}

Missing Requirements:
{missing_requirements}

Red Flags:
{red_flags}

Candidate Claims (projects, certs, work history summary):
{candidate_claims}
"""


def question_generator_prompt(
    jd_title: str,
    required_skills: list[str],
    missing_requirements: list[dict],
    red_flags: list[str],
    candidate_claims: str,
) -> str:
    import json
    return QUESTION_GENERATOR_PROMPT.format(
        jd_title=jd_title,
        required_skills=", ".join(required_skills),
        missing_requirements=json.dumps(missing_requirements, indent=2),
        red_flags="\n".join(f"- {f}" for f in red_flags) or "None detected",
        candidate_claims=candidate_claims[:2000],
    )
