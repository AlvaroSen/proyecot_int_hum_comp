import pandas as pd
import urllib
from sqlalchemy import create_engine
from django.core.management.base import BaseCommand
from portal_retenciones.models import Cliente, Circuito, Solicitud
import os
from dotenv import load_dotenv

load_dotenv()

SQL_SERVER = os.getenv("DB_HOST")
SQL_DATABASE = os.getenv("DB_NAME")
SQL_USER = os.getenv("DB_USER")
SQL_PASSWORD = os.getenv("DB_PASS")
SQL_DRIVER = os.getenv("DB_DRIVER")

QUERY_CLIENTES = "SELECT ruc, razon_social, fecha_registro, estado FROM RETENCION.CLIENTES"

QUERY_CIRCUITOS = """
    SELECT
        c.nombre_circuito,
        c.tipo_servicio,
        c.estado,
        c.renta_mensual,
        c.fecha_creacion,
        p.ruc
    FROM
        RETENCION.CIRCUITOS c
    INNER JOIN
        RETENCION.CLIENTES p ON c.cliente_id = p.cliente_id
"""

class Command(BaseCommand):
    help = 'Migra Clientes y Circuitos de SQL Server a SQLite via Pandas, mapeando por RUC.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Iniciando migración completa (Clientes y Circuitos) ---'))

        try:
            self.stdout.write(self.style.WARNING('Borrando datos transaccionales antiguos de SQLite...'))
            Solicitud.objects.all().delete()
            Circuito.objects.all().delete()
            Cliente.objects.all().delete()
            self.stdout.write(self.style.WARNING('Datos antiguos borrados (Solicitud, Circuito, Cliente).'))

            driver_safe = urllib.parse.quote_plus(SQL_DRIVER)
            connection_url = f"mssql+pyodbc://{SQL_USER}:{urllib.parse.quote_plus(SQL_PASSWORD)}@{SQL_SERVER}/{SQL_DATABASE}?driver={driver_safe}"
            self.stdout.write(f'Conectando a {SQL_SERVER}...')
            engine = create_engine(connection_url)

            self.stdout.write('--- Paso 1: Migrando Clientes ---')
            df_clientes = pd.read_sql(QUERY_CLIENTES, engine)
            self.stdout.write(f'Se encontraron {len(df_clientes)} clientes en SQL Server.')

            ruc_a_nuevo_id_map = {}

            for index, row in df_clientes.iterrows():
                cliente, created = Cliente.objects.get_or_create(
                    ruc=row['ruc'],
                    defaults={
                        'razon_social': row['razon_social'],
                        'estado': row['estado'],
                        'fecha_registro': row['fecha_registro']
                    }
                )
                ruc_a_nuevo_id_map[cliente.ruc] = cliente.id
            
            self.stdout.write(self.style.SUCCESS(f'Clientes creados en SQLite: {len(ruc_a_nuevo_id_map)}'))

            self.stdout.write('--- Paso 2: Migrando Circuitos ---')
            df_circuitos = pd.read_sql(QUERY_CIRCUITOS, engine)
            self.stdout.write(f'Se encontraron {len(df_circuitos)} circuitos en SQL Server.')

            circuitos_creados = 0
            circuitos_sin_padre = 0
            
            circuitos_a_crear = []

            for index, row in df_circuitos.iterrows():
                nuevo_cliente_id = ruc_a_nuevo_id_map.get(row['ruc'])

                if nuevo_cliente_id:
                    circuitos_a_crear.append(
                        Circuito(
                            cliente_id=nuevo_cliente_id,
                            nombre_circuito=row['nombre_circuito'],
                            tipo_servicio=row['tipo_servicio'],
                            estado=row['estado'],
                            renta_mensual=row['renta_mensual'],
                            fecha_creacion=row['fecha_creacion']
                        )
                    )
                    circuitos_creados += 1
                else:
                    circuitos_sin_padre += 1

            self.stdout.write(f'Insertando {len(circuitos_a_crear)} circuitos en SQLite (esto es rápido)...')
            Circuito.objects.bulk_create(circuitos_a_crear)

            self.stdout.write(self.style.SUCCESS(f'--- ¡Migración completada! ---'))
            self.stdout.write(f'Total Clientes migrados: {len(ruc_a_nuevo_id_map)}')
            self.stdout.write(f'Total Circuitos migrados: {circuitos_creados}')
            self.stdout.write(self.style.WARNING(f'Circuitos sin padre (omitidos): {circuitos_sin_padre}'))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error durante la migración: {e}'))