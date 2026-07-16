// =====================================================================
// product-selection.js – Seleção de Produto no Portal do Cliente
// =====================================================================

const PRODUCT_STORAGE_KEY = "homolog_selected_product";
let selectedProductId = localStorage.getItem(PRODUCT_STORAGE_KEY) || "";

// Global error handler
window.addEventListener("error", function(e) {
  console.error("[GLOBAL ERROR]", e.error, e.message);
});

/**
 * Seleciona um produto e mostra o painel de identificação
 */
function selectProduct(productId, event) {
  try {
    console.log("[selectProduct] START with productId:", productId);
    
    if (event) {
      event.preventDefault();
      event.stopPropagation();
      console.log("[selectProduct] Event prevented");
    }

    console.log("[selectProduct] Called with:", productId);

    // Mapear IDs simples para os nomes descritivos
    let normalizedId = String(productId || "").trim();
    if (normalizedId === "01" || normalizedId === "1") {
      normalizedId = "01_QRCARDSE";
    } else if (normalizedId === "02" || normalizedId === "2") {
      normalizedId = "02_AutorizadorCARDSE";
    }
    // Se já vem com o nome descritivo, usa como está

    selectedProductId = normalizedId;
    localStorage.setItem(PRODUCT_STORAGE_KEY, selectedProductId);
    console.log("[selectProduct] Set selectedProductId to:", selectedProductId);

    // Atualiza título e label do campo de identificação conforme o produto
    const title = document.getElementById("accessPanelTitle");
    const label = document.getElementById("accessIdentifierLabel");
    const input = document.getElementById("cnpjInput");

    console.log("[selectProduct] Got DOM elements - title:", title, "label:", label, "input:", input);

    if (selectedProductId === "01_QRCARDSE") {
      if (title) title.textContent = "Identificação QR Pago";
      if (label) label.textContent = "CUIT";
      if (input) input.placeholder = "Informe o CUIT do cliente";
    } else if (selectedProductId === "02_AutorizadorCARDSE") {
      if (title) title.textContent = "Identificação Autorizador";
      if (label) label.textContent = "Código Autorizador";
      if (input) input.placeholder = "Informe o Código Autorizador";
    }

    // Limpa o campo
    if (input) input.value = "";

    // Esconde o painel de produto
    const productPanel = document.getElementById("clientProductSelectionPanel");
    console.log("[selectProduct] productPanel:", productPanel);
    if (productPanel) {
      productPanel.classList.add("hidden");
      console.log("[selectProduct] Added hidden to productPanel");
    }

    // Mostra o painel de identificação
    const accessPanel = document.getElementById("clientAccessPanel");
    console.log("[selectProduct] accessPanel:", accessPanel);
    if (accessPanel) {
      accessPanel.classList.remove("hidden");
      console.log("[selectProduct] Removed hidden from accessPanel");
      if (input) input.focus();
    }
    
    // Atualizar campos de validação conforme o produto selecionado
    updateAccessFormForProduct(selectedProductId);
    
    console.log("[selectProduct] END");
  } catch (err) {
    console.error("[selectProduct] ERROR:", err);
  }
}

/**
 * Volta para o painel de seleção de produto a partir da identificação
 */
function backToProductPanel() {
  const accessPanel = document.getElementById("clientAccessPanel");
  const productPanel = document.getElementById("clientProductSelectionPanel");
  const testPanel = document.getElementById("clientTestSelectionPanel");
  const modePanel = document.getElementById("clientModeSelectionPanel");
  const batchPanel = document.getElementById("clientBatchValidationPanel");
  const workspacePanel = document.getElementById("clientWorkspacePanel");

  [accessPanel, testPanel, modePanel, batchPanel, workspacePanel].forEach((p) => {
    if (p) p.classList.add("hidden");
  });

  if (productPanel) productPanel.classList.remove("hidden");

  selectedProductId = "";
  localStorage.removeItem(PRODUCT_STORAGE_KEY);
}

/**
 * Mantém compatibilidade: backToAccessPanel agora redireciona para o produto
 */
function backToAccessPanel() {
  backToProductPanel();
}

/**
 * Volta para a tela de seleção de produto
 */
