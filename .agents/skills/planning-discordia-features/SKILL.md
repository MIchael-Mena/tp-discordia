---
name: planning-discordia-features
description: 'Planificar e implementar Historias de Usuario (HU) y tareas del backlog en los repositorios de Discordia (server, gateway, profile, auth-service, text-channel, voice-calls, notifications, web-client, backoffice, infra) estructurando planes detallados por etapas y PRs apilados. Use when: el usuario invoca /plan, pide armar un plan de implementación para una o más HU o tareas TSK-*, diseñar features que cruzan microservicios, o ejecutar un plan aprobado hasta publicar los PRs y cerrar el backlog.'
argument-hint: '<HU-XX / TSK-XXX> — p. ej. HU-24 + HU-55'
---

# Planificar e Implementar Features en Discordia

Guía y plantilla estándar para diseñar planes de implementación multi-servicio en TP-Discordia y ejecutarlos de punta a punta sin omitir commits atómicos, validaciones ni la publicación de Pull Requests.

## Cuándo usar

- El usuario inicia con `/plan` o pide un plan detallado por etapas para una o varias Historias de Usuario (`HU-XX`) o tareas locales (`TSK-XXX`).
- Una funcionalidad cruza repositorios (`server` / `auth-service` / `profile` / `text-channel` / `voice-calls` / `notifications` ↔ `gateway` ↔ `web-client` / `backoffice` ↔ `infra`) o requiere apilar PRs (*stacked PRs*).
- Al pasar de un plan aprobado a la implementación, para cumplir todo el ciclo hasta dejar los PRs publicados en GitHub y el seguimiento local actualizado.

## Reglas de oro

1. **Un PR lógico por etapa/repositorio y commits atómicos siempre.** Prohibido concentrar una etapa en un único commit gigante. Todo plan debe declarar en cada etapa la secuencia de commits atómicos en **Conventional Commits en español** (`docs` → `feat` migración/modelo → `feat` caso de uso/endpoint/UI → `test`), **sin trailers `Co-authored-by` ni firmas de IA**.
2. **Spec-First (SDD) y ADRs integrados en el plan.** Inspeccioná las specs y ADRs aplicables según el procedimiento de investigación. Incluí la spec (y el ADR si hay decisión arquitectónica) como primer paso `[NEW]`/`[MODIFY]` de la etapa. Una vez aprobado el plan, generá la spec primero y continuá con el código y los tests; si cambia una decisión material o aparece un bloqueo, detenete y consultá. Sincronizá la spec con el código final antes de commitear.
3. **Privacidad estricta del Backlog local.** En el artefacto local del plan podés trazar `TSK-*` y `Backlog.json`, pero está **prohibido** filtrar `TSK-*` o `Backlog.json` en `specs/`, `docs/arquitectura/`, código, mensajes de commit o títulos/descripciones de PR (usá únicamente `HU-XX`, `ADR-XXX` o `#PR`).
4. **Contratos cerrados de punta a punta.** Cuando apliquen, explicitá firmas, códigos y payloads de error, precedencia de rechazos y comportamiento del cliente, incluyendo errores desconocidos. No impongas un orden numérico ni una traducción literal 1:1: justificá el contrato y respetá las convenciones existentes. Revisá:
   - Auto-acciones (`caller == target`) y jerarquía/permisos cuando correspondan.
   - Rechazos solapados: definí y probá la precedencia adecuada al dominio y a la seguridad.
   - Invariantes de persistencia y concurrencia; elegí mecanismos apropiados al stack y seguí *expand/contract* cuando corresponda, sin prescribir locks o `flush()` para todos los casos.
   - **Paginación determinística:** toda consulta paginada (`limit/offset`) lleva desempate por clave primaria (p. ej. `ORDER BY created_at DESC, id DESC`) respaldado por un índice compuesto equivalente, para evitar resultados inestables con timestamps iguales.
   - **Trazabilidad sin entradas espurias:** registrá auditoría/eventos sólo cuando la operación cambió efectivamente el estado (p. ej. no auditar un `UNMUTE` si no había silenciamiento activo); si el caso de uso es idempotente, documentá el comportamiento esperado.
   - **Filtros UI ↔ contrato:** contrastá pestañas/filtros de la UI con los parámetros del endpoint (una pestaña que agrupa varias acciones requiere filtro multi-valor) y definí un `400 Bad Request` controlado ante valores inválidos, con test.
   - **Entidades no disponibles:** si la UI muestra usuarios o entidades de registros históricos que pudieron dejar de ser co-miembros (expulsados, baneados, ex-miembros), definí si el backend amplía la visibilidad o si el cliente aplica un fallback visual (ver [frontend-guidelines.md](./references/frontend-guidelines.md)).
