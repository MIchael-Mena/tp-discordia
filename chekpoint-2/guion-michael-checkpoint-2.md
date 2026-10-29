# Guion — Checkpoint 2 · Michael

Diapositivas a cargo: **2b, 3, 3b, 5, 6, 7, 8 y 11**. Duración estimada: ~12 minutos
(recortable a ~8 salteando los párrafos de contexto y los trade-offs).

| Diapo | Tema | Diagrama | Documento de respaldo |
|---|---|---|---|
| 2b | Comunicación asíncrona | `03-mensajeria-asincrona.svg` | `infra/docs/adr/adr-003` |
| 3 | Autenticación y seguridad | `04-autenticacion-jwt.svg` | `gateway/docs/flujo-autenticacion-jwt.md` |
| 3b | Recupero de contraseña | `13-flujo-recupero-password.svg` | `auth-service/docs/arquitectura/adr-002` |
| 5 | Persistencia por servicio y S3 | `06-persistencia-s3.svg` | `profile/docs/arquitectura/adr-002` y `adr-006` |
| 6 | Servidores y roles | `07-permisos-efectivos.svg` | `server/docs/arquitectura/adr-002` y `adr-003` |
| 7 | Mensajería en tiempo real | `08-tiempo-real-redis.svg` | `text-channel/docs/arquitectura/adr-002` y `adr-003` |
| 8 | Flujo end-to-end | `09-flujo-envio-mensaje.svg` | `text-channel/docs/arquitectura/adr-001` |
| 11 | Robustez de infraestructura | `11-redes-puertos.svg` | `infra/docs/ci-cd.md` y `adr-008` |

---

## Guion

### Diapo 11 — Robustez de Infraestructura (DevOps)

Cuatro cosas que hacen que esto se pueda operar.

**Perímetro.** Solo Traefik publica puertos, 80 y 443. Ningún servicio interno es alcanzable desde afuera, y por eso podemos confiar en `X-User-Id`: la única forma de que exista es que lo haya inyectado el gateway. Los certificados son de Let's Encrypt y Traefik los renueva solo.

**Migraciones.** El esquema tiene una única fuente de verdad y se aplica **en el pipeline**, entre el `pull` y el `up -d`, bajo `set -e`. Si la migración falla, el job queda rojo y **no** se recrea el contenedor: la versión anterior sigue sirviendo. Nunca hay un deploy a medias. Para cambios destructivos usamos *expand/contract* en dos releases. Hoy es Alembic en `auth-service` y `profile`; `server` aplica Flyway al arrancar y alinearlo al paso del pipeline está pendiente.

**Arranque determinístico.** Healthchecks en Compose con `depends_on: condition: service_healthy`: el gateway espera a `auth` y a `profile`, y `text-channel` espera a Redis. Y los healthchecks usan `/livez`, no `/readyz`, a propósito: un hipo de RDS, Atlas o LiveKit no debe reiniciar un contenedor sano. `/readyz` sirve para saber si el servicio puede atender, no para matarlo.

**Cadena de deploy.** GitHub Actions asume un rol por repositorio con **OIDC**, sin claves fijas, y ese rol solo puede empujar a su ECR y mandar comandos SSM a la instancia. Los tags son inmutables (`<sha>-<run_attempt>`), el deploy se acota a un servicio y el job verifica el estado real del comando: si no es `Success`, falla. Cobertura mínima 70% y `ruff` como gates.

Sobre observabilidad, para que no parezca más de lo que es: hoy tenemos sondas, healthchecks y badges; métricas con Grafana quedaron como exploración, no están desplegadas.

Con esto cierro la parte técnica.

### Diapo 2b — Comunicación Asíncrona con RabbitMQ

Ya vimos cómo se hablan los servicios por HTTP. El problema de ese camino es el **acoplamiento temporal**: si `profile` tarda o está caído, no queremos que el registro de una cuenta falle. Por eso todo lo que puede esperar va por RabbitMQ.

Tenemos dos patrones distintos en el mismo broker:

- **Colas de trabajo** — `create_perfil`, `update_username` y `send_email`. Un mensaje, un consumidor. Son colas **quorum**: los mensajes se persisten en disco y sobreviven a un reinicio del contenedor o del host, y cada una tiene su DLQ al lado.
- **Un exchange fanout** — `account_events`. Acá no se reparte, se difunde: cada réplica de `text-channel` declara **su** cola exclusiva, así todas se enteran de una suspensión y cierran sus propias conexiones.

