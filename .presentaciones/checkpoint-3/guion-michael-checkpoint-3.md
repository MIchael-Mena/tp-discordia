# Guion — Checkpoint 3 · Michael

Diapositivas a cargo: **Sección 06 (`slide 8 from pdf`: `06`, `06.1`, `06.2`, `06.3`, `06.4`, `06.5`) + `Progreso` (`slide 10`) + `Cierre` (`slide 11`)**.
Duración estimada: **~5,5–6 minutos** (recortable a **~3,5–4 minutos** siguiendo la guía rápida del final).

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

### Enganche desde `05.4` y Diapo `06` — Notificaciones y presencia (Resumen)

Venimos de ver cómo funcionan la voz y el video en mobile —donde quedó claro que las llamadas privadas todavía no mandan push—. Con la **sección 06** cerramos la parte funcional del producto: **notificaciones y presencia**.

Todo el bloque gira sobre dos ejes de la experiencia diaria:

1. **Notificaciones:** que el usuario no pierda nada importante, conserve un historial de lo recibido, elija qué nivel de avisos quiere en cada canal o servidor y reciba push en el celular cuando no está en la app.
2. **Identidad y presencia:** ver el perfil público de otra persona, su disponibilidad en tiempo real y un estado corto personalizado, cuidando siempre qué datos se exponen y a quién.

Arrancamos por la bandeja.

---

### Diapo `06.1` — Ver y marcar notificaciones

Lo que se ve a la derecha es la entrada principal del usuario: la **campana fija** arriba del riel de servidores con el contador rojo de canales y menciones pendientes. Si no hay nada sin leer, el badge desaparece.

Al abrirla se despliega la bandeja agrupada por servidor. Cada fila es un canal o un mensaje directo: tocar la fila lleva directo a esa conversación y la marca leída, el `✓` la limpia sin entrar, y **"Marcar todo como leído"** pone la bandeja en cero de una sola vez.

Tres decisiones sostienen esto sin sorpresas:

- **Sin auto-notificaciones.** Un mensaje propio avanza al instante el marcador de lectura de quien lo envió, así que nunca aparece como no leído para el autor.
- **Protección contra desfase de reloj.** El cliente manda el mayor timestamp entre la última actividad y su reloj local para no quedarse corto si está atrasado, y el backend lo recorta contra la hora del servidor para que un reloj adelantado no marque mensajes futuros.
- **Visibilidad real de canales (`VIEW_CHANNELS`).** El servicio de notificaciones no conoce roles ni bitmasks; por eso la bandeja cruza lo pendiente contra los canales visibles que devuelve `server` e invalida su caché en vivo si cambian los permisos, manteniendo desacoplado al microservicio.

> Con los canales al día, el paso siguiente es qué pasa con las menciones y los mensajes directos una vez que el usuario ya los leyó.

---

### Diapo `06.2` — Centro de notificaciones con historial

Antes, confirmar una mención la hacía desaparecer de la lista. Ahora **pendiente** y **eliminado** son cosas distintas, y el diagrama de la derecha muestra ese ciclo en tres pasos:

1. **Solo se persiste lo relevante.** La actividad común por canal se calcula al vuelo comparando marcas de tiempo —sin escribir un documento por cada miembro de un servidor grande—; en cambio, las menciones destacadas y los mensajes directos sí generan un aviso guardado por destinatario y se empujan en vivo por WebSocket.
2. **Leer no borra.** Al entrar al canal o marcarlo como leído, el backend cambia el estado a leído (`read: true`), pero conserva el registro.
3. **Dos vistas sobre el mismo inbox.** La pestaña activa filtra solo lo pendiente; la pestaña **Historial** consulta los últimos siete días paginados de a poco, diferenciando lo nuevo de lo ya leído y dejando saltar al canal o abrir el perfil público del autor desde la misma tarjeta.

**Regla de corte.** El marcado de un canal corta por fecha de creación hasta el timestamp del corte. Si entra una mención en el mismo milisegundo en que el usuario toca el check, no se pierde debajo del marcado anterior.

> Ya podemos ver y consultar lo que llegó; ahora falta darle al usuario control sobre cuánto ruido quiere escuchar.

---

### Diapo `06.3` — Preferencias y silenciamiento

