import io
import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader

from .config import DATA_DIR, settings


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_clean_text(item) for item in value if _clean_text(item))
    text = str(value)
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def load_json_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [str(item) for item in data if str(item).strip()]
    return []


def extract_resume_text(file_bytes: bytes | None = None, file_path: str | None = None, filename: str | None = None) -> str:
    if file_bytes and filename and filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()

    if file_bytes and filename and filename.lower().endswith(".txt"):
        return file_bytes.decode("utf-8", errors="ignore")

    if file_path and Path(file_path).exists():
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages).strip()
        return path.read_text(encoding="utf-8", errors="ignore")

    return ""


def _extract_json_payload(response_text: str) -> dict[str, Any]:
    text = response_text.strip()
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        return {}


def _generate_with_gemini(prompt: str, api_key: str | None) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("Gemini API key not configured")

    try:
        import google.generativeai as genai
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(f"google-generativeai unavailable: {exc}") from exc

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = getattr(response, "text", "") or ""
    except Exception as exc:  # pragma: no cover - network/credential path
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    if not text:
        raise RuntimeError("Gemini returned no content")
    return _extract_json_payload(text)


def _generate_with_openai(prompt: str, api_key: str | None, model: str | None = None) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("OpenAI API key not configured")

    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(f"openai unavailable: {exc}") from exc

    selected_model = model or settings.openai_model or "gpt-4o-mini"
    candidate_models = [selected_model]
    if selected_model != "gpt-4o-mini":
        candidate_models.append("gpt-4o-mini")
    if selected_model != "gpt-4.1-mini" and "gpt-4.1-mini" not in candidate_models:
        candidate_models.append("gpt-4.1-mini")

    last_error: Exception | None = None
    for attempt_model in candidate_models:
        try:
            client = OpenAI(api_key=api_key)
            request_kwargs: dict[str, Any] = {}
            if "gpt-5" not in attempt_model.lower() and "o1" not in attempt_model.lower():
                request_kwargs["temperature"] = 0.2

            response = client.chat.completions.create(
                model=attempt_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Você é um avaliador profissional. Responda apenas com JSON válido.",
                    },
                    {"role": "user", "content": prompt},
                ],
                **request_kwargs,
            )
            text = response.choices[0].message.content or ""
            if not text:
                raise RuntimeError("OpenAI returned no content")
            return _extract_json_payload(text)
        except Exception as exc:  # pragma: no cover - network/credential path
            last_error = exc

    if last_error is not None:
        raise RuntimeError(f"OpenAI request failed: {last_error}") from last_error
    raise RuntimeError("OpenAI request failed")


def evaluate_job(
    job_data: dict[str, Any],
    resume_text: str,
    skills: list[str] | None = None,
    exclusions: list[str] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    skills = skills or load_json_list(DATA_DIR / "habilidades.json")
    exclusions = exclusions or load_json_list(DATA_DIR / "excludentes.json")

    title = _clean_text(job_data.get("title", ""))
    description = _clean_text(job_data.get("description", ""))
    responsibilities = [_clean_text(item) for item in job_data.get("responsibilities", [])]
    requirements = [_clean_text(item) for item in job_data.get("requirements", [])]
    job_text = " ".join([title, description, *responsibilities, *requirements])

    prompt = f"""
Quero que você atue como um sistema ATS e também como um recrutador técnico experiente, avaliando a aderência de um currículo a uma vaga de emprego. Considere o contexto do currículo e da vaga, e forneça uma resumo com descrição na primeira pessoa (sem usar o Eu) para o ATS me identificar para a vaga.

Contexto do currículo:
{resume_text[:8000]}

Contexto da vaga:
Título: {title}
Descrição: {description}
Responsabilidades: {', '.join(responsibilities)}
Requisitos: {', '.join(requirements)}

Habilidades possíveis: {', '.join(skills)}
Termos excludentes: {', '.join(exclusions)}

Retorne APENAS um JSON válido com os campos:
- decision: "Fit" ou "No-Fit"
- fit_score: número de 0 a 100
- pros: lista de 3 strings
- cons: lista de 3 strings
- recommended_skills: lista com exatamente 3 habilidades da lista fornecida
- pitch: texto de até 1200 caracteres em português, persuasivo e objetivo
- warnings: lista com termos excludentes detectados
- mode: "openai", "gemini" ou "heuristic"
"""

    try:
        payload = _generate_with_openai(prompt, api_key or settings.openai_api_key, settings.openai_model)
    except Exception as exc:
        raise RuntimeError(
            f"Não foi possível gerar a avaliação via OpenAI. {exc}"
        ) from exc

    recommended_skills = payload.get("recommended_skills") or []
    if not isinstance(recommended_skills, list):
        recommended_skills = []
    recommended_skills = [str(item) for item in recommended_skills if str(item).strip()]
    if len(recommended_skills) < 3:
        matched = [skill for skill in skills if skill.lower() in resume_text.lower() and skill.lower() in job_text.lower()]
        if matched:
            recommended_skills = matched[:3]
        else:
            recommended_skills = skills[:3]
    recommended_skills = recommended_skills[:3]

    pitch = str(payload.get("pitch") or "").strip()
    if len(pitch) > 1200:
        pitch = pitch[:1197].rstrip() + "..."

    warnings = payload.get("warnings") or []
    if not isinstance(warnings, list):
        warnings = []
    warnings = [str(item) for item in warnings if str(item).strip()]

    fit_score = payload.get("fit_score")
    try:
        fit_score = int(float(fit_score))
    except (TypeError, ValueError):
        fit_score = 0
    fit_score = max(0, min(100, fit_score))

    decision = str(payload.get("decision") or "No-Fit")
    if decision not in {"Fit", "No-Fit"}:
        decision = "Fit" if fit_score >= 70 else "No-Fit"

    return {
        "decision": decision,
        "fit_score": fit_score,
        "pros": payload.get("pros") or ["Boa aderência ao contexto da vaga"],
        "cons": payload.get("cons") or ["Avaliação ainda pode ser refinada"],
        "recommended_skills": recommended_skills,
        "pitch": pitch,
        "warnings": warnings,
        "mode": payload.get("mode") or "heuristic",
    }
