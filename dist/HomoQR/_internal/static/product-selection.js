// =====================================================================
// product-selection.js – Seleção de Produto no Portal do Cliente
// =====================================================================

const PRODUCT_STORAGE_KEY = "homolog_selected_product";
let selectedProductId = localStorage.getItem(PRODUCT_STORAGE_KEY) || "";

/**
 * Seleciona um produto e mostra o formulário de acesso apropriado
 */
function selectProduct(productId, event) {
  if (event) {
    event.preventDefault();
  }

  selectedProductId = productId;
  localStorage.setItem(PRODUCT_STORAGE_KEY, productId);

  // Esconde a seleção de produto
  const productPanel = document.getElementById("clientProductSelectionPanel");
  if (productPanel) {
    productPanel.classList.add("hidden");
  }

  // Mostra o painel de acesso
  const accessPanel = document.getElementById("clientAccessPanel");
  if (accessPanel) {
    accessPanel.classList.remove("hidden");
  }

  // Mostra/esconde os campos apropriados
  updateAccessFormForProduct(productId);

  // Pré-carrega os testes do produto selecionado para evitar inconsistência de fluxo.
  if (typeof loadTests === "function") {
    loadTests(productId).catch(() => {
      // Falha de preload não deve impedir o usuário de avançar no fluxo.
    });
  }
}

/**
 * Volta para a tela de seleção de produto
 */
function backToProductSelection() {
  selectedProductId = "";
  localStorage.removeItem(PRODUCT_STORAGE_KEY);

  const productPanel = document.getElementById("clientProductSelectionPanel");
  const accessPanel = document.getElementById("clientAccessPanel");
  const onboardingPanel = document.getElementById("clientOnboardingPanel");
  const workspacePanel = document.getElementById("clientWorkspacePanel");
  const progressPanel = document.getElementById("clientProgressPanel");
  const resultPanel = document.getElementById("clientResultPanel");

  // Esconde todas as seções de acesso
  [accessPanel, onboardingPanel, workspacePanel, progressPanel, resultPanel].forEach((p) => {
    if (p) p.classList.add("hidden");
  });

  // Mostra apenas a seleção de produto
  if (productPanel) {
    productPanel.classList.remove("hidden");
  }

  // Limpa os campos
  const cnpjInput = document.getElementById("cnpjInput");
  const cnpjInputAut = document.getElementById("cnpjInputAutorizador");
  if (cnpjInput) cnpjInput.value = "";
  if (cnpjInputAut) cnpjInputAut.value = "";
}

/**
 * Atualiza o formulário de acesso para mostrar os campos corretos baseado no produto
 */
function updateAccessFormForProduct(productId) {
  const qrPagoFields = document.getElementById("qrPagoFields");
  const autorizadorFields = document.getElementById("autorizadorFields");
  const cnpjInput = document.getElementById("cnpjInput");
  const cnpjInputAut = document.getElementById("cnpjInputAutorizador");

  if (!qrPagoFields || !autorizadorFields) return;

  if (productId === "01") {
    // QR Pago - mostra CNPJ/CUIT
    qrPagoFields.style.display = "block";
    autorizadorFields.style.display = "none";
    if (cnpjInput) cnpjInput.required = true;
    if (cnpjInputAut) cnpjInputAut.required = false;
  } else if (productId === "02") {
    // Autorizador - mostra apenas CNPJ
    qrPagoFields.style.display = "none";
    autorizadorFields.style.display = "block";
    if (cnpjInput) cnpjInput.required = false;
    if (cnpjInputAut) cnpjInputAut.required = true;
  }
}

/**
 * Obtém o CNPJ do input apropriado baseado no produto selecionado
 */
function getCnpjFromForm() {
  if (selectedProductId === "02") {
    // Autorizador
    const input = document.getElementById("cnpjInputAutorizador");
    return input ? input.value : "";
  } else {
    // QR Pago (ou padrão)
    const input = document.getElementById("cnpjInput");
    return input ? input.value : "";
  }
}

/**
 * Inicializa a interface de seleção de produto ao carregar
 */
function initializeProductSelection() {
  // Se um produto foi selecionado antes, volta para aquela seleção
  if (!selectedProductId) {
    // Mostra a seleção de produto
    const productPanel = document.getElementById("clientProductSelectionPanel");
    if (productPanel) {
      productPanel.classList.remove("hidden");
    }

    // Esconde outros painéis
    const panels = ["clientAccessPanel", "clientOnboardingPanel", "clientWorkspacePanel", "clientProgressPanel", "clientResultPanel"];
    panels.forEach((panelId) => {
      const panel = document.getElementById(panelId);
      if (panel) panel.classList.add("hidden");
    });
  }
}

// Inicializa quando a página carrega
document.addEventListener("DOMContentLoaded", () => {
  initializeProductSelection();
});
