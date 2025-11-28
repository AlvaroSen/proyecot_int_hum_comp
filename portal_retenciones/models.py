from django.db import models
from django.contrib.auth.models import User

# -- Modelo: Cliente
class Cliente(models.Model):
    ruc = models.CharField(max_length=100, unique=True, blank=False, null=False)
    razon_social = models.CharField(max_length=100, blank=False, null=False)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, default='Activo')

    def __str__(self):
        return self.razon_social

# -- Modelo: Circuito
class Circuito(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, null=False)
    nombre_circuito = models.CharField(max_length=100, null=False)
    tipo_servicio = models.CharField(max_length=10, null=True, blank=True)
    estado = models.CharField(max_length=20, default='Activo')
    renta_mensual = models.DecimalField(max_digits=12, decimal_places=2, null=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre_circuito} ({self.cliente.razon_social})"

# -- Modelo: EjecutivoRetencion
class EjecutivoRetencion(models.Model):
    nombre = models.CharField(max_length=100, null=False)
    email = models.EmailField(max_length=100, null=False, unique=True)
    activo = models.BooleanField(default=True)
    max_carga_renta = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    disponible_asignacion = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

# -- Modelo: AnalistaRetencion
class AnalistaRetencion(models.Model):
    nombre = models.CharField(max_length=100, null=False)
    email = models.EmailField(max_length=100, null=False, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

# -- Modelo: EstadoAtencion
class EstadoAtencion(models.Model):
    nombre_estado = models.CharField(max_length=100, null=False)
    descripcion = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.nombre_estado

# -- Modelo: NivelAprobacion
class NivelAprobacion(models.Model):
    nombre_nivel = models.CharField(max_length=100, null=False)
    orden = models.IntegerField(null=False)

    def __str__(self):
        return self.nombre_nivel

# -- Modelo: ConfiguracionAsignacion (NUEVO MODELO PARA ROUND-ROBIN)
class ConfiguracionAsignacion(models.Model):
    # La clave de configuración (siempre 'last_ejecutivo_id')
    clave = models.CharField(max_length=50, primary_key=True)
    # El ID del último ejecutivo asignado
    valor = models.IntegerField(default=0) 

    def __str__(self):
        return self.clave

# -- Modelo: Solicitud
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
    fecha_solicitud_baja = models.DateField(null=True, blank=True) 
    
    usuario_creador = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="solicitudes_creadas"
    )

    class Meta:
        permissions = [
            ("can_view_menu", "Puede ver el menú de inicio (requerido para login)"),
            ("can_create_solicitud", "Puede acceder al formulario de Nueva Solicitud"),
            ("can_view_solicitud_list", "Puede acceder a la lista de Solicitudes"),
            ("can_view_personal", "Puede acceder a la lista de Personal Activo"),
            ("can_manage_personnel", "Puede gestionar la asignación de personal a roles"),
        ]

    def __str__(self):
        return f"Solicitud #{self.id} - {self.cliente.razon_social}"

# -- Modelo: Comentario
class Comentario(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, null=False)
    usuario = models.CharField(max_length=100, null=False) 
    comentario = models.TextField(null=False)
    fecha_comentario = models.DateTimeField(auto_now_add=True)

# -- Modelo: HistorialAsignacion
class HistorialAsignacion(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, null=False)
    ejecutivo_anterior = models.ForeignKey(EjecutivoRetencion, related_name='historial_anterior', on_delete=models.PROTECT, null=False)
    ejecutivo_nuevo = models.ForeignKey(EjecutivoRetencion, related_name='historial_nuevo', on_delete=models.PROTECT, null=False)
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField(null=True, blank=True)

# -- Modelo: HistorialEstado
class HistorialEstado(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, null=False)
    estado_anterior = models.ForeignKey(EstadoAtencion, related_name='+', on_delete=models.PROTECT, null=False)
    estado_nuevo = models.ForeignKey(EstadoAtencion, related_name='+', on_delete=models.PROTECT, null=False)
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    usuario_cambio = models.CharField(max_length=100, null=False) 

# -- Modelo: SolicitudCircuito (Tabla intermedia)
class SolicitudCircuito(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE)
    circuito = models.ForeignKey(Circuito, on_delete=models.CASCADE)
    fecha_asociacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('solicitud', 'circuito')