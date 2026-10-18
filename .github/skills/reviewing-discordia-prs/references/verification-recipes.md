# Recetas de verificación

Todo lo de acá se probó en esta máquina (Windows + PowerShell). Los comandos son los que funcionan, no pseudocódigo.

---

## Worktree aislado

```powershell
cd "<repo>"
git --no-pager fetch origin --quiet
git worktree add "$env:TEMP\pr-<n>" origin/<headRefName> --detach
```

Leer y correr **siempre** desde `$env:TEMP\pr-<n>`.

### Borrar el worktree cuando tiene `node_modules`

Windows falla con *"Filename too long"*. La forma que funciona:

```powershell
$t = "$env:TEMP\pr-<n>"; $e = "$env:TEMP\_empty_del"
New-Item -ItemType Directory -Force -Path $e | Out-Null
robocopy $e $t /MIR /NJH /NJS /NFL /NDL /R:1 /W:1 | Out-Null
Remove-Item -Recurse -Force $t, $e -ErrorAction SilentlyContinue
```

Después, en el repo real: `git worktree prune` y verificá `git status --short --branch` (debe seguir en la rama del usuario, limpio).

---

## Gates por stack

### Java / Quarkus (`server`)

```powershell
.\gradlew.bat --no-daemon --offline compileJava compileTestJava
.\gradlew.bat --no-daemon --offline test --tests "discordia.MiTest"
```

- `@QuarkusTest` necesita **Docker corriendo** (Dev Services levanta Postgres). Aun filtrando a tests unitarios, Gradle inicializa el modelo de test y falla con `Please configure the datasource URL … or ensure the Docker daemon is up`.
- Antes de intentarlo: `docker info --format "{{.ServerVersion}}"`. Si falla, decilo en el informe ("no pude ejecutar los `@QuarkusTest`; CI está verde") y no inventes el resultado.

### Python (`gateway`, `voice-calls`, `profile`, `auth-service`, `text-channel`)

```powershell
uv run pytest -q                      # crea .venv e instala; necesita red
uv run ruff check .
```

- `uv run --offline` falla si el cache no tiene algún wheel. Si la red está rara, reintentá sin `--offline`.
- Para correr **un** archivo: `uv run pytest tests/unit/test_x.py -q`.
- El piso de cobertura (70%) se incumple al correr un solo archivo: es esperado, no es un hallazgo.

### Node / Expo (`web-client`)

```powershell
npm ci --no-audit --no-fund     # ~4-5 min, 1100+ paquetes
npx tsc --noEmit
npx jest --silent
```

Si el repo del usuario ya tiene `node_modules`, no sirve: la rama puede sumar dependencias nuevas (`livekit-client`). `npm ci` desde el lock del worktree es lo correcto.

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

```powershell
# 1) armar el JSON con node (nunca con Out-File -Encoding utf8: escribe BOM y `gh` falla con "Problems parsing JSON")
node "$env:TEMP\payload.js" "$env:TEMP\payload.json"

# 2) postear
gh api repos/fiuba-IS2-Discordia/<repo>/pulls/<n>/reviews -X POST --input "$env:TEMP\payload.json"

# 3) verificar
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
