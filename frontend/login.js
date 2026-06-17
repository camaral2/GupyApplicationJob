const authStatus = document.getElementById("auth-status");
const loginForm = document.getElementById("login-form");
const emailInput = document.getElementById("email-input");
const passwordInput = document.getElementById("password-input");
const registerButton = document.getElementById("register-button");

function setStatus(message, isError = false) {
  authStatus.textContent = message;
  authStatus.classList.toggle("error", isError);
  authStatus.classList.toggle("success", !isError && message.includes("sucesso"));
}

async function login(email, password) {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Falha no login.");
  }
  setAuthSession(payload.token, payload.email || email);
}

async function register(email, password) {
  const response = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Falha no cadastro.");
  }
  return payload;
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = emailInput.value.trim().toLowerCase();
  const password = passwordInput.value;
  setStatus("Validando acesso...");
  try {
    await login(email, password);
    setStatus("Login realizado com sucesso.");
    window.location.href = "/search";
  } catch (error) {
    setStatus(error.message, true);
  }
});

registerButton.addEventListener("click", async () => {
  const email = emailInput.value.trim().toLowerCase();
  const password = passwordInput.value;
  if (!email || !password) {
    setStatus("Preencha email e senha para cadastrar.", true);
    return;
  }
  setStatus("Criando conta...");
  try {
    await register(email, password);
    await login(email, password);
    setStatus("Conta criada com sucesso.");
    window.location.href = "/search";
  } catch (error) {
    setStatus(error.message, true);
  }
});

window.addEventListener("DOMContentLoaded", async () => {
  if (!getAuthToken()) {
    return;
  }
  try {
    const response = await authFetch("/api/auth/me");
    if (response.ok) {
      window.location.href = "/search";
    }
  } catch (error) {
    clearAuthSession();
  }
});
