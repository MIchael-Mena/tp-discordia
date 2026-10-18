# AGENTS.md — TP-Discordia (Directorio Raíz)

## 1. Qué es este directorio

`TP-Discordia/` **NO es un repositorio Git**. Es una carpeta de trabajo local que agrupa los repositorios del proyecto para facilitar el acceso desde herramientas de IA. No tiene `.git`, no tiene ramas, y no se hacen commits ni PRs desde aquí.

Los repositorios reales son subdirectorios independientes, cada uno con su propio `.git`:

| Subdirectorio   | Repositorio GitHub                                | Ramas disponibles            |
|-----------------|---------------------------------------------------|------------------------------|
| `auth-service/` | `github.com/[org]/auth-service`                   | `main`, `develop`, features  |
| `gateway/`      | `github.com/[org]/gateway`                        | `main`, `develop`, features  |
| `profile/`      | `github.com/[org]/profile`                        | `main`, `develop`, features  |
| `web-client/`   | `github.com/[org]/web-client`                     | `main`, `develop`, features  |
| `server/`       | `github.com/[org]/server`                         | `main`, `develop`, features  |
| `infra/`        | `github.com/[org]/infra`                          | **solo `main`** (sin develop)|

> **⚠️ Importante — repo `infra`:** solo tiene rama `main`. No existe rama `develop`. Todos los cambios se mergeando directamente a `main`. Los PRs de infra se crean con base `main`.

---

## 2. AGENTS.md por repositorio

Algunos repositorios tienen su propio `AGENTS.md` con reglas y contexto específico del servicio. **Si vas a trabajar dentro de un repositorio específico, léelo antes de hacer cualquier cambio:**

- **`profile/AGENTS.md`** — reglas de Clean Architecture, convenciones de testing (pytest + behave), manejo de identidad con `X-User-Id`, y creación asíncrona de perfiles (ADR-004). **Usa ese archivo como fuente primaria cuando trabajes en `profile/`.**
- Los demás repos (`auth-service/`, `gateway/`, `web-client/`, `server/`, `infra/`) pueden incorporar su propio `AGENTS.md` en el futuro; si lo encuentras, úsalo.

---

## 3. Arquitectura general del proyecto

Discordia es una plataforma tipo Discord compuesta por microservicios:

- **gateway**: API Gateway central. Autentica el JWT (lo firma `auth-service`) e inyecta `X-User-Id` en cada request hacia los servicios internos. Verifica el token localmente (sin llamar a auth en cada request). Expone `POST /login`, `POST /register`, `POST /token/refresh`, `POST /logout`, `GET /me`, y hace relay hacia `profile`.
- **auth-service**: Gestión de cuentas y sesiones. Emite `access_token` (JWT, firmado con `JWT_SECRET`, 15 min) + `refresh_token` (opaco, tabla `sessions` en PostgreSQL). Publica eventos RabbitMQ (`UserCreated`, `UsernameSet`). Base: `discordia_auth` en Amazon RDS.
- **profile**: Perfil de usuario. Consume el evento `UserCreated` (cola `create_perfil`) para crear perfiles de forma asíncrona. También consume `update_username` (cola `update_username`) via ADR-005. Base: `discordia_profile` en Amazon RDS. Esquema versionado con **Alembic** (`db/migrate.sh`).
- **server**: Servicio Quarkus (Java). Gestiona "servidores" (canales de la plataforma). Expone `/server/` y `/server/greetings/{uuid}`.
- **web-client**: App Expo/React Native. Interfaces web y mobile. Login por password y Google (Google Identity Services / `@react-native-google-signin`).
- **infra**: Configuración de infraestructura AWS (EC2, RDS, ECR), `compose.prod.yaml`, scripts (`script/startup-infra.sh`, `script/startup-servers.sh`, `script/apply-prod-env.sh`), documentación ADR y CI/CD.

### Comunicación
- **HTTP**: web-client → gateway → (auth-service | profile | server).
- **Async (RabbitMQ)**: auth-service publica → profile consume.
- El gateway **no llama a auth en cada request**; verifica el JWT localmente con `JWT_SECRET` compartido.

### URLs de producción
- Base pública: `http://44.221.105.52/api`
- Sondas: `/api/livez`, `/api/readyz` (el `readyz` del gateway verifica auth-service y profile internamente). Los prefijos `/auth-service` y `/profile` ya no se exponen: solo gateway (`/api`) y server (`/server`) son públicos.

---

## 4. Convenciones de desarrollo

### Branching
- **Flujo estándar** (`auth-service`, `gateway`, `profile`, `web-client`, `server`): `feature/*` → `develop` → `main` (via PR).
- **Realese** deben ser en formato CALVER `YYYY.MM.DD` (ej. `2026.09.30`) y se crean desde `develop` → `main` (via PR).
- **Flujo PR** cuando se abre un PR debe ser contra `develop` (salvo infra, que es contra `main`), salvo que la feature este construida sobre un PR previo que aún no se mergeó, en cuyo caso el PR se puede apilar sobre el PR base (branch de feature → PR a feature base → luego PR a develop).
- **Infra**: todo va directo a `main`. No hay `develop`.
- **Siempre** traer los cambios de `develop` antes de comenzar un feature: `git pull origin develop`.
- **Nunca** crear PRs de servicios con base `main` directamente (salvo hotfixes acordados).

