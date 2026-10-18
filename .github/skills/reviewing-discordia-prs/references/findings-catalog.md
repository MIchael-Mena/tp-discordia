# Catálogo de fallas recurrentes

Fallas que ya aparecieron en la cadena `server` → `gateway` → `voice-calls` → `web-client`. Cada entrada trae cómo detectarla rápido y el fix típico. **Ordená la búsqueda por este catálogo**: cubre la mayoría de los hallazgos reales.

---

## A. Autorización

**A1 · Autorizador allow-all disfrazado.**
Una clase llamada `ChannelAuthorizer`/`Guard` con `return true`, o un `if` que siempre pasa, mientras el contrato promete "sólo el dueño/miembro".
*Detectar:* buscá implementaciones del puerto de autorización y leé el cuerpo, no el nombre. Buscá quién lo instancia en el composition root.
*Ejemplo:* `AllowAllChannelAuthorizer` dejaba a cualquier autenticado crear/editar/borrar canales de cualquier server (server #10).
*Fix:* decisión real (owner o membresía) + test que verifique el camino negado.

**A2 · Política por existencia presentada como autorización.**
"Si el recurso existe y pertenece al padre ⇒ `allowed`". No autoriza a nadie: autoriza a todos.
*Detectar:* preguntá "¿qué caller obtiene *deny* hoy?" Si la respuesta es "sólo si no existe", es un oráculo de existencia, no un control de acceso.
*Ejemplo:* `DecideChannelAccess` v1 (server #12), consumido como única puerta de la voz.

**A3 · Justificación que cita un hecho falso.**
"El modelo de membresía no existe todavía" cuando la tabla, la entidad, el repositorio y tres casos de uso ya existen en `develop`.
*Detectar:* `git grep -n "<symbol>" origin/develop` antes de aceptar cualquier "no existe todavía". Verifiquémoslo también en la rama base, no sólo en `develop`.
*Ejemplo:* `server_members` + `ServerMemberRepository.existsByServerIdAndUserId` existían y ya se aplicaban en `LeaveServer`/`InitiateOwnershipTransfer` (server #12).
*Fix:* corregir el fundamento en **todos** los documentos donde se repite (spec, research, contract, data-model, javadoc) y enunciar el riesgo residual con palabras llanas.

**A4 · Endpoint "interno" que es público.**
La doc dice "no expuesto por el gateway" y el servicio está publicado igual con `PathPrefix`.
*Detectar:* abrí `infra/compose.prod.yaml` y leé las labels de Traefik del servicio. `PathPrefix('/x')` + `stripprefix` = **todo** `/x/*` es público, sin importar lo que diga el README. Verificá que no haya otra regla más restrictiva.
*Ejemplo:* `server` se publica en `/server`, así que `GET /server/channels/{id}/access-decision` era alcanzable desde internet (server #12, contradiciendo FR-009).

**A5 · El gate del cliente no es el gate del servidor.**
El menú de administración sólo aparece para el dueño, pero el backend no lo exige. *Detectar:* buscá si el callback que habilita la acción depende de `isOwner`/`isAdmin` y qué hace el servidor con el mismo request. Es correcto tener ambos, pero el hallazgo es cuando **sólo** existe el del cliente.

**A6 · Identidad que el cliente puede escribir.**
El servicio público confía en `X-User-Id` y se alcanza directo (ver A4). Cualquier valor no vacío sirve. *Detectar:* ¿dónde se valida el header? Si es sólo "no está en blanco" y el servicio está expuesto, la identidad es forjable.

---

## B. Contratos entre servicios

**B1 · La doc promete un status que el código nunca emite.**
*Detectar:* por cada status de la tabla del contrato, buscá quién lo produce (`throw`, `Response.status`). Si una rama del controller captura una excepción que nadie lanza, es código muerto y el status no existe.
*Ejemplo:* el contrato de `voice-calls` prometía `404` para canal inexistente; el access gateway convertía el 404 en `deny` ⇒ salía `403` (voice-calls #1).

**B2 · El contrato se contradice a sí mismo.**
"The body is always `{allowed, reason}`" conviviendo con "un UUID mal formado devuelve el 404 del contenedor". *Detectar:* leé las garantías y las excepciones en la misma tabla.
*Consecuencia real:* el consumidor no encuentra `reason` y reporta "servicio no disponible" en vez de "canal inexistente".

**B3 · Ejemplos del contrato mal formados.**
`"room_name": "server-server-uuid-channel-channel-uuid"` (placeholder sustituido dentro del literal). *Detectar:* compará el ejemplo con el `String.format`/f-string que lo genera y con el assert del test.

**B4 · El consumidor ya mergeado no manda un campo que el productor pasó a exigir.**
*Detectar:* por cada campo nuevo requerido, buscá el call site en el otro repo (`web-client`/`gateway`).
*Ejemplo:* `type` pasó a ser obligatorio en `server` #10 mientras `createChannel.ts` seguía mandando `{name}` ⇒ 400 en producción.

**B5 · Transporte de la confirmación inconsistente.**
`DELETE /servers/{id}` usa body y `DELETE /servers/{id}/channels/{id}` usa `?confirm=`. No es un bug, pero confunde al cliente y rompe la convención. *Fix:* unificar o documentarlo explícitamente.

**B6 · Verbatim relay + contrato distinto.**
El gateway reenvía el body tal cual: si el productor usa snake_case y el cliente camelCase, nada falla en el relay y todo falla en el borde. *Detectar:* comparar los tres (productor, relay, cliente) campo por campo.

---

## C. Persistencia y esquema

**C1 · `init_database.sql` que no se ejecuta nunca.**
Postgres corre `docker-entrypoint-initdb.d` **sólo** con el data directory vacío. Un `ALTER ... IF NOT EXISTS` agregado ahí no arregla volúmenes existentes.
*Detectar:* ¿el servicio tiene migraciones (Flyway/Alembic) o sólo el init script? ¿Hay volumen nombrado en el compose?
*Ejemplo:* `db/init_database.sql` con el comentario "sin paso manual" mientras el README exigía correr el `psql` a mano (server #13). Modo de falla: **500 en todos los endpoints** que tocan la tabla (`column c.type does not exist`).

**C2 · Dos PRs con mecanismos de migración incompatibles.**
Uno extiende el init script; el otro borra ese archivo y activa Flyway con `migrate-at-start`. Si el segundo mergea sobre una base creada por el primero, Flyway falla al bootear (schema no vacío sin `flyway_schema_history`, sin `baseline-on-migrate`).
*Detectar:* comparé `src/main/resources/application.properties`, la carpeta de migraciones y la existencia de `init_database.sql` en **cada** rama abierta.

**C3 · Falta el `CHECK` y nadie lo puede detectar en tests.**
La columna queda `TEXT NOT NULL` sin `CHECK (x IN (...))`, y como `%test` usa `hibernate schema-management=drop-and-create` desde la entidad (sin `@Check`), ningún test puede fallar por eso. El invariante del `data-model.md` no está garantizado por el storage.
*Fix:* `ADD CONSTRAINT ... NOT VALID` + `VALIDATE` para que sea idempotente.

**C4 · Upsert que ignora campos en el update.**
`save()` escribe todos los campos en el insert y sólo algunos en el update (o usa un `MERGE` parcial). *Detectar:* leé la rama de update del repositorio y compará con el DTO que recibe.
*Ejemplo:* `ChannelRepositoryImpl.save()` no persistía `serverId/type/categoryId/position/createdBy`.

**C5 · `max + 1` para el próximo orden.**
No es atómico: dos altas concurrentes se pisan. Aceptable si está documentado; hallazgo si el contrato promete unicidad o determinismo.

---

## D. Configuración

**D1 · Knob documentado que no hace nada.**
*Detectar:* por cada variable de entorno, buscá el punto donde **cambia el comportamiento observable**. Si sólo se lee y se guarda, es inerte.
*Ejemplo:* `LIVEKIT_TOKEN_TTL_SECONDS` se pasaba al servicio pero `AccessToken` nunca recibía `.with_ttl()`, así que el JWT salía con el default de la librería (6 h) y `expires_at` reportaba otra cosa. Probado decodificando el JWT.

**D2 · Config obligatoria que se descubre en el primer request.**
`Settings` con campos requeridos + `lru_cache` ⇒ `/livez` responde 200 y el primer request da 500 con un `ValidationError` sin manejar. *Fix:* forzar la validación en el `lifespan`/arranque.

**D3 · Defaults que rompen la simetría.**
Cuatro servicios con `http://localhost:220xx` y uno con el nombre Docker: correr fuera de Docker rompe **sólo** ese relay. *Detectar:* mirá los defaults juntos, en la misma clase.

**D4 · Valores de producción que apuntan a un servicio inexistente.**
`%prod` con `jdbc:postgresql://server-db:5432/...` o `VOICE_CALLS_SERVICE_URL` por defecto cuando el servicio no está en `compose.prod.yaml`: la ruta nace **inerte** (500/502 permanente). Puede ser aceptable (gate de infra), pero tenía que estar dicho.

---

## E. Concurrencia y recursos

**E1 · Timeout que no acota.**
`with ThreadPoolExecutor(...) as ex: future.result(timeout=T)` no limita nada: al salir del bloque, `shutdown(wait=True)` espera la tarea en curso. Peor si el trabajo es CPU local (firma HMAC), donde no hay nada que acotar.
*Detectar:* medí el tiempo real con una tarea más lenta que el timeout. Si el tiempo real ≈ la tarea, el timeout es decorativo. Un timeout real necesita `urlopen(timeout=)`, `httpx(timeout=)` o cancelación efectiva.

**E2 · Check-then-act en dos secciones críticas.**
`get_user_session(...)` y después `remove_user_session(...)`: entre las dos, un `join` puede guardar una sesión nueva y el remove borra **esa**.
*Detectar:* buscá pares get/modify sobre un repositorio con lock propio. El lock por método no hace atómica la operación de negocio.
*Fix:* un método atómico (`remove_session_if(user, server, channel)`).

**E3 · El estado de la UI dice "desconectado" pero el recurso sigue vivo.**
El caso clásico: conectar la sala y después pedir el micrófono. Si el micrófono falla, la conexión ya está establecida y nadie la cierra; el `catch` del provider sólo limpia estado local.
*Detectar:* por cada `await` después de adquirir un recurso, preguntá "¿quién libera esto si este await falla?".
*Ejemplo:* negar el micrófono en `livekit-client` emite `MediaDevicesError` **y re-lanza** ⇒ sala huérfana y error crudo en inglés, dos veces (web-client #131).

**E4 · Acción destructiva que deja a otros consumidores con estado inválido.**
Borrar un canal mientras el usuario está conectado a su llamada de voz: la fila desaparece, el panel deja de ser alcanzable y el micrófono sigue abierto.
*Detectar:* por cada borrado/desactivación, buscá quién más referencia ese id en el estado global (llamadas, sockets, selección, drafts).

---

## F. Validación de entrada

**F1 · Ids interpolados en una URL sin validar.**
`channel_id: str` → `f"{base}/channels/{channel_id}/..."`. Un `%2E%2E` normalizado por el cliente HTTP reescribe el path del upstream; un `%3F` inyecta query.
*Detectar:* probalo (probe de `httpx.URL`, `TestClient`) — no lo razones.
*Fix:* tipo fuerte en el borde (`uuid.UUID`, `UUID` de JAX-RS) o escape (`quote(safe="")`, `URLEncoder`, `encodeURIComponent`).

**F2 · Coerción silenciosa de tipos.**
DTO con `JsonNode` + `asText()`: `{"name": 123}` se convierte en `"123"`. Aceptable para PATCH parcial, pero hay que decirlo y testearlo, o tipar el DTO.

**F3 · Tipo de TypeScript que dice "siempre presente" sobre un payload que puede no traerlo.**
`type: ChannelType` (requerido) mientras el código hace `channelType?: ChannelType` y trata `undefined` como `text`. Peor: si el PR del backend que agrega el campo no está mergeado, **todo** cae en el default y la feature nueva es invisible.
*Detectar:* por cada campo nuevo del payload, verificá qué PR lo introduce y si ya está en la rama base.

---

## G. Tests

**G1 · Fixtures que fijan un contrato ficticio.**
`serverId`/`token`/`livekitUrl` cuando el productor usa `server_id`/`access_token`. Como el relay es passthrough, los tests quedan verdes igual y documentan algo falso (gateway #40).
*Detectar:* comparé los campos del fixture con el contrato autoritativo del otro repo, uno por uno.

**G2 · Se verifica el status pero no la propiedad de seguridad.**
"401 sin token" sin instalar un handler que registre si el upstream fue llamado. La propiedad ("verificar **antes** de llamar") queda sin cubrir (gateway #40, SC-003).

**G3 · Aserción tautológica.**
`assert seen["url"] == el_mismo_helper_que_produce_la_url(...)`: si el helper cambia el path, el test sigue verde.
*Fix:* derivar del entorno sólo el base y mantener el path literal.

**G4 · Camino de error sin test.**
Los que más importan: micrófono denegado, clic derecho, `401` que no debe propagar, timeout, body mal formado. Si el fix propone un `try/catch`, pedí el test que lo dispara.

**G5 · Cobertura alta, camino crítico sin cubrir.**
97% no dice nada si el 3% es el error del usuario. Mirá el reporte por archivo, no el total.

---

## H. Proceso y PR

**H1 · Dos PRs que implementan lo mismo.**
*Detectar:* `gh pr list --state open` en el repo, y comparé archivos por archivo. Si uno "portó" el trabajo del otro (buscá en el javadoc/commit "ported from"), hay que decidir el dueño antes de mergear.
*Ejemplo:* `server` #10 ya traía `ChannelType` "ported from 003" con Flyway, mientras #13 lo agregaba de nuevo con init script.

**H2 · PR apilado cuya base avanzó.**
`baseRefName` ≠ `develop` + `mergeable: CONFLICTING` + CI de días atrás. Bloqueante de proceso: hay que rebasar y volver a correr los gates antes del review final.

**H3 · Código muerto / rama inalcanzable.**
Excepción declarada y capturada que nadie lanza; use case que ningún router referencia; `403` en el mapa de errores que el backend no emite. *Detectar:* `grep` del símbolo en todo `src/` (sin contar tests).

**H4 · Convención inventada en la justificación.**
El `plan.md` dice "controller-owned HTTP error mapping" cuando el repo tiene 13 `ExceptionMapper`s y ningún controller con `try/catch`.
*Detectar:* si un documento afirma una convención de facto, verificá 2-3 archivos hermanos.

**H5 · El PR body miente sin querer.**
"Los escenarios del quickstart se ejecutaron" cuando el paso 6 no puede funcionar (falta `X-User-Id` ⇒ 401 ⇒ `jq` imprime 0). "Falta mergear `gateway` #37" cuando ya está `MERGED`.
*Detectar:* cada afirmación verificable del body (tests corridos, dependencia pendiente, endpoint documentado) chequeala contra el código o la API.

**H6 · Duplicación que ya divergió.**
4.ª copia del mismo relay; la nueva olvidó reenviar `request.url.query` mientras la original sí lo hace. Rechazar el refactor en un PR aditivo es defendible, pero **registrá la divergencia** y proponé el módulo común como paso aparte.

**H7 · Documentación desalineada tras una convergencia.**
El PR corrige `README` y `contracts` pero deja `data-model.md` con el contrato viejo, o marca `[X]` una tarea cuyo texto dice "Pending". *Detectar:* `grep` del término viejo en **todos** los `.md` del feature.
