from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone


RUC_VALIDATOR = RegexValidator(
    regex=r"^\d{11}$",
    message="El RUC debe tener exactamente 11 dígitos numéricos.",
)


class EstadoGeneral(models.TextChoices):
    ACTIVO = "Activo", "Activo"
    INACTIVO = "Inactivo", "Inactivo"


class Veredicto(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    RETENIDO = "RETENIDO", "Retenido"
    NO_RETENIDO = "NO_RETENIDO", "No retenido"
    DESESTIMADO = "DESESTIMADO", "Desestimado"


class EstrategiaAsignacion(models.TextChoices):
    ROUND_ROBIN = "ROUND_ROBIN", "Round-robin (por turno)"
    BALANCE_RENTA = "BALANCE_RENTA", "Balance por renta"
    CARGA_CASOS = "CARGA_CASOS", "Balance por carga de casos"
    PONDERADO = "PONDERADO", "Distribución ponderada"
    ALEATORIO = "ALEATORIO", "Aleatorio uniforme"
    STICKY_CLIENTE = "STICKY_CLIENTE", "Cliente fijo (sticky)"
    RENDIMIENTO = "RENDIMIENTO", "Por rendimiento histórico"


class RolAsignacion(models.TextChoices):
    EJECUTIVO = "EJECUTIVO", "Ejecutivo de Retención"
    ANALISTA = "ANALISTA", "Analista de Retención"


# --- Catálogos: se administran desde /admin sin requerir migración ----
class TipoServicio(models.Model):
    """Catálogo de tipos de servicio (Internet, Telefonía, etc.)."""

    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=80)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Tipo de Servicio"
        verbose_name_plural = "Tipos de Servicio"

    def __str__(self):
        return self.nombre


class TipoCaso(models.Model):
    """Catálogo de tipos de caso (Baja APC, Retención, etc.)."""

    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=80)
    descripcion = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Tipo de Caso"
        verbose_name_plural = "Tipos de Caso"

    def __str__(self):
        return self.nombre


class MotivoAusencia(models.Model):
    """Catálogo de motivos de no disponibilidad del personal."""

    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=80)
    descripcion = models.TextField(blank=True, default="")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Motivo de Ausencia"
        verbose_name_plural = "Motivos de Ausencia"

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    ruc = models.CharField(max_length=11, unique=True, validators=[RUC_VALIDATOR])
    razon_social = models.CharField(max_length=100)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoGeneral.choices,
        default=EstadoGeneral.ACTIVO,
    )

    class Meta:
        ordering = ["razon_social"]
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.razon_social


class Circuito(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="circuitos")
    nombre_circuito = models.CharField(max_length=100)
    tipo_servicio = models.ForeignKey(
        TipoServicio,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="circuitos",
    )
    estado = models.CharField(
        max_length=20,
        choices=EstadoGeneral.choices,
        default=EstadoGeneral.ACTIVO,
    )
    renta_mensual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre_circuito"]
        verbose_name = "Circuito"
        verbose_name_plural = "Circuitos"

    def __str__(self):
        return f"{self.nombre_circuito} ({self.cliente.razon_social})"


class PersonalRetencion(models.Model):
    """Base abstracta para roles de retención (ejecutivos, analistas)."""

    nombre = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, unique=True)
    activo = models.BooleanField(default=True)
    motivo_no_disponible = models.ForeignKey(
        MotivoAusencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Motivo de no disponibilidad (si aplica). Se ignora cuando el flag 'disponible' está activo.",
    )

    class Meta:
        abstract = True
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EjecutivoRetencion(PersonalRetencion):
    max_carga_renta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Tope de renta mensual acumulada. Dejar vacío para sin límite.",
    )
    disponible_asignacion = models.BooleanField(default=True)
    peso_asignacion = models.PositiveSmallIntegerField(
        default=1,
        help_text="Peso relativo para la estrategia Ponderado (mayor = más casos).",
    )

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Ejecutivo de Retención"
        verbose_name_plural = "Ejecutivos de Retención"


class AnalistaRetencion(PersonalRetencion):
    max_carga_renta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Tope de renta mensual acumulada. Dejar vacío para sin límite.",
    )
    disponible_asignacion = models.BooleanField(default=True)
    peso_asignacion = models.PositiveSmallIntegerField(
        default=1,
        help_text="Peso relativo para la estrategia Ponderado (mayor = más casos).",
    )

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Analista de Retención"
        verbose_name_plural = "Analistas de Retención"


class EstadoAtencion(models.Model):
    codigo = models.CharField(
        max_length=30,
        unique=True,
        help_text="Código estable para identificar el estado en código (p.ej. NUEVO, EN_ATENCION, CERRADO).",
    )
    nombre_estado = models.CharField(max_length=100)
    descripcion = models.TextField(null=True, blank=True)
    es_final = models.BooleanField(
        default=False,
        help_text="Marca que este estado cierra la solicitud (terminal).",
    )

    class Meta:
        ordering = ["nombre_estado"]
        verbose_name = "Estado de Atención"
        verbose_name_plural = "Estados de Atención"

    def __str__(self):
        return self.nombre_estado


