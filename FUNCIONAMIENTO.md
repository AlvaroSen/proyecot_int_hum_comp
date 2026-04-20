# Funcionamiento del código — Portal de Retenciones

Este documento explica **cómo trabaja el código** a grosso modo: qué hace cada pieza, cómo se conectan entre sí y por qué están así. Complementa al `README.md` (que describe el proyecto y el plan de calidad). Aquí el foco es recorrer el flujo principal junto al código real del repositorio.

---

## 1. Vista general en una sola frase

> Un usuario crea una solicitud de retención, el sistema calcula automáticamente quién la atiende (ejecutivo + analista) usando una estrategia configurable, se guarda todo en la base junto con un registro de auditoría, y luego se puede seguir, cerrar y reportar desde la UI.

Los bloques protagonistas del código son tres:

| Archivo | Responsabilidad |
|---|---|
| `portal_retenciones/models.py` | Estructura de datos y reglas de integridad (qué se guarda y cuándo es válido). |
| `portal_retenciones/asignacion.py` | **Motor de asignación** (patrón Strategy). Decide a quién se asigna cada caso. |
| `portal_retenciones/views/pages.py` | Vistas HTML: orquesta formulario → asignación → guardado → redirect. |

El resto (`admin.py`, `api.py`, `auth.py`, `context_processors.py`, `decorators.py`) es configuración, endpoints auxiliares y control de acceso.

---

## 2. El flujo principal: "crear una solicitud"

Es el caso más representativo porque toca casi todo el sistema. La vista encargada es `nueva_solicitud_view` en `portal_retenciones/views/pages.py:66`.

### 2.1. Paso a paso

```python
# portal_retenciones/views/pages.py:66
def nueva_solicitud_view(request):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        circuitos_ids = request.POST.getlist('circuitos_seleccionados')
        ...
        tipo_caso_id = request.POST.get('tipo_caso')
```

**1) Recoger los datos del formulario**: cliente, circuitos marcados, tipo de caso y (opcionalmente) fecha de baja y observaciones.

**2) Validar reglas de negocio mínimas** antes de tocar la base (hay cliente, hay al menos un circuito, el tipo de caso existe y está activo, existe el estado inicial `NUEVO`, existe un `NivelAprobacion`).

**3) Calcular la renta total de los circuitos seleccionados** (esto alimentará el tope de carga de las estrategias):

```python
# pages.py:92
renta_total = (
    Circuito.objects.filter(id__in=circuitos_ids)
    .aggregate(total=Sum('renta_mensual'))['total']
    or 0
)
contexto = asig.SolicitudContexto(
    cliente_id=int(cliente_id),
    renta_total=renta_total,
    tipo_caso=tipo_caso_obj.codigo,
)
```

`SolicitudContexto` es un `dataclass` muy pequeño (`asignacion.py:68`) — el único dato que necesita el motor de asignación para decidir.

**4) Pedir al motor que asigne ejecutivo y analista**, por separado (cada rol puede tener una estrategia distinta):

```python
# pages.py:104
ejecutivo, detalle_ejec = asig.asignar(RolAsignacion.EJECUTIVO, contexto)
if not ejecutivo:
    raise ValidationError('No hay ejecutivos activos disponibles...')

analista, detalle_anal = asig.asignar(RolAsignacion.ANALISTA, contexto)
```

El motor devuelve dos cosas: la persona elegida y un `dict` con el detalle de la decisión (candidatos evaluados, razón, etc.). Ese `dict` se guarda tal cual en `RegistroAsignacion.detalle` como JSON, lo cual permite auditar después con trazabilidad total.

**5) Guardar todo dentro de una transacción** para que no queden estados inconsistentes si algo falla a medias:

```python
# pages.py:118
with transaction.atomic():
    solicitud = Solicitud.objects.create(
        cliente_id=cliente_id,
        ejecutivo=ejecutivo,
        analista=analista,
        estado_actual=estado_nuevo,
        ...
    )
    for cid in circuitos_ids:
        SolicitudCircuito.objects.create(solicitud=solicitud, circuito_id=cid)
    RegistroAsignacion.objects.create(
        solicitud=solicitud,
        rol=RolAsignacion.EJECUTIVO,
        estrategia=detalle_ejec.get('estrategia', ''),
        persona_asignada_id=ejecutivo.id,
        persona_asignada_nombre=ejecutivo.nombre,
        detalle=detalle_ejec,
        ejecutado_por=request.user,
    )
    # idem para analista
```

