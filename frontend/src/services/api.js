const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";
const TOKEN_KEY = "mediscan_token";
const USER_KEY = "mediscan_user";

export function setSession(token, username) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, username);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUsername() {
  return localStorage.getItem(USER_KEY);
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function detailToMessage(detail, fallback) {
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || String(item)).join(", ");
  }
  return detail || fallback;
}

async function request(path, options = {}) {
  const headers = { ...authHeaders(), ...(options.headers || {}) };
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error("Cannot reach the API. Start the FastAPI server first.");
  }

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(detailToMessage(payload.detail, "Request failed."));
  }

  return payload;
}

function postJson(path, payload) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function registerUser(payload) {
  return postJson("/auth/register", payload);
}

export function loginUser(payload) {
  return postJson("/auth/login", payload);
}

export function fetchCurrentUser() {
  return request("/me");
}

export function scanPrescription(file) {
  const body = new FormData();
  body.append("file", file);
  return request("/scan", { method: "POST", body });
}

export function verifyPrescription(payload) {
  return postJson("/verify", payload);
}

export function fetchHistory() {
  return request("/history");
}

export function fetchResult(resultId) {
  return request(`/result/${encodeURIComponent(resultId)}`);
}

export function deleteResult(resultId) {
  return request(`/result/${encodeURIComponent(resultId)}`, { method: "DELETE" });
}

export function fetchModelInfo() {
  return request("/model-info");
}

export function fetchEvaluation() {
  return request("/evaluation");
}