El consumo **no corre dentro del proceso de la API**: `profile-worker` y `email-worker` son contenedores aparte con la misma imagen, así el tráfico HTTP y la sonda `/livez` no compiten con el procesamiento de eventos.

Dos garantías que nos importan. Si el broker está caído, la operación de negocio ya quedó confirmada: el publish se descarta con un warning y se reintenta la conexión en el próximo request; no rompemos el registro. Y como la entrega es *at-least-once*, los consumidores son idempotentes: `INSERT ... ON CONFLICT DO NOTHING` en el perfil, y el mail usa el `event_id` como `Idempotency-Key` contra Resend.

El costo del desacople es la consistencia eventual: entre el registro y la creación del perfil hay una ventana en la que un `404` es legítimo, y el cliente lo tolera reintentando.

> Con esto cerramos cómo se desacoplan los servicios. Paso a autenticación.


### Diapo 3 — Autenticación y Seguridad Robusta

El cambio grande respecto del MVP 1 es que **el gateway dejó de preguntarle a `auth-service` en cada request**. Ahora hay dos tokens: un **access JWT de 15 minutos**, firmado con HS256, que el gateway **verifica en local** —firma, expiración y lista de revocación—; y un **refresh opaco de 7 días** que vive en la tabla `sessions` y solo `auth-service` toca.

El access lleva el claim `sid`, que es el hash del refresh que lo emitió. Eso es lo que permite revocar de verdad: al hacer logout, o al suspender una cuenta, `auth-service` borra las sesiones y devuelve sus `sid`; el gateway los anota y esos access tokens se rechazan al instante, sin round-trip por request. El límite conocido es que esa lista es **por proceso**: si el gateway reinicia, un token ya revocado se acepta hasta su `exp`, o sea 15 minutos como máximo. Está documentado y se resuelve con un store compartido.

Del lado del cliente, el access vive **solo en memoria**, en Redux. El refresh, en web, viaja en una cookie **HttpOnly + Secure**, que JavaScript no puede leer; en móvil, en `expo-secure-store`. Un XSS no se lleva ninguna de las dos.

Y sumamos el **login federado con Google** (HU-33): verificamos el `id_token` contra nuestro client ID y el claim `email_verified`, y emitimos exactamente los mismos tokens. Una cuenta creada con Google nace **sin contraseña** —no le inventamos una— y el recupero de contraseña es, después, el camino para fijar la primera.

> El recupero es justamente el caso donde todo esto se combina. Lo vemos ahora.

### Diapo 3b — Recupero de Contraseña

El link de recupero **no es una contraseña temporal**: es un token aleatorio de 256 bits, y en la base guardamos **solo su SHA-256**. Si se filtra la base, no hay ningún link vivo.

Elegimos SHA-256 y no bcrypt a propósito: un token de 256 bits ya es inadivinable, y el hash nos permite buscarlo por igualdad con índice único en vez de compararlo uno por uno. Además hay **un solo token activo por cuenta**: emitir uno nuevo marca los anteriores como usados en la misma transacción.

El envío es asíncrono, como pide el criterio de aceptación: `auth-service` publica en la cola `send_email` y el `email-worker` renderiza el mail y lo despacha por Resend. Si el rechazo es transitorio reintenta con backoff; si el mensaje es inutilizable, va a la DLQ.

El consumo es **atómico** (`UPDATE ... WHERE used_at IS NULL`), así dos POST simultáneos no aplican el mismo link dos veces. Y al cambiar la clave se borran **todas** las sesiones de la cuenta. Dos detalles más: `/password/forgot` responde `200` exista o no la cuenta —no se pueden enumerar usuarios— y la contraseña nueva se valida **antes** de consumir el token, así una clave débil devuelve `400` sin quemar el link.

> Del login pasamos al dominio. Los perfiles.

### Diapo 5 — Perfiles y Almacenamiento S3

