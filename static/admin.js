// =====================================================================
// admin.js – lógica das abas e das telas de clientes/gestão (Stage 2)
// =====================================================================

// ---- Abas (novo layout com sidebar) ----
const navItems = document.querySelectorAll(".workspace-nav-item");
const adminPanels = document.querySelectorAll(".admin-tab-panel");
// i18n e t são declarados em app.js (carregado antes) e compartilhados no escopo global

navItems.forEach((item) => {
  item.addEventListener("click", () => {
    navItems.forEach((i) => i.classList.remove("active"));
    adminPanels.forEach((p) => p.classList.add("hidden"));
    item.classList.add("active");
    const target = document.getElementById(item.dataset.tab);
    if (target) {
      target.classList.remove("hidden");
    }

    if (item.dataset.tab === "tab-validador") {
      // Inicializa o seletor de modo
      initializeValidatorMode();
    }

    if (item.dataset.tab === "tab-clientes") {
      loadClients();
    }
    if (item.dataset.tab === "tab-gestao") {
      loadGestaoClientsList();
    }
  });
});

// ---- Utilitários ----
function escapeAdm(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showAdminToast(msg) {
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

function formatInternalStatus(status) {
  const raw = String(status || "").toUpperCase().replace(/_/g, " ");
  if (raw === "APROVADO") return String(t("status.approved")).toUpperCase();
  if (raw === "REPROVADO") return String(t("status.reproved")).toUpperCase();
  if (raw === "NAO APLICA" || raw === "NÃO APLICA") return String(t("status.na")).toUpperCase();
  if (raw === "NAO INICIADO" || raw === "NÃO INICIADO") return String(t("status.notStarted")).toUpperCase();
  if (raw === "EM ANDAMENTO") return String(t("status.inProgress")).toUpperCase();
  return raw || "-";
}

function localizedTestName(testId, fallbackName) {
  const currentProductId = String(
    (typeof selectedProductId !== "undefined" && selectedProductId)
      || localStorage.getItem("homolog_selected_product")
      || "01"
  ).trim().padStart(2, "0");

  // Em gestão multiproduto e no Autorizador, manter o nome do roteiro para não cruzar títulos de QR.
  if (currentProductId === "02" || String(fallbackName || "").trim()) {
    return String(fallbackName || "");
  }

  if (i18n.translateTestName) {
    return i18n.translateTestName(testId, fallbackName);
  }
  return String(fallbackName || "");
}

function localizedResultLabel(result) {
  const raw = String(result || "").toUpperCase().replace(/_/g, " ");
  if (raw === "APROVADO") return String(t("status.approved")).toUpperCase();
  if (raw === "REPROVADO") return String(t("status.reproved")).toUpperCase();
  if (raw === "NAO APLICA" || raw === "NÃO APLICA") return String(t("status.na")).toUpperCase();
  if (raw === "NAO INICIADO" || raw === "NÃO INICIADO") return String(t("status.notStarted")).toUpperCase();
  if (raw === "EM ANDAMENTO") return String(t("status.inProgress")).toUpperCase();
  return String(result || "-");
}

function formatInternalStatusWithIcon(status) {
  const raw = String(status || "").toUpperCase();
  const label = formatInternalStatus(status);
  if (raw === "APROVADO") {
    return `<span class="status-icon-ok" title="${escapeAdm(t("status.approved"))}">&#10003;</span> ${escapeAdm(label)}`;
  }
  return escapeAdm(label);
}

// =====================================================================
// ABA 2 – CLIENTES EM HOMOLOGAÇÃO
// =====================================================================
const clientsTableBody = document.getElementById("clientsTableBody");
const clientsSearchInput = document.getElementById("clientsSearchInput");
const refreshClientsBtn = document.getElementById("refreshClientsBtn");
const clientDetailPanel = document.getElementById("clientDetailPanel");
const clientDetailTitle = document.getElementById("clientDetailTitle");
const clientDetailTableBody = document.getElementById("clientDetailTableBody");

let clientsCache = [];
// productsCache é declarado em app.js e compartilhado no escopo global

function getProductName(produtoId) {
  const pid = String(produtoId || "").padStart(2, "0");
  const found = (productsCache || []).find((p) => String(p.id || "").padStart(2, "0") === pid);
  return found ? String(found.nome || pid) : pid;
}

async function loadProductsCache() {
  if (productsCache.length > 0) return;
  try {
    const resp = await fetch("/api/produtos");
    const data = await resp.json();
    if (resp.ok) {
      productsCache = Array.isArray(data.produtos) ? data.produtos : [];
    }
  } catch (_) {
    productsCache = [];
  }
}

async function loadClients() {
  if (clientsTableBody) {
    clientsTableBody.innerHTML = `<tr><td colspan="7">${escapeAdm(t("admin.loadingClients"))}</td></tr>`;
  }
  try {
    await loadProductsCache();
    const resp = await fetch("/api/admin/clients-produtos");
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || t("admin.errorListClients"));
    clientsCache = data.clients || [];
    renderClientsTable(clientsCache);
  } catch (err) {
    if (clientsTableBody) {
      clientsTableBody.innerHTML = `<tr><td colspan="7">${escapeAdm(t("admin.fail", { message: err.message }))}</td></tr>`;
    }
  }
}

function renderClientsTable(clients) {
  if (!clientsTableBody) return;

  if (!clients || clients.length === 0) {
    clientsTableBody.innerHTML = `<tr><td colspan="7">${escapeAdm(t("admin.noneClients"))}</td></tr>`;
    return;
  }

  clientsTableBody.innerHTML = clients
    .map((item) => {
      const onbStatus = item.onboarding_completed
        ? `<span class="tag ok">${escapeAdm(t("clients.onboardingDone"))}</span>`
        : `<span class="tag na">${escapeAdm(t("clients.onboardingPending"))}</span>`;
      const pct = Number(item.percentual_aprovacao_geral || 0).toFixed(2);
      return `
        <tr class="clients-row" data-cnpj="${escapeAdm(item.cnpj)}" style="cursor:pointer;">
          <td>${escapeAdm(item.cnpj)}</td>
          <td>${onbStatus}</td>
          <td>${escapeAdm(item.total_testes_planejados)}</td>
          <td>${escapeAdm(item.testes_iniciados)}</td>
          <td>${escapeAdm(item.testes_aprovados)}</td>
          <td><strong>${escapeAdm(pct)}%</strong></td>
          <td>${escapeAdm(item.updated_at || "-")}</td>
        </tr>
      `;
    })
    .join("");

  clientsTableBody.querySelectorAll("tr[data-cnpj]").forEach((row) => {
    row.addEventListener("click", () => {
      const cnpj = row.dataset.cnpj;
      loadClientDetail(cnpj);
    });
  });
}

async function loadClientDetail(cnpj) {
  if (!clientDetailPanel || !clientDetailTitle || !clientDetailTableBody) return;

  clientDetailPanel.classList.remove("hidden");
  clientDetailTitle.textContent = cnpj;
  clientDetailTableBody.innerHTML = `<tr><td colspan="6">${escapeAdm(t("common.loading"))}</td></tr>`;
  clientDetailPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    await loadProductsCache();
    const resp = await fetch(`/api/client/progress-all-products?cnpj=${encodeURIComponent(cnpj)}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || t("admin.errorLoadDetail"));

    const tests = [];
    for (const p of (data.products || [])) {
      const produtoNome = String((p.produto || {}).nome || "Produto");
      for (const testItem of (p.tests || [])) {
        tests.push({ ...testItem, _produto_nome: produtoNome });
      }
    }

    if (tests.length === 0) {
      clientDetailTableBody.innerHTML = `<tr><td colspan="6">${escapeAdm(t("admin.noneTestsYet"))}</td></tr>`;
      return;
    }

    clientDetailTableBody.innerHTML = tests
      .map((item) => {
        const testName = localizedTestName(item.teste_id, item.teste_nome || "");
        const lastResult = localizedResultLabel(item.last_result);
        return `
        <tr>
          <td><strong>${escapeAdm(item._produto_nome || "-")}</strong><br>${escapeAdm(item.teste_id)} - ${escapeAdm(testName)}</td>
          <td>${formatInternalStatusWithIcon(item.status)}</td>
          <td>${escapeAdm(item.attempts_total)}</td>
          <td>${escapeAdm(item.attempts_until_approval ?? "-")}</td>
          <td>${escapeAdm(Number(item.percentual_sucesso || 0).toFixed(2))}%</td>
          <td>${escapeAdm(lastResult)}</td>
        </tr>
      `;
      })
      .join("");
  } catch (err) {
    clientDetailTableBody.innerHTML = `<tr><td colspan="6">${escapeAdm(t("admin.fail", { message: err.message }))}</td></tr>`;
  }
}

if (clientsSearchInput) {
  clientsSearchInput.addEventListener("input", () => {
    const q = clientsSearchInput.value.trim().toLowerCase();
    const filtered = clientsCache.filter((item) =>
      String(item.cnpj || "").toLowerCase().includes(q)
    );
    renderClientsTable(filtered);
  });
}

if (refreshClientsBtn) {
  refreshClientsBtn.addEventListener("click", () => loadClients());
}

// =====================================================================
// ABA 3 – GESTÃO DE TESTES POR CLIENTE
// =====================================================================
const gestaoClienteInput = document.getElementById("gestaoClienteInput");
const gestaoCarregarBtn = document.getElementById("gestaoCarregarBtn");
const gestaoClientsList = document.getElementById("gestaoClientsList");
const gestaoClientePanel = document.getElementById("gestaoClientePanel");
const gestaoClienteLabel = document.getElementById("gestaoClienteLabel");
const gestaoTestesChecklist = document.getElementById("gestaoTestesChecklist");
const gestaoSalvarTestesBtn = document.getElementById("gestaoSalvarTestesBtn");
const gestaoResetTestsBtn = document.getElementById("gestaoResetTestsBtn");
const gestaoResetOnboardingBtn = document.getElementById("gestaoResetOnboardingBtn");
const gestaoProdutoSelect = document.getElementById("gestaoProdutoSelect");

let gestaoCnpjAtual = "";
let gestaoTestesCache = [];
let gestaoProdutoAtual = "01";

function renderGestaoProdutos() {
  if (!gestaoProdutoSelect) return;
  const options = (productsCache || []).map((p) => {
    const id = String(p.id || "").padStart(2, "0");
    const selected = id === gestaoProdutoAtual ? "selected" : "";
    return `<option value="${escapeAdm(id)}" ${selected}>${escapeAdm(p.nome || id)}</option>`;
  });
  if (options.length === 0) {
    options.push(`<option value="01">Produto 01</option>`);
  }
  gestaoProdutoSelect.innerHTML = options.join("");
}

function renderGestaoClientsList(clients) {
  if (!gestaoClientsList) return;

  if (!clients || clients.length === 0) {
    gestaoClientsList.innerHTML = `<div class="gestao-clients-empty">${escapeAdm(t("admin.noneClients"))}</div>`;
    return;
  }

  gestaoClientsList.innerHTML = clients
    .map((item) => {
      const cnpj = String(item.cnpj || "");
      const pct = Number(item.percentual_aprovacao_geral || 0).toFixed(2);
      const activeClass = cnpj === gestaoCnpjAtual ? "active" : "";
      return `
        <button type="button" class="gestao-client-item ${activeClass}" data-cnpj="${escapeAdm(cnpj)}">
          <span>${escapeAdm(cnpj)}</span>
          <span class="gestao-client-pct">${escapeAdm(pct)}%</span>
        </button>
      `;
    })
    .join("");
}

async function loadGestaoClientsList() {
  if (gestaoClientsList) {
    gestaoClientsList.innerHTML = `<div class="gestao-clients-empty">${escapeAdm(t("common.loading"))}</div>`;
  }
  try {
    await loadProductsCache();
    renderGestaoProdutos();
    const resp = await fetch("/api/admin/clients-produtos");
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || t("admin.errorListClients"));
    clientsCache = data.clients || [];
    renderGestaoClientsList(clientsCache);
  } catch (err) {
    if (gestaoClientsList) {
      gestaoClientsList.innerHTML = `<div class="gestao-clients-empty">${escapeAdm(t("admin.fail", { message: err.message }))}</div>`;
    }
  }
}

async function loadAllTestsForGestao(produtoId) {
  try {
    const pid = String(produtoId || gestaoProdutoAtual || "01").padStart(2, "0");
    const resp = await fetch(`/api/produtos/${encodeURIComponent(pid)}/tests`);
    const data = await resp.json();
    gestaoTestesCache = data.tests || [];
  } catch (_) {
    gestaoTestesCache = [];
  }
}

function renderGestaoChecklist(assignedIds) {
  if (!gestaoTestesChecklist) return;
  const assigned = new Set((assignedIds || []).map((id) => String(id).padStart(2, "0")));

  gestaoTestesChecklist.innerHTML = gestaoTestesCache
    .map((item) => {
      const tid = String(item.id || "").padStart(2, "0");
      const checked = assigned.has(tid) ? "checked" : "";
      const testName = localizedTestName(tid, item.nome || "");
      return `
        <label class="step" style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
          <input type="checkbox" name="gestao_test" value="${escapeAdm(tid)}" ${checked} />
          <span><strong>${escapeAdm(tid)} - ${escapeAdm(testName)}</strong><br>
          <small style="color:#4a5f7d;">${escapeAdm(item.objetivo_esperado || "")}</small></span>
        </label>
      `;
    })
    .join("");
}

async function carregarGestaoCliente(cnpj) {
  const clientId = String(cnpj || "").trim();
  if (!clientId) {
    showAdminToast(t("admin.enterCnpj"));
    return;
  }

  if (gestaoClienteInput) {
    gestaoClienteInput.value = clientId;
  }

  if (gestaoCarregarBtn) {
    gestaoCarregarBtn.disabled = true;
    gestaoCarregarBtn.textContent = t("common.loading");
  }

  try {
    const pid = String((gestaoProdutoSelect && gestaoProdutoSelect.value) || gestaoProdutoAtual || "01").padStart(2, "0");
    gestaoProdutoAtual = pid;
    await loadAllTestsForGestao(pid);
    const resp = await fetch(`/api/client/progress-produto?cnpj=${encodeURIComponent(clientId)}&produto_id=${encodeURIComponent(pid)}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || t("admin.errorLoadClient"));

    gestaoCnpjAtual = clientId;
    if (gestaoClienteLabel) gestaoClienteLabel.textContent = `${clientId} • ${getProductName(pid)}`;
    if (gestaoClientePanel) gestaoClientePanel.classList.remove("hidden");

    const assignedIds = (data.assigned_tests || []).map((item) => String(item.id || "")).filter(Boolean);
    renderGestaoChecklist(assignedIds);
    renderGestaoClientsList(clientsCache);
  } catch (err) {
    showAdminToast(t("admin.failLoad", { message: err.message }));
  } finally {
    if (gestaoCarregarBtn) {
      gestaoCarregarBtn.disabled = false;
      gestaoCarregarBtn.textContent = t("admin.loadClient");
    }
  }
}