**6) Redirigir al detalle**. Si algo falla, se captura `ValidationError` y se muestra como mensaje de Django `messages.error`.

### 2.2. Diagrama mental

```
Formulario POST
      │
      ▼
┌──────────────────┐
│ Validar campos   │──── error ──► messages.error
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Calcular renta   │
│ total + contexto │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐        ┌────────────────────────┐
│ asig.asignar()   │──────►│ Estrategia activa      │
│ (ejecutivo)      │        │ (ROUND_ROBIN, etc.)    │
└────────┬─────────┘        └────────────────────────┘
         │
         ▼
┌──────────────────┐
│ asig.asignar()   │
│ (analista)       │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────┐
│ transaction.atomic():        │
│   Solicitud.objects.create   │
│   SolicitudCircuito × N      │
│   RegistroAsignacion × 2     │
└────────┬─────────────────────┘
         │
         ▼
  redirect → detalle
```

---

## 3. El corazón del sistema: `asignacion.py`

Aquí está la parte más rica del código y la más interesante desde el punto de vista de calidad (es donde se concentran los casos de prueba CP-03 a CP-05 y CP-11 del README).

### 3.1. Patrón Strategy

En vez de tener un `if estrategia == "ROUND_ROBIN": ... elif ...`, cada estrategia es una **clase** que hereda de `AsignadorBase`:

```python
# asignacion.py:152
class AsignadorBase(ABC):
    codigo: str = ""

    def __init__(self, rol: str):
        self.rol = rol

    def candidatos_base(self):
        return (
            _modelo_persona(self.rol)
            .objects.filter(activo=True, disponible_asignacion=True)
            .order_by("id")
        )

    def aplicar_tope_carga(self, candidatos, renta_nueva):
        """Excluye candidatos cuya carga actual + nueva renta supera su tope."""
        ...

    def seleccionar(self, contexto):
        candidatos = list(self.candidatos_base())
        candidatos = self.aplicar_tope_carga(candidatos, contexto.renta_total)
        if not candidatos:
            return None, {...}
        persona, detalle = self._seleccionar(candidatos, contexto)
        detalle["estrategia"] = self.codigo
        return persona, detalle

    @abstractmethod
    def _seleccionar(self, candidatos, contexto):
        ...
```

Hay dos niveles:

- **`seleccionar` (público)** — común a todas las estrategias: filtra activos/disponibles, aplica el tope de carga por renta, arma el detalle final de auditoría.
- **`_seleccionar` (abstracto)** — lo implementa cada estrategia con su propia lógica.

Así, agregar una nueva estrategia son ~20 líneas y no se toca nada más.

### 3.2. Las 7 estrategias (una línea cada una)

| Clase | Clave | Regla |
|---|---|---|
| `AsignadorRoundRobin` | `ROUND_ROBIN` | El siguiente por id después del `last_<rol>_id` guardado en `ConfiguracionAsignacion`. |
| `AsignadorBalanceRenta` | `BALANCE_RENTA` | El que tiene **menor suma de renta** en casos abiertos. |
| `AsignadorCargaCasos` | `CARGA_CASOS` | El que tiene **menos casos abiertos**. |
| `AsignadorPonderado` | `PONDERADO` | El que tiene **mayor déficit** respecto a su peso configurado. |
| `AsignadorAleatorio` | `ALEATORIO` | `random.choice`. |
| `AsignadorStickyCliente` | `STICKY_CLIENTE` | El mismo agente que atendió al cliente la vez anterior; si no hay historial, fallback a round-robin. |
| `AsignadorRendimiento` | `RENDIMIENTO` | El de **mejor tasa de retención histórica**. |

### 3.3. Ejemplo: `ROUND_ROBIN`

```python
# asignacion.py:204
class AsignadorRoundRobin(AsignadorBase):
    codigo = EstrategiaAsignacion.ROUND_ROBIN

    def _seleccionar(self, candidatos, contexto):
        clave = f"last_{self.rol.lower()}_id"
        last_id = get_parametro_int(clave, 0)
        siguientes = [c for c in candidatos if c.id > last_id]
        elegido = siguientes[0] if siguientes else candidatos[0]
        set_parametro(clave, elegido.id)
        return elegido, {
            "razon": f"Siguiente en turno tras id previo={last_id}.",
            "ultimo_id_previo": last_id,
            "candidatos": [{"id": c.id, "nombre": c.nombre} for c in candidatos],
        }
```