Cada servicio es dueño de sus datos y ninguno comparte base: **tres PostgreSQL en RDS** —`discordia_auth`, `discordia_profile` y `discordia_server`—, **MongoDB Atlas** para el historial de `text-channel` y **`voice-calls` sin base**, porque su presencia vive en memoria. El motor lo elige el modelo de datos: relacional donde hay relaciones fuertes —cuentas, perfiles, servidores y roles— y documental donde cada mensaje es un documento con forma variable por canal. Lo que se comparte es el contrato, no el esquema: no hay consultas cruzadas ni transacciones distribuidas.

Dentro de ese mapa, `profile` es el caso interesante porque tiene **dos escritores** sobre la misma base: la API, para lo que hace el usuario, y el worker, que crea el perfil y sincroniza el username. Por eso todos los `PATCH` usan bloqueo optimista con `version` e `If-Match`: si el worker y el usuario escriben a la vez, el segundo recibe `412` en lugar de pisar el cambio del otro.

El avatar **no pasa por la EC2**. Es un flujo de tres fases: el servicio firma una **política de POST a S3** con 5 minutos de vida, el navegador sube el archivo directo al bucket y recién ahí el `PATCH` persiste la URL. El límite de tamaño y el `Content-Type` los aplica el storage, no el cliente.

Probamos primero el `PUT` prefirmado y lo descartamos con evidencia: contra el bucket real ignoraba el tamaño firmado —subimos 6 MB con una firma de 68 bytes y respondió `200`—. Con `POST` y `content-length-range` el objeto se rechaza antes de escribirse.

Dos cosas más: el contrato valida que la URL pertenezca a nuestro storage, así un cliente no puede persistir una URL ajena; y cuando un cambio de avatar se confirma, se borra el anterior. La consistencia con `auth` es eventual: el perfil nace del evento `UserCreated` y el username se replica con `UsernameSet`, que solo pisa el nombre visible si seguía derivando del username —no toca una personalización—.

> Los perfiles tienen su base. Los servidores tienen otra, y ahí vive el segundo sistema de permisos.

### Diapo 6 — Gestión de Servidores

Acá conviven **dos sistemas de permisos** y conviene no mezclarlos. El **rol de plataforma** (`visitor` / `admin`) vive en `accounts` y dice quién es staff de Discordia. El **rol de comunidad** vive en `server` y dice qué puede hacer un miembro dentro de un servidor. Una cuenta puede ser `admin` de la plataforma y miembro raso de un servidor, o al revés.

Los permisos de un rol son un **bitmask `BIGINT`** con un enum *append-only*: agregar un permiso nuevo usa un bit libre y no renumera nada de lo ya guardado. El permiso efectivo de un miembro es `DEFAULT ∪ OR(roles)`: el dueño tiene todo, el no miembro cero, y el miembro el baseline más la unión de sus roles. Es **aditivo**, así que asignar un rol nunca le quita una capacidad.

Las invitaciones también tienen una decisión fina: el consumo de un uso es un **UPDATE condicional** —`revoked = false`, `maxUses` nulo o `usesCount < maxUses`, y `expiresAt` vigente—. Dos personas entrando a la vez no pueden consumir el mismo último uso, y alguien que ya es miembro no consume ninguno.

Una aclaración de alcance: ban y transferencia de propiedad están resueltos **por API y gateway, sin UI**; unban todavía no está. Lo digo porque en la tabla de progreso aparecen exactamente así, como backend listo.

> Con los permisos resueltos, veamos cómo se usan de verdad. Primero, el transporte en vivo.

### Diapo 7 — Mensajería en Tiempo Real

El WebSocket entra por el gateway, que valida el access JWT y lo reenvía a `text-channel` inyectando `X-User-Id`. El navegador no puede mandar el header `Authorization` en el handshake, así que el token viaja como *query param*; el gateway lo valida igual que cualquier ruta y **no lo reenvía**. Si no sirve, cierra con `4401`.

Hoy corre una réplica, pero el fan-out ya está resuelto porque el problema aparece apenas hay dos: en un deploy con solapamiento, los clientes del contenedor viejo no ven los mensajes que entran por el nuevo. `text-channel` publica cada mensaje en un topic de Redis y cada réplica lo entrega a **sus** conexiones locales. El publicador no difunde en proceso: espera su propio mensaje de la suscripción, y así hay exactamente una entrega por conexión. Si `REDIS_URL` está vacío, el servicio funciona igual en modo local.

