const US_STATES = new Set(["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"]);
const NAME_PATTERN = /^[A-Za-z]+(?:[ '-][A-Za-z]+)*$/;
const tableBody = document.querySelector("#patient-table-body");
const tableMessage = document.querySelector("#table-message");
const count = document.querySelector("#patient-count");
const updated = document.querySelector("#last-updated");
const connection = document.querySelector("#connection-status");
const dialog = document.querySelector("#patient-dialog");
const dialogTitle = document.querySelector("#dialog-title");
const details = document.querySelector("#patient-details");
const deleteButton = document.querySelector("#delete-patient-button");
const formDialog = document.querySelector("#patient-form-dialog");
const form = document.querySelector("#patient-form");
const formError = document.querySelector("#form-error");
const filters = {
  last_name: document.querySelector("#last-name-filter"),
  date_of_birth: document.querySelector("#dob-filter"),
  phone_number: document.querySelector("#phone-filter")
};
let patients = [];
let allPatients = [];
function text(value) { return value?.trim() || "Not provided"; }
function escapeHtml(value) { return value.replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" })[character]); }
function formatPhone(value) { return value.length === 10 ? `(${value.slice(0, 3)}) ${value.slice(3, 6)}-${value.slice(6)}` : value; }
function formatDate(value) { const [year, month, day] = value.slice(0, 10).split("-"); return year && month && day ? `${month}/${day}/${year}` : value; }
function formatTimestamp(value) { return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
function setMessage(message) { tableMessage.textContent = message || ""; tableMessage.dataset.visible = String(Boolean(message)); }
function setConnection(label, state) { connection.textContent = label; connection.dataset.state = state; }
function setFormError(message) { formError.textContent = message || ""; formError.dataset.visible = String(Boolean(message)); }
function formControl(name) { return form.elements.namedItem(name); }
function validatePatientForm(payload) {
  const errors = [];
  Array.from(form.elements).forEach((element) => { if (element instanceof HTMLInputElement || element instanceof HTMLSelectElement) element.setCustomValidity(""); });
  const addError = (field, message) => { formControl(field).setCustomValidity(message); errors.push({ field, message }); };
  const trimmed = (field) => payload[field].trim();
  const validateName = (field) => { const value = trimmed(field); if (!NAME_PATTERN.test(value) || value.length > 50) addError(field, "Use 1-50 letters, spaces, hyphens, or apostrophes."); };
  validateName("first_name"); validateName("last_name");
  const dob = trimmed("date_of_birth");
  const dateParts = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(dob);
  if (!dateParts) { addError("date_of_birth", "Use a valid past date in MM/DD/YYYY format.");
  } else {
    const [, month, day, year] = dateParts;
    const parsed = new Date(Number(year), Number(month) - 1, Number(day));
    const today = new Date(); today.setHours(0, 0, 0, 0);
    if (parsed.getFullYear() !== Number(year) || parsed.getMonth() !== Number(month) - 1 || parsed.getDate() !== Number(day) || parsed > today) addError("date_of_birth", "Use a valid past date in MM/DD/YYYY format.");
  }
  const validatePhone = (field, required) => {
    const digits = payload[field].replace(/\D/g, "").replace(/^1(?=\d{10}$)/, "");
    if ((!required && !digits) || (digits.length === 10 && !"01".includes(digits[0]) && !"01".includes(digits[3]))) return;
    addError(field, "Enter a valid 10-digit U.S. phone number.");
  };
  validatePhone("phone_number", true); validatePhone("emergency_contact_phone", false);
  payload.state = trimmed("state").toUpperCase();
  if (!US_STATES.has(payload.state)) addError("state", "Enter a valid two-letter U.S. state abbreviation.");
  if (!/^\d{5}(?:-\d{4})?$/.test(trimmed("zip_code"))) addError("zip_code", "Enter a 5-digit ZIP code or ZIP+4.");
  if (trimmed("insurance_member_id") && !/^[A-Za-z0-9-]+$/.test(trimmed("insurance_member_id"))) addError("insurance_member_id", "Member ID may contain letters, numbers, and hyphens only.");
  if (trimmed("preferred_language").length > 100) addError("preferred_language", "Preferred language must be at most 100 characters.");
  if (trimmed("emergency_contact_name") && !NAME_PATTERN.test(trimmed("emergency_contact_name"))) addError("emergency_contact_name", "Enter a full name using letters, spaces, hyphens, or apostrophes.");
  if (!errors.length) return true;
  setFormError(errors[0].message); formControl(errors[0].field).focus(); form.reportValidity(); return false;
}
async function request(url, options) {
  const response = await fetch(url, { ...options, headers: { Accept: "application/json", ...options?.headers } });
  const result = await response.json();
  if (!response.ok || result.error) {
    const detail = result.error?.details?.[0];
    const field = detail?.loc.at(-1)?.replaceAll("_", " ");
    throw new Error(detail ? `${field}: ${detail.msg.replace(/^Value error, /, "")}` : (result.error?.message || "Request failed."));
  }
  return result.data;
}
function renderRows(records) {
  tableBody.replaceChildren();
  records.forEach((patient) => {
    const row = document.createElement("tr");
    row.innerHTML = `<td><span class="patient-name">${escapeHtml(patient.first_name)} ${escapeHtml(patient.last_name)}<span class="patient-email">${escapeHtml(text(patient.email))}</span></span></td><td>${escapeHtml(formatDate(patient.date_of_birth))}</td><td>${escapeHtml(formatPhone(patient.phone_number))}</td><td>${escapeHtml(patient.city)}, ${escapeHtml(patient.state)}</td><td class="muted">${escapeHtml(formatTimestamp(patient.created_at))}</td><td><button class="view-button" type="button" data-patient-id="${patient.patient_id}">View</button></td>`;
    tableBody.append(row);
  });
}
function applyFilters() {
  const lastName = filters.last_name.value.trim().toLocaleLowerCase();
  const dateOfBirth = filters.date_of_birth.value.trim();
  const phoneNumber = filters.phone_number.value.replace(/\D/g, "");
  patients = allPatients.filter((patient) => (!lastName || patient.last_name.toLocaleLowerCase().includes(lastName)) && (!dateOfBirth || formatDate(patient.date_of_birth).includes(dateOfBirth)) && (!phoneNumber || patient.phone_number.includes(phoneNumber)));
  renderRows(patients);
  count.textContent = `${patients.length} patient${patients.length === 1 ? "" : "s"}`;
  setMessage(patients.length ? null : "No active patient records match these filters.");
}
function openPatient(patientId) {
  const patient = patients.find((record) => record.patient_id === patientId);
  if (!patient) return;
  dialogTitle.textContent = `${patient.first_name} ${patient.last_name}`;
  deleteButton.dataset.patientId = patient.patient_id;
  const fields = [["Patient ID", patient.patient_id], ["Date of birth", formatDate(patient.date_of_birth)], ["Sex", patient.sex], ["Phone", formatPhone(patient.phone_number)], ["Email", text(patient.email)], ["Address", [patient.address_line_1, patient.address_line_2, `${patient.city}, ${patient.state} ${patient.zip_code}`].filter(Boolean).join(", ")], ["Preferred language", patient.preferred_language], ["Insurance provider", text(patient.insurance_provider)], ["Member ID", text(patient.insurance_member_id)], ["Emergency contact", text(patient.emergency_contact_name)], ["Emergency phone", patient.emergency_contact_phone ? formatPhone(patient.emergency_contact_phone) : "Not provided"], ["Registered", formatTimestamp(patient.created_at)]];
  details.replaceChildren(...fields.map(([label, value]) => { const item = document.createElement("div"); const term = document.createElement("dt"); const description = document.createElement("dd"); term.textContent = label; description.textContent = value; item.append(term, description); return item; }));
  dialog.showModal();
}
async function loadPatients() {
  setMessage("Loading patient records..."); setConnection("Loading", "loading");
  try {
    allPatients = await request("/patients"); applyFilters();
    updated.textContent = `Updated ${new Intl.DateTimeFormat("en-US", { timeStyle: "short" }).format(new Date())}`;
    setConnection("Connected", "ready");
  } catch (error) {
    patients = []; allPatients = []; renderRows([]); count.textContent = "Patients"; setMessage(error instanceof Error ? error.message : "Unable to load patient records."); setConnection("Connection error", "error");
  }
}
document.querySelector("#refresh-button").addEventListener("click", () => void loadPatients());
document.querySelector("#add-patient-button").addEventListener("click", () => { form.reset(); setFormError(null); formDialog.showModal(); form.elements.namedItem("first_name").focus(); });
document.querySelector("#clear-filters").addEventListener("click", () => { Object.values(filters).forEach((input) => { input.value = ""; }); applyFilters(); });
Object.values(filters).forEach((input) => input.addEventListener("input", applyFilters));
tableBody.addEventListener("click", (event) => { const button = event.target.closest("[data-patient-id]"); if (button) openPatient(button.dataset.patientId); });
document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
document.querySelector("#close-form-dialog").addEventListener("click", () => formDialog.close());
document.querySelector("#cancel-form").addEventListener("click", () => formDialog.close());
dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
formDialog.addEventListener("click", (event) => { if (event.target === formDialog) formDialog.close(); });
form.addEventListener("submit", async (event) => {
  event.preventDefault(); setFormError(null);
  const submitButton = form.querySelector("[type=submit]");
  submitButton.disabled = true;
  try {
    const payload = Object.fromEntries(new FormData(form).entries());
    if (!validatePatientForm(payload)) return;
    await request("/patients", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    formDialog.close(); await loadPatients();
  } catch (error) { setFormError(error instanceof Error ? error.message : "Unable to save this patient.");
  } finally { submitButton.disabled = false; }
});
deleteButton.addEventListener("click", async () => {
  const patient = patients.find((record) => record.patient_id === deleteButton.dataset.patientId);
  if (!patient || !window.confirm(`Delete the record for ${patient.first_name} ${patient.last_name}? This cannot be undone from the dashboard.`)) return;
  deleteButton.disabled = true;
  try { await request(`/patients/${patient.patient_id}`, { method: "DELETE" }); dialog.close(); await loadPatients();
  } catch (error) { window.alert(error instanceof Error ? error.message : "Unable to delete this patient.");
  } finally { deleteButton.disabled = false; }
});
void loadPatients();
