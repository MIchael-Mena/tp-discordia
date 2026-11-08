# AGENTS.md — TP-Discordia (Directorio Raíz)

## 1. Qué es este directorio

`TP-Discordia/` **NO es un repositorio Git del equipo**. Es una carpeta de trabajo local que agrupa los repositorios del proyecto para facilitar el acceso desde herramientas de IA; no se hacen commits ni PRs del proyecto desde aquí.

Los repositorios reales son subdirectorios independientes, cada uno con su propio `.git`:

| Subdirectorio | Repositorio GitHub | Ramas disponibles |
|---|---|---|
| `auth-service/` | `github.com/[org]/auth-service` | `main`, `develop`, features |
| `backoffice/` | `github.com/[org]/backoffice` | `main`, `develop`, features |
| `gateway/` | `github.com/[org]/gateway` | `main`, `develop`, features |
| `infra/` | `github.com/[org]/infra` | **solo `main`** (sin `develop`) |
| `notifications/` | `github.com/[org]/notifications` | `main`, `develop`, features |
| `profile/` | `github.com/[org]/profile` | `main`, `develop`, features |
| `server/` | `github.com/[org]/server` | `main`, `develop`, features |
| `text-channel/` | `github.com/[org]/text-channel` | `main`, `develop`, features |
| `voice-calls/` | `github.com/[org]/voice-calls` | `main`, `develop`, features |
| `web-client/` | `github.com/[org]/web-client` | `main`, `develop`, features |

> **⚠️ Importante — repo `infra`:** solo tiene rama `main` (no existe `develop`). Todos los cambios y PRs de `infra` tienen como base `main`.

---

## 2. AGENTS.md por repositorio

Algunos repositorios tienen su propio `AGENTS.md` con reglas específicas del servicio. **Léelo siempre antes de hacer cambios dentro de ese repositorio:**

- **`profile/AGENTS.md`** — Clean Architecture, testing (`pytest` + `behave`), identidad con `X-User-Id` y creación asíncrona de perfiles (ADR-004). Fuente primaria al trabajar en `profile/`.
- Si encuentras un `AGENTS.md` en cualquiera de los demás repositorios, úsalo como referencia primaria de ese servicio.

---

## 3. Arquitectura general del proyecto

Discordia es una plataforma tipo Discord compuesta por microservicios:

- **gateway**: API Gateway central (FastAPI). Verifica el JWT localmente con `JWT_SECRET` (sin llamar a `auth-service` en cada request) e inyecta `X-User-Id` hacia los servicios internos. Expone `/login`, `/register`, `/token/refresh`, `/logout`, `GET /me` y hace relay hacia los servicios internos.
- **auth-service**: Cuentas y sesiones. Emite `access_token` (JWT HS256, 15 min) + `refresh_token` (opaco, tabla `sessions` en PostgreSQL RDS `discordia_auth`). Publica eventos en RabbitMQ (`UserCreated`, `UsernameSet` y exchange fanout `account_events`).
- **profile**: Perfil de usuario. Consume `UserCreated` (cola `create_perfil`) y sincronización de username (`update_username`, ADR-005). Base PostgreSQL RDS `discordia_profile` versionada con **Alembic** (`db/migrate.sh`).
- **server**: Servicio Quarkus (Java 21). Gestiona servidores, canales, miembros y roles/permisos. Solo interno (`/api/servers...` vía gateway). Base PostgreSQL RDS `discordia_server` (Flyway al arrancar) y publicación en `server_events`.
- **text-channel**: Mensajería por canal (REST + WebSocket). MongoDB en **Atlas** (`TEXT_CHANNEL_MONGO_URL`; contenedor `mongo:7` solo para contingencia vía `mongo-mode.sh`) y Redis pub/sub entre réplicas.
- **voice-calls**: Orquestación de canales de voz contra **LiveKit Cloud**. Presencia en memoria (sin BD). Solo interno (`/api/voice/...`), con `/livez` y `/readyz`.
- **notifications**: Notificaciones y marcadores de lectura/no leído por canal y servidor (HU 27/28). Consume `account_events`, `server_events` y `message_events` manteniendo copia local de membresías y canales. MongoDB propio (`discordia_notifications`). Solo interno (`/api/notifications/...` y `/api/ws/notifications`).
- **web-client**: Cliente Expo/React Native (web y mobile). Login por contraseña y Google OAuth.
- **backoffice**: Cliente web Expo/React Native para staff (requiere claim `role == admin` en el JWT; listado/búsqueda de cuentas y suspensión/reactivación, HU 29/30/31). Publicado en Expo Hosting.
- **infra**: Configuración AWS (EC2, RDS, ECR), `compose.prod.yaml`, scripts operativos (`script/startup-infra.sh`, `script/startup-servers.sh`, `script/apply-prod-env.sh`), ADRs transversales y políticas CI/CD.

