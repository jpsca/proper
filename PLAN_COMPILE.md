# Plan: `proper jx compile` v1 (lowering de la app)

> **Actualización 2026-09-28:** las fases 3 y 4 (`Catalog.freeze`, `emit`/`load`,
> `proper jx compile`) ya no existen: Proper cambió el Jx vendorizado por minijx,
> que compila las vistas a módulos Python. `lower()` las compila al arrancar, en
> todos los modos. Las fases 1 y 2 (dispatch y rutas) siguen vigentes.

Estado: las cuatro fases implementadas (2026-09-26). `src/proper/compile/`
(`dispatch.py`, `routes.py`, `views.py`), `src/proper/jx/catalog.py`
(`freeze`) y `src/proper/jx/emit.py` (`emit`/`load`). `proper jx compile`
escribe las vistas; `App.lower()` (desde `startup()` y `proper run`) las
carga si están al día. No hay manifest: cada módulo lleva el mtime de su
fuente y la huella del entorno. Fecha del plan: 2026-09-26.

## Idea

Tomar de Roundhouse una sola cosa: **toda decisión cuya respuesta no puede
cambiar entre requests se toma una vez, no en cada request**. Roundhouse mide
~10x en el mismo intérprete solo con eso, antes de cambiar de lenguaje.

Proper hoy ya cachea algunas de esas decisiones (rutas estáticas, callbacks
por clase, scopes por modelo). Lo que falta es hacerlo de forma sistemática,
con una representación intermedia explícita, y con la opción de emitirla como
módulo Python para que `proper run` la cargue sin recalcular nada.

No es un compilador a nativo. No toca Peewee ni Jinja como librerías. Es la
etapa *lower* de Roundhouse aplicada a una app Proper, con Python como único
target.

## Supuestos y decisiones a confirmar

1. **Lowering en boot, emisión opcional.** El pass de lowering corre siempre
   al arrancar la app (cuesta milisegundos, nada queda obsoleto). El comando
   `proper jx compile` escribe el resultado a disco y `proper run` lo carga si
   la huella coincide. En v1 el archivo emitido es obligatorio solo para las
   vistas, que es donde compilar cuesta de verdad y donde la forma emitida
   (Python plano) abre la puerta a mypyc más adelante.
   Alternativa: emitir siempre y hacer que `proper run` falle sin compilar.
   Más parecido a Roundhouse pero agrega un paso de build y un modo de fallo
   nuevo. No la recomiendo para v1.
2. **Las vistas, solo fuera de DEBUG.** El lowering de dispatch y de rutas
   no decide nada que la app pueda cambiar en runtime, así que corre en
   todos los modos (y en DEBUG un callback mal escrito falla al arrancar).
   Las vistas no: en DEBUG el auto_reload de Jx sigue activo y no se
   congelan ni se cargan emitidas. (Cambiado 2026-09-26; antes todo el
   lowering se saltaba en DEBUG.)
3. **Sin cambios de API pública.** Una app existente compila y corre sin
   modificar código. Lo que no se puede lowerear cae al camino dinámico
   actual con un warning, nunca a un error (misma regla que Roundhouse: el
   analizador nunca falla).
4. **Jx vive en Proper.** Jx 0.16.0 está vendorizado en `src/proper/jx/`
   (con sus tests en `tests/jx/`) desde 2026-09-26. Las fases 3 y 4, el
   modo "congelado" del catálogo y el emisor de fuente Python, se hacen
   ahí directamente, sin depender de una release de Jx.

## Qué se decide hoy por request

Diagnóstico sobre el código actual, en orden de costo estimado. Los números
de referencia son los del plan de rendimiento: pipeline ~14 us/request,
render Jx ~28% del tiempo de `fortunes`, generación de SQL ~50% del tiempo
de una query.

