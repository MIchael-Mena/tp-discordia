# Recetas de verificación

Todo lo de acá se probó en esta máquina (Windows + PowerShell). Los comandos son los que funcionan, no pseudocódigo.

---

## Worktree aislado

```powershell
cd "<repo>"
git --no-pager fetch origin --quiet

# Caso A: Solo lectura y verificación
git worktree add "$env:TEMP\pr-<n>" origin/<headRefName> --detach

# Caso B: Si se van a commitear y pushear fixes directamente en la rama del PR
git worktree add "$env:TEMP\pr-<n>" -b <headRefName> origin/<headRefName>
```

Leer y correr **siempre** desde `$env:TEMP\pr-<n>`.

Pero antes de instalar nada: **un worktree nace sin `node_modules`** (Node no sube hasta el repo original) y casi nunca hace falta crearlo.

```powershell
# ¿la rama agrega o cambia dependencias respecto de la rama donde ya hay node_modules?
git --no-pager -C "<repo>" diff --name-only origin/develop...origin/<headRefName> -- package.json package-lock.json
```

| Resultado | Qué hacer en el worktree |
|---|---|
| Vacío | **No instalar.** Linkear: `New-Item -ItemType Junction -Path "$env:TEMP\pr-<n>\node_modules" -Target "<repo>\node_modules"` |
| Sólo `package.json` o `package-lock.json` | `npm install --prefer-offline --no-audit --no-fund` |
| Validar lock ↔ package.json, o CI | `npm ci --no-audit --no-fund` (borra y recrea: minutos de disco) |

Con junction, nunca corras `npm install` dentro del worktree: escribiría sobre el `node_modules` del repo original.

### Borrar el worktree cuando tiene `node_modules`

Windows falla con *"Filename too long"*. La forma que funciona:

```powershell
$t = "$env:TEMP\pr-<n>"; $e = "$env:TEMP\_empty_del"
New-Item -ItemType Directory -Force -Path $e | Out-Null
robocopy $e $t /MIR /NJH /NJS /NFL /NDL /R:1 /W:1 | Out-Null
Remove-Item -Recurse -Force $t, $e -ErrorAction SilentlyContinue
```

Después, en el repo real: `git worktree prune` y verificá `git status --short --branch` (debe seguir en la rama del usuario, limpio).

### Propagar fixes/refactors a PRs apilados (Stacked PRs)

Cuando pusheás un commit nuevo a la rama `<baseBranch>` de un PR propio, cualquier PR abierto cuya base sea `<baseBranch>` queda desactualizado o en conflicto.

```powershell
# 1. Detectar PRs abiertos apilados sobre la rama modificada
gh pr list -R fiuba-IS2-Discordia/<repo> --state open --json number,headRefName,baseRefName |
  ConvertFrom-Json | Where-Object { $_.baseRefName -eq "<baseBranch>" }

# 2. Para cada rama hija, hacer rebase sobre la nueva punta y pushear con --force-with-lease
git checkout <childBranch>
git pull --rebase origin <childBranch>
git rebase <baseBranch>
# Correr los gates del repo (tests, lint, tsc) y luego:
git push --force-with-lease origin <childBranch>
```

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
git --no-pager diff --name-only origin/develop...origin/<rama> -- package.json package-lock.json
```

| Resultado | Qué hacer |
|---|---|
| Vacío | **No instalar** (en worktree: junction de `node_modules`, ver arriba) |
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
# 1) postear
gh api repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/reviews -X POST --input "$env:TEMP\payload.json"

# 2) verificar
gh api repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/comments --paginate |
  Out-File "$env:TEMP\c.json" -Encoding utf8
node -e "const a=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8').replace(/^\uFEFF/,''));console.log(a.length);a.forEach(c=>console.log(c.path+':'+c.line))" "$env:TEMP\c.json"
```

Reglas que evitan el 400/422:

- **El `line` tiene que ser una línea agregada del diff.** Antes de anclar, extraé el hunk y confirmá que la línea es `+`:
  ```powershell
  gh pr diff <n> -R ... --repo <repo> | Out-File "$env:TEMP\pr.diff" -Encoding utf8
  ```
- Un archivo con `index e69de29..` en el diff estaba **vacío** en la base ⇒ todas sus líneas son agregadas, podés anclar en cualquiera.
- Un archivo modificado: anclá sólo en las líneas del `+`, no en las de contexto (GitHub las rechaza o las ancla mal).
- Para un comentario suelto fuera de la review: `POST /pulls/<n>/comments` con `commit_id`, `path`, `line`, `side: "RIGHT"`.

---

## Trampas de PowerShell

- No hay `&&` ni `||`: usá `;` y `if ($?) { ... }`.
- Heredoc no existe: `@'` … `'@ | Out-File` para scripts, o `node -e "..."` para una línea.
- Rutas con corchetes (`[channelId].tsx`) se interpretan como comodines: usá `-LiteralPath`.
- Un comando que imprime `git : ...` en rojo con exit 0 no es un error: git escribe en stderr.
- `Select-String` con `$env:TEMP` dentro de comillas dobles rompe el parseo (`\` + `:`), armá la ruta con `Join-Path`.
- **Archivos `M` fantasma por `LF` vs `CRLF` (`core.autocrlf`):** Si un script o herramienta escribe archivos con `LF`, tras un `git rebase` o `checkout` pueden figurar archivos modificados (`M`) en `git status -sb` cuyo `git diff` está vacío (`warning: LF will be replaced by CRLF`). Antes de terminar, verificá `git diff --stat`; si da 0 líneas cambiadas, limpiá el árbol de trabajo con `git checkout -- .`.
- **Nunca `cmd.exe` con comillas escapadas por `\`:** `& $env:ComSpec /c "rmdir /s /q \"$p\""` llega malformado (PowerShell no escapa `"` con `\`) y el `rmdir` puede ejecutarse sobre una ruta padre. Para borrados recursivos difíciles usá la receta `robocopy /MIR` de arriba y validá la ruta (absoluta, ≥3 segmentos, nunca la raíz ni el home).
