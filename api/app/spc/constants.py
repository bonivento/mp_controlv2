"""Constantes para gráficos de control por variables.

Fuente general: Montgomery, D. C., *Introduction to Statistical Quality Control*,
apéndice VI ("Factors for Constructing Variables Control Charts") y capítulo 6
(sección 6.2 para X-barra y R, sección 6.3 para X-barra y S, sección 6.4 para
individuales y rango móvil).

Solo se tabulan d2 y d3. c4 se calcula exacto con la función gamma. Todos los
demás factores (A2, A3, B3, B4, B5, B6, D1, D2, D3, D4) se derivan de esos tres,
de modo que existe una única fuente de verdad y se pueden construir con un ancho
L distinto de 3.

d2(n) = E[W] y d3(n) = sd(W), con W el rango relativo W = R/sigma de una muestra
de n normales. Los valores tabulados se obtuvieron por integración numérica de
(Montgomery, sección 6.2.1; Tippett, 1925):

    d2(n) = ∫ [1 - Φ(x)^n - (1 - Φ(x))^n] dx
    E[W²] = 2 ∫∫_{x<y} [1 - Φ(y)^n - (1 - Φ(x))^n + (Φ(y) - Φ(x))^n] dx dy
    d3(n) = sqrt(E[W²] - d2(n)²)

Se guardan con seis decimales; redondeados a tres coinciden con el apéndice VI.
La prueba `tests/spc/test_constants.py` repite la integración y compara.
"""

from __future__ import annotations

import math

from scipy.special import gammaln

MIN_N = 2
MAX_N_RANGE = 25  # d2 y d3 tabulados hasta n = 25, como el apéndice VI


class SPCInputError(ValueError):
    """Datos que no permiten construir el gráfico.

    `code` coincide con `ErrorResponse.code` del contrato para que la capa HTTP
    lo traduzca sin adivinar: "invalid_data", "insufficient_data" o
    "missing_limits". El mensaje va en español y se puede mostrar.
    """

    def __init__(self, message: str, code: str = "invalid_data"):
        super().__init__(message)
        self.code = code

# n: (d2, d3), seis decimales, integración numérica (ver docstring del módulo).
_D2_D3: dict[int, tuple[float, float]] = {
    2: (1.128379, 0.852502),
    3: (1.692569, 0.888368),
    4: (2.058751, 0.879808),
    5: (2.325929, 0.864082),
    6: (2.534413, 0.848040),
    7: (2.704357, 0.833205),
    8: (2.847201, 0.819831),
    9: (2.970026, 0.807834),
    10: (3.077505, 0.797051),
    11: (3.172873, 0.787315),
    12: (3.258455, 0.778478),
    13: (3.335980, 0.770416),
    14: (3.406763, 0.763023),
    15: (3.471827, 0.756211),
    16: (3.531983, 0.749908),
    17: (3.587884, 0.744052),
    18: (3.640064, 0.738591),
    19: (3.688963, 0.733481),
    20: (3.734950, 0.728686),
    21: (3.778336, 0.724173),
    22: (3.819385, 0.719915),
    23: (3.858323, 0.715887),
    24: (3.895348, 0.712068),
    25: (3.930629, 0.708441),
}


def _check_int(n: int, upper: int | None) -> int:
    if isinstance(n, bool) or int(n) != n:
        raise SPCInputError(f"El tamaño de subgrupo debe ser entero; se recibió {n!r}.")
    n = int(n)
    if n < MIN_N:
        raise SPCInputError(f"El tamaño de subgrupo debe ser al menos {MIN_N}; se recibió {n}.")
    if upper is not None and n > upper:
        raise SPCInputError(
            f"d2 y d3 están tabulados para n de {MIN_N} a {upper}; se recibió n = {n}. "
            "Para subgrupos grandes use el gráfico X-barra-S."
        )
    return n


def c4(n: int) -> float:
    """c4(n) = sqrt(2/(n-1)) · Γ(n/2) / Γ((n-1)/2), exacto.

    Es la constante de insesgamiento de S: E[S] = c4·sigma.
    Fuente: Montgomery, sección 6.3.1, ecuación de c4 y apéndice VI.
    Se usa gammaln para que funcione con n grande sin desbordar.
    """
    n = _check_int(n, None)
    return math.sqrt(2.0 / (n - 1)) * math.exp(gammaln(n / 2.0) - gammaln((n - 1) / 2.0))


