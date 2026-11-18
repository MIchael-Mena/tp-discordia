# Guion — Checkpoint 3 · Michael

Diapositivas a cargo: **Sección 06 (`slide 8 from pdf`: `06`, `06.1`, `06.2`, `06.3`, `06.4`, `06.5`) + `Progreso` (`slide 10`) + `Cierre` (`slide 11`)**.
Duración estimada: **~7–9 minutos** (recortable a **~4,5–5 minutos** salteando los párrafos marcados como `[Detalle técnico]` y comprimiendo `06` a una frase).

| Diapo | Tema | Qué muestra la slide | Respaldo técnico principal |
|---|---|---|---|
| `06` (`slide_1_resumen`) | Notificaciones y presencia | Grilla 2×2 con las 9 HUs (HU-27/28, 67, 65/64, 66, 36/37/38) | `notifications`, `profile`, `gateway`, `web-client` |
| `06.1` (`slide_2_hu27_28`) | Ver y marcar notificaciones | Mockup de campana con badge + bandeja agrupada por servidor | `unread_state.py`, `mark_read.py`, `useUnreadDirectory.ts`, `UnreadProvider.tsx` |
| `06.2` (`slide_3_hu67`) | Centro de notificaciones con historial | Flujo de 3 pasos: `notices` → `read: true` → `GET /notifications/inbox` | `inbox_controller.py`, `notices.py`, `indexes.py`, `useInboxHistory.ts` |
| `06.3` (`slide_4_hu65_hu64`) | Preferencias y silenciamiento | Flujo `canal ?? servidor ?? all` + tarjetas `all / mentions / none` | `preferences.py`, `MongoMuteStore`, `policy.py`, `unreadState.ts` |
| `06.4` (`slide_5_hu66`) | Notificaciones push en mobile | Secuencia registro token → filtro → push Expo | `push.py` (delivery & store), `push_controller.py`, `pushService.ts` |
| `06.5` (`slide_6_hu36_hu37_38`) | Perfil público, presencia y estado | Flujo `/public` → `WS /ws/presence` → estados + `custom-status` | `gateway/app/profiles.py`, `presence_controller.py`, `PresenceHub`, ADRs 007/008/010/012 |
| `Progreso` (`slide 10`) | Resumen del avance de HUs | KPIs `38` / `151` / `32/32` / `247`, barras y tabla por sección | `estado-historias.md` |
| `Cierre` (`slide 11`) | Cierre de entrega | Balance final de Checkpoint 3 | `estado-historias.md` |

---

## Guion

### Enganche desde la diapo anterior (`05.4 · Voz y llamadas en mobile`) y Diapo `06` — Notificaciones y presencia (Resumen)

Ya vimos voz y video en mobile —donde justamente quedó claro que las llamadas privadas hoy se recuperan con la app abierta y **no** disparan push—. Ahora cierro la parte funcional con la **sección 06: Notificaciones y presencia**.

En esta sección cerramos la experiencia diaria del usuario final sobre dos ejes:
1. **Notificaciones** (HU-27, 28, 67, 65, 64 y 66): que el usuario no pierda actividad importante, pueda consultar qué recibió incluso después de leerlo, decida canal por canal qué lo interrumpe y reciba avisos en el celular cuando no está mirando la app.
2. **Identidad y presencia** (HU-36, 37 y 38): ver la ficha pública de otra persona, su disponibilidad en tiempo real y qué está haciendo con un estado corto personalizado, cuidando en todo momento qué información se expone y a quién.

Vamos uno por uno, arrancando por la bandeja.

---

### Diapo `06.1` — Ver y marcar notificaciones (HU-27, HU-28)

Lo que ven a la derecha es literalmente la entrada principal del usuario: la **campana fija** arriba del riel de servidores con el contador rojo de canales con actividad o menciones pendientes. Si no hay pendientes, el badge no se muestra.

Al abrirla se despliega la bandeja agrupada por servidor. Cada fila es un canal (o conversación directa en la pestaña de menciones/DMs), y el usuario puede hacer dos cosas: tocar la fila para saltar directo al canal y marcarlo leído, o tocar el `✓` para limpiarlo sin siquiera entrar. Arriba también tiene **"Marcar todo como leído"** para poner la bandeja en cero de una sola vez.

Tres decisiones técnicas sostienen esta bandeja sin sorpresas:

