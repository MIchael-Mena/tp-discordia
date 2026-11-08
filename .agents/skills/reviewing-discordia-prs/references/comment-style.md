# Estilo de los comentarios

El equipo pidió, de forma explícita: **español**, con prioridades claras, sin referencias al backlog local y sin proponer tickets. Estas reglas salen de esas correcciones.

---

## Reglas duras

1. **Español (es-AR).** "Podés", "fijate", "conviene". Tuteo, no usted.
2. **Nunca** menciones `Backlog.json`, `TSK-*` ni "el backlog": es seguimiento local del usuario, no del equipo.
3. **Nunca** propongas "crear un ticket". Si algo queda fuera del PR, decí "como recomendación para un PR aparte" o "deuda con impacto: …".
4. **Referenciá con `archivo:línea`** en el texto del comentario (los inline ya están anclados, pero el body no).
5. **Un comentario = un tema.** No mezcles un bug con un nit.
6. **Destacá lo que está bien** cuando haya aciertos concretos verificados; no inventes una cantidad fija.
7. Si una decisión es defendible pero el motivo escrito es falso, **separalos**:
   > "La decisión v1 sigue siendo defendible, **pero por otro motivo**: …"
8. Cuando el autor tiene que elegir, **ofrecé opciones numeradas** y la consecuencia de cada una:
   > "Opción A (respeta el contrato): … Opción B: …"
   Si la decisión es binaria y urgente, cerrá con **una** pregunta concreta.

---

## Body de la review

````markdown
## Revisión de `<feature-slug>`

Revisé <qué miraste> y <qué corriste>. **<Resultado verificable: tests, cobertura, tsc>**.

**Lo que está bien y no hay que tocar:** <aciertos concretos verificados con su porqué, si los hay>.

El orden de abajo es el de importancia.

### Prioridad 1 — antes del merge

1. **<Título en una línea, con la consecuencia.>** <2-4 líneas de explicación con la evidencia; qué pasa en producción si entra así.>

### Prioridad 2 — conviene en este PR

2. **<…>**

### Prioridad 3 — menores

5. **<…>**

### Nits

<una línea con los detalles de forma, diciendo que están inline>.

### Nota de cadena (no es de este PR)

<dependencias con otros PRs, o efectos que se ven recién cuando se mergea el resto>.
````

Si el PR no se puede mergear por conflictos, eso es P1 **en el body** (no hay línea donde anclarlo).

---

## Comentarios inline

Encabezado con etiqueta descriptiva entre corchetes; después evidencia; después fix sugerido (o resolución aplicada si se commiteó en la rama).

**Etiquetas recomendadas:**
- `[Prioridad 1 · bloqueante]` o `[Bloqueante · <categoría>]`: para fallas críticas antes del merge.
- **Etiquetas semánticas por categoría** para hallazgos convenientes (evitar `[Prioridad 2]` genérico cuando no hay P1s o resulta poco informativo):
  - `[Bugfix de UI / Paginación]`
  - `[Alineación con dominio]`
  - `[Cobertura de tests]`
  - `[Robustez / Fallback]`
  - `[Contrato API]`
- `[Nit · <tema>]` o `[Nit]`: detalles menores de estilo, nombres o código muerto.

````markdown
**[<Etiqueta semántica o Bloqueante>] <Título: qué se rompe o mejora, en una línea.>**

<Qué pasa, con la línea concreta.>

```<lenguaje>
<el fragmento mínimo que prueba el punto>
```

<Consecuencia real, no teórica.>

**Fix sugerido:** <una o dos líneas de código, o la opción A/B.>
*(Si el usuario ordenó aplicar la corrección directamente en el PR: "Se aplica el fix/test directamente en esta rama (commit `<hash>`).")*
````

Para un nit alcanza con una línea:

````markdown
**[Nit] <afirmación>.**
````

### Plantillas por tipo de hallazgo

**Bug con repro** — incluí el experimento y el resultado:
> Medí con `request_timeout_seconds=1` y una tarea de 2 s: la llamada **bloquea 2.00 s** y recién ahí levanta. El timeout no acota nada.

**Decisión mal justificada**:
> La frase "membership and roles do not exist yet" no es cierta en `develop`: `server_members` y `ServerMemberRepository.existsByServerIdAndUserId` existen desde `c0c1a3e` y ya se aplicaban en `LeaveServer`/`InitiateOwnershipTransfer`. La política v1 sigue siendo defendible, pero por **otro** motivo: …

