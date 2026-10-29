# Estado de las Historias de Usuario — Discordia

**Actualizado:** 2026-10-28 (tener en cuenta que hay otros miembros del equipo que pueden haber avanzado en paralelo y no tienen acceso a este documento).

Seguimiento de todas las HU: completadas, parciales y sin implementar. Para ver el detalle de cada historia, ver [Discordia-TP](infra/docs/discordia-tp.md).

**Criterio:** una HU se marca como completada cuando el flujo funciona de punta a punta en el cliente web (`web-client`), con su respaldo en el servicio correspondiente y el relay del `gateway`. Las que tienen backend sin UI, o UI incompleta, se listan en «Parciales o solo backend».

## Obligatorias completadas — 77 / 104 pts

| # | Historia | Épica | Puntos |
| -- | --- | --- | --: |
| 1 | Registro de usuarios | Usuarios | 3 |
| 2 | Login con email y contraseña | Usuarios | 2 |
| 3 | Recupero de contraseña | Usuarios | 3 |
| 4 | Edición de perfil | Perfil | 2 |
| 5 | Visualización de perfil propio | Perfil | 1 |
| 6 | Crear servidor | Servidores | 3 |
| 7 | Generar invitación | Servidores | 5 |
| 8 | Unirse a servidor vía invitación | Servidores | 3 |
| 9 | Abandonar servidor | Servidores | 2 |
| 10 | Transferir propiedad del servidor | Servidores | 3 |
| 11 | Crear canal | Canales | 3 |
| 12 | Editar canal | Canales | 2 |
| 13 | Eliminar canal | Canales | 2 |
| 15 | Enviar mensaje en un canal | Mensajería | 8 |
| 16 | Historial y reconexión | Mensajería | 13 |
| 17 | Unirse a canal de voz de servidor | Canal de Voz | 11 |
| 18 | Salir de canal de voz | Canal de Voz | 1 |
| 19 | Silenciar micrófono propio | Canal de Voz | 1 |
| 20 | Ver participantes conectados | Canal de Voz | 3 |
| 21 | Crear rol | Roles y Permisos | 3 |
| 23 | Asignar rol a un miembro | Roles y Permisos | 3 |

## Optativas completadas — 18 pts

| # | Historia | Épica | Puntos |
| -- | --- | --- | --: |
| 33 | Login con proveedor federado | Usuarios | 5 |
| 40 | Eliminar servidor | Servidores | 5 |
| 44 | Editar mensaje | Mensajería | 3 |
| 45 | Eliminar mensaje | Mensajería | 3 |
| 58 | Ver miembros por rol | Roles y Permisos | 2 |

**Total implementado de punta a punta: 95 pts** (77 obligatorios + 18 optativos).

## Parciales o solo backend

| # | Historia | Épica | Puntos | Estado |
| -- | --- | --- | --: | --- |
| 14 | Organizar canales en categorías | Canales | 3 | El servicio acepta `categoryId`; la UI solo separa Texto/Voz. |
| 22 | Editar permisos de un rol | Roles y Permisos | 5 | No implementado. |
| 24 | Definir rol por defecto para nuevos miembros | Roles y Permisos | 2 | Solo el flag `isDefault` en el modelo; no se asigna ni se configura. |
| 25 | Banear miembro del servidor | Moderación | 3 | Backend + gateway (`POST /servers/{id}/bans`). Sin UI (caso S16 por API). |
| 26 | Revocar baneo | Moderación | 2 | No implementado (no hay endpoint). |
| 27 | Ver notificaciones no leídas | Notificaciones | 3 | No implementado (solo snackbars). |
| 28 | Marcar notificaciones como leídas | Notificaciones | 1 | No implementado. |
| 29 | Suspender usuario a nivel plataforma | Administración | 3 | API `PATCH /admin/accounts/{id}/status`; sin backoffice (caso M22). |
| 30 | Reactivar usuario suspendido | Administración | 1 | Ídem 29. |
| 31 | Ver listado de usuarios con filtros | Administración | 2 | `GET /admin/accounts`; sin backoffice. |
| 32 | Ver listado de servidores de la plataforma | Administración | 2 | No implementado. |
| 36 | Visualización de perfil público | Perfil | 2 | **Backend completo:** `GET /profiles/{id}/public` en `profile` (nombre, descripción y avatar; 404 si el perfil no existe o está suspendido), relayado por el gateway. El cliente ya lo consume para mostrar el nombre de otros usuarios en el chat y en el panel de miembros. **Falta:** la pantalla de perfil público (avatar y descripción de un tercero) y, de CA1, el estado de actividad y los servidores en común (ver ADR-007 en `profile`). |

## Sin implementar

Optativas 34–35, 37–39, 41–43, 46–57 y 59–69 (PIN, 2FA, estados, configuración de servidor, reordenamientos, DMs, adjuntos, menciones, reacciones, búsqueda, voz avanzada, moderación ampliada y notificaciones push).

## Notas

- **HU-21/23:** el gestor de roles permite listar, crear y asignar, pero **no** editar permisos (HU-22).
- **HU-36:** el endpoint público responde 200 o 404, así que antes de exponerlo masivamente hace falta el rate limit estricto por IP en el gateway (riesgo de enumeración documentado en ADR-007).
- **Trackers complementarios:** el detalle técnico de cada tarea y sus pendientes vive en [Backlog.json](Backlog.json); los pendientes de infraestructura y CI, en [mejoras-ci-cd.md](mejoras-ci-cd.md).
