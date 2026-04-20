# Portal de Retenciones

Aplicación web interna para gestionar casos de retención de clientes: un cliente solicita dar de baja un servicio y el portal asigna automáticamente un ejecutivo y un analista para intentar retenerlo, registra el tratamiento del caso y cierra con un veredicto (Retenido / No retenido / Desestimado).

Este repositorio corresponde a la **entrega del curso universitario "Calidad y Pruebas de Software"**, por lo que además del código funcional se documenta el plan de aseguramiento de calidad y los casos de prueba propuestos.

- **Entorno productivo (demo):** https://retencion.alvarosen.net.pe
- **Repositorio:** https://github.com/AlvaroSen/proyecot_int_hum_comp

---

## 1. Stack técnico

| Capa | Tecnología |
|---|---|
| Backend | Python 3.11 + Django 5.0 |
| Base de datos | SQLite (desarrollo) / SQL Server (producción, vía `mssql-django` y ODBC 17) |
| Servidor WSGI | Gunicorn (3 workers) |
| Archivos estáticos | WhiteNoise (compresión gzip + hashing) |
| Frontend | Plantillas Django + JavaScript vanilla + Chart.js para dashboard |
| Autenticación | `django.contrib.auth` (sesiones) + grupos con permisos granulares |
| Despliegue | Docker / docker-compose detrás de Cloudflare Tunnel |

---

## 2. Dominio y funcionalidades principales

### Actores

- **Ejecutivo de Retención**: primer contacto con el cliente, registra interacciones.
- **Analista de Retención**: reevalúa los casos escalados o complejos.
- **Administrador**: configura estrategias de asignación, catálogos y personal desde `/admin` y `/gestion-personal/`.

### Flujos principales

1. **Nueva solicitud** (`/solicitud/nueva/`): se registra el cliente, circuito, tipo de servicio, renta y tipo de caso. El sistema asigna automáticamente ejecutivo y analista según la estrategia activa de cada rol.
2. **Lista de solicitudes** (`/solicitudes/lista/`): listado con filtros (búsqueda, estado, tipo de caso, veredicto, ejecutivo, rango de fechas), KPIs en cabecera y exportación a CSV.
3. **Detalle de solicitud** (`/solicitud/detalle/<id>/`): historial de comentarios, trazabilidad de la estrategia usada en la asignación, y acciones de cierre (Retenido / No retenido / Desestimado) con motivo de cierre obligatorio.
4. **Dashboard** (`/dashboard/`): KPIs (tasa de retención, tiempo medio de gestión, cumplimiento de SLA, cumplimiento de primera respuesta) con filtro de período (30, 90, 180, 365 días o histórico) y gráficos por veredicto, estado, motivo de cierre, desempeño por ejecutivo, tendencia mensual y tipo de caso.
5. **Gestión de personal** (`/gestion-personal/`): configuración de la estrategia activa por rol y de los parámetros de cada persona (peso, tope de carga, disponibilidad, motivo de no disponibilidad).

### Estrategias de asignación

El módulo `portal_retenciones/asignacion.py` implementa el patrón Strategy con 7 estrategias intercambiables en tiempo de ejecución:

| Estrategia | Descripción |
|---|---|
| `ROUND_ROBIN` | Turno circular por ID. |
| `BALANCE_RENTA` | Prefiere al que menos renta activa tiene acumulada. |
| `CARGA_CASOS` | Prefiere al que menos casos abiertos tiene. |
| `PONDERADO` | Distribución proporcional al peso configurado por persona. |
| `ALEATORIO` | Selección uniforme. |
| `STICKY_CLIENTE` | Si el cliente ya tuvo un caso, se reasigna al mismo agente. |
| `RENDIMIENTO` | Prioriza al de mejor tasa histórica de retención. |

Cada asignación se audita en `RegistroAsignacion` con la estrategia usada, los candidatos evaluados y el detalle en JSON.

---

## 3. Arquitectura

```
proyecot_int_hum_comp/
├── config/                      # Proyecto Django (settings, urls, wsgi)
├── portal_retenciones/          # App principal
│   ├── models.py                # Clientes, Circuitos, Solicitudes, Personal, catálogos, auditoría
│   ├── asignacion.py            # Motor de estrategias (patrón Strategy)
│   ├── context_processors.py    # Inyecta estrategias activas en todos los templates
│   ├── admin.py                 # Configuración de Django admin
│   ├── apps.py                  # Signal post_migrate que crea el grupo "Analistas"
│   ├── views/
│   │   ├── pages.py             # Vistas HTML (dashboard, lista, detalle, gestión)
│   │   ├── api.py               # Endpoints JSON para autocompletar
│   │   ├── auth.py              # Login / logout
│   │   └── home.py              # Home y menú
│   └── migrations/              # 0001 a 0007
├── templates/                   # Plantillas HTML
├── static/                      # CSS y JS fuente
├── staticfiles/                 # Salida de collectstatic (servido por WhiteNoise)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

### Modelo de datos (resumen)

- **Catálogos**: `TipoServicio`, `TipoCaso`, `MotivoAusencia`, `MotivoCierre`, `EstadoAtencion`.
- **Entidades de negocio**: `Cliente`, `Circuito`, `Solicitud`.
- **Personal**: clase abstracta `PersonalRetencion` con subclases `EjecutivoRetencion` y `AnalistaRetencion`.
- **Configuración y auditoría**: `ConfiguracionAsignacion` (parámetros por rol) y `RegistroAsignacion` (traza de cada asignación).

---

## 4. Puesta en marcha

### 4.1 Requisitos

- Python 3.11 o Docker + docker-compose.
- Opcional (producción): SQL Server accesible y driver ODBC 17.

### 4.2 Variables de entorno

Crear un archivo `.env` en la raíz a partir de este ejemplo:

```env
DJANGO_SECRET_KEY=cambia-esta-clave
DEBUG=False
ALLOWED_HOSTS=retencion.alvarosen.net.pe,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://retencion.alvarosen.net.pe