if (gestaoCarregarBtn) {
  gestaoCarregarBtn.addEventListener("click", async () => {
    const cnpj = (gestaoClienteInput ? gestaoClienteInput.value.trim() : "");
    await carregarGestaoCliente(cnpj);
  });
}

if (gestaoClienteInput) {
  gestaoClienteInput.addEventListener("input", () => {
    const q = gestaoClienteInput.value.trim().toLowerCase();
    if (!q) {
      renderGestaoClientsList(clientsCache);
      return;
    }
    const filtered = clientsCache.filter((item) => String(item.cnpj || "").toLowerCase().includes(q));
    renderGestaoClientsList(filtered);
  });
}

if (gestaoClientsList) {
  gestaoClientsList.addEventListener("click", async (event) => {
    const btn = event.target.closest(".gestao-client-item");
    if (!btn) return;
    const cnpj = btn.dataset.cnpj || "";
    await carregarGestaoCliente(cnpj);
  });
}

if (gestaoSalvarTestesBtn) {
  gestaoSalvarTestesBtn.addEventListener("click", async () => {
    if (!gestaoCnpjAtual) return;

    const checked = Array.from(
      gestaoTestesChecklist ? gestaoTestesChecklist.querySelectorAll('input[name="gestao_test"]:checked') : []
    ).map((el) => el.value);

    if (checked.length === 0) {
      showAdminToast(t("admin.selectAtLeastOne"));
      return;
    }

    gestaoSalvarTestesBtn.disabled = true;
    gestaoSalvarTestesBtn.textContent = t("common.loading");

    try {
      const resp = await fetch(`/api/admin/clients/${encodeURIComponent(gestaoCnpjAtual)}/tests-produto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_tests: checked, produto_id: gestaoProdutoAtual }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || t("admin.errorSave"));
      showAdminToast(t("admin.testsSaved", { cnpj: gestaoCnpjAtual }));
    } catch (err) {
      showAdminToast(t("admin.fail", { message: err.message }));
    } finally {
      gestaoSalvarTestesBtn.disabled = false;
      gestaoSalvarTestesBtn.textContent = t("admin.saveEnabledTests");
    }
  });
}

if (gestaoResetOnboardingBtn) {
  gestaoResetOnboardingBtn.addEventListener("click", async () => {
    if (!gestaoCnpjAtual) return;

    if (!confirm(t("admin.confirmReset", { cnpj: gestaoCnpjAtual }))) {
      return;
    }

    gestaoResetOnboardingBtn.disabled = true;

    try {
      const resp = await fetch(`/api/admin/clients/${encodeURIComponent(gestaoCnpjAtual)}/reset-onboarding-produto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ produto_id: gestaoProdutoAtual }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || t("admin.errorReset"));
      showAdminToast(t("admin.onboardingReset", { cnpj: gestaoCnpjAtual }));
      renderGestaoChecklist([]);
    } catch (err) {
      showAdminToast(t("admin.fail", { message: err.message }));
    } finally {
      gestaoResetOnboardingBtn.disabled = false;
    }
  });
}

