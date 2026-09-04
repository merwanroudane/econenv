"""pandas <-> R.

Two transports, chosen automatically:

**feather** — used when ``pyarrow`` is importable on the Python side *and* the
``arrow`` package is installed on the R side. Binary, typed, fastest.

**typed CSV + schema sidecar** — the fallback, and deliberately not "just CSV".
The data goes out as CSV with an explicit ``__NA__`` sentinel (so an empty string
stays an empty string, not a missing value), and a companion schema file records
each column's logical type, factor levels and ordering. On arrival R re-applies
those types, so factors come back as factors, integers as integers, and dates as
``Date``. The reverse trip does the same in the other direction.

That is what brief §61's "do not use CSV as the only bridge" is really asking
for: the wire format may be text, but the *type information must not be*.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..exceptions import DataTransferError
from ..schema import (
    ColumnSchema,
    ConversionReport,
    DatasetMetadata,
    LogicalType,
    Severity,
    describe_frame,
    logical_type_of,
)

NA_SENTINEL = "__ECONENV_NA__"
#: Column R rownames travel in when they carry meaning (e.g. regression terms).
ROWNAME_COLUMN = ".econenv_rownames"

#: R names may not start with a digit or a dot-digit; ``make.names`` would mangle
#: silently, so EconEnv does it explicitly and reports it.
# fmt: off
_R_RESERVED = {
    "if", "else", "repeat", "while", "function", "for", "next", "break",
    "TRUE", "FALSE", "NULL", "Inf", "NaN", "NA", "in",
}
# fmt: on


def sanitise_name(name: str, taken: Optional[set] = None) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9._]", ".", str(name))
    if not cleaned or cleaned[0].isdigit() or (cleaned[0] == "." and cleaned[1:2].isdigit()):
        cleaned = f"X{cleaned}"
    if cleaned in _R_RESERVED:
        cleaned = f"{cleaned}."
    if taken is not None:
        base, suffix = cleaned, 1
        while cleaned in taken:
            cleaned = f"{base}.{suffix}"
            suffix += 1
        taken.add(cleaned)
    return cleaned


def _schema_payload(df: pd.DataFrame) -> List[Dict[str, Any]]:
    payload = []
    for column in df.columns:
        series = df[column]
        ltype = logical_type_of(series)
        entry: Dict[str, Any] = {"name": str(column), "type": ltype.value}
        if ltype is LogicalType.CATEGORICAL:
            entry["levels"] = [str(c) for c in series.cat.categories]
            entry["ordered"] = bool(series.cat.ordered)
        if ltype is LogicalType.DATETIME:
            tz = getattr(series.dtype, "tz", None)
            entry["tz"] = str(tz) if tz is not None else None
        payload.append(entry)
    return payload


def _use_feather(engine) -> bool:
    preference = str(engine.options.get("transfer") or "auto").lower()
    from .. import config as _config

    preference = str(_config.get_option("r", "transfer", preference)).lower()
    if preference == "csv":
        return False
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        return False
    if preference == "feather":
        return True
    return engine.has_r_package("arrow")


def push_frame(engine, name: str, df: pd.DataFrame, **kwargs: Any) -> ConversionReport:
    """Create the R data frame *name* from *df*."""
    report = ConversionReport(engine="r", direction="push")
    work = engine._tempdir_path()
    token = uuid.uuid4().hex[:8]

    out = df.copy()
    if not isinstance(out.index, pd.RangeIndex):
        index_frame = out.index.to_frame(index=False)
        index_frame.columns = [
            str(c) if c is not None else f"index_{i}" for i, c in enumerate(index_frame.columns)
        ]
        out = pd.concat([index_frame, out.reset_index(drop=True)], axis=1)
        report.add(Severity.INFO, f"index written as column(s) {list(index_frame.columns)}")

    taken: set = set()
    renames = {}
    for column in out.columns:
        safe = sanitise_name(column, taken)
        if safe != str(column):
            renames[column] = safe
    if renames:
        out = out.rename(columns=renames)
        for original, new in renames.items():
            report.add(Severity.WARNING, f"renamed to {new!r} for R", column=str(original))

    for column in out.columns:
        if logical_type_of(out[column]) is LogicalType.UNSUPPORTED:
            raise DataTransferError(
                f"dtype {out[column].dtype} cannot be sent to R",
                engine="r",
                name=str(column),
                hint="Cast it to a numeric, string, boolean, categorical or datetime dtype.",
            )

    if _use_feather(engine):
        path = work / f"push_{token}.feather"
        out.to_feather(path)
        script = f'{name} <- as.data.frame(arrow::read_feather("{path.as_posix()}"))'
        report.add(Severity.INFO, "transferred as Arrow feather (types preserved exactly)")
    else:
        data_path = work / f"push_{token}.csv"
        schema_path = work / f"push_{token}.schema.json"
        out.to_csv(data_path, index=False, na_rep=NA_SENTINEL, encoding="utf-8")
        schema_path.write_text(json.dumps(_schema_payload(out)), encoding="utf-8")
        script = _CSV_READ_TEMPLATE.format(
            name=name,
            data=data_path.as_posix(),
            schema=schema_path.as_posix(),
            na=NA_SENTINEL,
        )
        report.add(Severity.INFO, "transferred as typed CSV with a JSON schema sidecar")

    try:
        engine.execute(script, graphics="off")
    except Exception as exc:
        raise DataTransferError(
            f"R could not read the transferred frame: {exc}", engine="r", name=name, raw=exc
        ) from exc
    finally:
        for leftover in work.glob(f"push_{token}*"):
            with contextlib.suppress(OSError):
                leftover.unlink()

    report.emit()
    return report


def pull_frame(engine, name: str, **kwargs: Any) -> pd.DataFrame:
    """Read the R object *name* (anything ``as.data.frame`` accepts) into pandas."""
    work = engine._tempdir_path()
    token = uuid.uuid4().hex[:8]

    if _use_feather(engine):
        path = work / f"pull_{token}.feather"
        script = f'arrow::write_feather(as.data.frame({name}), "{path.as_posix()}")'
        engine.execute(script, graphics="off")
        if not path.exists():
            raise DataTransferError(f"R wrote no data for {name!r}.", engine="r", name=name)
        df = pd.read_feather(path)
        _unlink(path)
        meta = describe_frame(df, name=name, source_engine="r")
        df.attrs["econenv_metadata"] = meta
        return df

    data_path = work / f"pull_{token}.csv"
    schema_path = work / f"pull_{token}.schema.json"
    script = _CSV_WRITE_TEMPLATE.format(
        name=name, data=data_path.as_posix(), schema=schema_path.as_posix(), na=NA_SENTINEL
    )
    try:
        engine.execute(script, graphics="off")
    except Exception as exc:
        raise DataTransferError(
            f"R could not export {name!r}: {exc}", engine="r", name=name, raw=exc
        ) from exc
    if not data_path.exists():
        raise DataTransferError(f"R wrote no data for {name!r}.", engine="r", name=name)

    schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.exists() else []
    df = pd.read_csv(data_path, na_values=[NA_SENTINEL], keep_default_na=False, dtype=object)
    df = _apply_schema(df, schema)
    if ROWNAME_COLUMN in df.columns:
        df = df.set_index(ROWNAME_COLUMN)
        df.index.name = None

    _unlink(data_path)
    _unlink(schema_path)

    meta = describe_frame(df, name=name, source_engine="r")
    for entry in schema:
        column = meta.column(entry["name"])
        if column is not None:
            column.source_type = entry.get("r_class")
    df.attrs["econenv_metadata"] = meta
    return df


def _apply_schema(df: pd.DataFrame, schema: List[Dict[str, Any]]) -> pd.DataFrame:
    """Re-impose R's types on the CSV that came back as strings."""
    out = df.copy()
    for entry in schema:
        column = entry["name"]
        if column not in out.columns:
            continue
        ltype = entry.get("type", "string")
        series = out[column]
        if ltype == "boolean":
            out[column] = series.map({"TRUE": True, "FALSE": False, "T": True, "F": False}).astype(
                "boolean"
            )
        elif ltype == "integer":
            out[column] = pd.to_numeric(series, errors="coerce").astype("Int64")
        elif ltype == "float":
            out[column] = pd.to_numeric(series, errors="coerce")
        elif ltype == "categorical":
            levels = entry.get("levels") or None
            out[column] = pd.Categorical(
                series, categories=levels, ordered=bool(entry.get("ordered", False))
            )
        elif ltype == "date":
            out[column] = pd.to_datetime(series, errors="coerce").dt.date
            out[column] = pd.to_datetime(out[column], errors="coerce")
        elif ltype == "datetime":
            out[column] = pd.to_datetime(series, errors="coerce")
            tz = entry.get("tz")
            if tz:
                out[column] = out[column].dt.tz_localize(
                    tz, nonexistent="shift_forward", ambiguous="NaT"
                )
        else:
            out[column] = series.astype("object")
    return out


