// =====================================================================
// client.js – Navegacao e logica do portal do cliente
// =====================================================================

// ---- Navegacao Sidebar (Cliente) ----
const navButtons = document.querySelectorAll(".workspace-nav-item");
const sections = document.querySelectorAll(".client-section");

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const sectionId = btn.dataset.section;
    
    // Validar CNPJ para seção "submit"
    if (sectionId === "submit" && !cnpjHidden.value) {
      showToast(t("client.errorEnterCnpj"));
      return;
    }
    
    // Validar CNPJ para seção "progress"
    if (sectionId === "progress" && !cnpjHidden.value) {
      showToast(t("client.errorEnterCnpj"));
      return;
    }
    
    // Remove active de todos os botões
    navButtons.forEach((b) => b.classList.remove("active"));
    // Esconde todas as seções
    sections.forEach((s) => s.classList.add("hidden"));
    
    // Ativa o botão clicado
    btn.classList.add("active");
    
    // Mostra a seção correspondente
    if (sectionId === "access") {
      document.getElementById("clientAccessPanel").classList.remove("hidden");
    } else if (sectionId === "submit") {
      document.getElementById("clientWorkspacePanel").classList.remove("hidden");
      // Atualizar visibilidade dos campos DE41/DE42 conforme o produto
      const pid = normalizeProductId(selectedProductId || localStorage.getItem("homolog_selected_product") || "01_QRCARDSE");
      if (typeof updateAccessFormForProduct === "function") {
        updateAccessFormForProduct(pid);
      }
    } else if (sectionId === "progress") {
      document.getElementById("clientProgressPanel").classList.remove("hidden");
      // Recarrega dados de progresso ao abrir
      loadProgressData();
    }
  });
});

// Funcao para carregar dados de progresso (será chamada ao abrir a seção)
function loadProgressData() {
  const cnpj = cnpjHidden.value;
  if (!cnpj) {
    return;
  }
  const pid = normalizeProductId(selectedProductId || localStorage.getItem("homolog_selected_product") || "01");
  // Busca os dados de progresso via API
  fetch(`/api/client/progress-produto?cnpj=${encodeURIComponent(cnpj)}&produto_id=${encodeURIComponent(pid)}`)
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        console.error(data.error);
        return;
      }
      updateProgressVisualization(data);
    })
    .catch((err) => console.error("Erro ao carregar progresso:", err));
}

// Funcao para atualizar a visualizacao do progresso
function updateProgressVisualization(progressData) {
  // O endpoint retorna os dados dentro de "summary"; aceitar também na raiz por compatibilidade
  const src = (progressData.summary && typeof progressData.summary === 'object' && Object.keys(progressData.summary).length > 0)
    ? progressData.summary
    : progressData;

  // Mapear dados da API - tentar múltiplas chaves possíveis
  const planned = Number(src.total_testes_planejados ?? src.total_planned ?? src.planned ?? 0);
  const approved = Number(src.testes_aprovados ?? src.total_approved ?? src.approved ?? 0);
  const initiated = Number(src.testes_iniciados ?? src.total_initiated ?? src.initiated ?? approved);
  const pending = Math.max(0, planned - initiated);
  
  const completionPercent = planned > 0 ? Math.round((approved / planned) * 100) : 0;
  // Usar percentual_aprovacao_geral do backend (aprovados / planejados), não aprovados / iniciados
  const approvalRate = src.percentual_aprovacao_geral != null
    ? Math.round(src.percentual_aprovacao_geral)
    : (planned > 0 ? Math.round((approved / planned) * 100) : 0);
  const avgAttempts = src.tentativas_medias || src.avg_attempts || src.average_attempts || 0;
  
  // Atualiza os métricas
  document.getElementById("metricPlanned").textContent = planned;
  document.getElementById("metricApproved").textContent = approved;
  document.getElementById("metricInProgress").textContent = initiated;
  document.getElementById("metricPending").textContent = pending;
  
  // Atualiza a barra de progresso
  document.getElementById("progressPercentage").textContent = `${completionPercent}%`;
  document.getElementById("progressBarFill").style.width = `${completionPercent}%`;
  
  // Atualiza as estatísticas
  document.getElementById("statApprovalRate").textContent = `${approvalRate}%`;
  document.getElementById("statAverageAttempts").textContent = typeof avgAttempts === 'number' ? avgAttempts.toFixed(1) : avgAttempts;
}

