# Auditoría de Código y Q&A de Defensa — Checkpoint 3 · Michael

Respaldo técnico enfocado exclusivamente en tus diapositivas asignadas: **Sección 06 (`slide 8 from pdf`: `06`, `06.1`, `06.2`, `06.3`, `06.4`, `06.5`) + `Progreso` (`slide 10`) + `Cierre` (`slide 11`)**.

---

## 1. Auditoría Slide ↔ Código Real

### Diapo `06.1` — Ver y marcar notificaciones (`HU-27`, `HU-28`)

| Afirmación de la slide | Qué hace realmente el código | Matiz / límite a tener presente |
|---|---|---|
| *"Campana permanente en el riel de servidores con la cantidad de canales no leídos; sin pendientes no muestra badge."* | `Sidebar.tsx` (`lines 967-1000`) renderiza la campana y muestra `unreadCount` solo cuando `unreadCount > 0` (`99+` si supera 99). `UnreadProvider.tsx` (`line 843`) lo calcula con `getTotalUnreadCount(state)` (`unreadState.ts:736-757`), deduplicando `unread` + `mentions` activos y excluyendo `none` y actividad ordinaria en nivel `mentions`. | **Badge vs bandeja en `VIEW_CHANNELS`:** ver punto siguiente. |
| *"La bandeja solo lista canales visibles para el usuario (permiso `VIEW_CHANNELS`)."* | En **`web-client` (`useUnreadDirectory.ts:128-134, 253-264`)**, cada servidor con no leídos consulta `GET /servers/{id}` (donde `server` filtra `channels` por `VIEW_CHANNELS`), y la bandeja descarta cualquier `channelId` ausente en `server.channels`. Ante eventos `server_sync`, invalida caché con jitter `0–300 ms`. | **`notifications` y `server` interno no filtran overrides:** `server/src/main/java/discordia/core/usecase/ListUserMemberships.java` (`lines 30-39`) devuelve todos los canales del servidor en `/internal/users/{userId}/memberships`, y `UnreadState` (`notifications/app/core/usecases/unread_state.py`) no conoce bitmasks ni overrides. Por eso: (a) la **bandeja** (`NotificationsInboxPopup`) sí filtra por `VIEW_CHANNELS`, pero (b) `GET /notifications/unread` directo por API o `totalUnreadCount` de la campana (que lee directo de `state.unread` antes del directorio) podrían reflejar un canal al que se revocó `VIEW_CHANNELS`. |
| *"con la marca de tiempo `max(lastActivityAt, now)` del backend para evitar desfase de reloj."* | **Dos mitades complementarias:** en el **cliente** (`UnreadProvider.tsx:646-654`), `markChannelAsRead` elige `pickLatestTimestamp(lastActivityAt, recorded, now)` = `max(lastActivityAt, now)` para no perder cobertura si el reloj local está atrasado. En el **backend** (`notifications/app/core/usecases/mark_read.py:58-59`), `MarkChannelRead.execute` ejecuta **`up_to = min(up_to, now)`** (clamping contra el reloj UTC del servidor). Y `MongoReadMarkerStore.mark` (`read_markers.py:15-18`) usa `upsert_if_newer` para que el marcador solo avance. | Si el profesor mira `mark_read.py` y ve `min(up_to, now)` mientras la slide dice `max(...)`, explicá exactamente esa división: cliente hace `max(lastActivityAt, now)` contra reloj atrasado; backend hace `min(upTo, serverNow)` contra reloj adelantado. |
| *"El marcado de lectura avanza un marcador y no borra el aviso."* | `read_markers` solo avanza `readUpTo` (`upsert_if_newer`); en `notices`, `MarkChannelRead` pone `read: True` (`MongoNoticeStore.mark_channel_read`). | El autor tampoco se auto-notifica gracias a `AuthorReadProjector` (`author_read.py:7-32`) para canales y a `UnreadState.execute` (`actors.get(target) != user_id`) + `ExcludeActor` (`policy.py:9-15`). |

---

### Diapo `06.2` — Centro de notificaciones con historial (`HU-67`)

