"""Lectura de archivos CSV y XLSX para `/api/data/parse`.

Sin pandas: `csv` de la biblioteca estándar y openpyxl en modo solo lectura.
El archivo no se guarda: se lee desde memoria y se devuelve como tabla.
"""

from __future__ import annotations

import csv
import io
import math
import re
from datetime import date, datetime, time
from typing import Any, Optional

from app.spc.constants import SPCInputError

MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 20_000
MAX_COLUMNS = 200
# Una columna es numérica (o de fechas) si al menos esta fracción de sus celdas no vacías lo es.
KIND_THRESHOLD = 0.5

_NUMBER = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")
_DECIMAL_COMMA = re.compile(r"^[+-]?\d+,\d+$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$")
_DMY_DATE = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$")


# --- Celdas --------------------------------------------------------------
def parse_number(text: str) -> Optional[float]:
    """Número desde texto: punto o coma decimal. None si no es un número finito."""
    s = text.strip().replace(" ", "").replace(" ", "")
    if not s or not _NUMBER.match(s):
        return None
    if _DECIMAL_COMMA.match(s) or s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    elif "," in s:  # 1,234.5 -> separador de miles
        s = s.replace(",", "")
    try:
        value = float(s)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def parse_date(text: str) -> Optional[str]:
    """Fecha ISO (`YYYY-MM-DD` o con hora) desde texto ISO o día/mes/año."""
    s = text.strip()
    if _ISO_DATE.match(s):
        try:
            datetime.fromisoformat(s)
        except ValueError:
            return None
        return s
    m = _DMY_DATE.match(s)
    if m:
        day, month, year = int(m[1]), int(m[2]), int(m[3])
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    return None


