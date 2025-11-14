# En: portal_retenciones/models.py

from django.db import models

# Tabla: RETENCION.CLIENTES
class Cliente(models.Model):
    ruc = models.CharField(max_length=100, unique=True, blank=False, null=False)
    razon_social = models.CharField(max_length=100, blank=False, null=False)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, default='Activo')

    def __str__(self):
        return self.razon_social

# Tabla: RETENCION.CIRCUITOS
class Circuito(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=False)
    nombre_circuito = models.CharField(max_length=100, null=False)
    tipo_servicio = models.CharField(max_length=10, null=True, blank=True)
    estado = models.CharField(max_length=20, default='Activo')
    renta_mensual = models.DecimalField(max_digits=12, decimal_places=2, null=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre_circuito} ({self.cliente.razon_social})"

# Tabla: RETENCION.EJECUTIVOS_RETENCION
class EjecutivoRetencion(models.Model):
    nombre = models.CharField(max_length=100, null=False)
    email = models.EmailField(max_length=100, null=False, unique=True)
    activo = models.BooleanField(default=True)
    max_carga_renta = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    disponible_asignacion = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

# Tabla: RETENCION.ANALISTAS_RETENCION
class AnalistaRetencion(models.Model):
    nombre = models.CharField(max_length=100, null=False)
    email = models.EmailField(max_length=100, null=False, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

# Tabla: RETENCION.ESTADO_ATENCION
class EstadoAtencion(models.Model):
    nombre_estado = models.CharField(max_length=100, null=False)
    descripcion = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.nombre_estado

# Tabla: RETENCION.NIVELES_APROBACION
class NivelAprobacion(models.Model):
    nombre_nivel = models.CharField(max_length=100, null=False)
    orden = models.IntegerField(null=False)

    def __str__(self):
        return self.nombre_nivel

# Tabla: RETENCION.SOLICITUDES
class Solicitud(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, null=False)
    ejecutivo = models.ForeignKey(EjecutivoRetencion, on_delete=models.PROTECT, null=False)
    analista = models.ForeignKey(AnalistaRetencion, on_delete=models.PROTECT, null=False)
    estado_actual = models.ForeignKey(EstadoAtencion, on_delete=models.PROTECT, null=False)
    nivel_aprobacion = models.ForeignKey(NivelAprobacion, on_delete=models.PROTECT, null=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    descripcion = models.TextField(null=True, blank=True)
    asignado_automaticamente = models.BooleanField(default=False)
    circuitos = models.ManyToManyField(Circuito, through='SolicitudCircuito')

    def __str__(self):
        return f"Solicitud #{self.id} - {self.cliente.razon_social}"

# Tabla: RETENCION.COMENTARIOS
class Comentario(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, null=False)
    usuario = models.CharField(max_length=100, null=False) # Idealmente, esto sería un ForeignKey al User de Django
    comentario = models.TextField(null=False)
    fecha_comentario = models.DateTimeField(auto_now_add=True)

# Tabla: RETENCION.HISTORIAL_ASIGNACIONES
class HistorialAsignacion(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, null=False)
    ejecutivo_anterior = models.ForeignKey(EjecutivoRetencion, related_name='+', on_delete=models.PROTECT, null=False)
    ejecutivo_nuevo = models.ForeignKey(EjecutivoRetencion, related_name='+', on_delete=models.PROTECT, null=False)
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField(null=True, blank=True)

# Tabla: RETENCION.HISTORIAL_ESTADOS
class HistorialEstado(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, null=False)
    estado_anterior = models.ForeignKey(EstadoAtencion, related_name='+', on_delete=models.PROTECT, null=False)
    estado_nuevo = models.ForeignKey(EstadoAtencion, related_name='+', on_delete=models.PROTECT, null=False)
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    usuario_cambio = models.CharField(max_length=100, null=False) # Idealmente, esto también sería un ForeignKey al User

# Tabla: RETENCION.SOLICITUD_CIRCUITOS (Tabla intermedia para ManyToMany)
class SolicitudCircuito(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE)
    circuito = models.ForeignKey(Circuito, on_delete=models.CASCADE)
    fecha_asociacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('solicitud', 'circuito')