function backToProductSelection() {
  const productPanel = document.getElementById("clientProductSelectionPanel");
  const testPanel = document.getElementById("clientTestSelectionPanel");
  const modePanel = document.getElementById("clientModeSelectionPanel");
  const batchPanel = document.getElementById("clientBatchValidationPanel");
  const workspacePanel = document.getElementById("clientWorkspacePanel");

  // Esconde os painéis de teste, modo e batch
  [testPanel, modePanel, batchPanel, workspacePanel].forEach((p) => {
    if (p) p.classList.add("hidden");
  });

  // Mostra o painel de produto
  if (productPanel) {
    productPanel.classList.remove("hidden");
  }
}

/**
 * Volta para a tela de seleção de testes
 */
function backToTestSelection() {
  const testPanel = document.getElementById("clientTestSelectionPanel");
  const modePanel = document.getElementById("clientModeSelectionPanel");
  const batchPanel = document.getElementById("clientBatchValidationPanel");
  const workspacePanel = document.getElementById("clientWorkspacePanel");

  // Esconde os painéis de modo, batch e workspace
  [modePanel, batchPanel, workspacePanel].forEach((p) => {
    if (p) p.classList.add("hidden");
  });

  // Mostra o painel de testes
  if (testPanel) {
    testPanel.classList.remove("hidden");
  }
}

/**
 * Atualiza o formulário de acesso para mostrar os campos corretos baseado no produto
 */
function updateAccessFormForProduct(productId) {
  // Campos DE41 / DE42
  const de41Field = document.getElementById("de41Field");
  const de42Field = document.getElementById("de42Field");
  const de41Input = document.getElementById("de41");
  const de42Input = document.getElementById("de42");
  const comunicacaoTipoField = document.getElementById("comunicacaoTipoField");
  const comunicacaoTipoInput = document.getElementById("comunicacaoTipo");

  if (productId === "01_QRCARDSE") {
    // QR Pago - mostra DE41 (Terminal ID)
    if (de41Field) de41Field.style.display = "block";
    if (de42Field) de42Field.style.display = "none";
    if (de41Input) de41Input.required = true;
    if (de42Input) de42Input.required = false;
    if (comunicacaoTipoField) comunicacaoTipoField.style.display = "none";
    if (comunicacaoTipoInput) comunicacaoTipoInput.required = false;
  } else if (productId === "02_AutorizadorCARDSE") {
    // Autorizador - mostra DE42 (Merchant ID)
    if (de41Field) de41Field.style.display = "none";
    if (de42Field) de42Field.style.display = "block";
    if (de41Input) de41Input.required = false;
    if (de42Input) de42Input.required = true;
    if (comunicacaoTipoField) comunicacaoTipoField.style.display = "block";
    if (comunicacaoTipoInput) comunicacaoTipoInput.required = true;
  }
}

/**
 * Obtém o CNPJ do input apropriado baseado no produto selecionado
 */
