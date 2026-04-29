const accessForm = document.getElementById("clientAccessForm");
const accessPanel = document.getElementById("clientAccessPanel");
const onboardingPanel = document.getElementById("clientOnboardingPanel");
const onboardingForm = document.getElementById("clientOnboardingForm");
const onboardingChecklist = document.getElementById("clientOnboardingChecklist");
const onboardingSubmitBtn = document.getElementById("onboardingSubmitBtn");
const workspacePanel = document.getElementById("clientWorkspacePanel");
const progressPanel = document.getElementById("clientProgressPanel");
const cnpjInput = document.getElementById("cnpjInput");
const cnpjHidden = document.getElementById("cnpjHidden");
const clientCnpjLabel = document.getElementById("clientCnpjLabel");
const changeCnpjBtn = document.getElementById("changeCnpjBtn");
const accessSubmitBtn = document.getElementById("accessSubmitBtn");
const progressTitle = document.getElementById("clientProgressTitle");
const progressChip = document.getElementById("clientProgressChip");
const progressSummary = document.getElementById("clientProgressSummary");
const selectedTestSummary = document.getElementById("clientSelectedTestSummary");
const progressTableBody = document.getElementById("clientProgressTableBody");
const form = document.getElementById("clientValidateForm");
const testSelect = document.getElementById("testSelect");
const clientGoalBox = document.getElementById("clientGoalBox");
const submitBtn = document.getElementById("submitBtn");

const resultPanel = document.getElementById("clientResultPanel");
const overallStatus = document.getElementById("clientOverallStatus");
const statusChip = document.getElementById("clientStatusChip");
const protocol = document.getElementById("clientProtocol");
const deniedLeg = document.getElementById("clientDeniedLeg");
const deniedReason = document.getElementById("clientDeniedReason");
const i18n = window.I18N || { t: (key) => key };
const t = (key, vars) => i18n.t(key, vars);

