const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

function detailToMessage(detail, fallback) {
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || String(item)).join(", ");
  }
  return detail || fallback;
}

async function request(path, options) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error("Cannot reach the API. Start the FastAPI server first.");
  }

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(detailToMessage(payload.detail, "Request failed."));
  }

  return payload;
}

export function scanPrescription(file) {
  const body = new FormData();
  body.append("file", file);
  return request("/scan", { method: "POST", body });
}

export function verifyPrescription(payload) {
  return request("/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
