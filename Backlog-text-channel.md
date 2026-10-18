# Backlog — `text-channel` (Épica Mensajería)

Historias de usuario de la épica **Mensajería** de [discordia-tp.md](infra/docs/discordia-tp.md) que corresponden al microservicio [`text-channel`](text-channel/). Se conservan la numeración y el puntaje asignados por la cátedra.

- **Historias:** 10 (2 obligatorias, 8 optativas)
- **Puntaje:** 21 pts obligatorios + 35 pts optativos = **56 pts**
- **Fuente:** `infra/docs/discordia-tp.md` — sección *Épica: Mensajería*, y tablas *Historias obligatorias* / *Historias optativas*

> Las optativas de usuario final deben implementarse tanto en la app mobile como en el cliente web, salvo excepción acordada con el corrector.

## Resumen

| Tipo | Historias | Puntos |
| --- | ---: | ---: |
| Obligatorias | 2 | 21 |
| Optativas | 8 | 35 |
| **Total** | **10** | **56** |

## Tabla de historias

| # | Historia | Tipo | Puntos | Dependencias / motivo | Estado en `text-channel` |
| --: | --- | --- | ---: | --- | --- |
| 15 | Enviar mensaje en un canal | Obligatoria | 8 | Motivo de obligatoriedad: comunicación central en tiempo real y multiinstancia. | Implementado |
| 16 | Historial y reconexión | Obligatoria | 13 | Motivo de obligatoriedad: persistencia, paginación y recuperación sin pérdidas. | Parcial |
| 42 | Enviar mensaje directo (DM) | Optativa | 8 | Dependencias: Bloquear y desbloquear usuarios; sesiones e historial de mensajería. | Pendiente |
| 43 | Bloquear y desbloquear usuarios | Optativa | 3 | Dependencias: Usuarios; complementa mensajes directos. | Pendiente |
| 44 | Editar mensaje | Optativa | 3 | Dependencias: Enviar mensaje en un canal o DM. | Pendiente |
| 45 | Eliminar mensaje | Optativa | 3 | Dependencias: Enviar mensaje en un canal o DM. | Pendiente |
| 46 | Menciones | Optativa | 5 | Dependencias: Mensajería, roles y notificaciones. | Pendiente |
| 47 | Adjuntar archivos en mensajes | Optativa | 5 | Dependencias: Mensajería y almacenamiento externo de objetos. | Pendiente |
| 48 | Reacciones con emoji | Optativa | 3 | Dependencias: Enviar mensaje en un canal. | Pendiente |
| 49 | Buscar mensajes | Optativa | 5 | Dependencias: Historial y reconexión; autorización por canal o DM. | Pendiente |

Estados: **Implementado** (la historia queda cubierta por este servicio), **Parcial** (parte de los criterios dependen de otro servicio o del cliente), **Pendiente** (sin implementar).

## Detalle por historia

### #15 — Enviar mensaje en un canal

**Tipo:** Obligatoria · **Puntos:** 8

**Motivo de obligatoriedad: comunicación central en tiempo real y multiinstancia.**

