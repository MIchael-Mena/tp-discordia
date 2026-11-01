---
trigger: always_on
---

# Protocolo de Gestión del Backlog (`Backlog.json`)

**Nota de privacidad:** `Backlog.json` es de uso estrictamente local; los demás integrantes del equipo no tienen acceso a este archivo y contiene únicamente las tareas propias. **PROHIBIDO** mencionar `Backlog.json` o identificadores `TSK-*` en `specs/`, ADRs, código, commits o Pull Requests de repositorios compartidos.

El backlog se encuentra en **`Backlog.json`** en la raíz de `TP-Discordia/`. Todos los agentes deben leer y actualizar este archivo para reflejar su progreso cumpliendo estrictamente las siguientes reglas:

## 1. Uso Obligatorio de Identificadores (IDs)
- Cada tarea tiene un identificador único (ej. `TSK-001`, `TSK-042`).
- **Búsqueda y Actualización:** Utiliza siempre este ID como clave primaria para localizar el nodo JSON correcto antes de aplicar cualquier modificación. Nunca asumas la posición de la tarea en el array.
- **Inmutabilidad:** El ID de una tarea ya creada jamás debe ser modificado.

## 2. Vinculación de Pull Requests (PR) y Excepciones
- **Regla General:** Cada vez que finalices el trabajo de una tarea, debes crear un PR y enlazar la URL o el número (ej. `#42` o `server #36`) en el campo `pull_request` de la tarea.
- **Excepciones (Sin PR):** Si el trabajo no requiere un PR (por ejemplo, un push directo a `develop`/`main` acordado, o una investigación sin código), registrar la justificación en el campo `exception_note`. Ninguna tarea `completed` puede quedar sin `pull_request` ni `exception_note`.

## 3. Aislamiento de Pendientes Descubiertos
- Si durante la resolución de una tarea descubres trabajo adicional que excede su alcance original:
  - **NO** crees una tarea nueva en la raíz del backlog.
  - **SÍ** regístrala en `discovered_pending_tasks` de la tarea original.
- Esto garantiza trazabilidad y evita la saturación del backlog principal.
- Cada entrada de `discovered_pending_tasks` es **siempre un objeto**, nunca un string suelto, y declara tres campos:

  ```json
  {
    "description": "Qué falta y por qué importa, en una o dos frases.",
    "severity": "should",
    "resolved": false
  }
  ```

- `severity` es **obligatorio** y declara la urgencia real del pendiente. Solo existen tres valores válidos:

  | `severity`     | Significado             | Criterio de asignación |
  |----------------|-------------------------|------------------------|
  | `must`         | Hay que hacerlo sí o sí | Seguridad, pérdida de datos, requisito de una HU obligatoria o un contrato roto entre servicios. No puede quedar fuera del checkpoint. |
  | `should`       | Conviene hacerlo        | Deuda técnica real o funcionalidad incompleta de impacto acotado: se planifica, pero no bloquea. |
  | `nice-to-have` | Sugerencia              | Mejora opcional, caso borde o hipótesis a validar: se puede ignorar sin consecuencias. |

- `resolved` pasa a `true` cuando el trabajo se completa. Si el pendiente se promueve a una tarea del backlog (por ejemplo al abrir un checkpoint nuevo), además se agrega `migrated_to` con el ID de la tarea que lo absorbe:

  ```json
  { "description": "...", "severity": "must", "resolved": true, "migrated_to": "TSK-052" }
  ```

- Una tarea promovida desde un pendiente conserva la `severity` heredada (como campo propio de la tarea) y registra `origin` con los IDs de las tareas donde se descubrió el trabajo (`"origin": ["TSK-041"]`).

## 4. Integridad del Formato JSON
- Antes de modificar `Backlog.json`, realiza siempre una lectura completa, aplica tus cambios sobre el objeto parseado y sobrescribe el archivo serializando el objeto nuevamente.
- No uses reemplazos de texto plano para modificar el JSON.
- El campo `last_updated` (fecha ISO 8601) debe actualizarse en cada escritura.
- El archivo debe conservar formato JSON legible y uniforme: indentación de 2 espacios, un solo espacio después de cada `:`, arrays y objetos con saltos de línea, y un único salto de línea al final.
- Después de escribirlo, vuelve a parsearlo para comprobar que sigue siendo JSON válido y verifica que la cantidad de tareas y sus IDs no hayan cambiado accidentalmente.
- En VS Code, puedes aplicar el formato con `Shift + Alt + F` (**Format Document**). Desde Node.js, el equivalente es `JSON.stringify(data, null, 2) + "\n"`.

## 5. Estados válidos de una tarea
- `completed` — trabajo terminado, PR abierto/mergeado o excepción justificada.
- `in_progress` — trabajo activo actualmente.
- `pending` — en backlog, aún no iniciado.
- `blocked` — bloqueado por una dependencia externa.

## 6. Fecha de inicio (`start_date`)
- Toda tarea tiene el campo `start_date` (string ISO 8601, ej. `"2026-09-25"`).
- Se rellena con la fecha en que se comenzó a trabajar en la tarea.
- En tareas `pending` o `blocked` que aún no se iniciaron el valor es `null`.
- El estado de completitud se infiere del campo `status`; `start_date` no implica que la tarea esté terminada.
- **Nunca** se modifica una vez establecido.

## 7. Checkpoints (`checkpoint`)
- El proyecto tiene **4 checkpoints** a lo largo de ~4 meses de desarrollo (nomenclatura de la cátedra, equivalente a sprints).
- Cada tarea tiene el campo `checkpoint` (entero: `1`, `2`, `3` o `4`) que indica en qué checkpoint fue completada o está siendo trabajada.
- El objeto `checkpoints` en la raíz del JSON documenta el período y estado de cada checkpoint.
- **Regla de asignación:** al crear una tarea nueva, asignarle el checkpoint activo en ese momento. No reasignar checkpoints de tareas ya existentes, salvo el caso de una tarea `in_progress` que sigue activa al abrir un checkpoint nuevo (TSK-041 y TSK-042 pasaron del 2 al 3 por ese motivo).
- Checkpoints actuales:

| Checkpoint | Período                 | Estado      |
|------------|-------------------------|-------------|
| 1          | hasta 2026-09-24        | completed   |
| 2          | 2026-09-25 a 2026-10-27 | completed   |
| 3          | 2026-10-28 en adelante  | in_progress |
| 4          | por definir             | pending     |

- El backlog de los checkpoints 1 y 2 quedó archivado en **`Backlog-checkpoint-2.json`** (snapshot histórico, sin `discovered_pending_tasks`). Los pendientes sin resolver se promovieron a tareas del checkpoint 3 con su `severity` y su `origin`.

