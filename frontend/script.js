// The frontend is served by FastAPI, so same-origin requests need no CORS setup.
// For a separate development server, change this to the API origin, e.g. http://127.0.0.1:8000.
const API_BASE_URL = window.BULK_CERT_API_BASE_URL || window.location.origin;
const API_PREFIX = "/api/v1";
const MAX_RECIPIENTS = 500;
const POLL_INTERVAL_MS = 1200;
const TERMINAL_STATES = new Set(["completed", "completed_with_errors", "failed"]);

const form = document.querySelector("#job-form");
const recipientList = document.querySelector("#recipient-list");
const addRecipientButton = document.querySelector("#add-recipient");
const submitButton = document.querySelector("#submit-job");
const formError = document.querySelector("#form-error");
const jobPanel = document.querySelector("#job-panel");
const jobMessage = document.querySelector("#job-message");
let activeJobId = null;
let isBusy = false;

function createRecipientRow(name = "", email = "") {
  const row = document.createElement("div");
  row.className = "recipient-row";

  const nameInput = document.createElement("input");
  nameInput.name = "recipient_name";
  nameInput.type = "text";
  nameInput.maxLength = 200;
  nameInput.autocomplete = "name";
  nameInput.placeholder = "Full name";
  nameInput.setAttribute("aria-label", "Recipient full name");
  nameInput.value = name;

  const emailInput = document.createElement("input");
  emailInput.name = "recipient_email";
  emailInput.type = "email";
  emailInput.maxLength = 320;
  emailInput.autocomplete = "email";
  emailInput.placeholder = "name@example.com";
  emailInput.setAttribute("aria-label", "Recipient email address (optional)");
  emailInput.value = email;

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "button remove-button";
  removeButton.textContent = "×";
  removeButton.setAttribute("aria-label", "Remove recipient");
  removeButton.addEventListener("click", () => {
    if (recipientList.children.length > 1) row.remove();
    else {
      nameInput.value = "";
      emailInput.value = "";
      nameInput.focus();
    }
    updateAddButton();
  });

  row.append(nameInput, emailInput, removeButton);
  recipientList.append(row);
  updateAddButton();
  return nameInput;
}

function updateAddButton() {
  const count = recipientList.children.length;
  addRecipientButton.disabled = isBusy || count >= MAX_RECIPIENTS;
  addRecipientButton.title = count >= MAX_RECIPIENTS ? "The maximum batch size is 500 recipients" : "Add a recipient";
}

function setBusy(busy) {
  isBusy = busy;
  submitButton.disabled = busy;
  submitButton.querySelector("span:first-child").textContent = busy ? "Generating…" : "Generate certificates";
  form.querySelectorAll("input").forEach((input) => { input.disabled = busy; });
  recipientList.querySelectorAll("button").forEach((button) => { button.disabled = busy; });
  updateAddButton();
}

function showFormError(message) {
  formError.textContent = message;
  formError.hidden = false;
  formError.scrollIntoView({ behavior: "smooth", block: "center" });
}

function clearFormError() {
  formError.hidden = true;
  formError.textContent = "";
}