const accessForm = document.getElementById("clientAccessForm");
const accessPanel = document.getElementById("clientAccessPanel");
const onboardingPanel = document.getElementById("clientOnboardingPanel");
const onboardingForm = document.getElementById("clientOnboardingForm");
const onboardingChecklist = document.getElementById("clientOnboardingChecklist");
const onboardingSubmitBtn = document.getElementById("onboardingSubmitBtn");
const workspacePanel = document.getElementById("clientWorkspacePanel");
const progressPanel = document.getElementById("clientProgressPanel");
const cnpjInput = document.getElementById("cnpjInput");
const cnpjInputAutorizador = document.getElementById("cnpjInputAutorizador");
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
const dataTesteInput = document.getElementById("dataTeste");

const resultPanel = document.getElementById("clientResultPanel");
const overallStatus = document.getElementById("clientOverallStatus");
const statusChip = document.getElementById("clientStatusChip");
const protocol = document.getElementById("clientProtocol");
const deniedLeg = document.getElementById("clientDeniedLeg");
const deniedReason = document.getElementById("clientDeniedReason");
const i18n = window.I18N || { t: (key) => key };
const t = (key, vars) => i18n.t(key, vars);

const CNPJ_STORAGE_KEY = "homolog_client_cnpj";
var testsCache = [];
var assignedTestIds = [];
let lastFetchedQrLogDate = "";

// Inicializar formulário de validação conforme o produto armazenado
document.addEventListener("DOMContentLoaded", () => {
  const storedProduct = localStorage.getItem("homolog_selected_product");
  if (storedProduct && typeof updateAccessFormForProduct === "function") {
    updateAccessFormForProduct(storedProduct);
  }
});

function normalizeProductId(id) {
  let normalized = String(id || "").trim();
  // Se não for o nome completo, converter de número para nome
  if (normalized === "01" || normalized === "1") {
    return "01_QRCARDSE";
  } else if (normalized === "02" || normalized === "2") {
    return "02_AutorizadorCARDSE";
  }
  // Se já for o nome completo, retornar como está
  return normalized || "01_QRCARDSE";
}

function dateToCompact(isoDate) {
  return String(isoDate || "").replace(/-/g, "").slice(0, 8);
}

async function fetchLogsByDateForClientQr(testDateValue) {
  const pid = normalizeProductId(selectedProductId || localStorage.getItem("homolog_selected_product") || "01_QRCARDSE");
  if (pid !== "01_QRCARDSE") {
    return;
  }

  const compactDate = dateToCompact(testDateValue);
  if (!compactDate || compactDate.length !== 8) {
    return;
  }

  if (lastFetchedQrLogDate === compactDate) {
    return;
  }

  try {
    const resp = await fetch(`/api/produtos/${encodeURIComponent(pid)}/logs/fetch-by-date`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data_teste: compactDate }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      // Apenas avisa, não lança erro
      console.warn("[fetchLogsByDateForClientQr] Aviso:", data.error || "Falha ao buscar logs do dia para QR");
      showToast("⚠️ Não foi possível buscar os logs automaticamente. Você pode informar o nome do arquivo de log manualmente.");
      return;
    }

    lastFetchedQrLogDate = compactDate;
    showToast("✓ Logs coletados com sucesso para " + compactDate);
  } catch (err) {
    // Erro de conexão ou outro - apenas avisa
    console.warn("[fetchLogsByDateForClientQr] Erro:", err);
    showToast("⚠️ Não foi possível buscar os logs automaticamente. Você pode informar o nome do arquivo de log manualmente.");
  }
}

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
  const currentProductId = normalizeProductId(
    (typeof selectedProductId !== "undefined" && selectedProductId)
      || localStorage.getItem("homolog_selected_product")
      || "01_QRCARDSE"
  );

  // Para o Autorizador (produto 02_AutorizadorCARDSE), usar sempre o nome vindo do roteiro.
  if (currentProductId === "02_AutorizadorCARDSE") {
    return String(fallbackName || "");
  }

  if (i18n.translateTestName) {
    return i18n.translateTestName(testId, fallbackName);
  }
  return String(fallbackName || "");
}