5. **La implementación NO termina hasta publicar los PRs.** Todo plan debe incluir una etapa explícita de **Publicación de Pull Requests** (`git push -u origin <rama>` en orden topológico + `gh pr create` en PowerShell con la plantilla obligatoria de `AGENTS.md`) **después** de pasar linters/tests y **antes** de cerrar `Backlog.json` y `estado-historias.md`. Ninguna tarea `completed` con cambios de código se cierra poniendo solo nombres de ramas: debe enlazar los números reales de PR (`<repo> #<N>`).
6. **Coherencia visual en el frontend.** Todo cambio de UI en `web-client` o `backoffice` debe mantener coherencia visual con los módulos existentes (tokens del tema, patrones de encabezado, estados vacíos/carga/error), aunque sean funcionalidades distintas. La reutilización de componentes compartidos es una **sugerencia** que se aplica solo cuando corresponde. En `web-client`, planificá los estilos, incluso los específicos, en archivos separados bajo `src/styles/`; en otros clientes verificá su convención. Seguí [frontend-guidelines.md](./references/frontend-guidelines.md); la única excepción visual es un refactor pedido explícitamente por el usuario para ese módulo.
7. **Puntajes leídos en vivo y `## Notas` reservada.** Nunca estimes puntajes de memoria: leé `estado-historias.md` al armar el plan y calculá el impacto sobre los valores vigentes (optativos, obligatorios y total). La sección `## Notas` de `estado-historias.md` es **exclusiva para pendientes técnicos abiertos sin resolver**; está prohibido agregar allí PRs, evidencia de verificación o descripción de lo implementado (eso vive en `specs/`, ADRs y PRs).
8. **Separar tarea y HU.** Un PR abierto puede respaldar el cierre de una tarea local según `.agents/rules/backlog.md`, pero no demuestra por sí solo que la HU esté completa. Marcá una HU como completada y sumá sus puntos únicamente si todos los PRs necesarios están abiertos o mergeados y hay evidencia de verificación de todos sus criterios de aceptación de punta a punta. Indicá qué se verificó y en qué entorno; no afirmes que está desplegada si no se comprobó.

## Procedimiento para armar el plan

### 1. Investigación previa (obligatoria antes de escribir el plan)

1. **Requisitos y alcance:** Leé los Criterios de Aceptación exactos en `historias-usuario.md`, el estado actual en `estado-historias.md` (puntajes vigentes: obligatorios, optativos y total) y los nodos involucrados en `Backlog.json`.
   - **Si hay UI** en `web-client` o `backoffice`, leé [frontend-guidelines.md](./references/frontend-guidelines.md) e inspeccioná al menos un módulo hermano antes de redactar la sección de UI.
2. **Reglas por servicio:** Si trabajás en un repo con su propio `AGENTS.md` (p. ej. `profile/AGENTS.md`), leelo primero. Leé al menos 2 specs existentes del servicio para respetar numeración y formato; si faltan o hay menos de 2, registralo y completá la muestra con specs de otro servicio, sin inventar una convención local. Revisá los ADRs aplicables; si no existen en el servicio, indicá la ausencia y consultá ejemplos pertinentes. Una decisión transversal se documenta en `infra/docs/adr/` y se referencia desde los servicios afectados.
3. **Estado Git y PRs abiertos:** En cada repo afectado verificá ramas y PRs abiertos:
   ```powershell
   git -C <repo> fetch origin
   gh pr list -R fiuba-IS2-Discordia/<repo> --state open
   ```
   - Registrá rama actual y `git status -sb` (y `git worktree list` sólo si hay más de uno); seguí `.agents/rules/env-cost.md` §4 para trabajar directamente sobre la rama con `git switch` y aplicar el protocolo de árbol sucio antes de cambiar de rama. No descartes cambios existentes sin confirmación explícita.
   - Identificá repositorio base, repositorio de cabeza, rama y SHA del PR dependiente. Apilá sobre su cabeza sólo si corresponde al mismo repositorio y es accesible; una dependencia entre servicios no convierte su rama en base Git del otro repo. Ante divergencias, falta de acceso o una rama ocupada, detenete y consultá.
   - Si no hay una dependencia de rama en ese repositorio, partí de `origin/develop` (salvo `infra`, que usa únicamente `main`).
   - Si hay otro PR abierto tocando los mismos archivos (ej. routers o archivos de test en `gateway`), indicá en una nota `[!NOTE]` dónde ubicar el código nuevo para evitar conflictos de merge.

### 2. Redacción del plan

Instanciá la estructura completa de [plan-template.md](./references/plan-template.md), respetando todas sus secciones en este orden:

1. **Descripción del Objetivo** (HUs con puntos obligatorios/optativos, pendientes `TSK-*` que se resuelven e impacto en el puntaje de `estado-historias.md`).
2. **Decisiones de Diseño Acordadas** (alerta `[!IMPORTANT]` con invariantes de dominio, persistencia/concurrencia y privacidad del backlog) + **Topología de Ramas y Pull Requests** en un diagrama `mermaid` (`flowchart LR` con un `subgraph` por repositorio). Cuando corresponda, documentá aparte dependencias entre servicios, compatibilidad de versiones, despliegue y rollback.
3. **Cambios Propuestos por Etapa** (etapas numeradas en orden de dependencia; dentro de cada etapa, subsección por repositorio indicando rama y base, archivos `[NEW]` / `[MODIFY]` con links `file:///...`, contratos/reglas exactas, tests y **Secuencia de commits atómicos**).
4. **Plan de Verificación** (comandos de linter, tipos, tests/cobertura por stack, auditoría anti-fuga de `TSK-*`/coautoría IA y pasos de prueba manual E2E).
5. **Etapa N-1 — Publicación de Pull Requests** (push en orden topológico de ramas base a ramas apiladas y creación con `gh pr create` en PowerShell siguiendo la plantilla de `AGENTS.md`, únicamente cuando toda la verificación previa esté en verde).
6. **Etapa N — Cierre de Backlog y Actualización de `estado-historias.md`** (seguimiento según `.agents/rules/backlog.md`, PRs reales y actualización de historias y puntajes sólo cuando se cumpla la regla 6).

Antes de pedir aprobación, explicitá que aprobar el plan autoriza su ejecución, creación de commits, push, publicación de los PRs indicados y seguimiento local. Si el usuario limita esa autorización, respetá sus límites. Una aprobación de sólo planificación no habilita ejecución.

### 3. Ejecución del plan aprobado

Una vez que el usuario aprueba el plan:

1. Leé `.agents/rules/backlog.md` antes de editar el backlog; al iniciar cada tarea registrá `in_progress` y su fecha real de inicio si aún no la tiene, sin modificar una fecha ya establecida. En cada repositorio, aplicá `.agents/rules/env-cost.md` §4 (protocolo de árbol sucio, cambio de rama con `git switch` sin worktree por defecto y control anti-buffer-sucio) y creá cada rama desde la base acordada actualizada, verificando SHA y estado local.
2. En cada etapa/repositorio, generá primero la spec/ADR y realizá **commits atómicos** a medida que completás cada unidad lógica (`docs`, `feat`, `test`), verificando que no se agreguen trailers `Co-authored-by`.
3. Ejecutá pruebas dirigidas durante la implementación (`.agents/rules/env-cost.md` §2) y, antes de publicar cada PR, pasá la **compuerta pre-PR** completa (`.agents/rules/env-cost.md` §3) sobre el SHA final de la rama. Reutilizá evidencia para el mismo SHA; no repitas suites por cada commit.
4. Ejecutá la auditoría de privacidad (`git -C <repo> log` y `git -C <repo> diff <base>...HEAD`) confirmando ausencia total de `TSK-`, `Backlog.json` y firmas de IA.
5. Antes de cada push y creación, verificá el SHA local y remoto, la base y si ya existe un PR para la misma cabeza y base. Pusheá las ramas en orden topológico y publicá los PRs con `gh pr create --body-file ...` desde PowerShell sólo con la compuerta pre-PR en verde. No fuerces un push ni reescribas historia sin autorización expresa.
6. Cerrá las tareas y actualizá las historias que cumplan sus criterios siguiendo la plantilla y `.agents/rules/backlog.md`. Seguí `.agents/rules/env-cost.md` §4.5 y §6 para restaurar la rama/estado original cuando corresponda, retirar temporales propios y reportar el estado final por repositorio.

Ante una validación fallida, divergencia, cambio material del plan o publicación parcial, detenete e informá evidencia, ramas y PRs ya publicados, pendientes y residuos. No marques como completo el trabajo incompleto. Para retomar, consultá de nuevo el estado remoto y reutilizá un PR existente sólo tras confirmar repositorio, cabeza, base y SHA; no dupliques ni sobrescribas trabajo ajeno.

## Referencias

- [plan-template.md](./references/plan-template.md) — Plantilla Markdown completa con todas las secciones obligatorias, bloques de commits atómicos, recetas de verificación por stack y etapa de publicación de PRs.
- [frontend-guidelines.md](./references/frontend-guidelines.md) — Coherencia visual y reutilización sugerida de componentes en `web-client` y `backoffice`, cableado de entry points, fallbacks, filtros y verificación con `tsc --noEmit`.