const CNPJ_STORAGE_KEY = "homolog_client_cnpj";
let testsCache = [];
let assignedTestIds = [];

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(msg) {
  let toast = document.getElementById("appToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "appToast";
    toast.className = "app-toast";
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add("visible");
  setTimeout(() => toast.classList.remove("visible"), 4000);
}

function formatStatusLabel(status) {
  const raw = String(status || "").toUpperCase().replace(/_/g, " ");
  if (raw === "APROVADO") return String(t("status.approved")).toUpperCase();
  if (raw === "REPROVADO") return String(t("status.reproved")).toUpperCase();
  if (raw === "NAO APLICA" || raw === "NÃO APLICA") return String(t("status.na")).toUpperCase();
  if (raw === "NAO INICIADO" || raw === "NÃO INICIADO") return String(t("status.notStarted")).toUpperCase();
  if (raw === "EM ANDAMENTO") return String(t("status.inProgress")).toUpperCase();
  return raw || "-";
}

function formatStatusWithIcon(status) {
  const raw = String(status || "").toUpperCase();
  const label = formatStatusLabel(status);
  if (raw === "APROVADO") {
    return `<span class="status-icon-ok" title="${escapeHtml(t("status.approved"))}">&#10003;</span> ${escapeHtml(label)}`;
  }
  return escapeHtml(label);
}

function normalizeCnpj(value) {
  return String(value || "").trim();
}

function formatCnpj(value) {
  return normalizeCnpj(value);
}

function localizedTestName(testId, fallbackName) {
  if (i18n.translateTestName) {
    return i18n.translateTestName(testId, fallbackName);
  }
  return String(fallbackName || "");
}

function setWorkspaceCnpj(cnpj) {
  const normalized = normalizeCnpj(cnpj);
  cnpjHidden.value = normalized;
  clientCnpjLabel.textContent = formatCnpj(normalized);
  cnpjInput.value = formatCnpj(normalized);
  sessionStorage.setItem(CNPJ_STORAGE_KEY, normalized);
}

function clearWorkspaceCnpj() {
  sessionStorage.removeItem(CNPJ_STORAGE_KEY);
  cnpjHidden.value = "";
  cnpjInput.value = "";
  clientCnpjLabel.textContent = "-";
  assignedTestIds = [];
  accessPanel.classList.remove("hidden");
  onboardingPanel.classList.add("hidden");
  workspacePanel.classList.add("hidden");
  progressPanel.classList.add("hidden");
  resultPanel.classList.add("hidden");
}

function renderAllowedTestsSelect() {
  const allowedTests = testsCache.filter((item) => assignedTestIds.includes(String(item.id || "").padStart(2, "0")));

  const options = [`<option value="">${escapeHtml(t("common.select"))}</option>`];
  for (const testItem of allowedTests) {
    const testName = localizedTestName(testItem.id, testItem.nome || "");
    options.push(`<option value="${escapeHtml(testItem.id)}">${escapeHtml(testItem.id)} - ${escapeHtml(testName)}</option>`);
  }
  testSelect.innerHTML = options.join("");

  if (clientGoalBox) {
    clientGoalBox.textContent = t("client.goalDefault");
  }
}

function updateClientGoalBySelectedTest() {
  if (!clientGoalBox) {
    return;
  }

  const selectedId = String(testSelect.value || "").padStart(2, "0");
  if (!selectedId) {
    clientGoalBox.textContent = t("client.goalDefault");
    return;
  }

  const selectedTest = testsCache.find((item) => String(item.id || "").padStart(2, "0") === selectedId);
  clientGoalBox.textContent = selectedTest
    ? String(selectedTest.objetivo_esperado || t("client.goalMissing"))
    : t("client.goalNotFound");
}

function renderOnboardingChecklist() {
  onboardingChecklist.innerHTML = testsCache
    .map((item) => {
      const testName = localizedTestName(item.id, item.nome || "");
      return `
      <label class="step" style="display: flex; align-items: center; gap: 10px;">
        <input type="checkbox" name="selected_tests" value="${escapeHtml(item.id)}" />
        <span><strong>${escapeHtml(item.id)} - ${escapeHtml(testName)}</strong><br>${escapeHtml(item.objetivo_esperado || "")}</span>
      </label>
    `;
    })
    .join("");
}

async function loadTests() {
  const resp = await fetch("/api/tests");
  const data = await resp.json();
  const tests = data.tests || [];
  testsCache = tests;

  renderOnboardingChecklist();
  renderAllowedTestsSelect();
}

function applyClientProgressState(data, selectedTest) {
  assignedTestIds = Array.isArray(data.assigned_tests)
    ? data.assigned_tests.map((item) => String(item.id || "").padStart(2, "0"))
    : [];

  if (data.onboarding_required) {
    onboardingPanel.classList.remove("hidden");
    workspacePanel.classList.add("hidden");
    progressPanel.classList.add("hidden");
    resultPanel.classList.add("hidden");
    return;
  }

  onboardingPanel.classList.add("hidden");
  workspacePanel.classList.remove("hidden");
  renderAllowedTestsSelect();
  renderProgress(data, selectedTest);
}

function renderProgress(data, selectedTest) {
  const summary = data.summary || {};
  const tests = Array.isArray(data.tests) ? data.tests : [];
  const overallPercent = Number(summary.percentual_aprovacao_geral || 0);

  progressPanel.classList.remove("hidden");
  progressTitle.textContent = t("client.progressTitleText", {
    approved: summary.testes_aprovados || 0,
    planned: summary.total_testes_planejados || 0,
  });
  progressChip.textContent = `${overallPercent.toFixed(2)}%`;
  progressSummary.textContent = t("client.progressSummaryText", {
    started: summary.testes_iniciados || 0,
    approved: summary.testes_aprovados || 0,
    planned: summary.total_testes_planejados || 0,
  });

  if (selectedTest) {
    const selectedName = localizedTestName(selectedTest.teste_id, selectedTest.teste_nome || "Teste");
    selectedTestSummary.textContent = t("client.selectedTestLine", {
      id: selectedTest.teste_id,
      name: selectedName,
      attempts: selectedTest.attempts_total,
      success: Number(selectedTest.percentual_sucesso || 0).toFixed(2),
    });
  } else {
    selectedTestSummary.textContent = t("client.noRecentTest");
  }

  if (tests.length === 0) {
    progressTableBody.innerHTML = `<tr><td colspan="6">${escapeHtml(t("client.noTestsForCnpj"))}</td></tr>`;
    return;
  }

  progressTableBody.innerHTML = tests
    .map((item) => {
      const testName = localizedTestName(item.teste_id, item.teste_nome || "");
      return `
      <tr>
        <td>${escapeHtml(item.teste_id)} - ${escapeHtml(testName)}</td>
        <td>${formatStatusWithIcon(item.status)}</td>
        <td>${escapeHtml(item.attempts_total)}</td>
        <td>${escapeHtml(item.attempts_until_approval ?? "-")}</td>
        <td>${escapeHtml(Number(item.percentual_sucesso || 0).toFixed(2))}%</td>
        <td>${escapeHtml(Number(item.percentual_ate_aprovacao || 0).toFixed(2))}%</td>
      </tr>
    `;
    })
    .join("");
}

async function loadClientProgress(cnpj, selectedTest) {
  const normalized = normalizeCnpj(cnpj);
  const resp = await fetch(`/api/client/progress?cnpj=${encodeURIComponent(normalized)}`);
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.error || t("client.errorLoadProgress"));
  }
  applyClientProgressState(data, selectedTest);
}