Si Redis se cae, el mensaje ya está persistido: se difunde a las conexiones locales y se registra la degradación; el envío **no** falla. Es el criterio inverso al de la autorización, que sí es *fail-closed*, porque ahí todavía no se guardó nada.

Para el historial usamos **cursores** en vez de offset. Un cursor es una posición `(created_at, _id)`, no un id de mensaje: por eso borrar el mensaje que ancla una página no rompe la paginación. La reconexión usa `resume_after` y trae solo lo que pasó mientras el socket estaba caído. Y editar o borrar el mensaje de otro exige `MANAGE_MESSAGES`.

> Y ahora el mismo mensaje, de punta a punta.

### Diapo 8 — Flujo End-to-End: Envío de Mensaje

El orden es deliberado: **permiso, persistencia y difusión**.

1. **Permiso.** `text-channel` consulta a `server` por HTTP interno, con `X-User-Id` y `X-Internal-Token`. La respuesta se cachea 5 segundos por par (canal, usuario): absorbe ráfagas y acota la ventana de revocación. Si `server` no responde, es *fail-closed*: no se persiste ni se difunde, el emisor recibe un frame de error y el socket **no** se cierra.
2. **Persistencia** en MongoDB.
3. **Difusión** por Redis a todos los clientes del canal.

¿Por qué este orden? Porque al revés quedarían mensajes fantasma en pantalla. ¿Y por qué la autorización no está en el gateway? Porque tendría que parsear frames: duplicaría la política de dominio y dejaría de ser un relay agnóstico. `text-channel` consume un booleano; la regla vive en `server`.

El trade-off lo asumimos: `text-channel` suma una dependencia de disponibilidad **para escribir**. Si `server` está caído, el chat queda degradado —no se puede enviar— pero la lectura sigue disponible.

> Todo esto corre sobre la infraestructura, que cierro yo.

---

## Preguntas posibles y cómo defenderlas

### Mensajería asíncrona (2b)

**¿Por qué RabbitMQ y no Kafka?**
Necesitamos colas de trabajo con ACK, reintento y DLQ, no un log retenido. Kafka agrega JVM y KRaft: el costo operativo es desproporcionado para el volumen del TP. Está en las alternativas descartadas del ADR-003.

**¿Qué pasa exactamente si el broker se cae?**
`auth-service` sigue respondiendo: el publish se descarta con un warning y se reintenta la conexión en el próximo request. Los consumidores reconectan con backoff —en `text-channel` arranca en 2 s y duplica hasta 30 s, sin rendirse—. Los mensajes de las colas de trabajo sobreviven en disco: son quorum sobre un volumen persistente. El fanout de cuentas es distinto: la cola de cada réplica es exclusiva y no durable, así que una réplica que está reiniciando se pierde ese evento. El costo real: mientras el broker esté caído, la suspensión no se propaga y el perfil nuevo no se crea.

**¿At-least-once no genera duplicados?**
Sí, y por eso los consumidores son idempotentes: el perfil usa la clave natural (`INSERT ... ON CONFLICT (user_id) DO NOTHING`) y el mail viaja con `event_id` como `Idempotency-Key`, así una reentrega no manda dos correos.

**¿Por qué un worker separado en vez de consumir dentro de la API?**
Para aislar CPU e I/O: el proceso HTTP y `/livez` no compiten con el procesamiento de eventos. Reutiliza la misma imagen, el mismo ECR y el mismo pipeline, así que no suma infraestructura.

**¿Por qué fanout para los eventos de cuenta y no una cola?**
Una cola de trabajo **reparte**: el evento llegaría a una sola réplica y las conexiones de las demás quedarían abiertas. El fanout con una cola exclusiva por réplica hace que todas se enteren y cierren lo suyo.

**¿Qué es un mensaje "veneno"?**
Un payload inválido que se reintentaría para siempre. Se desvía a la DLQ y se hace `ack` en la cola principal para no bloquear a los demás. Lo que falta es alertar sobre la DLQ: hoy es revisión manual.

### Autenticación y sesiones (3)

**¿Por qué el gateway no valida contra `auth-service` en cada request?**
Porque el token es *stateless*: alcanza con verificar la firma y la expiración. Ese es el motivo del access de 15 minutos: cuanto más corto, menor la ventana de un token robado, y el refresh cubre la renovación.

