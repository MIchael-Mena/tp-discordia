---
name: reviewing-discordia-prs
description: 'Revisar pull requests propios o de compañeros en los repositorios de Discordia (server, gateway, profile, auth-service, text-channel, web-client, voice-calls, notifications, backoffice, infra): verificar si las decisiones están justificadas, detectar errores de ingeniería y oportunidades de refactor (Clean Architecture, SOLID, DRY), proponer mejoras de forma interactiva en PRs propios o publicar comentarios accionables en PRs del equipo. Use when: revisar un PR, hacer code review, evaluar comentarios recibidos en un PR propio, auditar o refactorizar un cambio antes de mergear, o revisar un feature apilado (stacked) entre servicios.'
argument-hint: '<repo>#<número> [repo2#número2...] — p. ej. server#10 o server#32 gateway#61 backoffice#3'
---

# Revisar PRs de Discordia

Code review y auditoría de ingeniería en microservicios y clientes del TP: **nunca afirmar un defecto sin evidencia reproducible**, evaluar tanto correctitud funcional como calidad arquitectónica/refactorización, y adaptar la salida según si el PR es **propio** o **de otro integrante del equipo**.

## Cuándo usar

- "Revisá el PR #N de `<repo>`" / "dale una revisión a este PR" / "¿están bien las decisiones de este PR?"
- Revisar un **PR propio** para encontrar bugs, huecos de contrato o refactors de arquitectura/clean code antes de mergear.
- Evaluar **comentarios de review recibidos en un PR propio** para decidir si corresponde refactorizar o responder con justificación técnica.
- Features fullstack o que cruzan múltiples servicios con PRs relacionados (p. ej. `server` + `gateway` + `backoffice` / `web-client`), evaluando contratos y orden de merge conjunto.
- Antes de mergear una feature que cruza servicios (`server` ↔ `gateway` ↔ `voice-calls` ↔ `web-client`).
- Un PR apilado (stacked) cuya base todavía no está en `develop`.

## Reglas de oro

1. **Detectar autoría primero (PR propio vs. PR de compañero):**
   - **Si el PR es del usuario (`author.login` coincide con `gh api user --jq .login`):** **NO dejar comentarios en GitHub**. El objetivo es buscar errores, huecos de contrato y oportunidades de refactor siguiendo las mejores prácticas de ingeniería de software (Clean Architecture, SRP, DRY, separación vista/modelo, custom hooks, estilos desacoplados). Presentá el diagnóstico y **usá `ask_question` para consultar qué propuestas de corrección o refactor aplicar** antes de modificar código (salvo que el usuario ya haya ordenado explícitamente aplicar y pushear todo directo, en cuyo caso consultá sólo si hay decisiones de diseño ambiguas).
   - **Si el PR es de otro compañero:** Entregá el informe en el chat y publicá comentarios en GitHub **sólo** con aprobación explícita del usuario. Si pide ajustes al texto, corregí y volvé a mostrar antes de publicar.
2. **No ensuciar el working tree del usuario.** Si sólo vas a inspeccionar o el repo local tiene cambios sin commitear en otra rama, usá un worktree temporal. Si aplicás cambios y pusheás, verificá al final que `git status -sb` quede completamente limpio (sin diffs fantasma de `LF`/`CRLF`).
3. **Sin evidencia no hay hallazgo.** Si no podés reproducirlo (test, grep, probe, lectura del código de la librería instalada), degradalo a pregunta o descartalo.
4. **Nunca** referenciar `Backlog.json`/`TSK-*` ni proponer "crear un ticket": el backlog es seguimiento local del usuario.
5. Comentarios y mensajes en **español (es-AR)**.

## Procedimiento

### 1. Contexto (antes de leer código)

```powershell
gh api user --jq .login
gh pr view <n> -R fiuba-IS2-Discordia/<repo> --json number,title,state,author,baseRefName,headRefName,additions,deletions,changedFiles,mergeable,body
gh pr checks <n> -R fiuba-IS2-Discordia/<repo>
gh pr diff <n> -R fiuba-IS2-Discordia/<repo> --name-only
# Si se pide revisar comentarios recibidos en el PR:
gh api repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/reviews
gh api repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/comments --paginate
```

Mirá de entrada:

- **Autoría y modo de operación**: determiná si `author.login` es el usuario actual (**Modo Autor**) o un compañero (**Modo Revisor**), y si hay comentarios de terceros pendientes de evaluar.
- **`baseRefName` distinto de `develop`** → PR apilado. Verificá si la base avanzó desde que se abrió (`mergeable: CONFLICTING` es bloqueante).
- **PRs hijos apilados sobre este PR**: corré `gh pr list -R fiuba-IS2-Discordia/<repo> --state open --json number,headRefName,baseRefName` para saber si hay ramas apiladas encima que requerirán rebase si este PR suma commits.
- **`mergeable`**: `CONFLICTING` = no se puede mergear, por más que el código esté bien.
- **Frescura del CI**: compará el `updatedAt` de los runs con el último commit de la base. Un check verde viejo no representa el merge.
- **PRs hermanos abiertos**: dos PRs que implementan lo mismo son un hallazgo de coordinación (ver catálogo, H1).
- **Revisión multi-PR / fullstack**: Si se revisan varios PRs de una misma HU o feature (p. ej. `server#32`, `gateway#61`, `backoffice#3`), relacioná los números, extraé los criterios de aceptación compartidos (de `infra/discordia-tp.md` o specs), verificá contratos de punta a punta y definí el orden de despliegue/merge.