- **El usuario nunca se auto-notifica:** un mensaje propio actualiza el marcador de lectura del autor al instante (`AuthorReadProjector`), así que jamás aparece como no leído para quien lo escribió.
- **Tolerancia a desfase horario (*clock skew*):** el navegador o el teléfono pueden tener el reloj atrasado o adelantado respecto del servidor. Al marcar leído un canal, el cliente manda `max(lastActivityAt, now)` para no quedarse corto por un reloj atrasado, y el backend lo recorta con `min(upTo, now)` del reloj propio para impedir que un cliente con reloj adelantado marque como leídos mensajes futuros.
- **Visibilidad real de canales (`VIEW_CHANNELS`):** la lista de canales dentro de la bandeja se cruza contra los canales visibles del servidor, así un canal privado al que el miembro ya no tiene acceso nunca se muestra ahí —y si cambian permisos, la caché del cliente se invalida con el evento en vivo.

`[Detalle técnico — saltear si falta tiempo]` Un matiz honesto de esta separación: `notifications` es dueño de marcadores y eventos, no de permisos de roles; por eso el filtro fino por `VIEW_CHANNELS` de la bandeja se resuelve en el cliente contrastando contra `GET /servers/{id}` cuando se arma el directorio, manteniendo desacoplado al microservicio de las reglas bitmask de Quarkus.

> Con los canales al día, el paso siguiente es qué pasa con las menciones y mensajes directos una vez que ya los leíste. Eso lo resuelve el centro con historial.

---

### Diapo `06.2` — Centro de notificaciones con historial (HU-67)

Antes de esta mejora, confirmar una mención la hacía desaparecer de la lista de pendientes. En **HU-67** separamos **pendiente** de **eliminado**, y es exactamente el ciclo de tres pasos del diagrama:

1. **Persistencia de avisos:** mientras la actividad común por canal se calcula al vuelo leyendo marcas de tiempo (sin guardar un documento por cada miembro de un servidor grande), las **menciones destacadas** y los **mensajes directos** sí generan un documento por destinatario en la colección `notices`. Además se empujan en vivo por WebSocket.
2. **Leer no borra:** cuando el usuario toca la notificación o marca el canal como leído, el backend actualiza `read: true` sobre esos documentos, pero **conserva el registro**.
3. **Dos vistas sobre la misma API (`GET /notifications/inbox`):** la pestaña activa consulta `unreadOnly=true` para mostrar solo lo pendiente; la pestaña **Historial** consulta sin ese filtro con ventana de 7 días y paginación incremental (de a 20 ítems en la UI, con tope de hasta 100 por request en API), diferenciando visualmente lo leído de lo nuevo y permitiendo navegar o reportar al autor desde la misma tarjeta.

Fíjense en la regla de corte abajo a la izquierda: al marcar un canal como leído, el `UPDATE` en MongoDB filtra por `createdAt <= upTo`. Si justo en el mismo milisegundo entra una mención nueva mientras el usuario tocaba el check, **no** se la traga el marcado anterior. Y para que la paginación no saltee ni duplique avisos ante timestamps idénticos, las consultas ordenan de forma determinista por `(createdAt DESC, _id DESC)` sobre un índice compuesto dedicado.

> Ya podemos ver y consultar el historial; ahora falta darle al usuario control sobre cuánto ruido quiere recibir.

---

### Diapo `06.3` — Preferencias (HU-65) y silenciamiento (HU-64)

Acá unificamos dos historias —silenciar un canal o servidor (HU-64) y elegir granularidad de avisos (HU-65)— en un único modelo de tres niveles: **Todos los mensajes (`all`)**, **Solo menciones (`mentions`)** y **Ninguno (`none`)**. Silenciar de HU-64 equivale simplemente a fijar el nivel en `none`, y reactivarlo borra el override (`DELETE` idempotente, `204`) para volver a heredar.

El diagrama de la derecha resume la precedencia cuando llega un mensaje: **`canal ?? servidor ?? all`**. Primero se busca si el usuario configuró algo explícito para ese canal; si no existe, hereda lo definido para el servidor; y si tampoco hay nada ahí, queda el default `all`. En la interfaz, si un canal tiene regla propia, el usuario ve la píldora **"Usar configuración del servidor"** para limpiar ese override y volver a heredar.

Qué hace cada nivel en la práctica:
- **`all`:** todo funciona normal: suma al badge, aparece en la bandeja activa y suena en vivo.
- **`mentions`:** pensado para canales ruidosos. Los mensajes comunes muestran solo un punto discreto sin sumar al contador rojo de la campana ni sonar; únicamente las menciones directas, de rol o `@everyone` generan aviso destacado.
- **`none`:** silenciado. No dispara avisos destacados, no suena, no suma al contador ni dispara push; sin embargo —como marca la regla al pie— la actividad nueva **sigue registrándose como no leída** y en la bandeja aparece agrupada aparte en una sección colapsable (*"Silenciados con actividad"* / *"Silenciadas"*), así nunca perdés un mensaje si decidís entrar a mirar.

