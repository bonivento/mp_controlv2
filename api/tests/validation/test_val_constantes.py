"""Validación independiente de constants.py (validador estadístico).

Caminos distintos a los del software:
- d2 con la esperanza del máximo, 2n∫xφΦ^(n-1); el software integra 1 - Φ^n - (1-Φ)^n.
- d3 con E[W²] = 2E[X(n)²] - 2E[X(1)X(n)] (densidad conjunta de mín y máx);
  el software integra la forma con funciones de distribución.
- c4 con la media de la distribución chi de scipy; el software usa gammaln.
"""

import math

import numpy as np
import pytest

from app.spc import constants as K

from .independiente import c4_por_chi, d2_por_maximo, d3_por_momentos, factores_propios

NS = list(range(2, 26))


@pytest.mark.parametrize("n", NS)
def test_d2_d3_otra_integral(n):
    assert K.d2(n) == pytest.approx(d2_por_maximo(n), abs=6e-7)
    assert K.d3(n) == pytest.approx(d3_por_momentos(n), abs=6e-7)


@pytest.mark.parametrize("n", NS + [30, 50, 100])
def test_c4_por_distribucion_chi(n):
    assert K.c4(n) == pytest.approx(c4_por_chi(n), rel=1e-12)


@pytest.mark.parametrize("n", NS)
def test_factores_derivados(n):
    propios = factores_propios(n)
    for name, value in propios.items():
        assert getattr(K, name)(n) == pytest.approx(value, abs=5e-6), name


def test_factores_con_otro_ancho():
    for n in (2, 5, 9):
        propios = factores_propios(n, L=2.5)
        for name in ("A", "A2", "A3", "B3", "B4", "D3", "D4"):
            assert getattr(K, name)(n, L=2.5) == pytest.approx(propios[name], abs=5e-6)


def test_d3_19_del_apendice_es_un_redondeo_de_la_tabla():
    """Duda 6: el apéndice imprime d3(19) = 0.734; dos integrales distintas dan 0.73348."""
    v = d3_por_momentos(19)
    assert round(v, 3) == 0.733
    assert K.d3(19) == pytest.approx(v, abs=6e-7)


def test_d2_d3_por_simulacion_grande():
    """Control grueso: 400 000 muestras de n = 19 (error estándar de sd(R) ≈ 8e-4)."""
    rng = np.random.default_rng(2026)
    x = rng.standard_normal((400_000, 19))
    r = x.max(axis=1) - x.min(axis=1)
    assert r.mean() == pytest.approx(K.d2(19), abs=4 * r.std() / math.sqrt(r.size))
    assert r.std(ddof=1) == pytest.approx(K.d3(19), abs=0.004)