| Afirmación de la slide | Qué hace realmente el código | Matiz / límite a tener presente |
|---|---|---|
| *"Menciones destacadas y mensajes directos se guardan por usuario en `notices` y se entregan por WS."* | `HighlightedMentionHandler` (`highlighted_mention.py`) y `DirectMessageHandler` (`direct_message.py`) usan `StorageTier.PER_USER` → `MongoNoticeStore.insert_many` en colección `notices` (con `_id = "{noticeId}:{recipient}"` para idempotencia ante reintentos `BulkWriteError` code `11000`). Si la audiencia supera `large_audience_threshold` (`1000`), `NoticePipeline` degrada a `COMPUTED_ON_READ` (`notice_pipeline.py:79-85`). | Solo `@menciones` y `DMs` van a `notices`; mensajes comunes de canal son `channel_activity` (`COMPUTED_ON_READ` en `target_activity`), por eso el Historial no se llena con miles de mensajes ordinarios. |
| *"Al marcar un canal o todo como leído se pone `read: true` sin eliminar."* | `MarkChannelRead` llama a `notices.mark_channel_read(user_id, channel_id, up_to=up_to)` y `MarkAllRead` llama a `notices.mark_all_read(user_id)`. Ningún endpoint de usuario hace `delete` de `notices`. | **`mark_channel_read` vs `mark_all_read`:** `mark_channel_read` (`notices.py:89-90`) sí aplica el corte `createdAt <= up_to` (`$lte`); en cambio, `mark_all_read` (`notices.py:70-75`) marca todas las pendientes (`read: False` → `True`) sin filtro de timestamp, mientras los `read_markers` se fijan en `now`. |
| *"El inbox devuelve hasta 100 avisos; `unreadOnly` filtra solo los pendientes."* | `inbox_controller.py` (`lines 25-33`) expone `limit: int = Query(default=50, ge=1, le=100)`, `unreadOnly: bool = False`, `offset >= 0`, `days: [1..90]` y `kind`. Índice compuesto `notices_recipient_created_id_idx` (`indexes.py:17-20`) ordena `(createdAt DESC, _id DESC)` en expand/contract junto al índice previo. | **Paginación en UI:** `useInboxHistory.ts` (`lines 5-7, 82-88`) consulta páginas de `HISTORY_PAGE_SIZE = 20` (pide `21` para calcular `hasMore` sin `count_documents`), acotado a `days = 7` y `kind = 'highlighted_mention,direct_message'`, y deduplica por `id` en `loadMore` (`line 186`) por si un aviso nuevo desplaza el `offset`. |
| *"Solo afecta avisos con `createdAt` anterior al corte."* | En Mongo (`notices.py:90`) el operador es `$lte` (`createdAt <= as_utc(up_to)`), con normalización UTC unificada (`as_utc` / `normalize_utc`) frente a datetimes naive de MongoDB. | Es "hasta el corte inclusive" (`<=`), así el aviso que originó `lastActivityAt` queda cubierto. |

---

### Diapo `06.3` — Preferencias (`HU-65`) y silenciamiento (`HU-64`)

| Afirmación de la slide | Qué hace realmente el código | Matiz / límite a tener presente |
|---|---|---|
| *"`PUT` y `DELETE` sobre `/notifications/mutes`... reactivar es idempotente (`204`)."* | `mutes_controller.py` expone `/notifications/mutes/{channels|servers}/{id}`; `preferences_controller.py` expone `/notifications/preferences/{channels|servers}/{id}`. Ambos delegan en `MongoMuteStore` (`mutes.py:26-137`) sobre la colección `mutes` con `_id = "{userId}:{target.type}:{target.id}"` y `DELETE` devuelve `204` aun si no había doc. | Se requiere membresía activa o ser participante DM (`require_channel_access` / `require_server_access`), si no devuelve `404`. Además `gateway/app/notifications.py` valida segmentos con `_encode_path_segment` y no reintenta mutaciones (`PUT`/`DELETE`). |
| *"Nivel = `canal ?? servidor ?? all`; `all`, `mentions`, `none`."* | `resolve_effective_level` (`preferences.py:26-35`) en backend y `resolveChannelPreference` (`unreadState.ts:568-598`) en frontend aplican exactamente **canal > servidor > `all`**. | **Qué decide el backend vs el frontend:** `RespectMutes` (`policy.py:18-30`) filtra **solo `NotificationLevel.NONE`** en avisos mutables (`highlighted_mention` y `direct_message`). El nivel **`mentions`** (ocultar tráfico común de la campana/sonido/tab "Canales", dejando un punto discreto) lo resuelve el **frontend** (`UnreadProvider.tsx:92`, `unreadState.ts:742`, `useUnreadDirectory.ts:230-232`) porque los mensajes comunes de canal (`channel_activity`) ya tienen `pushable=False` y no generan documentos en `notices`. |
| *"Sincronización entre dispositivos (`mute_updated`, `preference_updated`)."* | `_BaseMuteAction` (`mutes.py:74-82`) emite `mute_updated`; `_BasePreferenceAction` (`preferences.py:81-89`) emite `preference_updated` con `level: null` al limpiar. Además `UnreadProvider` mantiene reconciliación optimista anti-carreras (`inFlightPreferencesRef` + `preferenceUpdatesRef` al volver de `ready`). | Al igual que la entrega de avisos, el `ConnectionRegistry` de `notifications` vive en memoria (`InMemoryConnectionRegistry`), lo cual asume 1 réplica de `notifications` (como está hoy en `compose.prod.yaml`). |
| *"Un canal o servidor silenciado no genera menciones destacadas, pero la actividad nueva sigue contando como no leída."* | `ChannelActivityHandler` (`channel_activity.py:34`) declara **`mutable=False`**, por lo que `RespectMutes` no lo filtra nunca: actualiza `target_activity` y emite `channel_activity`. En UI, los canales/DMs en `none` aparecen agrupados aparte en colapsables *"Silenciados con actividad"* / *"Silenciadas"* (`NotificationsInboxPopup.tsx:770-848`). | En `HighlightedMentionHandler` / `DirectMessageHandler`, cuando el destino está en `none`, `RespectMutes` **ni siquiera persiste `notices` ni envía WS/push** para ese destinatario. (Sí puede figurar el canal en *"Silenciados con actividad"* vía `target_activity`, y las menciones previas al mute siguen apareciendo en *"Silenciadas"* hasta marcarse leídas). |