| # | Dónde | Qué se recalcula | Podría ser |
|---|---|---|---|
| 1 | `controller.py:_call` + `template_resolver.py` | `_prefixes()` recorre el MRO, `mimetypes.guess_extension` por cada mime del Accept, `catalog.has` por candidato | tabla `(clase, acción, formato) -> nombre de vista` |
| 2 | `controller.py:_dispatch` | `_should_run_callback` con `make_list` x2, `getattr(self, cb["do"])`, `make_list` sobre el resultado, `logger.debug` por callback | tupla de nombres de métodos ya filtrados por acción |
| 3 | `jx/catalog.py:render` | lock, `get_component_data`, construcción de un `Component` por render y por hijo, `_prepare_globals` | componentes precompilados y prearmados; render directo |
| 4 | `router.py:match` | rutas dinámicas: un `re.match` de host y otro de path por ruta, en orden, hasta acertar | una regex combinada por método, o un trie por primer segmento |
| 5 | `models/scopes.py` | `ScopedSelect.__getattribute__` envuelve cada método de cada query; `sql()` recompila la misma query cada vez | fuera de v1, ver "Fuera de alcance" |

## Diseño

```
app (clases ya importadas)
   │
   ▼  lower()            src/proper/compile/ (un módulo por pase: dispatch.py, ...)
   AppIR                 dataclasses serializables: rutas, dispatch, vistas
   │
   ├─▶ install(app)      la app usa las tablas en memoria (siempre)
   │
   └─▶ emit(path)        src/proper/compile/emit.py -> <app>/_compiled/
         routes.py, dispatch.py, views/*.py, manifest.json
                         ▲
proper run ──── load() ──┘  si manifest.hash == hash(fuentes); si no, lower()
```

`AppIR` es la única frontera. Los pases de lowering la producen, `install`
y `emit` la consumen. Cada pase es una función pura `App -> parte de AppIR`
con test propio, y una lista ordenada declara el orden (como
`POST_ANALYZE_PASS_ORDER` en Roundhouse).

La huella (`manifest.json`) es un hash del contenido de `controllers/`,
`views/`, `router.py` y `config/`. Si no coincide, `proper run` avisa y
lowerea en memoria. Nunca sirve un compilado viejo en silencio.

## Fases

Cada fase se mide sola con `~/Code/proper-bench/run.py` y `profile.py`
antes de pasar a la siguiente. Si una fase no mueve la aguja, se
documenta y se elimina.

### Fase 0. Armazón y medición

- `src/proper/compile/` con `AppIR`, `lower()`, `install()`, `emit()`,
  `load()` vacíos pero cableados.
- Comando `proper jx compile` en `cli/app_cli.py` que corre `lower()` + `emit()`
  y escribe el manifest.
- `proper run` llama a `load()` o `lower()` según el manifest, solo si no
  es DEBUG. Config `COMPILED_PATH` (default `<app>/_compiled`).
- Baseline guardado: `profile.py` en `plaintext`, `json` y `fortunes` sobre
  la app de bench, más `run.py` completo.
- Entregable: nada cambia de rendimiento. Todos los tests pasan.

### Fase 1. Dispatch y resolución de vista (hecha)

- Pase `lower_dispatch`: para cada controlador registrado en el router y
  cada acción enrutada, produce `(before: tuple[str], after: tuple[str])`
  ya filtradas por `only`/`exclude` y aplanadas con `make_list`. Los
  nombres se validan en lowering: un `do` que no existe en la clase es un
  error en `proper jx compile`, no un `AttributeError` en producción.
- Pase `lower_views`: para cada `(controlador, acción)` y cada formato
  registrado en `mimetypes` que tenga una vista en el catálogo, el nombre
  resuelto. Se precalcula `_prefixes()` una vez por clase. En runtime queda
  un `dict.get((cls, action, fmt))` y el fallback dinámico solo si el Accept
  trae un mime no visto en lowering.
- `Controller._dispatch` y `_call` consultan las tablas si `install()` corrió.
  El `logger.debug` por callback pasa a estar detrás de un `if debug` que
  se resuelve una vez por clase.