**¿Cómo revocan un access antes de que expire?**
El claim `sid` ata el token a su sesión. Logout y suspensión devuelven los `sid`, el gateway los anota con TTL de un access más 60 s de margen y responde `401 Session revoked`.

**¿Y si se reinicia el gateway?**
La lista es por proceso: los tokens revocados vuelven a aceptarse hasta su `exp`, 15 minutos como máximo. Es un límite conocido y documentado; la solución es un store compartido (Redis o la base de sesiones). Lo tenemos como deuda técnica, no lo ocultamos.

**¿Por qué el refresh es opaco y no un JWT?**
Porque es una clave, no un documento: el estado vive en la fila de `sessions`, y eso permite revocarlo de verdad y borrarlo. Un JWT de refresh solo podría invalidarse con otra lista negra.

**¿El refresh rota en cada renovación?**
Hoy no: se extiende la ventana deslizante sobre el mismo valor, con el mismo `sid`. La rotación con detección de reuso es una mejora posible; el argumento de seguridad actual es que nunca es accesible desde JavaScript.

**¿Dónde vive cada token y qué pasa con un XSS?**
El access, solo en memoria (Redux): un XSS podría usarlo mientras la pestaña esté abierta, pero no robarlo del storage. El refresh web es cookie `HttpOnly` —invisible para JS— y en móvil va en `expo-secure-store`. CORS es con orígenes explícitos y credenciales: `*` no es válido en ese modo.

**¿Cómo funciona el login con Google?**
El cliente obtiene un `id_token` y lo manda a `POST /api/login/google`. Se verifica contra nuestro `GOOGLE_CLIENT_ID` y se exige `email_verified`. Si la cuenta no existe se crea **sin contraseña** (`password_hash = NULL`), se publica `UserCreated` y el usuario elige username después. Si existe, se reutiliza. La suspensión también bloquea este camino.

**¿Cómo guardan las contraseñas?**
`bcrypt` con costo 12, y requisitos mínimos: 8 caracteres, mayúscula, minúscula y número. La comparación es `checkpw`, nunca comparación de strings.

**¿Por qué es seguro confiar en `X-User-Id`?**
Porque ningún servicio interno está publicado: solo Traefik expone puertos, y `server` y `voice-calls` no tienen router. La única vía para que ese header exista es el gateway. El endpoint interno de permisos suma además `X-Internal-Token`.

### Recupero de contraseña (3b)

**¿Por qué SHA-256 y no bcrypt para el token?**
Porque no es una contraseña: son 256 bits aleatorios, no hay diccionario que atacar. Y a diferencia de bcrypt, el hash permite buscar por igualdad con índice único, sin recorrer todos los tokens.

**¿Cómo evitan enumerar usuarios?**
`/password/forgot` responde siempre `200` con el mismo cuerpo. Si la cuenta no existe no se genera token ni se publica nada. El cliente muestra "si el email está registrado, vas a recibir un enlace".

**¿Dos pedidos simultáneos generan dos links?**
No: hay un solo token activo por cuenta. La emisión marca los anteriores e inserta el nuevo en la misma transacción, y además hay un cooldown de 60 segundos por cuenta para no inundar de mails.

**¿Y si el usuario hace doble clic en "cambiar contraseña"?**
El consumo es atómico: `UPDATE ... WHERE used_at IS NULL`. El segundo request no afecta ninguna fila y responde "token inválido, vencido o ya usado". No se aplica dos veces.

**¿Por qué revocar todas las sesiones al cambiar la clave?**
Porque el escenario típico de un reset es que la cuenta estuvo comprometida. `DELETE FROM sessions WHERE account_id = ?` expulsa cualquier sesión abierta, y el gateway revoca los access de esos `sid`.

**¿Cómo se protege de fuerza bruta?**
El gateway limita por IP: 3 pedidos por hora en `/password/forgot` y 10 por hora en `/password/reset`. Más un token de 256 bits, que no se adivina.

**¿Una cuenta creada con Google puede recuperar contraseña?**
Sí, y es el camino previsto: nació con `password_hash = NULL`, así que el reset es la forma de **adquirir** la primera contraseña. El ancla de confianza es la posesión del correo que Google ya verificó.

### Perfiles y S3 (5)