### Comunicación y URLs de producción
- **HTTP**: `web-client` / `backoffice` → `gateway` → servicios internos. Solo `gateway` (vía Traefik en `/api`) es público (`http://44.221.105.52/api`; sondas `/api/livez` y `/api/readyz`).
- **WebSocket**: `web-client` → `gateway` → `text-channel` (`/api/ws/channels/{id}`) y `notifications` (`/api/ws/notifications`).
- **Media**: `voice-calls` → LiveKit Cloud (externo).
- **Async (RabbitMQ)**: `auth-service` → `profile`; `auth-service`, `server` y `text-channel` → `notifications` (y `text-channel` para cierre de WS ante suspensión/baneo).

---

## 4. Convenciones de desarrollo

### Branching
- **Flujo estándar** (todos los repos salvo `infra`): `feature/*` → `develop` → `main` (vía PR).
- **Releases**: formato CALVER `YYYY.MM.DD` (ej. `2026.09.30`), desde `develop` → `main` (vía PR).
- **Flujo PR**: todo PR apunta a `develop` (salvo `infra`, que va directo a `main`), excepto cuando se construye sobre un PR previo aún no mergeado, en cuyo caso se apila sobre la rama del PR base (`feature/nueva` → `feature/base` → `develop`).
- **Siempre** actualizar `develop` antes de abrir una rama (`git pull origin develop`) y **nunca** abrir PRs de servicios directo a `main` (salvo hotfixes acordados).

### Convenciones de commits
- **Atomizar los commits**: un commit = un cambio lógico. No mezclar refactor + fix + feature en un solo commit; un PR puede tener varios commits, cada uno con su propio scope y tipo, pero nunca un único commit monolítico que mezcle varios scopes y tipos.
- Formato **Conventional Commits** en **español** (ej. `feat(gateway): agregar endpoint GET /me`, `fix(auth): corregir emit de rol en attach`, `docs(infra): actualizar ci-cd.md con paso de migración`).
- **Sin co-autoría de IA**: el commit debe quedar **únicamente** a nombre de la persona desarrolladora. **Nunca** agregar trailers `Co-authored-by` de agentes/IA ni firmas de "generado por IA". Si aparecen en una rama no mergeada, eliminarlos con `git rebase`/`amend` y republicar con `git push --force-with-lease`.

### Spec-Driven Development (SDD) — Carpeta `specs/`
Al desarrollar funcionalidades nuevas, modificar contratos o alterar lógica de dominio, seguir obligatoriamente el flujo SDD en `<servicio>/specs/`:

1. **Inspección previa:** Leer al menos 2 especificaciones existentes en `<servicio>/specs/` (o en otro servicio si estuviera vacía) para respetar exactamente la numeración, estructura de secciones y formato del equipo.
2. **Flujo obligatorio Spec-First (integración con `/plan`):**
   - Si se inicia con `/plan`, incluir la estructura de la spec dentro del plan. Una vez aprobado el plan, **no volver a detenerse**: crear/actualizar el archivo en `<servicio>/specs/` como primer paso y continuar directo con código y tests. Si no se usó `/plan`, redactar primero la spec y pedir confirmación antes de programar.
   - **Sincronización pre-PR:** Si durante la implementación cambia algún detalle técnico, actualizar `specs/` antes de commitear para que coincida con el código final.
3. **Reglas de contenido en `specs/`:**
   - **PROHIBIDO filtrar el Backlog local:** Nunca incluir referencias a `Backlog.json` ni identificadores `TSK-*` (usar solo `HU XX` según [`historias-usuario.md`](historias-usuario.md) o `ADR-XXX`).
   - **Alineación entre servicios:** Si cambia un contrato transversal (rutas en `gateway`, payloads o eventos RabbitMQ), verificar specs y código de todos los servicios afectados.

### Documentación de ADRs
- Antes de introducir cambios arquitectónicos, revisar `docs/arquitectura/` del repositorio y crear un ADR nuevo siguiendo el formato de los existentes, referenciándolo en la spec y en el PR. Si la decisión cruza varios servicios, documentarla en `infra/docs/adr/` y referenciarla desde los repositorios involucrados.

