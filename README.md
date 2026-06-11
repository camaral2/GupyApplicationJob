# Inscrição Gupy

Aplicação local para avaliar vagas do Gupy, comparar com um currículo e gerar um pitch de candidatura.

## Funcionalidades

- Avaliação de vagas a partir de URL
- Extração de dados de currículo em PDF/TXT
- Geração de pitch e sugestão de habilidades
- Busca de vagas no Gupy com fluxo de avaliação em lote

## Estrutura

- `backend/`: API FastAPI, scraper e avaliador
- `frontend/`: interface web estática
- `tests/`: testes automatizados

## Requisitos

- Python 3.11+
- Dependências do arquivo `backend/requirements.txt`

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Execução

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Acesse:
- http://127.0.0.1:8000/
- http://127.0.0.1:8000/search

## Variáveis de ambiente

Crie um arquivo `.env` com as configurações necessárias, como chave da OpenAI e caminho do currículo padrão.