- Criterio: pipeline en `plaintext` baja de forma medible (objetivo
  14 -> 11 us en proceso). Tests de `tests/controller/` en ambos modos.

**Resultado (2026-09-26).** Implementado en `src/proper/compile/dispatch.py`
como un `DispatchPlan` por `(clase, acción)`, construido en el primer uso y
prellenado por `lower(app)`. Diferencias respecto al plan:

- Hay un solo camino, no dos: `Controller` usa siempre el plan; en DEBUG
  solo se desactiva el memo de vistas (el catálogo puede cambiar).
- La vista no se precalcula por formato en lowering. Se memoiza por tupla
  de formatos del `Accept` (acotado a 64 por plan) usando el mismo
  `catalog.has` de siempre; da el mismo resultado sin depender de
  enumerar formatos. Las extensiones de cada mime se cachean en
  `template_resolver.formats_for`.
- La validación corre en `App.lower()`, llamado desde `startup()` (RSGI) y
  desde `proper run` (WSGI) fuera de DEBUG. `proper jx compile` no existe aún.
- El criterio de `plaintext` no aplica: la app de bench no tiene callbacks
  ni vista inferida en esa ruta y no cambia (13.7 us antes y después).
  Medido en cambio con un controlador típico (4 `before`, 1 `after`, vista
  inferida, `Accept` de navegador), en proceso, 3.14t, mejor de 5:

  | | us/request |
  |---|--:|
  | antes | 46.8 |
  | después | 39.5 |

  Es un 15% en el request completo de ese controlador. Los tests de
  `tests/compile/` sirven las mismas rutas en modo normal y DEBUG y
  comparan las respuestas.

### Fase 2. Router (hecha)

- Pase `lower_routes`: rutas estáticas quedan igual (ya es un `dict`). Las
  dinámicas de cada método se combinan en una única regex con grupos
  nombrados por índice de ruta, preservando el orden de registro. El host
  se incluye en la misma regex solo para las rutas que lo restringen.
- `url_for` inverso: tabla `nombre -> (RouteTemplate, placeholders)` sin
  recorrer `routes`.
- Criterio: `match` en una app con ~50 rutas dinámicas es O(1 regex) en
  vez de O(n). Se mide con una app sintética en `tests/router/` porque la
  app de bench tiene pocas rutas dinámicas. Detección de 405 conserva el
  mismo comportamiento (test existente).

**Resultado (2026-09-26).** Implementado en `src/proper/compile/routes.py`.
El router construye una `RouteTable` en el primer `match` después del
último `add_route` (o en `router.lower()`, que `App.lower()` llama).
Diferencias respecto al plan:

- Las rutas con host no entran en la regex combinada: quedan como
  entradas individuales en su posición (`Hosted`). Meter el host en la
  misma regex obligaba a un separador que los formatos de placeholder
  podían cruzar. Son raras y el orden de prioridad se conserva exacto.
- Además de la regex combinada (`Combined`), las rutas consecutivas que
  empiezan por un segmento literal se indexan por ese segmento
  (`Bucketed`): un `dict.get` elige la única regex que puede coincidir.
  Es el caso de casi todas las rutas de una app (`/posts/:id`). Las que
  empiezan por placeholder siguen en una `Combined` propia, en su lugar.
- `url_for` ya usaba un `dict` por nombre. Lo que se precalcula ahora por
  ruta es el `RouteTemplate`, la regex compilada de cada placeholder y el
  prefijo del controlador (`Route.controller_prefix`).
- Medido en proceso, 3.14t, mejor de 5, con 50 recursos (100 rutas
  dinámicas):

  | | antes | después |
  |---|--:|--:|
  | `match` última de 50 | 5.68 us | 0.90 us |
  | `match` primera de 50 | 0.74 us | 0.88 us |
  | `url_for` | 2.57 us | 2.05 us |

  La primera ruta paga ~0.1 us más por la indirección; a partir de la
  segunda o tercera ya gana. Un test compara la tabla con el recorrido
  ruta por ruta sobre un juego de rutas y paths.

