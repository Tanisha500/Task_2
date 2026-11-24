const API_ROOT = "/api";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error("Cannot reach the Flask API. Confirm that the backend is running.");
  }

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    // A non-JSON error is still surfaced below using its HTTP status.
  }
  if (!response.ok) {
    const error = new Error(payload.error || `The request failed (${response.status}).`);
    error.fields = payload.fields || {};
    error.status = response.status;
    throw error;
  }
  return payload;
}

export const api = {
  patients: () => request("/patients"),
  rejected: () => request("/assignment/rejected"),
  references: () => request("/medlineplus"),
  createPatient: (patient) => request("/patients", { method: "POST", body: JSON.stringify(patient) }),
  updatePatient: (id, patient) => request(`/patients/${id}`, { method: "PUT", body: JSON.stringify(patient) }),
  deletePatient: (id) => request(`/patients/${id}`, { method: "DELETE" }),
};
