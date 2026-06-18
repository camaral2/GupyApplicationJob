import asyncio
import json
import os
import warnings
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import DATA_DIR, FRONTEND_DIR, settings
from .db_store import DatabaseStore
from .evaluator import evaluate_job, extract_resume_text, load_json_list
from .scraper import build_gupy_search_url, parse_gupy_page, parse_gupy_search_results

# Suprime warning conhecido do pypdf/cryptography (não afeta execução).
warnings.filterwarnings(
    "ignore",
    message=".*ARC4 has been moved to cryptography.hazmat.decrepit.ciphers.algorithms.ARC4.*",
    category=Warning,
)

def _fetch_gupy_search_page(search_url: str) -> str:
    # Em Vercel, evitar Playwright para não disparar erros internos de subprocesso.
    if os.getenv("VERCEL") != "1":
        try:
            from playwright.sync_api import sync_playwright
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
        except Exception:
            pass

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    with httpx.Client(timeout=25.0, follow_redirects=True, headers=headers) as client:
        response = client.get(search_url)
        response.raise_for_status()
        return response.text


app = FastAPI(title="Gupy Job Evaluator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
if not settings.database_url:
    raise RuntimeError("DATABASE_URL não configurada. Configure a conexão PostgreSQL (Supabase).")
db_store = DatabaseStore(settings.database_url)
db_store.init_schema()


def _require_user(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Usuário não autenticado.")
    token = authorization.replace("Bearer ", "", 1).strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sessão inválida.")
    email = db_store.get_email_by_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Sessão expirada ou inválida.")
    return email


@app.get("/")
def home() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/evaluate")
def evaluate_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/search")
def search_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "search.html")


@app.post("/api/auth/register")
def register(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Informe um email válido.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter pelo menos 6 caracteres.")
    try:
        profile = db_store.register_user(email, password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return profile


@app.post("/api/auth/login")
def login(payload: dict[str, Any]) -> dict[str, Any]:
    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    try:
        return db_store.login_user(email, password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/auth/me")
def me(request: Request) -> dict[str, str]:
    email = _require_user(request)
    return {"email": email}


@app.post("/api/auth/logout")
def logout(request: Request) -> dict[str, str]:
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "", 1).strip()
        if token:
            db_store.revoke_token(token)
    return {"status": "ok"}


@app.get("/api/settings")
def get_settings(request: Request) -> dict[str, Any]:
    email = _require_user(request)
    user_data = db_store.load_user_data(email)
    default_skills = load_json_list(DATA_DIR / "habilidades.json")
    default_exclusions = load_json_list(DATA_DIR / "excludentes.json")
    return {
        "skills": user_data.get("skills") or default_skills,
        "exclusions": user_data.get("exclusions") or default_exclusions,
        "resume_text": user_data.get("resume_text") or "",
        "resume_file_name": user_data.get("resume_file_name") or "",
        "resume_updated_at": user_data.get("resume_updated_at") or "",
    }


@app.post("/api/settings")
def save_settings(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    email = _require_user(request)
    skills = payload.get("skills") or []
    exclusions = payload.get("exclusions") or []
    resume_text = str(payload.get("resume_text") or "")
    resume_file_name = str(payload.get("resume_file_name") or "")

    data = db_store.save_user_data(
        email,
        {
            "skills": skills,
            "exclusions": exclusions,
            "resume_text": resume_text,
            "resume_file_name": resume_file_name,
        },
    )
    return data


@app.get("/api/validated-jobs")
def get_validated_jobs(request: Request) -> dict[str, list[str]]:
    email = _require_user(request)
    data = db_store.load_user_data(email)
    return {"validated_jobs": data.get("validated_jobs") or []}


@app.post("/api/validated-jobs")
def add_validated_job(payload: dict[str, Any], request: Request) -> dict[str, list[str]]:
    email = _require_user(request)
    job_url = str(payload.get("job_url") or "").strip()
    if not job_url:
        raise HTTPException(status_code=400, detail="job_url é obrigatório.")
    data = db_store.add_validated_job(email, job_url)
    return {"validated_jobs": data.get("validated_jobs") or []}


@app.delete("/api/validated-jobs")
def remove_validated_job(payload: dict[str, Any], request: Request) -> dict[str, list[str]]:
    email = _require_user(request)
    job_url = str(payload.get("job_url") or "").strip()
    if not job_url:
        raise HTTPException(status_code=400, detail="job_url é obrigatório.")
    data = db_store.remove_validated_job(email, job_url)
    return {"validated_jobs": data.get("validated_jobs") or []}


@app.post("/api/search-jobs")
async def search_jobs(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    _require_user(request)
    term = str(payload.get("term") or "product owner").strip() or "product owner"
    page = int(payload.get("page") or 1)
    workplace_types = str(payload.get("workplace_types") or "remote").strip() or "remote"
    search_url = build_gupy_search_url(term=term, page=page, workplace_types=workplace_types)

    try:
        html = await asyncio.to_thread(_fetch_gupy_search_page, search_url)
    
        print(f"Fetched search results for '{term}' (page {page}, workplace: {workplace_types})")
        print(f"Search URL: {search_url}")
        print(f"HTML content length: {len(html)} characters")
        
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
    request: Request,
    url: str = Form(...),
    resume: UploadFile | None = File(None),
    resume_text: str | None = Form(None),
    skills: str | None = Form(None),
    exclusions: str | None = Form(None),
) -> dict[str, Any]:
    email = _require_user(request)
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
    
    user_data = db_store.load_user_data(email)
    default_skills = load_json_list(DATA_DIR / "habilidades.json")
    default_exclusions = load_json_list(DATA_DIR / "excludentes.json")

    file_bytes = None
    file_name = None
    if resume is not None:
        file_bytes = await resume.read()
        file_name = resume.filename or ""

    if file_bytes is not None and file_name:
        extracted_text = extract_resume_text(file_bytes=file_bytes, filename=file_name)
    elif resume_text:
        extracted_text = resume_text
    elif user_data.get("resume_text"):
        extracted_text = str(user_data.get("resume_text") or "")
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

    # Mantém o currículo em cache por usuário para próximas análises.
    if extracted_text:
        db_store.save_user_data(
            email,
            {
                "resume_text": extracted_text,
                "resume_file_name": file_name or user_data.get("resume_file_name") or "",
            },
        )

    try:
        result = evaluate_job(
            job_data=job_data,
            resume_text=extracted_text,
            skills=parsed_skills or user_data.get("skills") or default_skills,
            exclusions=parsed_exclusions or user_data.get("exclusions") or default_exclusions,
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
