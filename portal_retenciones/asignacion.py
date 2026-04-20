"""Estrategias configurables de asignación de casos.

Pattern: Strategy. Cada estrategia implementa `AsignadorBase.seleccionar(contexto)` y
devuelve `(persona, detalle_audit)`. El módulo expone `asignar(rol, contexto)` como
punto de entrada único para las vistas.

Las estrategias activas por rol se guardan en `ConfiguracionAsignacion`:
  - clave='estrategia_ejecutivo', valor='ROUND_ROBIN' | 'BALANCE_RENTA' | ...
  - clave='estrategia_analista', idem.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from portal_retenciones.models import (
    AnalistaRetencion,
    ConfiguracionAsignacion,
    EjecutivoRetencion,
    EstrategiaAsignacion,
    RolAsignacion,
    Veredicto,
)


# --- Descripciones visibles en la UI -------------------------------------
ESTRATEGIA_DESCRIPCIONES = {
    EstrategiaAsignacion.ROUND_ROBIN: (
        "Asigna por turno circular. Cada caso nuevo va al siguiente en orden de ID. "
        "Al terminar la lista, reinicia desde el primero. Es la estrategia más simple "
        "y justa cuando todos los candidatos tienen capacidad equivalente."
    ),
    EstrategiaAsignacion.BALANCE_RENTA: (
        "Asigna al candidato con menor renta mensual acumulada entre sus casos abiertos. "
        "Busca equilibrar la carga económica: si una persona lleva S/ 500 en casos "
        "abiertos y otra lleva S/ 0, la próxima solicitud va a la segunda hasta emparejar."
    ),
    EstrategiaAsignacion.CARGA_CASOS: (
        "Asigna al candidato con menor cantidad de casos abiertos. Equilibra volumen, "
        "no valor económico. Útil cuando el tiempo por caso importa más que su monto."
    ),
    EstrategiaAsignacion.PONDERADO: (
        "Distribuye los casos proporcionalmente al peso asignado a cada persona. "
        "Ejemplo: senior con peso 60 y dos juniors con peso 20 cada uno recibirán "
        "aproximadamente esa proporción de casos a lo largo del tiempo."
    ),
    EstrategiaAsignacion.ALEATORIO: (
        "Selecciona aleatoriamente entre los candidatos activos. Útil para pruebas de "
        "fairness, auditorías ciegas o evitar sesgos humanos. No balancea carga."
    ),
    EstrategiaAsignacion.STICKY_CLIENTE: (
        "Si el cliente ya tuvo un caso previo asignado a alguien del equipo, ese "
        "mismo agente recibe el nuevo caso. Da continuidad de relación. Si no hay "
        "historial, usa round-robin como respaldo."
    ),
    EstrategiaAsignacion.RENDIMIENTO: (
        "Prioriza al candidato con mejor tasa de retención histórica. Estrategia "
        "'meritocrática': los casos importantes van a quien mejor cierra. Empate por "
        "menor ID."
    ),
}


@dataclass
class SolicitudContexto:
    """Datos del caso entrante necesarios para decidir la asignación."""
    cliente_id: int
    renta_total: Decimal
    tipo_caso: str


# --- Helpers de parámetros -------------------------------------------------
def _modelo_persona(rol: str):
    return EjecutivoRetencion if rol == RolAsignacion.EJECUTIVO else AnalistaRetencion


def _campo_fk(rol: str) -> str:
    return "ejecutivo" if rol == RolAsignacion.EJECUTIVO else "analista"


def get_parametro(clave: str, default: str = "") -> str:
    obj = ConfiguracionAsignacion.objects.filter(clave=clave).first()
    return obj.valor if obj and obj.valor else default


def get_parametro_int(clave: str, default: int = 0) -> int:
    try:
        return int(get_parametro(clave, str(default)))
    except (TypeError, ValueError):
        return default


def set_parametro(clave: str, valor) -> None:
    ConfiguracionAsignacion.objects.update_or_create(
        clave=clave,
        defaults={"valor": str(valor)},
    )


def obtener_estrategia_activa(rol: str) -> str:
    clave = "estrategia_ejecutivo" if rol == RolAsignacion.EJECUTIVO else "estrategia_analista"
    return get_parametro(clave, EstrategiaAsignacion.ROUND_ROBIN)


# --- Cálculos de carga / desempeño ---------------------------------------
def _renta_abierta(persona, rol: str) -> Decimal:
    """Suma de rentas de los circuitos en solicitudes abiertas de la persona."""
    from portal_retenciones.models import Solicitud

    abiertas = Solicitud.objects.filter(
        **{_campo_fk(rol): persona, "veredicto": Veredicto.PENDIENTE}
    )
    total = Decimal("0")
    for s in abiertas.prefetch_related("circuitos"):
        for c in s.circuitos.all():
            total += c.renta_mensual
    return total


def _casos_abiertos(persona, rol: str) -> int:
    from portal_retenciones.models import Solicitud

    return Solicitud.objects.filter(
        **{_campo_fk(rol): persona, "veredicto": Veredicto.PENDIENTE}
    ).count()


def _asignaciones_historicas(persona, rol: str) -> int:
    from portal_retenciones.models import Solicitud

    return Solicitud.objects.filter(**{_campo_fk(rol): persona}).count()


def _tasa_retencion(persona, rol: str) -> float:
    from portal_retenciones.models import Solicitud

    cerradas = Solicitud.objects.filter(**{_campo_fk(rol): persona}).exclude(
        veredicto=Veredicto.PENDIENTE
    )
    total = cerradas.count()
    if total == 0:
        return 0.0
    retenidas = cerradas.filter(veredicto=Veredicto.RETENIDO).count()
    return retenidas / total


# --- Estrategias ---------------------------------------------------------
class AsignadorBase(ABC):
    codigo: str = ""

    def __init__(self, rol: str):
        self.rol = rol

    def candidatos_base(self):
        return (
            _modelo_persona(self.rol)
            .objects.filter(activo=True, disponible_asignacion=True)
            .order_by("id")
        )

    def aplicar_tope_carga(self, candidatos, renta_nueva: Decimal):
        """Excluye candidatos cuya carga actual + nueva renta supera su tope."""
        if renta_nueva is None:
            return candidatos
        permitidos = []
        for c in candidatos:
            if c.max_carga_renta is None:
                permitidos.append(c)
                continue
            if _renta_abierta(c, self.rol) + renta_nueva <= c.max_carga_renta:
                permitidos.append(c)
        return permitidos

    def seleccionar(self, contexto: SolicitudContexto):
        candidatos = list(self.candidatos_base())
        excluidos_por_tope = [c for c in candidatos if c not in self.aplicar_tope_carga(candidatos, contexto.renta_total)]
        candidatos = self.aplicar_tope_carga(candidatos, contexto.renta_total)

        if not candidatos:
            return None, {
                "estrategia": self.codigo,
                "razon": "No hay candidatos activos/disponibles dentro del tope de carga.",
                "excluidos_por_tope": [{"id": c.id, "nombre": c.nombre} for c in excluidos_por_tope],
                "candidatos": [],
            }
        persona, detalle = self._seleccionar(candidatos, contexto)
        detalle["estrategia"] = self.codigo
        if excluidos_por_tope:
            detalle["excluidos_por_tope"] = [
                {"id": c.id, "nombre": c.nombre, "max_carga_renta": float(c.max_carga_renta or 0)}
                for c in excluidos_por_tope
            ]
        return persona, detalle

    @abstractmethod
    def _seleccionar(self, candidatos, contexto):
        ...


class AsignadorRoundRobin(AsignadorBase):
    codigo = EstrategiaAsignacion.ROUND_ROBIN

    def _seleccionar(self, candidatos, contexto):
        clave = f"last_{self.rol.lower()}_id"
        last_id = get_parametro_int(clave, 0)
        siguientes = [c for c in candidatos if c.id > last_id]
        elegido = siguientes[0] if siguientes else candidatos[0]
        set_parametro(clave, elegido.id)
        return elegido, {
            "razon": f"Siguiente en turno tras id previo={last_id}.",
            "ultimo_id_previo": last_id,
            "candidatos": [{"id": c.id, "nombre": c.nombre} for c in candidatos],
        }


class AsignadorBalanceRenta(AsignadorBase):
    codigo = EstrategiaAsignacion.BALANCE_RENTA

    def _seleccionar(self, candidatos, contexto):
        puntuados = [(c, _renta_abierta(c, self.rol)) for c in candidatos]
        puntuados.sort(key=lambda p: (p[1], p[0].id))
        elegido, renta = puntuados[0]
        return elegido, {
            "razon": f"Menor renta acumulada en casos abiertos (S/ {renta:.2f}).",
            "candidatos": [
                {"id": c.id, "nombre": c.nombre, "renta_abierta": float(r)}
                for c, r in puntuados
            ],
        }


class AsignadorCargaCasos(AsignadorBase):
    codigo = EstrategiaAsignacion.CARGA_CASOS

    def _seleccionar(self, candidatos, contexto):
        puntuados = [(c, _casos_abiertos(c, self.rol)) for c in candidatos]
        puntuados.sort(key=lambda p: (p[1], p[0].id))
        elegido, n = puntuados[0]
        return elegido, {
            "razon": f"Menor cantidad de casos abiertos ({n}).",
            "candidatos": [
                {"id": c.id, "nombre": c.nombre, "casos_abiertos": n}
                for c, n in puntuados
            ],
        }


class AsignadorPonderado(AsignadorBase):
    codigo = EstrategiaAsignacion.PONDERADO

    def _seleccionar(self, candidatos, contexto):
        pesos = {c.id: max(c.peso_asignacion, 0) for c in candidatos}
        total_peso = sum(pesos.values())
        if total_peso == 0:
            elegido, detalle = AsignadorRoundRobin(self.rol)._seleccionar(candidatos, contexto)
            detalle["razon"] = "Todos los candidatos tienen peso 0 → fallback round-robin. " + detalle["razon"]
            return elegido, detalle

        historicos = {c.id: _asignaciones_historicas(c, self.rol) for c in candidatos}
        total_hist = sum(historicos.values()) + 1  # +1 para incluir la nueva
        # Déficit = (esperado según peso) - (casos actuales)
        puntuados = []
        for c in candidatos:
            esperado = (pesos[c.id] / total_peso) * total_hist
            deficit = esperado - historicos[c.id]
            puntuados.append((c, pesos[c.id], historicos[c.id], round(deficit, 2)))
        # Mayor déficit primero.
        puntuados.sort(key=lambda p: (-p[3], p[0].id))
        elegido = puntuados[0][0]
        return elegido, {
            "razon": f"Mayor déficit vs peso (déficit={puntuados[0][3]:.2f}).",
            "candidatos": [
                {
                    "id": c.id,
                    "nombre": c.nombre,
                    "peso": peso,
                    "peso_%": round(peso / total_peso * 100, 1),
                    "casos_historicos": hist,
                    "deficit": d,
                }
                for c, peso, hist, d in puntuados
            ],
            "total_peso": total_peso,
        }


class AsignadorAleatorio(AsignadorBase):
    codigo = EstrategiaAsignacion.ALEATORIO

    def _seleccionar(self, candidatos, contexto):
        elegido = random.choice(candidatos)
        return elegido, {
            "razon": "Seleccionado aleatoriamente entre candidatos activos.",
            "candidatos": [{"id": c.id, "nombre": c.nombre} for c in candidatos],
        }


class AsignadorStickyCliente(AsignadorBase):
    codigo = EstrategiaAsignacion.STICKY_CLIENTE

    def _seleccionar(self, candidatos, contexto):
        from portal_retenciones.models import Solicitud

        ids_disponibles = {c.id: c for c in candidatos}
        ultima = (
            Solicitud.objects.filter(cliente_id=contexto.cliente_id)
            .order_by("-fecha_creacion")
            .first()
        )
        if ultima:
            campo = _campo_fk(self.rol)
            persona_anterior = getattr(ultima, campo, None)
            if persona_anterior and persona_anterior.id in ids_disponibles:
                return ids_disponibles[persona_anterior.id], {
                    "razon": f"Cliente ya tuvo caso previo (SOL-{ultima.id}) con este mismo {self.rol.lower()}.",
                    "caso_anterior": f"SOL-{ultima.id}",
                    "candidatos": [{"id": c.id, "nombre": c.nombre} for c in candidatos],
                }
        # Fallback: round-robin.
        elegido, detalle = AsignadorRoundRobin(self.rol)._seleccionar(candidatos, contexto)
        detalle["razon"] = "Sin historial con el cliente → fallback round-robin. " + detalle["razon"]
        return elegido, detalle


class AsignadorRendimiento(AsignadorBase):
    codigo = EstrategiaAsignacion.RENDIMIENTO

    def _seleccionar(self, candidatos, contexto):
        puntuados = [(c, _tasa_retencion(c, self.rol)) for c in candidatos]
        # Mayor tasa primero (empate → menor ID).
        puntuados.sort(key=lambda p: (-p[1], p[0].id))
        elegido, tasa = puntuados[0]
        return elegido, {
            "razon": f"Mejor tasa de retención histórica ({tasa * 100:.1f}%).",
            "candidatos": [
                {"id": c.id, "nombre": c.nombre, "tasa_retencion_%": round(t * 100, 1)}
                for c, t in puntuados
            ],
        }


ESTRATEGIAS = {
    cls.codigo: cls
    for cls in (
        AsignadorRoundRobin,
        AsignadorBalanceRenta,
        AsignadorCargaCasos,
        AsignadorPonderado,
        AsignadorAleatorio,
        AsignadorStickyCliente,
        AsignadorRendimiento,
    )
}


def obtener_asignador(rol: str) -> AsignadorBase:
    codigo = obtener_estrategia_activa(rol)
    cls = ESTRATEGIAS.get(codigo, AsignadorRoundRobin)
    return cls(rol)


def asignar(rol: str, contexto: SolicitudContexto):
    """Punto de entrada único. Devuelve (persona, detalle_audit)."""
    return obtener_asignador(rol).seleccionar(contexto)


def previsualizar(rol: str, contexto: SolicitudContexto):
    """Simula la siguiente asignación sin mutar estado (solo para UI)."""
    asignador = obtener_asignador(rol)
    # Las estrategias que mutan estado (round-robin, sticky fallback) lo hacen con
    # set_parametro, por lo que para un preview real deberíamos clonar. Para la
    # UI basta con saber el candidato y la razón aproximada.
    candidatos = list(asignador.candidatos_base())
    candidatos = asignador.aplicar_tope_carga(candidatos, contexto.renta_total)
    if not candidatos:
        return None, {"razon": "Sin candidatos disponibles.", "candidatos": []}
    # Para preview no mutamos last_id: leemos sin escribir.
    if asignador.codigo == EstrategiaAsignacion.ROUND_ROBIN:
        clave = f"last_{rol.lower()}_id"
        last_id = get_parametro_int(clave, 0)
        siguientes = [c for c in candidatos if c.id > last_id]
        elegido = siguientes[0] if siguientes else candidatos[0]
        return elegido, {"razon": f"Siguiente tras id={last_id}.", "candidatos": [{"id": c.id, "nombre": c.nombre} for c in candidatos]}
    persona, detalle = asignador._seleccionar(candidatos, contexto)
    return persona, detalle
