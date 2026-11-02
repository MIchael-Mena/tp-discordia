---
name: reviewing-discordia-prs
description: 'Revisar pull requests de los repositorios de Discordia (server, gateway, profile, auth-service, text-channel, web-client, voice-calls, infra): verificar si las decisiones están justificadas, detectar errores graves de ingeniería, priorizar hallazgos y publicar comentarios accionables. Use when: revisar un PR, hacer code review, dejar comentarios en un pull request, auditar un cambio antes de mergear, evaluar una decisión de diseño, revisar un feature apilado (stacked) entre servicios, o corregir un PR ya abierto.'
argument-hint: '<repo>#<número> [repo2#número2...] — p. ej. server#10 o server#32 gateway#61 backoffice#3'
---

# Revisar PRs de Discordia

Code review de un microservicio del TP con el criterio del equipo: **primero el informe, después los comentarios**, y nunca afirmar un defecto sin evidencia reproducible.

## Cuándo usar

- "Revisá el PR #N de `<repo>`" / "dale una revisión a este PR" / "¿están bien las decisiones de este PR?"
- Features fullstack o que cruzan múltiples servicios con PRs relacionados (p. ej. `server` + `gateway` + `backoffice` / `web-client`), evaluando contratos y orden de merge conjunto.
- Antes de mergear una feature que cruza servicios (`server` ↔ `gateway` ↔ `voice-calls` ↔ `web-client`).
- Un PR apilado (stacked) cuya base todavía no está en `develop`.

## Reglas de oro

1. **Informe antes que comentarios.** Entregá el informe en el chat; publicá en GitHub **sólo** con aprobación explícita. Si el usuario pide ajustes al texto, corregí y volvé a mostrar antes de publicar.
2. **No tocar el working tree del usuario.** Todo se lee y se corre en un worktree temporal.
3. **Sin evidencia no hay hallazgo.** Si no podés reproducirlo (test, grep, probe, lectura del código de la librería instalada), degradalo a pregunta o descartalo.
4. **Nunca** referenciar `Backlog.json`/`TSK-*` ni proponer "crear un ticket": el backlog es seguimiento local del usuario.
5. Comentarios y mensajes en **español (es-AR)**.

## Procedimiento

### 1. Contexto (antes de leer código)

```powershell
gh pr view <n> -R fiuba-IS2-Discordia/<repo> --json number,title,state,author,baseRefName,headRefName,additions,deletions,changedFiles,mergeable,body
gh pr checks <n> -R fiuba-IS2-Discordia/<repo>
gh pr diff <n> -R fiuba-IS2-Discordia/<repo> --name-only
```

Mirá de entrada:

- **`baseRefName` distinto de `develop`** → PR apilado. Verificá si la base avanzó desde que se abrió (`mergeable: CONFLICTING` es bloqueante).
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

### 4. Verificar

Corré los gates del repo y, cuando un hallazgo dependa de comportamiento de una librería, **leelo o ejecutalo**. Recetas concretas en [verification-recipes.md](./references/verification-recipes.md).

### 5. Clasificar

| Prioridad | Qué entra |
|---|---|
| **P1 · antes del merge** | Bypass o ausencia real de autorización; pérdida/fuga de datos; recurso que queda vivo tras un error (micrófono, sesión, sala); contrato roto que deja un consumidor ya mergeado sin funcionar; producción/despliegue que no puede arrancar; el PR no mergea (conflictos). Tag inline: `[Prioridad 1 · bloqueante]` o `[Bloqueante · <categoría>]`. |
| **P2 · conviene en este PR** | Correctitud que va a morder pronto (mapeo de errores incompleto, carrera, timeout que no acota, condición de borde sin cubrir), criterios de aceptación declarados que no se verifican, fragilidad estructural con fix barato. **Evitá la etiqueta genérica `[Prioridad 2]`** (puede ser confusa y poco informativa, especialmente cuando no hay P1s); usá **etiquetas semánticas por categoría** (p. ej. `[Bugfix de UI / Paginación]`, `[Alineación con dominio]`, `[Cobertura de tests]`, `[Robustez / Fallback]`, `[Contrato API]`). |
| **P3 · nit** | Deriva de documentación, nombres, UX, accesibilidad, estilo, código muerto. Tag inline: `[Nit · <tema>]` o `[Nit]`. |

Regla de honestidad: si una decisión es **defendible pero su justificación escrita es falsa**, decilo así — separá la decisión de su fundamento. Es un hallazgo de P1/P2 aunque el código esté bien.

### 6. Informe (chat)

Estructura fija, en este orden:

1. **Veredicto** en 3-5 líneas: qué tan sólido es el PR y qué lo bloquea, si algo. Si es multi-PR, incluí un resumen global y el desglose por repo.
2. **Agradecimiento concreto**: 3-6 cosas que están bien y no hay que tocar (con nombre y archivo). Nunca un review sin esto.
3. **Decisiones del PR**: tabla `decisión · ¿correcta? · comentario`. Ahí se responde "¿están justificadas?".
4. **Hallazgos** ordenados por prioridad/categoría, cada uno con `archivo:línea`, evidencia y fix sugerido.
5. **Verificación hecha**: qué corriste y qué resultado dio (tests, cobertura, probe, lint, typecheck).
6. **Observaciones de cadena** que no son defectos de este PR (contratos cruzados, orden de merge).
7. **Plan de comentarios**: tabla `# · archivo:línea · tema · etiqueta` + una línea diciendo qué va en el body.
8. Cerrar con `ask_user` ofreciendo el alcance (todo / sin nits / sólo bloqueantes / nada).

### 7. Publicar (con aprobación)

Un solo POST de review con `event: COMMENT`; los inline van dentro de `comments` (formato en [comment-style.md](./references/comment-style.md)).

- Verificá que cada `line` sea una línea **agregada** del diff; si no, GitHub rechaza el comentario o lo ancla mal.
- **Si el usuario instruye aplicar los fixes y commitear en la rama**: incluí en el cuerpo del comentario inline la cláusula de resolución explícita: `Se aplica el fix/test directamente en esta rama (commit <hash>).`
- Para evitar errores de parseo JSON (`HTTP 400 Problems parsing JSON`) en Windows/PowerShell, generá el payload con Node.js o Python en UTF-8 sin BOM y usá `gh api --input` (receta en [verification-recipes.md](./references/verification-recipes.md)).
- Después de publicar, leé los comentarios por API y confirmá cuántos quedaron y en qué línea.
- Si un nit queda fuera de la review (por ejemplo agregado después), publicalo como comentario suelto y avisá que no aparece dentro del bloque de la review.

### 8. Cerrar

Borrá worktree y temporales, y confirmá que el repo del usuario sigue en su rama y limpio.

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
