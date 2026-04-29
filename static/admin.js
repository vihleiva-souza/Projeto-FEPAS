// =====================================================================
// admin.js – lógica das abas e das telas de clientes/gestão (Stage 2)
// =====================================================================

// ---- Abas ----
const adminTabs = document.querySelectorAll(".admin-tab");
const adminPanels = document.querySelectorAll(".admin-tab-panel");

adminTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    adminTabs.forEach((t) => t.classList.remove("active"));
    adminPanels.forEach((p) => p.classList.add("hidden"));
    tab.classList.add("active");
    const target = document.getElementById(tab.dataset.tab);
    if (target) {
      target.classList.remove("hidden");
    }

    if (tab.dataset.tab === "tab-clientes") {
      loadClients();
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
  return String(status || "-")
    .replace(/_/g, " ")
    .toUpperCase();
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
    clientsTableBody.innerHTML = '<tr><td colspan="7">Carregando...</td></tr>';
  }
  try {
    const resp = await fetch("/api/admin/clients");
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Erro ao listar clientes.");
    clientsCache = data.clients || [];
    renderClientsTable(clientsCache);
  } catch (err) {
    if (clientsTableBody) {
      clientsTableBody.innerHTML = `<tr><td colspan="7">Falha: ${escapeAdm(err.message)}</td></tr>`;
    }
  }
}

function renderClientsTable(clients) {
  if (!clientsTableBody) return;

  if (!clients || clients.length === 0) {
    clientsTableBody.innerHTML = '<tr><td colspan="7">Nenhum cliente encontrado.</td></tr>';
    return;
  }

  clientsTableBody.innerHTML = clients
    .map((item) => {
      const onbStatus = item.onboarding_completed
        ? '<span class="tag ok">Concluido</span>'
        : '<span class="tag na">Pendente</span>';
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
  clientDetailTableBody.innerHTML = '<tr><td colspan="6">Carregando...</td></tr>';
  clientDetailPanel.scrollIntoView({ behavior: "smooth", block: "start" });

  try {
    const resp = await fetch(`/api/client/progress?cnpj=${encodeURIComponent(cnpj)}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Erro ao carregar detalhe.");

    const tests = Array.isArray(data.tests) ? data.tests : [];
    if (tests.length === 0) {
      clientDetailTableBody.innerHTML = '<tr><td colspan="6">Nenhum teste realizado ainda.</td></tr>';
      return;
    }

    clientDetailTableBody.innerHTML = tests
      .map((item) => `
        <tr>
          <td>${escapeAdm(item.teste_id)} - ${escapeAdm(item.teste_nome || "")}</td>
          <td>${escapeAdm(formatInternalStatus(item.status))}</td>
          <td>${escapeAdm(item.attempts_total)}</td>
          <td>${escapeAdm(item.attempts_until_approval ?? "-")}</td>
          <td>${escapeAdm(Number(item.percentual_sucesso || 0).toFixed(2))}%</td>
          <td>${escapeAdm(item.last_result || "-")}</td>
        </tr>
      `)
      .join("");
  } catch (err) {
    clientDetailTableBody.innerHTML = `<tr><td colspan="6">Falha: ${escapeAdm(err.message)}</td></tr>`;
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
const gestaoClientePanel = document.getElementById("gestaoClientePanel");
const gestaoClienteLabel = document.getElementById("gestaoClienteLabel");
const gestaoTestesChecklist = document.getElementById("gestaoTestesChecklist");
const gestaoSalvarTestesBtn = document.getElementById("gestaoSalvarTestesBtn");
const gestaoResetOnboardingBtn = document.getElementById("gestaoResetOnboardingBtn");

let gestaoCnpjAtual = "";
let gestaoTestesCache = [];

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
      return `
        <label class="step" style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
          <input type="checkbox" name="gestao_test" value="${escapeAdm(tid)}" ${checked} />
          <span><strong>${escapeAdm(tid)} - ${escapeAdm(item.nome || "")}</strong><br>
          <small style="color:#4a5f7d;">${escapeAdm(item.objetivo_esperado || "")}</small></span>
        </label>
      `;
    })
    .join("");
}

if (gestaoCarregarBtn) {
  gestaoCarregarBtn.addEventListener("click", async () => {
    const cnpj = (gestaoClienteInput ? gestaoClienteInput.value.trim() : "");
    if (!cnpj) {
      showAdminToast("Informe o CNPJ do cliente.");
      return;
    }

    gestaoCarregarBtn.disabled = true;
    gestaoCarregarBtn.textContent = "Carregando...";

    try {
      await loadAllTestsForGestao();
      const resp = await fetch(`/api/client/progress?cnpj=${encodeURIComponent(cnpj)}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Erro ao carregar cliente.");

      gestaoCnpjAtual = cnpj;
      if (gestaoClienteLabel) gestaoClienteLabel.textContent = cnpj;
      if (gestaoClientePanel) gestaoClientePanel.classList.remove("hidden");

      const assignedIds = (data.assigned_tests || []).map((item) => String(item.id || "")).filter(Boolean);
      renderGestaoChecklist(assignedIds);
    } catch (err) {
      showAdminToast(`Falha ao carregar: ${err.message}`);
    } finally {
      gestaoCarregarBtn.disabled = false;
      gestaoCarregarBtn.textContent = "Carregar cliente";
    }
  });
}

if (gestaoSalvarTestesBtn) {
  gestaoSalvarTestesBtn.addEventListener("click", async () => {
    if (!gestaoCnpjAtual) return;

    const checked = Array.from(
      gestaoTestesChecklist ? gestaoTestesChecklist.querySelectorAll('input[name="gestao_test"]:checked') : []
    ).map((el) => el.value);

    if (checked.length === 0) {
      showAdminToast("Selecione ao menos um teste.");
      return;
    }

    gestaoSalvarTestesBtn.disabled = true;
    gestaoSalvarTestesBtn.textContent = "Salvando...";

    try {
      const resp = await fetch(`/api/admin/clients/${encodeURIComponent(gestaoCnpjAtual)}/tests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_tests: checked }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Erro ao salvar.");
      showAdminToast(`Testes salvos para ${gestaoCnpjAtual}.`);
    } catch (err) {
      showAdminToast(`Falha: ${err.message}`);
    } finally {
      gestaoSalvarTestesBtn.disabled = false;
      gestaoSalvarTestesBtn.textContent = "Salvar testes habilitados";
    }
  });
}

if (gestaoResetOnboardingBtn) {
  gestaoResetOnboardingBtn.addEventListener("click", async () => {
    if (!gestaoCnpjAtual) return;

    if (!confirm(`Confirmar reset de onboarding para ${gestaoCnpjAtual}? O cliente precisará selecionar os testes novamente no próximo acesso.`)) {
      return;
    }

    gestaoResetOnboardingBtn.disabled = true;

    try {
      const resp = await fetch(`/api/admin/clients/${encodeURIComponent(gestaoCnpjAtual)}/reset-onboarding`, {
        method: "POST",
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "Erro ao resetar.");
      showAdminToast(`Onboarding do cliente ${gestaoCnpjAtual} foi resetado.`);
      renderGestaoChecklist([]);
    } catch (err) {
      showAdminToast(`Falha: ${err.message}`);
    } finally {
      gestaoResetOnboardingBtn.disabled = false;
    }
  });
}
