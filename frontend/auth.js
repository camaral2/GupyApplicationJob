const AUTH_TOKEN_KEY = "gupyAuthToken";
const AUTH_EMAIL_KEY = "gupyAuthEmail";

function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

function getAuthEmail() {
  return localStorage.getItem(AUTH_EMAIL_KEY) || "";
}

function setAuthSession(token, email) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_EMAIL_KEY, (email || "").toLowerCase());
}

function clearAuthSession() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_EMAIL_KEY);
}

async function authFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getAuthToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    clearAuthSession();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }
  return response;
}

function ensureAuthenticated() {
  const token = getAuthToken();
  if (!token) {
    window.location.href = "/login";
    return false;
  }
  return true;
}

function mountAuthHeader() {
  const emailNode = document.getElementById("auth-email");
  const logoutNode = document.getElementById("logout-button");
  if (emailNode) {
    emailNode.textContent = getAuthEmail() || "Usuário";
  }
  if (logoutNode) {
    logoutNode.addEventListener("click", async () => {
      try {
        await authFetch("/api/auth/logout", { method: "POST" });
      } catch (error) {
        console.error(error);
      } finally {
        clearAuthSession();
        window.location.href = "/login";
      }
    });
  }
}
