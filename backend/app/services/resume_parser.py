"""Resume parser — extract text from PDF/DOCX, parse with Claude."""
import io
import json
from typing import Any
import anthropic
from app.core.config import settings


async def extract_text(file_bytes: bytes, mime_type: str) -> str:
    if "pdf" in mime_type:
        from pdfminer.high_level import extract_text as pdf_extract
        return pdf_extract(io.BytesIO(file_bytes))
    else:
        import docx2txt, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(file_bytes)
            path = f.name
        try:
            return docx2txt.process(path)
        finally:
            os.unlink(path)


async def parse_resume_with_claude(resume_text: str) -> dict[str, Any]:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    prompt = f"""Parse this resume into the exact JSON schema below.
Only include information explicitly present. Use null for absent fields.
Output ONLY valid JSON — no markdown, no commentary.

Resume:
---
{resume_text[:8000]}
---

Output this schema:
{{
  "contact": {{"name":null,"email":null,"phone":null,"location":null,"linkedin":null,"github":null}},
  "summary": null,
  "experience": [{{"title":"","company":"","location":null,"start_date":null,"end_date":null,"bullets":[]}}],
  "education": [{{"degree":"","field":null,"institution":"","graduation_year":null}}],
  "skills": {{"technical":[],"tools":[],"languages":[],"soft":[]}},
  "certifications": [{{"name":"","issuer":null,"year":null}}],
  "projects": [{{"name":"","description":null,"tech_stack":[],"url":null}}],
  "total_years_experience": null
}}"""

    message = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