---

### Diapo `06.4` — Notificaciones push en mobile (`HU-66`)

| Afirmación de la slide | Qué hace realmente el código | Matiz / límite a tener presente |
|---|---|---|
| *"En mobile se obtiene el token con `expo-notifications` y se registra en el backend; al cerrar sesión se desregistra antes de revocarla."* | `expo-notifications ~57.0.25` está configurado en `web-client/package.json` y `web-client/app.json` (permiso `POST_NOTIFICATIONS`, `projectId`). `pushService.ts:166-209` crea el canal Android (`default`, `HIGH`), pide permiso, obtiene Expo Push Token y llama a `POST /notifications/push-tokens`. En logout, `authThunks.ts:172-180` ejecuta `await unregisterCurrentPushToken()` (timeout `1500 ms`) **antes** de `await logoutApi()`. | **Seguridad multi-cuenta:** `MongoPushStore.upsert_token` (`push.py:58`) borra previamente `{token, userId: {$ne: user_id}}` antes del upsert, y `PushTokenCleanupProjector` borra todos los tokens al consumir `AccountSuspended` / `AccountDeleted`. **Build nativo vs Expo Go:** en producción Android/iOS requiere credenciales FCM/APNs en EAS (en código cliente y backend ya está todo conectado). |
| *"En background se cierra el WebSocket; el servidor ve al usuario sin conexiones y envía el push por menciones y DMs."* | En mobile (`UnreadProvider.tsx:375-378, 546-573`), ante `AppState` `background`/`inactive`, `UnreadProvider` detiene timers y cierra `/ws/notifications`. Al reconectar en `active`, refetchea unread/inbox/preferencias en `onReady`. En backend, `PushDeliveryAdapter.deliver` (`push.py:88-90`) filtra `self._registry.count(u) == 0`, `filter_push_enabled` y tokens, enviando batches de hasta `100` a `https://exp.host/--/api/v2/push/send` y borrando tokens `DeviceNotRegistered`. | **Dos límites importantes:** (1) `InMemoryConnectionRegistry` es por proceso (ok con 1 réplica en `compose.prod.yaml`, habría que compartir presencia WS en Redis al escalar `notifications`); (2) **Web abierta bloquea push móvil:** en Web (`Platform.OS === 'web'`), la pestaña oculta **no** cierra `/ws/notifications` (lo necesita abierto para `Notification` del navegador), así que si un usuario deja Discordia abierto en la PC y sale con el celular, `count >= 1` impide el push Expo al teléfono. |
| *"Interruptor global 'Notificaciones push' con botón Guardar; no altera badges ni historial dentro de la app."* | `UserMenu.tsx:588` y el ícono en `NotificationsInboxPopup.tsx:712` abren `NotificationPreferencesPopup` en modo `targetType="global"` (`Guardar` → `PUT /notifications/push-settings`). `PushDeliveryAdapter` consulta `push_settings`; `Notices`, `UnreadState` y `WebSocketDeliveryAdapter` no se ven afectados. | El estado global por usuario (`pushEnabled`, default `true`) aplica a todos los dispositivos de la cuenta (se sincroniza por WS vía `push_settings_updated`, pero en un dispositivo móvil con token activo, al pasar a `false` también desregistra su token en `syncDevicePushToken`). |
| *"El texto se sanea (`<@id>` pasa a `@usuario`). En web solo hay aviso con la pestaña oculta."* | Backend `sanitize_push_snippet` (`notifications/app/infra/delivery/push.py:20-26`) reemplaza `<@&...>` → `@rol` y `<@!?...>` → `@usuario`. Cliente Web `sanitizeNotificationSnippet` (`pushService.ts:75-89`) sanea igual y `showBrowserPushNotification` (`lines 128-149`) exige `Platform.OS === 'web'`, `document.visibilityState === 'hidden'` y permiso `granted`. | Coherencia con **Slide 7 (`Voz en mobile`)**: `PrivateVoiceCallHandler` (`private_voice_calls.py:24`) tiene `pushable=False`, por lo que las llamadas entrantes no mandan push Expo; solo menciones y DMs. |

---

