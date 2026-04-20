# Generated manually — agrega cierre de casos, tipo de caso y catálogo de motivos.

import django.db.models.deletion
from django.db import migrations, models


ESTADOS_SEED = [
    ("Registrado", "NUEVO", False),
    ("En Análisis", "EN_ATENCION", False),
    ("Aprobado", "APROBADO", True),
    ("Rechazado", "RECHAZADO", True),
    ("Baja Ejecutada", "BAJA_EJECUTADA", True),
]

MOTIVOS_SEED = [
    # Retenidos
    ("RET_DESCUENTO", "Descuento aplicado", "RETENIDO"),
    ("RET_UPGRADE", "Upgrade / mejora de servicio", "RETENIDO"),
    ("RET_CAMBIO_PLAN", "Cambio de plan", "RETENIDO"),
    ("RET_COMPROMISO", "Compromiso escrito / acuerdo", "RETENIDO"),
    ("RET_BENEFICIO", "Beneficio adicional otorgado", "RETENIDO"),
    # No retenidos
    ("NRE_PRECIO", "Precio de la competencia", "NO_RETENIDO"),
    ("NRE_CALIDAD", "Problemas de calidad del servicio", "NO_RETENIDO"),
    ("NRE_COBERTURA", "Mudanza a zona sin cobertura", "NO_RETENIDO"),
    ("NRE_FALLECIMIENTO", "Fallecimiento del titular", "NO_RETENIDO"),
    ("NRE_DECISION", "Decisión final del cliente", "NO_RETENIDO"),
    ("NRE_FACTURACION", "Problemas de facturación", "NO_RETENIDO"),
    # Desestimados
    ("DES_DUPLICADA", "Solicitud duplicada", "DESESTIMADO"),
    ("DES_DATOS", "Datos del cliente incorrectos", "DESESTIMADO"),
    ("DES_NO_CONTACTABLE", "Cliente no contactable", "DESESTIMADO"),
    ("DES_FUERA_SCOPE", "Fuera de alcance del área", "DESESTIMADO"),
]


def seed_catalogos(apps, schema_editor):
    EstadoAtencion = apps.get_model("portal_retenciones", "EstadoAtencion")
    MotivoCierre = apps.get_model("portal_retenciones", "MotivoCierre")

    # Rellenar código y es_final en estados existentes.
    for nombre, codigo, es_final in ESTADOS_SEED:
        EstadoAtencion.objects.filter(nombre_estado=nombre).update(
            codigo=codigo,
            es_final=es_final,
        )
    # Para cualquier estado que no esté en el seed, derivar código del nombre.
    for estado in EstadoAtencion.objects.filter(codigo__isnull=True):
        estado.codigo = estado.nombre_estado.upper().replace(" ", "_")[:30]
        estado.save(update_fields=["codigo"])

    # Sembrar motivos iniciales.
    for codigo, descripcion, veredicto in MOTIVOS_SEED:
        MotivoCierre.objects.update_or_create(
            codigo=codigo,
            defaults={
                "descripcion": descripcion,
                "veredicto_aplicable": veredicto,
                "activo": True,
            },
        )


def limpiar_catalogos(apps, schema_editor):
    MotivoCierre = apps.get_model("portal_retenciones", "MotivoCierre")
    MotivoCierre.objects.filter(codigo__in=[m[0] for m in MOTIVOS_SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portal_retenciones", "0003_refactor_modelos"),
    ]

    operations = [
        # -- Catálogo: MotivoCierre ------------------------------------------
        migrations.CreateModel(
            name="MotivoCierre",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=40, unique=True)),
                ("descripcion", models.CharField(max_length=150)),
                (
                    "veredicto_aplicable",
                    models.CharField(
                        choices=[
                            ("PENDIENTE", "Pendiente"),
                            ("RETENIDO", "Retenido"),
                            ("NO_RETENIDO", "No retenido"),
                            ("DESESTIMADO", "Desestimado"),
                        ],
                        help_text="Veredicto al que aplica este motivo.",
                        max_length=20,
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Motivo de Cierre",
                "verbose_name_plural": "Motivos de Cierre",
                "ordering": ["veredicto_aplicable", "descripcion"],
            },
        ),
        # -- EstadoAtencion: nuevos campos (codigo nullable inicialmente) ----
        migrations.AddField(
            model_name="estadoatencion",
            name="codigo",
            field=models.CharField(
                max_length=30,
                null=True,
                help_text="Código estable para identificar el estado en código (p.ej. NUEVO, EN_ATENCION, CERRADO).",
            ),
        ),
        migrations.AddField(
            model_name="estadoatencion",
            name="es_final",
            field=models.BooleanField(
                default=False,
                help_text="Marca que este estado cierra la solicitud (terminal).",
            ),
        ),
        # -- Solicitud: campos de cierre y tipo_caso --------------------------
        migrations.AddField(
            model_name="solicitud",
            name="tipo_caso",
            field=models.CharField(
                choices=[("BAJA_APC", "Baja APC"), ("RETENCION", "Retención")],
                default="RETENCION",
                help_text="Tipo de caso. Editable solo mientras la solicitud no esté cerrada.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="veredicto",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente"),
                    ("RETENIDO", "Retenido"),
                    ("NO_RETENIDO", "No retenido"),
                    ("DESESTIMADO", "Desestimado"),
                ],
                default="PENDIENTE",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="motivo_cierre",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes",
                to="portal_retenciones.motivocierre",
            ),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="comentario_final",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="fecha_cierre",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # -- Data seed --------------------------------------------------------
        migrations.RunPython(seed_catalogos, limpiar_catalogos),
        # -- EstadoAtencion.codigo: convertir a unique y NOT NULL ------------
        migrations.AlterField(
            model_name="estadoatencion",
            name="codigo",
            field=models.CharField(
                max_length=30,
                unique=True,
                help_text="Código estable para identificar el estado en código (p.ej. NUEVO, EN_ATENCION, CERRADO).",
            ),
        ),
    ]