function resolveTestNameById(testId, fallbackName) {
  // Validar que testsCache é um array
  if (!Array.isArray(testsCache)) {
    return String(fallbackName || "");
  }
  
  const normalizedId = String(testId || "").padStart(2, "0");
  const fromCache = testsCache.find((item) => String(item.id || "").padStart(2, "0") === normalizedId);
  const cachedName = fromCache ? String(fromCache.nome || "") : "";
  const nameBase = cachedName || String(fallbackName || "");
  return localizedTestName(normalizedId, nameBase);
}

function setWorkspaceCnpj(cnpj) {
  const normalized = normalizeCnpj(cnpj);
  cnpjHidden.value = normalized;
  clientCnpjLabel.textContent = formatCnpj(normalized);
  if (cnpjInput) cnpjInput.value = formatCnpj(normalized);
  if (cnpjInputAutorizador) cnpjInputAutorizador.value = formatCnpj(normalized);
  sessionStorage.setItem(CNPJ_STORAGE_KEY, normalized);
}

// Funcao auxiliar para atualizar o sidebar quando as seções mudam
function updateSidebarActive(sectionId) {
  navButtons.forEach((b) => b.classList.remove("active"));
  const btn = document.querySelector(`[data-section="${sectionId}"]`);
  if (btn) {
    btn.classList.add("active");
  }
}

function clearWorkspaceCnpj() {
  sessionStorage.removeItem(CNPJ_STORAGE_KEY);
  cnpjHidden.value = "";
  clientCnpjLabel.textContent = "-";
  assignedTestIds = [];
  
  // Volta para o painel de acesso (CNPJ)
  if (typeof backToAccessPanel !== "undefined") {
    backToAccessPanel();
  } else {
    // Fallback
    const accessPanel = document.getElementById("clientAccessPanel");
    const panels = document.querySelectorAll(".client-section");
    panels.forEach((p) => p.classList.add("hidden"));
    if (accessPanel) accessPanel.classList.remove("hidden");
  }
}

function renderAllowedTestsSelect() {
  // Validar que testsCache é um array
  if (!Array.isArray(testsCache)) {
    console.error("[renderAllowedTestsSelect] testsCache não é um array:", testsCache);
    testsCache = [];
  }
  
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

  // Validar que testsCache é um array
  if (!Array.isArray(testsCache)) {
    clientGoalBox.textContent = t("client.goalMissing");
    return;
  }
  
  const selectedTest = testsCache.find((item) => String(item.id || "").padStart(2, "0") === selectedId);
  clientGoalBox.textContent = selectedTest
    ? String(selectedTest.objetivo_esperado || t("client.goalMissing"))
    : t("client.goalNotFound");
}