### Diapo `06.5` — Perfil público (`HU-36`), presencia (`HU-37`) y estado personalizado (`HU-38`)

| Afirmación de la slide | Qué hace realmente el código | Matiz / límite a tener presente |
|---|---|---|
| *"`GET /profiles/{id}/public` devuelve solo nombre, descripción y avatar; inexistente o suspendido responde `404`."* | `PublicProfileResponse` (`profile_contract.py:51-61`) expone 6 campos públicos: `user_id`, `name`, `description`, `avatar_url`, `custom_status` y `activity_status` (omite metadata privada como `registration_date`, `status`, `version`, `updated_at`). `RetrieveProfile` retorna `None` si `SUSPENDED` → `404` uniforme. | **Dónde vive la co-membresía:** `profile` no la conoce; la aplica el **`gateway`** (`gateway/app/profiles.py:207-412`): consulta `POST /users/co-members` en `server`, y para IDs restantes consulta `GET /conversations?limit=200` en `text-channel` (excepción DM de HU-25). Si tampoco hay DM, el Gateway corta con `404` (o filtra en `POST /profiles/public/batch`). Roles `admin` (staff de backoffice) sí pueden consultar sin co-membresía. |
| *"En línea al conectarse, ausente tras inactividad; no molestar e invisible se fijan a mano y persisten."* | `WS /ws/presence` conecta → `ConnectActivity` marca `connected=True` (`ONLINE` si es `AUTOMATIC`, o mantiene `DO_NOT_DISTURB` / `INVISIBLE` si es `MANUAL`). `PresenceProvider.tsx` manda heartbeats `{"type":"activity"}` cada `60 s` (o eager al volver de `AWAY` si hubo interacción y la vista está visible). En `profile/app/main.py:30-43`, `_presence_sweep_loop` corre cada `10 s` y pasa a `AWAY` tras `300 s` sin heartbeat. | Al desconectar el último socket del usuario (tolera múltiples pestañas/dispositivos hasta `8` sockets, código `4429`), `DisconnectActivity` marca `connected=False` (y `OFFLINE` en modo automático). A diferencia de `UnreadProvider`, `PresenceProvider` **no** cierra `/ws/presence` explícitamente ante `AppState` `background` en mobile (solo deja de enviar heartbeats cuando `isVisible()` es falso). |
| *"El cliente pide los ids que muestra y recibe `presence_snapshot` y `presence_changed` solo de ellos... 3 ráfaga + 1/s... oráculo de conexión, no de existencia. Invisible no se filtra."* | `PresenceHub` (`presence_hub.py`) mantiene `self._users` y `self._watchers`. Al abrir WS envía `presence_snapshot([])` vacío. `subscribe(user_ids)` acepta hasta `200` IDs, bajo `TokenBucket` por **usuario** (3 ráfaga, 1/s, TTL `60 s` tras cerrar último socket). Si agota budget responde `{"type":"error","code":"rate_limited"}` sin cerrar ni perder suscripción previa. `effective_activity_type` (`profile_dto`) proyecta `INVISIBLE` o desconectado siempre como `OFFLINE`. | **Oráculo de conexión y escala:** `WS /ws/presence` (`presence_controller.py:208-228`) **NO** valida co-membresía contra `server` en `subscribe` (documentado en `profile/docs/arquitectura/adr-008` y `estado-historias.md:138`). Solo lista conectados (`ListConnectedActivity`), así que un ID inexistente y un usuario offline/invisible son indistinguibles. Además `PresenceHub` y `TokenBucket` viven **en memoria** (`1` réplica en `compose.prod.yaml`); con N réplicas habría que mover pub/sub y bucket a Redis. |
| *"Texto de hasta 64 caracteres... editable y borrable al instante; `custom_status_changed` por WS... se lee filtrado por co-membresía."* | `PUT`/`DELETE /profiles/{user_id}/custom-status` (`profile_controller.py:330-404`, `SetCustomStatus`) guardan en tabla `custom_statuses` (`VARCHAR(64)`, sin saltos de línea, 1–64 caracteres Unicode code points consistentes entre JS `Array.from`, Python `len` y PostgreSQL `VARCHAR(64)`). Va fuera del `version`/`If-Match` del perfil (`last write wins`). `DELETE` devuelve `204` idempotente (sin emitir WS si no había nada). | **Por qué no entra en `presence_snapshot` (`adr-012`):** Como `WS /ws/presence` no valida co-membresía, incluir `custom_status` en el `presence_snapshot` permitiría leer textos de desconocidos con `subscribe`. Por eso la lectura inicial entra exclusivamente vía REST (`GET /public` o `POST /public/batch`, filtrados por co-membresía en `gateway`), y por WS solo se emite `custom_status_changed` cuando cambia en vivo. Independiente de `INVISIBLE`/offline. |

---

### Diapo `Progreso` (`slide 10`) y `Cierre` (`slide 11`)

