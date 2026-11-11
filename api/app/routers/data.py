"""Módulo 1. Datos."""

import math
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth import require_auth
from app.files import MAX_BYTES, parse_upload
from app.schemas import data
from app.spc import descriptive
from app.spc.constants import SPCInputError

router = APIRouter(dependencies=[Depends(require_auth)])


@router.post("/api/data/parse", response_model=data.ParsedFile, tags=["datos"])
def parse_file(file: UploadFile = File(...)):
    raw = file.file.read(MAX_BYTES + 1)
    return parse_upload(file.filename or "", raw)


@router.post("/api/data/summary", response_model=data.SummaryResponse, tags=["datos"])
def summary(body: data.SummaryRequest):
    return asdict(descriptive.summarize(body.subgroups, body.labels))


def _names(labels, idx):
    return ", ".join(labels[i] for i in idx[:8]) + (f" y {len(idx) - 8} más" if len(idx) > 8 else "")


@router.post("/api/data/summary/attributes", response_model=data.AttributeSummaryResponse, tags=["datos"])
def attribute_summary(body: data.AttributeSummaryRequest):
    # Solo agregación: no hay función en `spc` para esta ruta (sin docstring: iría al OpenAPI).
    counts, sizes, m = body.counts, body.sizes, len(body.counts)
    if sizes is not None and len(sizes) != m:
        raise SPCInputError(f"Se recibieron {len(sizes)} tamaños para {m} subgrupos.")
    if body.labels is not None and len(body.labels) != m:
        raise SPCInputError(f"Se recibieron {len(body.labels)} etiquetas para {m} subgrupos.")
    if not all(math.isfinite(c) for c in counts) or (sizes and not all(math.isfinite(s) for s in sizes)):
        raise SPCInputError("Hay valores no numéricos o infinitos en los conteos o en los tamaños.")
    labels = list(body.labels) if body.labels is not None else [str(i + 1) for i in range(m)]

    rows = []
    for i in range(m):
        size = sizes[i] if sizes is not None else None
        rate = counts[i] / size if size is not None and size > 0 else None
        rows.append({"label": labels[i], "count": counts[i], "size": size, "rate": rate})

    warnings = []
    negative = [i for i in range(m) if counts[i] < 0]
    if negative:
        warnings.append(f"Hay conteos negativos en los subgrupos: {_names(labels, negative)}. Revise la captura.")
    if sizes is not None:
        neg_size = [i for i in range(m) if sizes[i] < 0]
        zero = [i for i in range(m) if sizes[i] == 0]
        over = [i for i in range(m) if sizes[i] > 0 and counts[i] > sizes[i]]
        if neg_size:
            warnings.append(f"Hay tamaños de muestra negativos en los subgrupos: {_names(labels, neg_size)}.")
        if zero:
            warnings.append(
                f"Hay tamaños de muestra iguales a cero en los subgrupos: {_names(labels, zero)}; no tienen tasa."
            )
        if over:
            warnings.append(
                f"El conteo es mayor que el tamaño de muestra en los subgrupos: {_names(labels, over)}. "
                "Es imposible si se cuentan unidades no conformes (p, np); solo es posible si se cuentan "
                "no conformidades (u)."
            )

    total_count = float(sum(counts))
    total_size = float(sum(sizes)) if sizes is not None else None
    return {
        "rows": rows,
        "subgroups": m,
        "total_count": total_count,
        "total_size": total_size,
        "overall_rate": total_count / total_size if total_size is not None and total_size > 0 else None,
        "mean_count": total_count / m,
        "min_size": min(sizes) if sizes is not None else None,
        "max_size": max(sizes) if sizes is not None else None,
        "constant_size": (min(sizes) == max(sizes)) if sizes is not None else None,
        "warnings": warnings,
    }
