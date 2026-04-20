# Generated manually — estrategias de asignación configurables + auditoría.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


ESTRATEGIA_CHOICES = [
    ("ROUND_ROBIN", "Round-robin (por turno)"),
    ("BALANCE_RENTA", "Balance por renta"),
    ("CARGA_CASOS", "Balance por carga de casos"),
    ("PONDERADO", "Distribución ponderada"),
    ("ALEATORIO", "Aleatorio uniforme"),
    ("STICKY_CLIENTE", "Cliente fijo (sticky)"),
    ("RENDIMIENTO", "Por rendimiento histórico"),
]

ROL_CHOICES = [
    ("EJECUTIVO", "Ejecutivo de Retención"),
    ("ANALISTA", "Analista de Retención"),
]


def seed_configuracion_y_grupos(apps, schema_editor):
    """Siembra estrategias por defecto. El grupo Analistas se crea vía post_migrate
    en apps.py porque los permisos se generan después de esta migración."""
    ConfiguracionAsignacion = apps.get_model("portal_retenciones", "ConfiguracionAsignacion")

    # Migrar valor existente (integer → string) si hay una fila previa.
    for fila in ConfiguracionAsignacion.objects.all():
        if fila.valor in (None, ""):
            fila.valor = "0"
            fila.save(update_fields=["valor"])

    # Estrategias por defecto.
    ConfiguracionAsignacion.objects.update_or_create(
        clave="estrategia_ejecutivo",
        defaults={"valor": "ROUND_ROBIN"},
    )
    ConfiguracionAsignacion.objects.update_or_create(
        clave="estrategia_analista",
        defaults={"valor": "ROUND_ROBIN"},
    )


def revertir_seed(apps, schema_editor):
    ConfiguracionAsignacion = apps.get_model("portal_retenciones", "ConfiguracionAsignacion")
    ConfiguracionAsignacion.objects.filter(
        clave__in=["estrategia_ejecutivo", "estrategia_analista"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portal_retenciones", "0004_cierre_y_tipo_caso"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # -- Ejecutivo: peso_asignacion --------------------------------------
        migrations.AddField(
            model_name="ejecutivoretencion",
            name="peso_asignacion",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Peso relativo para la estrategia Ponderado (mayor = más casos).",
            ),
        ),
        # -- Analista: campos de asignación equivalentes a Ejecutivo ----------
        migrations.AddField(
            model_name="analistaretencion",
            name="max_carga_renta",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
                help_text="Tope de renta mensual acumulada. Dejar vacío para sin límite.",
            ),
        ),
        migrations.AddField(
            model_name="analistaretencion",
            name="disponible_asignacion",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="analistaretencion",
            name="peso_asignacion",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Peso relativo para la estrategia Ponderado (mayor = más casos).",
            ),
        ),
        # -- ConfiguracionAsignacion.valor: IntegerField → CharField ----------
        migrations.AlterField(
            model_name="configuracionasignacion",
            name="valor",
            field=models.CharField(default="", max_length=100),
        ),
        # -- Permisos adicionales en Solicitud --------------------------------
        migrations.AlterModelOptions(
            name="solicitud",
            options={
                "ordering": ["-fecha_creacion"],
                "permissions": [
                    ("can_view_menu", "Puede ver el menú de inicio (requerido para login)"),
                    ("can_create_solicitud", "Puede acceder al formulario de Nueva Solicitud"),
                    ("can_view_solicitud_list", "Puede acceder a la lista de Solicitudes"),
                    ("can_view_personal", "Puede acceder a la lista de Personal Activo"),
                    ("can_manage_personnel", "Puede gestionar la asignación de personal a roles"),
                    ("can_configure_asignacion_ejecutivos", "Puede configurar la estrategia de asignación de ejecutivos"),
                    ("can_configure_asignacion_analistas", "Puede configurar la estrategia de asignación de analistas"),
                ],
                "verbose_name": "Solicitud",
                "verbose_name_plural": "Solicitudes",
            },
        ),
        # -- Modelo de auditoría: RegistroAsignacion --------------------------
        migrations.CreateModel(
            name="RegistroAsignacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rol", models.CharField(max_length=20, choices=ROL_CHOICES)),
                ("estrategia", models.CharField(max_length=30, choices=ESTRATEGIA_CHOICES)),
                ("persona_asignada_id", models.PositiveIntegerField()),
                ("persona_asignada_nombre", models.CharField(max_length=100)),
                ("detalle", models.JSONField(default=dict, help_text="Candidatos evaluados, scores, razón de la decisión.")),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                (
                    "ejecutado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="asignaciones_ejecutadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "solicitud",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="registros_asignacion",
                        to="portal_retenciones.solicitud",
                    ),
                ),
            ],
            options={
                "verbose_name": "Registro de Asignación",
                "verbose_name_plural": "Registros de Asignación",
                "ordering": ["-fecha"],
            },
        ),
        migrations.AddConstraint(
            model_name="registroasignacion",
            constraint=models.UniqueConstraint(
                fields=("solicitud", "rol"),
                name="unique_asignacion_por_rol",
            ),
        ),
        # -- Data migration: defaults + grupo Analistas -----------------------
        migrations.RunPython(seed_configuracion_y_grupos, revertir_seed),
    ]