Verificado 100% contra `estado-historias.md` (cálculo exacto sobre las 81 filas del catálogo):
- **Catálogo total:** 81 historias · 333 pts (32 obligatorias = 104 pts; 49 optativas = 229 pts).
- **Base previa (CP1 + CP2):** 23 obligatorias (80 pts) + 4 optativas (16 pts: HU-33, 40, 44, 45) = **27 HUs · 96 pts**.
- **Nuevo en CP3:** **38 HUs · 151 pts** (**9 obligatorias · 24 pts** + **29 optativas · 127 pts**).
- **Acumulado final:** **32/32 obligatorias (104/104 pts — 100%)** + **33/49 optativas (143/229 pts)** = **65/81 HUs · 247 pts**.
- **Desglose de los 151 pts de CP3 por las 6 secciones del deck:**
  - `01 Administración y estructura`: `4` HUs (`2` oblig + `2` opt) = `11` pts (HU-10, 14, 39, 41).
  - `02 Roles y permisos`: `6` HUs (`2` oblig + `4` opt) = `20` pts (HU-22, 24, 55, 56, 57, 58).
  - `03 Moderación y operación`: `11` HUs (`3` oblig + `8` opt) = `41` pts (HU-25, 26, 32, 59, 60, 61, 62, 63, 68, 69, 81).
  - `04 Mensajería y colaboración`: `6` HUs (`0` oblig + `6` opt) = `29` pts (HU-42, 43, 46, 47, 48, 49).
  - `05 Voz y video`: `2` HUs (`0` oblig + `2` opt) = `21` pts (HU-50, 54).
  - `06 Notificaciones y presencia`: `9` HUs (`2` oblig + `7` opt) = `29` pts (HU-27, 28, 36, 37, 38, 64, 65, 66, 67).
- **Mínimos por tamaño de equipo:** 4 integ. = 48 opt (152 tot) · 5 integ. = 80 opt (184 tot) · **6 integ. = 112 opt (216 tot)**. Con **247 pts** (`143` opt) superan el mínimo en **+31 pts**.

---

## 2. Preguntas Posibles del Profesor y Respuestas de Defensa (Q&A)

### Sobre Bandeja, Marcadores y `VIEW_CHANNELS` (`06.1`)

**P1: En la slide dicen que la bandeja filtra por `VIEW_CHANNELS`, pero si miro `notifications` (`unread_state.py`) y `server` (`/internal/users/{id}/memberships`), ninguno evalúa `VIEW_CHANNELS`. ¿Cómo funciona realmente y qué pasa con el número rojo de la campana?**  
*R:* `notifications` no conoce el modelo bitmask ni overrides de roles; su dominio son eventos, actividad por target y marcadores. El filtro estricto de `VIEW_CHANNELS` en la bandeja (`NotificationsInboxPopup`) se hace en el `web-client` (`useUnreadDirectory`) cruzando las respuestas de `GET /notifications/unread` contra `GET /servers/{id}`, que sí viene filtrado por `VIEW_CHANNELS` desde Quarkus, e invalidando esa caché con `server_sync` ante cambios de permisos. Es cierto que un canal oculto recién restringido no entra nunca a la lista de la bandeja, pero la suma bruta de la campana (`totalUnreadCount`) y `GET /notifications/unread` hoy todavía lo contarían si existía actividad previa en ese canal; filtrarlo también desde `/internal/users/{id}/memberships` en `server` cerraría esa brecha de raíz sin acoplar `notifications` a permisos.

**P2: En la slide hablan de `max(lastActivityAt, now)` para el clock skew, pero en `notifications/app/core/usecases/mark_read.py` se ve `up_to = min(up_to, now)`. ¿No es contradictorio?**  
*R:* Son dos protecciones complementarias, una de cada lado del contrato. En el cliente (`UnreadProvider.tsx`), `markChannelAsRead` toma el **`max(lastActivityAt, recorded, now)`** para que, si el reloj del dispositivo del usuario está atrasado respecto del servidor, el `upTo` enviado cubra igual el mensaje que acaba de leer. En el backend (`MarkChannelRead`), aplicamos **`min(up_to, serverNow)`** para acotar hacia arriba contra el reloj del servidor: si un cliente tuviera el reloj adelantado (o enviara una fecha futura maliciosa), jamás podría marcar como pre-leídos mensajes que todavía no llegaron.

**P3: ¿Por qué el usuario nunca ve sus propios mensajes como no leídos, incluso si abre otro dispositivo después?**  
*R:* Porque tenemos doble guarda. Al consumir `message_events.MessageCreated`, el `AuthorReadProjector` (`notifications/app/core/projectors/author_read.py`) corre **antes** que los handlers y avanza el `readUpTo` del autor hasta el timestamp del evento; además `UnreadState` verifica `actors.get(target) != user_id` y el pipeline aplica `ExcludeActor` para no emitir avisos en vivo al emisor.

---

### Sobre Historial y Consistencia (`06.2`)

