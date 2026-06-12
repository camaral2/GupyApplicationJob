const state = {
  jobs: [],
  term: "product owner",
  page: 1,
  processed: new Set(JSON.parse(localStorage.getItem("gupyProcessedJobs") || "[]")),
};

const searchForm = document.getElementById("search-form");
const termInput = document.getElementById("term-input");
const workplaceInput = document.getElementById("workplace-input");
const results = document.getElementById("results");
const statusMessage = document.getElementById("status-message");
const prevPageButton = document.getElementById("prev-page");
const nextPageButton = document.getElementById("next-page");
const pageInfo = document.getElementById("page-info");

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}

function persistProcessedJobs() {
  localStorage.setItem("gupyProcessedJobs", JSON.stringify([...state.processed]));
}

function renderJobs() {
  if (!state.jobs.length) {
    results.innerHTML = '<p class="empty-state">Nenhuma vaga encontrada.</p>';
    return;
  }

  results.innerHTML = state.jobs
    .map((job) => {
      const alreadyProcessed = state.processed.has(job.url);
      return `
        <article class="job-card search-job-card">
          <div class="job-card-header">
            <div>
              <h3>${job.title}</h3>
              <p>${job.company || "Empresa não informada"}</p>
            </div>
            <span class="status-badge ${alreadyProcessed ? "done" : "pending"}">${alreadyProcessed ? "Já avaliada" : "Pendente"}</span>
          </div>
          <div class="job-card-actions">
            <a class="ghost-link" href="${job.url}" target="_blank" rel="noreferrer">Abrir vaga</a>
            <button class="evaluate-button" data-job-url="${job.url}" ${alreadyProcessed ? "disabled" : ""}>
              ${alreadyProcessed ? "Já avaliada" : "Avaliar"}
            </button>
          </div>
        </article>
      `;
    })
    .join("");
}

function updatePaginationControls() {
  pageInfo.textContent = `Página ${state.page}`;
  prevPageButton.disabled = state.page <= 1;
}

async function searchJobs(page = 1) {
  const term = termInput.value.trim() || "product owner";
  const workplaceTypes = workplaceInput.value || "remote";
  setStatus(`Buscando vagas para “${term}”...`);

  try {
    const response = await fetch("/api/search-jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ term, workplace_types: workplaceTypes, page }),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Não foi possível buscar as vagas.");
    }

    state.jobs = payload.jobs || [];
    state.term = term;
    state.page = page;
    renderJobs();
    updatePaginationControls();
    setStatus(`Encontradas ${state.jobs.length} vagas para “${term}”.`);
  } catch (error) {
    console.error(error);
    setStatus(error.message, true);
  }
}

function openEvaluator(jobUrl) {
  state.processed.add(jobUrl);
  persistProcessedJobs();
  renderJobs();

  sessionStorage.setItem("prefillJobUrl", jobUrl);
  const redirectUrl = `/?url=${encodeURIComponent(jobUrl)}`;
  const targetWindow = window.open(redirectUrl, "_blank", "noopener,noreferrer");

  if (!targetWindow) {
    setStatus("Permita pop-ups para abrir o avaliador em uma nova aba.");
    return null;
  }

  return redirectUrl;
}

async function evaluateJob(jobUrl) {
  openEvaluator(jobUrl);
  setStatus("Abrindo o avaliador para a vaga...");
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchJobs(1);
});

prevPageButton.addEventListener("click", () => {
  if (state.page > 1) {
    searchJobs(state.page - 1);
  }
});

nextPageButton.addEventListener("click", () => {
  searchJobs(state.page + 1);
});

results.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-job-url]");
  if (!button) {
    return;
  }

  const jobUrl = button.getAttribute("data-job-url");
  if (!jobUrl) {
    return;
  }

  setStatus("Abrindo o avaliador para esta vaga...");
  try {
    await evaluateJob(jobUrl);
  } catch (error) {
    setStatus(error.message, true);
  }
});

searchJobs(1);