function renderResult(data) {
  const resultado = String(data.resultado || "").toUpperCase();
  const isApproved = resultado === "APROVADO";

  resultPanel.classList.remove("hidden");

  overallStatus.textContent = isApproved ? t("client.resultApproved") : t("client.resultDenied");
  statusChip.textContent = isApproved ? t("client.resultApproved") : t("client.resultDenied");
  statusChip.style.background = isApproved ? "#d5f1e5" : "#f6dada";
  statusChip.style.color = isApproved ? "#0f6e4f" : "#9e2424";

  protocol.textContent = data.protocolo || "-";

  if (isApproved) {
    deniedLeg.textContent = "-";
    deniedReason.textContent = t("client.approvedHint");
  } else {
    deniedLeg.textContent = data.perna_negada || t("client.deniedLegUnknown");
    deniedReason.textContent = data.motivo_negacao || t("client.deniedReasonUnknown");
  }

  if (data.progresso) {
    renderProgress(
      {
        summary: data.progresso.summary,
        tests: data.progresso.all_tests,
      },
      data.progresso.selected_test,
    );
  }

  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

cnpjInput.addEventListener("input", () => {
  cnpjInput.value = formatCnpj(cnpjInput.value);
});

accessForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  const normalized = normalizeCnpj(cnpjInput.value);
  if (!normalized) {
    showToast(t("client.errorEnterCnpj"));
    return;
  }

  accessSubmitBtn.disabled = true;
  accessSubmitBtn.classList.add("loading");
  accessSubmitBtn.textContent = t("client.accessing");

  try {
    setWorkspaceCnpj(normalized);
    accessPanel.classList.add("hidden");
    await loadClientProgress(normalized);
  } catch (err) {
    clearWorkspaceCnpj();
    const msg = err instanceof Error && err.message
      ? err.message
      : t("client.errorCannotLoadCnpj");
    showToast(msg);
  } finally {
    accessSubmitBtn.disabled = false;
    accessSubmitBtn.classList.remove("loading");
    accessSubmitBtn.textContent = t("client.access");
  }
});

changeCnpjBtn.addEventListener("click", () => {
  clearWorkspaceCnpj();
});

onboardingForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  if (!cnpjHidden.value) {
    showToast(t("client.errorCnpjBeforeSelect"));
    return;
  }

  const selectedTests = Array.from(onboardingChecklist.querySelectorAll('input[name="selected_tests"]:checked'))
    .map((item) => item.value);

  if (selectedTests.length === 0) {
    showToast(t("client.errorSelectAtLeastOne"));
    return;
  }

  onboardingSubmitBtn.disabled = true;
  onboardingSubmitBtn.classList.add("loading");
  onboardingSubmitBtn.textContent = t("client.saving");

  try {
    const formData = new FormData();
    formData.append("cnpj", cnpjHidden.value);
    selectedTests.forEach((item) => formData.append("selected_tests", item));

    const resp = await fetch("/api/client/enroll", {
      method: "POST",
      body: formData,
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || t("client.errorSaveTests"));
    }

    applyClientProgressState(data);
  } catch (err) {
    const msg = err instanceof Error && err.message
      ? err.message
      : t("client.errorCannotSaveTests");
    showToast(msg);
  } finally {
    onboardingSubmitBtn.disabled = false;
    onboardingSubmitBtn.classList.remove("loading");
    onboardingSubmitBtn.textContent = t("client.saveTests");
  }
});

testSelect.addEventListener("change", () => {
  updateClientGoalBySelectedTest();
});

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  if (!cnpjHidden.value) {
    showToast(t("client.errorCnpjBeforeValidate"));
    return;
  }

  submitBtn.disabled = true;
  submitBtn.classList.add("loading");
  submitBtn.textContent = t("client.processing");

  try {
    const formData = new FormData(form);
    const resp = await fetch("/api/client/validate", {
      method: "POST",
      body: formData,
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || t("client.errorValidate"));
    }

    renderResult(data);
  } catch (err) {
    const msg = err instanceof Error && err.message
      ? err.message
      : t("client.errorCannotValidate");
    showToast(msg);
  } finally {
    submitBtn.disabled = false;
    submitBtn.classList.remove("loading");
    submitBtn.textContent = t("client.sendValidation");
  }
});

loadTests().catch(() => {
  testSelect.innerHTML = `<option value="">${escapeHtml(t("validator.failTests"))}</option>`;
});

const savedCnpj = normalizeCnpj(sessionStorage.getItem(CNPJ_STORAGE_KEY) || "");
if (savedCnpj) {
  setWorkspaceCnpj(savedCnpj);
  accessPanel.classList.add("hidden");
  loadClientProgress(savedCnpj).catch(() => {
    clearWorkspaceCnpj();
  });
}

window.addEventListener("app-language-changed", () => {
  renderAllowedTestsSelect();
  updateClientGoalBySelectedTest();
  accessSubmitBtn.textContent = t("client.access");
  onboardingSubmitBtn.textContent = t("client.saveTests");
  submitBtn.textContent = t("client.sendValidation");
});
