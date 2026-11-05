# Plantilla de Plan de Implementación — Discordia

Usá este esqueleto al redactar `implementation_plan.md`. Adaptá la cantidad de etapas y repositorios al alcance real, pero **no elimines** los bloques de commits atómicos, el plan de verificación, la etapa de publicación de PRs ni la etapa de cierre administrativo local.

---

`````markdown
# Plan de Implementación: <Título claro con alcance funcional y HUs involucradas>

## Descripción del Objetivo

<Resumen ejecutivo de qué se completa de punta a punta:>
1. **<HU-XX — Nombre de la historia>** (*<Obligatoria | Optativa>, <N> pts*): <qué resuelve y qué tarea `TSK-XXX` o pendiente cierra>.
2. **<Pre-requisito o HU sinérgica si aplica>**: <detalle breve>.
3. **Cierre administrativo local**: publicar los PRs correspondientes, actualizar `<TSK-XXX>` (y registrar nuevas tareas si aplica) en `Backlog.json` con los números reales de PR, y actualizar `estado-historias.md` (llevando el puntaje a **<X> / 104 obligatorios** y **<Y> pts totales**).

---

## Decisiones de Diseño Acordadas (User Review Required)

> [!IMPORTANT]
> **Decisiones confirmadas e invariantes arquitectónicas**
> - **<Invariante de dominio / autorización 1>:** <Ej. comportamiento cuando `caller == target`, orden exacto de evaluación de rechazos en reglas de negocio>.
> - **<Invariante de persistencia / concurrencia 2>:** <Ej. migración Alembic/Flyway siguiendo patrón *expand/contract*, `lockById`, `flush()`, cascadas>.
> - **<Contrato entre servicios 3>:** <Ej. códigos de estado HTTP exactos, payloads y propagación en `gateway`>.
> - **Commits atómicos y sin rastro de IA:** Cada PR se divide en commits atómicos por cambio lógico (`docs`, `feat`, `test`) en formato Conventional Commits en español, sin trailers `Co-authored-by` ni leyendas generadas por IA.
> - **Privacidad del Backlog en repositorios compartidos:** Ningún archivo en `specs/`, `docs/arquitectura/`, mensajes de commit ni descripciones de PR mencionará `Backlog.json` ni identificadores `TSK-*` (solo referencias a `HU XX`, `ADR-XXX` o PRs de GitHub).

### Topología de Ramas y Pull Requests (<N> PRs en <M> etapas de código + publicación y cierre local)

```mermaid
flowchart LR
    subgraph SERVER["repo: <servicio-backend>"]
        S_BASE["<origin/develop o PR #N>\n<rama-base>"] --> S1["Etapa 1 · PR S1 (<HU-XX>)\nfeature/<slug-1>"]
        S1 --> S2["Etapa 2 · PR S2 (<HU-YY>)\nfeature/<slug-2>"]
    end

    subgraph GATEWAY["repo: gateway"]
        G_DEV["origin/develop"] --> G1["Etapa X · PR G1\nfeature/<slug-relay>"]
    end

    subgraph CLIENT["repo: <web-client | backoffice>"]
        W_BASE["<origin/develop o PR #M>\n<rama-base>"] --> W1["Etapa 1 · PR W1 (<HU-XX>)\nfeature/<slug-1>"]
        W1 --> W2["Etapa 2 · PR W2 (<HU-YY>)\nfeature/<slug-2>"]
    end
```

> [!NOTE]
> <Si existen otros PRs abiertos en los mismos repositorios, explicar cómo se evitan conflictos de merge o por qué conviene apilar sobre determinada rama.>

---

## Cambios Propuestos por Etapa

### Etapa 1 — <Nombre de la Etapa / HU> (`<repo-1>` + `<repo-2>`)

#### Repositorio `<repo-1>` (rama `feature/<slug>` desde `<rama-base>`)

##### [NEW] `docs/arquitectura/adr-<NNN>-<slug>.md` *(si hay decisión arquitectónica)*
- Contexto, Decisiones, Alternativas descartadas, Orden de errores / invariantes y Consecuencias (siguiendo el formato de los ADRs previos del servicio).

##### [NEW] `specs/<NNN>-<slug>/spec.md` (y `contracts/<api>.md`, `data-model.md` según convención del repo)
- Especificación SDD imitando las specs existentes de `<repo-1>` (`Contexto`, `User Scenarios & Testing`, `Functional Requirements`). Sin referencias a `TSK-*` ni `Backlog.json`.

##### [NEW / MODIFY] [<ArchivoDeDominioORepositorio>](file:///ruta/absoluta/al/archivo)
- Detalle concreto de cambios, firmas de métodos, migraciones, orden de validación de errores (`400` → `401` → `403` → `404` → `409`) y mensajes exactos de error.

##### [NEW / MODIFY] [<ArchivoDeTest>](file:///ruta/absoluta/al/test)
- Casos unitarios y de integración a cubrir (camino feliz, bordes, jerarquía/permisos, concurrencia/esquema).

**Secuencia de commits atómicos prevista (`<repo-1>`):**
1. `docs(<scope>): spec, contratos y adr de <funcionalidad> (HU-XX)`
2. `feat(<scope>): migracion <V# / alembic> para <cambio de esquema>` *(si aplica)*
3. `feat(<scope>): <caso de uso, reglas de dominio y endpoint>`
4. `test(<scope>): pruebas unitarias e integracion de <funcionalidad>`

---

#### Repositorio `<web-client | gateway | otro>` (rama `feature/<slug>` desde `<rama-base>`)