**¿Cuántas bases tiene la plataforma y por qué no una sola?**
Tres PostgreSQL en RDS —`discordia_auth`, `discordia_profile` y `discordia_server`— y MongoDB Atlas para `text-channel`; `voice-calls` no persiste. Una base por servicio: cada esquema evoluciona con su equipo y su pipeline, sin acoplar despliegues ni exigir transacciones distribuidas.

**¿Por qué MongoDB para el chat y PostgreSQL para el resto?**
Porque el mensaje es un documento con forma variable por canal y se lee como una posición dentro de un historial; el resto son relaciones fuertes —cuentas, perfiles, servidores, roles— donde las constraints de la base hacen el trabajo. Se eligió por modelo de datos, no por moda.

**¿Y si una consulta necesita datos de dos servicios?**
No se hace contra la base del otro: se resuelve por contrato HTTP —como el permiso de envío— o por evento, como el perfil y el username. Compartir la base sería el atajo que rompe la autonomía y obliga a coordinar cada migración entre equipos.

**¿Por qué el archivo no pasa por la EC2?**
Porque el servicio solo firma: el navegador hace el `POST` directo al bucket. Ahorramos ancho de banda y latencia, y el tamaño lo aplica el storage, no el cliente.

**¿Por qué POST prefirmado y no PUT prefirmado?**
Porque lo probamos contra el bucket: el `PUT` ignoraba el `ContentLength` firmado —subimos 6 MB con una firma de 68 bytes y devolvió `200`—. Con `POST` la condición `content-length-range` y el `Content-Type` firmado rechazan el objeto antes de escribirlo.

**¿Qué pasa si el usuario sube el archivo y nunca confirma el cambio?**
Queda un objeto huérfano en el bucket. Está registrado como fuera de alcance en el ADR; lo que sí limpiamos es el avatar **reemplazado** en un cambio confirmado.

**¿Puede un cliente guardar una URL de otro sitio como avatar?**
No: el contrato `PATCH` valida que el host de la URL coincida con nuestro `s3_public_base_url`. Una URL externa devuelve `422`.

**¿Por qué dos escritores en la misma base no se pisan?**
Porque la escritura es optimista: cada perfil tiene `version` y los `PATCH` mandan `If-Match`. Si la versión cambió, `412 Precondition Failed` y el cliente relee.

**¿Cómo se sincroniza el username sin pisar lo que el usuario personalizó?**
`auth-service` publica `UsernameSet` con `previous_username`, leído de su base y no del token. `profile` actualiza el nombre visible solo si todavía derivaba del username —el placeholder o el valor anterior—; cualquier otro valor fue personalizado y no se toca.

### Servidores, roles e invitaciones (6)

**¿Por qué no reutilizar `accounts.role`?**
Porque son conceptos distintos con ciclos de vida distintos: ser `admin` de la plataforma no dice nada dentro de un servidor. El rol de comunidad vive en `server`, que ya es dueño de servidores, canales y miembros.

**¿Por qué un bitmask y no una tabla de permisos?**
Porque el permiso efectivo es un `OR` sobre un entero, sin un join por permiso en cada verificación. Y es *append-only*: agregar un permiso no renumera los datos existentes.

**¿Cómo se calcula el permiso efectivo?**
Dueño: todos. No miembro: cero. Miembro: `DEFAULT ∪ OR(roles)`. Es aditivo a propósito: asignar un rol nunca degrada lo que el miembro ya podía hacer, y quitar el último rol vuelve al baseline.

**¿Un rol puede escalar privilegios?**
Hoy no, porque `MANAGE_ROLES` **no se acepta**: administrar roles exige `ADMINISTRATOR` (o ser dueño). Sin comparación de jerarquía, `MANAGE_ROLES` permitiría crear o asignarse un rol con `ADMINISTRATOR`. Se habilita cuando exista el reordenamiento.

**¿Dos roles creados a la vez no colisionan en la posición?**
No: `CreateRole` bloquea la fila del servidor con `SELECT ... FOR UPDATE` y calcula `max(position) + 1` en la misma transacción. El `UNIQUE (server_id, position)` diferido es el backstop para el reordenamiento.

**¿Dos personas usando la misma invitación de un solo uso?**
Solo una entra: el incremento es un `UPDATE` condicional que exige `usesCount < maxUses`. El que pierde recibe `400` y no crea membresía.

