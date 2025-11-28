# En: portal_retenciones/management/commands/seed_db.py

from django.core.management.base import BaseCommand
from portal_retenciones.models import (
    EstadoAtencion, 
    NivelAprobacion
)

# -----------------------------------------------------------------
# --- DATOS MAESTROS (Catálogos) ---
# -----------------------------------------------------------------

ESTADOS = [
    ('Registrado', 'Solicitud registrada por el ejecutivo.'),
    ('En Análisis', 'Analista revisando el caso.'),
    ('Aprobado', 'Solicitud de retención/baja aprobada.'),
    ('Rechazado', 'Solicitud rechazada.'),
    ('Baja Ejecutada', 'Baja del servicio completada.'),
]

NIVELES = [
    ('Nivel 1 - Ejecutivo', 1),
    ('Nivel 2 - Analista', 2),
    ('Nivel 3 - Gerencia', 3),
]

class Command(BaseCommand):
    help = 'Carga los catálogos esenciales (Estados y Niveles) para el sistema.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Empezando la carga de catálogos ---'))

        # -- Cargando Estados de Atención
        for nombre, desc in ESTADOS:
            EstadoAtencion.objects.get_or_create(nombre_estado=nombre, defaults={'descripcion': desc})
        self.stdout.write('Estados de Atención cargados.')
        
        # -- Cargando Niveles de Aprobación
        for nombre, orden in NIVELES:
            NivelAprobacion.objects.get_or_create(nombre_nivel=nombre, defaults={'orden': orden})
        self.stdout.write('Niveles de Aprobación cargados.')

        # -- NOTA: Ejecutivos y Analistas ya no se cargan aquí.

        self.stdout.write(self.style.SUCCESS('--- ¡Carga de catálogos completada! ---'))