### Convenciones de commits
- Formato **Conventional Commits** en **español**.
- Ejemplos: `feat(gateway): agregar endpoint GET /me`, `fix(auth): corregir emit de rol en attach`, `docs(infra): actualizar ci-cd.md con paso de migración`.
- Atomizar los commits: un commit = un cambio lógico. No mezclar refactor + fix + feature en un solo commit, ejemplo un PR puede tener varios commits, cada uno con su propio scope y tipo.
- **Sin co-autoría de IA**: el commit debe quedar a nombre **únicamente** de la persona desarrolladora. **Nunca** agregar trailers de coautoría de agentes/herramientas de IA (p. ej. `Co-authored-by: Copilot <...>`) ni firmas de "generado por IA" en el mensaje, aunque una herramienta lo proponga. Si un commit de una rama aún no mergeada ya los tiene, eliminar el trailer con `git rebase`/`amend` y republicar la rama con `git push --force-with-lease`.

### Migraciones de base de datos (ADR-008)
- **auth-service** y **profile** usan **Alembic** como única fuente del esquema. El punto de entrada es `db/migrate.sh`.
- Patrón **expand/contract**: primero expand (la columna queda nullable o se agrega), luego contract en un release posterior (DROP).
- El paso de migración ocurre en CI y en el deploy SSM (entre `docker compose pull` y `docker compose up -d`).
- **Nunca** modificar el esquema con SQL manual ni alterar `init_database.sql` en `auth-service` (fue retirado).

### CI/CD
- Pipeline unificado: `push` a cualquier rama → tests; PR a `main`/`develop` → tests + validación de imagen; `push` a `main` → tests + build + push a ECR + deploy vía SSM.
- Cobertura mínima: **70%** en todos los servicios Python.
- Linter: `ruff` (Python). Ejecutar siempre antes de abrir un PR.

---

## 5. Variables de entorno críticas

| Variable              | Servicios que la usan          | Nota                                               |
|-----------------------|--------------------------------|----------------------------------------------------|
| `JWT_SECRET`          | `auth-service`, `gateway`      | Debe ser el **mismo valor** en ambos               |
| `JWT_ALGORITHM`       | `auth-service`, `gateway`      | Debe coincidir (`HS256` por defecto)               |
| `ACCESS_TOKEN_TTL_SECONDS` | `auth-service`            | Default: 900 s (15 min)                            |
| `REFRESH_TOKEN_TTL_SECONDS`| `auth-service`            | TTL del refresh opaco                              |
| `AUTH_REQUIRE_IDENTITY`| `profile`                     | `false` en dev sin gateway; `true` en prod         |
| `DATABASE_URL`        | `auth-service`, `profile`      | Apunta a RDS en producción                         |
| `GOOGLE_CLIENT_ID`    | `auth-service`, `web-client`   | Mismo Web Client ID en ambos                       |

---

## 6. Protocolo de Gestión del Backlog

** Nota:** El backlog es para uso local los demas integrantes del equipo no tienen acceso a este archivo. El backlog es un archivo JSON que contiene todas las tareas del proyecto hechas solo por mi.

El backlog del proyecto se encuentra en **`Backlog.json`** en la raíz de este directorio. Todos los agentes deben leer y actualizar este archivo para reflejar su progreso. Al interactuar con este archivo, se deben cumplir estrictamente las siguientes reglas:

### 6.1. Uso Obligatorio de Identificadores (IDs)
- Cada tarea tiene un identificador único (ej. `TSK-001`, `TSK-042`).
- **Búsqueda y Actualización:** Utiliza siempre este ID como clave primaria para localizar el nodo JSON correcto antes de aplicar cualquier modificación. Nunca asumas la posición de la tarea en el array.
- **Inmutabilidad:** El ID de una tarea ya creada jamás debe ser modificado.

### 6.2. Vinculación de Pull Requests (PR) y Excepciones
- **Regla General:** Cada vez que finalices el trabajo de una tarea, debes crear un PR y enlazar la URL o el número (ej. `#42`) en el campo `pull_request` de la tarea.
- **Excepciones (Sin PR):** Si el trabajo no requiere un PR (por ejemplo, un push directo a `develop`/`main` acordado, o una investigación sin código), registrar la justificación en el campo `exception_note`. Ninguna tarea `completed` puede quedar sin `pull_request` ni `exception_note`.

### 6.3. Aislamiento de Pendientes Descubiertos
- Si durante la resolución de una tarea descubres trabajo adicional que excede su alcance original:
  - **NO** crees una tarea nueva en la raíz del backlog.
  - **SÍ** regístrala en `discovered_pending_tasks` de la tarea original.
