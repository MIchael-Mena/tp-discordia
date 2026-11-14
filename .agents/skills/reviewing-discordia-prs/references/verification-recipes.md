# Recetas de verificación

Recetas para Windows + PowerShell. Sustituí los marcadores y verificá las precondiciones antes de ejecutar; no asumas que una ruta, rama o remoto pertenece a la tarea.

---

## Acceder al código del PR

Política de aislamiento (rama directa, árbol sucio, worktree como excepción): [env-cost.md](../../../rules/env-cost.md) §4. Esta sección sólo da los comandos.

Registrá `git status -sb` y la rama actual. Identificá el remoto que apunta al repositorio **base** del PR; no presupongas que es `origin`. Obtené `headRefOid` y `baseRefOid` de GitHub (`gh pr view`).

### 1. Leer sin tocar el repo (por defecto)

```powershell
gh pr diff <n> -R fiuba-IS2-Discordia/<repo>
git -C "<repo>" fetch "<remoto-base>" "refs/pull/<n>/head"
if ($LASTEXITCODE -ne 0) { throw "No se pudo obtener la cabeza del PR" }
$head = git -C "<repo>" rev-parse FETCH_HEAD
if ($LASTEXITCODE -ne 0 -or $head -ne "<headRefOid>") { throw "La cabeza no coincide con GitHub; volver a consultar el PR" }
git -C "<repo>" --no-pager show "${head}:<ruta/del/archivo>"      # archivo completo
git -C "<repo>" --no-pager diff --stat "<baseRefOid>" $head        # mapa de cambios
```

`fetch` sólo agrega objetos: no cambia la rama, el índice ni los archivos del usuario. Registrá los SHA revisados. Si el PR cambia durante la revisión, volvé a obtener los datos.

### 2. Ejecutar tests/lint/typecheck: `git switch --detach`

Sólo si hace falta correr algo. Primero aplicá el protocolo de árbol sucio de `env-cost.md` §4.2 y luego:

```powershell
git -C "<repo>" switch --detach $head
git -C "<repo>" status -sb      # anti-buffer-sucio (env-cost.md §4.3)
```

Decidí si hay que instalar dependencias con `env-cost.md` §1 (comparar lockfile entre la rama del entorno y `$head`). Al terminar: `git -C "<repo>" switch <rama-original>`, `git status -sb` y comparación con el estado registrado.

### 3. Modificar la rama de un PR propio

Verificá el repositorio y remoto de la cabeza, permisos de push, SHA remoto y estado local. No uses `-B`, `--force` ni `git reset --hard`. Si la rama local existe, usala sólo si coincide con el SHA revisado (`git switch <rama>`); si no existe, creala desde ese SHA (`git switch -c <rama> $head`). Ante divergencias, detenete y consultá. Para un fork, no pushees por defecto al remoto base.

Antes de publicar aplicá la **compuerta pre-PR** (`env-cost.md` §3).

### Propagar fixes/refactors a PRs apilados (Stacked PRs)

Un commit nuevo en la base no implica que todos los hijos requieran rebase. Identificá los descendientes y verificá si están afectados antes de proponer cambios.

```powershell
# 1. Detectar PRs abiertos apilados sobre la rama modificada
gh pr list -R fiuba-IS2-Discordia/<repo> --state open --limit 1000 --json number,author,headRefName,baseRefName,headRepositoryOwner,headRepository,isCrossRepository |
  ConvertFrom-Json | Where-Object { $_.baseRefName -eq "<baseBranch>" }
```

Comprobá los repositorios además de los nombres de rama y consultá más resultados si la lista está truncada. Mostrá ramas, autores y acciones propuestas; antes de reescribir historia o hacer push obtené aprobación explícita para las ramas afectadas, salvo autorización expresa previa. Verificá permisos, ausencia de cambios locales y SHA remoto de cada rama. Si están aprobadas, procesalas en orden de dependencia, ejecutá los gates y usá `--force-with-lease` con la referencia y el SHA remoto esperados explícitamente; ante divergencia, conflicto o fallo detenete e informá. No asumas autorización sobre ramas de compañeros.

---

## Gates por stack

Presupuesto de verificación, política de instalación de dependencias y **compuerta pre-PR**: [env-cost.md](../../../rules/env-cost.md) (§1–§3). Abajo los comandos y trampas específicas de cada stack.

### Java / Quarkus (`server`)

```powershell
$env:_JAVA_OPTIONS="-Duser.timezone=UTC"
.\gradlew.bat --no-daemon --offline compileJava compileTestJava
.\gradlew.bat --no-daemon --offline test --tests "discordia.MiTest"
```

- `@QuarkusTest` necesita **Docker corriendo** (Dev Services levanta Postgres). Aun filtrando a tests unitarios, Gradle inicializa el modelo de test y falla con `Please configure the datasource URL … or ensure the Docker daemon is up`.
- Antes de intentarlo: `docker info --format "{{.ServerVersion}}"`. Si falla, decilo en el informe ("no pude ejecutar los `@QuarkusTest`; CI está verde") y no inventes el resultado.

### Python (`gateway`, `voice-calls`, `profile`, `auth-service`, `text-channel`, `notifications`)

```powershell
uv run pytest -q                      # suite completa (incluye cobertura >= 70%)
uv run ruff check .
uv run lint-imports                   # si el servicio lo define
```

- `uv run --offline` falla si el cache no tiene algún wheel. Si la red está rara, reintentá sin `--offline`.
- Para correr **un** archivo: `uv run pytest tests/unit/test_x.py -q`.
- El piso de cobertura (70%) se incumple al correr un solo archivo: es esperado, no es un hallazgo.

### Node / Expo (`backoffice`, `web-client`)

Antes de instalar cualquier dependencia, aplicá [env-cost.md](../../../rules/env-cost.md) §1 (comparar `package.json` y `package-lock.json` entre la rama del entorno y el SHA revisado; nunca correr `npm ci` por defecto en local).

Gates:

```powershell
# web-client
npx tsc --noEmit
npx jest --silent --maxWorkers=50%
npm run lint          # expo lint

# backoffice
npm run typecheck     # tsc --noEmit
$env:CI="true"; npm test -- --maxWorkers=50%
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
