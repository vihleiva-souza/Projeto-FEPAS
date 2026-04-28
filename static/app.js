const testSelect = document.getElementById("testSelect");
const logSelect = document.getElementById("logSelect");
const refreshLogsBtn = document.getElementById("refreshLogsBtn");
const goalBox = document.getElementById("goalBox");
const form = document.getElementById("validateForm");
const submitBtn = document.getElementById("submitBtn");
const resultPanel = document.getElementById("resultPanel");
const approvedPanel = document.getElementById("approvedPanel");
const approvedTitle = document.getElementById("approvedTitle");
const approvedMessage = document.getElementById("approvedMessage");
const downloadEvidenceBtn = document.getElementById("downloadEvidenceBtn");
const overallStatus = document.getElementById("overallStatus");
const statusChip = document.getElementById("statusChip");
const resultGoalText = document.getElementById("resultGoalText");
const legsSummaryChips = document.getElementById("legsSummaryChips");
const stepsList = document.getElementById("stepsList");
const legsTableBody = document.getElementById("legsTableBody");
const legsMtiFilter = document.getElementById("legsMtiFilter");
const legsStatusFilter = document.getElementById("legsStatusFilter");
const legsSearchFilter = document.getElementById("legsSearchFilter");
const legsObjectiveOnly = document.getElementById("legsObjectiveOnly");
const legsWithErrorsOnly = document.getElementById("legsWithErrorsOnly");
const legsCounter = document.getElementById("legsCounter");
const legDetailPanel = document.getElementById("legDetailPanel");
const legDetailTitle = document.getElementById("legDetailTitle");
const legDetailMeta = document.getElementById("legDetailMeta");
const isoViewerContent = document.getElementById("isoViewerContent");
const isoRawContent = document.getElementById("isoRawContent");
const legErrors = document.getElementById("legErrors");
const legWarnings = document.getElementById("legWarnings");

let testsCache = [];
let logsCache = [];
let legsCache = [];
let filteredLegsCache = [];
let selectedLegKey = "";
let evidenceCache = null;

