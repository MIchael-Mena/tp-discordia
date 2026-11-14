---
trigger: always_on
---

# Protocolo de Costo de Entorno y Verificación

La máquina es de la persona desarrolladora y no está dedicada a esta tarea: consume CPU, disco y batería que no se recuperan. La regla es **obtener la misma evidencia con el menor costo**, no correr todo "por las dudas".

Esta regla es la **única fuente de verdad** sobre aislamiento del árbol de trabajo, dependencias y compuerta pre-PR. Las skills y `AGENTS.md` la referencian; no duplican su política.

## 1. Instalar dependencias sólo si hace falta

Antes de cualquier instalación, comprobá si la rama destino cambia dependencias respecto de la rama a la que corresponde el `node_modules` actual:

```powershell
git --no-pager diff --name-only <rama-del-entorno> <rama-destino> -- package.json package-lock.json
```

| Resultado | Qué hacer |
|---|---|
| Vacío | **No instalar nada.** El `node_modules` existente ya es válido |
| Sólo `package.json` | `npm install --prefer-offline --no-audit --no-fund` |
| `package-lock.json` cambió | lo mismo (aplica el delta). `npm ci` sólo para validar lock ↔ package.json |
| CI | `npm ci --no-audit --no-fund` |

- `npm ci` **borra y recrea** `node_modules` (≈200k archivos en los clientes Expo): es el comando de CI, no el comando local por defecto.
- Al volver a la rama original tras una instalación por cambio de lockfile, **no reinstales automáticamente**: avisá "`node_modules` quedó de la rama X; corré `npm install` si el lockfile difiere".
- Python (`gateway`, `profile`, `auth-service`, `text-channel`, `voice-calls`, `notifications`): `uv run pytest` / `uv run ruff` ya resuelven el entorno. No antepongas `uv sync` ni `pip install -r` preventivos.
- Java (`server`): Gradle reutiliza el cache; no agregues `--refresh-dependencies` salvo problema de resolución real.

## 2. Presupuesto de verificación

| Momento | Qué correr |
|---|---|
| Cada iteración / hipótesis | sólo el archivo de test tocado (`npx jest src/core/chat/useDirectChat.test.ts`, `uv run pytest tests/unit/test_x.py -q`, `.\gradlew.bat test --tests "..."`) |
| Antes de cada commit atómico | los tests del módulo, no la suite entera |
| Al cerrar, antes de publicar | la **compuerta pre-PR** (sección 3), una sola vez por estado final de rama/PR; reutilizar resultados para el mismo SHA |

- Demostrar que un test de regresión falla en el código viejo requiere **un** experimento por hallazgo, no una corrida completa por commit.
- Evitá cobertura durante pruebas dirigidas salvo necesidad explícita: multiplica el tiempo del runner. Para publicar PRs de servicios Python, verificá en la suite completa el mínimo de cobertura >= 70% exigido por `AGENTS.md`; aprovechá la configuración del servicio y no repitas la medición sin necesidad.
- Si el runner satura la máquina: `npx jest --silent --maxWorkers=50%`.
- No relances una suite que ya está corriendo por un comando tuyo: leé su salida con `read_powershell`.
- Es legítimo cerrar con "los `@QuarkusTest` no corrieron (Docker apagado); CI está verde", informándolo, en vez de forzar la suite.

## 3. Compuerta pre-PR

**Ningún `git push` de una rama de PR ni `gh pr create` sin que la compuerta haya pasado localmente sobre el SHA a publicar.** Si cambia el SHA después de pasar, la evidencia deja de valer para los archivos afectados.

| Stack | Comandos (desde la raíz del repo) |
|---|---|
| Python (`gateway`, `profile`, `auth-service`, `text-channel`, `voice-calls`, `notifications`) | `uv run ruff check .` · `uv run pytest` (suite completa; la cobertura >= 70% la fija la config del servicio) · `uv run lint-imports` si el servicio lo define |
| Java (`server`) | `$env:_JAVA_OPTIONS="-Duser.timezone=UTC"; .\gradlew.bat test` (los `@QuarkusTest` requieren Docker) |
| `web-client` | `npx tsc --noEmit` · `npm run lint` · `npx jest --silent --maxWorkers=50%` |
| `backoffice` | `npm run typecheck` · `npm run lint` · `$env:CI="true"; npm test -- --maxWorkers=50%` |
| `infra` | sin suite; si cambió `compose.prod.yaml`, verificar la regla de oro de Compose (`AGENTS.md` §6) |

Además, antes de publicar:

- **Auditoría de privacidad** sobre `git log <base>..HEAD` y `git diff <base>...HEAD`: sin `TSK-`, `Backlog.json` ni trailers `Co-authored-by`/firmas de IA.
- **Árbol limpio** (`git status -sb`) y SHA local = SHA verificado.