class MotivoCierre(models.Model):
    """Catálogo de motivos de cierre, filtrables por veredicto aplicable."""

    codigo = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=150)
    veredicto_aplicable = models.CharField(
        max_length=20,
        choices=Veredicto.choices,
        help_text="Veredicto al que aplica este motivo.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["veredicto_aplicable", "descripcion"]
        verbose_name = "Motivo de Cierre"
        verbose_name_plural = "Motivos de Cierre"

    def __str__(self):
        return f"[{self.get_veredicto_aplicable_display()}] {self.descripcion}"


class NivelAprobacion(models.Model):
    nombre_nivel = models.CharField(max_length=100)
    orden = models.IntegerField()

    class Meta:
        ordering = ["orden"]
        verbose_name = "Nivel de Aprobación"
        verbose_name_plural = "Niveles de Aprobación"

    def __str__(self):
        return self.nombre_nivel


class ConfiguracionAsignacion(models.Model):
    """Pares clave/valor para estado y parámetros de las estrategias de asignación."""

    clave = models.CharField(max_length=50, primary_key=True)
    valor = models.CharField(max_length=100, default="")

    class Meta:
        verbose_name = "Configuración de Asignación"
        verbose_name_plural = "Configuración de Asignación"

    def __str__(self):
        return f"{self.clave} = {self.valor}"


class Solicitud(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="solicitudes")
    ejecutivo = models.ForeignKey(EjecutivoRetencion, on_delete=models.PROTECT, related_name="solicitudes")
    analista = models.ForeignKey(AnalistaRetencion, on_delete=models.PROTECT, related_name="solicitudes")
    estado_actual = models.ForeignKey(EstadoAtencion, on_delete=models.PROTECT, related_name="solicitudes")
    nivel_aprobacion = models.ForeignKey(NivelAprobacion, on_delete=models.PROTECT, related_name="solicitudes")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    descripcion = models.TextField(null=True, blank=True)
    asignado_automaticamente = models.BooleanField(default=False)
    circuitos = models.ManyToManyField(Circuito, through="SolicitudCircuito", related_name="solicitudes")
    fecha_solicitud_baja = models.DateField(null=True, blank=True)
    tipo_caso = models.ForeignKey(
        TipoCaso,
        on_delete=models.PROTECT,
        related_name="solicitudes",
        help_text="Tipo de caso. Editable solo mientras la solicitud no esté cerrada.",
    )
    veredicto = models.CharField(
        max_length=20,
        choices=Veredicto.choices,
        default=Veredicto.PENDIENTE,
    )
    motivo_cierre = models.ForeignKey(
        MotivoCierre,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitudes",
    )
    comentario_final = models.TextField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    usuario_creador = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_creadas",
    )

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Solicitud"
        verbose_name_plural = "Solicitudes"
        permissions = [
            ("can_view_menu", "Puede ver el menú de inicio (requerido para login)"),
            ("can_create_solicitud", "Puede acceder al formulario de Nueva Solicitud"),
            ("can_view_solicitud_list", "Puede acceder a la lista de Solicitudes"),
            ("can_view_personal", "Puede acceder a la lista de Personal Activo"),
            ("can_manage_personnel", "Puede gestionar la asignación de personal a roles"),
            ("can_configure_asignacion_ejecutivos", "Puede configurar la estrategia de asignación de ejecutivos"),
            ("can_configure_asignacion_analistas", "Puede configurar la estrategia de asignación de analistas"),
        ]

    def __str__(self):
        return f"Solicitud #{self.id} - {self.cliente.razon_social}"

    # -- Propiedades derivadas --------------------------------------------

    @property
    def esta_cerrada(self):
        return self.veredicto != Veredicto.PENDIENTE and self.fecha_cierre is not None

    @property
    def tiempo_gestion(self):
        """Duración entre creación y cierre. None si sigue abierta."""
        if not self.esta_cerrada:
            return None
        return self.fecha_cierre - self.fecha_creacion

    @property
    def cumple_sla(self):
        """True si la solicitud cerró dentro del SLA configurado. None si abierta."""
        if not self.esta_cerrada:
            return None
        sla_horas = getattr(settings, "SOLICITUD_SLA_HORAS", 72)
        return self.tiempo_gestion.total_seconds() <= sla_horas * 3600

    @property
    def tiempo_primera_respuesta(self):
        """Duración entre creación y primer comentario registrado."""
        primer_comentario = self.comentarios.order_by("fecha_comentario").first()
        if not primer_comentario:
            return None
        return primer_comentario.fecha_comentario - self.fecha_creacion

    # -- Validaciones de integridad ---------------------------------------

    def clean(self):
        super().clean()
        errores = {}

        # Regla 1: tipo_caso no se puede cambiar una vez cerrada.
        if self.pk:
            original = Solicitud.objects.filter(pk=self.pk).only("tipo_caso", "veredicto", "fecha_cierre").first()
            if original and original.veredicto != Veredicto.PENDIENTE:
                if self.tipo_caso != original.tipo_caso:
                    errores["tipo_caso"] = "No se puede modificar el tipo de caso después del cierre."

        # Regla 2: si hay veredicto final, deben existir motivo, comentario y fecha de cierre.
        if self.veredicto != Veredicto.PENDIENTE:
            if not self.motivo_cierre_id:
                errores["motivo_cierre"] = "Requerido al cerrar la solicitud."
            if not self.comentario_final:
                errores["comentario_final"] = "Requerido al cerrar la solicitud."
            if not self.fecha_cierre:
                errores["fecha_cierre"] = "Requerido al cerrar la solicitud."

        # Regla 3: el motivo debe coincidir con el veredicto.
        if self.motivo_cierre_id and self.veredicto != Veredicto.PENDIENTE:
            if self.motivo_cierre.veredicto_aplicable != self.veredicto:
                errores["motivo_cierre"] = (
                    f"El motivo seleccionado no aplica al veredicto {self.get_veredicto_display()}."
                )

        if errores:
            raise ValidationError(errores)

    # -- Acciones de dominio ----------------------------------------------

    def cerrar(self, veredicto, motivo, comentario_final, usuario=None, estado_final=None):
        """Cierra la solicitud en forma atómica validando integridad."""
        if self.esta_cerrada:
            raise ValidationError("La solicitud ya está cerrada.")

        self.veredicto = veredicto
        self.motivo_cierre = motivo
        self.comentario_final = comentario_final
        self.fecha_cierre = timezone.now()
        if estado_final is not None:
            self.estado_actual = estado_final
        self.full_clean()
        self.save()


