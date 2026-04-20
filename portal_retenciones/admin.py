from django.contrib import admin

from .models import (
    AnalistaRetencion,
    Circuito,
    Cliente,
    Comentario,
    ConfiguracionAsignacion,
    EjecutivoRetencion,
    EstadoAtencion,
    HistorialAsignacion,
    HistorialEstado,
    MotivoAusencia,
    MotivoCierre,
    NivelAprobacion,
    RegistroAsignacion,
    Solicitud,
    TipoCaso,
    TipoServicio,
)


# --- Catálogos: registro con lista/edit inline --------------------------
@admin.register(TipoServicio)
class TipoServicioAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "activo")
    list_editable = ("nombre", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(TipoCaso)
class TipoCasoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "activo")
    list_editable = ("nombre", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(MotivoAusencia)
class MotivoAusenciaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "activo")
    list_editable = ("nombre", "activo")
    search_fields = ("codigo", "nombre")


@admin.register(MotivoCierre)
class MotivoCierreAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descripcion", "veredicto_aplicable", "activo")
    list_filter = ("veredicto_aplicable", "activo")
    search_fields = ("codigo", "descripcion")


@admin.register(EstadoAtencion)
class EstadoAtencionAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre_estado", "es_final")
    list_editable = ("nombre_estado", "es_final")


# --- Modelos operativos ------------------------------------------------
@admin.register(EjecutivoRetencion)
class EjecutivoRetencionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "email", "activo", "disponible_asignacion", "peso_asignacion", "motivo_no_disponible")
    list_filter = ("activo", "disponible_asignacion")
    search_fields = ("nombre", "email")


@admin.register(AnalistaRetencion)
class AnalistaRetencionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "email", "activo", "disponible_asignacion", "peso_asignacion", "motivo_no_disponible")
    list_filter = ("activo", "disponible_asignacion")
    search_fields = ("nombre", "email")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("ruc", "razon_social", "estado")
    search_fields = ("ruc", "razon_social")


@admin.register(Circuito)
class CircuitoAdmin(admin.ModelAdmin):
    list_display = ("nombre_circuito", "cliente", "tipo_servicio", "renta_mensual", "estado")
    list_filter = ("tipo_servicio", "estado")
    search_fields = ("nombre_circuito", "cliente__razon_social")


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ("id", "cliente", "tipo_caso", "estado_actual", "veredicto", "ejecutivo", "fecha_creacion")
    list_filter = ("tipo_caso", "veredicto", "estado_actual")
    search_fields = ("cliente__razon_social", "cliente__ruc")
    date_hierarchy = "fecha_creacion"


@admin.register(NivelAprobacion)
class NivelAprobacionAdmin(admin.ModelAdmin):
    list_display = ("orden", "nombre_nivel")
    list_editable = ("nombre_nivel",)


@admin.register(RegistroAsignacion)
class RegistroAsignacionAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "rol", "estrategia", "persona_asignada_nombre", "fecha")
    list_filter = ("rol", "estrategia")


@admin.register(ConfiguracionAsignacion)
class ConfiguracionAsignacionAdmin(admin.ModelAdmin):
    list_display = ("clave", "valor")
    list_editable = ("valor",)


admin.site.register(Comentario)
admin.site.register(HistorialAsignacion)
admin.site.register(HistorialEstado)
