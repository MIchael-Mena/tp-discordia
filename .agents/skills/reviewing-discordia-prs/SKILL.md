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
   - **Si el PR es del usuario (`author.login` coincide con `gh api user --jq .login`):** **NO dejar comentarios en GitHub**. El objetivo es buscar errores, huecos de contrato y oportunidades de refactor siguiendo las mejores prácticas de ingeniería de software. Presentá el diagnóstico y consultá con la herramienta interactiva disponible qué propuestas aplicar antes de modificar código (salvo que el usuario ya haya ordenado explícitamente aplicar y pushear todo directo, en cuyo caso consultá sólo si hay decisiones de diseño ambiguas).
   - **Si el PR es de otro compañero:** Entregá el informe en el chat y publicá comentarios en GitHub **sólo** con aprobación explícita del usuario. Si pide ajustes al texto, corregí y volvé a mostrar antes de publicar.
   - **Identidad incierta:** si falla la autenticación, falta el autor o hay dudas sobre qué cuenta representa al usuario, consultá antes de elegir modo. Una cuenta autenticada distinta no demuestra por sí sola que el PR sea ajeno.
2. **Preservar el working tree del usuario (sin worktree por defecto).** Seguí [env-cost.md](../../rules/env-cost.md) §4: registrá rama actual y `git status -sb` (y `git worktree list` sólo si hay más de uno). Leé el PR primero sin tocar el repo (`gh pr diff`, `git show`); hacé `git switch` sólo si necesitás ejecutar tests/lint/typecheck o modificar la rama, aplicando antes el protocolo de árbol sucio y la regla anti-buffer-sucio. Al cerrar, volvé a la rama original y verificá que el estado inicial se conserve.
3. **Sin evidencia no hay hallazgo.** Si no podés reproducirlo (test, grep, probe, lectura del código de la librería instalada), degradalo a pregunta o descartalo.
4. **Nunca** referenciar `Backlog.json`/`TSK-*` ni proponer "crear un ticket": el backlog es seguimiento local del usuario.
5. Comentarios y mensajes en **español (es-AR)**.

## Procedimiento

### 1. Contexto (antes de leer código)

```powershell
gh api user --jq .login
gh pr view <n> -R fiuba-IS2-Discordia/<repo> --json number,title,state,author,baseRefName,baseRefOid,headRefName,headRefOid,headRepositoryOwner,headRepository,isCrossRepository,additions,deletions,changedFiles,mergeable,body
gh pr checks <n> -R fiuba-IS2-Discordia/<repo>
gh pr diff <n> -R fiuba-IS2-Discordia/<repo> --name-only
# Si se pide revisar comentarios recibidos en el PR:
gh api repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/reviews --paginate
gh api repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/comments --paginate
gh api repos/fiuba-IS2-Discordia/<repo>/issues/<n>/comments --paginate
```

Mirá de entrada:

- **Autoría y modo de operación**: verificá la identidad conforme a las reglas de oro y si hay comentarios de terceros pendientes de evaluar.
- **Base y cadena**: la rama de integración habitual es `main` para `infra` y `develop` para los demás; contemplá excepciones como releases o hotfixes. Una base distinta no demuestra por sí sola que el PR esté apilado: comprobá si corresponde a la rama cabeza de otro PR.
- **PRs hijos apilados sobre este PR**: consultá los PRs abiertos y relacioná repositorio y rama de base con repositorio y rama de cabeza. Identificá descendientes, autoría y dependencias; no presupongas que deben rebasarse.
- **`mergeable`**: `CONFLICTING` = no se puede mergear; `UNKNOWN` no prueba que sea mergeable.
- **Frescura del CI**: verificá conclusión y SHA evaluado por los checks. Para afirmar que se probó la integración, comprobá que el merge o merge queue evaluado corresponda a los SHA actuales de cabeza y base; una fecha o check verde en la cabeza no basta. Informá cualquier dato no verificable.
- **PRs hermanos abiertos**: dos PRs que implementan lo mismo son un hallazgo de coordinación (ver catálogo, H1).
- **Revisión multi-PR / fullstack**: Si se revisan varios PRs de una misma HU o feature (p. ej. `server#32`, `gateway#61`, `backoffice#3`), relacioná los números, extraé los criterios de aceptación compartidos (de `infra/discordia-tp.md` o specs), verificá contratos de punta a punta y definí el orden de despliegue/merge.

### 2. Acceder al código (escalonado, sin worktree)

Seguí [env-cost.md](../../rules/env-cost.md) §4 y las recetas de [verification-recipes.md](./references/verification-recipes.md):