**P4: ¿Por qué no guardan todos los mensajes comunes en `notices` y solo persisten menciones destacadas y DMs? ¿Cómo escala eso?**  
*R:* Por cardinalidad (`StorageTier.COMPUTED_ON_READ` vs `PER_USER`): en un canal de un servidor con 1.000 miembros, escribir 1.000 documentos por cada línea de chat multiplicaría la escritura de MongoDB por N. Para tráfico común guardamos una sola marca `target_activity` por canal y comparamos contra `read_markers` al consultar; solo lo personalmente relevante (menciones y DMs) va a `notices` —y aun así, si una mención `@everyone` supera `large_audience_threshold = 1000`, el pipeline la degrada automáticamente a `COMPUTED_ON_READ`.

**P5: ¿Cómo evitan que al hacer clic en "marcar leído" se borre una mención que llegó exactamente en ese instante, y cómo evitan duplicados al paginar historial con `offset`?**  
*R:* Para el marcado por canal (`MongoNoticeStore.mark_channel_read`), el `update_many` filtra explícitamente `createdAt <= up_to`, de modo que cualquier mención posterior queda en `read: False`. Para la paginación del historial, en Mongo creamos el índice compuesto `(recipientId: 1, createdAt: -1, _id: -1)` (`notices_recipient_created_id_idx`) para que empates exactos de timestamp tengan orden determinista, y en `useInboxHistory.ts` deduplicamos por `id` al anexar páginas con `loadMore` en caso de que entre un aviso nuevo mientras el usuario scrollea (`offset` corrido).

**P6: ¿Por qué dejaron los índices viejos de MongoDB al sumar `notices_recipient_created_id_idx`?**  
*R:* Por *expand/contract* en MongoDB: cambiar o dropear un índice existente sobre una colección ya desplegada con el mismo nombre o patrón provoca `IndexOptionsConflict` al iniciar la nueva versión del contenedor. Agregar el nuevo índice compuesto con nombre explícito es seguro e idempotente en cada boot.

---

### Sobre Preferencias y Silenciamiento (`06.3`)

**P7: En `notifications/app/core/pipeline/policy.py`, `RespectMutes` llama a `muted()` que solo filtra `level == NONE`. ¿Dónde se aplica entonces el nivel `mentions` de la HU-65?**  
*R:* `ChannelActivityHandler` es `mutable=False` y `pushable=False`, es decir que los mensajes comunes **nunca** generan push ni documentos en `notices`; únicamente actualizan actividad no leída por canal (regla explícita de HU-64: silenciar no oculta la actividad). Por eso el backend solo necesita suprimir documentos/push cuando el nivel es `none`, mientras que elegir mostrar la actividad ordinaria de un canal como un punto sutil sin sumar al contador rojo ni sonar (`mentions`) se resuelve limpiamente en los selectores del cliente (`getTotalUnreadCount`, `maybePlaySoundForFrame`, `useUnreadDirectory`) sin disparar tráfico extra al backend.

**P8: ¿Cómo garantizan que HU-64 (`/mutes`) y HU-65 (`/preferences`) no se contradigan ni rompan clientes viejos?**  
*R:* Ambos endpoints persisten en el mismo `MongoMuteStore` bajo el enum unificado `NotificationLevel` (`all | mentions | none`): `PUT /mutes/...` escribe `level="none"`, `DELETE /mutes/...` o `DELETE /preferences/...` elimina el override para volver a heredar, y el store normaliza documentos legados sin campo `level` como `NONE`.

**P9: ¿Qué pasa con las ráfagas de sonidos en vivo si llegan 10 mensajes juntos o una mención al mismo tiempo que actividad común?**  
*R:* `notificationSound.ts` usa un único `AudioContext` compartido con cooldown de `1500 ms` por tipo de señal (`activity`, `mention`, `direct_message`) y retarda `50 ms` la señal de `activity` (`ACTIVITY_DELAY_MS`) para cancelar el tono común si en ese lapso entra una mención o DM de mayor prioridad.

---

### Sobre Push Notifications (`06.4`)

**P10: ¿Por qué desregistran el token push antes de llamar a `/logout`, y qué pasa si el usuario simplemente desinstala la app o cambia de cuenta sin desloguearse?**  
*R:* Porque `DELETE /notifications/push-tokens` requiere autenticación (`X-User-Id` inyectado por el gateway desde el access JWT); si revocáramos la sesión primero, el `DELETE` fallaría con `401`. Por eso `logoutSession` (`authThunks.ts`) ejecuta `unregisterCurrentPushToken` con timeout acotado de `1500 ms` antes de `/logout`. Si no hubo logout: (1) al cambiar de cuenta en el mismo teléfono, `MongoPushStore.upsert_token` borra cualquier documento previo de ese `token` asociado a otro `userId`; (2) si desinstaló la app, Expo devuelve ticket `DeviceNotRegistered` y `PushDeliveryAdapter` limpia ese token automáticamente; (3) si la cuenta es suspendida o eliminada, RabbitMQ (`PushTokenCleanupProjector`) purga todos sus tokens.

