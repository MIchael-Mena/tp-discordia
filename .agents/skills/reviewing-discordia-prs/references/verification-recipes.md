# Recetas de verificación

Recetas para Windows + PowerShell. Sustituí los marcadores y verificá las precondiciones antes de ejecutar; no asumas que una ruta, rama o remoto pertenece a la tarea.

---

## Worktree aislado

Registrá `git status --short --branch` y `git worktree list` antes de empezar. Identificá el remoto que apunta al repositorio **base** del PR; no presupongas que es `origin`. Obtené `headRefOid` y `baseRefOid` de GitHub y recuperá la cabeza incluso si procede de un fork:

```powershell
git -C "<repo>" fetch "<remoto-base>" "refs/pull/<n>/head"
if ($LASTEXITCODE -ne 0) { throw "No se pudo obtener la cabeza del PR" }
$head = git -C "<repo>" rev-parse FETCH_HEAD
if ($LASTEXITCODE -ne 0 -or $head -ne "<headRefOid>") { throw "La cabeza no coincide con GitHub; volver a consultar el PR" }
$worktree = Join-Path $env:TEMP ("discordia-pr-<n>-" + [guid]::NewGuid().ToString("N"))
if (Test-Path -LiteralPath $worktree) { throw "La ruta temporal ya existe" }
git -C "<repo>" worktree add --detach $worktree $head
if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el worktree" }
```

Leé y verificá desde ese worktree. Para comparar con la base, obtené su commit del repositorio base y comprobá que coincide con `baseRefOid`; si cambia, volvé a obtener los datos. Registrá los SHA revisados. Si se van a aplicar cambios aprobados, verificá el repositorio y remoto de la cabeza, permisos de push, SHA remoto y estado local; no uses `-b` con una rama existente ni `-B`, `--force` o checkout de una rama ocupada. Si la rama local existe, usala sólo si está libre y coincide con el SHA revisado; si no existe, podés crearla en el worktree desde ese SHA. Ante divergencias, detenete y consultá. Para un fork, no pushees por defecto al remoto base.

Pero antes de instalar nada: **un worktree nace sin `node_modules`** (Node no sube hasta el repo original) y casi nunca hace falta crearlo.

```powershell
# Compará el commit que corresponde al node_modules existente con la cabeza revisada.
git --no-pager -C "<repo>" diff --name-only "<sha-entorno>" $head -- package.json package-lock.json
```

| Resultado | Qué hacer en el worktree |
|---|---|
| Vacío | Si el entorno existente está disponible y es compatible, linkear: `New-Item -ItemType Junction -Path (Join-Path $worktree "node_modules") -Target "<repo>\node_modules"` |
| Sólo `package.json` o `package-lock.json` | `npm install --prefer-offline --no-audit --no-fund` |
| Validar lock ↔ package.json, o CI | `npm ci --no-audit --no-fund` (borra y recrea: minutos de disco) |

Confirmá también versión de Node, plataforma y estado real de la instalación: un diff vacío no garantiza por sí solo que el entorno sea válido. Con junction, nunca corras `npm install` dentro del worktree: escribiría sobre el `node_modules` del repo original.

### Retirar el worktree

Confirmá que la ruta absoluta es exactamente la creada por esta tarea y figura en `git worktree list`. Inspeccioná su estado y archivos no rastreados o ignorados; preservá cualquier dato que no se pueda descartar con seguridad. Si creaste una junction, verificá que es esa junction y retirala **sin recorrer ni borrar su destino**. Luego intentá `git -C "<repo>" worktree remove "<ruta-exacta>"` sin `--force` y comprobá el código de salida y la lista de worktrees.

Si hay cambios sin guardar, rutas largas, dudas sobre la propiedad de archivos o falla el retiro, detenete e informá la ruta y el error; no uses `git checkout -- .`, borrado recursivo, `robocopy /MIR` ni `worktree prune` como solución automática. Retirá sólo temporales propios identificados. Compará rama y estado del repo original con los registrados al inicio.

### Propagar fixes/refactors a PRs apilados (Stacked PRs)

Un commit nuevo en la base no implica que todos los hijos requieran rebase. Identificá los descendientes y verificá si están afectados antes de proponer cambios.

```powershell
# 1. Detectar PRs abiertos apilados sobre la rama modificada
gh pr list -R fiuba-IS2-Discordia/<repo> --state open --limit 1000 --json number,author,headRefName,baseRefName,headRepositoryOwner,headRepository,isCrossRepository |
  ConvertFrom-Json | Where-Object { $_.baseRefName -eq "<baseBranch>" }
```

