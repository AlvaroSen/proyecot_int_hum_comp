from django.db import migrations, models


MOTIVO_CHOICES = [
    ("OCUPADO", "Ocupado"),
    ("VACACIONES", "Vacaciones"),
    ("BAJA_MEDICA", "Baja médica"),
    ("LICENCIA", "Licencia / Permiso"),
    ("CAPACITACION", "Capacitación"),
    ("OTRO", "Otro"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("portal_retenciones", "0005_estrategias_asignacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="ejecutivoretencion",
            name="motivo_no_disponible",
            field=models.CharField(
                blank=True,
                null=True,
                choices=MOTIVO_CHOICES,
                max_length=20,
                help_text="Motivo de no disponibilidad (si aplica).",
            ),
        ),
        migrations.AddField(
            model_name="analistaretencion",
            name="motivo_no_disponible",
            field=models.CharField(
                blank=True,
                null=True,
                choices=MOTIVO_CHOICES,
                max_length=20,
                help_text="Motivo de no disponibilidad (si aplica).",
            ),
        ),
    ]