function renderOnboardingChecklist() {
  if (!onboardingChecklist) return;
  
  // Validar que testsCache é um array
  if (!Array.isArray(testsCache)) {
    console.error("[renderOnboardingChecklist] testsCache não é um array:", testsCache);
    onboardingChecklist.innerHTML = "<p>Erro ao carregar testes disponíveis.</p>";
    return;
  }
  
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

async function loadTests(productId, cnpj) {
  // Normalizar productId - sempre usar nome descritivo
  const pid = normalizeProductId(productId || selectedProductId || "01_QRCARDSE");
  let url = `/api/produtos/${pid}/tests`;
  
  // Debug
  console.log("[loadTests] Loading tests for product:", pid, "CNPJ:", cnpj);
  
  // Adicionar CNPJ como parâmetro se disponível
  if (cnpj) {
    url += `?cnpj=${encodeURIComponent(cnpj)}`;
  }
  
  // Limpar cache antigo
  testsCache = [];
  
  const resp = await fetch(url);
  const data = await resp.json();
  const tests = data.testes || data.tests || [];  // ✅ Tenta ambos: "testes" (correto) e "tests" (compatibilidade)
  console.log("[loadTests] Loaded", tests.length, "tests:", tests.map(t => t.id + " - " + t.nome).join(", "));
  testsCache = tests;

  renderOnboardingChecklist();
  renderAllowedTestsSelect();
}

function applyClientProgressState(data, selectedTest) {
  assignedTestIds = Array.isArray(data.assigned_tests)
    ? data.assigned_tests.map((item) => String(item.id || "").padStart(2, "0"))
    : [];

  // Esconde todas as seções
  sections.forEach((s) => s.classList.add("hidden"));

  if (data.onboarding_required) {
    if (onboardingPanel) onboardingPanel.classList.remove("hidden");
    updateSidebarActive("access");
    return;
  }

  if (onboardingPanel) onboardingPanel.classList.add("hidden");
  
  // NOVO: Verifica se há testes selecionados em localStorage
  const selectedProductId = normalizeProductId(
    (typeof window.selectedProductId !== "undefined" && window.selectedProductId) 
    || localStorage.getItem("homolog_selected_product") 
    || "01_QRCARDSE"
  );
  const selectedTests = typeof getSelectedTests !== "undefined" ? getSelectedTests() : [];
  
  if (selectedTests && selectedTests.length > 0) {
    // Cliente já tem testes selecionados → vai direto para modo
    const modePanel = document.getElementById("clientModeSelectionPanel");
    if (modePanel) {
      modePanel.classList.remove("hidden");
    } else {
      // Fallback
      workspacePanel.classList.remove("hidden");
    }
  } else {
    // Cliente precisa selecionar testes → mostra painel de modo
    const modePanel = document.getElementById("clientModeSelectionPanel");
    if (modePanel) {
      modePanel.classList.remove("hidden");
    } else {
      // Fallback
      workspacePanel.classList.remove("hidden");
    }
  }
  
  updateSidebarActive("submit");
  renderAllowedTestsSelect();
  renderProgress(data, selectedTest);
}

function renderProgress(data, selectedTest) {
  const summary = data.summary || {};
  const tests = Array.isArray(data.tests) ? data.tests : [];
  const overallPercent = Number(summary.percentual_aprovacao_geral || 0);

  // Mantém o card visual de progresso sincronizado em qualquer fluxo (acesso, resultado e navegação).
  updateProgressVisualization({ summary });

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
    const selectedName = resolveTestNameById(selectedTest.teste_id, selectedTest.teste_nome || "Teste");
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
      const testName = resolveTestNameById(item.teste_id, item.teste_nome || "");
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

async function loadClientProgress(cnpj, selectedTest, productId) {
  const normalized = normalizeCnpj(cnpj);
  const pid = normalizeProductId(productId || selectedProductId || localStorage.getItem("homolog_selected_product") || "01");
  const url = `/api/client/progress-produto?cnpj=${encodeURIComponent(normalized)}&produto_id=${encodeURIComponent(pid)}`;
  const resp = await fetch(url);
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.error || t("client.errorLoadProgress"));
  }
  applyClientProgressState(data, selectedTest);
}

