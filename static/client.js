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
const submitBtn = document.getElementById("submitBtn");

const resultPanel = document.getElementById("clientResultPanel");
const overallStatus = document.getElementById("clientOverallStatus");
const statusChip = document.getElementById("clientStatusChip");
const protocol = document.getElementById("clientProtocol");
const deniedLeg = document.getElementById("clientDeniedLeg");
const deniedReason = document.getElementById("clientDeniedReason");

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

function normalizeCnpj(value) {
  return String(value || "").trim();
}

function formatCnpj(value) {
  return normalizeCnpj(value);
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

  const options = ['<option value="">Selecione...</option>'];
  for (const t of allowedTests) {
    options.push(`<option value="${escapeHtml(t.id)}">${escapeHtml(t.id)} - ${escapeHtml(t.nome || "")}</option>`);
  }
  testSelect.innerHTML = options.join("");
}

function renderOnboardingChecklist() {
  onboardingChecklist.innerHTML = testsCache
    .map((item) => `
      <label class="step" style="display: flex; align-items: center; gap: 10px;">
        <input type="checkbox" name="selected_tests" value="${escapeHtml(item.id)}" />
        <span><strong>${escapeHtml(item.id)} - ${escapeHtml(item.nome || "")}</strong><br>${escapeHtml(item.objetivo_esperado || "")}</span>
      </label>
    `)
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
  progressTitle.textContent = `${summary.testes_aprovados || 0} de ${summary.total_testes_planejados || 0} testes aprovados`;
  progressChip.textContent = `${overallPercent.toFixed(2)}%`;
  progressSummary.textContent = `${summary.testes_iniciados || 0} testes iniciados, ${summary.testes_aprovados || 0} aprovados, de ${summary.total_testes_planejados || 0} planejados.`;

  if (selectedTest) {
    selectedTestSummary.textContent = `${selectedTest.teste_id} - ${selectedTest.teste_nome || "Teste"}: ${selectedTest.attempts_total} tentativa(s), ${selectedTest.percentual_sucesso.toFixed(2)}% de sucesso.`;
  } else {
    selectedTestSummary.textContent = "Nenhum teste selecionado recentemente.";
  }

  if (tests.length === 0) {
    progressTableBody.innerHTML = '<tr><td colspan="6">Nenhum teste realizado para este CNPJ.</td></tr>';
    return;
  }

  progressTableBody.innerHTML = tests
    .map((item) => `
      <tr>
        <td>${escapeHtml(item.teste_id)} - ${escapeHtml(item.teste_nome || "")}</td>
        <td>${escapeHtml(item.status || "-")}</td>
        <td>${escapeHtml(item.attempts_total)}</td>
        <td>${escapeHtml(item.attempts_until_approval ?? "-")}</td>
        <td>${escapeHtml(Number(item.percentual_sucesso || 0).toFixed(2))}%</td>
        <td>${escapeHtml(Number(item.percentual_ate_aprovacao || 0).toFixed(2))}%</td>
      </tr>
    `)
    .join("");
}

async function loadClientProgress(cnpj, selectedTest) {
  const normalized = normalizeCnpj(cnpj);
  const resp = await fetch(`/api/client/progress?cnpj=${encodeURIComponent(normalized)}`);
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.error || "Falha ao carregar progresso do cliente.");
  }
  applyClientProgressState(data, selectedTest);
}

function renderResult(data) {
  const resultado = String(data.resultado || "").toUpperCase();
  const isApproved = resultado === "APROVADO";

  resultPanel.classList.remove("hidden");

  overallStatus.textContent = isApproved ? "APROVADO" : "NEGADO";
  statusChip.textContent = isApproved ? "APROVADO" : "NEGADO";
  statusChip.style.background = isApproved ? "#d5f1e5" : "#f6dada";
  statusChip.style.color = isApproved ? "#0f6e4f" : "#9e2424";

  protocol.textContent = data.protocolo || "-";

  if (isApproved) {
    deniedLeg.textContent = "-";
    deniedReason.textContent = "Resultado aprovado. Nenhum detalhe adicional necessario.";
  } else {
    deniedLeg.textContent = data.perna_negada || "Perna nao identificada";
    deniedReason.textContent = data.motivo_negacao || "Motivo nao identificado";
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
    showToast("Informe o CNPJ do cliente.");
    return;
  }

  accessSubmitBtn.disabled = true;
  accessSubmitBtn.classList.add("loading");
  accessSubmitBtn.textContent = "Acessando...";

  try {
    setWorkspaceCnpj(normalized);
    accessPanel.classList.add("hidden");
    await loadClientProgress(normalized);
  } catch (err) {
    clearWorkspaceCnpj();
    const msg = err instanceof Error && err.message
      ? err.message
      : "Não foi possível carregar o progresso deste CNPJ.";
    showToast(msg);
  } finally {
    accessSubmitBtn.disabled = false;
    accessSubmitBtn.classList.remove("loading");
    accessSubmitBtn.textContent = "Acessar homologacoes";
  }
});

changeCnpjBtn.addEventListener("click", () => {
  clearWorkspaceCnpj();
});

onboardingForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  if (!cnpjHidden.value) {
    showToast("Informe o CNPJ antes de selecionar os testes.");
    return;
  }

  const selectedTests = Array.from(onboardingChecklist.querySelectorAll('input[name="selected_tests"]:checked'))
    .map((item) => item.value);

  if (selectedTests.length === 0) {
    showToast("Selecione ao menos um teste para este cliente.");
    return;
  }

  onboardingSubmitBtn.disabled = true;
  onboardingSubmitBtn.classList.add("loading");
  onboardingSubmitBtn.textContent = "Salvando...";

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
      throw new Error(data.error || "Falha ao salvar testes do cliente.");
    }

    applyClientProgressState(data);
  } catch (err) {
    const msg = err instanceof Error && err.message
      ? err.message
      : "Não foi possível salvar os testes deste cliente.";
    showToast(msg);
  } finally {
    onboardingSubmitBtn.disabled = false;
    onboardingSubmitBtn.classList.remove("loading");
    onboardingSubmitBtn.textContent = "Salvar testes do cliente";
  }
});

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  if (!cnpjHidden.value) {
    showToast("Informe o CNPJ antes de realizar homologações.");
    return;
  }

  submitBtn.disabled = true;
  submitBtn.classList.add("loading");
  submitBtn.textContent = "Processando...";

  try {
    const formData = new FormData(form);
    const resp = await fetch("/api/client/validate", {
      method: "POST",
      body: formData,
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Falha ao processar validacao.");
    }

    renderResult(data);
  } catch (err) {
    const msg = err instanceof Error && err.message
      ? err.message
      : "Nao foi possivel validar seu teste. Tente novamente.";
    showToast(msg);
  } finally {
    submitBtn.disabled = false;
    submitBtn.classList.remove("loading");
    submitBtn.textContent = "Enviar para validacao";
  }
});

loadTests().catch(() => {
  testSelect.innerHTML = '<option value="">Falha ao carregar testes</option>';
});

const savedCnpj = normalizeCnpj(sessionStorage.getItem(CNPJ_STORAGE_KEY) || "");
if (savedCnpj) {
  setWorkspaceCnpj(savedCnpj);
  accessPanel.classList.add("hidden");
  loadClientProgress(savedCnpj).catch(() => {
    clearWorkspaceCnpj();
  });
}
