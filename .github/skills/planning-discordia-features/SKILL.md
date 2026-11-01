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
2. **Spec-First (SDD) y ADRs integrados en el plan.** Antes de proponer cambios en `<servicio>`, inspeccioná al menos 2 specs en `<servicio>/specs/` y los ADRs en `docs/arquitectura/` (o `infra/docs/adr/`). Incluí la spec (y el ADR si hay decisión arquitectónica) como primer paso `[NEW]`/`[MODIFY]` de la etapa. Una vez aprobado el plan, generá la spec primero y continuá directo con el código y los tests sin volver a frenar.
3. **Privacidad estricta del Backlog local.** En el artefacto local del plan podés trazar `TSK-*` y `Backlog.json`, pero está **prohibido** filtrar `TSK-*` o `Backlog.json` en `specs/`, `docs/arquitectura/`, código, mensajes de commit o títulos/descripciones de PR (usá únicamente `HU-XX`, `ADR-XXX` o `#PR`).
4. **Contratos cerrados de punta a punta.** Explicitá firmas, orden exacto de códigos HTTP y mensajes de rechazo en backend junto con su traducción 1:1 en el cliente (`*Errors.ts`). Revisá siempre:
   - Casos de auto-acción (`caller == target`) en reglas de jerarquía/permisos.
   - Orden de evaluación cuando dos rechazos se solapan (el motivo específico va **antes** que el general).
   - Concurrencia e invariantes en base de datos (patrón *expand/contract*, `lockById`, `flush()` ante constraints o índices únicos parciales).
5. **La implementación NO termina hasta publicar los PRs.** Todo plan debe incluir una etapa explícita de **Publicación de Pull Requests** (`git push -u origin <rama>` en orden topológico + `gh pr create` en PowerShell con la plantilla obligatoria de `AGENTS.md`) **después** de pasar linters/tests y **antes** de cerrar `Backlog.json` y `estado-historias.md`. Ninguna tarea `completed` con cambios de código se cierra poniendo solo nombres de ramas: debe enlazar los números reales de PR (`<repo> #<N>`).

## Procedimiento para armar el plan

### 1. Investigación previa (obligatoria antes de escribir el plan)

1. **Requisitos y alcance:** Leé los Criterios de Aceptación exactos en `infra/discordia-tp.md`, el estado actual en `estado-historias.md` y los nodos involucrados en `Backlog.json`.
2. **Reglas por servicio:** Si trabajás en un repo con su propio `AGENTS.md` (p. ej. `profile/AGENTS.md`), leelo primero. Leé 2 carpetas recientes de `<servicio>/specs/` para respetar numeración correlativa y secciones.
3. **Estado Git y PRs abiertos:** En cada repo afectado verificá ramas y PRs abiertos:
   ```powershell
   git -C <repo> fetch origin
   gh pr list -R fiuba-IS2-Discordia/<repo> --state open
   ```
   - Si la feature depende de un PR abierto aún no mergeado, **apilá** la nueva rama sobre la rama `headRefName` de ese PR base.
   - Si no depende de ninguno, partí de `origin/develop` (salvo `infra`, que usa únicamente `main`).
   - Si hay otro PR abierto tocando los mismos archivos (ej. routers o archivos de test en `gateway`), indicá en una nota `[!NOTE]` dónde ubicar el código nuevo para evitar conflictos de merge.

### 2. Redacción del plan

Instanciá la estructura completa de [plan-template.md](./references/plan-template.md), respetando todas sus secciones en este orden:

1. **Descripción del Objetivo** (HUs con puntos obligatorios/optativos, pendientes `TSK-*` que se resuelven e impacto en el puntaje de `estado-historias.md`).
2. **Decisiones de Diseño Acordadas** (alerta `[!IMPORTANT]` con invariantes de dominio, persistencia/concurrencia y privacidad del backlog) + **Topología de Ramas y Pull Requests** en un diagrama `mermaid` (`flowchart LR` con un `subgraph` por repositorio).
3. **Cambios Propuestos por Etapa** (etapas numeradas en orden de dependencia; dentro de cada etapa, subsección por repositorio indicando rama y base, archivos `[NEW]` / `[MODIFY]` con links `file:///...`, contratos/reglas exactas, tests y **Secuencia de commits atómicos**).
4. **Plan de Verificación** (comandos de linter, tipos, tests/cobertura por stack, auditoría anti-fuga de `TSK-*`/coautoría IA y pasos de prueba manual E2E).
5. **Etapa N-1 — Publicación de Pull Requests** (push en orden topológico de ramas base a ramas apiladas y creación con `gh pr create` en PowerShell siguiendo la plantilla de `AGENTS.md`, únicamente cuando toda la verificación previa esté en verde).
6. **Etapa N — Cierre de Backlog y Actualización de `estado-historias.md`** (edición JSON parseada de `Backlog.json` con los números `#PR` reales recién creados y actualización de tablas/totales en `estado-historias.md`).

### 3. Ejecución del plan aprobado

Una vez que el usuario aprueba el plan:

1. Creá cada rama desde la base acordada actualizada.
2. En cada etapa/repositorio, generá primero la spec/ADR y realizá **commits atómicos** a medida que completás cada unidad lógica (`docs`, `feat`, `test`), verificando que no se agreguen trailers `Co-authored-by`.
3. Ejecutá todos los linters, chequeos de tipos y suites de tests del servicio antes de avanzar o pushear.
4. Ejecutá la auditoría de privacidad (`git -C <repo> log` y `git -C <repo> diff <base>...HEAD`) confirmando ausencia total de `TSK-`, `Backlog.json` y firmas de IA.
5. Pusheá las ramas en orden topológico y publicá todos los PRs con `gh pr create --body-file ...` desde PowerShell.
6. Actualizá `Backlog.json` (lectura completa → modificación en memoria → `JSON.stringify(data, null, 2) + "\n"` → re-parseo de validación) con los `#PR` reales y actualizá `estado-historias.md`.

## Referencias

- [plan-template.md](./references/plan-template.md) — Plantilla Markdown completa con todas las secciones obligatorias, bloques de commits atómicos, recetas de verificación por stack y etapa de publicación de PRs.