**¿Ban y transferencia están terminados?**
Backend y gateway sí; **UI no**, y unban no está implementado. Lo presentamos como "API lista" y así figura en la tabla de progreso.

### Mensajería en tiempo real (7)

**¿Por qué WebSocket y no polling o SSE?**
Porque el canal es bidireccional y de baja latencia: un frame entra y se difunde sin handshakes nuevos. SSE solo serviría para recibir.

**¿Cómo se autentica el WebSocket?**
El navegador no permite headers en el handshake, así que el access token va en la query. El gateway lo valida con la misma lógica que una ruta protegida —firma, `exp`, revocación— y **no lo reenvía**: hacia `text-channel` solo viaja `X-User-Id`. Si el token es inválido, `close 4401`.

**¿Qué aporta Redis si hoy hay una sola réplica?**
Corrección futura sin reescribir nada: en un deploy con solapamiento conviven dos contenedores, y sin fan-out los clientes de uno no verían los mensajes del otro. Con `REDIS_URL` vacío el servicio funciona igual, en modo local.

**¿No se duplica el mensaje para el emisor?**
No: si el publish sale bien, la réplica publicadora no difunde en proceso; recibe su propio mensaje por la suscripción, como todas. Exactamente una entrega por conexión.

**¿Y si Redis se cae?**
El mensaje ya está en MongoDB: se entrega a las conexiones locales y se registra la degradación. El envío no falla, porque el criterio es "persistido primero".

**¿Por qué cursores en vez de offset?**
Porque con offset, un mensaje nuevo entre dos páginas hace que el cliente repita o se saltee uno. El cursor es una posición `(created_at, _id)` y no depende de que el mensaje ancla exista —clave para cuando llega el borrado—.

**¿Cómo recupera el cliente lo que se perdió mientras estaba desconectado?**
Con `resume_after=<cursor>` en el handshake o al reconectar: trae solo lo posterior a esa posición, sin recargar el historial completo.

### Flujo end-to-end (8)

**¿Por qué el permiso se consulta por mensaje y no en el handshake?**
Porque una membresía puede revocarse con el socket abierto. Validar solo el handshake no detecta esa revocación; la caché de 5 segundos acota la ventana exactamente a eso.

**¿Por qué *fail-closed* y no *fail-open*?**
Porque es preferible un chat degradado a un mensaje sin permiso. Si `server` no responde no se persiste ni se difunde, y el socket se mantiene abierto para que el usuario reintente.

**¿Por qué persistir antes de difundir?**
Porque el emisor nunca debe ver un mensaje que no quedó guardado. Al revés, un fallo de escritura deja mensajes fantasma en pantalla que desaparecen al recargar.

**¿No agrega latencia un HTTP por mensaje?**
Solo para pares (canal, usuario) que no estén cacheados: la caché de 5 s absorbe las ráfagas de una conversación normal. Y es una llamada interna, en la misma red Docker.

**¿Por qué el gateway no autoriza?**
Porque tendría que parsear frames: acoplaría el transporte al protocolo, duplicaría la política y dejaría de ser agnóstico. El gateway hace relay; la regla vive en `server` y `text-channel` consume un booleano.

### DevOps y operación (11)

**¿Qué pasa si un servicio se cae?**
`restart: unless-stopped` y healthchecks. El orden de arranque está declarado: el gateway espera a `auth` y `profile` sanos, y `text-channel` espera a Redis.

**¿Por qué `/livez` en el healthcheck y no `/readyz`?**
Porque `/readyz` consulta dependencias —Mongo, LiveKit, la base— y un hipo del proveedor reiniciaría un contenedor sano. `/livez` responde si el proceso está vivo: es lo que corresponde para decidir un reinicio.

**¿Y si la migración falla en producción?**
El paso corre bajo `set -e` **antes** de recrear el contenedor: el job queda rojo y la versión anterior sigue sirviendo. Nunca queda un deploy verde con el servicio roto.

**¿Cómo cambian el esquema sin downtime?**
Con *expand/contract*: primero se deja el esquema compatible con las dos versiones del código y, en un release posterior, se retira lo viejo. El caso real fue `sessions.role`: primero se quitó el `NOT NULL` y el drop de la columna quedó para el release siguiente.