### Formato de Pull Requests (PRs)
- Publicar un PR **solo cuando el trabajo esté completo** y los linters/tests pasen. Usar GitHub CLI (`gh`) autenticado desde **PowerShell** (no Git Bash).
- **Título:** Conventional Commits en español (`tipo(alcance): descripción breve`, ej. `feat(notifications): agregar consumidor de message_events`).
- **Privacidad y autoría:** **PROHIBIDO** mencionar `TSK-*` o `Backlog.json` en título, descripción o comentarios (referenciar solo `HU XX`, `ADR-XXX` o `#PR`). **Sin firmas ni footers de IA**.
- **Plantilla obligatoria para la descripción (Body):**

  ```md
  ## Resumen
  Breve explicación de qué problema resuelve este PR y por qué es necesario (referenciar HU o ADR si aplica).

  ## Cambios principales
  - Lista concisa de los cambios técnicos agrupados por capa o módulo.
  - Omitir detalles triviales que ya son evidentes en el diff.

  ## Contratos e Impacto Operativo
  - **APIs / Eventos:** Cambios en rutas HTTP/WS, payloads o exchanges/colas de RabbitMQ (indicar cómo afecta a productores, `gateway` o consumidores). Si no hay, indicar "Sin cambios".
  - **Base de datos:** Migraciones de Alembic/Flyway (aclarar si sigue el patrón expand/contract). Si no hay, indicar "Sin cambios".
  - **Configuración / Infra:** Nuevas variables de entorno (`.env.example`) o cambios requeridos en `infra/compose.prod.yaml`. Si no hay, indicar "Sin cambios".
  - **PRs relacionados / apilados:** Enlace a PRs base si este PR está apilado sobre otra rama o depende de un cambio en otro repositorio.

  ## Verificación
  - [ ] Linter ejecutado sin errores (`ruff` / equivalente del stack).
  - [ ] Tests automatizados pasando (cobertura >= 70% en servicios Python).
  - [ ] Verificación manual o de integración (detallar brevemente comandos o flujo probado).
  ```

### Migraciones de base de datos (ADR-008) y CI/CD
- **Alembic** es la única fuente del esquema en `auth-service` y `profile` (`db/migrate.sh`, ejecutado en CI y en deploy SSM entre `docker compose pull` y `up -d`); **Flyway** en `server` al iniciar. Seguir siempre el patrón **expand/contract** y nunca alterar esquemas con SQL manual ni usar `init_database.sql`.
- **CI/CD:** `push` → tests; PR a `main`/`develop` → tests + build de imagen; `push` a `main` → tests + ECR + deploy SSM. En servicios Python: `ruff` sin errores y cobertura **>= 70%** obligatoria antes de abrir PR.

---

## 5. Historias de Usuario, Seguimiento y Backlog

### Catálogo de Historias y Estado de Avance
En la raíz de `TP-Discordia/` se encuentran los dos documentos de referencia funcional del proyecto:
- **[`historias-usuario.md`](historias-usuario.md):** Catálogo de las 12 épicas y las 81 Historias de Usuario con sus Criterios de Aceptación (CA) completos, Requisitos No Funcionales (RNF) e instancias de entrega. Cada historia se encuentra identificada unívocamente con el prefijo `HU <N>: <Título>` (ej. `HU 1: Registro de usuarios`). Es la fuente de verdad técnica para consultar el alcance, redactar especificaciones en `specs/` y verificar criterios de aceptación.
- **[`estado-historias.md`](estado-historias.md):** Matriz de seguimiento y avance de todas las historias (obligatorias y optativas). Cada fila enlaza directamente a su criterio en `historias-usuario.md` e indica puntos, épica, motivo o dependencia, y el `Checkpoint` en que fue completada (`-` si continúa pendiente). Contiene además el puntaje total acumulado (104/104 obligatorios + 38 optativos = 142 pts), mínimos por equipo y las notas técnicas de implementación de punta a punta.

### Protocolo de Gestión del Backlog (`Backlog.json`)
`Backlog.json` (en la raíz de `TP-Discordia/`) es de **uso estrictamente local**; el resto del equipo no tiene acceso a él. Nunca menciones `Backlog.json` ni IDs `TSK-*` en repositorios compartidos.

