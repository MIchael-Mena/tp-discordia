# Estado de las Historias de Usuario — Discordia

**Actualizado:** 2026-11-07 (tener en cuenta que hay otros miembros del equipo que pueden haber avanzado en paralelo y no tienen acceso a este documento).

Seguimiento de todas las HU: completadas y pendientes. Para ver el detalle y criterios de aceptación de cada historia, ver [Historias de Usuario](historias-usuario.md).

**Criterio:** una HU se marca como completada cuando el flujo funciona de punta a punta en el cliente que le corresponde —`web-client` para las historias de usuario final, `backoffice` para las de staff—, con su respaldo en el servicio correspondiente y el relay del `gateway`. La columna **Checkpoint** indica en qué checkpoint se completó; las historias que aún no están implementadas llevan un guion (`-`).

---

## Historias obligatorias — 104 / 104 pts (100%)

Este catálogo define el alcance funcional obligatorio. Los puntos expresan complejidad relativa con escala Fibonacci y contemplan la implementación de las historias de usuario final en la aplicación mobile y el cliente web, y las historias de staff en el backoffice.

Los puntos no reemplazan los Requisitos No Funcionales: todos los RNF del enunciado, incluidos los tres clientes, forman parte obligatoria de la entrega y fueron considerados al calibrar este núcleo.