Cada cambio se persiste y se difunde por WebSocket (`mute_updated` y `preference_updated`) a todas las pestañas o dispositivos abiertos de ese usuario, manteniendo el estado sincronizado en tiempo real.

> Todo esto gobierna lo que pasa con la aplicación abierta. Ahora veamos qué ocurre cuando el usuario guarda el teléfono o cambia de pestaña.

---

### Diapo `06.4` — Notificaciones push en mobile (HU-66)

El diagrama de secuencia muestra el flujo completo de principio a fin:

1. **Ciclo de vida del token:** al iniciar sesión en mobile, la app pide permiso, obtiene el token con `expo-notifications` y lo registra en `POST /notifications/push-tokens`. Cuando el usuario cierra sesión, el cliente **desregistra el token primero** (con un timeout corto acotado) antes de revocar el JWT, mientras la sesión todavía es válida. Y si otra persona inicia sesión en el mismo teléfono sin haber cerrado antes, el backend borra cualquier vínculo previo de ese token con otro `userId` para evitar fugas entre cuentas.
2. **Solo en segundo plano, sin duplicados:** cuando llega una `@mención` o un `DM`, el `PushDeliveryAdapter` evalúa tres condiciones: que el canal/DM **no** esté silenciado (`none`), que el interruptor global **`pushEnabled`** esté activo, y que el usuario tenga **cero WebSockets abiertos** (`ConnectionRegistry.count == 0`). En mobile, apenas la app pasa a `background` o `inactive`, `UnreadProvider` cierra limpiamente `/ws/notifications` (sin timers de reconexión en background) justamente para que el servidor lo vea sin conexiones abiertas e inmediatamente derive el aviso a Expo Push Service.
3. **Privacidad en el texto y limpieza automática:** las menciones crudas como `<@id>` o `<@&rolId>` se sanean en el snippet a `@usuario` / `@rol` para no filtrar IDs internos en la pantalla bloqueada. Si Expo responde `DeviceNotRegistered`, el backend limpia automáticamente ese token vencido; y si una cuenta se suspende o elimina por RabbitMQ, se purgan todos sus tokens.

Dos notas importantes de alcance real: en **web** también hay soporte de avisos vía Web Notifications API, pero **únicamente cuando la pestaña está oculta** (`visibilityState === 'hidden'`); y el interruptor global **"Notificaciones push"** con botón Guardar apaga el envío externo sin alterar ni los badges ni el historial dentro de la app.

> Cerramos notificaciones. En la última diapo del bloque pasamos a la otra mitad: qué ve el usuario de las demás personas.

---

### Diapo `06.5` — Perfil público (HU-36), estado de actividad (HU-37) y estado personalizado (HU-38)

Esta diapositiva reúne las tres historias de perfil y tiempo real, siguiendo el flujo de arriba hacia abajo en el diagrama:

1. **Perfil público mínimo (HU-36):** `GET /profiles/{id}/public` devuelve únicamente la proyección pública (nombre, biografía, avatar, estado de presencia y estado personalizado), nunca metadatos internos de cuenta. Lo crítico es el control de acceso en el **Gateway**: antes de consultar `profile`, exige que quien consulta comparta al menos un servidor con el objetivo —o tenga una conversación directa previa, para no romper los nombres en la bandeja de DMs—. Si no comparten nada, la cuenta no existe o está suspendida, **siempre responde `404`**, cerrando la enumeración por IDs secuenciales. Además sumamos `POST /profiles/public/batch` (hasta 50 IDs) para hidratar chats y listas de miembros sin ráfagas de requests individuales.
2. **Presencia en tiempo real por suscripción (HU-37):** el cliente abre `WS /ws/presence`, pero al conectar el snapshot arranca vacío: **no** hacemos broadcast global de toda la plataforma. Cada componente declara con `subscribe(user_ids)` los IDs que tiene en pantalla (miembros visibles o un perfil abierto), acotado a 200 IDs y protegido por un token bucket por usuario (3 de ráfaga y 1 por segundo, retenido 60 segundos entre reconexiones) para frenar escaneos masivos.
   - Los estados visibles son cuatro: `ONLINE` al conectar, `AWAY` automático tras inactividad sin heartbeats de interacción (barrido cada 10 s con ventana de 300 s), `DO_NOT_DISTURB` manual, y `OFFLINE`. Si el usuario elige **`INVISIBLE`**, el modo manual persiste entre reconexiones para él, pero hacia afuera **siempre se proyecta como `OFFLINE`**: nunca se filtra por el socket ni por REST.
   - Y dejamos explicitado el límite honesto de diseño: la suscripción WebSocket en `profile` no cruza co-membresía con `server`, pero consulta solo conectados, por lo que **es un oráculo de conexión, no de existencia** (un inexistente y un desconectado/invisible son indistinguibles).
