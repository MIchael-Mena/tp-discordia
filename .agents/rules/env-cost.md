---
trigger: always_on
---

# Protocolo de Costo de Entorno y Verificación

La máquina es de la persona desarrolladora y no está dedicada a esta tarea: consume CPU, disco y batería que no se recuperan. La regla es **obtener la misma evidencia con el menor costo**, no correr todo "por las dudas".

## 1. Instalar dependencias sólo si hace falta

Antes de cualquier instalación, comprobá si la rama introduce dependencias respecto de la rama donde ya existe `node_modules`:

```powershell
git --no-pager diff --name-only origin/develop...origin/<rama> -- package.json package-lock.json
```

| Resultado | Qué hacer |
|---|---|
| Vacío | **No instalar nada.** El `node_modules` existente ya es válido |
| Sólo `package.json` | `npm install --prefer-offline --no-audit --no-fund` |
| `package-lock.json` cambió | lo mismo (aplica el delta). `npm ci` sólo para validar lock ↔ package.json |
| CI | `npm ci --no-audit --no-fund` |

- `npm ci` **borra y recrea** `node_modules` (≈200k archivos en los clientes Expo): es el comando de CI, no el comando local por defecto.
- **Un worktree nace sin `node_modules`** (Node no sube hasta el repo original). Si el lockfile coincide, linkeá en vez de instalar:

  ```powershell
  New-Item -ItemType Junction -Path "$env:TEMP\pr-<n>\node_modules" -Target "<ruta repo>\node_modules"
  ```

  Con junction, **nunca** corras `npm install` dentro del worktree: escribiría sobre el `node_modules` original.
- Python (`gateway`, `profile`, `auth-service`, `text-channel`, `voice-calls`, `notifications`): `uv run pytest` / `uv run ruff` ya resuelven el entorno. No antepongas `uv sync` ni `pip install -r` preventivos.
- Java (`server`): Gradle reutiliza el cache; no agregues `--refresh-dependencies` salvo problema de resolución real.

## 2. Presupuesto de verificación

| Momento | Qué correr |
|---|---|
| Cada iteración / hipótesis | sólo el archivo de test tocado (`npx jest src/core/chat/useDirectChat.test.ts`, `uv run pytest tests/unit/test_x.py -q`, `.\gradlew.bat test --tests "..."`) |
| Antes de cada commit atómico | los tests del módulo, no la suite entera |
| **Una sola vez**, al cerrar la tarea | suite completa + typecheck + lint |

- Demostrar que un test de regresión falla en el código viejo requiere **un** experimento por hallazgo, no una corrida completa por commit.
- Sin `--coverage` salvo pedido explícito: multiplica el tiempo del runner.
- Si el runner satura la máquina: `npx jest --silent --maxWorkers=50%`.
- No relances una suite que ya está corriendo por un comando tuyo: leé su salida con `read_powershell`.
- Es legítimo cerrar con "los `@QuarkusTest` no corrieron (Docker apagado); CI está verde", informándolo, en vez de forzar la suite.

## 3. Aislamiento del árbol de trabajo

Una sola pregunta: **¿el árbol de la persona usuaria está limpio y libre?**

- **Limpio y sin dev server/watch sobre esa rama** ⇒ `git switch <rama>`, trabajar ahí y `git switch <rama original>` al final. Es más barato y conserva `node_modules`.
- **Con cambios sin commitear, dev server corriendo, o necesidad de dos ramas vivas a la vez** ⇒ worktree temporal.
- En todos los casos, cerrar con `git status -sb` limpio en el repo original y `git worktree list` sin residuos.
- Si el sistema de archivos del worktree hace fallar `git worktree remove` (rutas largas de `node_modules`), usar la receta `robocopy /MIR` de [`verification-recipes.md`](../skills/reviewing-discordia-prs/references/verification-recipes.md), nunca comandos recursivos de `cmd.exe`.

## 4. Borrado de directorios en Windows

**Prohibido** invocar `cmd.exe` con comillas escapadas por `\`:

```powershell
& $env:ComSpec /c "rmdir /s /q \"$p\""   # MAL
```

PowerShell **no** escapa comillas con `\`: el argumento llega malformado y el `rmdir` puede ejecutarse sobre una ruta padre (ya pasó con `C:\`). Si `Remove-Item` no alcanza:

```powershell
$e = "$env:TEMP\_empty_del"
New-Item -ItemType Directory -Force -Path $e | Out-Null
robocopy $e $p /MIR /NFL /NDL /NJH /NJS /R:0 /W:0 | Out-Null
Remove-Item -LiteralPath $p, $e -Recurse -Force
```

Antes, validá `$p`: ruta absoluta, **al menos 3 segmentos**, nunca una raíz (`C:\`, `D:\`), nunca `$env:USERPROFILE`, nunca `$env:TEMP`.

## 5. Recursos vivos

- Nada de procesos `detach` para pruebas puntuales: verificar y bajar con `Stop-Process -Id <PID>`.
- Un servidor o watcher que quede vivo al cerrar la tarea es un hallazgo propio, no un efecto colateral aceptable.
- Al terminar, borrar worktrees, scripts y payloads temporales, y confirmar que no quedó ningún proceso hijo de los comandos lanzados.
