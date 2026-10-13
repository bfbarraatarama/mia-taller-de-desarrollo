#!/usr/bin/env python3
"""Valida las cinco tablas del esquema normalizado del Hito 2.

No altera datos, no decide viabilidad y no produce ni congela particiones.
Uso: python hito-2/scripts/validar_muestra.py [--componente asr|diarizacion|todos]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from numbers import Real
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1] / "muestra" / "normalizado"

# En 436 de las 438 anotaciones originales de Figshare, la marca final
# está expresada en centésimas de segundo. La tolerancia no modifica las
# referencias ni permite puntuar audio fuera de su duración física.
TOLERANCIA_FIN_FIGSHARE_S = 0.01

ARCHIVOS = {
    "asr_instancias": "asr_instancias.parquet",
    "asr_hablantes": "asr_hablantes.csv",
    "diarizacion_grabaciones": "diarizacion_grabaciones.csv",
    "diarizacion_segmentos": "diarizacion_segmentos.parquet",
    "diarizacion_hablantes": "diarizacion_hablantes.csv",
}

COLUMNAS = {
    "asr_instancias": (
        "source", "recording_id", "source_recording_id", "session_id",
        "group_id", "speaker_id", "duration_s", "audio_ref", "audio_status",
        "reference_raw", "reference_norm", "reference_origin",
        "reference_scope", "language", "source_split", "project_split",
    ),
    "asr_hablantes": (
        "source", "speaker_id", "source_speaker_id", "speaker_scope",
        "session_id", "recording_id",
    ),
    "diarizacion_grabaciones": (
        "source", "recording_id", "source_recording_id", "session_id",
        "group_id", "duration_s", "audio_ref", "audio_status",
        "reference_origin", "source_split", "project_split",
    ),
    "diarizacion_segmentos": (
        "source", "recording_id", "speaker_id", "start_s", "end_s",
        "annotation_raw", "is_silence_marker", "scored_as_speech",
        "reference_origin",
    ),
    "diarizacion_hablantes": (
        "source", "speaker_id", "source_speaker_id", "speaker_scope",
        "session_id", "recording_id",
    ),
}

REQUERIDOS = {
    "asr_instancias": (
        "source", "recording_id", "source_recording_id",
        "audio_status", "reference_scope",
    ),
    "asr_hablantes": ("source", "speaker_id", "speaker_scope"),
    "diarizacion_grabaciones": (
        "source", "recording_id", "source_recording_id", "audio_status",
    ),
    "diarizacion_segmentos": (
        "source", "recording_id", "start_s", "end_s",
    ),
    "diarizacion_hablantes": ("source", "speaker_id", "speaker_scope"),
}

CATEGORIAS = {
    "audio_status": {"no_verificado", "valido", "ilegible", "no_disponible"},
    "reference_scope": {"recording", "segment", "unknown"},
    "speaker_scope": {"recording", "session", "source", "unknown"},
}


def _nulo(v) -> bool:
    return (
        v is None
        or v is pd.NA
        or (
            isinstance(v, (str, Real, np.generic))
            and bool(pd.isna(v))
        )
    )


def _texto(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _numero(v) -> bool:
    return (
        isinstance(v, Real)
        and not isinstance(v, (bool, np.bool_))
        and bool(np.isfinite(v))
    )


def _verdadero(v) -> bool:
    return isinstance(v, (bool, np.bool_)) and bool(v)


def _clave(v) -> str | None:
    return v.strip() if _texto(v) else None


def _reporte(tabla: str, codigo: str, detalle: str, filas=()) -> dict:
    return {
        "tabla": tabla,
        "codigo": codigo,
        "detalle": detalle,
        "cantidad": len(filas),
        "filas": list(filas)[:10],
    }


def _filas(df: pd.DataFrame):
    # Se numeran las filas independientemente del índice de pandas.
    for i, row in enumerate(df.itertuples(index=False, name=None), 1):
        yield i, dict(zip(df.columns, row))


def _columnas_y_valores(nombre: str, df: pd.DataFrame) -> list[dict]:
    issues = []

    faltan = sorted(set(COLUMNAS[nombre]) - set(df.columns))
    if faltan:
        return [
            _reporte(nombre, "columnas_ausentes", ", ".join(faltan))
        ]

    if not df.columns.is_unique:
        return [
            _reporte(
                nombre, "columnas_duplicadas",
                "Nombres de columna repetidos",
            )
        ]

    if df.empty and nombre in {
        "asr_instancias", "diarizacion_grabaciones"
    }:
        issues.append(
            _reporte(nombre, "tabla_vacia", "No contiene grabaciones")
        )

    requeridos = REQUERIDOS[nombre]

    for columna in COLUMNAS[nombre]:
        malos = []

        for numero, valor in enumerate(df[columna].tolist(), 1):
            if _nulo(valor):
                if columna in requeridos:
                    malos.append(numero)
                continue

            if columna in ("start_s", "end_s", "duration_s"):
                valido = _numero(valor)
            elif columna in ("is_silence_marker", "scored_as_speech"):
                valido = isinstance(valor, (bool, np.bool_))
            else:
                valido = _texto(valor)

            if valido and columna in CATEGORIAS:
                valido = valor in CATEGORIAS[columna]

            if not valido:
                malos.append(numero)

        if malos:
            issues.append(
                _reporte(nombre, "campo_invalido", columna, malos)
            )

    return issues


def _sin_faltantes(df: pd.DataFrame, columnas: tuple[str, ...]):
    for i, fila in _filas(df):
        valores = tuple(_clave(fila[c]) for c in columnas)
        if all(v is not None for v in valores):
            yield i, fila, valores


def _unicos(
    nombre: str,
    df: pd.DataFrame,
    columnas: tuple[str, ...],
) -> list[dict]:
    vistos, duplicados = set(), []

    for i, _, valores in _sin_faltantes(df, columnas):
        if valores in vistos:
            duplicados.append(i)
        vistos.add(valores)

    if duplicados:
        return [
            _reporte(
                nombre, "clave_duplicada",
                ", ".join(columnas), duplicados,
            )
        ]
    return []


def _hablantes(nombre: str, df: pd.DataFrame) -> list[dict]:
    issues = _unicos(nombre, df, ("source", "speaker_id"))
    mal_scope = []

    for i, fila, _ in _sin_faltantes(
        df, ("source", "speaker_id")
    ):
        scope = fila["speaker_scope"]

        if scope == "recording" and not _texto(
            fila["recording_id"]
        ):
            mal_scope.append(i)

        if scope == "session" and not _texto(
            fila["session_id"]
        ):
            mal_scope.append(i)

    if mal_scope:
        issues.append(
            _reporte(
                nombre,
                "ambito_hablante_incompleto",
                "Falta identificador de grabación/sesión",
                mal_scope,
            )
        )

    return issues


def _enlaces_hablantes(
    nombre: str,
    filas: pd.DataFrame,
    hablantes: pd.DataFrame,
    grabaciones: pd.DataFrame | None = None,
) -> list[dict]:
    catalogo = {}

    for _, fila, clave in _sin_faltantes(
        hablantes, ("source", "speaker_id")
    ):
        catalogo[clave] = fila

    sesiones = {}

    if grabaciones is not None:
        for _, fila, clave in _sin_faltantes(
            grabaciones, ("source", "recording_id")
        ):
            sesiones[clave] = fila["session_id"]

    ausentes, scope_malo = [], []

    for i, fila, _ in _sin_faltantes(
        filas, ("source", "recording_id")
    ):
        sp = _clave(fila["speaker_id"])
        if sp is None:
            continue

        speaker = catalogo.get((_clave(fila["source"]), sp))

        if speaker is None:
            ausentes.append(i)
            continue

        scope = speaker["speaker_scope"]
        grabacion = _clave(fila["recording_id"])

        if scope == "recording":
            if _clave(speaker["recording_id"]) != grabacion:
                scope_malo.append(i)

        elif scope == "session":
            if grabaciones is None:
                sesion = fila.get("session_id")
            else:
                sesion = sesiones.get(
                    (_clave(fila["source"]), grabacion)
                )

            if (
                _clave(speaker["session_id"]) is None
                or _clave(sesion) != _clave(speaker["session_id"])
            ):
                scope_malo.append(i)

    issues = []

    if ausentes:
        issues.append(
            _reporte(
                nombre, "hablante_inexistente",
                "speaker_id sin fila en tabla de hablantes",
                ausentes,
            )
        )

    if scope_malo:
        issues.append(
            _reporte(
                nombre, "ambito_hablante_incompatible",
                "Identidad fuera de su grabación/sesión",
                scope_malo,
            )
        )

    return issues


def _grabaciones(nombre: str, df: pd.DataFrame) -> list[dict]:
    issues = _unicos(nombre, df, ("source", "recording_id"))
    duracion_mala, audio_malo = [], []
    norm_malo, split_sin_grupo = [], []
    por_sesion: dict[tuple[str, str], set[str]] = defaultdict(set)

    for i, fila, _ in _sin_faltantes(
        df, ("source", "recording_id")
    ):
        dur = fila["duration_s"]

        if not _nulo(dur) and _numero(dur) and dur <= 0:
            duracion_mala.append(i)

        if fila["audio_status"] == "valido" and (
            not _texto(fila["audio_ref"])
            or not _numero(dur)
            or dur <= 0
        ):
            audio_malo.append(i)

        if (
            "reference_norm" in df.columns
            and _texto(fila["reference_norm"])
            and not _texto(fila["reference_raw"])
        ):
            norm_malo.append(i)

        if (
            _texto(fila["project_split"])
            and not _texto(fila["group_id"])
        ):
            split_sin_grupo.append(i)

        session = _clave(fila["session_id"])
        group = _clave(fila["group_id"])

        if session is not None and group is not None:
            por_sesion[
                (_clave(fila["source"]), session)
            ].add(group)

    if duracion_mala:
        issues.append(
            _reporte(
                nombre, "duracion_no_positiva",
                "duration_s debe ser > 0", duracion_mala,
            )
        )

    if audio_malo:
        issues.append(
            _reporte(
                nombre, "audio_valido_sin_soporte",
                "Audio válido exige referencia y duración",
                audio_malo,
            )
        )

    if norm_malo:
        issues.append(
            _reporte(
                nombre, "normalizacion_sin_original",
                "reference_norm sin reference_raw", norm_malo,
            )
        )

    if split_sin_grupo:
        issues.append(
            _reporte(
                nombre, "particion_sin_grupo",
                "project_split necesita un group_id comprobable",
                split_sin_grupo,
            )
        )

    conflictivas = [
        f"{s}:{ses}"
        for (s, ses), grupos in por_sesion.items()
        if len(grupos) > 1
    ]

    if conflictivas:
        issues.append(
            _reporte(
                nombre, "sesion_en_grupos_distintos",
                ", ".join(sorted(conflictivas)[:10]),
                conflictivas,
            )
        )

    return issues


def _segmentos(
    df: pd.DataFrame,
    grabaciones: pd.DataFrame,
    hablantes: pd.DataFrame,
) -> list[dict]:
    nombre = "diarizacion_segmentos"
    issues = []
    lookup = {}

    for _, fila, clave in _sin_faltantes(
        grabaciones, ("source", "recording_id")
    ):
        lookup[clave] = fila["duration_s"]

    sin_grabacion, limites = [], []
    silencio, sin_sp = [], []
    duplicados, vistos = [], set()

    for i, fila, clave in _sin_faltantes(
        df, ("source", "recording_id")
    ):
        if clave not in lookup:
            sin_grabacion.append(i)

        inicio, fin = fila["start_s"], fila["end_s"]

        if _numero(inicio) and _numero(fin):
            duracion = lookup.get(clave)

            if (
                inicio < 0
                or fin <= inicio
                or (
                    _numero(duracion)
                    and fin > duracion + (
                        TOLERANCIA_FIN_FIGSHARE_S
                        if clave[0] == "uba_games_figshare" else 0.0
                    ) + 1e-12
                )
            ):
                limites.append(i)

        if (
            _verdadero(fila["is_silence_marker"])
            and _verdadero(fila["scored_as_speech"])
        ):
            silencio.append(i)

        if (
            _verdadero(fila["scored_as_speech"])
            and not _texto(fila["speaker_id"])
        ):
            sin_sp.append(i)

        # El solapamiento entre hablantes es válido;
        # el mismo evento repetido, no.
        if _numero(inicio) and _numero(fin):
            ident = (
                clave,
                _clave(fila["speaker_id"]),
                float(inicio),
                float(fin),
                _clave(fila["annotation_raw"]),
                _clave(fila["reference_origin"]),
            )

            if ident in vistos:
                duplicados.append(i)

            vistos.add(ident)

    for codigo, detalle, filas in (
        (
            "grabacion_inexistente",
            "Intervalos que no tienen grabación",
            sin_grabacion,
        ),
        (
            "intervalo_invalido",
            "Inicio/fin fuera de límites",
            limites,
        ),
        (
            "silencio_puntuado_como_habla",
            "Marcador # incompatible con puntuación de habla",
            silencio,
        ),
        (
            "habla_sin_hablante",
            "Un segmento puntuado necesita hablante",
            sin_sp,
        ),
        (
            "segmento_duplicado",
            "Intervalos idénticos repetidos",
            duplicados,
        ),
    ):
        if filas:
            issues.append(
                _reporte(nombre, codigo, detalle, filas)
            )

    issues.extend(
        _enlaces_hablantes(
            nombre, df, hablantes, grabaciones
        )
    )
    return issues


def _particiones(tablas: dict[str, pd.DataFrame]) -> list[dict]:
    grupos: dict[tuple[str, str], set[str]] = defaultdict(set)
    ubicacion: dict[tuple[str, str], list[str]] = defaultdict(list)

    for nombre in ("asr_instancias", "diarizacion_grabaciones"):
        if nombre not in tablas:
            continue

        for i, fila, clave in _sin_faltantes(
            tablas[nombre], ("source", "recording_id")
        ):
            group = _clave(fila["group_id"])
            split = _clave(fila["project_split"])

            if group is None or split is None:
                continue

            k = (clave[0], group)
            grupos[k].add(split)
            ubicacion[k].append(f"{nombre}:{i}")

    conflictos = [
        (k, ubicacion[k])
        for k, partes in grupos.items()
        if len(partes) > 1
    ]

    if not conflictos:
        return []

    return [
        _reporte(
            "normalizado",
            "grupo_en_distintas_particiones",
            ", ".join(
                f"{a}:{b}"
                for (a, b), _ in conflictos[:10]
            ),
            [
                v
                for _, filas in conflictos[:10]
                for v in filas[:3]
            ],
        )
    ]


def _consistencia_modalidades(
    tablas: dict[str, pd.DataFrame],
) -> list[dict]:
    if not {
        "asr_instancias", "diarizacion_grabaciones"
    } <= tablas.keys():
        return []

    origen = {}

    for _, fila, clave in _sin_faltantes(
        tablas["asr_instancias"],
        ("source", "recording_id"),
    ):
        origen[clave] = fila

    diferentes = []

    for i, fila, clave in _sin_faltantes(
        tablas["diarizacion_grabaciones"],
        ("source", "recording_id"),
    ):
        anterior = origen.get(clave)
        if anterior is None:
            continue

        for columna in ("session_id", "group_id"):
            a = _clave(anterior[columna])
            b = _clave(fila[columna])

            if a is not None and b is not None and a != b:
                diferentes.append(i)
                break

    if diferentes:
        return [
            _reporte(
                "diarizacion_grabaciones",
                "identidad_multimodal_incompatible",
                "Grabación compartida con distinta sesión o grupo",
                diferentes,
            )
        ]

    return []


def validar_tablas(
    tablas: dict[str, pd.DataFrame],
    componente: str = "todos",
) -> list[dict]:
    """Valida sin modificar datos ni imputar valores."""
    if componente not in {"asr", "diarizacion", "todos"}:
        raise ValueError(f"Componente inválido: {componente}")

    nombres = [
        n for n in ARCHIVOS
        if componente == "todos"
        or n.startswith("asr_") == (componente == "asr")
    ]

    issues = []

    for nombre in nombres:
        df = tablas.get(nombre)

        if df is None:
            issues.append(
                _reporte(
                    nombre, "tabla_ausente", ARCHIVOS[nombre]
                )
            )
        elif not isinstance(df, pd.DataFrame):
            issues.append(
                _reporte(
                    nombre, "tipo_invalido",
                    "Se esperaba DataFrame",
                )
            )
        else:
            issues.extend(
                _columnas_y_valores(nombre, df)
            )

    # Se verifican relaciones solo cuando están las columnas necesarias.
    validas = {
        nombre: tablas[nombre]
        for nombre in nombres
        if nombre in tablas
        and isinstance(tablas[nombre], pd.DataFrame)
        and set(COLUMNAS[nombre]).issubset(
            tablas[nombre].columns
        )
        and tablas[nombre].columns.is_unique
    }

    for nombre in (
        "asr_instancias", "diarizacion_grabaciones"
    ):
        if nombre in validas:
            issues.extend(
                _grabaciones(nombre, validas[nombre])
            )

    for nombre in (
        "asr_hablantes", "diarizacion_hablantes"
    ):
        if nombre in validas:
            issues.extend(
                _hablantes(nombre, validas[nombre])
            )

    if {
        "asr_instancias", "asr_hablantes"
    } <= validas.keys():
        issues.extend(
            _enlaces_hablantes(
                "asr_instancias",
                validas["asr_instancias"],
                validas["asr_hablantes"],
            )
        )

    if {
        "diarizacion_grabaciones",
        "diarizacion_segmentos",
        "diarizacion_hablantes",
    } <= validas.keys():
        issues.extend(
            _segmentos(
                validas["diarizacion_segmentos"],
                validas["diarizacion_grabaciones"],
                validas["diarizacion_hablantes"],
            )
        )

    issues.extend(
        _consistencia_modalidades(validas)
    )
    issues.extend(
        _particiones(validas)
    )

    return issues


def cargar(
    raiz: Path,
    componente: str,
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    tablas, fallos = {}, []

    nombres = [
        n for n in ARCHIVOS
        if componente == "todos"
        or n.startswith("asr_") == (componente == "asr")
    ]

    for nombre in nombres:
        ruta = raiz / ARCHIVOS[nombre]

        if not ruta.is_file():
            continue

        try:
            if ruta.suffix == ".parquet":
                tablas[nombre] = pd.read_parquet(ruta)
            else:
                tablas[nombre] = pd.read_csv(
                    ruta,
                    keep_default_na=False,
                    na_values=[""],
                    dtype={
                        "source": "string",
                        "recording_id": "string",
                        "source_recording_id": "string",
                        "speaker_id": "string",
                        "source_speaker_id": "string",
                        "session_id": "string",
                        "group_id": "string",
                        "source_split": "string",
                        "project_split": "string",
                    },
                )
        except (OSError, ValueError, ImportError, KeyError) as error:
            fallos.append(
                _reporte(
                    nombre,
                    "lectura_fallida",
                    (
                        f"{ruta}: {type(error).__name__}: "
                        f"{error}"
                    ),
                )
            )

    return tablas, fallos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raiz", type=Path, default=RAIZ
    )
    parser.add_argument(
        "--componente",
        choices=("asr", "diarizacion", "todos"),
        default="todos",
    )
    parser.add_argument(
        "--informe",
        type=Path,
        help="Guardar los errores como JSON (opcional)",
    )
    args = parser.parse_args(argv)

    tablas, errores = cargar(
        args.raiz, args.componente
    )
    errores.extend(
        validar_tablas(tablas, args.componente)
    )

    resultado = {
        "estado": "OK" if not errores else "ERROR",
        "componente": args.componente,
        "tablas": {
            k: len(v) for k, v in tablas.items()
        },
        "errores": errores,
    }

    if args.informe:
        args.informe.parent.mkdir(
            parents=True, exist_ok=True
        )
        args.informe.write_text(
            json.dumps(
                resultado,
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    print(
        f"{resultado['estado']}: "
        f"{len(tablas)} tablas leídas, "
        f"{len(errores)} incidencias"
    )

    for error in errores:
        print(
            f"  {error['tabla']} | {error['codigo']} "
            f"| {error['detalle']} "
            f"| filas: {error['filas']}"
        )

    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())