Acá unificamos silenciar un canal o servidor y elegir la granularidad de avisos en un solo modelo de tres niveles: **Todos los mensajes (`all`)**, **Solo menciones (`mentions`)** y **Ninguno (`none`)**. Silenciar equivale directamente a fijar `none`, y reactivar borra la excepción para volver a heredar.

Como resume el diagrama, la precedencia es **`canal ?? servidor ?? all`**. Primero manda la regla del canal; si no tiene, hereda la del servidor, y por defecto queda en `all`. Cuando un canal tiene regla propia, la UI muestra **"Usar configuración del servidor"** para limpiar esa excepción.

En la práctica, cada nivel cambia el comportamiento así:

- **`all`:** todo suma al contador, aparece en bandeja y suena en vivo.
- **`mentions`:** pensado para canales ruidosos. Los mensajes comunes muestran solo un punto discreto sin sumar al badge rojo ni sonar; únicamente las menciones destacan.
- **`none`:** silenciado por completo: sin alertas destacadas, sin sonido, sin sumar al contador y sin push. Sin embargo, la actividad nueva **se sigue registrando como no leída** y aparece agrupada aparte en una sección colapsable de silenciados, para que el usuario nunca pierda contexto si decide entrar a mirar.

Cada cambio se persiste y se sincroniza en tiempo real por WebSocket entre todas las pestañas y dispositivos abiertos del usuario.

> Todo esto gobierna lo que pasa con la aplicación abierta. Veamos ahora qué ocurre cuando el usuario guarda el teléfono o cambia de pestaña.

---

### Diapo `06.4` — Notificaciones push en mobile

El diagrama de secuencia muestra el camino completo de principio a fin:

- **Ciclo de vida del token.** Al iniciar sesión en mobile, la app pide permiso, obtiene el token con Expo y lo registra en el backend. Al cerrar sesión, lo desregistra **antes** de revocar el JWT, mientras la sesión todavía es válida. Si otra persona entra en el mismo teléfono sin haber cerrado la cuenta anterior, el backend borra el vínculo previo; y si Expo informa un dispositivo vencido o una cuenta se suspende, los tokens se purgan solos.
- **Solo en segundo plano y sin duplicados.** Cuando la app móvil pasa a segundo plano, cierra limpiamente su WebSocket de notificaciones. Así el servidor ve al usuario sin conexiones abiertas y, si entra una mención o un mensaje directo —y ni el canal está silenciado ni el interruptor global apagado—, deriva el aviso a Expo.
- **Privacidad y alcance.** Antes de salir hacia Expo, el extracto reemplaza menciones internas crudas por `@usuario` o `@rol` para no filtrar IDs en la pantalla bloqueada. Dos aclaraciones de alcance: en web soportamos notificaciones del navegador únicamente cuando la pestaña está oculta, y el interruptor global **"Notificaciones push"** apaga los envíos externos sin alterar ni los badges ni el historial dentro de la app.

> Cerramos notificaciones. En la última diapo del bloque pasamos a la otra mitad: qué muestra el usuario hacia afuera y qué ve de los demás.

---

### Diapo `06.5` — Perfil público, presencia y estado personalizado

Acá cerramos las tres piezas de identidad y tiempo real, siguiendo el diagrama de arriba hacia abajo:

- **Perfil público mínimo.** `GET /profiles/{id}/public` expone únicamente nombre, descripción, avatar, presencia y estado personalizado, nunca datos internos de cuenta. Lo crítico es el control de acceso en el **Gateway**: antes de consultar a `profile`, exige que ambos usuarios compartan al menos un servidor o tengan un mensaje directo previo. Si no comparten nada, la cuenta no existe o está suspendida, responde siempre **`404`** para frenar la enumeración de IDs. Sumamos además un endpoint en lote (`/public/batch`) para hidratar chats y listas de miembros sin ráfagas de pedidos.
- **Presencia por suscripción.** Al abrir `WS /ws/presence`, la lista arranca vacía: no hay broadcast global de toda la plataforma. Cada vista pide solo los IDs que tiene en pantalla, con un tope por pedido y *rate limiting* por token bucket para frenar escaneos masivos.
- **Estados e `INVISIBLE`.** Hacia afuera se ven cuatro estados: `ONLINE` al conectar, `AWAY` automático tras un tiempo sin interacción, `DO_NOT_DISTURB` manual y `OFFLINE`. Si el usuario elige **`INVISIBLE`**, ese modo persiste entre reconexiones para él, pero hacia el resto siempre se proyecta como `OFFLINE`. Y dejamos explícito el límite de diseño: el WebSocket consulta solo conectados y no cruza co-membresía con `server`, así que un ID inexistente, uno desconectado y uno invisible son indistinguibles —es un **oráculo de conexión, no de existencia**.
- **Estado personalizado.** Una frase corta de hasta 64 caracteres junto al nombre, editable y borrable al instante. Se guarda en su propia tabla fuera del bloqueo optimista del perfil para no colisionar con cambios de nombre o avatar, se difunde en vivo al cambiar y es independiente del modo `INVISIBLE`. Y queda **fuera del snapshot inicial** del WebSocket a propósito, para que la primera lectura entre siempre por REST filtrada por co-membresía.