def d2(n: int) -> float:
    """d2(n) = E[R/sigma] para muestras normales de tamaño n (tabulado, n = 2..25).

    Fuente: Montgomery, sección 6.2.1 y apéndice VI.
    """
    return _D2_D3[_check_int(n, MAX_N_RANGE)][0]


def d3(n: int) -> float:
    """d3(n) = sd(R/sigma) para muestras normales de tamaño n (tabulado, n = 2..25).

    Fuente: Montgomery, sección 6.2.1 (límites del gráfico R) y apéndice VI.
    """
    return _D2_D3[_check_int(n, MAX_N_RANGE)][1]


# --- Factores derivados -------------------------------------------------------
# Todas las ecuaciones: Montgomery, capítulo 6 y notas del apéndice VI.
# Los factores con max(0, ·) son límites inferiores que se truncan en 0 porque
# R y S no pueden ser negativos.


def A(n: int, L: float = 3.0) -> float:
    """A = L/sqrt(n). Límites de X-barra con sigma conocido: mu ± A·sigma."""
    n = _check_int(n, None)
    return L / math.sqrt(n)


def A2(n: int, L: float = 3.0) -> float:
    """A2 = L/(d2·sqrt(n)). Límites de X-barra: x̿ ± A2·R̄ (sección 6.2.1)."""
    return L / (d2(n) * math.sqrt(n))


def A3(n: int, L: float = 3.0) -> float:
    """A3 = L/(c4·sqrt(n)). Límites de X-barra: x̿ ± A3·S̄ (sección 6.3.1)."""
    return L / (c4(n) * math.sqrt(n))


def _s_spread(n: int) -> float:
    """sqrt(1 - c4²): desviación estándar de S en unidades de sigma."""
    c = c4(n)
    return math.sqrt(max(0.0, 1.0 - c * c))


def B3(n: int, L: float = 3.0) -> float:
    """B3 = max(0, 1 - L·sqrt(1-c4²)/c4). LCL del gráfico S: B3·S̄ (sección 6.3.1)."""
    return max(0.0, 1.0 - L * _s_spread(n) / c4(n))


def B4(n: int, L: float = 3.0) -> float:
    """B4 = 1 + L·sqrt(1-c4²)/c4. UCL del gráfico S: B4·S̄ (sección 6.3.1)."""
    return 1.0 + L * _s_spread(n) / c4(n)


def B5(n: int, L: float = 3.0) -> float:
    """B5 = max(0, c4 - L·sqrt(1-c4²)). LCL del gráfico S con sigma conocido: B5·sigma."""
    return max(0.0, c4(n) - L * _s_spread(n))


def B6(n: int, L: float = 3.0) -> float:
    """B6 = c4 + L·sqrt(1-c4²). UCL del gráfico S con sigma conocido: B6·sigma."""
    return c4(n) + L * _s_spread(n)


def D1(n: int, L: float = 3.0) -> float:
    """D1 = max(0, d2 - L·d3). LCL del gráfico R con sigma conocido: D1·sigma."""
    return max(0.0, d2(n) - L * d3(n))


def D2(n: int, L: float = 3.0) -> float:
    """D2 = d2 + L·d3. UCL del gráfico R con sigma conocido: D2·sigma."""
    return d2(n) + L * d3(n)


def D3(n: int, L: float = 3.0) -> float:
    """D3 = max(0, 1 - L·d3/d2). LCL del gráfico R: D3·R̄ (sección 6.2.1)."""
    return max(0.0, 1.0 - L * d3(n) / d2(n))


def D4(n: int, L: float = 3.0) -> float:
    """D4 = 1 + L·d3/d2. UCL del gráfico R: D4·R̄ (sección 6.2.1)."""
    return 1.0 + L * d3(n) / d2(n)


def factor_table(n: int, L: float = 3.0) -> dict[str, float]:
    """Todos los factores para un n, útil para mostrar o documentar."""
    out = {"n": float(n), "c4": c4(n), "A": A(n, L), "A3": A3(n, L),
           "B3": B3(n, L), "B4": B4(n, L), "B5": B5(n, L), "B6": B6(n, L)}
    if n <= MAX_N_RANGE:
        out.update({"d2": d2(n), "d3": d3(n), "A2": A2(n, L), "D1": D1(n, L),
                    "D2": D2(n, L), "D3": D3(n, L), "D4": D4(n, L)})
    return out


__all__ = [
    "SPCInputError", "MIN_N", "MAX_N_RANGE", "c4", "d2", "d3", "A", "A2", "A3",
    "B3", "B4", "B5", "B6", "D1", "D2", "D3", "D4", "factor_table",
]