##### [NEW] `specs/<NNN>-<slug>/spec.md` (y `contracts/<ui>.md` si aplica)
- Especificación SDD del cliente / gateway alineada con los contratos del backend.

##### [NEW / MODIFY] [<ClienteApiYMapeoDeErrores>](file:///ruta/absoluta/al/archivo)
- Funciones de cliente HTTP/WS y mapeo exacto 1:1 de códigos/mensajes del backend a mensajes localizados en español para el usuario.

##### [NEW / MODIFY] [<ComponentesUI>](file:///ruta/absoluta/al/componente)
- Estados visuales, accesibilidad (`accessibilityLabel`, `testID`), deshabilitación preventiva según permisos/jerarquía y actualización local del estado.

##### [NEW / MODIFY] [<TestsDeCliente>](file:///ruta/absoluta/al/test)
- Pruebas de API, mapeo de errores y componentes.

**Secuencia de commits atómicos prevista (`<repo-2>`):**
1. `docs(<scope>): spec y contratos de <funcionalidad> (HU-XX)`
2. `feat(<scope>): cliente api y mapeo de errores para <funcionalidad>`
3. `feat(<scope>): <componentes y controles de interfaz>`
4. `test(<scope>): pruebas de <funcionalidad> en api y componentes`

---

<!-- Repetir la misma estructura para Etapa 2, Etapa 3, etc. -->

## Plan de Verificación

### 1. Tests Automatizados y Linters (obligatorios antes de pushear cada rama)

- **Servicios Python (`gateway`, `auth-service`, `profile`, `text-channel`, `voice-calls`, `notifications`)** — `ruff` sin errores y cobertura >= 70%:
  ```powershell
  cd <servicio>
  ruff check app tests
  pytest --cov=app --cov-fail-under=70
  ```
  *(En `profile`, ejecutar además `behave` si se tocaron escenarios BDD).*
- **`server` (Quarkus / Java 21 — obligatorio `_JAVA_OPTIONS=-Duser.timezone=UTC`)**:
  ```powershell
  cd server
  $env:_JAVA_OPTIONS="-Duser.timezone=UTC"
  .\gradlew.bat test
  ```
- **Clientes Expo / React Native (`web-client`, `backoffice`)**:
  ```powershell
  cd <cliente>
  npx tsc --noEmit
  npm run lint
  npm test -- --watchAll=false
  ```

### 2. Auditoría de Atomicidad, Autoría y Privacidad (previa al `git push`)

En cada rama creada, verificar antes de subir cambios:
```powershell
git -C <repo> log <rama-base>..HEAD --oneline
git -C <repo> log <rama-base>..HEAD --format="%B"
git -C <repo> diff <rama-base>...HEAD
```
- Confirmar commits atómicos en español (Conventional Commits) y **cero** trailers `Co-authored-by` o firmas de IA.
- Confirmar **cero** apariciones de `TSK-` o `Backlog.json` en commits, `specs/`, `docs/` y código.

### 3. Verificación Manual / Integración Punta a Punta

1. Levantar stack local (`infra/script/startup-infra.sh` + `infra/script/startup-servers.sh`) y cliente (`npx expo start --web`).
2. <Paso 1 verificando CA 1>.
3. <Paso 2 verificando CA 2 / bloqueo / error esperado>.

---

### Etapa <N-1> — Publicación de Pull Requests (Obligatoria una vez validado todo lo anterior)

Con todos los linters, tests y auditorías en verde, subir las ramas en **orden topológico** (primero ramas base, luego ramas apiladas) y crear los Pull Requests mediante GitHub CLI en **PowerShell** (`gh pr create`):

| Orden | Repositorio | Rama (`--head`) | Base (`--base`) | Título del PR |
|------:|-------------|-----------------|-----------------|---------------|
| 1 | `<repo>` | `feature/<slug-1>` | `<develop o rama-base>` | `feat(<scope>): <descripción breve en español>` |
| 2 | `<repo>` | `feature/<slug-2>` | `feature/<slug-1>` | `feat(<scope>): <descripción breve en español> (HU-XX)` |

Cada PR debe usar la **plantilla obligatoria de `AGENTS.md`** (sin mencionar `TSK-*`/`Backlog.json` ni firmas de IA):
- `## Resumen` (qué resuelve y referencia a `HU-XX` / `ADR-XXX`).
- `## Cambios principales` (agrupados por capa o módulo).
- `## Contratos e Impacto Operativo` (`APIs / Eventos`, `Base de datos`, `Configuración / Infra`, `PRs relacionados / apilados`).
- `## Verificación` (checks marcados `[x]` con los comandos y resultados reales ejecutados).

---

### Etapa <N> — Cierre de Backlog y Actualización de Estado de Historias

Recién una vez creados los PRs y obtenidos sus números reales (`#<N>`):

##### [MODIFY] `Backlog.json`
Siguiendo el protocolo en `.agents/rules/backlog.md` (lectura completa, modificación sobre el objeto parseado, actualización de `last_updated`, serialización `JSON.stringify(data, null, 2) + "\n"` y re-parseo de verificación):
- Actualizar `<TSK-XXX>` (`status: "completed"`, `start_date` si estaba `null`, `pull_request: "<repo> #<N>; ..."`).
- Registrar nuevas tareas completadas si el usuario lo solicitó, con su `checkpoint` activo, `severity`, `origin` y `pull_request` con los números reales de GitHub.

##### [MODIFY] `estado-historias.md`
- Mover/agregar las `HU-XX` completadas de punta a punta a la tabla correspondiente («Obligatorias completadas» u «Optativas completadas»), recalcular subtotales y puntaje total, limpiar «Parciales o solo backend» / «Sin implementar» y actualizar la sección «Notas».
`````

