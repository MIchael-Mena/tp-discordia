# Estilo de los comentarios

El equipo pidió, de forma explícita: **español**, con prioridades claras, sin referencias al backlog local y sin proponer tickets. Estas reglas salen de esas correcciones.

---

## Reglas duras

1. **Español (es-AR).** "Podés", "fijate", "conviene". Tuteo, no usted.
2. **Nunca** menciones `Backlog.json`, `TSK-*` ni "el backlog": es seguimiento local del usuario, no del equipo.
3. **Nunca** propongas "crear un ticket". Si algo queda fuera del PR, decí "como recomendación para un PR aparte" o "deuda con impacto: …".
4. **Referenciá con `archivo:línea`** en el texto del comentario (los inline ya están anclados, pero el body no).
5. **Un comentario = un tema.** No mezcles un bug con un nit.
6. **Empezá por lo que está bien.** En el body, siempre.
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

**Lo que está bien y no hay que tocar:** <3-6 ítems concretos con su porqué>.

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

Encabezado con prioridad entre corchetes; después evidencia; después fix.

````markdown
**[Prioridad 1 · bloqueante] <Título: qué se rompe, en una línea.>**

<Qué pasa, con la línea concreta.>

```<lenguaje>
<el fragmento mínimo que prueba el punto>
```

<Consecuencia real, no teórica.>

**Fix:** <una o dos líneas de código, o la opción A/B.>
````

Para un nit alcanza con una línea:

````markdown
**[Nit] <afirmación>.**
````

### Plantillas por tipo de hallazgo

**Bug con repro** — incluí el experimento y el resultado:
> Medí con `request_timeout_seconds=1` y una tarea de 2 s: la llamada **bloquea 2.00 s** y recién ahí levanta. El timeout no acota nada.

**Decisión mal justificada**:
> La frase "membership and roles do not exist yet" no es cierta en `develop`: `server_members` y `ServerMemberRepository.existsByServerIdAndUserId` existen desde `c0c1a3e` y ya se aplican en `LeaveServer`/`InitiateOwnershipTransfer`. La política v1 sigue siendo defendible, pero por **otro** motivo: …

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

- `side: "RIGHT"` siempre (el comentario va sobre el estado nuevo).
- No pongas `comments` con `position`: usá `line` + `side`.
- Escribí el JSON con `fs.writeFileSync` de node. `Out-File -Encoding utf8` de PowerShell 5.1 agrega BOM y `gh api --input` responde `Problems parsing JSON`.
- Después de postear, listá los comentarios por API y confirmá **cuántos** y en **qué línea** quedaron. Si falta uno, publicalo suelto y avisá que no está dentro del bloque de la review.

---

## Check final antes de publicar

- [ ] Cada inline está en una línea **agregada** del diff.
- [ ] El body no menciona backlog, `TSK-`, tickets ni rutas locales del usuario.
- [ ] Cada P1 explica **qué se rompe** y por qué no puede esperar.
- [ ] Cada hallazgo tiene evidencia (grep, test, medición o línea de código).
- [ ] Hay una sección de "lo que está bien".
- [ ] El orden de prioridad está explícito en el body y en cada inline.
