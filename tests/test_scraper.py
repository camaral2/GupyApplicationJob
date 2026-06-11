import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.scraper import parse_gupy_page, parse_gupy_search_results


def test_parse_gupy_page_from_next_data():
    html = '''
    <html><head><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"job":{"name":"Desenvolvedor Backend","jobDescription":"Trabalhar com APIs e bancos de dados","responsibilities":["Criar endpoints"],"requirements":["Python"]},"applyUrl":"https://jobs.gupy.io/123"}}}</script></head><body></body></html>
    '''

    result = parse_gupy_page(html)

    assert result["title"] == "Desenvolvedor Backend"
    assert result["description"] == "Trabalhar com APIs e bancos de dados"
    assert result["responsibilities"] == ["Criar endpoints"]
    assert result["requirements"] == ["Python"]
    assert result["apply_url"] == "https://jobs.gupy.io/123"


def test_parse_gupy_page_fallback_to_basic_html():
    html = '''
    <html><head><title>Analista de Dados</title></head><body>
    <h1>Analista de Dados</h1>
    <div class="job-description">Analisar dados em Python</div>
    <div class="responsibilities">Criar dashboards</div>
    <div class="requirements">SQL</div>
    </body></html>
    '''

    result = parse_gupy_page(html)

    assert result["title"] == "Analista de Dados"
    assert result["description"] == "Analisar dados em Python"
    assert result["responsibilities"] == ["Criar dashboards"]
    assert result["requirements"] == ["SQL"]


def test_parse_gupy_page_extracts_apply_url_from_cta_link():
    html = '''
    <html><head><title>Desenvolvedor Python</title></head><body>
    <h1>Desenvolvedor Python</h1>
    <p>Vaga para desenvolver APIs</p>
    <a href="/candidates/jobs/11206363/apply?jobBoardSource=gupy_portal" data-testid="job-cta-link">Candidatar-se</a>
    </body></html>
    '''

    result = parse_gupy_page(html, url="https://www.gupy.io/vagas/11206363")

    assert result["apply_url"] == "https://www.gupy.io/candidates/jobs/11206363/apply?jobBoardSource=gupy_portal"


def test_parse_gupy_search_results_from_rendered_links():
    html = '''
    <html><body>
      <a aria-label="Ir para vaga Product Owner Sr. da empresa Lojacorr - Carreiras" href="https://lojacorr.gupy.io/job/123?jobBoardSource=gupy_portal">Lojacorr</a>
      <a aria-label="Ir para vaga Analista de Negócios da empresa ACME" href="https://acme.gupy.io/job/456?jobBoardSource=gupy_portal">ACME</a>
    </body></html>
    '''

    results = parse_gupy_search_results(html)

    assert results[0]["title"] == "Product Owner Sr."
    assert results[0]["company"] == "Lojacorr - Carreiras"
    assert results[0]["url"] == "https://lojacorr.gupy.io/job/123?jobBoardSource=gupy_portal"
    assert results[1]["title"] == "Analista de Negócios"