**¿Dónde están las credenciales de AWS?**
No hay claves fijas: GitHub Actions asume un rol por repositorio con OIDC. Ese rol solo puede empujar a su repositorio ECR y enviar comandos SSM a la instancia. Los tags de imagen son inmutables.

**¿Por qué Compose y no Kubernetes?**
Una instancia, un stack, sin necesidad de orquestación multi-nodo. Kubernetes sumaría control plane, manifiestos y superficie de ataque sin resolver nada que hoy nos duela. Si mañana hay que escalar, el paso natural es migrar `text-channel` con balanceo y mover la presencia de voz a un store compartido.

**¿Tienen métricas?**
Hoy sondas `/livez` y `/readyz`, healthchecks de Compose y badges de tests y cobertura. Un tablero de métricas con Grafana quedó como exploración, no está desplegado. Es parte del roadmap, no lo vendemos como hecho.

### Transversales (las incómodas)

**¿Qué es lo más débil de la arquitectura?**
Cuatro cosas, en orden: la lista de revocación del gateway es por proceso; `voice-calls` no consume `account_events`, así que la suspensión no corta una llamada en curso; hay una sola réplica de `text-channel` en producción; y las DLQ no tienen alertas. Las cuatro están documentadas y con plan.

**¿Por qué microservicios y no un monolito?**
Por el dominio y por el equipo: cada servicio tiene su modelo de datos y su stack —Quarkus para `server`, Python para el resto, Mongo para el chat—. Asumimos el costo: más complejidad operativa, que es exactamente lo que cubre la parte de DevOps.

**¿La consistencia eventual es aceptable?**
Donde la usamos, sí: perfiles y username toleran una ventana de milisegundos y el cliente reintenta. Donde no es aceptable, no la usamos: el permiso de envío es *fail-closed* y la suspensión revoca en el momento.

**¿Qué harían distinto si empezaran de nuevo?**
Un store compartido para las revocaciones desde el día uno, y presencia de voz fuera de la memoria del proceso. Lo demás lo volveríamos a hacer igual.

**¿Cuánto de esto es código propio y cuánto es servicio gestionado?**
Propio: los seis servicios de la plataforma —gateway incluido—, el modelo de permisos y todo el flujo de mensajería. Gestionado: RDS, S3, Atlas, LiveKit y RabbitMQ como contenedor con volumen persistente. La decisión fue no operar lo que no aporta al TP.

---

## Chuleta de números

| Dato | Valor |
|---|---|
| Access token | JWT HS256, 900 s (15 min) |
| Refresh token | opaco, 7 días deslizante, tabla `sessions` |
| Ventana de revocación en el gateway | access TTL + 60 s |
| Hash de contraseña | bcrypt, costo 12 |
| Token de reset | 256 bits, solo SHA-256 en la base, TTL 3600 s |
| Cooldown de reset | 60 s por cuenta |
| Rate limit | 3/h `forgot`, 10/h `reset` (por IP) |
| Política de POST a S3 | TTL 5 min, avatar 1–5 MB |
| Caché de permisos | 5 s, 1024 entradas |
| Mensaje | máximo 2000 caracteres |
| Historial | 50 por página (máximo 100) |
| Cobertura mínima | 70% |
| Bases por servicio | PostgreSQL 16 `discordia_auth` · PostgreSQL 17 `discordia_profile` · PostgreSQL `discordia_server` · MongoDB Atlas `discordia_text_channel` · `voice-calls` sin base |
| Puertos internos | 22000 gateway · 22001 auth · 22002 server · 22004 profile · 22005 text-channel · 22007 voice-calls |
| Reconexión al broker (`text-channel`) | 2 s inicial, duplica hasta 30 s |

---

## Lo que NO conviene afirmar

- Que la suspensión **expulsa de los canales de voz**: `voice-calls` no consume `account_events`. Sí expulsa de las WebSockets de texto.
- Que **ban, unban y transferencia** están terminados: hay API y gateway, sin UI; unban no existe.
- Que el **perfil público** (HU-36) está terminado: el endpoint responde, la pantalla del cliente no está.
- Que la lista de revocación **sobrevive a un reinicio** del gateway: no, vive en el proceso.
- Que hay **métricas o Grafana** en producción: no están desplegados.
- Que el **refresh token rota** en cada renovación: no rota; se extiende la ventana.