### Fase 3. Vistas: catálogo congelado (hecha)

- `proper.jx`: `Catalog.freeze()` compila todos los componentes, guarda `Component`
  prearmados por `relpath` (imports, slots, css, js ya resueltos) y hace
  que `render` sea `self._frozen[relpath].render(**kw)` sin lock ni stat.
  `auto_reload=False` pasa a implicar `freeze()` al primer render.
- Proper: `install()` llama a `catalog.freeze()` en no-DEBUG.
- Criterio: `fortunes` sube (objetivo: la parte de render baja de 28% a
  ~15% del request). Tests de Jx en modo congelado.

**Resultado (2026-09-26).** El diagnóstico de esta fase se escribió sobre
Jx 0.13.0. La 0.16.0 vendorizada ya hace en `render` lo que la fase pedía
cuando `auto_reload` está apagado: sin lock, sin `stat`, una instancia de
`Component` por `relpath` y los hijos y assets cacheados. Perfilando
`/fortunes` con esa versión, el render es el 26% del request, pero cuatro
quintos de eso es Jinja ejecutando el cuerpo de la plantilla (el bucle,
26 escapes por página); la envoltura de Jx es ~5% del request. No hay 13
puntos que recuperar ahí; el criterio de esta fase ya estaba cumplido al
vendorizar.

Lo que faltaba era la compilación anticipada: cada plantilla se parseaba
y compilaba en su primer render. `Catalog.freeze()` compila todos los
componentes registrados, construye sus `Component`, resuelve los imports
y colecta los assets. `proper.compile.lower()` lo llama, así que
`App.lower()` (en `startup()` y en `proper run`, fuera de DEBUG) deja el
catálogo listo, y una plantilla rota o un import que no resuelve fallan
al arrancar y no en el primer request que los toca.

Medido en proceso, 3.14t, catálogo de 41 componentes:

| | |
|---|--:|
| primer render de una página, sin freeze | 0.93 ms |
| primer render de una página, con freeze | 0.017 ms |
| `freeze()` de los 41 componentes | 40 ms |
| render en régimen (igual antes y después) | 14 us |

### Fase 4. Vistas: emisión como Python (hecha)

- `proper.jx`: `Catalog.emit(path)` escribe cada componente como módulo Python
  usando `jinja_env.compile(source, raw=True)` (Jinja ya devuelve fuente
  Python), más un índice con metadatos (`required`, `optional`, imports,
  slots, assets). `Catalog.load(path)` reconstruye el catálogo congelado
  importando esos módulos, sin parsear ni compilar.
- Proper: `emit()` incluye `views/`, `load()` los usa.
- Criterio: arranque en producción no parsea ningún `.jx`. Rendimiento
  por request igual a fase 3 (esta fase compra tiempo de arranque y la
  forma emitida, no rps). Test de conformidad: misma salida HTML
  renderizando desde fuente y desde emitido, para todas las vistas de la
  app de bench y del blueprint.

**Resultado (2026-09-26).** Implementado en `src/proper/jx/emit.py` y
`src/proper/compile/views.py`. Diferencias respecto al plan:

- No hay índice aparte: cada módulo lleva un `JX_META` con sus
  metadatos, el mtime de su `.jx`, y la huella del entorno Jinja del
  catálogo (la misma que usa el bytecode cache). Los tipos de los props
  se escriben por nombre (solo pueden ser builtins) y los defaults con
  `repr`, verificado que se lee igual; si no, `EmitError`.
- Los módulos no se importan con `import`: el código generado por Jinja
  toma `environment` como argumento por defecto, así que se ejecutan con
  el mismo namespace que `Template.from_code`. El código se obtiene con
  `SourceFileLoader.get_code`, que usa `__pycache__`: la segunda carga
  es un `marshal`.
- `load` rechaza todo el conjunto (`EmittedOutOfDate`) si un módulo lo
  escribió otro entorno o si su fuente está en disco y cambió. Eso hace
  innecesario el manifest de la fase 0: `proper run` avisa y compila
  desde fuente.