function renderResult(data) {
  const resultado = String(data.resultado || "").toUpperCase();
  const isApproved = resultado === "APROVADO";

  // Esconde outras seções e mostra o resultado
  sections.forEach((s) => s.classList.add("hidden"));
  resultPanel.classList.remove("hidden");
  navButtons.forEach((b) => b.classList.remove("active"));

  overallStatus.textContent = isApproved ? t("client.resultApproved") : t("client.resultDenied");
  statusChip.textContent = isApproved ? t("client.resultApproved") : t("client.resultDenied");
  statusChip.style.background = isApproved ? "#d5f1e5" : "#f6dada";
  statusChip.style.color = isApproved ? "#0f6e4f" : "#9e2424";

  protocol.textContent = data.protocolo || "-";
  deniedReason.style.whiteSpace = "pre-line";

  if (isApproved) {
    deniedLeg.textContent = "-";
    deniedReason.textContent = t("client.approvedHint");
  } else {
    const deniedLegs = Array.isArray(data.pernas_negadas) && data.pernas_negadas.length
      ? data.pernas_negadas
      : [data.perna_negada || t("client.deniedLegUnknown")];
    const deniedReasons = Array.isArray(data.motivos_negacao) && data.motivos_negacao.length
      ? data.motivos_negacao
      : [data.motivo_negacao || t("client.deniedReasonUnknown")];

    deniedLeg.textContent = deniedLegs.join(" | ");
    deniedReason.textContent = deniedReasons.map((msg, idx) => `${idx + 1}. ${msg}`).join("\n");
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

function voltarParaValidacao() {
  // Esconde resultado e volta ao formulário de validação, mantendo o CNPJ
  sections.forEach((s) => s.classList.add("hidden"));
  resultPanel.classList.add("hidden");
  workspacePanel.classList.remove("hidden");
  // Limpa apenas os campos do teste (não o CNPJ)
  if (form) form.reset();
  // Restaura o CNPJ oculto e o label
  const storedCnpj = sessionStorage.getItem(CNPJ_STORAGE_KEY);
  if (storedCnpj) {
    cnpjHidden.value = storedCnpj;
  }
  if (clientGoalBox) clientGoalBox.textContent = t("client.goalDefault");
  updateSidebarActive("submit");
  workspacePanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function mostrarProgresso() {
  sections.forEach((s) => s.classList.add("hidden"));
  resultPanel.classList.add("hidden");
  progressPanel.classList.remove("hidden");
  if (cnpjHidden && cnpjHidden.value) {
    loadProgressData();
  }
  updateSidebarActive("progress");
  progressPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

if (cnpjInput) {
  cnpjInput.addEventListener("input", () => {
    cnpjInput.value = formatCnpj(cnpjInput.value);
  });
}

if (cnpjInputAutorizador) {
  cnpjInputAutorizador.addEventListener("input", () => {
    cnpjInputAutorizador.value = formatCnpj(cnpjInputAutorizador.value);
  });
}

changeCnpjBtn.addEventListener("click", () => {
  if (typeof backToProductPanel !== "undefined") {
    backToProductPanel();
  } else {
    clearWorkspaceCnpj();
  }
});

accessForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  const cnpjValue = document.getElementById("cnpjInput").value || "";
  const normalized = normalizeCnpj(cnpjValue);

  if (!normalized) {
    showToast(t("client.errorEnterCnpj"));
    return;
  }

  // Validação: Autorizador aceita máximo 4 dígitos
  const pid = normalizeProductId(selectedProductId || localStorage.getItem("homolog_selected_product") || "01_QRCARDSE");
  if (pid === "02_AutorizadorCARDSE" && normalized.length > 4) {
    showToast("Código Autorizador deve ter no máximo 4 dígitos");
    return;
  }

  accessSubmitBtn.disabled = true;
  accessSubmitBtn.classList.add("loading");
  accessSubmitBtn.textContent = t("client.accessing");

  try {
    setWorkspaceCnpj(normalized);

    const accessPanel = document.getElementById("clientAccessPanel");
    if (accessPanel) accessPanel.classList.add("hidden");

    // Verifica se é primeiro acesso para este CNPJ + produto
    const pid = normalizeProductId(selectedProductId || localStorage.getItem("homolog_selected_product") || "01");
    const resp = await fetch(`/api/client/progress-produto?cnpj=${encodeURIComponent(normalized)}&produto_id=${encodeURIComponent(pid)}`);
    const data = await resp.json();

    const isFirstAccess = data.onboarding_required ||
      !Array.isArray(data.assigned_tests) || data.assigned_tests.length === 0;

    if (isFirstAccess) {
      // Primeiro acesso: carrega testes disponíveis e mostra seleção
      await loadAvailableTests(pid);
    } else {
      // Cliente retornando: vai direto para seleção de modo
      // Restaura assignedTestIds a partir dos testes designados
      assignedTestIds = (data.assigned_tests || []).map((item) =>
        String(item.id || item).padStart(2, "0")
      );
      const modePanel = document.getElementById("clientModeSelectionPanel");
      if (modePanel) modePanel.classList.remove("hidden");
    }
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

if (onboardingForm) onboardingForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  if (!cnpjHidden.value) {
    showToast(t("client.errorEnterCnpj"));
    return;
  }

  if (onboardingSubmitBtn) onboardingSubmitBtn.disabled = true;
  if (onboardingSubmitBtn) onboardingSubmitBtn.classList.add("loading");
  if (onboardingSubmitBtn) onboardingSubmitBtn.textContent = t("client.saving");

  try {
    const formData = new FormData(onboardingForm);
    formData.append("cnpj", cnpjHidden.value);
    const pid = normalizeProductId(selectedProductId || localStorage.getItem("homolog_selected_product") || "01");
    formData.append("produto_id", pid);

    const resp = await fetch("/api/client/enroll-produto", {
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
    if (onboardingSubmitBtn) onboardingSubmitBtn.disabled = false;
    if (onboardingSubmitBtn) onboardingSubmitBtn.classList.remove("loading");
    if (onboardingSubmitBtn) onboardingSubmitBtn.textContent = t("client.saveTests");
  }
});

testSelect.addEventListener("change", () => {
  updateClientGoalBySelectedTest();
});

// Removed automatic log fetch on date change - only fetch when clicking validate button
// if (dataTesteInput) {
//   dataTesteInput.addEventListener("change", async () => {
//     // Tenta buscar logs automaticamente, mas não falha se não conseguir
//     await fetchLogsByDateForClientQr(dataTesteInput.value);
//   });
// }

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
    // Adicionar produto_id - usar a mesma lógica de recuperação
    let pid = selectedProductId || (localStorage.getItem("homolog_selected_product") || "");
    pid = normalizeProductId(pid || "01_QRCARDSE");
    
    if (!pid || pid === "00_UNKNOWN") {
      throw new Error(t("client.errorSelectProduct") || "Por favor, selecione um produto.");
    }

    // Somente QR: tenta buscar logs da data selecionada (mas não falha se não conseguir)
    if (pid === "01_QRCARDSE") {
      const dataTeste = String(formData.get("data_teste") || "");
      await fetchLogsByDateForClientQr(dataTeste);
    }
    
    console.log("[form.submit] Validating with product:", pid);
    formData.append("produto_id", pid);
    
    const resp = await fetch("/api/client/validate-produto", {
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

// Listener para formulário de batch validation
const batchValidationForm = document.getElementById("batchValidationForm");
if (batchValidationForm) {
  batchValidationForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();

    if (!cnpjHidden.value) {
      showToast(t("client.errorCnpjBeforeValidate"));
      return;
    }

    const batchSubmitBtn = document.getElementById("batchSubmitBtn");
    const roteiroFile = document.getElementById("batchRoteiroFile");
    const dataLog = document.getElementById("batchDataLog");

    if (!roteiroFile.files.length) {
      showToast("Por favor, selecione um arquivo roteiro");
      return;
    }

    batchSubmitBtn.disabled = true;
    batchSubmitBtn.classList.add("loading");
    batchSubmitBtn.textContent = "Enviando...";

    try {
      const formData = new FormData();
      formData.append("roteiro_file", roteiroFile.files[0]);
      formData.append("log_name", "aud_" + dateToCompact(dataLog.value) + ".txt");
      formData.append("cnpj", cnpjHidden.value);
      
      let pid = selectedProductId || (localStorage.getItem("homolog_selected_product") || "");
      pid = normalizeProductId(pid || "02_AutorizadorCARDSE");
      formData.append("produto_id", pid);

      // Adicionar testes selecionados
      const selectedTests = typeof getSelectedTests !== "undefined" ? getSelectedTests() : [];
      if (selectedTests.length > 0) {
        formData.append("testes_selecionados", JSON.stringify(selectedTests));
      }

      const resp = await fetch("/api/validar-roteiro-cliente-batch", {
        method: "POST",
        body: formData,
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || "Falha ao validar roteiro em batch");
      }

      // Mostra resultado
      renderBatchValidationResult(data);
    } catch (err) {
      const msg = err instanceof Error && err.message ? err.message : "Erro ao validar roteiro";
      showToast(msg);
    } finally {
      batchSubmitBtn.disabled = false;
      batchSubmitBtn.classList.remove("loading");
      batchSubmitBtn.textContent = "Validar Roteiro em Batch";
    }
  });
}

// Função para renderizar resultado de batch validation
function renderBatchValidationResult(data) {
  // Cria um painel de resultado customizado para batch
  const resultPanel = document.getElementById("clientResultPanel");
  if (!resultPanel) return;

  sections.forEach((s) => s.classList.add("hidden"));
  resultPanel.classList.remove("hidden");

  const overallStatus = document.getElementById("clientOverallStatus");
  const statusChip = document.getElementById("clientStatusChip");
  
  const percentual = data.resumo?.percentual_sucesso || 0;
  const isSuccess = percentual === 100;
  
  if (overallStatus) {
    overallStatus.textContent = `Batch: ${percentual}% de sucesso (${data.resumo?.aprovados || 0}/${data.resumo?.validados || 0} testes)`;
  }
  if (statusChip) {
    statusChip.textContent = isSuccess ? "100% ✓" : `${percentual}%`;
    statusChip.style.background = isSuccess ? "#d5f1e5" : "#fff3cd";
    statusChip.style.color = isSuccess ? "#0f6e4f" : "#856404";
  }

  const deniedReason = document.getElementById("clientDeniedReason");
  if (deniedReason) {
    deniedReason.style.whiteSpace = "pre-wrap";
    deniedReason.style.fontFamily = "monospace";
    deniedReason.style.fontSize = "0.9rem";
    deniedReason.style.lineHeight = "1.6";
    
    let resultText = `📋 VALIDAÇÃO EM BATCH\n`;
    resultText += `${"═".repeat(70)}\n\n`;
    
    resultText += `🆔 Submissão ID: ${data.submissao_id}\n`;
    resultText += `📅 Timestamp: ${data.timestamp}\n`;
    resultText += `📂 Log: ${data.log_name}\n`;
    resultText += `🏢 Produto: ${data.produto_id}\n\n`;
    
    resultText += `📊 RESUMO EXECUTIVO:\n`;
    resultText += `${"─".repeat(70)}\n`;
    resultText += `  Total Selecionados:   ${data.resumo?.total_selecionados || 0}\n`;
    resultText += `  Validados:            ${data.resumo?.validados || 0}\n`;
    resultText += `  Não Validados:        ${data.resumo?.nao_validados || 0}\n`;
    resultText += `  ✅ Aprovados:         ${data.resumo?.aprovados || 0}\n`;
    resultText += `  ❌ Reprovados:        ${data.resumo?.reprovados || 0}\n`;
    resultText += `  📈 Taxa de Sucesso:   ${percentual}%\n\n`;

    // Detalhes de cada teste
    if (data.resultados && data.resultados.length > 0) {
      resultText += `🔍 DETALHES DOS TESTES:\n`;
      resultText += `${"═".repeat(70)}\n\n`;
      
      const aprovadosTeste = [];
      const reprovadosTeste = [];
      
      data.resultados.forEach((teste) => {
        if (teste.status === "APROVADO") {
          aprovadosTeste.push(teste);
        } else {
          reprovadosTeste.push(teste);
        }
      });
      
      // Testes Aprovados
      if (aprovadosTeste.length > 0) {
        resultText += `✅ TESTES APROVADOS (${aprovadosTeste.length}):\n`;
        resultText += `${"─".repeat(70)}\n`;
        
        aprovadosTeste.forEach((teste) => {
          resultText += `\n  Teste ${teste.teste_id.toString().padStart(2, "0")}: APROVADO ✓\n`;
          resultText += `    BIT 11 (Stan): ${teste.bit11}\n`;
          resultText += `    BIT 42 (Estab): ${teste.bit42}\n`;
          if (teste.data_hora) {
            resultText += `    Data/Hora: ${teste.data_hora}\n`;
          }
          if (teste.cadeia && teste.cadeia !== "Nenhuma") {
            resultText += `    Cadeia: ${teste.cadeia}\n`;
          }
          if (teste.pernas_totais) {
            resultText += `    Pernas: ${teste.pernas_aprovadas}/${teste.pernas_totais} aprovadas\n`;
          }
        });
        resultText += `\n`;
      }
      
      // Testes Reprovados
      if (reprovadosTeste.length > 0) {
        resultText += `❌ TESTES REPROVADOS (${reprovadosTeste.length}):\n`;
        resultText += `${"─".repeat(70)}\n`;
        
        reprovadosTeste.forEach((teste) => {
          resultText += `\n  Teste ${teste.teste_id.toString().padStart(2, "0")}: REPROVADO ✗\n`;
          resultText += `    BIT 11 (Stan): ${teste.bit11}\n`;
          resultText += `    BIT 42 (Estab): ${teste.bit42}\n`;
          
          if (teste.motivo) {
            resultText += `    ⚠️  Motivo: ${teste.motivo}\n`;
          }
          
          if (teste.data_hora) {
            resultText += `    Data/Hora: ${teste.data_hora}\n`;
          }
          
          if (teste.cadeia && teste.cadeia !== "Nenhuma") {
            resultText += `    Cadeia: ${teste.cadeia}\n`;
          }
          
          if (teste.pernas_totais) {
            resultText += `    Pernas: ${teste.pernas_aprovadas}/${teste.pernas_totais} aprovadas\n`;
          }
        });
        resultText += `\n`;
      }
    }

    // Testes ignorados
    if (data.testes_ignorados && data.testes_ignorados.length > 0) {
      resultText += `⏭️  TESTES NÃO VALIDADOS (${data.testes_ignorados.length}):\n`;
      resultText += `${"═".repeat(70)}\n\n`;
      data.testes_ignorados.forEach((t) => {
        resultText += `  Teste ${t.teste_id.toString().padStart(2, "0")}: NÃO VALIDADO\n`;
        resultText += `    Motivo: ${t.motivo}\n\n`;
      });
    }
    
    resultText += `\n${"═".repeat(70)}\n`;
    resultText += `✨ FIM DO RELATÓRIO\n`;

    deniedReason.textContent = resultText;
  }

  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Pré-carrega os testes do produto selecionado ao carregar a página
// Isso é apenas para inicialização - os testes reais serão carregados quando o usuário fazer login
const savedProductId = normalizeProductId(selectedProductId || localStorage.getItem("homolog_selected_product") || "01");
console.log("[initialization] Initializing with product:", savedProductId);
loadTests(savedProductId, "").catch(() => {
  testSelect.innerHTML = `<option value="">${escapeHtml(t("validator.failTests"))}</option>`;
});

const savedCnpj = normalizeCnpj(sessionStorage.getItem(CNPJ_STORAGE_KEY) || "");
if (savedCnpj) {
  // Cliente já tem CNPJ salvo → mostra painel de produto
  setWorkspaceCnpj(savedCnpj);
  
  const accessPanel = document.getElementById("clientAccessPanel");
  const productPanel = document.getElementById("clientProductSelectionPanel");
  const sections = document.querySelectorAll(".client-section");
  
  sections.forEach((s) => s.classList.add("hidden"));
  
  if (productPanel) {
    productPanel.classList.remove("hidden");
  }
}

window.addEventListener("app-language-changed", () => {
  renderAllowedTestsSelect();
  updateClientGoalBySelectedTest();
  accessSubmitBtn.textContent = t("client.access");
  if (onboardingSubmitBtn) onboardingSubmitBtn.textContent = t("client.saveTests");
  submitBtn.textContent = t("client.sendValidation");
});