if (gestaoResetTestsBtn) {
  gestaoResetTestsBtn.addEventListener("click", async () => {
    if (!gestaoCnpjAtual) return;

    if (!confirm(t("admin.confirmResetTests", { cnpj: gestaoCnpjAtual }))) {
      return;
    }

    gestaoResetTestsBtn.disabled = true;

    try {
      const resp = await fetch(`/api/admin/clients/${encodeURIComponent(gestaoCnpjAtual)}/reset-tests-produto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ produto_id: gestaoProdutoAtual }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || t("admin.errorResetTests"));
      showAdminToast(t("admin.testsReset", { cnpj: gestaoCnpjAtual }));
      await carregarGestaoCliente(gestaoCnpjAtual);
      loadGestaoClientsList();
      loadClients();
    } catch (err) {
      showAdminToast(t("admin.fail", { message: err.message }));
    } finally {
      gestaoResetTestsBtn.disabled = false;
    }
  });
}

if (gestaoProdutoSelect) {
  gestaoProdutoSelect.addEventListener("change", async () => {
    gestaoProdutoAtual = String(gestaoProdutoSelect.value || "01").padStart(2, "0");
    if (gestaoCnpjAtual) {
      await carregarGestaoCliente(gestaoCnpjAtual);
    }
  });
}

window.addEventListener("app-language-changed", () => {
  renderClientsTable(clientsCache);
  if (gestaoSalvarTestesBtn && !gestaoSalvarTestesBtn.disabled) {
    gestaoSalvarTestesBtn.textContent = t("admin.saveEnabledTests");
  }
  if (gestaoCarregarBtn && !gestaoCarregarBtn.disabled) {
    gestaoCarregarBtn.textContent = t("admin.loadClient");
  }
  renderGestaoClientsList(clientsCache);
});

// =====================================================================
// Funções para gerenciar seleção de modo (Manual vs Batch) - Painel Interno
// =====================================================================

/**
 * Seleciona o modo de validação para o painel interno: 'manual', 'batch', ou 'back'
 */
function selectValidationModeInterno(mode) {
  const modePanel = document.getElementById("adminModeSelectionPanel");
  const batchPanel = document.getElementById("adminBatchValidationPanel");
  const manualPanel = document.getElementById("adminManualValidationPanel");
  
  if (mode === "back") {
    // Volta para o painel de seleção de modo
    if (batchPanel) batchPanel.classList.add("hidden");
    if (manualPanel) manualPanel.classList.add("hidden");
    if (modePanel) modePanel.classList.remove("hidden");
    return;
  }
  
  // Esconde o painel de seleção de modo
  if (modePanel) modePanel.classList.add("hidden");
  
  if (mode === "manual") {
    // Mostra painel de validação manual
    if (manualPanel) manualPanel.classList.remove("hidden");
  } else if (mode === "batch") {
    // Mostra painel de validação em batch
    if (batchPanel) batchPanel.classList.remove("hidden");
    
    // Carrega lista de produtos para batch
    loadProductsForBatch();
  }
}

/**
 * Volta para a aba de validador inicial
 */
function backToValidatorTabs() {
  const modePanel = document.getElementById("adminModeSelectionPanel");
  if (modePanel) modePanel.classList.remove("hidden");
}

/**
 * Carrega lista de produtos para o seletor de batch do painel interno
 */
function loadProductsForBatch() {
  const productSelect = document.getElementById("batchProductSelectInterno");
  if (!productSelect) return;
  
  fetch("/api/produtos")
    .then(res => res.json())
    .then(data => {
      productSelect.innerHTML = '<option value="">Selecione um produto</option>';
      if (Array.isArray(data)) {
        data.forEach(prod => {
          const opt = document.createElement("option");
          opt.value = prod.id;
          opt.textContent = prod.nome;
          productSelect.appendChild(opt);
        });
      }
    })
    .catch(err => console.error("Erro ao carregar produtos:", err));
}

/**
 * Inicializa o seletor de modo do validador
 */
function initializeValidatorMode() {
  const modePanel = document.getElementById("adminModeSelectionPanel");
  const manualPanel = document.getElementById("adminManualValidationPanel");
  const batchPanel = document.getElementById("adminBatchValidationPanel");
  
  if (modePanel && manualPanel && batchPanel) {
    modePanel.classList.remove("hidden");
    manualPanel.classList.add("hidden");
    batchPanel.classList.add("hidden");
  }
}

/**
 * Valida roteiro em batch no painel interno
 */
document.addEventListener("DOMContentLoaded", () => {
  const internoBatchForm = document.getElementById("internoBatchValidationForm");
  if (internoBatchForm) {
    internoBatchForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      
      const fileInput = document.getElementById("batchRoteiroFileInterno");
      const productSelect = document.getElementById("batchProductSelectInterno");
      const dateInput = document.getElementById("batchDataLogInterno");
      
      if (!fileInput.files.length) {
        showAdminToast("Selecione um arquivo roteiro");
        return;
      }
      
      if (!productSelect.value) {
        showAdminToast("Selecione um produto");
        return;
      }
      
      if (!dateInput.value) {
        showAdminToast("Selecione uma data");
        return;
      }
      
      const formData = new FormData();
      formData.append("roteiro_file", fileInput.files[0]);
      formData.append("produto_id", productSelect.value);
      formData.append("data_log", dateInput.value);
      
      const submitBtn = document.getElementById("internoSubmitBtn");
      submitBtn.disabled = true;
      submitBtn.textContent = "Processando...";
      
      try {
        const response = await fetch("/api/validar-roteiro-cliente-batch", {
          method: "POST",
          body: formData
        });
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.message || "Erro ao validar roteiro");
        }
        
        const result = await response.json();
        showAdminToast("Roteiro validado com sucesso!");
        
        // Volta para modo de seleção após sucesso
        setTimeout(() => {
          selectValidationModeInterno("back");
        }, 2000);
      } catch (err) {
        showAdminToast("Erro: " + err.message);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Validar Roteiro em Batch";
      }
    });
  }
});