**Doc desalineada**:
> T015 corrigió `README.md` y `contracts/`, pero `data-model.md:34` quedó con "<texto viejo>". Es el archivo que alguien va a leer para entender el passthrough.

**Contrato vs código**:
> El contrato dice "<cita>"; el camino real es `<cadena de llamadas>` y termina en `403`. Hoy el código documenta un estado que el cliente nunca va a ver. Elegí uno: A (respetar el contrato: …) o B (cambiar el contrato y borrar la rama muerta).

**Nit de estilo**:
> **[Nit]** `org.hamcrest.Matchers.hasItems(...)` con nombre completo; el resto del archivo usa imports estáticos.

---

## Cómo NO escribir

| ❌ | ✅ |
|---|---|
| "Esto está mal." | "Devuelve `403` donde el contrato dice `404`; el consumidor lo reporta como 'servicio no disponible'." |
| "Habría que agregar tests." | "Falta el test de micrófono denegado, que es el camino más común: hoy nada cubre el `catch`." |
| "Esto podría fallar en producción." | "Con un volumen existente, `db/init_database.sql` no se ejecuta ⇒ 500 en los endpoints de canales." |
| "Deberías crear un ticket." | "Como recomendación para un PR aparte: …" |
| "Según el backlog…" | (no aplica: el backlog no se menciona). |
| "Creo que `shutdown` espera." | "`shutdown(wait=True)` espera; lo medí: 2.00 s." |
| "[Prioridad 2] ..." (cuando no hay P1s) | "[Bugfix de UI / Paginación] ..." o "[Alineación con dominio] ..." |

**Falsos positivos a evitar** (ya pasaron):

- Afirmar que falta un `try/catch` de recurso sin revisar si el `catch` de arriba lo tiene.
- Afirmar que una API no existe sin `git grep` en `origin/develop`.
- Afirmar que el autor no corrió los tests cuando el CI está verde: lo que falta es *ese* caso, no la corrida.
- Sugerir que `onContextMenu` no funciona sin verificar que `react-native-web` lo reenvía (está en `clickProps`).
- Proponer un refactor grande dentro de un PR aditivo: registralo como divergencia y proponé el módulo común aparte.

---

## Payload de la API

```js
{
  body: reviewBody,          // markdown del body
  event: "COMMENT",          // nunca APPROVE ni REQUEST_CHANGES salvo pedido explícito
  comments: [
    { path: "src/.../File.ts", line: 103, side: "RIGHT", body: inlineBody }
  ]
}
```

- Usá `side: "RIGHT"` para el lado nuevo y `side: "LEFT"` para una línea eliminada del lado anterior. Confirmá que la línea y el lado pertenezcan a un hunk válido del diff vigente; si no existe un anclaje válido, describí el hallazgo en el body con su ubicación.
- No pongas `comments` con `position`: usá `line` + `side`.
- Escribí el JSON con un script de Node (`fs.writeFileSync`) o Python (`json.dump` con `encoding='utf-8'`). **Nunca** uses `Out-File -Encoding utf8` de PowerShell 5.1 porque antepone un BOM UTF-8 (`\xef\xbb\xbf`) y `gh api --input` responde `Problems parsing JSON (HTTP 400)`.
- Si aplicaste correcciones en la misma rama antes o junto con la publicación de los comentarios, aclará explícitamente en el inline qué commit resuelve la observación.
- Después de postear, identificá la review creada, listá sus comentarios y confirmá **cuántos** y en **qué línea y lado** quedaron. Si falta uno, informalo y consultá antes de publicar un comentario adicional.

---

## Check final antes de publicar

- [ ] Cada inline usa la línea y el lado correctos de un hunk del diff vigente; los hallazgos sin anclaje válido están en el body.
- [ ] El body no menciona backlog, `TSK-`, tickets ni rutas locales del usuario.
- [ ] Cada P1 explica **qué se rompe** y por qué no puede esperar.
- [ ] Los hallazgos convenientes usan etiquetas semánticas descriptivas en lugar de un `[Prioridad 2]` ambiguo.
- [ ] Si se commiteó un fix directamente en la rama, el comentario inline aclara el commit de resolución.
- [ ] Cada hallazgo tiene evidencia (grep, test, medición o línea de código).
- [ ] Los aciertos mencionados están verificados, si los hay.
- [ ] El orden de prioridad está explícito en el body y en cada inline.
