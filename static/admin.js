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

async function loadClients() {
  if (clientsTableBody) {
    clientsTableBody.innerHTML = `<tr><td colspan="7">${escapeAdm(t("admin.loadingClients"))}</td></tr>`;
  }
  try {
    const resp = await fetch("/api/admin/clients");
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
    const resp = await fetch(`/api/client/progress?cnpj=${encodeURIComponent(cnpj)}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || t("admin.errorLoadDetail"));

    const tests = Array.isArray(data.tests) ? data.tests : [];
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
          <td>${escapeAdm(item.teste_id)} - ${escapeAdm(testName)}</td>
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

let gestaoCnpjAtual = "";
let gestaoTestesCache = [];

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
    const resp = await fetch("/api/admin/clients");
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

async function loadAllTestsForGestao() {
  try {
    const resp = await fetch("/api/tests");
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
    await loadAllTestsForGestao();
    const resp = await fetch(`/api/client/progress?cnpj=${encodeURIComponent(clientId)}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || t("admin.errorLoadClient"));

    gestaoCnpjAtual = clientId;
    if (gestaoClienteLabel) gestaoClienteLabel.textContent = clientId;
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
      const resp = await fetch(`/api/admin/clients/${encodeURIComponent(gestaoCnpjAtual)}/tests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_tests: checked }),
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
      const resp = await fetch(`/api/admin/clients/${encodeURIComponent(gestaoCnpjAtual)}/reset-onboarding`, {
        method: "POST",
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
      const resp = await fetch(`/api/admin/clients/${encodeURIComponent(gestaoCnpjAtual)}/reset-tests`, {
        method: "POST",
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