Todas las reglas obligatorias para consultar y modificar `Backlog.json` (búsqueda por ID inmutable, vinculación de `pull_request` o `exception_note`, estructura y `severity` de `discovered_pending_tasks`, integridad de serialización JSON con `JSON.stringify(data, null, 2) + "\n"`, estados válidos, `start_date` y `checkpoint`) están definidas en **[`.agents/rules/backlog.md`](.agents/rules/backlog.md)** (regla `always_on` en Antigravity; lectura obligatoria antes de editar `Backlog.json` en cualquier otra herramienta).

---

## 6. Notas operativas

- **Variables de entorno:** documentadas de forma transversal en [`infra/README.md`](infra/README.md) (sección *Variables que espera `/opt/discordia/.env`*), por microservicio en [`infra/docs/servicios/README.md`](infra/docs/servicios/README.md) y para entorno local en el `.env.example` de cada repositorio.
- **Stack y pruebas locales:** levantar con `infra/script/startup-infra.sh` (RabbitMQ + bases) y `infra/script/startup-servers.sh` (servicios), documentado en [`infra/README.local.md`](infra/README.local.md); para los clientes Expo usar `npx expo start` (web).
- **Conexión a bases RDS:** usar `infra/script/db-shell.sh` (solo accesible desde la EC2).
- **Regla de oro de Compose:** `infra/compose.prod.yaml` y `/opt/discordia/docker-compose.yml` en la EC2 deben ser idénticos (`git show HEAD:compose.prod.yaml | diff --strip-trailing-cr - /opt/discordia/docker-compose.yml` → vacío). Sincronizar en la VM antes de redesplegar si cambia.
- **`discordia-key.pem`** en la raíz de `TP-Discordia/` es la clave privada SSH de la EC2: nunca commitear ni exponer.
- **Timezone en Java (`server`):** ejecutar siempre tests y procesos locales con `_JAVA_OPTIONS=-Duser.timezone=UTC`.
- **Costo de entorno y verificación:** instalar dependencias sólo si cambió el lockfile, correr tests dirigidos durante la iteración y **una sola** suite completa al cierre, y preferir `git switch` sobre un worktree cuando el árbol está limpio. Reglas completas en [`env-cost.md`](.agents/rules/env-cost.md) (regla `always_on`); recetas en [`verification-recipes.md`](.agents/skills/reviewing-discordia-prs/references/verification-recipes.md).

---

## 7. Revisión de PRs

Skill del equipo para revisar PRs en cualquier repositorio: **`.agents/skills/reviewing-discordia-prs/SKILL.md`** (`/reviewing-discordia-prs`, expuesto también vía `.agents/skills.json`).

- **Detección automática de autoría (PR propio vs. PR de compañero)**:
  - **PR propio**: no publicar comentarios en GitHub; buscar errores, huecos de contrato y oportunidades de refactor (Clean Architecture, SOLID, DRY, custom hooks, separación vista/lógica), presentar las propuestas y usar `ask_question` para confirmar cuáles aplicar antes de commitear, pushear y rebasar PRs apilados.
  - **PR de compañero**: **primero el informe, después los comentarios**, publicando en GitHub solo con aprobación explícita del usuario.
- Revisar en un **worktree temporal** cuando solo se inspecciona o el árbol local tiene cambios, siguiendo la receta de la skill para verificar los SHA y preservar la rama y el estado inicial del usuario al cerrar.
- No afirmar defectos sin evidencia reproducible; clasificar por prioridad (**P1 antes del merge** / P2 / Refactor / nit); prohibido mencionar `Backlog.json`/`TSK-*`; verificar ambos lados de cada contrato y `infra/compose.prod.yaml`.
- Referencias: `findings-catalog.md`, `verification-recipes.md` y `comment-style.md`.

---

## 8. Planificación e Implementación de Features

Skill con la plantilla y flujo estándar para planificar e implementar HUs/tareas por etapas: **`.agents/skills/planning-discordia-features/SKILL.md`** (`/planning-discordia-features`, con plantilla en `references/plan-template.md`).

- **Topología de ramas y PRs apilados** diagramada en Mermaid + invariantes de diseño y SDD/ADRs desde la planificación.
- **Secuencia explícita de commits atómicos** declarada por cada PR dentro del plan (`docs` → `feat` → `test`, sin coautoría de IA).
- **Publicación obligatoria de PRs** (`git push` en orden topológico + `gh pr create` en PowerShell con la plantilla de la sección 4) apenas todos los linters y tests pasen, **antes** de cerrar las tareas en `Backlog.json` y actualizar [`estado-historias.md`](estado-historias.md).
