import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import DATA_DIR, FRONTEND_DIR, settings
from .evaluator import evaluate_job, extract_resume_text, load_json_list
from .scraper import build_gupy_search_url, parse_gupy_page, parse_gupy_search_results

def _fetch_gupy_search_page(search_url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError(f"playwright unavailable: {exc}") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        try:
            page.goto(search_url, wait_until="load", timeout=60000)
            page.wait_for_selector('a[aria-label*="Ir para vaga"]', timeout=25000)
            return page.content()
        finally:
            browser.close()


app = FastAPI(title="Gupy Job Evaluator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/search")
def search_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "search.html")


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return {
        "skills": load_json_list(DATA_DIR / "habilidades.json"),
        "exclusions": load_json_list(DATA_DIR / "excludentes.json"),
    }


@app.post("/api/settings")
def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    skills = payload.get("skills") or []
    exclusions = payload.get("exclusions") or []

    (DATA_DIR / "habilidades.json").write_text(json.dumps(skills, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DATA_DIR / "excludentes.json").write_text(json.dumps(exclusions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {"skills": skills, "exclusions": exclusions}


@app.post("/api/search-jobs")
async def search_jobs(payload: dict[str, Any]) -> dict[str, Any]:
    term = str(payload.get("term") or "product owner").strip() or "product owner"
    page = int(payload.get("page") or 1)
    workplace_types = str(payload.get("workplace_types") or "remote").strip() or "remote"
    search_url = build_gupy_search_url(term=term, page=page, workplace_types=workplace_types)

    try:
        html = await asyncio.to_thread(_fetch_gupy_search_page, search_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to search vacancies: {exc}") from exc

    jobs = parse_gupy_search_results(html, search_url)
    return {
        "term": term,
        "page": page,
        "workplace_types": workplace_types,
        "search_url": search_url,
        "jobs": jobs,
    }


@app.post("/api/evaluate")
async def evaluate(
    url: str = Form(...),
    resume: UploadFile | None = File(None),
    resume_text: str | None = Form(None),
    skills: str | None = Form(None),
    exclusions: str | None = Form(None),
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unable to fetch vacancy page: {exc}") from exc

    job_data = parse_gupy_page(html, url)
    if not job_data.get("title") and not job_data.get("description"):
        raise HTTPException(status_code=400, detail="The page could not be parsed as a Gupy vacancy")
    


    file_bytes = None
    file_name = None
    if resume is not None:
        file_bytes = await resume.read()
        file_name = resume.filename or ""

    if file_bytes is not None and file_name:
        extracted_text = extract_resume_text(file_bytes=file_bytes, filename=file_name)
    elif resume_text:
        extracted_text = resume_text
    else:
        extracted_text = extract_resume_text(file_path=settings.default_resume_path)

    if not extracted_text:
        raise HTTPException(status_code=400, detail="Resume could not be read. Please upload a PDF/TXT or configure a default file path")

    parsed_skills = None
    if skills:
        try:
            parsed_skills = json.loads(skills)
        except json.JSONDecodeError:
            parsed_skills = None

    parsed_exclusions = None
    if exclusions:
        try:
            parsed_exclusions = json.loads(exclusions)
        except json.JSONDecodeError:
            parsed_exclusions = None

    try:
        result = evaluate_job(
            job_data=job_data,
            resume_text=extracted_text,
            skills=parsed_skills or load_json_list(DATA_DIR / "habilidades.json"),
            exclusions=parsed_exclusions or load_json_list(DATA_DIR / "excludentes.json"),
            api_key=settings.openai_api_key,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    result["job"] = job_data
    result["resume_excerpt"] = extracted_text[:2000]
    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