| # | Historia | Épica | Puntos | Checkpoint | Motivo de obligatoriedad |
| -: | --- | --- | -: | :-: | --- |
| 1 | [Registro de usuarios](historias-usuario.md#hu-1-registro-de-usuarios) | Usuarios | 3 | 1 | Identidad base del sistema |
| 2 | [Login con email y contraseña](historias-usuario.md#hu-2-login-con-email-y-contraseña) | Usuarios | 2 | 1 | Acceso, cierre de sesión y continuidad de la sesión |
| 3 | [Recupero de contraseña](historias-usuario.md#hu-3-recupero-de-contraseña) | Usuarios | 3 | 2 | Recuperación segura, no enumeración y rate limiting |
| 4 | [Edición de perfil](historias-usuario.md#hu-4-edición-de-perfil) | Perfil | 2 | 1 | Gestión de la identidad visible |
| 5 | [Visualización de perfil propio](historias-usuario.md#hu-5-visualización-de-perfil-propio) | Perfil | 1 | 1 | Acceso a los datos y preferencias propios |
| 6 | [Crear servidor](historias-usuario.md#hu-6-crear-servidor) | Servidores | 3 | 2 | Entrada al flujo central de comunidades |
| 7 | [Generar invitación](historias-usuario.md#hu-7-generar-invitación) | Servidores | 5 | 2 | Ingreso con expiración, límite de usos y revocación |
| 8 | [Unirse a servidor vía invitación](historias-usuario.md#hu-8-unirse-a-servidor-vía-invitación) | Servidores | 3 | 2 | Crecimiento y membresía de comunidades |
| 9 | [Abandonar servidor](historias-usuario.md#hu-9-abandonar-servidor) | Servidores | 2 | 2 | Control del usuario sobre su membresía |
| 10 | [Transferir propiedad del servidor](historias-usuario.md#hu-10-transferir-propiedad-del-servidor) | Servidores | 3 | 3 | Salida coherente del owner y continuidad del servidor |
| 11 | [Crear canal](historias-usuario.md#hu-11-crear-canal) | Canales | 3 | 2 | Organización mínima del servidor |
| 12 | [Editar canal](historias-usuario.md#hu-12-editar-canal) | Canales | 2 | 2 | Gestión del espacio de comunicación |
| 13 | [Eliminar canal](historias-usuario.md#hu-13-eliminar-canal) | Canales | 2 | 2 | Ciclo de vida completo de canales |
| 14 | [Organizar canales en categorías](historias-usuario.md#hu-14-organizar-canales-en-categorías) | Canales | 3 | 3 | Navegación de servidores con múltiples canales |
| 15 | [Enviar mensaje en un canal](historias-usuario.md#hu-15-enviar-mensaje-en-un-canal) | Mensajería | 8 | 2 | Comunicación central en tiempo real y multiinstancia |
| 16 | [Historial y reconexión](historias-usuario.md#hu-16-historial-y-reconexión) | Mensajería | 13 | 2 | Persistencia, paginación y recuperación sin pérdidas |
| 17 | [Unirse a canal de voz de servidor](historias-usuario.md#hu-17-unirse-a-canal-de-voz-de-servidor) | Canal de Voz | 11 | 2 | Riesgo técnico principal y comunicación de voz real |
| 18 | [Salir de canal de voz](historias-usuario.md#hu-18-salir-de-canal-de-voz) | Canal de Voz | 1 | 2 | Ciclo básico de una sesión de voz |
| 19 | [Silenciar micrófono propio](historias-usuario.md#hu-19-silenciar-micrófono-propio) | Canal de Voz | 1 | 2 | Control mínimo durante una sesión |
| 20 | [Ver participantes conectados](historias-usuario.md#hu-20-ver-participantes-conectados) | Canal de Voz | 3 | 2 | Presencia sincronizada en la sesión |
| 21 | [Crear rol](historias-usuario.md#hu-21-crear-rol) | Roles y Permisos | 3 | 2 | Base del modelo de autorización del servidor |
| 22 | [Editar permisos de un rol](historias-usuario.md#hu-22-editar-permisos-de-un-rol) | Roles y Permisos | 5 | 3 | Autorización efectiva y consistente |
| 23 | [Asignar rol a un miembro](historias-usuario.md#hu-23-asignar-rol-a-un-miembro) | Roles y Permisos | 3 | 2 | Aplicación del modelo de permisos |
| 24 | [Definir rol por defecto para nuevos miembros](historias-usuario.md#hu-24-definir-rol-por-defecto-para-nuevos-miembros) | Roles y Permisos | 2 | 3 | Permisos seguros desde el ingreso |
| 25 | [Banear miembro del servidor](historias-usuario.md#hu-25-banear-miembro-del-servidor) | Moderación | 3 | 3 | Prevención de reingreso de usuarios abusivos |
| 26 | [Revocar baneo](historias-usuario.md#hu-26-revocar-baneo) | Moderación | 2 | 3 | Reversibilidad de las decisiones de moderación |
| 27 | [Ver notificaciones no leídas](historias-usuario.md#hu-27-ver-notificaciones-no-leídas) | Notificaciones | 3 | 3 | Seguimiento de actividad relevante |
| 28 | [Marcar notificaciones como leídas](historias-usuario.md#hu-28-marcar-notificaciones-como-leídas) | Notificaciones | 1 | 3 | Gestión del estado de lectura |
| 29 | [Suspender usuario a nivel plataforma](historias-usuario.md#hu-29-suspender-usuario-a-nivel-plataforma) | Administración | 3 | 2 | Control global de abuso y revocación de sesiones |
| 30 | [Reactivar usuario suspendido](historias-usuario.md#hu-30-reactivar-usuario-suspendido) | Administración | 1 | 2 | Reversibilidad de la suspensión |
| 31 | [Ver listado de usuarios con filtros](historias-usuario.md#hu-31-ver-listado-de-usuarios-con-filtros) | Administración | 2 | 2 | Entrada operativa para gestionar cuentas |
| 32 | [Ver listado de servidores de la plataforma](historias-usuario.md#hu-32-ver-listado-de-servidores-de-la-plataforma) | Administración | 2 | 3 | Visibilidad operativa del backoffice |

**Puntaje obligatorio completado: 104 / 104 pts.**

---

## Historias optativas — 52 / 229 pts

El puntaje optativo amplía las capacidades de la plataforma. La cantidad de puntos a implementar depende del tamaño del grupo (ver tabla de mínimos más abajo).

| # | Historia | Épica | Puntos | Checkpoint | Dependencia / Requisito previo |
| -: | --- | --- | -: | :-: | --- |
| 33 | [Login con proveedor federado](historias-usuario.md#hu-33-login-con-proveedor-federado) | Usuarios | 5 | 2 | Login con email y contraseña |
| 34 | [Registro con PIN](historias-usuario.md#hu-34-registro-con-pin) | Usuarios | 2 | - | Registro de usuarios y aplicación mobile |
| 35 | [Autenticación de dos factores (2FA)](historias-usuario.md#hu-35-autenticación-de-dos-factores-2fa) | Usuarios | 5 | - | Login con email y contraseña |
| 36 | [Visualización de perfil público](historias-usuario.md#hu-36-visualización-de-perfil-público) | Perfil | 2 | 3 | Visualización de perfil propio |
| 37 | [Estado de actividad](historias-usuario.md#hu-37-estado-de-actividad) | Perfil | 5 | 3 | Mensajería en tiempo real y sesiones autenticadas |
| 38 | [Estado personalizado](historias-usuario.md#hu-38-estado-personalizado) | Perfil | 2 | - | Edición de perfil |
| 39 | [Administrar configuración del servidor](historias-usuario.md#hu-39-administrar-configuración-del-servidor) | Servidores | 3 | 3 | Crear servidor |
| 40 | [Eliminar servidor](historias-usuario.md#hu-40-eliminar-servidor) | Servidores | 5 | 2 | Administrar configuración del servidor |
| 41 | [Reordenar canales](historias-usuario.md#hu-41-reordenar-canales) | Canales | 2 | 3 | Organizar canales en categorías |
| 42 | [Enviar mensaje directo (DM)](historias-usuario.md#hu-42-enviar-mensaje-directo-dm) | Mensajería | 8 | 3 | Bloquear y desbloquear usuarios; sesiones e historial de mensajería |
| 43 | [Bloquear y desbloquear usuarios](historias-usuario.md#hu-43-bloquear-y-desbloquear-usuarios) | Mensajería | 3 | 3 | Usuarios; complementa mensajes directos |
| 44 | [Editar mensaje](historias-usuario.md#hu-44-editar-mensaje) | Mensajería | 3 | 2 | Enviar mensaje en un canal o DM |
| 45 | [Eliminar mensaje](historias-usuario.md#hu-45-eliminar-mensaje) | Mensajería | 3 | 2 | Enviar mensaje en un canal o DM |
| 46 | [Menciones](historias-usuario.md#hu-46-menciones) | Mensajería | 5 | - | Mensajería, roles y notificaciones |
| 47 | [Adjuntar archivos en mensajes](historias-usuario.md#hu-47-adjuntar-archivos-en-mensajes) | Mensajería | 5 | - | Mensajería y almacenamiento externo de objetos |
| 48 | [Reacciones con emoji](historias-usuario.md#hu-48-reacciones-con-emoji) | Mensajería | 3 | - | Enviar mensaje en un canal |
| 49 | [Buscar mensajes](historias-usuario.md#hu-49-buscar-mensajes) | Mensajería | 5 | - | Historial y reconexión; autorización por canal o DM |
| 50 | [Iniciar y recibir llamada de voz privada](historias-usuario.md#hu-50-iniciar-y-recibir-llamada-de-voz-privada) | Canal de Voz | 13 | - | Mensajes directos y flujo de voz operativo |
| 51 | [Indicador de quién está hablando](historias-usuario.md#hu-51-indicador-de-quién-está-hablando) | Canal de Voz | 3 | - | Unirse a canal de voz de servidor |
| 52 | [Silenciar a otro participante localmente](historias-usuario.md#hu-52-silenciar-a-otro-participante-localmente) | Canal de Voz | 2 | - | Unirse a canal de voz de servidor |
| 53 | [Compartir pantalla](historias-usuario.md#hu-53-compartir-pantalla) | Canal de Voz | 8 | - | Flujo de voz operativo |
| 54 | [Video en llamada](historias-usuario.md#hu-54-video-en-llamada) | Canal de Voz | 8 | - | Flujo de voz operativo |
| 55 | [Eliminar rol](historias-usuario.md#hu-55-eliminar-rol) | Roles y Permisos | 3 | 3 | Crear, asignar y editar roles |
| 56 | [Reordenar jerarquía de roles](historias-usuario.md#hu-56-reordenar-jerarquía-de-roles) | Roles y Permisos | 3 | 3 | Crear rol y asignar rol a un miembro |
| 57 | [Sobrescribir permisos de un rol en un canal específico](historias-usuario.md#hu-57-sobrescribir-permisos-de-un-rol-en-un-canal-específico) | Roles y Permisos | 5 | 3 | Editar permisos de un rol y gestión de canales |
| 58 | [Ver miembros por rol](historias-usuario.md#hu-58-ver-miembros-por-rol) | Roles y Permisos | 2 | 3 | Asignar rol a un miembro |
| 59 | [Expulsar miembro del servidor](historias-usuario.md#hu-59-expulsar-miembro-del-servidor) | Moderación | 3 | - | Roles y membresía del servidor |
| 60 | [Silenciar temporalmente a un miembro](historias-usuario.md#hu-60-silenciar-temporalmente-a-un-miembro) | Moderación | 5 | - | Roles, mensajería y voz |
| 61 | [Ver registro de auditoría de moderación](historias-usuario.md#hu-61-ver-registro-de-auditoría-de-moderación) | Moderación | 3 | - | Acciones de moderación |
| 62 | [Reportar mensaje o usuario](historias-usuario.md#hu-62-reportar-mensaje-o-usuario) | Moderación | 5 | - | Mensajería y backoffice |
| 63 | [Filtro automático de palabras prohibidas](historias-usuario.md#hu-63-filtro-automático-de-palabras-prohibidas) | Moderación | 3 | - | Enviar mensaje en un canal |
| 64 | [Silenciar notificaciones de un canal o servidor](historias-usuario.md#hu-64-silenciar-notificaciones-de-un-canal-o-servidor) | Notificaciones | 3 | - | Notificaciones obligatorias |
| 65 | [Configurar preferencias de notificación](historias-usuario.md#hu-65-configurar-preferencias-de-notificación) | Notificaciones | 3 | - | Notificaciones obligatorias |
| 66 | [Notificaciones push](historias-usuario.md#hu-66-notificaciones-push) | Notificaciones | 5 | - | Configurar preferencias y aplicación mobile |
| 67 | [Centro de notificaciones con historial](historias-usuario.md#hu-67-centro-de-notificaciones-con-historial) | Notificaciones | 5 | - | Notificaciones obligatorias |
| 68 | [Eliminar servidor desde el backoffice](historias-usuario.md#hu-68-eliminar-servidor-desde-el-backoffice) | Administración | 5 | - | Listado de servidores y eliminación en cascada |
| 69 | [Suspender servidor completo](historias-usuario.md#hu-69-suspender-servidor-completo) | Administración | 5 | - | Listado de servidores de la plataforma |
| 70 | [Ver métricas de actividad de un servidor](historias-usuario.md#hu-70-ver-métricas-de-actividad-de-un-servidor) | Métricas | 5 | - | Eventos de membresía y mensajería |
| 71 | [Ver métricas globales de la plataforma](historias-usuario.md#hu-71-ver-métricas-globales-de-la-plataforma) | Métricas | 5 | - | Eventos globales y acceso de staff |
| 72 | [Gráfico de crecimiento de miembros](historias-usuario.md#hu-72-gráfico-de-crecimiento-de-miembros) | Métricas | 3 | - | Métricas de actividad de un servidor |
| 73 | [Exportar métricas a CSV](historias-usuario.md#hu-73-exportar-métricas-a-csv) | Métricas | 3 | - | Métricas de servidor o globales |
| 74 | [Estado de la plataforma e incidentes](historias-usuario.md#hu-74-estado-de-la-plataforma-e-incidentes) | Métricas | 5 | - | Backoffice y health checks de los RNF |
| 75 | [Gestionar emojis personalizados del servidor](historias-usuario.md#hu-75-gestionar-emojis-personalizados-del-servidor) | Monetización | 5 | - | Administración del servidor y almacenamiento de objetos |
| 76 | [Suscribirse a Plan Premium](historias-usuario.md#hu-76-suscribirse-a-plan-premium) | Monetización | 13 | - | Adjuntos, perfil, reacciones, emojis y pagos externos |
| 77 | [Cancelar suscripción Premium](historias-usuario.md#hu-77-cancelar-suscripción-premium) | Monetización | 3 | - | Suscribirse a Plan Premium |
| 78 | [Comprar puntos](historias-usuario.md#hu-78-comprar-puntos) | Monetización | 8 | - | Integración con pagos externos |
| 79 | [Usar puntos para boostear un servidor](historias-usuario.md#hu-79-usar-puntos-para-boostear-un-servidor) | Monetización | 13 | - | Comprar puntos y membresía de servidor |
| 80 | [Ver beneficios de servidor boosteado](historias-usuario.md#hu-80-ver-beneficios-de-servidor-boosteado) | Monetización | 3 | - | Usar puntos para boostear y gestionar emojis |
| 81 | [Ver expediente de investigación de usuario o servidor](historias-usuario.md#hu-81-ver-expediente-de-investigación-de-usuario-o-servidor) | Administración | 5 | - | Reportar mensaje o usuario |

**Puntaje optativo completado: 52 pts** (de 229 pts disponibles en el catálogo).

---

## Resumen de avance y puntaje

**Total implementado de punta a punta: 156 pts** (104 obligatorios + 52 optativos).

## Mínimo de puntos por tamaño de equipo

| Integrantes | Mínimo optativas | % del pool optativo | Total mínimo |
| :---------: | :--------------: | :-----------------: | :----------: |
| 4           | 48 pts           | 21,0%               | 152 pts      |
| 5           | 80 pts           | 34,9%               | 184 pts      |
| 6           | 112 pts          | 48,9%               | 216 pts      |

El total mínimo considera los 104 puntos obligatorios. Los RNF completos, la aplicación mobile, el cliente web de usuario final y el backoffice también son obligatorios y no otorgan puntos adicionales.

---

## Notas

Pendientes técnicos y deuda asumida que siguen abiertos, para poder retomarlos como tarea de refactor. Lo ya implementado se documenta en las `specs/` de cada servicio y en los PRs; acá va solo lo que quedó sin resolver.

### Seguridad

- **HU-36 — `WS /ws/presence`:** la presencia quedó como **suscripción por usuario** con token bucket (1 comando/s, ráfaga 3, agregado por usuario y retenido entre reconexiones) porque el fan-out original entregaba la presencia de toda la plataforma a cualquier sesión; el riesgo residual es que la presencia es un oráculo de conexión y no de existencia, y se cierra con la misma validación de servidor compartido (ADR-008).

### Escalabilidad multi-réplica

- **HU-37 — Hub de presencia en memoria:** el hub y el token bucket de `profile` viven en memoria, así que con más de una réplica el techo se multiplica y el fan-out no cruza réplicas; mudarlos a Redis va junto con la validación de servidor compartido de la HU-36.

### Funcionalidad pendiente

- **HU-27 (CA 3) — Indicador destacado por menciones:** queda pendiente porque depende de la optativa HU-46 (menciones), fuera de alcance.
- **HU-41 — Auto-scroll durante el arrastre:** el auto-scroll de la lista mientras se arrastra un canal quedó fuera de alcance.

Los pendientes de infraestructura y CI que no son deuda de código se siguen en [mejoras-ci-cd.md](mejoras-ci-cd.md).