1. **Lectura sin tocar el repo (por defecto):** hacé `git fetch <remoto-base> refs/pull/<n>/head`, confirmá que `FETCH_HEAD` coincide con `headRefOid` e inspeccioná con `gh pr diff` y `git show <headRefOid>:<ruta>`.
2. **Ejecución de gates (`git switch --detach`):** sólo cuando haga falta correr tests/lint/typecheck. Si el árbol local está sucio, detenete y aplicá el protocolo de `env-cost.md` §4.2 antes de cambiar de rama; tras cada `git switch`, ejecutá `git status -sb` para limpiar cualquier archivo reaplicado por un buffer abierto del editor (`env-cost.md` §4.3).
3. **Modificación de rama (PR propio):** verificá repositorio de origen, permisos, estado local/remoto y que la rama no esté ocupada por otro worktree antes de hacer `git switch <rama>`. Si el PR cambia durante la revisión, actualizá el diagnóstico o informá qué SHA se revisó.

### 3. Leer

1. El diff completo (`gh pr diff`) para el mapa de cambios.
2. Los archivos completos (`git show <headRefOid>:<ruta>` o en la rama si ya hiciste `git switch`, porque el diff esconde el contexto que explica el bug).
3. Los specs del PR (`specs/<feature>/`) para comparar lo prometido contra lo implementado.
4. **El otro lado de cada contrato**: si el PR consume una API, leé el productor; si la expone, leé el consumidor. La mitad de los hallazgos están ahí.
5. **Calidad de diseño y oportunidades de refactor**: evaluá cohesión, responsabilidades, dependencias y duplicación según las convenciones comprobadas del repo. Proponé extracciones o patrones sólo cuando resuelvan un problema concreto y su beneficio justifique el costo. Ver sección **I** de [findings-catalog.md](./references/findings-catalog.md).
6. **Estilos en clientes**: compará los estilos nuevos con componentes similares, estilos compartidos y tokens del tema existentes. Proponé reutilizarlos cuando correspondan y eviten duplicación o inconsistencias visuales; los estilos específicos son válidos cuando el componente los necesita, pero en `web-client` deben ubicarse en un archivo aparte bajo `src/styles/`, no junto al componente. Verificá la convención del repositorio para otros clientes, fundamentá la propuesta con referencias concretas y evitá forzar una abstracción compartida innecesaria.

### 4. Verificar

Corré los gates del repo y, cuando un hallazgo dependa de comportamiento de una librería, **leelo o ejecutalo**. Recetas concretas en [verification-recipes.md](./references/verification-recipes.md).

### 5. Clasificar

| Prioridad | Qué entra |
|---|---|
| **P1 · antes del merge** | Bypass o ausencia real de autorización; pérdida/fuga de datos; recurso que queda vivo tras un error (micrófono, sesión, sala); contrato roto que deja un consumidor ya mergeado sin funcionar; producción/despliegue que no puede arrancar; el PR no mergea (conflictos). Tag inline: `[Prioridad 1 · bloqueante]` o `[Bloqueante · <categoría>]`. |
| **P2 · conviene en este PR** | Correctitud que va a morder pronto (mapeo de errores incompleto, carrera, timeout que no acota, condición de borde sin cubrir), criterios de aceptación declarados que no se verifican, fragilidad estructural con fix barato. **Evitá la etiqueta genérica `[Prioridad 2]`** (puede ser confusa y poco informativa, especialmente cuando no hay P1s); usá **etiquetas semánticas por categoría** (p. ej. `[Bugfix de UI / Paginación]`, `[Alineación con dominio]`, `[Cobertura de tests]`, `[Robustez / Fallback]`, `[Contrato API]`). |
| **Refactor / Diseño · buenas prácticas** | Acoplamiento, duplicación o responsabilidades mezcladas con un costo concreto; convenciones verificadas del repo cuando corresponda. Considerá alcance y costo del cambio. Tag: `[Refactor · <categoría>]` (p. ej. `[Refactor · Clean Architecture / Core]`, `[Refactor · Custom Hook / DRY]`, `[Refactor · Modularización UI]`). |
| **P3 · nit** | Deriva de documentación, nombres, UX, accesibilidad, estilo, código muerto. Tag inline: `[Nit · <tema>]` o `[Nit]`. |

Regla de honestidad: si una decisión es **defendible pero su justificación escrita es falsa**, separá la decisión de su fundamento. Clasificá según el impacto real de la afirmación y sus consecuencias, no automáticamente como P1/P2.

### 6. Informe (chat)

Estructura fija, en este orden:

1. **Veredicto** en 3-5 líneas: qué tan sólido es el PR y qué lo bloquea, si algo. Si es multi-PR, incluí un resumen global y el desglose por repo.
2. **Aciertos concretos**: destacá lo que verificaste que está bien, con nombre y archivo, sin inventar ni exigir una cantidad fija.
3. **Decisiones del PR**: tabla `decisión · ¿correcta? · comentario`. Ahí se responde "¿están justificadas?".
4. **Hallazgos y Propuestas de Refactor** ordenados por prioridad/categoría (`P1`, `P2`, `Refactor / Diseño`, `P3`), cada uno con `archivo:línea`, evidencia y cambio propuesto. (Si se están evaluando comentarios de un revisor externo en un PR propio, estructurá esta sección respondiendo punto por punto cada comentario del revisor: si amerita refactor o si el diseño actual es válido).
5. **Verificación hecha**: qué corriste y qué resultado dio (tests, cobertura, probe, lint, typecheck).
6. **Observaciones de cadena** que no son defectos de este PR (contratos cruzados, orden de merge, PRs apilados afectados).
7. **Cierre interactivo según autoría** (con la herramienta de preguntas disponible):
   - **Si el PR es PROPIO (Modo Autor):**
     - **No armes plan de comentarios para GitHub.**
     - Presentá las propuestas de corrección y refactor numeradas y consultá cuáles aplicar (p. ej.: `Aplicar todos los fixes y refactors propuestos y subir al PR`, `Aplicar sólo correcciones de bugs/contratos (P1/P2)`, `Elegir propuestas puntuales`, `No aplicar cambios`). Si algún refactor admite más de una alternativa de diseño, incluí la pregunta de diseño con tu opción recomendada.
   - **Si el PR es de un COMPAÑERO (Modo Revisor):**
     - Incluí el **Plan de comentarios**: tabla `# · archivo:línea · tema · etiqueta` + una línea diciendo qué va en el body.
     - Consultá el alcance a publicar en GitHub (todo / sin nits / sólo bloqueantes / nada).

### 7. Ejecutar acción aprobada (Aplicar en PR propio vs. Publicar review en PR ajeno)

#### Caso A: PR propio — Aplicar fixes/refactors aprobados y propagar a PRs apilados
1. Aplicá los fixes y refactors aprobados respetando las convenciones del repo (tests unitarios para toda lógica extraída a `src/core/` o casos de uso, sin romper tests existentes).
2. Ejecutá la **compuerta pre-PR** de [env-cost.md](../../rules/env-cost.md) §3 sobre el SHA final antes de hacer `git push`.
3. Creá commits atómicos en español (`fix(<scope>): ...`, `refactor(<scope>): ...`, `test(<scope>): ...`, sin `Co-authored-by` de IA) y hacé `git push` a la rama del PR sólo con la compuerta en verde.
4. **PRs apilados:** informá ramas hijas y posibles conflictos. Antes de reescribir o pushear cada rama, verificá su autoría, permisos y estado y obtené aprobación explícita para las ramas afectadas, salvo que el usuario ya haya autorizado expresamente esa propagación. Seguí las salvaguardas de [verification-recipes.md](./references/verification-recipes.md); ante conflicto o divergencia inesperada, detenete e informá.
5. Si la revisión partió de comentarios de un compañero, entregá en el chat el texto sugerido de respuesta (en `es-AR`) explicando qué se refactorizó (con el hash del commit) o la justificación técnica de por qué se mantuvo una decisión.

#### Caso B: PR de compañero — Publicar review en GitHub (con aprobación)

Un solo POST de review con `event: COMMENT`; los inline van dentro de `comments` (formato en [comment-style.md](./references/comment-style.md)).

- Antes de publicar, comprobá que los SHA de cabeza y base siguen siendo los revisados. Si cambiaron, actualizá el diagnóstico y obtené aprobación para cualquier cambio en los comentarios.
- Verificá que cada comentario esté anclado al lado y línea correctos del diff vigente; para líneas eliminadas usá el lado anterior cuando la API lo permita y, si no hay anclaje válido, describí el hallazgo en el body. Ver [comment-style.md](./references/comment-style.md).
- **Si el usuario instruye aplicar los fixes y commitear en la rama**: incluí en el cuerpo del comentario inline la cláusula de resolución explícita: `Se aplica el fix/test directamente en esta rama (commit <hash>).`
- Para evitar errores de parseo JSON (`HTTP 400 Problems parsing JSON`) en Windows/PowerShell, generá el payload con Node.js o Python en UTF-8 sin BOM y usá `gh api --input` (receta en [verification-recipes.md](./references/verification-recipes.md)).
- Después de publicar, leé los comentarios por API y confirmá cuántos quedaron y en qué línea.
- Si algún comentario aprobado no quedó publicado, informalo y consultá antes de publicar uno adicional fuera de la review.

### 8. Cerrar

Seguí [env-cost.md](../../rules/env-cost.md) §4.5 y §6: volvé a la rama original, ejecutá `git status -sb` (aplicando anti-buffer-sucio si hace falta), restaurá el stash si se creó uno, retirá archivos temporales propios de la revisión, confirmá que no quedaron procesos hijos vivos y reportá el estado final por repositorio en una línea.

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