Comprobá los repositorios además de los nombres de rama y consultá más resultados si la lista está truncada. Mostrá ramas, autores y acciones propuestas; antes de reescribir historia o hacer push obtené aprobación explícita para las ramas afectadas, salvo autorización expresa previa. Verificá permisos, ausencia de cambios locales y SHA remoto de cada rama. Si están aprobadas, procesalas en orden de dependencia, ejecutá los gates y usá `--force-with-lease` con la referencia y el SHA remoto esperados explícitamente; ante divergencia, conflicto o fallo detenete e informá. No asumas autorización sobre ramas de compañeros.
---

## Costo de verificación

La máquina es de la persona usuaria: misma evidencia, menos CPU.

| Momento | Qué correr |
|---|---|
| Cada iteración / hipótesis | sólo el archivo de test tocado |
| Antes de cada commit atómico | los tests del módulo |
| Una sola vez, al cerrar | suite completa + typecheck + lint |

- Probar que un test de regresión falla en el código viejo requiere **un** experimento por hallazgo, no la suite completa por commit.
- Sin `--coverage` salvo pedido explícito.
- `--maxWorkers=50%` cuando el runner satura la máquina.
- No relanzar una suite que ya está corriendo: `read_powershell` de esa sesión.

---

## Gates por stack

### Java / Quarkus (`server`)

```powershell
.\gradlew.bat --no-daemon --offline compileJava compileTestJava
.\gradlew.bat --no-daemon --offline test --tests "discordia.MiTest"
```

- `@QuarkusTest` necesita **Docker corriendo** (Dev Services levanta Postgres). Aun filtrando a tests unitarios, Gradle inicializa el modelo de test y falla con `Please configure the datasource URL … or ensure the Docker daemon is up`.
- Antes de intentarlo: `docker info --format "{{.ServerVersion}}"`. Si falla, decilo en el informe ("no pude ejecutar los `@QuarkusTest`; CI está verde") y no inventes el resultado.

### Python (`gateway`, `voice-calls`, `profile`, `auth-service`, `text-channel`, `notifications`)

```powershell
uv run pytest -q                      # crea .venv e instala; necesita red
uv run ruff check .
```

- `uv run --offline` falla si el cache no tiene algún wheel. Si la red está rara, reintentá sin `--offline`.
- Para correr **un** archivo: `uv run pytest tests/unit/test_x.py -q`.
- El piso de cobertura (70%) se incumple al correr un solo archivo: es esperado, no es un hallazgo.

### Node / Expo (`backoffice`, `web-client`)

Primero decidí **si hay que instalar**: `npm ci` borra y recrea `node_modules` (≈200k archivos, 4-5 min) y en la mayoría de las reviews no hace falta.

```powershell
git --no-pager diff --name-only "<sha-entorno>" "<sha-revisado>" -- package.json package-lock.json
```

| Resultado | Qué hacer |
|---|---|
| Vacío | Si el entorno existe y es compatible, no instalar (en worktree: junction de `node_modules`, ver arriba) |
| Sólo `package.json` | `npm install --prefer-offline --no-audit --no-fund` |
| `package-lock.json` cambió | lo mismo; `npm ci` sólo si querés validar lock ↔ package.json |
| CI | `npm ci --no-audit --no-fund` |

Gates:

```powershell
# web-client
npx tsc --noEmit
npx jest --silent --maxWorkers=50%
npm run lint          # expo lint

# backoffice
npm run typecheck     # tsc --noEmit
npm run lint
```

Durante la iteración corré sólo lo tocado: `npx jest src/core/chat/useDirectChat.test.ts`.

---

## Probar comportamiento real (no razonarlo)

### ¿Un JWT respeta el TTL configurado?

```powershell
uv run python -c "import base64,json; p='<jwt>'.split('.')[1]; p+='='*(-len(p)%4); c=json.loads(base64.urlsafe_b64decode(p)); print(c['exp']-c['nbf'])"
```

O un script que arme el grant con el servicio real y compare `exp - nbf` contra el `expires_at` que devuelve la API.

### ¿Un timeout acota de verdad?

Envolvé el trabajo en una tarea de N segundos con `timeout` menor y medí con `time.monotonic()`. Si el tiempo real ≈ N, el timeout es decorativo.

### ¿Un id interpolado permite reescribir la URL?

```python
import httpx
for cid in ["..", "%2e%2e", "a?b=1", "a#frag"]:
    print(cid, "->", httpx.URL(f"http://svc:22007/voice/channels/{cid}/join"))
```

Y para confirmar el end-to-end: `TestClient` de FastAPI con `MockTransport` que capture `request.url`.

