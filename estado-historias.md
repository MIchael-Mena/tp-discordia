# Estado de las Historias de Usuario — Discordia

**Actualizado:** 2026-11-01 (tener en cuenta que hay otros miembros del equipo que pueden haber avanzado en paralelo y no tienen acceso a este documento).

Seguimiento de todas las HU: completadas, parciales y sin implementar. Para ver el detalle de cada historia, ver [Discordia-TP](infra/discordia-tp.md).

**Criterio:** una HU se marca como completada cuando el flujo funciona de punta a punta en el cliente que le corresponde —`web-client` para las historias de usuario final, `backoffice` para las de staff—, con su respaldo en el servicio correspondiente y el relay del `gateway`. Las que tienen backend sin UI, o UI incompleta, se listan en «Parciales o solo backend».

## Obligatorias completadas — 102 / 104 pts

| # | Historia | Épica | Puntos | Checkpoint |
| -- | --- | --- | --: | --: |
| 1 | Registro de usuarios | Usuarios | 3 | 1 |
| 2 | Login con email y contraseña | Usuarios | 2 | 1 |
| 3 | Recupero de contraseña | Usuarios | 3 | 2 |
| 4 | Edición de perfil | Perfil | 2 | 1 |
| 5 | Visualización de perfil propio | Perfil | 1 | 1 |
| 6 | Crear servidor | Servidores | 3 | 2 |
| 7 | Generar invitación | Servidores | 5 | 2 |
| 8 | Unirse a servidor vía invitación | Servidores | 3 | 2 |
| 9 | Abandonar servidor | Servidores | 2 | 2 |
| 10 | Transferir propiedad del servidor | Servidores | 3 | 3 |
| 11 | Crear canal | Canales | 3 | 2 |
| 12 | Editar canal | Canales | 2 | 2 |
| 13 | Eliminar canal | Canales | 2 | 2 |
| 14 | Organizar canales en categorías | Canales | 3 | 3 |
| 15 | Enviar mensaje en un canal | Mensajería | 8 | 2 |
| 16 | Historial y reconexión | Mensajería | 13 | 2 |
| 17 | Unirse a canal de voz de servidor | Canal de Voz | 11 | 2 |
| 18 | Salir de canal de voz | Canal de Voz | 1 | 2 |
| 19 | Silenciar micrófono propio | Canal de Voz | 1 | 2 |
| 20 | Ver participantes conectados | Canal de Voz | 3 | 2 |
| 21 | Crear rol | Roles y Permisos | 3 | 2 |
| 22 | Editar permisos de un rol | Roles y Permisos | 5 | 3 |
| 23 | Asignar rol a un miembro | Roles y Permisos | 3 | 2 |
| 24 | Definir rol por defecto para nuevos miembros | Roles y Permisos | 2 | 3 |
| 25 | Banear miembro del servidor | Moderación | 3 | 3 |
| 26 | Revocar baneo | Moderación | 2 | 3 |
| 27 | Ver notificaciones no leídas | Notificaciones | 3 | 3 |
| 28 | Marcar notificaciones como leídas | Notificaciones | 1 | 3 |
| 29 | Suspender usuario a nivel plataforma | Administración | 3 | 2 |
| 30 | Reactivar usuario suspendido | Administración | 1 | 2 |
| 31 | Ver listado de usuarios con filtros | Administración | 2 | 2 |

## Optativas completadas — 38 pts

| # | Historia | Épica | Puntos | Checkpoint |
| -- | --- | --- | --: | --: |
| 33 | Login con proveedor federado | Usuarios | 5 | 2 |
| 36 | Visualización de perfil público | Perfil | 2 | 3 |
| 37 | Estado de actividad en tiempo real | Perfil | 5 | 3 |
| 40 | Eliminar servidor | Servidores | 5 | 2 |
| 41 | Reordenar canales | Canales | 2 | 3 |
| 44 | Editar mensaje | Mensajería | 3 | 2 |
| 45 | Eliminar mensaje | Mensajería | 3 | 2 |
| 55 | Eliminar rol | Roles y Permisos | 3 | 3 |
| 56 | Reordenar jerarquía de roles | Roles y Permisos | 3 | 3 |
| 57 | Sobrescribir permisos de un rol en un canal específico | Roles y Permisos | 5 | 3 |
| 58 | Ver miembros por rol | Roles y Permisos | 2 | 2 |

