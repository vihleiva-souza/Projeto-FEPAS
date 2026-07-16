(function () {
  const STORAGE_KEY = "homolog_ui_lang";
  const SUPPORTED = new Set(["pt", "es"]);

  const translations = {
    pt: {
      "lang.label": "Idioma",
      "lang.pt": "Portugues",
      "lang.es": "Espanhol",

      "portal.brand": "Portal de Homologacao",
      "portal.access": "Acesso",
      "portal.selectProfile": "Selecione seu perfil",
      "portal.subtitle": "Cliente acessa o fluxo de auto-homologacao. Administrador acessa o painel interno com autenticacao.",
      "portal.clientTag": "CLIENTE",
      "portal.clientTitle": "Auto-homologacao",
      "portal.enterClient": "Entrar como Cliente",
      "portal.adminTag": "TIME CERTIFICAÇÃO",
      "portal.adminTitle": "Painel Interno",
      "portal.enterAdmin": "Entrar como Time Certificação",

      "login.brand": "Administrador",
      "login.eyebrow": "Login",
      "login.title": "Acesso ao painel interno",
      "login.subtitle": "Informe usuario e senha para continuar.",
      "login.username": "Usuario",
      "login.usernamePlaceholder": "admin",
      "login.password": "Senha",
      "login.passwordPlaceholder": "********",
      "login.enter": "Entrar",
      "login.backToProfile": "Voltar para selecao de perfil",

      "client.brand": "Portal do Cliente - Auto-homologacao",
      "client.stage": "Stage 2",
      "client.selectProduct": "Selecionar o produto a homologar",
      "client.title": "Envie seu teste de homologacao com dados minimos",
      "client.cnpj": "CNPJ/CUIT",
      "client.cnpjPlaceholder": "Informe o CNPJ/CUIT do cliente",
      "client.access": "Acessar homologacoes",
      "client.accessing": "Acessando...",
      "client.firstAccess": "Primeiro acesso do cliente",
      "client.onboardingTitle": "Selecione os testes que este CNPJ/CUIT vai homologar",
      "client.onboardingHint": "Essa selecao sera salva para este CNPJ/CUIT e nao sera solicitada novamente nos proximos acessos.",
      "client.saveTests": "Salvar testes do cliente",
      "client.saving": "Salvando...",
      "client.authByCnpj": "Cliente autenticado por CNPJ/CUIT",
      "client.changeCnpj": "Trocar CNPJ/CUIT",

      "client.accessTab": "Acesso ao Portal",
      "client.accessDesc": "Informe seu CNPJ",
      "client.submitTab": "Enviar Testes",
      "client.submitDesc": "Execute homologacoes",
      "client.progressTab": "Ver Estado",
      "client.progressDesc": "Acompanhe o progresso",

      "client.statusOverview": "Visao Geral de Progresso",
      "client.planned": "Testes Planejados",
      "client.approved": "Aprovados",
      "client.inProgress": "Em Andamento",
      "client.pending": "Pendentes",
      "client.completionRate": "Taxa de Conclusao",
      "client.approvalRate": "Taxa de Aprovacao",
      "client.averageAttempts": "Tentativas Medias",

      "client.changeCnpj": "Trocar CNPJ/CUIT",
      "client.testDate": "Data do teste",
      "client.testInHomolog": "Teste em homologacao",
      "client.de11": "Bit 11 (Stan)",
      "client.de41": "Bit 41 (Identificacao de Terminal)",
      "client.expectedResult": "Resultado esperado",
      "client.goalDefault": "Selecione um teste para visualizar o objetivo esperado.",
      "client.goalMissing": "Objetivo esperado nao informado para este teste.",
      "client.goalNotFound": "Objetivo esperado nao encontrado para o teste selecionado.",
      "client.sendValidation": "Enviar para validacao",
      "client.processing": "Processando...",
      "client.progress": "Progresso do cliente",
      "client.summary": "Resumo geral",
      "client.selectedTest": "Teste selecionado",
      "client.tableTest": "Teste",
      "client.tableStatus": "Status",
      "client.tableAttempts": "Tentativas",
      "client.tableApprovedAttempt": "Aprovado na tentativa",
      "client.tableSuccess": "% sucesso",
      "client.tableUntilApproval": "% ate aprovacao",
      "client.progressSummaryText": "{started} testes iniciados, {approved} aprovados, de {planned} planejados.",
      "client.progressTitleText": "{approved} de {planned} testes aprovados",
      "client.selectedTestLine": "{id} - {name}: {attempts} tentativa(s), {success}% de sucesso.",
      "client.selectCnpjAndRun": "Selecione um CNPJ/CUIT e execute um teste.",
      "client.noRecentTest": "Nenhum teste selecionado recentemente.",
      "client.noTestsForCnpj": "Nenhum teste realizado para este CNPJ/CUIT.",
      "client.protocol": "Protocolo",
      "client.deniedDetail": "Detalhe da negacao",
      "client.deniedReasonDefault": "Quando negado, o motivo aparece aqui.",
      "client.resultApproved": "APROVADO",
      "client.resultDenied": "NEGADO",
      "client.approvedHint": "Resultado aprovado. Nenhum detalhe adicional necessario.",
      "client.deniedLegUnknown": "Perna nao identificada",
      "client.deniedReasonUnknown": "Motivo nao identificado",
      "client.errorLoadProgress": "Falha ao carregar progresso do cliente.",
      "client.errorEnterCnpj": "Informe o CNPJ/CUIT do cliente.",
      "client.errorCannotLoadCnpj": "Nao foi possivel carregar o progresso deste CNPJ/CUIT.",
      "client.errorCnpjBeforeSelect": "Informe o CNPJ/CUIT antes de selecionar os testes.",
      "client.errorSelectAtLeastOne": "Selecione ao menos um teste para este cliente.",
      "client.errorSaveTests": "Falha ao salvar testes do cliente.",
      "client.errorCannotSaveTests": "Nao foi possivel salvar os testes deste cliente.",
      "client.errorCnpjBeforeValidate": "Informe o CNPJ/CUIT antes de realizar homologacoes.",
      "client.errorValidate": "Falha ao processar validacao.",
      "client.errorCannotValidate": "Nao foi possivel validar seu teste. Tente novamente.",

      "common.back": "Voltar",
      "common.logout": "Sair",
      "common.loading": "Carregando...",
      "common.select": "Selecione...",
      "common.all": "Todos",
      "common.search": "Buscar",
      "common.yes": "Concluido",
      "common.no": "Pendente",

      "tabs.validator": "Ferramenta de Validacao",
      "tabs.validatorDesc": "Importe logs",
      "tabs.clients": "Clientes em Homologacao",
      "tabs.clientsDesc": "Acompanhe o progresso",
      "tabs.management": "Gestao de Testes por Cliente",
      "tabs.managementDesc": "Configure por cliente",

      "validator.eyebrow": "Validador de Homologacao",
      "validator.title": "Importe o log e valide todas as pernas por objetivo de teste",
      "validator.subtitle": "Resultado por perna com status e motivo, comparando o fluxo real com o objetivo esperado do teste selecionado.",
      "validator.testDate": "Data da execucao do teste",
      "validator.testLabel": "Teste de homologacao",
      "validator.logLabel": "Arquivo de log",
      "validator.refreshLogs": "Recarregar lista",
      "validator.de11": "DE11 / Bit 11 - Stan",
      "validator.de41": "DE41 / Bit 41 - Identificacao de Terminal",
      "validator.de11Placeholder": "6 digitos",
      "validator.de41Placeholder": "8 caracteres",
      "validator.filterHint": "Dica: Use DE11 e DE41 para filtrar uma TRN especifica no log.",
      "validator.goalDefault": "Selecione um teste para ver o objetivo esperado.",
      "validator.validate": "Validar Log",
      "validator.validating": "Validando...",

      "result.overall": "Status geral",
      "result.goal": "Objetivo esperado",
      "result.legsFound": "Pernas encontradas",
      "result.objectiveSteps": "Passos do objetivo",
      "result.foundLegs": "Pernas encontradas",
      "result.filterMti": "Filtrar MTI",
      "result.filterStatus": "Filtrar status",
      "result.search": "Buscar",
      "result.searchPlaceholder": "MTI, DE03, DE11, DE41, motivo...",
      "result.onlyObjective": "Somente objetivo",
      "result.onlyErrors": "Somente com erro",
      "result.shownCount": "{count} exibidas",
      "result.noneForFilters": "Nenhuma perna encontrada para os filtros atuais.",
      "result.noSteps": "Nenhum passo configurado para este teste.",
      "result.noErrors": "Sem erros para exibir.",
      "result.noWarnings": "Sem avisos para exibir.",
      "result.details": "Detalhes da perna",
      "result.clickLeg": "Clique em uma perna da tabela para visualizar.",
      "result.noIsoFormatted": "Sem ISO formatado para esta perna.",
      "result.noIsoRaw": "Sem ISO bruto disponivel para esta perna.",
      "result.rawIso": "ISO bruto",
      "result.warnings": "Avisos",
      "result.errors": "Erros",
      "result.final": "Resultado final",
      "result.approvedTitle": "Teste Aprovado",
      "result.approvedMessage": "O teste foi aprovado por completo.",
      "result.download": "Baixar evidencia .txt",

      "status.approved": "Aprovado",
      "status.reproved": "Reprovado",
      "status.na": "Nao aplica",
      "status.notStarted": "Nao iniciado",
      "status.inProgress": "Em andamento",

      "chips.approved": "{count} Aprovada{suffix}",
      "chips.reproved": "{count} Reprovada{suffix}",
      "chips.na": "{count} Nao aplica",
      "chips.total": "{count} total",

      "admin.panel": "Painel Admin",
      "admin.clientsTitle": "Clientes em homologacao",
      "admin.clientsSubtitle": "Visao geral do status de cada cliente: testes selecionados, progresso e % de aprovacao.",
      "admin.searchClient": "Buscar cliente",
      "admin.searchClientPlaceholder": "CNPJ/CUIT ou identificador...",
      "admin.refreshList": "Atualizar lista",
      "admin.clientSelected": "Cliente selecionado",
      "admin.testsByClient": "Gestao de testes por cliente",
      "admin.testsByClientSubtitle": "Selecione um cliente para alterar os testes habilitados para homologacao ou resetar o onboarding.",
      "admin.clientId": "CNPJ/CUIT / Identificador do cliente",
      "admin.clientIdPlaceholder": "Informe o CNPJ/CUIT do cliente",
      "admin.loadClient": "Carregar cliente",
      "admin.resetTests": "Resetar testes realizados",
      "admin.resetOnboarding": "Resetar Onboarding",
      "admin.markTests": "Marque os testes habilitados para este cliente e salve. Isso substitui a selecao atual.",
      "admin.saveEnabledTests": "Salvar testes habilitados",
      "admin.progressDetail": "Progresso detalhado",

      "admin.loadingClients": "Carregando...",
      "admin.errorListClients": "Erro ao listar clientes.",
      "admin.noneClients": "Nenhum cliente encontrado.",
      "admin.noneTestsYet": "Nenhum teste realizado ainda.",
      "admin.errorLoadDetail": "Erro ao carregar detalhe.",
      "admin.fail": "Falha: {message}",
      "admin.enterCnpj": "Informe o CNPJ/CUIT do cliente.",
      "admin.errorLoadClient": "Erro ao carregar cliente.",
      "admin.failLoad": "Falha ao carregar: {message}",
      "admin.selectAtLeastOne": "Selecione ao menos um teste.",
      "admin.errorSave": "Erro ao salvar.",
      "admin.testsSaved": "Testes salvos para {cnpj}.",
      "admin.errorResetTests": "Erro ao resetar testes realizados.",
      "admin.testsReset": "Testes realizados do cliente {cnpj} foram resetados.",
      "admin.errorReset": "Erro ao resetar.",
      "admin.onboardingReset": "Onboarding do cliente {cnpj} foi resetado.",
      "admin.confirmResetTests": "Confirmar reset dos testes realizados para {cnpj}? O histórico e os arquivos de execução serão removidos.",
      "admin.confirmReset": "Confirmar reset de onboarding para {cnpj}? O cliente precisara selecionar os testes novamente no proximo acesso.",

      "validator.selectLog": "Selecione o log...",
      "validator.noneLogs": "Nenhum log encontrado",
      "validator.failLogs": "Falha ao carregar logs",
      "validator.failTests": "Falha ao carregar testes",
      "validator.goalExpected": "Objetivo esperado: {goal}",
      "validator.failValidation": "Falha na validacao",
      "validator.toastUnavailableEvidence": "Evidencia indisponivel para download.",
      "validator.toastValidateFail": "Nao foi possivel validar o log. Verifique a selecao e tente novamente.",
      "validator.testsLoadError": "Erro ao carregar testes: {message}",

      "clients.onboardingDone": "Concluido",
      "clients.onboardingPending": "Pendente",
      "clients.loading": "Carregando...",

      "tests.01.name": "Transacao sem leitura de QR",
      "tests.02.name": "Transacao financeira carteira digital",
      "tests.03.name": "Transacao financeira cartao de debito",
      "tests.04.name": "Transacao financeira cartao de credito (VISA)",
      "tests.05.name": "Transacao financeira cartao de debito (MasterCard)",
      "tests.06.name": "Transacao financeira cartao de credito (MasterCard)",
      "tests.07.name": "Transacao financeira com alteracao de valor no fluxo de planos",
      "tests.08.name": "Transacao de credito com 02 parcelas",
      "tests.09.name": "Transacao financeira credito 02 parcelas com alteracao para 03 nos planos",
      "tests.10.name": "Transacao de credito com mudanca de MID no meio do fluxo",
      "tests.11.name": "Cancelamento parcial de transacao de compra de debito",
      "tests.12.name": "Cancelamento total da transacao de compra credito/debito",
      "tests.13.name": "Cancelamento com valor inferior ao da compra do teste 02 (PCT)",
      "tests.14.name": "Compra PCT com cancelamento total",
      "tests.15.name": "Realizar uma compra de Cartao e na autorizacao enviar o desfazimento",
      "tests.16.name": "Desfazer cancelamento na autorizacao",
      "tests.17.name": "Pagamento PCT com consulta e confirmacao posterior",
      "tests.18.name": "PCT com desfazimento B6 e confirmacao posterior",
      "tests.19.name": "Cancelamento PCT com consulta e confirmacao posterior",
      "tests.20.name": "Compra credito com tres estornos"
    },

    es: {
      "lang.label": "Idioma",
      "lang.pt": "Portugues",
      "lang.es": "Espanol",

      "portal.brand": "Portal de Homologacion",
      "portal.access": "Acceso",
      "portal.selectProfile": "Seleccione su perfil",
      "portal.subtitle": "Cliente accede al flujo de auto-homologacion. Administrador accede al panel interno con autenticacion.",
      "portal.clientTag": "CLIENTE",
      "portal.clientTitle": "Auto-homologacion",
      "portal.enterClient": "Entrar como Cliente",
      "portal.adminTag": "TEAM CERTIFICACIÓN",
      "portal.adminTitle": "Panel Interno",
      "portal.enterAdmin": "Entrar como Team Certificación",

      "login.brand": "Administrador",
      "login.eyebrow": "Login",
      "login.title": "Acceso al panel interno",
      "login.subtitle": "Ingrese usuario y contrasena para continuar.",
      "login.username": "Usuario",
      "login.usernamePlaceholder": "admin",
      "login.password": "Contrasena",
      "login.passwordPlaceholder": "********",
      "login.enter": "Entrar",
      "login.backToProfile": "Volver a seleccion de perfil",

      "client.brand": "Portal del Cliente - Auto-homologacion",
      "client.stage": "Stage 2",
      "client.selectProduct": "Seleccionar el producto a homologar",
      "client.title": "Envie su prueba de homologacion con datos minimos",
      "client.cnpj": "CNPJ/CUIT",
      "client.cnpjPlaceholder": "Ingrese el CNPJ/CUIT del cliente",
      "client.access": "Acceder a homologaciones",
      "client.accessing": "Accediendo...",
      "client.firstAccess": "Primer acceso del cliente",
      "client.onboardingTitle": "Seleccione las pruebas que este CNPJ/CUIT va a homologar",
      "client.onboardingHint": "Esta seleccion se guardara para este CNPJ/CUIT y no se solicitara nuevamente en los proximos accesos.",
      "client.saveTests": "Guardar pruebas del cliente",
      "client.saving": "Guardando...",
      "client.authByCnpj": "Cliente autenticado por CNPJ/CUIT",
      "client.changeCnpj": "Cambiar CNPJ/CUIT",

      "client.accessTab": "Acceso al Portal",
      "client.accessDesc": "Ingrese su CNPJ",
      "client.submitTab": "Enviar Pruebas",
      "client.submitDesc": "Ejecute homologaciones",
      "client.progressTab": "Ver Estado",
      "client.progressDesc": "Siga el progreso",

      "client.statusOverview": "Vision General del Progreso",
      "client.planned": "Pruebas Planificadas",
      "client.approved": "Aprobadas",
      "client.inProgress": "En Curso",
      "client.pending": "Pendientes",
      "client.completionRate": "Tasa de Finalizacion",
      "client.approvalRate": "Tasa de Aprobacion",
      "client.averageAttempts": "Intentos Promedio",

      "client.testDate": "Fecha de la prueba",
      "client.testInHomolog": "Prueba en homologacion",
      "client.de11": "Bit 11 (Stan)",
      "client.de41": "Bit 41 (Identificacion de Terminal)",
      "client.expectedResult": "Resultado esperado",
      "client.goalDefault": "Seleccione una prueba para visualizar el objetivo esperado.",
      "client.goalMissing": "Objetivo esperado no informado para esta prueba.",
      "client.goalNotFound": "Objetivo esperado no encontrado para la prueba seleccionada.",
      "client.sendValidation": "Enviar para validacion",
      "client.processing": "Procesando...",
      "client.progress": "Progreso del cliente",
      "client.summary": "Resumen general",
      "client.selectedTest": "Prueba seleccionada",
      "client.tableTest": "Prueba",
      "client.tableStatus": "Estado",
      "client.tableAttempts": "Intentos",
      "client.tableApprovedAttempt": "Aprobado en el intento",
      "client.tableSuccess": "% exito",
      "client.tableUntilApproval": "% hasta aprobacion",
      "client.progressSummaryText": "{started} pruebas iniciadas, {approved} aprobadas, de {planned} planificadas.",
      "client.progressTitleText": "{approved} de {planned} pruebas aprobadas",
      "client.selectedTestLine": "{id} - {name}: {attempts} intento(s), {success}% de exito.",
      "client.selectCnpjAndRun": "Seleccione un CNPJ/CUIT y ejecute una prueba.",
      "client.noRecentTest": "Ninguna prueba seleccionada recientemente.",
      "client.noTestsForCnpj": "No hay pruebas realizadas para este CNPJ/CUIT.",
      "client.protocol": "Protocolo",
      "client.deniedDetail": "Detalle de rechazo",
      "client.deniedReasonDefault": "Cuando es negado, el motivo aparece aqui.",
      "client.resultApproved": "APROBADO",
      "client.resultDenied": "NEGADO",
      "client.approvedHint": "Resultado aprobado. Ningun detalle adicional necesario.",
      "client.deniedLegUnknown": "Etapa no identificada",
      "client.deniedReasonUnknown": "Motivo no identificado",
      "client.errorLoadProgress": "Fallo al cargar el progreso del cliente.",
      "client.errorEnterCnpj": "Ingrese el CNPJ/CUIT del cliente.",
      "client.errorCannotLoadCnpj": "No fue posible cargar el progreso de este CNPJ/CUIT.",
      "client.errorCnpjBeforeSelect": "Ingrese el CNPJ/CUIT antes de seleccionar las pruebas.",
      "client.errorSelectAtLeastOne": "Seleccione al menos una prueba para este cliente.",
      "client.errorSaveTests": "Fallo al guardar pruebas del cliente.",
      "client.errorCannotSaveTests": "No fue posible guardar las pruebas de este cliente.",
      "client.errorCnpjBeforeValidate": "Ingrese el CNPJ/CUIT antes de realizar homologaciones.",
      "client.errorValidate": "Fallo al procesar validacion.",
      "client.errorCannotValidate": "No fue posible validar su prueba. Intente nuevamente.",

      "common.back": "Volver",
      "common.logout": "Salir",
      "common.loading": "Cargando...",
      "common.select": "Seleccionar...",
      "common.all": "Todos",
      "common.search": "Buscar",
      "common.yes": "Completado",
      "common.no": "Pendiente",

      "tabs.validator": "Herramienta de Validacion",
      "tabs.validatorDesc": "Importar logs",
      "tabs.clients": "Clientes en Homologacion",
      "tabs.clientsDesc": "Seguir el progreso",
      "tabs.management": "Gestion de Pruebas por Cliente",
      "tabs.managementDesc": "Configurar por cliente",

      "validator.eyebrow": "Validador de Homologacion",
      "validator.title": "Importe el log y valide todas las etapas por objetivo de prueba",
      "validator.subtitle": "Resultado por etapa con estado y motivo, comparando el flujo real con el objetivo esperado de la prueba seleccionada.",
      "validator.testDate": "Fecha de ejecucion de la prueba",
      "validator.testLabel": "Prueba de homologacion",
      "validator.logLabel": "Archivo de log",
      "validator.refreshLogs": "Recargar lista",
      "validator.de11": "DE11 / Bit 11 - Stan",
      "validator.de41": "DE41 / Bit 41 - Identificacion de Terminal",
      "validator.de11Placeholder": "6 digitos",
      "validator.de41Placeholder": "8 caracteres",
      "validator.filterHint": "Sugerencia: use DE11 y DE41 para filtrar una TRN especifica en el log.",
      "validator.goalDefault": "Seleccione una prueba para ver el objetivo esperado.",
      "validator.validate": "Validar Log",
      "validator.validating": "Validando...",

      "result.overall": "Estado general",
      "result.goal": "Objetivo esperado",
      "result.legsFound": "Etapas encontradas",
      "result.objectiveSteps": "Pasos del objetivo",
      "result.foundLegs": "Etapas encontradas",
      "result.filterMti": "Filtrar MTI",
      "result.filterStatus": "Filtrar estado",
      "result.search": "Buscar",
      "result.searchPlaceholder": "MTI, DE03, DE11, DE41, motivo...",
      "result.onlyObjective": "Solo objetivo",
      "result.onlyErrors": "Solo con error",
      "result.shownCount": "{count} mostradas",
      "result.noneForFilters": "No se encontraron etapas para los filtros actuales.",
      "result.noSteps": "No hay pasos configurados para esta prueba.",
      "result.noErrors": "Sin errores para mostrar.",
      "result.noWarnings": "Sin avisos para mostrar.",
      "result.details": "Detalles de la etapa",
      "result.clickLeg": "Haga clic en una etapa de la tabla para visualizar.",
      "result.noIsoFormatted": "Sin ISO formateado para esta etapa.",
      "result.noIsoRaw": "Sin ISO bruto disponible para esta etapa.",
      "result.rawIso": "ISO bruto",
      "result.warnings": "Avisos",
      "result.errors": "Errores",
      "result.final": "Resultado final",
      "result.approvedTitle": "Prueba Aprobada",
      "result.approvedMessage": "La prueba fue aprobada por completo.",
      "result.download": "Descargar evidencia .txt",

      "status.approved": "Aprobado",
      "status.reproved": "Reprobado",
      "status.na": "No aplica",
      "status.notStarted": "No iniciado",
      "status.inProgress": "En curso",

      "chips.approved": "{count} Aprobada{suffix}",
      "chips.reproved": "{count} Reprobada{suffix}",
      "chips.na": "{count} No aplica",
      "chips.total": "{count} total",

      "admin.panel": "Panel Admin",
      "admin.clientsTitle": "Clientes en homologacion",
      "admin.clientsSubtitle": "Vista general del estado de cada cliente: pruebas seleccionadas, progreso y % de aprobacion.",
      "admin.searchClient": "Buscar cliente",
      "admin.searchClientPlaceholder": "CNPJ/CUIT o identificador...",
      "admin.refreshList": "Actualizar lista",
      "admin.clientSelected": "Cliente seleccionado",
      "admin.testsByClient": "Gestion de pruebas por cliente",
      "admin.testsByClientSubtitle": "Seleccione un cliente para cambiar las pruebas habilitadas para homologacion o reiniciar el onboarding.",
      "admin.clientId": "CNPJ/CUIT / Identificador del cliente",
      "admin.clientIdPlaceholder": "Ingrese el CNPJ/CUIT del cliente",
      "admin.loadClient": "Cargar cliente",
      "admin.resetTests": "Reiniciar pruebas realizadas",
      "admin.resetOnboarding": "Reiniciar Onboarding",
      "admin.markTests": "Marque las pruebas habilitadas para este cliente y guarde. Esto reemplaza la seleccion actual.",
      "admin.saveEnabledTests": "Guardar pruebas habilitadas",
      "admin.progressDetail": "Progreso detallado",

      "admin.loadingClients": "Cargando...",
      "admin.errorListClients": "Error al listar clientes.",
      "admin.noneClients": "No se encontraron clientes.",
      "admin.noneTestsYet": "Todavia no hay pruebas realizadas.",
      "admin.errorLoadDetail": "Error al cargar detalle.",
      "admin.fail": "Fallo: {message}",
      "admin.enterCnpj": "Ingrese el CNPJ/CUIT del cliente.",
      "admin.errorLoadClient": "Error al cargar cliente.",
      "admin.failLoad": "Fallo al cargar: {message}",
      "admin.selectAtLeastOne": "Seleccione al menos una prueba.",
      "admin.errorSave": "Error al guardar.",
      "admin.testsSaved": "Pruebas guardadas para {cnpj}.",
      "admin.errorResetTests": "Error al reiniciar pruebas realizadas.",
      "admin.testsReset": "Las pruebas realizadas del cliente {cnpj} fueron reiniciadas.",
      "admin.errorReset": "Error al reiniciar.",
      "admin.onboardingReset": "Se reinicio el onboarding del cliente {cnpj}.",
      "admin.confirmResetTests": "Confirmar reinicio de pruebas realizadas para {cnpj}? Se eliminara el historial y los archivos de ejecucion.",
      "admin.confirmReset": "Confirmar reinicio de onboarding para {cnpj}? El cliente debera seleccionar las pruebas nuevamente en el proximo acceso.",

      "validator.selectLog": "Seleccione el log...",
      "validator.noneLogs": "No se encontro ningun log",
      "validator.failLogs": "Fallo al cargar logs",
      "validator.failTests": "Fallo al cargar pruebas",
      "validator.goalExpected": "Objetivo esperado: {goal}",
      "validator.failValidation": "Fallo en la validacion",
      "validator.toastUnavailableEvidence": "Evidencia no disponible para descarga.",
      "validator.toastValidateFail": "No se pudo validar el log. Revise la seleccion e intente nuevamente.",
      "validator.testsLoadError": "Error al cargar pruebas: {message}",

      "clients.onboardingDone": "Completado",
      "clients.onboardingPending": "Pendiente",
      "clients.loading": "Cargando...",

      "tests.01.name": "Transaccion sin lectura de QR",
      "tests.02.name": "Transaccion financiera billetera digital",
      "tests.03.name": "Transaccion financiera tarjeta de debito",
      "tests.04.name": "Transaccion financiera tarjeta de credito (VISA)",
      "tests.05.name": "Transaccion financiera tarjeta de debito (MasterCard)",
      "tests.06.name": "Transaccion financiera tarjeta de credito (MasterCard)",
      "tests.07.name": "Transaccion financiera con cambio de valor en el flujo de planes",
      "tests.08.name": "Transaccion de credito con 02 cuotas",
      "tests.09.name": "Transaccion financiera credito 02 cuotas con cambio a 03 en planes",
      "tests.10.name": "Transaccion de credito con cambio de MID en medio del flujo",
      "tests.11.name": "Cancelacion parcial de transaccion de compra de debito",
      "tests.12.name": "Cancelacion total de la transaccion de compra credito/debito",
      "tests.13.name": "Cancelacion con valor inferior al de la compra de la prueba 02 (PCT)",
      "tests.14.name": "Compra PCT con cancelacion total",
      "tests.15.name": "Realizar una compra con tarjeta y en la autorizacion enviar el deshacer",
      "tests.16.name": "Deshacer cancelacion en la autorizacion",
      "tests.17.name": "Pago PCT con consulta y confirmacion posterior",
      "tests.18.name": "PCT con deshacer B6 y confirmacion posterior",
      "tests.19.name": "Cancelacion PCT con consulta y confirmacion posterior",
      "tests.20.name": "Compra credito con tres reversiones"
    }
  };

  let currentLanguage = "pt";

  function getByPath(obj, path) {
    if (!obj) return undefined;
    return path.split(".").reduce((acc, part) => (acc && acc[part] != null ? acc[part] : undefined), obj);
  }

  function getTranslation(dict, key) {
    if (!dict) return undefined;
    if (Object.prototype.hasOwnProperty.call(dict, key)) {
      return dict[key];
    }
    return getByPath(dict, key);
  }

  function formatTemplate(value, vars) {
    if (!vars) return value;
    return String(value).replace(/\{(\w+)\}/g, (_, token) => {
      const replacement = vars[token];
      return replacement == null ? "" : String(replacement);
    });
  }

  function t(key, vars) {
    const dict = translations[currentLanguage] || translations.pt;
    const fallback = translations.pt;
    const value = getTranslation(dict, key) ?? getTranslation(fallback, key) ?? key;
    return formatTemplate(value, vars);
  }

  function translateTestName(testId, fallbackName) {
    const normalized = String(testId || "").padStart(2, "0");
    const key = `tests.${normalized}.name`;
    const translated = t(key);
    if (translated === key) {
      return String(fallbackName || "");
    }
    return translated;
  }

  function applyPageTranslations(root) {
    const scope = root || document;
    scope.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;
      el.textContent = t(key);
    });

    scope.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (!key) return;
      el.setAttribute("placeholder", t(key));
    });

    scope.querySelectorAll("[data-i18n-title]").forEach((el) => {
      const key = el.getAttribute("data-i18n-title");
      if (!key) return;
      el.setAttribute("title", t(key));
      el.setAttribute("aria-label", t(key));
    });
  }

  function getLanguage() {
    return currentLanguage;
  }

  function setLanguage(lang) {
    const normalized = String(lang || "").toLowerCase();
    currentLanguage = SUPPORTED.has(normalized) ? normalized : "pt";
    try {
      localStorage.setItem(STORAGE_KEY, currentLanguage);
    } catch (_) {
      // noop
    }
    document.documentElement.setAttribute("lang", currentLanguage === "es" ? "es" : "pt-BR");
    applyPageTranslations(document);
    window.dispatchEvent(new CustomEvent("app-language-changed", { detail: { language: currentLanguage } }));
  }

  function init() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && SUPPORTED.has(saved)) {
        currentLanguage = saved;
      }
    } catch (_) {
      // noop
    }

    const select = document.getElementById("languageSelect");
    if (select) {
      select.value = currentLanguage;
      select.addEventListener("change", (event) => {
        setLanguage(event.target.value);
      });
    }

    setLanguage(currentLanguage);
  }

  window.I18N = {
    t,
    translateTestName,
    setLanguage,
    getLanguage,
    applyPageTranslations,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
