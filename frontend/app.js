const form = document.getElementById('evaluate-form');
const urlInput = document.getElementById('url-input');
const resumeInput = document.getElementById('resume-input');
const resumeText = document.getElementById('resume-text');
const skillsInput = document.getElementById('skills-input');
const exclusionsInput = document.getElementById('exclusions-input');
const results = document.getElementById('results');
const statusMessage = document.getElementById('status-message');
const loading = document.getElementById('loading');
const decisionBadge = document.getElementById('decision-badge');
const fitScore = document.getElementById('fit-score');
const prosList = document.getElementById('pros-list');
const consList = document.getElementById('cons-list');
const skillsTags = document.getElementById('skills-tags');
const pitchText = document.getElementById('pitch-text');
const pitchStats = document.getElementById('pitch-stats');
const applyLink = document.getElementById('apply-link');
const copyPitch = document.getElementById('copy-pitch');
const uploadCard = document.getElementById('upload-card');
const saveSettings = document.getElementById('save-settings');

function prefillUrlFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const urlFromQuery = params.get('url') || params.get('jobUrl');
  const urlFromStorage = sessionStorage.getItem('prefillJobUrl');
  const resolvedUrl = urlFromQuery || urlFromStorage || '';

  if (resolvedUrl) {
    urlInput.value = resolvedUrl;
    sessionStorage.removeItem('prefillJobUrl');
  }
}

async function loadSettings() {
  try {
    const response = await fetch('/api/settings');
    const data = await response.json();
    skillsInput.value = (data.skills || []).join('\n');
    exclusionsInput.value = (data.exclusions || []).join('\n');
  } catch (error) {
    statusMessage.textContent = 'Não foi possível carregar as configurações salvas.';
  }
}

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle('error', isError);
  statusMessage.classList.toggle('success', !isError && message.includes('sucesso'));
}

function showLoading(message) {
  loading.classList.remove('hidden');
  setStatus(message, false);
  results.classList.add('hidden');
}

function hideLoading() {
  loading.classList.add('hidden');
}

function renderResults(data) {
  decisionBadge.textContent = data.decision || 'No-Fit';
  fitScore.textContent = data.fit_score || 0;
  prosList.innerHTML = '';
  consList.innerHTML = '';
  (data.pros || []).forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item;
    prosList.appendChild(li);
  });
  (data.cons || []).forEach((item) => {
    const li = document.createElement('li');
    li.textContent = item;
    consList.appendChild(li);
  });

  skillsTags.innerHTML = '';
  (data.recommended_skills || []).forEach((item) => {
    const span = document.createElement('span');
    span.className = 'tag';
    span.textContent = item;
    skillsTags.appendChild(span);
  });

  pitchText.textContent = data.pitch || '';
  pitchStats.textContent = `${(data.pitch || '').length} caracteres · ${(data.pitch || '').split(/\s+/).filter(Boolean).length} palavras`;
  applyLink.href = data.job?.apply_url || '#';
  applyLink.textContent = data.job?.apply_url ? 'Candidatar-se' : 'Link indisponível';
  results.classList.remove('hidden');
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const payload = new FormData();
  payload.append('url', urlInput.value);
  if (resumeInput.files[0]) {
    payload.append('resume', resumeInput.files[0]);
  }
  if (resumeText.value) {
    payload.append('resume_text', resumeText.value);
  }
  payload.append('skills', JSON.stringify(skillsInput.value.split('\n').map((item) => item.trim()).filter(Boolean)));
  payload.append('exclusions', JSON.stringify(exclusionsInput.value.split('\n').map((item) => item.trim()).filter(Boolean)));

  showLoading('Analisando a vaga e o currículo…');

  try {
    const response = await fetch('/api/evaluate', {
      method: 'POST',
      body: payload,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Erro ao avaliar a vaga');
    }
    renderResults(data);
    statusMessage.textContent = 'Análise concluída com sucesso.';
  } catch (error) {
    setStatus(error.message || 'Falha inesperada na análise.', true);
    results.classList.add('hidden');
  } finally {
    hideLoading();
  }
});

saveSettings.addEventListener('click', async () => {
  try {
    const response = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        skills: skillsInput.value.split('\n').map((item) => item.trim()).filter(Boolean),
        exclusions: exclusionsInput.value.split('\n').map((item) => item.trim()).filter(Boolean),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Falha ao salvar');
    }
    setStatus('Configurações salvas com sucesso.', false);
  } catch (error) {
    setStatus(error.message || 'Falha ao salvar as configurações.', true);
  }
});

copyPitch.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(pitchText.textContent || '');
    copyPitch.textContent = 'Copiado!';
    window.setTimeout(() => {
      copyPitch.textContent = 'Copiar';
    }, 1200);
  } catch (error) {
    setStatus('Não foi possível copiar o pitch.', true);
  }
});

['dragenter', 'dragover'].forEach((eventName) => {
  uploadCard.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadCard.style.borderColor = 'rgba(86, 204, 242, 0.7)';
  });
});

['dragleave', 'drop'].forEach((eventName) => {
  uploadCard.addEventListener(eventName, (event) => {
    event.preventDefault();
    uploadCard.style.borderColor = 'rgba(86, 204, 242, 0.4)';
  });
});

uploadCard.addEventListener('drop', (event) => {
  const [file] = event.dataTransfer.files || [];
  if (file) {
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    resumeInput.files = dataTransfer.files;
    setStatus(`Arquivo selecionado: ${file.name}`, false);
  }
});

uploadCard.addEventListener('click', () => resumeInput.click());
resumeInput.addEventListener('change', () => {
  if (resumeInput.files[0]) {
    setStatus(`Arquivo selecionado: ${resumeInput.files[0].name}`, false);
  }
});

window.addEventListener('DOMContentLoaded', () => {
  prefillUrlFromQuery();
  loadSettings();
});