3. **Estado personalizado (HU-38):** una frase corta de hasta **64 caracteres** (contados por code points Unicode para soportar emojis, sin saltos de línea) configurable inline desde el menú de usuario o el perfil. Persiste en su propia tabla `custom_statuses` vía `PUT` y `DELETE` idempotente, **fuera** del bloqueo optimista (`If-Match`) de `profiles` para no colisionar con ediciones de perfil. Se propaga en vivo mediante `custom_status_changed` a los observadores suscriptos, pero el `presence_snapshot` inicial lo omite a propósito para que la lectura inicial siempre entre por el REST filtrado por co-membresía. Y es totalmente independiente del modo `INVISIBLE`.

> Con notificaciones, presencia y perfil queda completo todo el bloque funcional del producto. Paso ahora al resumen general de avance para el Checkpoint 3.

---

### Diapo `Progreso` (`slide 10`) — Resumen del avance de historias de usuario

Esta lámina resume dónde queda parado todo el TP al cierre del Checkpoint 3 frente a lo que teníamos en el Checkpoint 2:

- En la entrega anterior ya contábamos con una base de **23 historias obligatorias (80 pts)** y **4 optativas (16 pts)** —96 pts acumulados—.
- En este **Checkpoint 3** sumamos **38 historias nuevas por 151 puntos**: completamos las **9 obligatorias que restaban (24 pts)** —transferencia de servidor, categorías, permisos de rol y rol por defecto, ban/unban, notificaciones base y listado de servidores— y agregamos **29 optativas (127 pts)**.
- Con eso alcanzamos el **100% de las historias obligatorias (32/32 · 104 pts)** y **33 de las 49 optativas (143 de 229 pts)**, llegando a **247 puntos totales de 333** (65 de 81 historias). Para un equipo de 6 integrantes, el mínimo de optativas exigido era 112 pts (216 totales), así que quedamos **31 puntos por encima del umbral**.

En la tabla de la derecha se ve el reparto de los 151 puntos nuevos de este checkpoint por las seis secciones que fuimos mostrando: **Moderación y operación** lideró en volumen (11 historias, 41 pts), seguida por **Mensajería y colaboración** (6 hist., 29 pts) y **Notificaciones y presencia** (9 hist., 29 pts, con las 2 obligatorias de bandeja y 7 optativas), más **Roles y permisos** (20 pts), **Voz y video** (21 pts) y **Administración y estructura** (11 pts).

---

### Diapo `Cierre` (`slide 11`) — Cierre

Con estas 38 historias implementadas de punta a punta entre frontend web/mobile, backoffice, API Gateway y los microservicios, llegamos a **247 puntos acumulados** y el contenido requerido para el TP queda concluido. Desde ya, muchas gracias; quedamos atentos a sus preguntas o para pasar directo a la demo.

---

## Guía rápida si hay que acortar a ~4,5–5 minutos

Si el reloj apura, seguí exactamente esta versión compacta:
1. **`06` Resumen (~15 s):** solo nombrá los dos pilares (Notificaciones controlables + Presencia/Perfil en vivo sin exponer datos privados).
2. **`06.1` Bandeja (~45 s):** mostrá campana + agrupación + `✓` / "Marcar todo" + regla `VIEW_CHANNELS` + reloj (`max` cliente / `min` backend).
3. **`06.2` Historial (~40 s):** leer cambia `read: true` sin borrar; pestaña Historial a 7 días paginada; regla de corte `createdAt <= upTo`.
4. **`06.3` Preferencias/Mutes (~45 s):** fórmula `canal ?? servidor ?? all`; diferencia entre `mentions` (punto pasivo para tráfico común, alerta solo en mención) y `none` (silenciado aparte pero mantiene no leído).
5. **`06.4` Push (~45 s):** token Expo al loguear y desregistro *antes* del logout; mobile cierra WS en `background` → `count == 0` dispara push con texto saneado `<@id>` → `@usuario`; toggle global no toca badges/historial.
6. **`06.5` Perfil/Presencia/Estado (~60 s):** co-membresía + excepción DM en Gateway (si no → `404`); `WS /ws/presence` por suscripción (3 ráfaga + 1/s, 200 IDs, `INVISIBLE` = `OFFLINE`, oráculo de conexión no existencia); `custom_status` 64 chars fuera de `If-Match` y sin entrar en `presence_snapshot`.
7. **`Progreso` + `Cierre` (~40 s):** `38` HUs nuevas (`151 pts`), `32/32` obligatorias (`104 pts`), `143` optativas (`247 pts` totales sobre mínimo de `216`), tabla por secciones de un vistazo y cierre.