Si un gate falla, **no publiques**: corregí y repetí sólo lo afectado, o informá la causa. Si un gate no puede correr (p. ej. Docker apagado), decilo explícitamente y pedí confirmación antes de publicar; nunca lo reportes como pasado. Detalles y trampas por stack: [`verification-recipes.md`](../skills/reviewing-discordia-prs/references/verification-recipes.md) (sección *Gates por stack*).

## 4. Aislamiento del árbol de trabajo

**Por defecto se trabaja directamente sobre la rama con `git switch`, sin worktree.** Es más barato, conserva `node_modules` y no deja residuos.

### 4.1 Estado inicial

Al empezar, registrá la rama actual y `git status -sb`. Corré `git worktree list` y anotalo **sólo si hay más de un worktree** (otra rama puede estar ocupada); registrá remotos **sólo** cuando el PR provenga de un fork o de otro repositorio.

### 4.2 Árbol sucio

Si hay cambios sin commitear y hay que cambiar de rama, **detenete antes de cambiar** y mostrá `git status -sb` y un resumen del diff (`git diff --stat`). Ofrecé con la herramienta de preguntas:

1. **Me encargo yo:** el agente espera.
2. **Guardar (stash):** `git stash push -u -m "agent: <tarea>"`. Se restaura con `git stash pop` sobre la rama original al terminar, verificando que sea la entrada creada por la tarea; ante conflicto, detenete e informá.
3. **Descartar:** sólo tras confirmación explícita que **liste los archivos afectados** (incluidos los no rastreados). Nunca descartes por iniciativa propia.

No cambies de rama ni descartes nada sin una de estas respuestas. Si la tarea ya transcurre en la rama con los cambios del usuario, no hace falta cambiar de rama.

### 4.3 Cambio de rama

- Para **leer** un PR no hace falta tocar el repo: `gh pr diff`, `gh pr view` y `git show <ref>:<ruta>` (ver [`verification-recipes.md`](../skills/reviewing-discordia-prs/references/verification-recipes.md)).
- Hacé `git switch` sólo para **ejecutar** tests/lint/typecheck o **modificar** la rama. Para sólo ejecutar, preferí `git switch --detach` sobre el SHA verificado: no crea ni ocupa ramas locales.
- **Anti-buffer-sucio:** inmediatamente después de cada `git switch`, corré `git status -sb`. El editor puede reaplicar sobre la rama nueva cambios de un buffer abierto; si reaparece como modificado un archivo que ya está commiteado y que no tocaste en esta rama, restauralo con `git restore -- <archivo>`. Nunca restaures archivos con cambios reales del usuario ni con `git checkout -- .`.
- No uses `-B`, `--force` ni `git reset --hard` para cambiar de rama.

### 4.4 Worktree (excepción)

**Nunca automático.** Proponelo y esperá el OK del usuario sólo si:

1. hay agentes, subagentes o swarm **editando en paralelo** sobre el mismo repo,
2. se necesitan **dos ramas vivas a la vez**, o
3. hay un **dev server/watcher** corriendo sobre la rama.

Si se aprueba: ruta **corta** (`C:\wt\<repo>-<n>`) para evitar `Filename too long`; un worktree nace sin `node_modules` (aplicá la sección 1; no hagas junction hacia el `node_modules` original); retiralo al terminar con `git -C <repo> worktree remove <ruta-exacta>` sin `--force` y verificá `git worktree list`. Si falla, informá ruta y error; no recurras a borrado recursivo (sección 5).

### 4.5 Cierre

Volvé a la rama original, corré `git status -sb` y verificá que coincide con el estado registrado al inicio (salvo lo que el usuario autorizó cambiar). Si hiciste stash, confirmá que se restauró. Reportá el estado final por repo en una línea.

## 5. Borrado de directorios en Windows

**Prohibido** invocar `cmd.exe` con comillas escapadas por `\`:

```powershell
& $env:ComSpec /c "rmdir /s /q \"$p\""   # MAL
```

PowerShell **no** escapa comillas con `\`: el argumento llega malformado y el `rmdir` puede ejecutarse sobre una ruta padre (ya pasó con `C:\`). No sustituyas un fallo de limpieza por `robocopy /MIR` ni por borrado recursivo automático. Verificá la ruta exacta y la propiedad de cada recurso; si no podés retirarlo sin riesgo, detenete e informá.

## 6. Recursos vivos

- Nada de procesos `detach` para pruebas puntuales: verificar y bajar con `Stop-Process -Id <PID>`.
- Un servidor o watcher que quede vivo al cerrar la tarea es un hallazgo propio, no un efecto colateral aceptable.
- Al terminar, retirar sólo scripts, payloads y (si se aprobaron) worktrees propios cuando sea seguro, informar cualquier residuo y confirmar que no quedó ningún proceso hijo de los comandos lanzados.