class Comentario(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name="comentarios")
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comentarios",
    )
    comentario = models.TextField()
    fecha_comentario = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_comentario"]
        verbose_name = "Comentario"
        verbose_name_plural = "Comentarios"

    def __str__(self):
        autor = self.usuario.get_username() if self.usuario else "anónimo"
        return f"Comentario de {autor} el {self.fecha_comentario:%Y-%m-%d}"


class HistorialAsignacion(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name="historial_asignaciones")
    ejecutivo_anterior = models.ForeignKey(
        EjecutivoRetencion,
        on_delete=models.PROTECT,
        related_name="historial_anterior",
    )
    ejecutivo_nuevo = models.ForeignKey(
        EjecutivoRetencion,
        on_delete=models.PROTECT,
        related_name="historial_nuevo",
    )
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_cambio"]
        verbose_name = "Historial de Asignación"
        verbose_name_plural = "Historial de Asignaciones"

    def __str__(self):
        return (
            f"Solicitud #{self.solicitud_id}: {self.ejecutivo_anterior} → {self.ejecutivo_nuevo}"
        )


class HistorialEstado(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name="historial_estados")
    estado_anterior = models.ForeignKey(EstadoAtencion, related_name="+", on_delete=models.PROTECT)
    estado_nuevo = models.ForeignKey(EstadoAtencion, related_name="+", on_delete=models.PROTECT)
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    usuario_cambio = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cambios_estado",
    )

    class Meta:
        ordering = ["-fecha_cambio"]
        verbose_name = "Historial de Estado"
        verbose_name_plural = "Historial de Estados"

    def __str__(self):
        return (
            f"Solicitud #{self.solicitud_id}: {self.estado_anterior} → {self.estado_nuevo}"
        )


class SolicitudCircuito(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE)
    circuito = models.ForeignKey(Circuito, on_delete=models.CASCADE)
    fecha_asociacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["solicitud", "circuito"],
                name="unique_solicitud_circuito",
            ),
        ]
        verbose_name = "Circuito en Solicitud"
        verbose_name_plural = "Circuitos en Solicitudes"

    def __str__(self):
        return f"Solicitud #{self.solicitud_id} ↔ Circuito #{self.circuito_id}"


class RegistroAsignacion(models.Model):
    """Auditoría: guarda qué estrategia asignó cada caso y qué variables se evaluaron."""

    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name="registros_asignacion",
    )
    rol = models.CharField(max_length=20, choices=RolAsignacion.choices)
    estrategia = models.CharField(max_length=30, choices=EstrategiaAsignacion.choices)
    persona_asignada_id = models.PositiveIntegerField()
    persona_asignada_nombre = models.CharField(max_length=100)
    detalle = models.JSONField(
        default=dict,
        help_text="Candidatos evaluados, scores, razón de la decisión.",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    ejecutado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asignaciones_ejecutadas",
    )

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Registro de Asignación"
        verbose_name_plural = "Registros de Asignación"
        constraints = [
            models.UniqueConstraint(
                fields=["solicitud", "rol"],
                name="unique_asignacion_por_rol",
            ),
        ]

    def __str__(self):
        return f"Solicitud #{self.solicitud_id} {self.rol}: {self.persona_asignada_nombre} ({self.estrategia})"