> Con esto queda completo todo el bloque funcional del producto. Paso ahora al balance de avance del Checkpoint 3.

---

### Diapo `Progreso` (`slide 10`) — Resumen del avance de historias de usuario

Esta diapo resume dónde queda parado todo el TP frente al cierre del Checkpoint 2:

- **La foto macro.** En este **Checkpoint 3** sumamos **38 historias nuevas por 151 puntos**. Con las **9 obligatorias que restaban** —transferencia de servidor, categorías, permisos y rol por defecto, ban y desbaneo, notificaciones base y listado de servidores— cerramos el **100% de las obligatorias: 32 de 32 (104 puntos)**. Y con 29 optativas nuevas alcanzamos **247 puntos totales** de 333, quedando **31 puntos por encima** del mínimo de 216 exigido para un equipo de 6 integrantes.
- **Dónde estuvo el esfuerzo.** Como muestra la tabla de la derecha, **Moderación y operación** lideró el aporte del checkpoint con 41 puntos, seguida por **Mensajería y colaboración** y **Notificaciones y presencia** con 29 puntos cada una, además del trabajo de **Voz y video**, **Roles y permisos** y **Administración y estructura**.

---

### Diapo `Cierre` (`slide 11`) — Cierre

Con estas 38 historias integradas de punta a punta entre la app web y mobile, el backoffice, el API Gateway y los microservicios, cerramos el contenido requerido para el TP con **247 puntos acumulados**. Desde ya, muchas gracias; quedamos atentos a cualquier pregunta o para pasar directo a la demo en vivo.

---

## Guía rápida si hay que acortar a ~3,5–4 minutos

Si el reloj apura, usá estos puntos cortos en cada diapo:

1. **`06` Resumen (~15 s):** venimos de voz en mobile; cerramos el bloque funcional con dos ejes: notificaciones configurables y perfil/presencia en vivo cuidando la privacidad.
2. **`06.1` Bandeja (~35 s):** campana fija con badge, bandeja por servidor con salto directo, `✓` y "Marcar todo"; el autor no se auto-notifica, cruce `max`/`min` de reloj, y filtro `VIEW_CHANNELS` contrastado contra `server`.
3. **`06.2` Historial (~30 s):** solo menciones y DMs se guardan por usuario; leer marca `read: true` sin borrar; pestaña Historial paginada a 7 días; corte por fecha `<= upTo` para no tapar mensajes simultáneos.
4. **`06.3` Preferencias (~35 s):** precedencia `canal ?? servidor ?? all`; `mentions` deja punto discreto sin sumar ni sonar; `none` silencia avisos y push pero mantiene la actividad en una sección colapsable; sincronizado por WS.
5. **`06.4` Push (~35 s):** token Expo al entrar y desregistro *antes* del logout; en segundo plano mobile cierra el WS → 0 sockets abiertos dispara push saneando `<@id>` a `@usuario`; web solo notifica con pestaña oculta y el toggle global no toca badges ni historial.
6. **`06.5` Perfil y presencia (~50 s):** Gateway exige co-membresía o DM previo y si no responde `404` uniforme; `WS /ws/presence` solo por suscripción con rate limit, `INVISIBLE` = `OFFLINE` (oráculo de conexión, no existencia); estado personalizado de 64 chars fuera del bloqueo optimista del perfil y fuera del snapshot inicial.
7. **`Progreso` + `Cierre` (~30 s):** `38` historias nuevas (`151 pts`), `32/32` obligatorias cerradas (`104 pts`), `247 pts` totales (`+31` sobre el mínimo de `216`), tabla liderada por Moderación/Mensajería/Notificaciones y pase a preguntas o demo en vivo.