### 2. Aislar el código

```powershell
# Solo lectura y verificación:
git -C <repo> worktree add "$env:TEMP\<pr>" origin/<headRefName> --detach

# Si el usuario pide aplicar correcciones y commitear en la rama del PR:
git -C <repo> worktree add "$env:TEMP\<pr>" -b <headRefName> origin/<headRefName>
```

Trabajá siempre ahí. Al terminar, borrá el worktree y los temporales (receta con `node_modules` en [verification-recipes.md](./references/verification-recipes.md)).

### 3. Leer

1. El diff completo (`gh pr diff`) para el mapa de cambios.
2. Los archivos completos **en el worktree** (el diff esconde el contexto que explica el bug).
3. Los specs del PR (`specs/<feature>/`) para comparar lo prometido contra lo implementado.
4. **El otro lado de cada contrato**: si el PR consume una API, leé el productor; si la expone, leé el consumidor. La mitad de los hallazgos están ahí.
5. **Calidad de diseño y oportunidades de refactor**: evaluá adherencia a Clean Architecture y buenas prácticas del stack (en backend: puertos sin métodos `default` mudos en adaptadores reales, casos de uso desacoplados; en frontend: lógica pura en `src/core/`, efectos/paginación/WebSockets en custom hooks reutilizables, componentes cortos con una sola responsabilidad, `StyleSheet.create` en `src/styles/`). Ver sección **I** de [findings-catalog.md](./references/findings-catalog.md).

### 4. Verificar

Corré los gates del repo y, cuando un hallazgo dependa de comportamiento de una librería, **leelo o ejecutalo**. Recetas concretas en [verification-recipes.md](./references/verification-recipes.md).

### 5. Clasificar

| Prioridad | Qué entra |
|---|---|
| **P1 · antes del merge** | Bypass o ausencia real de autorización; pérdida/fuga de datos; recurso que queda vivo tras un error (micrófono, sesión, sala); contrato roto que deja un consumidor ya mergeado sin funcionar; producción/despliegue que no puede arrancar; el PR no mergea (conflictos). Tag inline: `[Prioridad 1 · bloqueante]` o `[Bloqueante · <categoría>]`. |
| **P2 · conviene en este PR** | Correctitud que va a morder pronto (mapeo de errores incompleto, carrera, timeout que no acota, condición de borde sin cubrir), criterios de aceptación declarados que no se verifican, fragilidad estructural con fix barato. **Evitá la etiqueta genérica `[Prioridad 2]`** (puede ser confusa y poco informativa, especialmente cuando no hay P1s); usá **etiquetas semánticas por categoría** (p. ej. `[Bugfix de UI / Paginación]`, `[Alineación con dominio]`, `[Cobertura de tests]`, `[Robustez / Fallback]`, `[Contrato API]`). |
| **Refactor / Diseño · buenas prácticas** | Acoplamiento entre vista y lógica de negocio, duplicación de hooks/efectos o paginación, componentes monolíticos con múltiples responsabilidades, estilos inline fuera de `src/styles/`, o deuda de Clean Architecture. Tag: `[Refactor · <categoría>]` (p. ej. `[Refactor · Clean Architecture / Core]`, `[Refactor · Custom Hook / DRY]`, `[Refactor · Modularización UI]`). |
| **P3 · nit** | Deriva de documentación, nombres, UX, accesibilidad, estilo, código muerto. Tag inline: `[Nit · <tema>]` o `[Nit]`. |

Regla de honestidad: si una decisión es **defendible pero su justificación escrita es falsa**, decilo así — separá la decisión de su fundamento. Es un hallazgo de P1/P2 aunque el código esté bien.

### 6. Informe (chat)

Estructura fija, en este orden:

1. **Veredicto** en 3-5 líneas: qué tan sólido es el PR y qué lo bloquea, si algo. Si es multi-PR, incluí un resumen global y el desglose por repo.
2. **Agradecimiento concreto**: 3-6 cosas que están bien y no hay que tocar (con nombre y archivo). Nunca un review sin esto.
3. **Decisiones del PR**: tabla `decisión · ¿correcta? · comentario`. Ahí se responde "¿están justificadas?".
4. **Hallazgos y Propuestas de Refactor** ordenados por prioridad/categoría (`P1`, `P2`, `Refactor / Diseño`, `P3`), cada uno con `archivo:línea`, evidencia y cambio propuesto. (Si se están evaluando comentarios de un revisor externo en un PR propio, estructurá esta sección respondiendo punto por punto cada comentario del revisor: si amerita refactor o si el diseño actual es válido).
5. **Verificación hecha**: qué corriste y qué resultado dio (tests, cobertura, probe, lint, typecheck).
6. **Observaciones de cadena** que no son defectos de este PR (contratos cruzados, orden de merge, PRs apilados afectados).
7. **Cierre interactivo según autoría (usando `ask_question`)**:
   - **Si el PR es PROPIO (Modo Autor):**
     - **No armes plan de comentarios para GitHub.**
     - Presentá las propuestas de corrección y refactor numeradas y cerrá con `ask_question` para que el usuario elija cuáles aplicar (p. ej.: `(Recommended) Aplicar todos los fixes y refactors propuestos y subir al PR`, `Aplicar sólo correcciones de bugs/contratos (P1/P2)`, `Elegir propuestas puntuales`, `No aplicar cambios (sólo informe / texto de respuesta)`). Si algún refactor admite más de una alternativa de diseño, incluí la pregunta de diseño con tu opción recomendada.
   - **Si el PR es de un COMPAÑERO (Modo Revisor):**
     - Incluí el **Plan de comentarios**: tabla `# · archivo:línea · tema · etiqueta` + una línea diciendo qué va en el body.
     - Cerrá con `ask_question` ofreciendo el alcance a publicar en GitHub (todo / sin nits / sólo bloqueantes / nada).

### 7. Ejecutar acción aprobada (Aplicar en PR propio vs. Publicar review en PR ajeno)

#### Caso A: PR propio — Aplicar fixes/refactors aprobados y propagar a PRs apilados
1. Aplicá los fixes y refactors aprobados respetando las convenciones del repo (tests unitarios para toda lógica extraída a `src/core/` o casos de uso, sin romper tests existentes).
2. Corré todos los gates del stack (`ruff` + `pytest`, `gradlew test`, o `tsc --noEmit` + `npm run lint` + `jest`).
3. Creá commits atómicos en español (`fix(<scope>): ...`, `refactor(<scope>): ...`, `test(<scope>): ...`, sin `Co-authored-by` de IA) y hacé `git push` a la rama del PR.
4. **Propagación a PRs apilados (Stacked PRs):** Si en el Paso 1 detectaste PRs abiertos cuya base (`baseRefName`) es la rama que acabás de actualizar, hacé rebase de cada rama hija sobre la nueva punta (`git rebase origin/<rama-base>`), corré sus gates y actualizala con `git push --force-with-lease`.
5. Si la revisión partió de comentarios de un compañero, entregá en el chat el texto sugerido de respuesta (en `es-AR`) explicando qué se refactorizó (con el hash del commit) o la justificación técnica de por qué se mantuvo una decisión.

#### Caso B: PR de compañero — Publicar review en GitHub (con aprobación)

Un solo POST de review con `event: COMMENT`; los inline van dentro de `comments` (formato en [comment-style.md](./references/comment-style.md)).

- Verificá que cada `line` sea una línea **agregada** del diff; si no, GitHub rechaza el comentario o lo ancla mal.
- **Si el usuario instruye aplicar los fixes y commitear en la rama**: incluí en el cuerpo del comentario inline la cláusula de resolución explícita: `Se aplica el fix/test directamente en esta rama (commit <hash>).`
- Para evitar errores de parseo JSON (`HTTP 400 Problems parsing JSON`) en Windows/PowerShell, generá el payload con Node.js o Python en UTF-8 sin BOM y usá `gh api --input` (receta en [verification-recipes.md](./references/verification-recipes.md)).
- Después de publicar, leé los comentarios por API y confirmá cuántos quedaron y en qué línea.
- Si un nit queda fuera de la review (por ejemplo agregado después), publicalo como comentario suelto y avisá que no aparece dentro del bloque de la review.

### 8. Cerrar

Borrá worktree y temporales, y confirmá que el repo del usuario sigue en su rama y limpio (`git status -sb` sin archivos modificados ni diffs de `LF`/`CRLF`).

## Referencias

- [findings-catalog.md](./references/findings-catalog.md) — las fallas que ya aparecieron en esta cadena, con ejemplo y cómo detectarlas rápido.
- [verification-recipes.md](./references/verification-recipes.md) — comandos por stack, cómo probar comportamiento real y trampas de Windows.
- [comment-style.md](./references/comment-style.md) — formato del body y de los inline, y el payload de la API.

## Checklist mínimo (si no hay tiempo para nada más)

- [ ] ¿La autorización real existe? (no `return true`, no "existe el canal ⇒ permitido")
- [ ] ¿Los ids que entran por la URL se validan antes de interpolarse en otra URL?
- [ ] ¿Lo que la doc dice "interno" es realmente inalcanzable desde afuera? (`infra/compose.prod.yaml`, labels de Traefik)
- [ ] ¿Cada knob de config (`*_TTL_*`, `*_TIMEOUT_*`, `*_URL`) tiene efecto observable?
- [ ] ¿El esquema nuevo se aplica a bases que ya existen? (init script ≠ migración)
- [ ] ¿Los tests fijan el contrato **real** del otro servicio, y verifican las propiedades de seguridad (no sólo el status)?
- [ ] ¿Un error en el camino común libera el recurso? (sala, socket, stream, sesión)