**P11: ¿Qué ocurre si tengo Discordia abierto en la PC (pestaña oculta) y salgo con el celular bloqueado en el bolsillo?**  
*R:* Es una limitación real del diseño actual basada en `ConnectionRegistry.count(user_id) == 0`: en Web no cerramos `/ws/notifications` al ocultar la pestaña (porque el navegador usa ese socket abierto para disparar `new Notification(...)` cuando `document.visibilityState === 'hidden'`). En consecuencia, mientras quede una pestaña web abierta en la PC, el servidor ve `count >= 1` y deriva los avisos al WebSocket web en lugar de llamar a Expo Push Service para el teléfono.

**P12: En `Slide 7` dijeron que las llamadas privadas no mandan push, pero pasan por el servicio `notifications`. ¿Por qué no se mezclan con `HU-66`?**  
*R:* Porque cada tipo de handler define su `NotificationProfile`: `HighlightedMentionHandler` y `DirectMessageHandler` tienen `pushable=True` y almacenamiento `PER_USER`, mientras que `PrivateVoiceCallHandler` (`private_voice_calls.py`) está definido como `StorageTier.EPHEMERAL` y `pushable=False`, de modo que `select_adapters` nunca lo envía al `PushDeliveryAdapter`.

---

### Sobre Perfil Público, Presencia y Estado Personalizado (`06.5`)

**P13: ¿Por qué la validación de co-membresía de perfil público está en el `gateway` y no en `profile` ni en el WebSocket `/ws/presence`?**  
*R:* Para preservar la arquitectura *Database-per-Service* sin acoplar `profile` a `server` ni a `text-channel`: el `gateway` ya conoce a ambos servicios y aplica la composición de políticas en `check_profile_access` (`POST /users/co-members` en `server`, y fallback solo para restantes a `GET /conversations?limit=200` en `text-channel` por la excepción de DMs). En `WS /ws/presence`, no cruzar co-membresía en cada `subscribe` fue un trade-off explícito (ADR-008): en su lugar solo devolvemos conectados (`list_connected_activity`), limitamos a `200` IDs con `TokenBucket` (`3` ráfaga + `1/s` por usuario retenido `60 s`) y nunca exponemos `custom_status` ni cuentas desconectadas.

**P14: Si alguien cambia a modo `INVISIBLE` y además escribe un estado personalizado, ¿se filtra de alguna forma que está conectado?**  
*R:* No. En presencia (`effective_activity_type`), `INVISIBLE` y desconectado se proyectan exactamente igual como `OFFLINE` en cada frame `presence_changed` y en `REST /public`. Y `custom_status` (HU-38) es intencionalmente independiente de la conexión y de `INVISIBLE`: permanece visible mientras exista fila en `custom_statuses`, incluso estando desconectado, así que ver un estado personalizado no revela si la persona está conectada ni en modo invisible.

**P15: ¿Por qué el estado personalizado usa `PUT`/`DELETE /profiles/{id}/custom-status` propio en vez de `PATCH /profiles/{id}` con `If-Match`?**  
*R:* Por dos razones documentadas en ADR-012: primero, evita colisiones `412 Precondition Failed` entre actualizaciones frecuentes del estado efímero y ediciones de nombre/avatar o sincronizaciones asíncronas de `UsernameSet`; segundo, permite contar la longitud uniformemente en Unicode code points (`1..64` en frontend con `Array.from`, Python `len` y Postgres `VARCHAR(64)`), hacer upsert atómico (`last write wins`) y emitir `custom_status_changed` solo cuando hubo un cambio real sin reescribir la fila del perfil.

---

### Transversales (las incómodas)

**P16: ¿Qué pasa hoy si `notifications` o `profile` escalan a 2 réplicas detrás del gateway?**  
*R:* Ambos servicios persisten correctamente su estado en base de datos (`MongoDB` para `notifications` y `PostgreSQL RDS` para `profile`), pero sus registries WebSocket viven en memoria del proceso:
- En **`notifications`** (`InMemoryConnectionRegistry`), una réplica que reciba el evento RabbitMQ no vería las conexiones abiertas en la otra réplica: perdería entregas WS en vivo y podría pensar `count == 0`, disparando push duplicado.
- En **`profile`** (`PresenceHub` y `TokenBucket`), el fan-out de `presence_changed`/`custom_status_changed` no cruzaría entre réplicas y el techo de `subscribe` se multiplicaría por N réplicas.
En producción hoy ambos corren con 1 réplica (`infra/compose.prod.yaml`), y la evolución documentada —igual que ya hicimos en `text-channel` con Redis Pub/Sub— es externalizar el fan-out y el rate limit del socket a Redis.

