# Generated manually — refactor de modelos (puntos 1-8).
# Convierte Comentario.usuario y HistorialEstado.usuario_cambio de CharField a
# ForeignKey(User), preservando los datos existentes mediante lookup por username.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrar_usuarios_a_fk(apps, schema_editor):
    """Copia el username almacenado como string al FK hacia auth.User."""
    User = apps.get_model(settings.AUTH_USER_MODEL)
    Comentario = apps.get_model("portal_retenciones", "Comentario")
    HistorialEstado = apps.get_model("portal_retenciones", "HistorialEstado")

    def resolver_usuario(valor):
        if not valor:
            return None
        valor = valor.strip()
        if not valor:
            return None
        # Primero intentamos username directo, luego first/last name.
        user = User.objects.filter(username__iexact=valor).first()
        if user:
            return user
        partes = valor.split()
        if len(partes) >= 2:
            user = User.objects.filter(
                first_name__iexact=partes[0],
                last_name__iexact=" ".join(partes[1:]),
            ).first()
            if user:
                return user
        return None

    for comentario in Comentario.objects.all():
        comentario.usuario_tmp = resolver_usuario(comentario.usuario)
        comentario.save(update_fields=["usuario_tmp"])

    for historial in HistorialEstado.objects.all():
        historial.usuario_cambio_tmp = resolver_usuario(historial.usuario_cambio)
        historial.save(update_fields=["usuario_cambio_tmp"])