### ¿Qué hace realmente una librería?

No adivines: leé el código instalado.

```powershell
Get-ChildItem .\node_modules\<pkg>\dist -Filter *.mjs
node -e "const fs=require('fs');const l=fs.readFileSync('node_modules/x/dist/x.mjs','utf8').split('\n');console.log(l.slice(A,B).join('\n'))"
```

Así se confirmó que `setMicrophoneEnabled` de `livekit-client` emite `MediaDevicesError` **y** re-lanza (⇒ la sala queda huérfana).

### ¿Un símbolo existe en `develop`?

```powershell
git --no-pager grep -n "<symbol>" origin/develop
git --no-pager log --oneline -1 origin/develop -- <path>
```

Así se desmintió que "la membresía no existía todavía".

### ¿El endpoint es realmente interno?

```powershell
git --no-pager show origin/main:compose.prod.yaml | Select-String -Pattern "<servicio>:" -Context 0,30
```

Buscá `traefik.http.routers.*.rule` y `.middlewares`: `PathPrefix('/x')` + `stripprefix` sin regla más específica = **todo** `/x/*` público.

---

## Publicar la review

Para evitar el error `Problems parsing JSON (HTTP 400)` generado por PowerShell (`Out-File -Encoding utf8` suele anteponer BOM `\xef\xbb\xbf` o romper el escape de comillas), generá el JSON con Node.js o Python:

### Opción con Python:
```powershell
uv run python -c "
import json
payload = {
    'body': '''$reviewBody''',
    'event': 'COMMENT',
    'comments': [
        {'path': 'src/archivo.ts', 'line': 42, 'side': 'RIGHT', 'body': '''**[Bugfix de UI / Paginación] ...**'''}
    ]
}
with open(r'$env:TEMP\payload.json', 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
"
```

### Opción con Node:
```powershell
node "$env:TEMP\payload.js" "$env:TEMP\payload.json"
```

### Posteo y verificación:
```powershell
# 1) Postear la review aprobada y guardar su identificador.
$response = gh api repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/reviews -X POST --input "$env:TEMP\payload.json"
if ($LASTEXITCODE -ne 0) { throw "No se pudo publicar la review" }
$review = $response | ConvertFrom-Json
if (-not $review.id) { throw "La respuesta no contiene el identificador de la review" }

# 2) Verificar sólo los comentarios de esa review, incluso si hay varias páginas.
gh api "repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/reviews/$($review.id)/comments" --paginate --slurp --jq '[.[][] | {path, line, side}]'
if ($LASTEXITCODE -ne 0) { throw "No se pudieron verificar los comentarios" }
```

Compará cantidad, líneas y lados con lo aprobado; si falta algo, informalo y consultá antes de publicar contenido adicional.

Reglas que evitan el 400/422:

- Antes de anclar, extraé el hunk del diff revisado y confirmá línea y lado:
  ```powershell
  gh pr diff <n> -R fiuba-IS2-Discordia/<repo> | Out-File "$env:TEMP\pr.diff" -Encoding utf8
  ```
- Usá `RIGHT` para líneas del lado nuevo y `LEFT` para líneas eliminadas del lado anterior, dentro de los hunks admitidos. Si no hay anclaje válido, describí el hallazgo en el body con su ubicación. Consultá [comment-style.md](./comment-style.md).
- Para un comentario suelto aprobado fuera de la review: `POST /pulls/<n>/comments` con `commit_id`, `path`, `line` y el `side` correspondiente.

---

## Trampas de PowerShell

- No hay `&&` ni `||`: usá `;` y `if ($?) { ... }`.
- Heredoc no existe: `@'` … `'@ | Out-File` para scripts, o `node -e "..."` para una línea.
- Rutas con corchetes (`[channelId].tsx`) se interpretan como comodines: usá `-LiteralPath`.
- Un comando que imprime `git : ...` en rojo con exit 0 no es un error: git escribe en stderr.
- `Select-String` con `$env:TEMP` dentro de comillas dobles rompe el parseo (`\` + `:`), armá la ruta con `Join-Path`.
- **Archivos `M` posiblemente relacionados con `LF`/`CRLF`:** inspeccioná estado, diff y atributos, y compará con el estado inicial. Un `git diff --stat` vacío no autoriza a descartar archivos; ante dudas informá y consultá.
- **Nunca `cmd.exe` con comillas escapadas por `\`:** PowerShell no escapa `"` con `\` y un borrado puede alcanzar otra ruta. Ante dificultades de limpieza seguí el procedimiento seguro de arriba y no sustituyas por borrado recursivo automático.