# Solo si se usa SQL Server en producción
SQL_USER=usuario
SQL_PASSWORD=secreto
SQL_HOST=servidor\\instancia

# SLA en horas para el cierre de casos
SOLICITUD_SLA_HORAS=48
```

### 4.3 Ejecución local (SQLite)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

La aplicación queda disponible en `http://127.0.0.1:8000`.

### 4.4 Ejecución con Docker

```bash
docker compose up --build -d
```

El `Dockerfile` usa Python 3.11-slim, instala ODBC Driver 17, ejecuta `collectstatic` y arranca Gunicorn con 3 workers en el puerto 8000. El `docker-compose.yml` monta volúmenes para persistir `db.sqlite3` y los archivos estáticos.

---

## 5. Plan de calidad y pruebas

Esta sección cubre los aspectos exigidos por el curso de Calidad y Pruebas de Software.

### 5.1 Niveles de prueba previstos

| Nivel | Objetivo | Herramienta |
|---|---|---|
| Unitarias | Lógica pura de `asignacion.py`, validadores, métodos de modelo (`Solicitud.cerrar()`, `cumple_sla`, `tiempo_gestion`). | `pytest` + `pytest-django` |
| Integración | Vistas (`nueva_solicitud_view`, `lista_solicitudes_view`, `dashboard_view`) con base de datos en memoria y usuarios de prueba. | `pytest-django` + `Client` de Django |
| Sistema | Flujo completo: login → crear solicitud → asignar → cerrar → aparece en dashboard y CSV. | `pytest` + `Selenium` o `Playwright` |
| Regresión | Suite ejecutada en cada Pull Request. | GitHub Actions |

### 5.2 Herramientas de aseguramiento recomendadas

- **`pytest-django`** para ejecutar la suite.
- **`coverage.py`** con objetivo mínimo de **80 %** en `portal_retenciones/asignacion.py` y `models.py`.
- **`ruff`** (o `flake8`) como linter.
- **`mypy`** en las funciones con type hints (el módulo `asignacion.py` ya los usa).
- **`pre-commit`** para ejecutar linter + tests antes de cada commit.
- **GitHub Actions**: workflow `ci.yml` que instale dependencias, corra `python manage.py migrate --run-syncdb`, `pytest` y `ruff`.

### 5.3 Casos de prueba críticos (resumen)

| ID | Caso | Resultado esperado |
|---|---|---|
| CP-01 | Crear solicitud con RUC inválido (≠ 11 dígitos). | Rechazo con mensaje del `RUC_VALIDATOR`. |
| CP-02 | Crear solicitud sin tipo de caso. | Rechazo del formulario, la solicitud no se guarda. |
| CP-03 | Estrategia `ROUND_ROBIN` con 3 ejecutivos activos y 7 solicitudes. | Distribución 3-2-2 (o permutación equivalente). |
| CP-04 | Estrategia `BALANCE_RENTA` con un agente saturado. | El nuevo caso no va al saturado, va al de menor renta activa. |
| CP-05 | Estrategia `STICKY_CLIENTE` para cliente con historial. | Reasigna al mismo agente del caso anterior. |
| CP-06 | Cerrar solicitud ya cerrada. | `ValidationError`; el estado no cambia. |
| CP-07 | Cerrar con `veredicto=RETENIDO` y sin `motivo_cierre`. | Rechazo; se exige motivo. |
| CP-08 | Caso abierto > SLA horas. | `cumple_sla` devuelve `False` y el dashboard lo cuenta en alertas. |
| CP-09 | Exportar CSV con filtros aplicados. | El CSV contiene solo los casos filtrados y las columnas documentadas. |
| CP-10 | Usuario sin permiso `can_configure_asignacion_ejecutivos`. | `/gestion-personal/` responde 403. |
| CP-11 | Registro de auditoría. | Cada solicitud creada genera un `RegistroAsignacion` con estrategia y candidatos. |
| CP-12 | Dashboard con período = 30 días. | Solo se consideran solicitudes creadas en los últimos 30 días. |

### 5.4 Estado actual de la suite

> `portal_retenciones/tests.py` está vacío. La implementación de los casos de la tabla 5.3 está pendiente y es el principal entregable de calidad del curso.

---

## 6. Convenciones

- Commits en español, usando prefijos temáticos: `infra:`, `modelos:`, `asignación:`, `vistas:`, `ui:`, `admin:`, `chore:`, `test:`, `docs:`.
- Cada cambio de modelo debe venir acompañado de su migración correspondiente.
- Nada de credenciales en el repositorio: todo va por `.env`.

---

## 7. Autor

Alvaro — Curso "Calidad y Pruebas de Software".