- Los restos de la fase 0 quedaron aquí: config `COMPILED_PATH` (default
  `_compiled`, relativo a la carpeta que contiene el paquete de la app),
  comando `proper jx compile`, y `_compiled/` en el `.gitignore` del
  blueprint.
- Conformidad: los tests renderizan los mismos componentes desde fuente
  y desde emitido y comparan HTML y firmas; otro hace la ida y vuelta
  con las 38 vistas de `docs/views`. Las vistas del blueprint importan
  `layouts/base.jx`, que no existe hasta que se genera la app, así que
  no sirven como corpus.
- Medido en proceso, 3.14t, catálogo de 41 componentes:

  | | |
  |---|--:|
  | `freeze()` desde fuente | 37 ms |
  | `emit()` | 26 ms |
  | `load()` la primera vez (escribe `__pycache__`) | 20 ms |
  | `load()` siguientes | 1.5 ms |
  | render en régimen desde lo cargado | 14.7 us |

  Nota: el bytecode cache de Jinja que Jx ya traía (`bytecode_cache`)
  habría dado una parte de esto (la compilación de Jinja es 1.3 de los
  1.4 ms por componente) sin código nuevo, pero seguiría parseando cada
  `.jx` y necesitándolo en disco. La forma emitida es lo que deja las
  vistas como Python plano para lo que venga después.

## Verificación

Criterios de éxito de v1, todos medibles:

- La suite completa pasa con `COMPILED` activo y desactivado. Se agrega un
  fixture parametrizado en `tests/conftest.py` para correr los tests de
  controllers, router y vistas en ambos modos.
- Test de conformidad (el "oráculo" de Roundhouse a escala mínima): la app
  de bench y la app del blueprint sirven cada ruta GET en ambos modos y los
  cuerpos y headers son idénticos byte a byte.
- `proper jx compile` sobre una app con un `before` que apunta a un método
  inexistente falla con un mensaje que nombra la clase y el callback.
- `proper run` con un manifest desactualizado avisa y sirve igual.
- Rendimiento, medido en Hypercubo con `run.py` (3.14t, 1 proceso, misma
  configuración que el último baseline 115.5k / 109k / 35.0k rps):
  `plaintext` >= +15%, `fortunes` >= +15%, RSS sin subir. Si fase 1 y 3
  no dan eso juntas, se revisa el diagnóstico antes de seguir.

## Fuera de alcance en v1

- **SQL precompilado por query.** Es un cache en Peewee (o en
  `ProperModel.select`), no un lowering de la app. Se evalúa aparte una
  vez cerrado v1, sobre los datos del microbench de ORM.
- **`ScopedSelect.__getattribute__`.** Mismo motivo. Candidato a
  reemplazar por una subclase generada por modelo con los scopes como
  métodos reales; queda anotado para después.
- **Inferencia de tipos, targets no Python, mypyc.** La forma emitida de
  la fase 4 es el prerrequisito, pero nada de esto entra en v1.
- **Formularios y modelos.** Son declarativos y ya se resuelven en import.
  No hay decisión por request que lowerear.

## Riesgos

- **Dos caminos de ejecución.** Cada tabla precomputada deja un fallback
  dinámico. El test parametrizado en ambos modos existe para que el camino
  dinámico no se pudra. Si alguna tabla resulta cubrir el 100% de los casos,
  el fallback se elimina y queda un solo camino.
- **Jx vendorizado.** Ya no bloquea en releases, pero la copia diverge
  del repo de Jx desde el primer cambio. Si algo de las fases 3 y 4 vale
  para Jx en general, se porta a mano.
- **Ganancia menor a la esperada.** El pipeline ya está bastante recortado
  (13.9 us). Es posible que fase 1 y 2 den poco y la ganancia real esté
  en fase 3. Por eso se mide fase por fase y no se acumula trabajo sin
  evidencia.