def _normalize(raw: Any) -> Any:
    """Celda cruda -> None | float | datetime-iso (tupla marcada) | str."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return str(raw).upper()
    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if math.isfinite(value) else None
    if isinstance(raw, datetime):
        return ("date", raw.isoformat(timespec="seconds") if (raw.hour or raw.minute or raw.second) else raw.date().isoformat())
    if isinstance(raw, date):
        return ("date", raw.isoformat())
    if isinstance(raw, time):
        return str(raw)
    text = str(raw).strip()
    return text or None


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _classify(column: list[Any], name: str = "", warnings: Optional[list[str]] = None) -> tuple[str, list[Any], int]:
    """Devuelve (tipo, celdas convertidas, faltantes) para una columna.

    Si se pasa `warnings`, agrega un aviso por tipo de conversión hecha en la columna.
    """
    w = warnings if warnings is not None else []
    col = f"Columna '{name}'"
    cells = [_normalize(c) for c in column]
    present = [c for c in cells if c is not None]
    if not present:
        return "empty", [None] * len(cells), len(cells)

    trimmed = sum(1 for c in column if isinstance(c, str) and c.strip() and c != c.strip())
    if trimmed:
        w.append(f"{col}: {_plural(trimmed, 'celda con espacios', 'celdas con espacios')} al inicio o al final, recortados.")
    blanks = len(cells) - len(present)

    numeric = sum(1 for c in present if isinstance(c, float) or (isinstance(c, str) and parse_number(c) is not None))
    dates = sum(1 for c in present if isinstance(c, tuple) or (isinstance(c, str) and parse_date(c) is not None))

    if numeric / len(present) >= KIND_THRESHOLD:
        commas = sum(1 for c in cells if isinstance(c, str) and _DECIMAL_COMMA.match(c.replace(" ", "")))
        bad = [c for c in cells if isinstance(c, str) and parse_number(c) is None]
        other = sum(1 for c in cells if isinstance(c, tuple))
        if commas:
            w.append(f"{col}: {_plural(commas, 'valor con coma decimal convertido', 'valores con coma decimal convertidos')} a punto.")
        if bad or other:
            examples = []
            for b in bad:
                if b not in examples:
                    examples.append(b)
            ex = ", ".join(f'"{e}"' for e in examples[:3])
            w.append(
                f"{col}: {_plural(len(bad) + other, 'texto no numérico tratado', 'textos no numéricos tratados')} como faltante"
                + (f" (por ejemplo {ex})." if ex else ".")
            )
        if blanks:
            w.append(f"{col}: {_plural(blanks, 'celda vacía registrada', 'celdas vacías registradas')} como faltante.")
        out = []
        for c in cells:
            if isinstance(c, float):
                out.append(c)
            elif isinstance(c, str):
                out.append(parse_number(c))  # texto no numérico ("N/D") -> faltante
            else:
                out.append(None)
        return "numeric", out, sum(1 for v in out if v is None)
    if dates / len(present) >= KIND_THRESHOLD:
        dmy = sum(1 for c in cells if isinstance(c, str) and _DMY_DATE.match(c))
        bad = [c for c in cells if isinstance(c, str) and parse_date(c) is None]
        if dmy:
            w.append(f"{col}: {_plural(dmy, 'fecha en formato día/mes/año normalizada', 'fechas en formato día/mes/año normalizadas')} a ISO (AAAA-MM-DD).")
        if bad:
            ex = ", ".join(f'"{e}"' for e in list(dict.fromkeys(bad))[:3])
            w.append(f"{col}: {_plural(len(bad), 'texto que no es fecha tratado', 'textos que no son fecha tratados')} como faltante (por ejemplo {ex}).")
        if blanks:
            w.append(f"{col}: {_plural(blanks, 'celda vacía registrada', 'celdas vacías registradas')} como faltante.")
        out = []
        for c in cells:
            if isinstance(c, tuple):
                out.append(c[1])
            elif isinstance(c, str):
                out.append(parse_date(c))
            else:
                out.append(None)
        return "datetime", out, sum(1 for v in out if v is None)
    out = []
    for c in cells:
        if isinstance(c, tuple):
            out.append(c[1])
        elif isinstance(c, float):
            out.append(str(int(c)) if c == int(c) else repr(c))
        else:
            out.append(c)
    if blanks:
        w.append(f"{col}: {_plural(blanks, 'valor de texto vacío registrado', 'valores de texto vacíos registrados')} como faltante.")
    return "text", out, sum(1 for v in out if v is None)


# --- Tabla -----------------------------------------------------------------
def _unique_headers(header: list[Any]) -> list[str]:
    names: list[str] = []
    seen: dict[str, int] = {}
    for i, raw in enumerate(header):
        norm = _normalize(raw)
        name = norm[1] if isinstance(norm, tuple) else (str(norm).strip() if norm is not None else "")
        if isinstance(norm, float):
            name = str(int(norm)) if norm == int(norm) else repr(norm)
        name = name or f"columna_{i + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        names.append(name)
    return names


def build_sheet(name: str, table: list[list[Any]], notes: Optional[list[str]] = None) -> Optional[dict[str, Any]]:
    """Convierte filas crudas (la primera es el encabezado) en una hoja del contrato.

    `notes` son avisos previos (separador, codificación) que van al inicio de `warnings`.
    """
    while table and all(_normalize(c) is None for c in table[-1]):
        table.pop()
    if not table:
        return None
    header = table[0]
    body_all = table[1:]
    body = [r for r in body_all if any(_normalize(c) is not None for c in r)]
    dropped = len(body_all) - len(body)
    width = len(header)
    while width > 0 and _normalize(header[width - 1]) is None and all(
        _normalize(r[width - 1]) is None if len(r) >= width else True for r in body
    ):
        width -= 1
    if width == 0:
        return None
    if width > MAX_COLUMNS:
        raise SPCInputError(f"El archivo tiene más de {MAX_COLUMNS} columnas.", "invalid_data")
    if len(body) > MAX_ROWS:
        raise SPCInputError(
            f"La hoja '{name}' tiene {len(body)} filas y el máximo es {MAX_ROWS:,}.".replace(",", " "),
            "invalid_data",
        )
    headers = _unique_headers(header[:width])
    columns, converted = [], []
    warnings: list[str] = list(notes or [])
    if dropped:
        warnings.append(f"{_plural(dropped, 'fila completamente vacía descartada', 'filas completamente vacías descartadas')}.")
    for j in range(width):
        col = [(r[j] if j < len(r) else None) for r in body]
        kind, cells, missing = _classify(col, headers[j], warnings)
        columns.append({"name": headers[j], "kind": kind, "missing": missing})
        converted.append(cells)
    rows = [[converted[j][i] for j in range(width)] for i in range(len(body))]
    return {"name": name, "columns": columns, "rows": rows, "warnings": warnings}


# --- Lectores --------------------------------------------------------------
def _decode(raw: bytes) -> tuple[str, str]:
    """Texto y nombre de la codificación detectada."""
    try:
        return raw.decode("utf-8-sig"), "UTF-8"
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("cp1252"), "Windows-1252"
    except UnicodeDecodeError:
        return raw.decode("latin-1"), "Latin-1"


def detect_delimiter(text: str) -> str:
    lines = [ln for ln in text.splitlines()[:20] if ln.strip()]
    if not lines:
        return ","
    best, best_score = ",", (-1, -1)
    for delim in (",", ";", "\t"):
        counts = [len(next(csv.reader([ln], delimiter=delim))) for ln in lines]
        modal = max(set(counts), key=counts.count)
        # Prefiere el separador que da más columnas de forma consistente.
        score = (counts.count(modal) if modal > 1 else 0, modal)
        if score > best_score:
            best, best_score = delim, score
    return best


def parse_csv(raw: bytes) -> list[dict[str, Any]]:
    text, encoding = _decode(raw)
    delimiter = detect_delimiter(text)
    notes = []
    if delimiter != ",":
        notes.append(f"Separador de columnas detectado: {'punto y coma' if delimiter == ';' else 'tabulador'}.")
    if encoding != "UTF-8":
        notes.append(f"Codificación detectada: {encoding} (no es UTF-8); los caracteres se convirtieron al leer.")
    table = [list(r) for r in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)]
    sheet = build_sheet("CSV", table, notes)
    if sheet is None:
        raise SPCInputError("El archivo CSV está vacío.", "invalid_data")
    return [sheet]


def parse_xlsx(raw: bytes) -> list[dict[str, Any]]:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:
        raise SPCInputError("No se pudo abrir el archivo Excel: está dañado o no es un .xlsx válido.", "unsupported_file") from exc
    sheets = []
    try:
        for ws in workbook.worksheets:
            table: list[list[Any]] = []
            for row in ws.iter_rows(values_only=True):
                table.append(list(row))
                if len(table) > MAX_ROWS + 1 + 1000:  # filas vacías de cola no cuentan; corta lo desmesurado
                    break
            sheet = build_sheet(ws.title, table)
            if sheet is not None:
                sheets.append(sheet)
    finally:
        workbook.close()
    if not sheets:
        raise SPCInputError("El archivo Excel no tiene hojas con datos.", "invalid_data")
    return sheets


def parse_upload(filename: str, raw: bytes) -> dict[str, Any]:
    """Punto de entrada: `ParsedFile` como diccionario."""
    if len(raw) > MAX_BYTES:
        raise SPCInputError("El archivo supera el límite de 4 MB.", "unsupported_file")
    if not raw:
        raise SPCInputError("El archivo está vacío.", "invalid_data")
    lower = (filename or "").lower()
    if lower.endswith(".csv") or lower.endswith(".txt"):
        sheets = parse_csv(raw)
    elif lower.endswith(".xlsx") or lower.endswith(".xlsm"):
        sheets = parse_xlsx(raw)
    elif lower.endswith(".xls"):
        raise SPCInputError("El formato .xls antiguo no se admite: guárdelo como .xlsx o .csv.", "unsupported_file")
    else:
        raise SPCInputError("Tipo de archivo no admitido: use .csv o .xlsx.", "unsupported_file")
    return {"filename": filename, "sheets": sheets}