def revertir_usuarios_a_string(apps, schema_editor):
    """Reversión: copia el username del FK de vuelta al CharField temporal."""
    Comentario = apps.get_model("portal_retenciones", "Comentario")
    HistorialEstado = apps.get_model("portal_retenciones", "HistorialEstado")

    for comentario in Comentario.objects.all():
        if comentario.usuario_tmp_id:
            comentario.usuario = comentario.usuario_tmp.username
            comentario.save(update_fields=["usuario"])

    for historial in HistorialEstado.objects.all():
        if historial.usuario_cambio_tmp_id:
            historial.usuario_cambio = historial.usuario_cambio_tmp.username
            historial.save(update_fields=["usuario_cambio"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal_retenciones", "0002_configuracionasignacion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # -- Meta options (ordering / verbose_name) ---------------------------
        migrations.AlterModelOptions(
            name="analistaretencion",
            options={
                "ordering": ["nombre"],
                "verbose_name": "Analista de Retención",
                "verbose_name_plural": "Analistas de Retención",
            },
        ),
        migrations.AlterModelOptions(
            name="circuito",
            options={
                "ordering": ["nombre_circuito"],
                "verbose_name": "Circuito",
                "verbose_name_plural": "Circuitos",
            },
        ),
        migrations.AlterModelOptions(
            name="cliente",
            options={
                "ordering": ["razon_social"],
                "verbose_name": "Cliente",
                "verbose_name_plural": "Clientes",
            },
        ),
        migrations.AlterModelOptions(
            name="comentario",
            options={
                "ordering": ["-fecha_comentario"],
                "verbose_name": "Comentario",
                "verbose_name_plural": "Comentarios",
            },
        ),
        migrations.AlterModelOptions(
            name="configuracionasignacion",
            options={
                "verbose_name": "Configuración de Asignación",
                "verbose_name_plural": "Configuración de Asignación",
            },
        ),
        migrations.AlterModelOptions(
            name="ejecutivoretencion",
            options={
                "ordering": ["nombre"],
                "verbose_name": "Ejecutivo de Retención",
                "verbose_name_plural": "Ejecutivos de Retención",
            },
        ),
        migrations.AlterModelOptions(
            name="estadoatencion",
            options={
                "ordering": ["nombre_estado"],
                "verbose_name": "Estado de Atención",
                "verbose_name_plural": "Estados de Atención",
            },
        ),
        migrations.AlterModelOptions(
            name="historialasignacion",
            options={
                "ordering": ["-fecha_cambio"],
                "verbose_name": "Historial de Asignación",
                "verbose_name_plural": "Historial de Asignaciones",
            },
        ),
        migrations.AlterModelOptions(
            name="historialestado",
            options={
                "ordering": ["-fecha_cambio"],
                "verbose_name": "Historial de Estado",
                "verbose_name_plural": "Historial de Estados",
            },
        ),
        migrations.AlterModelOptions(
            name="nivelaprobacion",
            options={
                "ordering": ["orden"],
                "verbose_name": "Nivel de Aprobación",
                "verbose_name_plural": "Niveles de Aprobación",
            },
        ),
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
                ],
                "verbose_name": "Solicitud",
                "verbose_name_plural": "Solicitudes",
            },
        ),
        migrations.AlterModelOptions(
            name="solicitudcircuito",
            options={
                "verbose_name": "Circuito en Solicitud",
                "verbose_name_plural": "Circuitos en Solicitudes",
            },
        ),
        migrations.AlterUniqueTogether(
            name="solicitudcircuito",
            unique_together=set(),
        ),
        # -- AlterFields simples ---------------------------------------------
        migrations.AlterField(
            model_name="circuito",
            name="cliente",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="circuitos",
                to="portal_retenciones.cliente",
            ),
        ),
        migrations.AlterField(
            model_name="circuito",
            name="estado",
            field=models.CharField(
                choices=[("Activo", "Activo"), ("Inactivo", "Inactivo")],
                default="Activo",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="circuito",
            name="renta_mensual",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AlterField(
            model_name="circuito",
            name="tipo_servicio",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Internet", "Internet"),
                    ("Telefonia", "Telefonía"),
                    ("Cable", "Cable"),
                    ("Datos", "Datos"),
                    ("Otro", "Otro"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="estado",
            field=models.CharField(
                choices=[("Activo", "Activo"), ("Inactivo", "Inactivo")],
                default="Activo",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="cliente",
            name="ruc",
            field=models.CharField(
                max_length=11,
                unique=True,
                validators=[
                    django.core.validators.RegexValidator(
                        message="El RUC debe tener exactamente 11 dígitos numéricos.",
                        regex=r"^\d{11}$",
                    )
                ],
            ),
        ),
        migrations.AlterField(
            model_name="comentario",
            name="solicitud",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="comentarios",
                to="portal_retenciones.solicitud",
            ),
        ),
        migrations.AlterField(
            model_name="ejecutivoretencion",
            name="max_carga_renta",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
            ),
        ),
        migrations.AlterField(
            model_name="historialasignacion",
            name="solicitud",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="historial_asignaciones",
                to="portal_retenciones.solicitud",
            ),
        ),
        migrations.AlterField(
            model_name="historialestado",
            name="solicitud",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="historial_estados",
                to="portal_retenciones.solicitud",
            ),
        ),
        migrations.AlterField(
            model_name="solicitud",
            name="analista",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes",
                to="portal_retenciones.analistaretencion",
            ),
        ),
        migrations.AlterField(
            model_name="solicitud",
            name="circuitos",
            field=models.ManyToManyField(
                related_name="solicitudes",
                through="portal_retenciones.SolicitudCircuito",
                to="portal_retenciones.circuito",
            ),
        ),
        migrations.AlterField(
            model_name="solicitud",
            name="cliente",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes",
                to="portal_retenciones.cliente",
            ),
        ),
        migrations.AlterField(
            model_name="solicitud",
            name="ejecutivo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes",
                to="portal_retenciones.ejecutivoretencion",
            ),
        ),
        migrations.AlterField(
            model_name="solicitud",
            name="estado_actual",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes",
                to="portal_retenciones.estadoatencion",
            ),
        ),
        migrations.AlterField(
            model_name="solicitud",
            name="nivel_aprobacion",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitudes",
                to="portal_retenciones.nivelaprobacion",
            ),
        ),
        migrations.AddConstraint(
            model_name="solicitudcircuito",
            constraint=models.UniqueConstraint(
                fields=("solicitud", "circuito"),
                name="unique_solicitud_circuito",
            ),
        ),
        # -- Migración de datos: CharField → FK(User) -------------------------
        migrations.AddField(
            model_name="comentario",
            name="usuario_tmp",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="historialestado",
            name="usuario_cambio_tmp",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(migrar_usuarios_a_fk, revertir_usuarios_a_string),
        migrations.RemoveField(
            model_name="comentario",
            name="usuario",
        ),
        migrations.RemoveField(
            model_name="historialestado",
            name="usuario_cambio",
        ),
        migrations.RenameField(
            model_name="comentario",
            old_name="usuario_tmp",
            new_name="usuario",
        ),
        migrations.RenameField(
            model_name="historialestado",
            old_name="usuario_cambio_tmp",
            new_name="usuario_cambio",
        ),
        migrations.AlterField(
            model_name="comentario",
            name="usuario",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="comentarios",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="historialestado",
            name="usuario_cambio",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cambios_estado",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