**Total implementado de punta a punta: 140 pts** (102 obligatorios + 38 optativos).

## Parciales o solo backend

| # | Historia | Épica | Puntos | Estado |
| -- | --- | --- | --: | --- |
| 32 | Ver listado de servidores de la plataforma | Administración | 2 | No implementado. |

## Sin implementar

Optativas 34–35, 38–39, 42–43, 46–54 y 59–69 (PIN, 2FA, estado personalizado, configuración de servidor, DMs, adjuntos, menciones, reacciones, búsqueda, voz avanzada, moderación ampliada y notificaciones push).

## Notas

- **HU-14:** las categorías se administran desde la barra lateral (crear, renombrar, eliminar y mover canales) y agrupan canales de texto y de voz en una sección por categoría, con **General** para los que no tienen ninguna. El backend es la fuente de verdad (`channel_categories` con FK `ON DELETE SET NULL`, `V6`), `GET /servers/{id}` expone `canManageChannels` y las rutas nuevas se relayan por el gateway (`023-channel-categories`).
- **HU-41:** el orden se cambia con un `position` **aditivo** en los dos `PATCH` que ya existían (`024-channel-reordering`), definido como **hueco de inserción** sobre la lista original — el corrimiento del mismo bucket (`slot - 1`) lo aplica el servidor, y el cliente manda el hueco crudo. El servidor renumera `0..n-1` bajo el lock pesimista del server y la base lo respalda con `UNIQUE NULLS NOT DISTINCT (server_id, category_id, position) DEFERRABLE` (V7); al borrar una categoría, General se renumera porque la FK `SET NULL` devolvía los canales con posiciones duplicadas. En el cliente se arrastra con `PanResponder` (touch en móvil y mouse en web, sin dependencias nuevas) y hay «Subir»/«Bajar» en los menús como camino accesible, con orden optimista y rollback. **El gateway no cambió**: relaya el cuerpo tal cual. Sigue fuera de alcance el auto-scroll durante el arrastre. El reorden de la jerarquía de roles (HU-56) reusa el mismo patrón y está implementado en `025-role-hierarchy`.
- **HU-56:** el orden de la jerarquía se cambia con `PATCH /servers/{serverId}/roles/{roleId}` y un `position` que también es **hueco de inserción** (`025-role-hierarchy` en `server`, `gateway` y `web-client`). El servidor renumera `0..n-1` bajo el lock pesimista del server, respaldado por la constraint diferida que ya tenía `V4` (**sin migración nueva**), y responde con la jerarquía completa ya renumerada. El CA 2 se aplica con dos guards: no se mueve un rol igual o superior al propio **y** el destino no puede quedar por encima del rol más alto del caller (si no, mover un rol propio al tope sorteaba la regla). En el cliente la misma señal `editable` de la HU-22 decide qué filas se pueden mover y dónde está el tope; hay arrastre con el handle de la HU-41 y flechas Subir/Bajar, con orden optimista y rollback. La jerarquía dejó de vivir en el popup: `pages/index.tsx` la guarda por servidor porque `GET /servers/{id}` no embebe roles y el live sync no la trae.
- **HU-21/22/23/24/55/56/57/58 (Épica Roles y Permisos 100% completada):** el gestor de roles permite listar, crear, asignar y desasignar miembros respetando jerarquía (Etapa 1), **editar los permisos de un rol** (HU-22), **reordenar la jerarquía** (HU-56), **definir el rol por defecto del servidor** (HU-24, asignación automática al unirse, índice único parcial en PostgreSQL V9 y switch protegido en la UI) y **eliminar roles** (HU-55, desasignación en cascada, renumeración 0..n-2, bloqueo por jerarquía y bloqueo al intentar eliminar el rol por defecto).
- **HU-25/26:** el baneo evalúa `BAN_MEMBERS` con restricción por jerarquía y el baneado ve el servidor como inexistente; `text-channel` corta también el acceso al historial. UI en el panel de miembros (`BanConfirmation` / `RevokeBanConfirmation`) con listado de baneados (`019-ban-unban-members`).
- **HU-27/28:** el estado de no leído lo posee el servicio `notifications` (`GET /notifications/unread`, `PUT /notifications/read-markers/channels/{id}` y `POST /notifications/read-markers/read-all`, alimentado por los `message_events` que publica `text-channel` y por la copia propia de membresías que refresca contra `server`); el `gateway` lo relayá por REST y WebSocket (`app/notifications.py`) y el cliente pinta el punto por canal y por servidor, lo limpia al abrir el canal y ofrece «Marcar todo como leído» (`022-unread-indicators`). El **CA 3 de la HU-27** (indicador destacado para menciones) queda pendiente porque depende de la optativa HU-46 (menciones), fuera de alcance. **Despliegue pendiente:** `notifications` todavía no está en `infra/compose.prod.yaml`, así que en producción esas rutas responden 502 hasta que se lo agregue.
- **HU-29/30/31:** el `backoffice` (cliente Expo de staff) lista cuentas con búsqueda por usuario/email y filtro por estado, suspende con confirmación y reactiva; `auth-service` es el dueño del estado (`PATCH /account/{id}/status`), invalida los refresh tokens y publica `AccountSuspended` / `AccountReactivated`; el `gateway` exige `role == "admin"`, reenvía el `X-User-Id` del staff (para impedir la auto-suspensión) y revoca los access tokens de los `sid` devueltos; `profile` oculta el perfil y lo restituye, y `text-channel` cierra el WebSocket. **Pendiente menor:** `voice-calls` no consume `AccountSuspended`, así que un suspendido no se desconecta de una sala de voz.
- **HU-36:** el perfil público se abre como popup desde la fila de un miembro y desde el nombre de un autor ajeno en el chat (`026-public-profile-ui`). Compone `GET /profiles/{id}/public` (nombre, avatar, descripción y `activity_status`) con `GET /users/{id}/mutual-servers`, y degrada de a una: sin presencia no hay indicador, y si fallan los servidores en común la sección avisa y ofrece reintentar. El `gateway` publica ambas rutas (`026-public-profile-relay`) y la del perfil lleva **rate limit propio** (`PUBLIC_PROFILE_RATE_LIMIT`, 10/s + 120/min): antes la atendía el catch-all, que no admite presupuesto por ruta, y el límite global dejaba 1200/min para enumerar ids secuenciales. La barra de usuario pasó a ser un menú (Mi perfil / Editar perfil / Cerrar sesión) pensado para las acciones de sesión futuras.
- **HU-36, pendiente de seguridad:** el techo de enumeración bajó de 1200/min a 120/min, pero cerrarlo del todo exige validar que quien consulta **comparte un servidor** con el consultado (no vive en `profile` ni en el `gateway`) y, con eso, el `POST /profiles/public/batch` que permitiría etiquetar una lista de miembros en una sola request. Además, en `WS /ws/presence` la presencia quedó **suscripción por usuario** con token bucket (1 comando/s, ráfaga 3, agregado por usuario y retenido entre reconexiones) porque el fan-out original entregaba la presencia de toda la plataforma a cualquier sesión; el riesgo residual es que la presencia es un oráculo de conexión y no de existencia, y se cierra con la misma validación de servidor compartido (ADR-008).
- **HU-37:** el estado de actividad se ve **en vivo** en la lista de miembros, en el perfil público y en la barra de usuario (`027-presence-ui`), con un solo WebSocket por sesión que el `gateway` relaya (`027-presence-relay`). El cliente **espeja el presupuesto** del servicio en vez de gastarlo: los componentes registran interés con `usePresenceWatch`, el provider fusiona todos los watchers en un set (tope de 200 ids), agrupa las altas con 1 s de debounce y posterga el envío con un token bucket local; las bajas viajan como `unsubscribe`, que es gratis. El latido solo sale **tras interacción real y con la pestaña visible** —así una sesión inactiva de verdad deriva a ausente (CA2)— pero al volver se manda en el acto, con piso de 1 s. El estado propio se lee por REST porque `INVISIBLE` llega proyectado como `OFFLINE` por el socket. El relay del gateway **propaga los códigos de cierre privados** (4429, 4404): sin eso el cliente los ve como 1005 y reconecta en bucle contra un servicio que lo sigue rechazando (lo encontró el E2E, no los tests con fakes).
- **HU-37, pendiente estructural:** el hub y el token bucket de `profile` viven en memoria, así que con más de una réplica el techo se multiplica y el fan-out no cruza réplicas; mudarlos a Redis va junto con la validación de servidor compartido de HU-36.
- **Trackers complementarios:** el detalle técnico de cada tarea y sus pendientes vive en [Backlog.json](Backlog.json); los pendientes de infraestructura y CI, en [mejoras-ci-cd.md](mejoras-ci-cd.md).