function normalizeTestLabel(test) {
  const normalized = { ...(test || {}) };
  const id = String(normalized.id || "");
  const nome = String(normalized.nome || "");
  if (id === "13" && nome && !/\(PCT\)/i.test(nome)) {
    normalized.nome = `${nome} (PCT)`;
  }
  return normalized;
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatBytes(bytes) {
  const size = Number(bytes || 0);
  if (!Number.isFinite(size) || size <= 0) {
    return "0 B";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
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

function buildEvidenceContentFallback(data) {
  const teste = data.teste || {};
  const resumo = data.resumo || {};
  const pernas = Array.isArray(data.pernas) ? data.pernas : [];
  const passos = Array.isArray(data.passos_objetivo) ? data.passos_objetivo : [];
  const motivos = Array.isArray(data.motivos_status_geral) ? data.motivos_status_geral : [];

  const lines = [];
  lines.push("EVIDENCIA DE HOMOLOGACAO ISO 8583");
  lines.push("=".repeat(80));
  lines.push(`Teste: ${String(teste.id || "").padStart(2, "0")} - ${teste.nome || ""}`);
  lines.push(`Status geral: ${data.status || "-"}`);
  lines.push(`Objetivo esperado: ${teste.objetivo_esperado || "-"}`);
  lines.push("");
  lines.push("RESUMO");
  lines.push("-".repeat(80));
  lines.push(`Total de pernas: ${Number(resumo.total_pernas || 0)}`);
  lines.push(`Pernas aprovadas: ${Number(resumo.pernas_aprovadas || 0)}`);
  lines.push(`Pernas reprovadas: ${Number(resumo.pernas_negadas || 0)}`);
  lines.push(`Pernas nao aplicam: ${Number(resumo.pernas_nao_aplicam || 0)}`);

  if (motivos.length > 0) {
    lines.push("");
    lines.push("MOTIVOS STATUS GERAL");
    lines.push("-".repeat(80));
    motivos.forEach((motivo, idx) => lines.push(`${idx + 1}. ${motivo}`));
  }

  if (passos.length > 0) {
    lines.push("");
    lines.push("PASSOS DO OBJETIVO");
    lines.push("-".repeat(80));
    passos.forEach((passo) => {
      lines.push(`${passo.ordem || "-"} | ${passo.label || "-"} | ${passo.status || "-"} | ${passo.motivo || "-"}`);
    });
  }

  lines.push("");
  lines.push("TROCA DE MENSAGENS ISO");
  lines.push("-".repeat(80));
  pernas.forEach((leg, index) => {
    lines.push(`PERNA ${index + 1}`);
    lines.push(`Ordem no log: ${leg.ordem_log || "-"}`);
    lines.push(`MTI: ${leg.mti || "-"}`);
    lines.push(`DE03: ${leg.de03 || "-"}`);
    lines.push(`DE11: ${leg.de11 || "-"}`);
    lines.push(`DE41: ${leg.de41 || "-"}`);
    lines.push(`Status: ${leg.status || "-"}`);
    lines.push(`Motivo: ${leg.motivo || "-"}`);
    lines.push("ISO BRUTO:");
    lines.push((leg.raw_iso || "").trim() || "(sem ISO bruto)");
    lines.push("ISO FORMATADO:");
    lines.push((leg.iso_formatado || "").trim() || "(sem ISO formatado)");
    lines.push("-".repeat(80));
  });

  return lines.join("\n");
}

function buildEvidenceFileName(data) {
  const evid = data.evidencia || {};
  if (evid.file_name) {
    return String(evid.file_name);
  }
  const teste = data.teste || {};
  const testId = String(teste.id || "00").padStart(2, "0");
  return `evidencia_teste_${testId}.txt`;
}

function setupApprovedPanel(data) {
  const isApproved = String(data.status || "") === "APROVADO";
  if (!approvedPanel) {
    return;
  }

  if (!isApproved) {
    approvedPanel.classList.add("hidden");
    evidenceCache = null;
    return;
  }

  const teste = normalizeTestLabel(data.teste || {});
  if (approvedTitle) {
    approvedTitle.textContent = `Teste ${teste.id || "--"} Aprovado`;
  }
  if (approvedMessage) {
    approvedMessage.textContent = "Validacao concluida com sucesso. Baixe a evidencia completa da troca de mensagens ISO em .txt.";
  }

  const evid = data.evidencia || {};
  evidenceCache = {
    fileName: buildEvidenceFileName(data),
    content: (evid.content && String(evid.content)) || buildEvidenceContentFallback(data),
  };

  approvedPanel.classList.remove("hidden");
  approvedPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

if (downloadEvidenceBtn) {
  downloadEvidenceBtn.addEventListener("click", () => {
    if (!evidenceCache || !evidenceCache.content) {
      showToast("Evidencia indisponivel para download.");
      return;
    }

    const blob = new Blob([evidenceCache.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = evidenceCache.fileName || "evidencia.txt";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  });
}

function setStatusVisual(status) {
  const ok = status === "APROVADO";
  statusChip.textContent = status;
  statusChip.style.background = ok ? "#d5f1e5" : "#f6dada";
  statusChip.style.color = ok ? "#0f6e4f" : "#9e2424";
}

function renderResultSummary(data) {
  const t = data.teste || {};
  const r = data.resumo || {};

  resultGoalText.textContent = t.objetivo_esperado || "-";

  const aprovadas = Number(r.pernas_aprovadas ?? 0);
  const negadas = Number(r.pernas_negadas ?? 0);
  const naoAplicam = Number(r.pernas_nao_aplicam ?? 0);
  const total = Number(r.total_pernas ?? 0);

  legsSummaryChips.innerHTML = [
    aprovadas > 0 ? `<span class="legs-chip chip-ok">✓ ${aprovadas} Aprovada${aprovadas !== 1 ? "s" : ""}</span>` : "",
    negadas > 0 ? `<span class="legs-chip chip-bad">✗ ${negadas} Reprovada${negadas !== 1 ? "s" : ""}</span>` : "",
    naoAplicam > 0 ? `<span class="legs-chip chip-na">– ${naoAplicam} N\u00e3o aplica</span>` : "",
    `<span class="legs-chip chip-total">${total} total</span>`,
  ].filter(Boolean).join("");
}

function renderSteps(steps) {
  if (!Array.isArray(steps) || steps.length === 0) {
    stepsList.innerHTML = '<div class="step bad">Nenhum passo configurado para este teste.</div>';
    return;
  }

  stepsList.innerHTML = steps
    .map((s) => {
      const isNa = s.aprovado === null || String(s.status || "").toLowerCase() === "não aplica";
      const ok = !!s.aprovado;
      const stepClass = isNa ? "na" : (ok ? "ok" : "bad");
      return `
        <article class="step ${stepClass}">
          <strong>${escapeHtml(s.ordem)}. ${escapeHtml(s.label)}</strong>
          <div>${escapeHtml(s.status)} - ${escapeHtml(s.motivo)}</div>
        </article>
      `;
    })
    .join("");
}

function renderLegFilterOptions(legs) {
  const mtis = Array.from(new Set((legs || []).map((leg) => String(leg.mti || "")).filter(Boolean))).sort();
  const current = legsMtiFilter.value;
  legsMtiFilter.innerHTML = [
    '<option value="">Todos</option>',
    ...mtis.map((mti) => `<option value="${escapeHtml(mti)}"${mti === current ? ' selected' : ''}>${escapeHtml(mti)}</option>`),
  ].join("");
}

function applyLegFilters() {
  const mtiValue = String(legsMtiFilter.value || "");
  const statusValue = String(legsStatusFilter.value || "");
  const searchValue = String(legsSearchFilter.value || "").trim().toLowerCase();
  const onlyObjective = !!legsObjectiveOnly.checked;
  const onlyWithErrors = !!legsWithErrorsOnly.checked;

  filteredLegsCache = legsCache.filter((leg) => {
    if (mtiValue && String(leg.mti || "") !== mtiValue) {
      return false;
    }
    if (statusValue && String(leg.status || "") !== statusValue) {
      return false;
    }
    if (onlyObjective && (!Array.isArray(leg.objetivo_refs) || leg.objetivo_refs.length === 0)) {
      return false;
    }
    if (onlyWithErrors && (!Array.isArray(leg.erros) || leg.erros.length === 0)) {
      return false;
    }
    if (!searchValue) {
      return true;
    }

    const haystack = [
      leg.mti,
      leg.de03,
      leg.de11,
      leg.de41,
      leg.status,
      leg.motivo,
      ...(leg.objetivo_refs || []),
      ...(leg.erros || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(searchValue);
  });

  renderLegRows(filteredLegsCache);
}

function renderLegRows(legs) {
  legsCounter.textContent = `${legs.length} exibidas`;

  if (!Array.isArray(legs) || legs.length === 0) {
    legsTableBody.innerHTML = '<tr><td colspan="8">Nenhuma perna encontrada para os filtros atuais.</td></tr>';
    clearLegDetail();
    return;
  }

  const legKey = (leg) => [
    String(leg.header_line || ""),
    String(leg.ordem_log || ""),
    String(leg.mti || ""),
    String(leg.de11 || ""),
    String(leg.de41 || ""),
  ].join("|");

  legsTableBody.innerHTML = legs
    .map((leg, index) => {
      const isOk = leg.aprovado === true;
      const isBad = leg.aprovado === false;
      const refs = Array.isArray(leg.objetivo_refs) && leg.objetivo_refs.length ? leg.objetivo_refs.join(", ") : "-";
      const rowClass = isOk ? "leg-ok" : (isBad ? "leg-bad" : "leg-na");
      const tagClass = isOk ? "ok" : (isBad ? "bad" : "na");
      const currentKey = legKey(leg);
      const activeClass = selectedLegKey && selectedLegKey === currentKey ? " active" : "";
      return `
        <tr class="${rowClass}${activeClass}" data-leg-index="${index}">
          <td>${escapeHtml(leg.ordem_log)}</td>
          <td>${escapeHtml(leg.mti || "-")}</td>
          <td>${escapeHtml(leg.de03 || "-")}</td>
          <td>${escapeHtml(leg.de11 || "-")}</td>
          <td>${escapeHtml(leg.de41 || "-")}</td>
          <td><span class="tag ${tagClass}">${escapeHtml(leg.status || "-")}</span></td>
          <td>${escapeHtml(leg.motivo || "-")}</td>
          <td>${escapeHtml(refs)}</td>
        </tr>
      `;
    })
    .join("");

  const hasActiveInFilter = legs.some((leg) => legKey(leg) === selectedLegKey);
  if (!hasActiveInFilter) {
    clearLegDetail();
  }
}

function legStructuredList(items, emptyText) {
  if (!Array.isArray(items) || items.length === 0) {
    return `<p class="empty-state">${escapeHtml(emptyText)}</p>`;
  }

  return items
    .map((item) => `<div class="structured-entry error"><div class="structured-message">${escapeHtml(item)}</div></div>`)
    .join("");
}

function clearLegDetail() {
  selectedLegKey = "";
  if (legDetailPanel) {
    legDetailPanel.classList.add("hidden");
  }
}

function showLegDetail(leg) {
  if (!leg) {
    clearLegDetail();
    return;
  }

  const currentKey = [
    String(leg.header_line || ""),
    String(leg.ordem_log || ""),
    String(leg.mti || ""),
    String(leg.de11 || ""),
    String(leg.de41 || ""),
  ].join("|");
  selectedLegKey = currentKey;

  if (legDetailPanel) {
    legDetailPanel.classList.remove("hidden");
  }

  if (legDetailTitle) {
    legDetailTitle.textContent = `Perna ${leg.ordem_log || "-"} - MTI ${leg.mti || "-"}`;
  }
  if (legDetailMeta) {
    legDetailMeta.textContent = `DE03 ${leg.de03 || "-"} | DE11 ${leg.de11 || "-"} | DE41 ${leg.de41 || "-"} | Status ${leg.status || "-"}`;
  }
  if (isoViewerContent) {
    isoViewerContent.textContent = leg.iso_formatado || "Sem ISO formatado para esta perna.";
  }
  if (isoRawContent) {
    isoRawContent.textContent = leg.raw_iso || "Sem ISO bruto disponível para esta perna.";
  }
  if (legErrors) {
    legErrors.innerHTML = legStructuredList(leg.erros || [], "Sem erros para exibir.");
  }
  if (legWarnings) {
    legWarnings.innerHTML = legStructuredList(leg.avisos || [], "Sem avisos para exibir.");
  }

  renderLegRows(filteredLegsCache);
}

function renderLegs(legs) {
  legsCache = Array.isArray(legs) ? legs : [];
  clearLegDetail();
  renderLegFilterOptions(legsCache);
  applyLegFilters();
}

legsTableBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-leg-index]");
  if (!row) {
    return;
  }

  const idx = Number(row.dataset.legIndex || -1);
  if (!Number.isInteger(idx) || idx < 0 || idx >= filteredLegsCache.length) {
    return;
  }

  showLegDetail(filteredLegsCache[idx]);
});

async function loadTests() {
  const resp = await fetch("/api/tests");
  const data = await resp.json();
  testsCache = (data.tests || []).map(normalizeTestLabel);

  const options = ['<option value="">Selecione...</option>'];
  for (const t of testsCache) {
    options.push(`<option value="${escapeHtml(t.id)}">${escapeHtml(t.id)} - ${escapeHtml(t.nome)}</option>`);
  }
  testSelect.innerHTML = options.join("");
}

async function loadLogs() {
  const prev = logSelect.value;
  logSelect.innerHTML = '<option value="">Carregando...</option>';
  try {
    const resp = await fetch("/api/logs");
    const data = await resp.json();
    logsCache = data.logs || [];

    if (!Array.isArray(logsCache) || logsCache.length === 0) {
      logSelect.innerHTML = '<option value="">Nenhum log encontrado</option>';
      return;
    }

    const options = ['<option value="">Selecione o log...</option>'];
    for (const item of logsCache) {
      const name = typeof item === "string" ? item : item.name;
      options.push(`<option value="${escapeHtml(name)}"${name === prev ? ' selected' : ''}>${escapeHtml(name)}</option>`);
    }
    logSelect.innerHTML = options.join("");
  } catch (err) {
    logSelect.innerHTML = '<option value="">Falha ao carregar logs</option>';
  }
}

refreshLogsBtn.addEventListener("click", () => loadLogs());

testSelect.addEventListener("change", () => {
  const testId = testSelect.value;
  const t = testsCache.find((x) => x.id === testId);
  goalBox.textContent = t
    ? `Objetivo esperado: ${t.objetivo_esperado}`
    : "Selecione um teste para ver o objetivo esperado.";
});

legsMtiFilter.addEventListener("change", applyLegFilters);
legsStatusFilter.addEventListener("change", applyLegFilters);
legsSearchFilter.addEventListener("input", applyLegFilters);
legsObjectiveOnly.addEventListener("change", applyLegFilters);
legsWithErrorsOnly.addEventListener("change", applyLegFilters);

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();

  submitBtn.disabled = true;
  submitBtn.classList.add("loading");
  submitBtn.textContent = "Validando...";

  try {
    const formData = new FormData(form);
    const resp = await fetch("/api/validate", {
      method: "POST",
      body: formData,
    });

    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Falha na validacao");
    }

    resultPanel.classList.remove("hidden");
    const displayTest = normalizeTestLabel(data.teste || {});
    overallStatus.textContent = `${data.status} - ${displayTest.id || ""} ${displayTest.nome || ""}`;
    setStatusVisual(data.status);
    renderResultSummary(data);
    renderSteps(data.passos_objetivo || []);
    renderLegs(data.pernas || []);
    setupApprovedPanel(data);
    resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    const msg = err instanceof Error && err.message
      ? err.message
      : "Não foi possível validar o log. Verifique a seleção e tente novamente.";
    showToast(msg);
    if (approvedPanel) {
      approvedPanel.classList.add("hidden");
    }
    evidenceCache = null;
  } finally {
    submitBtn.disabled = false;
    submitBtn.classList.remove("loading");
    submitBtn.textContent = "Validar Log";
  }
});

loadTests().catch((err) => {
  testSelect.innerHTML = '<option value="">Falha ao carregar testes</option>';
  goalBox.textContent = `Erro ao carregar testes: ${err.message}`;
});
loadLogs().catch(() => {
  logSelect.innerHTML = '<option value="">Falha ao carregar logs</option>';
});
