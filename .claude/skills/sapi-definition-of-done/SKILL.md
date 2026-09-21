---
name: sapi-definition-of-done
description: Evaluar si un cambio de S.A.P.I. cumple sus criterios de aceptacion y tiene evidencia suficiente para considerarlo terminado.
---
# Definicion de terminado
Evaluar los criterios de aceptacion reales uno por uno, indicando evidencia o brecha.
Comprobar integracion en el destino requerido por la tarea, pruebas relevantes ejecutadas con su resultado real, regresiones conocidas, documentacion necesaria y trazabilidad Jira-codigo-prueba.
Para cambios cientificos, comprobar causalidad temporal, significado del score y limites de los datos conforme al freeze de arquitectura; tests de software no validan el modelo cientificamente.
Para UI, verificar el comportamiento en navegador y estados relevantes; una captura aislada no prueba un flujo completo.
Usar verificaciones proporcionales al cambio. No afirmar PASS si no se ejecuto la comprobacion. Registrar lo no ejecutado y por que.
Concluir Listo o Pendiente con brechas concretas. Esta evaluacion no concede permiso para publicar, fusionar ni cambiar Jira.
