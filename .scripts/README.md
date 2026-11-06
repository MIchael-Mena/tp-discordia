# Scripts de Automatización — TP-Discordia

Scripts utilitarios para el mantenimiento, release y despliegue del monorepo / workspace de TP-Discordia.

---

## 1. `deploy.py` — Automatización de Release y Despliegue

Automatiza el ciclo de vida de release y despliegue de los servicios declarados en [`repos.json`](./repos.json) (las entradas con `"deploy": false`, como `infra`, se omiten sin borrarlas del archivo), siguiendo estrictamente las convenciones de `AGENTS.md`:

- **Sin cambios, sin release**: si `origin/develop` no tiene commits nuevos respecto de `origin/main`, el servicio se informa como `SIN CAMBIOS` y no se abre PR, no se mergea ni se tagea.
- **Formato CalVer**: `YYYY.MM.DD` (ej. `2026.10.30`). Si ya existe un release en la misma fecha —local o remoto— genera automáticamente la siguiente revisión (`.1`, `.2`, etc., ej. `2026.10.30.1`).
- **Flujo de ramas**: Creación de PR de release desde `develop` hacia `main` con título `Release/<CalVer>` y changelog automático de los commits incluidos.
- **Merge y tags**: Merge con merge commit estándar (`--merge`, sin borrar `develop`), protegido con `--match-head-commit` para no mergear si `develop` se movió durante el proceso. Luego crea y empuja el tag anotado `v<CalVer>` verificando que no exista previamente apuntando a otro commit.
- **Disparo de CI/CD**: El merge a `main` dispara automáticamente las GitHub Actions de cada servicio (lint + tests + build Docker/ECR + SSM deploy a EC2 o Expo Hosting).
- **Orden de dependencias**:
  1. `profile` (modelo base y migraciones Alembic)
  2. `auth-service` (cuentas, sesiones y JWT)
  3. `server` (servidores, canales, roles)
  4. `text-channel` (mensajería)
  5. `voice-calls` (sesiones de voz LiveKit)
  6. `notifications` (notificaciones y contadores)
  7. `gateway` (routing y relays hacia todos los anteriores)
  8. `web-client` (cliente de usuarios Expo Web/Android)
  9. `backoffice` (cliente staff Expo Web/Android)

  El orden se puede redefinir con `deploy.order` en `repos.json`; los repos nuevos sin `order` se agregan al final.

### Requisitos

- **Python 3.10+**
- **Git** configurado con acceso SSH/HTTPS al remoto `origin`.
- **GitHub CLI (`gh`)**: autenticado con `gh auth login` o `gh auth refresh -h github.com`.

### Uso y Ejemplos

```bash
# Ver estado de cada servicio (commits pendientes y último tag)
python .scripts/deploy.py --status

# Simulación completa sin aplicar cambios (dry-run)
python .scripts/deploy.py --dry-run

# Despliegue interactivo con confirmación paso a paso (por defecto)
python .scripts/deploy.py

# Despliegue interactivo monitoreando el pipeline de GitHub Actions en vivo
python .scripts/deploy.py --watch

# Despliegue completamente automático (sin pedir confirmación)
python .scripts/deploy.py --auto

# Solo abrir los PRs de release para revisión en GitHub (sin mergear)
python .scripts/deploy.py --create-pr-only

# Esperar que los checks de CI del PR pasen antes de mergear
python .scripts/deploy.py --wait-checks

# Desplegar solo servicios específicos
python .scripts/deploy.py --only profile,gateway

# Omitir clientes de frontend
python .scripts/deploy.py --skip web-client,backoffice

# Forzar una versión CalVer base específica
python .scripts/deploy.py --calver 2026.10.30
```

---

## 2. `limpiar_ramas.py` — Limpieza de ramas mergeadas

Limpia ramas locales ya integradas en los repositorios configurados en `repos.json`:

```bash
# Simular ramas a borrar
python .scripts/limpiar_ramas.py --dry-run

# Borrar ramas mergeadas
python .scripts/limpiar_ramas.py --yes
```

---

## 3. `repos.json` — Configuración de repositorios

Define la lista de repositorios del workspace y la configuración opcional de cada uno. Es compartido por `deploy.py` y `limpiar_ramas.py`; cada script interpreta solo las claves que le corresponden.

```json
{
  "repos": [
    { "folder": "auth-service", "deploy": { "order": 20, "workflow": "Build Auth Service" } },
    { "folder": "infra", "branch": "main", "deploy": false }
  ]
}
```

| Clave | Script | Descripción |
|---|---|---|
| `folder` | ambos | Carpeta del repo, relativa a la raíz del workspace (obligatoria). |
| `enabled` | ambos | `false` ignora la entrada sin aviso (útil si el repo todavía no está clonado). |
| `branch` | `limpiar_ramas.py` | Rama objetivo a mantener; si falta se autodetecta (`develop` si existe, si no `main`). |
| `keep` | `limpiar_ramas.py` | Ramas extra que nunca se borran. |
| `deploy` | `deploy.py` | `false` excluye el repo del release/deploy. |
| `deploy.order` | `deploy.py` | Entero de orden de despliegue (menor primero); default: orden interno del script. |
| `deploy.from` / `deploy.to` | `deploy.py` | Ramas origen y destino del release (default `develop` → `main`). |
| `deploy.workflow` | `deploy.py` | Nombre del workflow de GitHub Actions que monitorea `--watch`. |
| `deploy.tag` | `deploy.py` | `false` para no crear ni empujar tag en ese repo. |

Para **agregar un servicio nuevo** alcanza con clonarlo dentro del workspace y sumar una entrada en `repos.json`:

```json
{ "folder": "mi-servicio", "deploy": { "order": 55, "workflow": "Build mi-servicio" } }
```

Si el repositorio no tiene rama `develop` (no hay flujo de release), `deploy.py` lo detecta y lo informa como `SIN RELEASE` sin necesidad de configurar nada más.