Puntos a notar:
- El estado del round-robin se guarda en la tabla `ConfiguracionAsignacion` como par clave/valor (`last_ejecutivo_id`, `last_analista_id`).
- Si ya pasó el último id, envuelve desde el principio (`candidatos[0]`).
- Devuelve un detalle que deja rastro de **quién era el último antes** y **quiénes eran los candidatos considerados**.

### 3.4. Ejemplo: `PONDERADO` (la más compleja)

```python
# asignacion.py:252
class AsignadorPonderado(AsignadorBase):
    codigo = EstrategiaAsignacion.PONDERADO

    def _seleccionar(self, candidatos, contexto):
        pesos = {c.id: max(c.peso_asignacion, 0) for c in candidatos}
        total_peso = sum(pesos.values())
        if total_peso == 0:
            # Si todos tienen peso 0, no se puede ponderar → fallback round-robin.
            return AsignadorRoundRobin(self.rol)._seleccionar(candidatos, contexto)

        historicos = {c.id: _asignaciones_historicas(c, self.rol) for c in candidatos}
        total_hist = sum(historicos.values()) + 1  # +1: incluye la nueva

        # Déficit = (cuántos casos "debería" tener según su peso) - (cuántos tiene)
        puntuados = [
            (c, pesos[c.id], historicos[c.id],
             round((pesos[c.id] / total_peso) * total_hist - historicos[c.id], 2))
            for c in candidatos
        ]
        puntuados.sort(key=lambda p: (-p[3], p[0].id))   # mayor déficit primero
        return puntuados[0][0], {...}
```

La idea: no repartir "por ronda" sino **converger** hacia la proporción deseada. Si senior pesa 60 y los dos juniors pesan 20 cada uno, a largo plazo recibirá ~60 % de los casos.

### 3.5. Punto de entrada único

Desde la vista no se importa ninguna clase concreta — solo se llama a:

```python
# asignacion.py:366
def asignar(rol: str, contexto: SolicitudContexto):
    """Punto de entrada único. Devuelve (persona, detalle_audit)."""
    return obtener_asignador(rol).seleccionar(contexto)
```

Que internamente lee la estrategia activa de `ConfiguracionAsignacion` y busca la clase en un diccionario:

```python
# asignacion.py:346
ESTRATEGIAS = {
    cls.codigo: cls
    for cls in (AsignadorRoundRobin, AsignadorBalanceRenta, ...)
}

def obtener_asignador(rol: str) -> AsignadorBase:
    codigo = obtener_estrategia_activa(rol)
    cls = ESTRATEGIAS.get(codigo, AsignadorRoundRobin)  # fallback seguro
    return cls(rol)
```

Si la clave guardada en base no coincide con ninguna estrategia conocida (por ejemplo, tras borrar una), cae al `ROUND_ROBIN` por defecto en vez de explotar.

---

## 4. Modelo de datos y reglas de integridad

Todos los modelos viven en `portal_retenciones/models.py`. Lo importante no es la lista (está en el README), sino **dónde se aplican las reglas de negocio**.

### 4.1. Validación centralizada en `Solicitud.clean()`

```python
# models.py:365
def clean(self):
    super().clean()
    errores = {}

    # Regla 1: tipo_caso no se puede cambiar una vez cerrada.
    if self.pk:
        original = Solicitud.objects.filter(pk=self.pk).only(...).first()
        if original and original.veredicto != Veredicto.PENDIENTE:
            if self.tipo_caso != original.tipo_caso:
                errores["tipo_caso"] = "No se puede modificar..."

    # Regla 2: si hay veredicto final, motivo/comentario/fecha son obligatorios.
    if self.veredicto != Veredicto.PENDIENTE:
        if not self.motivo_cierre_id:
            errores["motivo_cierre"] = "Requerido al cerrar la solicitud."
        ...

    # Regla 3: el motivo seleccionado debe aplicar al veredicto elegido.
    if self.motivo_cierre_id and self.veredicto != Veredicto.PENDIENTE:
        if self.motivo_cierre.veredicto_aplicable != self.veredicto:
            errores["motivo_cierre"] = "El motivo no aplica al veredicto..."

    if errores:
        raise ValidationError(errores)
```

