from django.contrib import admin
from .models import (
    EjecutivoRetencion, 
    AnalistaRetencion, 
    Cliente, 
    Circuito, 
    Solicitud, 
    EstadoAtencion, 
    NivelAprobacion, 
    Comentario,
    HistorialAsignacion,
    HistorialEstado
)

# Registramos los modelos para que aparezcan en el panel de administración
admin.site.register(EjecutivoRetencion)
admin.site.register(AnalistaRetencion)
admin.site.register(Cliente)
admin.site.register(Circuito)
admin.site.register(Solicitud)
admin.site.register(EstadoAtencion)
admin.site.register(NivelAprobacion)
admin.site.register(Comentario)
admin.site.register(HistorialAsignacion)
admin.site.register(HistorialEstado)