**P17: Si un usuario recibe una notificación en un canal y luego pierde el permiso `VIEW_CHANNELS` (o lo expulsan), ¿puede seguir viendo los textos en el Historial (`GET /inbox`)?**  
*R:* Si lo expulsan o deja el servidor, `notifications` actualiza su copia de membresías por `server_events`; además en `web-client`, `isNoticeTargetAvailable` verifica que el servidor y el canal sigan visibles y bloquea la navegación si ya no tiene acceso. Sin embargo, los documentos ya persistidos previamente en `notices` (con su snippet de hasta 100 chars) permanecen en MongoDB del destinatario mientras no se borren ni filtren por permiso histórico en `GET /inbox`.

---

## 3. Chuleta de Números, Límites y Contratos

| Dato | Valor verificado en código |
|---|---|
| `GET /notifications/inbox` | `limit` default `50`, máx `100`; `offset >= 0`; `days` `[1..90]`; `kind` ∈ `{highlighted_mention, direct_message}` |
| Pestaña Historial (`web-client`) | `HISTORY_PAGE_SIZE = 20`, `HISTORY_DAYS = 7` |
| Corte lectura canal (`mark_read.py`) | Cliente envía `max(lastActivityAt, recorded, now)`; Backend clampa `min(up_to, now)`; Mongo `$lte` |
| Umbral degradación pipeline | `large_audience_threshold = 1000` · agrupación `channel_activity = 5 s` · timeout entrega = `2.0 s` |
| Retención eventos procesados (`notifications`) | `7` días (índice TTL en `processed_events.expiresAt`) |
| Niveles de preferencia (`HU-64/65`) | `all` \| `mentions` \| `none` · precedencia `canal ?? servidor ?? all` |
| Audio cues (`notificationSound.ts`) | Cooldown `1500 ms` por cue; delay de `50 ms` para `activity` |
| Push (`HU-66`) | Batch Expo máx `100`; cleanup timeout en logout `1500 ms`; solo cuando `ConnectionRegistry.count == 0` |
| Presencia (`HU-37`) | Sweep cada `10 s`; `AWAY` tras `300 s`; heartbeat cliente `60 s`; debounce subscribe `1000 ms` |
| Rate limit `WS /ws/presence` | `3` ráfaga + `1/s` por usuario (TTL `60 s`); máx `200` IDs por `subscribe`; máx `8` sockets (`4429`) |
| Perfil público y batch (`gateway`) | Individual `2/second;30/minute`; Batch `5/second;30/minute`, máx `50` IDs; lookup DMs `limit = 200` |
| Estado personalizado (`HU-38`) | `1..64` code points Unicode, una línea; fuera de `If-Match`; omitido en `presence_snapshot` |
| Progreso CP3 (`Slide 10`) | `38` HUs nuevas (`151` pts: `9` oblig `24` pts + `29` opt `127` pts) · Acumulado `247/333` pts (`104/104` oblig + `143/229` opt) |
| Mínimo de equipo (`estado-historias`) | 4 integ `152` · 5 integ `184` · 6 integ `216` pts (están en `247`, **+31 pts** sobre mínimo) |
| Puertos internos clave | `22000` gateway · `22002` server · `22004` profile · `22005` text-channel · `22008` notifications |

---

## 4. Lo que NO conviene afirmar

- **No afirmar** que `notifications` o `server` filtran `VIEW_CHANNELS` dentro de `GET /notifications/unread`: el filtrado fino por `VIEW_CHANNELS` de la bandeja ocurre en **`web-client`** (`useUnreadDirectory` contra `GET /servers/{id}`), aunque para la UI de la bandeja el efecto práctico sea ocultar canales sin acceso.
- **No afirmar** que el nivel `mentions` detiene notificaciones push de mensajes comunes de canal porque sí: los mensajes comunes (`channel_activity`) ya no son pushables; `mentions` actúa en UI (punto pasivo en barra lateral, sin sonar ni sumar al badge rojo).
- **No afirmar** que `notifications` o `profile` están listos hoy para correr con múltiples réplicas sin cambios: ambos usan registros WS en memoria (`InMemoryConnectionRegistry` y `PresenceHub`) y hoy despliegan como **1 réplica** en `compose.prod.yaml`.
- **No afirmar** que `WS /ws/presence` valida co-membresía en `subscribe`: lo valida el **REST** en `gateway` (`/public` y `/public/batch`); el socket mitiga con `list_connected_activity` (oráculo solo de conexión, no existencia), rate limit por usuario y omisión de `custom_status` en snapshots.
- **No afirmar** que las llamadas privadas (`HU-50`) disparan push notifications con la app cerrada: la diapo anterior (`05.4`) ya aclaró que son efímeras sin push (`pushable=False` en `notifications`).
- **No afirmar** que abrir Web en una PC mientras salís con el celular igual te manda Expo push al móvil: mientras el WS de la pestaña web siga abierto, `count >= 1` suprime el push Expo.