def _unlink(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


# R side of the CSV transport. Kept as plain base R plus an optional
# data.table fast path so it works on a bare R installation.
_CSV_READ_TEMPLATE = r"""
local({{
  schema <- .econenv_read_schema("{schema}")
  if (requireNamespace("data.table", quietly = TRUE)) {{
    d <- as.data.frame(data.table::fread("{data}", na.strings = "{na}",
                                         colClasses = "character",
                                         showProgress = FALSE))
  }} else {{
    d <- utils::read.csv("{data}", na.strings = "{na}", colClasses = "character",
                         check.names = FALSE, stringsAsFactors = FALSE)
  }}
  for (s in schema) {{
    nm <- s$name
    if (!nm %in% names(d)) next
    d[[nm]] <- switch(s$type,
      "boolean"     = as.logical(d[[nm]]),
      "integer"     = as.integer(d[[nm]]),
      "float"       = as.numeric(d[[nm]]),
      "categorical" = factor(d[[nm]], levels = s$levels, ordered = isTRUE(s$ordered)),
      "date"        = as.Date(d[[nm]]),
      "datetime"    = as.POSIXct(d[[nm]], tz = "UTC"),
      as.character(d[[nm]]))
  }}
  assign("{name}", d, envir = globalenv())
}})
"""

_CSV_WRITE_TEMPLATE = r"""
local({{
  d <- as.data.frame({name})
  # Meaningful row names (coef(summary(fit)) uses the term names) would be lost
  # by write.csv(row.names = FALSE), so promote them to a real column first.
  rn <- rownames(d)
  if (!is.null(rn) && !identical(rn, as.character(seq_len(nrow(d))))) {{
    d <- cbind(.econenv_rownames = rn, d)
  }}
  schema <- lapply(names(d), function(nm) {{
    col <- d[[nm]]
    entry <- list(name = nm, type = .econenv_typeof(col),
                  r_class = paste(class(col), collapse = ","))
    if (is.factor(col)) {{
      entry$levels <- levels(col)
      entry$ordered <- is.ordered(col)
    }}
    entry
  }})
  .econenv_write_schema(schema, "{schema}")
  for (nm in names(d)) {{
    if (inherits(d[[nm]], "POSIXct")) d[[nm]] <- format(d[[nm]], "%Y-%m-%d %H:%M:%OS6", tz = "UTC")
    else if (inherits(d[[nm]], "Date")) d[[nm]] <- format(d[[nm]], "%Y-%m-%d")
  }}
  utils::write.csv(d, "{data}", row.names = FALSE, na = "{na}", fileEncoding = "UTF-8")
}})
"""

#: Appended to the engine bootstrap so the templates above have their helpers.
SCHEMA_HELPERS = r"""
.econenv_write_schema <- function(schema, path) {
  if (requireNamespace("jsonlite", quietly = TRUE)) {
    writeLines(jsonlite::toJSON(schema, auto_unbox = TRUE), path, useBytes = TRUE)
    return(invisible(NULL))
  }
  esc <- function(x) gsub('"', '\\\\"', as.character(x))
  parts <- vapply(schema, function(s) {
    bits <- c(sprintf('"name":"%s"', esc(s$name)), sprintf('"type":"%s"', esc(s$type)),
              sprintf('"r_class":"%s"', esc(s$r_class)))
    if (!is.null(s$levels))
      bits <- c(bits, sprintf('"levels":[%s]',
                paste(sprintf('"%s"', esc(s$levels)), collapse = ",")))
    if (!is.null(s$ordered))
      bits <- c(bits, sprintf('"ordered":%s', if (isTRUE(s$ordered)) "true" else "false"))
    paste0("{", paste(bits, collapse = ","), "}")
  }, character(1))
  writeLines(paste0("[", paste(parts, collapse = ","), "]"), path, useBytes = TRUE)
  invisible(NULL)
}

.econenv_read_schema <- function(path) {
  if (!file.exists(path)) return(list())
  if (requireNamespace("jsonlite", quietly = TRUE))
    return(jsonlite::fromJSON(path, simplifyDataFrame = FALSE))
  stop("EconEnv needs the 'jsonlite' R package for typed CSV transfer without arrow. ",
       "Install it with install.packages('jsonlite').")
}
"""


def numeric_only(df: pd.DataFrame) -> np.ndarray:
    return df.select_dtypes(include=[np.number]).to_numpy(dtype=float)


def metadata_of(df: pd.DataFrame) -> Optional[DatasetMetadata]:
    return df.attrs.get("econenv_metadata")


def schema_of(df: pd.DataFrame) -> List[ColumnSchema]:
    meta = metadata_of(df)
    return meta.columns if meta else []
