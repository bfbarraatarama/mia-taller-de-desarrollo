"""Cuantización temporal compartida por las etapas con referencias temporales."""

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


def techo_3_decimales(duracion: float) -> float:
    """Mayor valor con tres decimales que no supera la duración no negativa."""
    mil = Decimal(1000)
    d3 = (Decimal(str(duracion)) * mil).to_integral_value(rounding=ROUND_FLOOR) / mil
    return max(float(d3), 0.0)


def cuantizar_intervalo(inicio: float, fin: float) -> tuple[float, float]:
    """Para un intervalo finito 0 <= inicio < fin, conservar el redondeo usual.

    Si ambos extremos coinciden al redondear, usar los límites de la grilla
    de milisegundos que contienen el intervalo. No corregir aquí tiempos inválidos.
    """
    a, b = round(float(inicio), 3), round(float(fin), 3)
    if a < b:
        return a, b
    mil = Decimal(1000)
    a = (Decimal(str(inicio)) * mil).to_integral_value(rounding=ROUND_FLOOR)
    b = (Decimal(str(fin)) * mil).to_integral_value(rounding=ROUND_CEILING)
    return float(a / mil), float(b / mil)