- Esto garantiza trazabilidad y evita la saturación del backlog principal.

### 6.4. Integridad del Formato JSON
- Antes de modificar `Backlog.json`, realiza siempre una lectura completa, aplica tus cambios sobre el objeto parseado, y sobrescribe el archivo serializando el objeto nuevamente.
- No uses reemplazos de texto plano para modificar el JSON.
- El campo `last_updated` (fecha ISO 8601) debe actualizarse en cada escritura.
- El archivo debe conservar formato JSON legible y uniforme: indentación de 2 espacios, un solo espacio después de cada `:`, arrays y objetos con saltos de línea, y un único salto de línea al final.
- Después de escribirlo, vuelve a parsearlo para comprobar que sigue siendo JSON válido y verifica que la cantidad de tareas y sus IDs no hayan cambiado accidentalmente.
- En VS Code, puedes aplicar el formato con `Shift + Alt + F` (**Format Document**). Desde Node.js, el equivalente es `JSON.stringify(data, null, 2) + "\n"`.

### 6.5. Estados válidos de una tarea
- `completed` — trabajo terminado, PR mergeado o excepción justificada.
- `in_progress` — trabajo activo actualmente.
- `pending` — en backlog, aún no iniciado.
- `blocked` — bloqueado por una dependencia externa.

### 6.6. Fecha de inicio (`start_date`)
- Toda tarea tiene el campo `start_date` (string ISO 8601, ej. `"2026-09-25"`).
- Se rellena con la fecha en que se comenzó a trabajar en la tarea.
- En tareas `pending` o `blocked` que aún no se iniciaron el valor es `null`.
- El estado de completitud se infiere del campo `status`; `start_date` no implica que la tarea esté terminada.
- **Nunca** se modifica una vez establecido.

### 6.7. Checkpoints (`checkpoint`)
- El proyecto tiene **4 checkpoints** a lo largo de ~4 meses de desarrollo (nomenclatura de la cátedra, equivalente a sprints).
- Cada tarea tiene el campo `checkpoint` (entero: `1`, `2`, `3` o `4`) que indica en qué checkpoint fue completada o está siendo trabajada.
- El objeto `checkpoints` en la raíz del JSON documenta el período y estado de cada checkpoint.
- **Regla de asignación:** al crear una tarea nueva, asignarle el checkpoint activo en ese momento. No reasignar checkpoints de tareas ya existentes.
- Los checkpoints actuales:

| Checkpoint | Período              | Estado      |
|------------|----------------------|-------------|
| 1          | hasta 2026-09-24     | completed   |
| 2          | 2026-09-25 en adelante | in_progress |
| 3          | por definir          | pending     |
| 4          | por definir          | pending     |

---

## 7. Notas operativas

- **Stack local:** levantarlo con `infra/script/startup-infra.sh` (RabbitMQ + bases) y luego `infra/script/startup-servers.sh` (los servicios). Cada servicio tiene su propio `.env` (copiar desde `.env.example`).
- **Conexión a bases RDS:** usar `infra/script/db-shell.sh` (solo desde la EC2).
- **Regla de oro de compose:** el `compose.prod.yaml` del repo `infra` y el `/opt/discordia/docker-compose.yml` de la EC2 deben ser idénticos (`git show HEAD:compose.prod.yaml | diff --strip-trailing-cr - /opt/discordia/docker-compose.yml` → vacío). Si hay cambio en el compose, sincronizar el archivo en la VM antes de redesplegar.
- **`discordia-key.pem`** en la raíz de `TP-Discordia/` es la clave privada SSH de la EC2. No commitear ni exponer.

---

## 8. Revisión de PRs

Existe un skill para revisar PRs de cualquier repo del proyecto con el criterio del equipo:
**`.github/skills/reviewing-discordia-prs/SKILL.md`** (invocable como `/reviewing-discordia-prs`).

Puntos que resume y conviene respetar:

- **Primero el informe, después los comentarios**: publicar en GitHub solo con aprobación explícita del usuario.
- Trabajar en un **worktree temporal** (`git worktree add "$env:TEMP\<pr>" origin/<branch> --detach`); nunca en el árbol de trabajo del usuario.
- No afirmar un defecto sin evidencia reproducible (test, grep, medición o lectura del código de la librería instalada).
- Clasificar cada hallazgo por prioridad (**P1 antes del merge** / P2 / nit) y decirlo en el body y en cada comentario.
- **Nunca** referenciar `Backlog.json`/`TSK-*` ni proponer "crear un ticket": el backlog es seguimiento local.
- Verificar el **otro lado de cada contrato** (productor ↔ gateway ↔ consumidor) y la exposición real en `infra/compose.prod.yaml` antes de creer lo que dice la documentación del PR.

Referencias del skill: `findings-catalog.md` (fallas recurrentes de esta cadena), `verification-recipes.md` (comandos por stack) y `comment-style.md` (formato y payload).