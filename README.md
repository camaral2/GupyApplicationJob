# Gupy Application

A local application designed to evaluate Gupy job postings, compare them against a resume, and generate an application pitch.

![Flow](flow.png)

## Features

* Job evaluation from a URL
* Resume data extraction from PDF/TXT files
* Generation of application pitches and skill suggestions
* Gupy job search with a batch evaluation workflow

## Project Structure

* `backend/`: FastAPI API, scraper, and evaluation engine
* `frontend/`: Static web interface
* `tests/`: Automated tests

## Requirements

* Python 3.11+
* Dependencies listed in `backend/requirements.txt`

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Running the Application

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Access:

* [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* [http://127.0.0.1:8000/search](http://127.0.0.1:8000/search)

## Environment Variables

Copy the `.env.example` file to `.env` and fill in the local values, such as your OpenAI API key and the default resume path.

```bash
cp .env.example .env
```

For authentication and user data persistence, configure a PostgreSQL connection string (Supabase), for example:

```bash
DATABASE_URL=postgresql://postgres:your_password@db.your-project-ref.supabase.co:5432/postgres?sslmode=require
```