function getCnpjFromForm() {
  if (selectedProductId === "02_AutorizadorCARDSE") {
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
 * Carrega os testes disponíveis para um produto e mostra o painel de seleção
 */
async function loadAvailableTests(productId) {
  try {
    // Endpoint correto: /api/produtos/{productId}/tests
    console.log("[loadAvailableTests] Carregando testes para:", productId);
    const response = await fetch(`/api/produtos/${productId}/tests`);
    if (!response.ok) {
      throw new Error(`Erro ao carregar testes: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log("[loadAvailableTests] Resposta da API:", data);
    
    // API retorna "tests" (não "testes")
    const tests = data.tests || data.testes || [];
    console.log("[loadAvailableTests] Testes a popular:", tests);
    populateTestCheckboxes(tests);
    
    // Mostra o painel de seleção de testes
    const testSelectionPanel = document.getElementById("clientTestSelectionPanel");
    if (testSelectionPanel) {
      testSelectionPanel.classList.remove("hidden");
    }
  } catch (error) {
    console.error("Erro ao carregar testes:", error);
    alert(`Erro ao carregar testes disponíveis: ${error.message}`);
    backToProductSelection();
  }
}

/**
 * Popula o container de testes com checkboxes
 */
function populateTestCheckboxes(testes) {
  const container = document.getElementById("testChecklistContainer");
  if (!container) return;
  
  // Validar que testes é um array
  if (!Array.isArray(testes)) {
    console.error("[populateTestCheckboxes] testes não é um array:", testes);
    container.innerHTML = "<p>Erro ao carregar testes. Nenhum teste disponível.</p>";
    return;
  }
  
  if (testes.length === 0) {
    container.innerHTML = "<p>Nenhum teste disponível para este produto.</p>";
    return;
  }
  
  container.innerHTML = "";
  
  testes.forEach((teste) => {
    const label = document.createElement("label");
    label.style.cssText = `
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px;
      border: 1px solid #ddd;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
    `;
    label.onmouseover = () => label.style.backgroundColor = "#f5f5f5";
    label.onmouseout = () => label.style.backgroundColor = "transparent";
    
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.name = "selected_tests";
    checkbox.value = teste.id;
    checkbox.style.cursor = "pointer";
    
    const labelText = document.createElement("span");
    // Montar o label a partir de id e nome (ou usar o campo label se existir)
    const testLabel = teste.label || (`${teste.id} - ${teste.nome}`);
    labelText.textContent = testLabel;
    labelText.style.flex = "1";
    
    label.appendChild(checkbox);
    label.appendChild(labelText);
    container.appendChild(label);
  });
}

/**
 * Prossegue para a tela de seleção de modo com os testes selecionados salvos
 */
function proceedWithTestSelection() {
  const checkboxes = document.querySelectorAll('input[name="selected_tests"]:checked');
  const selectedTests = Array.from(checkboxes).map((cb) => parseInt(cb.value, 10));
  
  if (selectedTests.length === 0) {
    alert("Por favor, selecione pelo menos um teste para prosseguir.");
    return;
  }
  
  // Salva os testes selecionados
  localStorage.setItem("selected_tests_" + selectedProductId, JSON.stringify(selectedTests));
  
  // Esconde o painel de seleção de testes
  const testSelectionPanel = document.getElementById("clientTestSelectionPanel");
  if (testSelectionPanel) {
    testSelectionPanel.classList.add("hidden");
  }
  
  // Mostra o painel de seleção de modo
  const modePanel = document.getElementById("clientModeSelectionPanel");
  if (modePanel) {
    modePanel.classList.remove("hidden");
  }
}

/**
 * Retorna os testes selecionados para um produto
 */
function getSelectedTests() {
  const stored = localStorage.getItem("selected_tests_" + selectedProductId);
  return stored ? JSON.parse(stored) : [];
}

/**
 * Seleciona o modo de validação: 'manual', 'batch', ou 'back'
 */
function selectValidationMode(mode) {
  const modePanel = document.getElementById("clientModeSelectionPanel");
  const batchPanel = document.getElementById("clientBatchValidationPanel");
  const workspacePanel = document.getElementById("clientWorkspacePanel");
  
  if (mode === "back") {
    // Volta para o painel de seleção de modo
    if (batchPanel) batchPanel.classList.add("hidden");
    if (modePanel) modePanel.classList.remove("hidden");
    return;
  }
  
  // Esconde o painel de seleção de modo
  if (modePanel) modePanel.classList.add("hidden");

  // Salva os testes no backend ANTES de prosseguir
  const cnpjEl = document.getElementById("cnpjHidden");
  const cnpj = cnpjEl ? cnpjEl.value : "";
  const selectedTests = getSelectedTests();
  const pid = selectedProductId || localStorage.getItem("homolog_selected_product") || "01";

  console.log("[selectValidationMode]", { mode, cnpj, selectedTests, pid });

  // Validação: CNPJ obrigatório
  if (!cnpj) {
    console.error("[selectValidationMode] CNPJ vazio!");
    alert("Erro: CNPJ não está definido. Volte e identifique-se novamente.");
    if (modePanel) modePanel.classList.remove("hidden");
    return;
  }

  // Validação: testes obrigatórios
  if (!selectedTests || selectedTests.length === 0) {
    console.error("[selectValidationMode] Nenhum teste selecionado!");
    alert("Erro: Nenhum teste foi selecionado. Selecione pelo menos um teste.");
    if (modePanel) modePanel.classList.remove("hidden");
    return;
  }

  // Faz POST para enroll-produto
  const formData = new FormData();
  formData.append("cnpj", cnpj);
  formData.append("produto_id", pid);
  selectedTests.forEach((testId) => {
    formData.append("selected_tests", testId);
  });

  console.log("[selectValidationMode] Enviando POST para /api/client/enroll-produto");

  fetch("/api/client/enroll-produto", {
    method: "POST",
    body: formData,
  })
    .then((resp) => {
      console.log("[selectValidationMode] Response status:", resp.status, resp.ok);
      if (!resp.ok) {
        return resp.json().then((data) => {
          throw new Error(data.error || `HTTP ${resp.status}: Erro ao salvar testes`);
        });
      }
      return resp.json();
    })
    .then((data) => {
      console.log("[selectValidationMode] POST sucesso!", data);
      
      // Salva assignedTestIds após confirmação do backend
      if (typeof assignedTestIds !== "undefined") {
        assignedTestIds = selectedTests.map((id) => String(id).padStart(2, "0"));
      }

      // Agora sim mostra o painel apropriado
      if (mode === "manual") {
        // Carrega cache de testes antes de mostrar workspace
        const cnpjEl = document.getElementById("cnpjHidden");
        const cnpj = cnpjEl ? cnpjEl.value : "";
        if (typeof loadTests === "function") {
          console.log("[selectValidationMode] Carregando testes para manual mode...");
          loadTests(selectedProductId, cnpj).then(() => {
            console.log("[selectValidationMode] Testes carregados, mostrando workspace");
            if (workspacePanel) workspacePanel.classList.remove("hidden");
            // Atualizar campos de validação conforme o produto
            if (typeof updateAccessFormForProduct === "function") {
              updateAccessFormForProduct(selectedProductId);
            }
          }).catch((err) => {
            console.error("[selectValidationMode] Erro ao carregar testes:", err);
            if (workspacePanel) workspacePanel.classList.remove("hidden");
            // Atualizar campos de validação mesmo em caso de erro
            if (typeof updateAccessFormForProduct === "function") {
              updateAccessFormForProduct(selectedProductId);
            }
          });
        } else {
          console.log("[selectValidationMode] loadTests não definido, mostrando workspace direto");
          if (workspacePanel) workspacePanel.classList.remove("hidden");
          // Atualizar campos de validação conforme o produto
          if (typeof updateAccessFormForProduct === "function") {
            updateAccessFormForProduct(selectedProductId);
          }
        }
      } else if (mode === "batch") {
        console.log("[selectValidationMode] Mostrando painel batch");
        if (batchPanel) batchPanel.classList.remove("hidden");
        const selectedTestsLabel = document.getElementById("selectedTestsLabel");
        if (selectedTestsLabel) {
          selectedTestsLabel.textContent = selectedTests.length > 0 
            ? selectedTests.join(", ") 
            : "Nenhum teste selecionado";
        }
      }
    })
    .catch((err) => {
      console.error("[selectValidationMode] Erro ao salvar testes:", err);
      alert(`Erro ao salvar testes: ${err.message}`);
      // Em caso de erro, volta para o modo
      if (modePanel) modePanel.classList.remove("hidden");
    });
}

/**
 * Mostra o painel de seleção de modo de validação
 */
function showValidationModeSelection() {
  const modePanel = document.getElementById("clientModeSelectionPanel");
  if (modePanel) {
    modePanel.classList.remove("hidden");
  }
}


/**
 * Inicializa a interface: produto é o primeiro passo
 */
function initializeProductSelection() {
  const productPanel = document.getElementById("clientProductSelectionPanel");
  const panels = ["clientAccessPanel", "clientTestSelectionPanel", "clientModeSelectionPanel",
    "clientBatchValidationPanel", "clientWorkspacePanel", "clientProgressPanel", "clientResultPanel"];

  panels.forEach((id) => {
    const p = document.getElementById(id);
    if (p) p.classList.add("hidden");
  });

  if (productPanel) productPanel.classList.remove("hidden");

  selectedProductId = "";
  localStorage.removeItem(PRODUCT_STORAGE_KEY);
}

// Inicializa quando a página carrega
document.addEventListener("DOMContentLoaded", () => {
  initializeProductSelection();
});
