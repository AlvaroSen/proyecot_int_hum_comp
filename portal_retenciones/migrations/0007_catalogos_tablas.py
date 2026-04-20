# Generated manually — convierte TextChoices hardcodeados a tablas catálogo.

import django.db.models.deletion
from django.db import migrations, models


SEED_TIPOS_SERVICIO = [
    ("Internet", "Internet"),
    ("Telefonia", "Telefonía"),
    ("Cable", "Cable"),
    ("Datos", "Datos"),
    ("Otro", "Otro"),
]

SEED_TIPOS_CASO = [
    ("BAJA_APC", "Baja APC", "Cliente envió baja formal (carta o correo)."),
    ("RETENCION", "Retención", "Cliente con intenciones pero sin baja formal."),
]

SEED_MOTIVOS_AUSENCIA = [
    ("OCUPADO", "Ocupado"),
    ("VACACIONES", "Vacaciones"),
    ("BAJA_MEDICA", "Baja médica"),
    ("LICENCIA", "Licencia / Permiso"),
    ("CAPACITACION", "Capacitación"),
    ("OTRO", "Otro"),
]


def seed_catalogos(apps, schema_editor):
    TipoServicio = apps.get_model("portal_retenciones", "TipoServicio")
    TipoCaso = apps.get_model("portal_retenciones", "TipoCaso")
    MotivoAusencia = apps.get_model("portal_retenciones", "MotivoAusencia")

    for codigo, nombre in SEED_TIPOS_SERVICIO:
        TipoServicio.objects.update_or_create(codigo=codigo, defaults={"nombre": nombre, "activo": True})
    for codigo, nombre, descripcion in SEED_TIPOS_CASO:
        TipoCaso.objects.update_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "descripcion": descripcion, "activo": True},
        )
    for codigo, nombre in SEED_MOTIVOS_AUSENCIA:
        MotivoAusencia.objects.update_or_create(codigo=codigo, defaults={"nombre": nombre, "activo": True})


def migrar_datos_a_fks(apps, schema_editor):
    """Mapea los valores string existentes a sus filas en las nuevas tablas."""
    TipoServicio = apps.get_model("portal_retenciones", "TipoServicio")
    TipoCaso = apps.get_model("portal_retenciones", "TipoCaso")
    MotivoAusencia = apps.get_model("portal_retenciones", "MotivoAusencia")
    Circuito = apps.get_model("portal_retenciones", "Circuito")
    Solicitud = apps.get_model("portal_retenciones", "Solicitud")
    Ejecutivo = apps.get_model("portal_retenciones", "EjecutivoRetencion")
    Analista = apps.get_model("portal_retenciones", "AnalistaRetencion")

    tipos_servicio = {t.codigo: t for t in TipoServicio.objects.all()}
    tipos_caso = {t.codigo: t for t in TipoCaso.objects.all()}
    motivos = {m.codigo: m for m in MotivoAusencia.objects.all()}

    for c in Circuito.objects.all():
        valor = c.tipo_servicio_old
        if valor and valor in tipos_servicio:
            c.tipo_servicio_new = tipos_servicio[valor]
            c.save(update_fields=["tipo_servicio_new"])

    for s in Solicitud.objects.all():
        valor = s.tipo_caso_old or "RETENCION"
        if valor in tipos_caso:
            s.tipo_caso_new = tipos_caso[valor]
            s.save(update_fields=["tipo_caso_new"])

    for persona in list(Ejecutivo.objects.all()) + list(Analista.objects.all()):
        valor = persona.motivo_no_disponible_old
        if valor and valor in motivos:
            persona.motivo_no_disponible_new = motivos[valor]
            persona.save(update_fields=["motivo_no_disponible_new"])


def revertir_seed(apps, schema_editor):
    """Limpia los catálogos (sin revertir datos, se asume reversión total)."""
    for model_name in ("MotivoAusencia", "TipoCaso", "TipoServicio"):
        apps.get_model("portal_retenciones", model_name).objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portal_retenciones", "0006_motivo_no_disponible"),
    ]

    operations = [
        # -- 1) Crear las tres tablas catálogo ------------------------------
        migrations.CreateModel(
            name="TipoServicio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=30, unique=True)),
                ("nombre", models.CharField(max_length=80)),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Tipo de Servicio",
                "verbose_name_plural": "Tipos de Servicio",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="TipoCaso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=30, unique=True)),
                ("nombre", models.CharField(max_length=80)),
                ("descripcion", models.TextField(blank=True, default="")),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Tipo de Caso",
                "verbose_name_plural": "Tipos de Caso",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="MotivoAusencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=30, unique=True)),
                ("nombre", models.CharField(max_length=80)),
                ("descripcion", models.TextField(blank=True, default="")),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Motivo de Ausencia",
                "verbose_name_plural": "Motivos de Ausencia",
                "ordering": ["nombre"],
            },
        ),
        # -- 2) Sembrar catálogos --------------------------------------------
        migrations.RunPython(seed_catalogos, revertir_seed),
        # -- 3) Renombrar campos actuales para liberar el nombre final -------
        migrations.RenameField("circuito", "tipo_servicio", "tipo_servicio_old"),
        migrations.RenameField("solicitud", "tipo_caso", "tipo_caso_old"),
        migrations.RenameField("ejecutivoretencion", "motivo_no_disponible", "motivo_no_disponible_old"),
        migrations.RenameField("analistaretencion", "motivo_no_disponible", "motivo_no_disponible_old"),
        # -- 4) Agregar los nuevos FKs (temporales, con sufijo _new) ---------
        migrations.AddField(
            model_name="circuito",
            name="tipo_servicio_new",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="circuitos",
                to="portal_retenciones.tiposervicio",
            ),
        ),
        migrations.AddField(
            model_name="solicitud",
            name="tipo_caso_new",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes",
                to="portal_retenciones.tipocaso",
            ),
        ),
        migrations.AddField(
            model_name="ejecutivoretencion",
            name="motivo_no_disponible_new",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="portal_retenciones.motivoausencia",
            ),
        ),
        migrations.AddField(
            model_name="analistaretencion",
            name="motivo_no_disponible_new",
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="portal_retenciones.motivoausencia",
            ),
        ),
        # -- 5) Migrar datos string → FK --------------------------------------
        migrations.RunPython(migrar_datos_a_fks, migrations.RunPython.noop),
        # -- 6) Eliminar los campos viejos ------------------------------------
        migrations.RemoveField(model_name="circuito", name="tipo_servicio_old"),
        migrations.RemoveField(model_name="solicitud", name="tipo_caso_old"),
        migrations.RemoveField(model_name="ejecutivoretencion", name="motivo_no_disponible_old"),
        migrations.RemoveField(model_name="analistaretencion", name="motivo_no_disponible_old"),
        # -- 7) Renombrar los nuevos FK al nombre final -----------------------
        migrations.RenameField("circuito", "tipo_servicio_new", "tipo_servicio"),
        migrations.RenameField("solicitud", "tipo_caso_new", "tipo_caso"),
        migrations.RenameField("ejecutivoretencion", "motivo_no_disponible_new", "motivo_no_disponible"),
        migrations.RenameField("analistaretencion", "motivo_no_disponible_new", "motivo_no_disponible"),
        # -- 8) Solicitud.tipo_caso: ahora es obligatorio (no-null) -----------
        migrations.AlterField(
            model_name="solicitud",
            name="tipo_caso",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes",
                to="portal_retenciones.tipocaso",
                help_text="Tipo de caso. Editable solo mientras la solicitud no esté cerrada.",
            ),
        ),
    ]
