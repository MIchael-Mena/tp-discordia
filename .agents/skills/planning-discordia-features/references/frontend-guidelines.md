# Guía de Frontend para Planes — `web-client` y `backoffice`

Aplicá esta guía al planificar cualquier cambio de UI en `web-client` o `backoffice` (Expo/React Native). El objetivo es **coherencia visual** entre módulos; la reutilización de componentes es una **sugerencia** que depende de si el caso encaja.

> [!IMPORTANT]
> **Alcance y excepción.** La guía rige siempre, salvo que el usuario pida **explícitamente** un refactor visual de una pantalla o módulo concreto. En ese caso, limitá el cambio a lo pedido y mantené el resto igual.

## 1. Principio: coherencia visual (obligatoria) vs. reutilización de componentes (sugerida)

- **Coherencia visual (obligatoria):** dos módulos con funcionalidades distintas deben verse como parte del mismo producto: mismos tokens del tema (colores semánticos, tipografía, espaciados, radios, iconografía), mismo patrón de encabezado, estados vacíos, carga y error, y mismo tono de textos.
- **Reutilización de componentes (sugerida):** reutilizá un componente compartido **solo si corresponde** a la función. Módulos con funcionalidades diferentes pueden necesitar componentes distintos; lo que no cambia es el resultado visual. No fuerces un componente donde no encaja, ni dupliques uno que ya resuelve exactamente el caso.
- **Prohibido** introducir paletas, tamaños o estilos aislados si existe un token del tema equivalente.

## 2. Investigación previa (antes de redactar la sección de UI del plan)

1. Identificá en el mismo cliente el **módulo hermano más parecido** (modal, pantalla, sección) y leelo: estructura, estilos y componentes que usa.
2. Revisá el tema del cliente (p. ej. `paperTheme` y los tokens que usan los módulos hermanos) y listá los tokens que va a usar el cambio.
3. Si el cambio toca ambos clientes, verificá cada uno por separado; no asumas que comparten componentes (cada uno tiene su propio `src/components`).
4. En el plan, registrá: qué módulo hermano se tomó como referencia, qué componentes se reutilizan y por qué, y cuáles no se reutilizan y por qué (si corresponde).

## 3. Catálogo de componentes sugeridos (`web-client`)

Referencia no exhaustiva; verificá que existan y su API actual antes de citarlos en el plan.

| Necesidad | Componente sugerido | Ubicación |
|---|---|---|
| Contenedor modal | `Popup` | `web-client/src/components/popups/Popup.tsx` |
| Encabezado de modal (`title`, `icon`, `onClose`) | `ModalHeader` | `web-client/src/components/popups/ModalHeader.tsx` |
| Filtros / pestañas | `SegmentedTabs` | `web-client/src/components/popups/SegmentedTabs.tsx` |
| Avatar / identidad | `MemberAvatar` | `web-client/src/components/popups/MemberAvatar.tsx` |
| Perfil público de un usuario | `PublicProfilePopup` | `web-client/src/components/popups/PublicProfilePopup.tsx` |
| Botones de acción | `ActionButton` | `web-client/src/components/ActionButton.tsx` (también en `backoffice/src/components/`) |
| Ejemplos de módulos hermanos | `MembersPopup`, `BannedMembersSection` | `web-client/src/components/popups/` |

En `backoffice`, buscá primero el equivalente local; si no existe, replicá la apariencia del módulo hermano, no la del `web-client`.

## 4. Navegación interna entre vistas

Si un modal permite abrir el detalle de una entidad (p. ej. el perfil de un usuario), seguí el patrón de `MembersPopup`: mostrar el detalle **dentro del mismo modal** con un `onBack` que vuelva al listado **conservando filtro, scroll y página cargada**. Declaralo en el plan junto con el estado que se preserva.

## 5. Puntos de entrada y cableado

Un componente nuevo no está completo hasta que está conectado. En el plan listá como `[MODIFY]` todos los archivos de la cadena:

- Tipo del modal/ruta (p. ej. `types.ts`) y su manejo (p. ej. `HomeModals.tsx`).
- Punto de disparo (`Sidebar.tsx`, `ServerMenu.tsx` u otro) con su callback `onShow<Feature>`.
- Archivo raíz que conecta el callback (p. ej. `src/app/pages/index.tsx`: `modals.openModal({ type: '<tipo>' })`).
- Reglas de visibilidad según permisos (*fail-closed*: si el flag falta, no se muestra).

## 6. Datos referenciados que pueden no estar disponibles

Cuando la UI muestra usuarios o entidades de registros históricos (auditoría, bans, mensajes antiguos), puede que ya no sean co-miembros y que la resolución de perfiles (`POST /profiles/public/batch`, restringido por co-membresía en `gateway`) no los devuelva. El plan debe definir uno de dos caminos, justificado:

1. **Backend:** ampliar la visibilidad (p. ej. regla de co-membresía para moderadores) con su contrato y tests; o
2. **Frontend:** *fallback* visual limpio y coherente con el resto de la UI (p. ej. `names[id] ?? id`, avatar con iniciales, `fallbackName` al abrir el perfil, sin errores visibles).

## 7. Filtros de UI vs. contrato del backend

Antes de fijar pestañas o filtros, contrastalos con los parámetros reales del endpoint:

- Si una pestaña agrupa varias acciones (p. ej. "Baneos" = `BAN` + `UNBAN`), el endpoint debe aceptar múltiples valores (lista separada por coma o `Set<Enum>`) o el plan debe justificar otra solución.
- Un valor inválido en el query param debe responder `400 Bad Request` controlado (no `404` ni `500`); el plan incluye el test correspondiente y el comportamiento del cliente.

## 8. Accesibilidad y testabilidad

`accessibilityLabel` y `testID` en controles y filas interactivas, siguiendo el estilo de los módulos hermanos; estados de carga, vacío y error visibles y consistentes.

## 9. Verificación obligatoria en clientes Expo

Comprobá los scripts del `package.json` y declará en el plan los comandos reales, incluyendo el chequeo de tipos:

```powershell
npx --prefix web-client tsc --noEmit
npx --prefix backoffice tsc --noEmit   # si se tocó backoffice
```

Además lint y tests (dirigidos durante la iteración, suite completa al cierre; ver `.agents/rules/env-cost.md`).

## 10. Checklist para la sección de UI del plan

- [ ] Módulo hermano de referencia identificado y leído.
- [ ] Tokens del tema listados; sin estilos aislados nuevos.
- [ ] Componentes reutilizados (con motivo) o no reutilizados (con motivo).
- [ ] Navegación interna con `onBack` y estado preservado, si aplica.
- [ ] Cadena de cableado completa hasta el archivo raíz (`index.tsx`).
- [ ] Fallback para entidades no disponibles, si aplica.
- [ ] Filtros alineados con el contrato del backend y caso 400 cubierto.
- [ ] `accessibilityLabel` / `testID` y estados de carga, vacío y error.
- [ ] `tsc --noEmit`, lint y tests declarados en el Plan de Verificación.
- [ ] Sin refactor visual fuera de lo pedido explícitamente.