**Estado en `text-channel`:** Implementado en código y desplegable en producción (HU-15; PRs abiertos con CI en verde). El MVP `001-realtime-messaging-mvp` (`text-channel` PR #1) cubre CA1 (envío, persistencia y broadcast en vivo) y CA2 (mensaje vacío). Sobre eso:

- **CA3 (sin permisos):** `text-channel` consulta a `server` el permiso de envío por cada mensaje (`GET /internal/channels/{id}/send-permission`), con caché TTL/LRU de 5 s y **fail-closed**. `server` resuelve `owner || server_members` y expone el alta idempotente `POST /servers/{id}/members/me`; `gateway` relaya el alta y `web-client` muestra el canal en solo lectura + botón "Unirse al servidor". Los rechazos vuelven como `{"type":"error","code":"forbidden"}` sin cerrar el WebSocket.
- **CA4 (muy largo):** el error `too_long` incluye el máximo configurado y el historial expone `max_message_length`; el cliente muestra contador y bloquea el envío por encima del límite.

Documentación: `text-channel/docs/arquitectura/flujo-mensajeria-tiempo-real.md`, `adr-001-consumo-de-autorizacion-de-envio.md`, `adr-002-broadcast-multi-replica.md`, `docs/operacion/despliegue.md`, y el ADR equivalente en `server/docs/arquitectura/`.

**Despliegue y multi-réplica (TSK-031):** `text-channel` ya está en el stack de producción (compose + Mongo + Redis, `TEXT_CHANNEL_TAG`, `INTERNAL_SERVICE_TOKEN`) y difunde cada mensaje por un topic de Redis, así que el chat es correcto con más de una réplica y durante un deploy con solapamiento (`REDIS_URL` vacío mantiene el fan-out en proceso). Pipeline propio: ECR `discordia/text-channel` + deploy por SSM. Quedan como pendientes los prerrequisitos manuales de AWS (repo ECR, rol OIDC, gist) y el runbook de aplicación en la EC2, documentados en `infra/docs/servicios/text-channel.md`.

PRs: `text-channel` #2 y #3, `server` #11, `gateway` #39, `web-client` #130, `infra` #20. Pendientes funcionales: roles/permisos granulares (la política queda como seam), invitaciones con expiración, backups de MongoDB y balanceador para escalar `text-channel`.

**Descripción:** Como **miembro de un canal**, quiero **enviar mensajes de texto** para **comunicarme con el resto de la comunidad en tiempo real**.

**Criterios de aceptación:**

- **CA 1 — Envío exitoso**
  - Dado que un miembro con permisos escribe un mensaje válido en un canal
  - Cuando lo envía
  - Entonces el mensaje se entrega en tiempo real a todos los miembros conectados a ese canal.
- **CA 2 — Mensaje vacío**
  - Dado que un miembro intenta enviar un mensaje sin contenido ni adjuntos (historia optativa)
  - Cuando lo intenta
  - Entonces el sistema no lo envía.
- **CA 3 — Sin permisos**
  - Dado que un miembro no tiene permiso de enviar mensajes en un canal
  - Cuando lo intenta
  - Entonces el sistema no le permite escribir ahí.
- **CA 4 — Mensaje muy largo**
  - Dado que un miembro escribe un mensaje que excede el largo máximo permitido
  - Cuando intenta enviarlo
  - Entonces el sistema indica el límite y no lo envía.

### #16 — Historial y reconexión

**Tipo:** Obligatoria · **Puntos:** 13

**Motivo de obligatoriedad: persistencia, paginación y recuperación sin pérdidas.**

**Estado en `text-channel`:** Parcial. `GET /channels/{channel_id}/messages` implementa paginación y orden (CA 1 y CA 3). La reconexión y el catch-up son responsabilidad del cliente (`gateway/specs/012-*` y `web-client/specs/013-*`): no hay reanudación del WebSocket del lado del servidor (CA 2).

**Descripción:** Como **miembro de un canal**, quiero **ver el historial de mensajes y no perder mensajes si me desconecto brevemente** para **mantener el contexto de la conversación**. Si el grupo implementa mensajes directos, el mismo comportamiento aplica también a esas conversaciones.

**Criterios de aceptación:**

- **CA 1 — Carga de historial**
  - Dado que un usuario abre un canal con mensajes previos
  - Cuando accede
  - Entonces ve los mensajes más recientes con opción de cargar mensajes anteriores mediante paginación.
- **CA 2 — Reconexión sin pérdida de mensajes**
  - Dado que un usuario pierde la conexión en tiempo real por un período breve
  - Cuando se reconecta
  - Entonces recibe los mensajes que se enviaron durante la desconexión.
- **CA 3 — Orden cronológico**
  - Dado que existen múltiples mensajes en un canal
  - Cuando un usuario ve el historial
  - Entonces los mensajes se muestran en orden cronológico.

### #42 — Enviar mensaje directo (DM)

**Tipo:** Optativa · **Puntos:** 8

**Dependencias: Bloquear y desbloquear usuarios; sesiones e historial de mensajería.**

**Estado en `text-channel`:** Pendiente. Requiere un modelo de conversación 1:1, distinto del actual `channel_id`: hoy `text-channel` solo conoce canales.

**Descripción:** Como **usuario**, quiero **enviar mensajes directos a otro usuario** para **tener conversaciones privadas fuera de los servidores**.

**Criterios de aceptación:**

- **CA 1 — Envío exitoso**
  - Dado que un usuario inicia o continúa una conversación directa con otro usuario
  - Cuando envía un mensaje
  - Entonces se entrega en tiempo real al destinatario si está conectado, o queda pendiente de lectura si no lo está.
- **CA 2 — Primer mensaje crea la conversación**
  - Dado que dos usuarios nunca tuvieron una conversación directa
  - Cuando uno le envía un mensaje al otro por primera vez
  - Entonces se crea la conversación y queda disponible para ambos.
- **CA 3 — Bloqueo de usuario**
  - Dado que un usuario bloqueó a otro
  - Cuando el usuario bloqueado intenta enviarle un mensaje directo
  - Entonces el sistema no lo entrega.

### #43 — Bloquear y desbloquear usuarios

**Tipo:** Optativa · **Puntos:** 3

**Dependencias: Usuarios; complementa mensajes directos.**

**Estado en `text-channel`:** Pendiente. Debe resolverse antes o junto con los DMs, porque la entrega depende de la relación de bloqueo.

**Descripción:** Como **usuario**, quiero **bloquear o desbloquear a otro usuario** para **controlar quién puede contactarme mediante mensajes directos y llamadas privadas**.

**Criterios de aceptación:**

- **CA 1 — Bloqueo exitoso**
  - Dado que un usuario selecciona a otro usuario que no está bloqueado
  - Cuando confirma el bloqueo
  - Entonces el usuario bloqueado no puede enviarle nuevos mensajes directos ni iniciar llamadas privadas.
- **CA 2 — Conversación previa conservada**
  - Dado que dos usuarios tenían una conversación directa antes del bloqueo
  - Cuando uno bloquea al otro
  - Entonces el historial previo se conserva para ambos, pero no se permiten nuevos contactos desde el usuario bloqueado.
- **CA 3 — Desbloqueo exitoso**
  - Dado que un usuario había bloqueado a otro
  - Cuando confirma el desbloqueo
  - Entonces ese usuario vuelve a poder enviarle mensajes directos e iniciar llamadas privadas.

### #44 — Editar mensaje

**Tipo:** Optativa · **Puntos:** 3

**Dependencias: Enviar mensaje en un canal o DM.**

**Estado en `text-channel`:** Pendiente. El contrato actual ya expone `edited_at` en el mensaje, pero no hay endpoint ni frame de edición.

**Descripción:** Como **autor de un mensaje**, quiero **editarlo** para **corregir errores o actualizar su contenido**.

**Criterios de aceptación:**

- **CA 1 — Edición exitosa**
  - Dado que un usuario es autor de un mensaje
  - Cuando lo edita y guarda un nuevo contenido válido
  - Entonces el mensaje se actualiza para todos los miembros y queda marcado como editado.
- **CA 2 — Solo el autor puede editar**
  - Dado que un usuario intenta editar un mensaje que no le pertenece
  - Cuando lo intenta
  - Entonces el sistema no se lo permite.
- **CA 3 — Edición propagada en tiempo real**
  - Dado que un mensaje fue editado
  - Cuando otros miembros tienen el canal abierto
  - Entonces ven el contenido actualizado sin necesidad de recargar.

### #45 — Eliminar mensaje

**Tipo:** Optativa · **Puntos:** 3

**Dependencias: Enviar mensaje en un canal o DM.**

**Estado en `text-channel`:** Pendiente. El contrato actual ya expone `deleted_at` en el mensaje, pero no hay endpoint ni frame de borrado.

**Descripción:** Como **autor de un mensaje o miembro con permisos de moderación**, quiero **eliminar un mensaje** para **retirarlo de la conversación**.

**Criterios de aceptación:**

- **CA 1 — Eliminación por el autor**
  - Dado que un usuario es autor de un mensaje
  - Cuando lo elimina
  - Entonces el mensaje deja de mostrarse para todos los miembros.
- **CA 2 — Eliminación por moderación**
  - Dado que un usuario con permisos de gestión de mensajes elimina un mensaje ajeno
  - Cuando lo hace
  - Entonces el mensaje deja de mostrarse para todos los miembros.
- **CA 3 — Sin permisos**
  - Dado que un usuario sin autoría ni permisos de moderación intenta eliminar un mensaje ajeno
  - Cuando lo intenta
  - Entonces el sistema no se lo permite.

### #46 — Menciones

**Tipo:** Optativa · **Puntos:** 5

**Dependencias: Mensajería, roles y notificaciones.**

**Estado en `text-channel`:** Pendiente. Requiere resolver usuarios/roles (dominio de `server`) y disparar notificaciones; parte del trabajo queda fuera de `text-channel`.

**Descripción:** Como **miembro de un servidor**, quiero **mencionar a un usuario, un rol o a todo el servidor en un mensaje** para **llamar su atención específicamente**.

**Criterios de aceptación:**

- **CA 1 — Mención a un usuario**
  - Dado que un miembro menciona a otro usuario en un mensaje
  - Cuando lo envía
  - Entonces el usuario mencionado recibe una notificación destacada.
- **CA 2 — Mención a un rol**
  - Dado que un miembro con permisos menciona a un rol
  - Cuando lo envía
  - Entonces todos los miembros con ese rol reciben una notificación destacada.
- **CA 3 — Mención a todo el servidor**
  - Dado que un miembro con el permiso correspondiente menciona a todo el servidor (@everyone)
  - Cuando lo envía
  - Entonces todos los miembros del canal reciben una notificación destacada.
- **CA 4 — Mención sin permisos**
  - Dado que un miembro sin el permiso de mencionar a todo el servidor intenta usar @everyone
  - Cuando lo intenta
  - Entonces el sistema no se lo permite o lo trata como texto plano.

### #47 — Adjuntar archivos en mensajes

**Tipo:** Optativa · **Puntos:** 5

**Dependencias: Mensajería y almacenamiento externo de objetos.**

**Estado en `text-channel`:** Pendiente. Requiere almacenamiento de objetos y URLs; `text-channel` solo persistiría los metadatos del adjunto.

**Descripción:** Como **miembro de un canal o conversación**, quiero **adjuntar imágenes o archivos a mis mensajes** para **compartir contenido más allá del texto**.

**Criterios de aceptación:**

- **CA 1 — Adjunto exitoso**
  - Dado que un usuario adjunta un archivo de un formato y tamaño permitido
  - Cuando envía el mensaje
  - Entonces el archivo se sube, se persiste su URL y se muestra junto al mensaje.
- **CA 2 — Formato no soportado**
  - Dado que un usuario intenta adjuntar un archivo de un formato no permitido
  - Cuando lo intenta
  - Entonces el sistema lo rechaza con un error descriptivo.
- **CA 3 — Archivo demasiado grande**
  - Dado que un usuario intenta adjuntar un archivo que excede el tamaño máximo permitido
  - Cuando lo intenta
  - Entonces el sistema lo rechaza con un error descriptivo.

### #48 — Reacciones con emoji

**Tipo:** Optativa · **Puntos:** 3

**Dependencias: Enviar mensaje en un canal.**

**Estado en `text-channel`:** Pendiente. Requiere un frame/endpoint de reacciones y broadcast del cambio en tiempo real.

**Descripción:** Como **miembro de un canal**, quiero **reaccionar a un mensaje con un emoji** para **expresar una respuesta rápida sin escribir un mensaje nuevo**.

**Criterios de aceptación:**

- **CA 1 — Reacción exitosa**
  - Dado que un miembro con acceso al canal selecciona un emoji para reaccionar a un mensaje
  - Cuando confirma
  - Entonces la reacción se agrega y se muestra en tiempo real a todos los miembros del canal.
- **CA 2 — Quitar reacción propia**
  - Dado que un miembro ya reaccionó a un mensaje con un emoji
  - Cuando vuelve a seleccionar ese mismo emoji
  - Entonces su reacción se retira.
- **CA 3 — Sin permisos**
  - Dado que un miembro no tiene permiso de agregar reacciones en el canal
  - Cuando lo intenta
  - Entonces el sistema no se lo permite.

### #49 — Buscar mensajes

**Tipo:** Optativa · **Puntos:** 5

**Dependencias: Historial y reconexión; autorización por canal o DM.**

**Estado en `text-channel`:** Pendiente. Requiere índice de texto en MongoDB y acotar resultados a los canales a los que el usuario tiene acceso.

**Descripción:** Como **miembro de un servidor**, quiero **buscar mensajes por texto o autor** para **encontrar información específica sin scrollear todo el historial**.

**Criterios de aceptación:**

- **CA 1 — Búsqueda por texto**
  - Dado que un usuario ingresa un término de búsqueda
  - Cuando ejecuta la búsqueda
  - Entonces el sistema devuelve los mensajes que contienen ese término, dentro de los canales a los que tiene acceso.
- **CA 2 — Filtro por autor**
  - Dado que un usuario filtra la búsqueda por un autor específico
  - Cuando ejecuta la búsqueda
  - Entonces los resultados se limitan a mensajes de ese autor.
- **CA 3 — Sin resultados**
  - Dado que una búsqueda no encuentra mensajes coincidentes
  - Cuando se ejecuta
  - Entonces el sistema indica que no hay resultados.

