"""Context processors del portal.

Exponen información global (disponible en todos los templates) sin necesidad de
inyectarla en cada vista.
"""

from portal_retenciones import asignacion as asig
from portal_retenciones.models import EstrategiaAsignacion, RolAsignacion


def estrategias_activas(request):
    """Expone la estrategia de asignación activa para ejecutivos y analistas.

    Usada por la sidebar y el dashboard para mostrar qué algoritmo se está
    aplicando en cada rol sin tocar cada vista individual.
    """
    if not request.user.is_authenticated:
        return {}

    try:
        cod_ejec = asig.obtener_estrategia_activa(RolAsignacion.EJECUTIVO)
        cod_anal = asig.obtener_estrategia_activa(RolAsignacion.ANALISTA)
    except Exception:
        # Durante migraciones iniciales la tabla puede no existir todavía.
        return {}

    display = dict(EstrategiaAsignacion.choices)
    return {
        'estrategia_ejec_codigo': cod_ejec,
        'estrategia_ejec_nombre': display.get(cod_ejec, cod_ejec),
        'estrategia_ejec_descripcion': asig.ESTRATEGIA_DESCRIPCIONES.get(cod_ejec, ''),
        'estrategia_anal_codigo': cod_anal,
        'estrategia_anal_nombre': display.get(cod_anal, cod_anal),
        'estrategia_anal_descripcion': asig.ESTRATEGIA_DESCRIPCIONES.get(cod_anal, ''),
    }