Estas tres reglas son las que cubren los casos CP-06 y CP-07 del plan de pruebas.

### 4.2. Acción de dominio `cerrar()`

En vez de dejar que la vista manipule campos sueltos, el cierre es un método del modelo que valida y guarda atómicamente:

```python
# models.py:397
def cerrar(self, veredicto, motivo, comentario_final, usuario=None, estado_final=None):
    if self.esta_cerrada:
        raise ValidationError("La solicitud ya está cerrada.")
    self.veredicto = veredicto
    self.motivo_cierre = motivo
    self.comentario_final = comentario_final
    self.fecha_cierre = timezone.now()
    if estado_final is not None:
        self.estado_actual = estado_final
    self.full_clean()   # dispara Solicitud.clean() → reglas 2 y 3
    self.save()
```

### 4.3. Propiedades derivadas (usadas en dashboard)

```python
# models.py:336
@property
def esta_cerrada(self):
    return self.veredicto != Veredicto.PENDIENTE and self.fecha_cierre is not None

@property
def tiempo_gestion(self):
    if not self.esta_cerrada:
        return None
    return self.fecha_cierre - self.fecha_creacion

@property
def cumple_sla(self):
    if not self.esta_cerrada:
        return None
    sla_horas = getattr(settings, "SOLICITUD_SLA_HORAS", 72)
    return self.tiempo_gestion.total_seconds() <= sla_horas * 3600
```

Estas son las que alimentan los KPIs del dashboard (CP-08, CP-12).

---

## 5. Otras piezas más pequeñas

### 5.1. `context_processors.py`
Inyecta en **todos los templates** las estrategias activas por rol, para que la UI pueda pintar "actualmente usando: ROUND_ROBIN" sin tener que pedirlo en cada vista.

### 5.2. `decorators.py`
Contiene decoradores de control de acceso que envuelven las vistas por permiso (`@permission_required('portal_retenciones.can_create_solicitud')`, etc.). Las permissions se declaran en `Solicitud.Meta.permissions` (`models.py:321`). Esto es lo que cubre CP-10 (403 si no tiene permiso).

### 5.3. `apps.py`
Conecta una señal `post_migrate` que crea automáticamente el grupo "Analistas" con los permisos correctos — así, al clonar el repo y correr `migrate`, los grupos ya quedan configurados.

### 5.4. `views/api.py`
Endpoints JSON ligeros (47 líneas) para autocompletar clientes y circuitos en el formulario, sin recargar la página.

### 5.5. `views/auth.py`
Login/logout con redirect a la vista `home`. Nada exótico — reutiliza `django.contrib.auth`.

---

## 6. Cómo se conecta todo (resumen final)

```
┌─────────────────────────────────────────────────────────────┐
│  Usuario (browser)                                          │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  URLs (config/urls.py) → vistas (views/pages.py)            │
│    - nueva_solicitud_view                                   │
│    - lista_solicitudes_view                                 │
│    - detalle_solicitud_view                                 │
│    - dashboard_view                                         │
│    - gestion_personal_view                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├──► asignacion.asignar(rol, contexto)
                   │         │
                   │         ▼
                   │    ┌────────────────────────────────┐
                   │    │ ConfiguracionAsignacion        │
                   │    │ (lee estrategia activa)        │
                   │    └──────────────┬─────────────────┘
                   │                   │
                   │                   ▼
                   │    ┌────────────────────────────────┐
                   │    │ AsignadorXxx._seleccionar()    │
                   │    │ → (persona, detalle)           │
                   │    └────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  Models (models.py)                                         │
│    Solicitud.clean() / .cerrar()  ← reglas de integridad    │
│    RegistroAsignacion             ← auditoría JSON          │
│    Cliente, Circuito, Personal…                             │
└─────────────────────────────────────────────────────────────┘
```

Ese es el recorrido completo: **form → vista → motor Strategy → base con auditoría → redirect**. Cualquier prueba unitaria razonable del curso va a apuntar a uno de esos cuatro bloques.