async function readError(response) {
  let body;
  try { body = await response.json(); } catch { return `Request failed (${response.status}).`; }
  if (Array.isArray(body.detail)) {
    return body.detail.map((item) => {
      const field = Array.isArray(item.loc) ? item.loc.slice(1).join(" → ") : "Request";
      return `${field || "Request"}: ${item.msg}`;
    }).join(". ");
  }
  return body.detail || body.message || `Request failed (${response.status}).`;
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${API_PREFIX}${path}`, options);
  } catch {
    throw new Error("Could not reach the API. Check that the FastAPI server is running and try again.");
  }
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

function makePayload() {
  const recipients = [...recipientList.querySelectorAll(".recipient-row")].map((row) => {
    const name = row.querySelector('[name="recipient_name"]').value.trim();
    const email = row.querySelector('[name="recipient_email"]').value.trim();
    return email ? { name, email } : { name };
  });
  return {
    certificate_title: form.elements.certificate_title.value.trim(),
    event_name: form.elements.event_name.value.trim(),
    issuer_name: form.elements.issuer_name.value.trim(),
    issue_date: form.elements.issue_date.value,
    recipients,
  };
}

function statusLabel(status) {
  return ({ pending: "Queued", processing: "Processing", completed: "Completed", completed_with_errors: "Completed with errors", failed: "Failed" })[status] || status;
}

function updateStatus(job) {
  const finished = TERMINAL_STATES.has(job.status);
  // Per-recipient statuses update as the worker runs; job counters are finalized at completion.
  const recipients = job.recipients || [];
  const successCount = recipients.filter((recipient) => recipient.status === "success").length;
  const failedCount = recipients.filter((recipient) => recipient.status === "failed").length;
  const doneCount = successCount + failedCount;
  const percent = job.total_count ? Math.min(100, Math.round((doneCount / job.total_count) * 100)) : 0;
  const pill = document.querySelector("#job-status");
  pill.textContent = statusLabel(job.status);
  pill.className = "status-pill";
  pill.classList.add(finished ? (job.status === "completed" ? "status-completed" : "status-error") : "status-processing");
  document.querySelector("#progress-label").textContent = finished ? "Generation finished" : job.status === "pending" ? "Your job is queued" : "Creating personalized certificates";
  document.querySelector("#progress-value").textContent = `${percent}%`;
  document.querySelector(".progress-track").setAttribute("aria-valuenow", String(percent));
  document.querySelector("#progress-fill").style.width = `${percent}%`;
  document.querySelector("#total-count").textContent = job.total_count;
  document.querySelector("#success-count").textContent = successCount;
  document.querySelector("#failed-count").textContent = failedCount;
  renderRecipients(recipients, job.job_id);

  const zipLink = document.querySelector("#zip-download");
  if (finished && successCount > 0) {
    zipLink.href = `${API_BASE_URL}${API_PREFIX}/jobs/${encodeURIComponent(job.job_id)}/certificates`;
    zipLink.hidden = false;
  } else zipLink.hidden = true;

  if (finished) {
    if (job.status === "completed") showJobMessage("All certificates were generated successfully.", "success");
    else if (job.status === "completed_with_errors") showJobMessage("The batch finished. Some recipients need attention; successful certificates are ready to download.", "error");
    else showJobMessage("No certificates were generated successfully. Check the recipient results and try again.", "error");
  }
}

function showJobMessage(message, type) {
  jobMessage.textContent = message;
  jobMessage.className = `notice${type === "error" ? " notice-error" : ""}`;
  jobMessage.hidden = false;
}

function renderRecipients(recipients, jobId) {
  const body = document.querySelector("#results-body");
  body.replaceChildren();
  recipients.forEach((recipient) => {
    const row = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = recipient.name || "Unnamed recipient";
    const statusCell = document.createElement("td");
    const status = document.createElement("span");
    status.className = `result-status ${recipient.status === "success" ? "success" : recipient.status === "failed" ? "failed" : "processing"}`;
    status.textContent = recipient.status === "success" ? "Successful" : recipient.status === "failed" ? "Failed" : statusLabel(recipient.status);
    statusCell.append(status);
    const details = document.createElement("td");
    if (recipient.error_message) {
      details.className = "result-error";
      details.textContent = recipient.error_message;
    } else details.textContent = recipient.email || "—";
    const download = document.createElement("td");
    if (recipient.status === "success") {
      const link = document.createElement("a");
      link.className = "download-link";
      link.href = `${API_BASE_URL}${API_PREFIX}/jobs/${encodeURIComponent(jobId)}/certificates/${encodeURIComponent(recipient.id)}`;
      link.textContent = "↓ PDF";
      link.setAttribute("aria-label", `Download certificate for ${recipient.name}`);
      download.append(link);
    } else download.textContent = "—";
    row.append(name, statusCell, details, download);
    body.append(row);
  });
}

const sleep = (milliseconds) => new Promise((resolve) => window.setTimeout(resolve, milliseconds));

async function pollJob(jobId) {
  const started = Date.now();
  while (Date.now() - started < 10 * 60 * 1000) {
    const job = await requestJson(`/jobs/${encodeURIComponent(jobId)}`);
    updateStatus(job);
    if (TERMINAL_STATES.has(job.status)) return;
    await sleep(POLL_INTERVAL_MS);
  }
  throw new Error("This job is taking longer than expected. Its progress is still saved; refresh the page and check the job in the API docs.");
}

addRecipientButton.addEventListener("click", () => {
  if (recipientList.children.length < MAX_RECIPIENTS) createRecipientRow().focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isBusy) return;
  activeJobId = null;
  clearFormError();
  form.querySelectorAll("input").forEach((input) => input.removeAttribute("aria-invalid"));

  const requiredFields = ["certificate_title", "event_name", "issuer_name", "issue_date"];
  const missing = requiredFields.map((name) => form.elements[name]).find((input) => !input.value.trim());
  if (missing) {
    missing.setAttribute("aria-invalid", "true");
    showFormError(`Please complete the ${missing.labels[0].textContent.trim().toLowerCase()} field.`);
    missing.focus();
    return;
  }
  const payload = makePayload();
  if (payload.recipients.length < 1 || payload.recipients.length > MAX_RECIPIENTS) {
    showFormError(`Add between 1 and ${MAX_RECIPIENTS} recipients.`);
    return;
  }

  setBusy(true);
  jobMessage.hidden = true;
  document.querySelector("#results-body").replaceChildren();
  document.querySelector("#zip-download").hidden = true;
  try {
    const accepted = await requestJson("/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    activeJobId = accepted.job_id;
    document.querySelector("#job-id").textContent = accepted.job_id;
    jobPanel.hidden = false;
    document.querySelector("#job-id-label").setAttribute("aria-label", `Job ID ${accepted.job_id}`);
    document.querySelector("#job-status").textContent = statusLabel(accepted.status);
    document.querySelector("#total-count").textContent = payload.recipients.length;
    document.querySelector("#success-count").textContent = "0";
    document.querySelector("#failed-count").textContent = "0";
    document.querySelector("#progress-value").textContent = "0%";
    document.querySelector("#progress-fill").style.width = "0%";
    document.querySelector(".progress-track").setAttribute("aria-valuenow", "0");
    jobPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    await pollJob(activeJobId);
  } catch (error) {
    if (activeJobId) showJobMessage(error.message, "error");
    else showFormError(error.message);
  } finally {
    setBusy(false);
  }
});

createRecipientRow();
document.querySelector("#issue-date").value = new Date().toISOString().slice(0, 10);
