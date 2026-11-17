"""Workflow de minutas: adaptar, extraer, consolidar, validar y presentar."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ..rutas import (
    DEFINICIONES_SECCIONES_MINUTAS,
    PROMPT_CONSOLIDACION_MINUTAS,
    PROMPT_EXTRACCION_MINUTAS,
    rutas_resultado_minutas,
)

from .contratos import (
    Intervencion, SECCIONES_MINUTA, modelo_minuta, validar_evidencias, validar_secciones,
)
from .entrada import leer_transcripcion, representar_intervenciones
from .experimento import Bloque, ExperimentoMinutas
from .formato import a_markdown
from .modelos import MODELO_PREDETERMINADO, obtener_modelo
from .proveedores import (
    ClienteModelo, ClienteOllama, LimiteModelo, RespuestaEstructuradaAusente, construir_cliente,
    resolver_destino, comprobar_autorizacion, liberar_modelo_ollama,
)


@dataclass(frozen=True)
class ConfiguracionMinutas:
    modelo: str = MODELO_PREDETERMINADO
    permitir_remoto: bool = False
    temperatura: float = 0.0
    num_ctx: int = 16384
    max_tokens_salida: int = 4096
    max_caracteres_bloque: int = 12000
    reintentos_formato: int = 2
    secciones: tuple[str, ...] = SECCIONES_MINUTA
    destino_autorizado: str | None = None  # solo para la solicitud actual

    def __post_init__(self) -> None:
        obtener_modelo(self.modelo)
        if type(self.permitir_remoto) is not bool:
            raise ValueError("permitir_remoto debe ser booleano.")
        if type(self.temperatura) not in (int, float) or not 0 <= self.temperatura <= 1:
            raise ValueError("La temperatura debe ser numérica y estar entre 0 y 1.")
        if any(type(valor) is not int for valor in (self.num_ctx, self.max_tokens_salida,
                                                   self.max_caracteres_bloque, self.reintentos_formato)):
            raise ValueError("Los presupuestos y la cantidad de reintentos deben ser enteros.")
        if self.num_ctx < 2048 or self.max_tokens_salida < 256:
            raise ValueError("Los límites de contexto y generación son demasiado pequeños.")
        if self.max_caracteres_bloque < 1000:
            raise ValueError("El límite de caracteres por bloque debe ser al menos 1000.")
        if self.reintentos_formato < 0:
            raise ValueError("Los reintentos no pueden ser negativos.")
        validar_secciones(self.secciones)


@dataclass(frozen=True)
class ResultadoMinutas:
    json: Path
    markdown: Path
    manifiesto: Path
    llamadas_modelo: int
    duracion_s: float


def _preparar_prompts(secciones: tuple[str, ...]) -> tuple[str, str, dict[str, str]]:
    """Incorpora solo las definiciones seleccionadas; los archivos son la fuente normativa."""
    validar_secciones(secciones)
    bytes_definiciones = DEFINICIONES_SECCIONES_MINUTAS.read_bytes()
    definiciones = json.loads(bytes_definiciones)
    if not isinstance(definiciones, dict) or set(definiciones) != set(SECCIONES_MINUTA):
        raise ValueError("Las definiciones de secciones no coinciden con el contrato.")
    if any(not isinstance(valor, str) or not valor.strip() for valor in definiciones.values()):
        raise ValueError("Todas las definiciones deben contener texto en español.")
    descripcion = "\n".join(f"- `{seccion}`: {definiciones[seccion]}" for seccion in secciones)

    prompts: list[str] = []
    hashes: dict[str, str] = {}
    for ruta in (PROMPT_EXTRACCION_MINUTAS, PROMPT_CONSOLIDACION_MINUTAS):
        plantilla = ruta.read_text(encoding="utf-8").strip()
        marca = "{{SECCIONES_SOLICITADAS}}"
        if plantilla.count(marca) != 1:
            raise ValueError(f"El prompt {ruta.name} debe contener una sola marca {marca}.")
        texto = plantilla.replace(marca, descripcion)
        prompts.append(texto)
        hashes[ruta.name] = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    hashes[DEFINICIONES_SECCIONES_MINUTAS.name] = hashlib.sha256(bytes_definiciones).hexdigest()
    return prompts[0], prompts[1], hashes


VERSION_CONSOLIDACION = 2
_MAX_PROFUNDIDAD_EXTRACCION = 8
_MAX_SUBDIVISIONES_POR_BLOQUE = 31


def _json(datos: Any) -> str:
    return json.dumps(datos, ensure_ascii=False, separators=(",", ":"))


def _presupuesto(config: ConfiguracionMinutas, instrucciones: str,
                 esquema: dict[str, Any]) -> Callable[[str], bool]:
    modelo = obtener_modelo(config.modelo)
    contexto = modelo.contexto_maximo
    if modelo.proveedor == "ollama":
        if config.num_ctx > contexto:
            raise ValueError("El contexto solicitado supera el admitido por el modelo.")
        contexto = config.num_ctx
    if config.max_tokens_salida > modelo.salida_maxima:
        raise ValueError("El límite de generación solicitado supera el admitido por el modelo.")
    # Estimación de 2 bytes/token, con margen para plantilla y protocolo.
    fijos = len(instrucciones.encode("utf-8")) + len(_json(esquema).encode("utf-8"))
    bytes_datos = 2 * (contexto - config.max_tokens_salida - 512) - fijos
    if bytes_datos <= 0:
        raise ValueError("El contexto solicitado no deja espacio para los datos y el esquema.")
    return lambda texto: (len(texto) <= config.max_caracteres_bloque
                          and len(texto.encode("utf-8")) <= bytes_datos)


def _partir_intervencion(intervencion: Intervencion, cabe: Callable[[str], bool], max_caracteres: int,
                         experimento: ExperimentoMinutas | None = None) -> list[Intervencion]:
    """Partes textuales del mismo intervalo y del mismo identificador original."""
    if cabe(representar_intervenciones([intervencion])):
        return [intervencion]
    texto = intervencion.texto
    partes = []
    while texto:
        bajo, alto = 0, min(len(texto), max_caracteres)
        while bajo < alto:
            medio = (bajo + alto + 1) // 2
            parte = intervencion.model_copy(update={"texto": texto[:medio]})
            if cabe(representar_intervenciones([parte])):
                bajo = medio
            else:
                alto = medio - 1
        if bajo == 0:
            raise ValueError(f"Los metadatos de {intervencion.id} no caben en el presupuesto de extracción.")
        corte = bajo
        if bajo < len(texto):
            espacio = max((i + 1 for i, c in enumerate(texto[:bajo]) if c.isspace()), default=0)
            if espacio >= bajo // 2 and espacio > 0:
                corte = espacio
        parte = intervencion.model_copy(update={"texto": texto[:corte]})
        if experimento is not None:
            experimento.registrar_fragmento(intervencion, parte, len(intervencion.texto) - len(texto))
        partes.append(parte)
        texto = texto[corte:]
    return partes


def _fragmentar_intervenciones(
    intervenciones: list[Intervencion], cabe: Callable[[str], bool], max_caracteres: int,
    experimento: ExperimentoMinutas | None = None,
) -> list[list[Intervencion]]:
    bloques: list[list[Intervencion]] = []
    actual: list[Intervencion] = []
    for original in intervenciones:
        for intervencion in _partir_intervencion(original, cabe, max_caracteres, experimento):
            candidato = actual + [intervencion]
            if cabe(representar_intervenciones(candidato)):
                actual = candidato
                continue
            bloques.append(actual)
            contexto = actual[-2:]
            while contexto and not cabe(representar_intervenciones(contexto + [intervencion])):
                contexto = contexto[1:]
            actual = contexto + [intervencion]
    if actual:
        bloques.append(actual)
    return bloques


def huella_experimento(config: ConfiguracionMinutas) -> str:
    """Fija configuración, prompts y versión de consolidación para comparar."""
    _, _, prompts = _preparar_prompts(config.secciones)
    datos = {"configuracion": asdict(config), "prompts": prompts, "consolidacion": VERSION_CONSOLIDACION}
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _datos_minutas(minutas: list[BaseModel]) -> str:
    return _json({"minutas_parciales": [item.model_dump() for item in minutas]})


def _agrupar_minutas(minutas: list[BaseModel], cabe: Callable[[str], bool]) -> list[list[BaseModel]]:
    """Un parcial demasiado grande se conserva aislado; no se envía así al LLM."""
    grupos: list[list[BaseModel]] = []
    actual: list[BaseModel] = []
    for minuta in minutas:
        if actual and not cabe(_datos_minutas(actual + [minuta])):
            grupos.append(actual)
            actual = []
        actual.append(minuta)
    if actual:
        grupos.append(actual)
    return grupos


def _union_minutas(minutas: list[BaseModel], tipo: type[BaseModel]) -> BaseModel:
    """Unión estable: misma afirmación y ancla pueden compartir evidencias."""
    datos = {}
    for seccion in tipo.model_fields:
        if seccion == "resumen":
            datos[seccion] = "\n\n".join(dict.fromkeys(m.resumen for m in minutas))
        else:
            unicos = {}
            for minuta in minutas:
                for elemento in getattr(minuta, seccion):
                    registro = elemento.model_dump()
                    clave = _json({k: v for k, v in registro.items() if k != "ids_intervenciones"})
                    if clave in unicos:
                        anterior = unicos[clave]["ids_intervenciones"]
                        unicos[clave]["ids_intervenciones"] = list(dict.fromkeys(
                            anterior + registro["ids_intervenciones"]))
                    else:
                        unicos[clave] = registro
            datos[seccion] = list(unicos.values())
    return tipo.model_validate(datos)


def _cobertura(minutas: list[BaseModel], secciones: tuple[str, ...]) -> dict[str, set[str]]:
    return {seccion: {identificador for minuta in minutas
                      for elemento in getattr(minuta, seccion)
                      for identificador in elemento.ids_intervenciones}
            for seccion in secciones if seccion != "resumen"}


class _FormatoAgotado(ValueError):
    """El modelo no produjo una salida estructuralmente válida tras los reintentos."""


def _guardar_resultados(
    contenidos: tuple[tuple[Path, str], ...], *, sobrescribir: bool
) -> None:
    """Prepara las salidas antes de sustituirlas y revierte fallos de escritura.

    Cada reemplazo es atómico, pero el conjunto no lo es ante una interrupción
    abrupta del proceso. El manifiesto se publica en último lugar.
    """
    directorio = contenidos[0][0].parent
    directorio.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".minutas-", dir=directorio) as temporal:
        carpeta = Path(temporal)
        preparados: dict[Path, Path] = {}
        respaldos: dict[Path, Path] = {}

        for numero, (destino, contenido) in enumerate(contenidos):
            preparado = carpeta / f"nuevo-{numero}"
            # El SHA-256 del JSON se calcula sobre UTF-8 con saltos LF.
            preparado.write_text(contenido, encoding="utf-8", newline="\n")
            preparado.chmod(0o600)
            preparados[destino] = preparado
            if destino.exists():
                respaldo = carpeta / f"anterior-{numero}"
                shutil.copy2(destino, respaldo)
                respaldos[destino] = respaldo

        if not sobrescribir and respaldos:
            raise FileExistsError(
                "Ya existe un resultado de minutas. Elegí otra carpeta o sobrescribir=True."
            )

        reemplazados: list[Path] = []
        try:
            for destino, _ in contenidos:
                os.replace(preparados[destino], destino)
                reemplazados.append(destino)
        except BaseException:
            for destino in reversed(reemplazados):
                if destino in respaldos:
                    os.replace(respaldos[destino], destino)
                else:
                    destino.unlink(missing_ok=True)
            raise


def _describir_error_validacion(error: ValidationError | ValueError | TypeError) -> str:
    """Diagnóstico acotado, sin copiar valores devueltos por el modelo."""
    if isinstance(error, ValidationError):
        if any(d["type"] == "missing" for d in error.errors(include_input=False, include_url=False)):
            return "faltan campos obligatorios"
        return "campos, tipos o evidencias fuera del contrato"
    if isinstance(error, json.JSONDecodeError):
        return "JSON inválido"
    if isinstance(error, ValueError) and "referencias inexistentes" in str(error):
        return "referencias inexistentes"
    return "campos, tipos o evidencias fuera del contrato"


def _integrar_anclas_en_evidencias(contenido: Any) -> tuple[Any, int]:
    """Integra las anclas declaradas por el modelo en sus evidencias.

    No modifica las anclas ni crea identificadores. La validación posterior
    comprueba que todas las referencias existan en la entrada correspondiente.
    """
    if not isinstance(contenido, dict):
        return contenido, 0

    normalizado = dict(contenido)
    cambios = 0

    for categoria in ("temas", "decisiones", "problemas", "acciones"):
        elementos = normalizado.get(categoria)
        if not isinstance(elementos, list):
            continue

        revisados = []
        for elemento in elementos:
            if not isinstance(elemento, dict):
                revisados.append(elemento)
                continue

            ancla = elemento.get("id_ancla")
            evidencias = elemento.get("ids_intervenciones")

            if (
                isinstance(ancla, str)
                and ancla
                and isinstance(evidencias, list)
                and all(isinstance(identificador, str) for identificador in evidencias)
                and ancla not in evidencias
            ):
                elemento = {
                    **elemento,
                    "ids_intervenciones": [*evidencias, ancla],
                }
                cambios += 1

            revisados.append(elemento)

        normalizado[categoria] = revisados

    return normalizado, cambios


def generar_minuta(
    entrada: str | Path | dict[str, Any],
    directorio_salida: str | Path,
    *,
    modelo: str = MODELO_PREDETERMINADO,
    permitir_remoto: bool = False,
    configuracion: ConfiguracionMinutas | None = None,
    secciones: tuple[str, ...] | None = None,
    cliente: ClienteModelo | None = None,
    sobrescribir: bool = False,
    experimento: ExperimentoMinutas | None = None,
) -> ResultadoMinutas:
    """Produce únicamente las secciones solicitadas en minutes.json y minutes.md."""
    inicio = time.monotonic()
    if configuracion is not None and secciones is not None:
        raise ValueError("Indicá las secciones en la configuración o como argumento, no en ambos.")
    config = configuracion or ConfiguracionMinutas(
        modelo=modelo, permitir_remoto=permitir_remoto,
        secciones=SECCIONES_MINUTA if secciones is None else secciones,
    )
    rutas = rutas_resultado_minutas(directorio_salida)
    destinos = (rutas.json, rutas.markdown, rutas.manifiesto)
    if not sobrescribir and any(ruta.exists() for ruta in destinos):
        raise FileExistsError("Ya existe un resultado de minutas. Elegí otra carpeta o sobrescribir=True.")
    todas, bytes_origen = leer_transcripcion(entrada)
    intervenciones = [i for i in todas if i.inicio is not None]
    if not intervenciones:
        raise ValueError("No existe evidencia temporal utilizable para generar la minuta; se conserva la transcripción.")
    extraccion, consolidacion, hashes_prompts = _preparar_prompts(config.secciones)
    destino = resolver_destino(config.modelo)
    try:
        comprobar_autorizacion(destino, config.permitir_remoto, config.destino_autorizado)
    except PermissionError as exc:
        raise ValueError(str(exc)) from None
    tipo_minuta = modelo_minuta(config.secciones)
    esquema = tipo_minuta.model_json_schema()
    cabe_extraccion = _presupuesto(config, extraccion, esquema)
    cabe_consolidacion = _presupuesto(config, consolidacion, esquema)
    grupos_experimento: list[list[Intervencion]] | None = None
    if experimento is not None:
        grupos_experimento = experimento.preparar(
            intervenciones, hashlib.sha256(bytes_origen).hexdigest(), huella_experimento(config), cabe_extraccion)
    llm = cliente or construir_cliente(
        config.modelo, permitir_remoto=config.permitir_remoto,
        temperatura=config.temperatura, num_ctx=config.num_ctx,
        max_tokens=config.max_tokens_salida, destino_autorizado=destino.huella,
    )
    if llm.proveedor != "ollama" and not config.permitir_remoto:
        raise ValueError("El proveedor remoto no está habilitado.")

    llamadas = 0
    tokens_entrada = 0
    tokens_salida = 0
    medido_entrada = 0
    medido_salida = 0
    normalizaciones_ancla = 0
    recuperaciones_extraccion = 0
    motivos_union = {"presupuesto": 0, "limite_modelo": 0, "formato": 0, "evidencias": 0}
    niveles_consolidacion = 0
    bloques_extraccion = 0
    sintesis_resumen = 0
    alternativas_resumen = 0
    max_caracteres_enviados = 0
    max_bytes_enviados = 0
    hash_prompt_resumen = None

    def medir(respuesta: Any) -> None:
        nonlocal tokens_entrada, tokens_salida, medido_entrada, medido_salida
        if respuesta.tokens_entrada is not None:
            tokens_entrada += respuesta.tokens_entrada
            medido_entrada += 1
        if respuesta.tokens_salida is not None:
            tokens_salida += respuesta.tokens_salida
            medido_salida += 1

    def pedir(instrucciones: str, datos: str, evidencias: list[Intervencion],
              tipo: type[BaseModel] = tipo_minuta) -> BaseModel:
        nonlocal llamadas, normalizaciones_ancla, max_caracteres_enviados, max_bytes_enviados
        esquema = tipo.model_json_schema()
        mensaje = datos
        instrucciones_intento = instrucciones
        cabe = _presupuesto(config, instrucciones, esquema)
        if not cabe(datos):
            raise LimiteModelo("La entrada estructurada supera el presupuesto efectivo.")

        def reparar(aviso: str) -> tuple[str, str]:
            # No reenviar la salida inválida, que puede ser arbitrariamente grande.
            if cabe(datos + aviso):
                return datos + aviso, instrucciones
            nuevas = instrucciones + aviso
            if _presupuesto(config, nuevas, esquema)(datos):
                return datos, nuevas
            raise LimiteModelo("No queda margen de contexto para reparar la respuesta.")

        ultimo_error: Exception | None = None
        for intento in range(config.reintentos_formato + 1):
            llamadas += 1
            max_caracteres_enviados = max(max_caracteres_enviados, len(mensaje))
            max_bytes_enviados = max(max_bytes_enviados, len(mensaje.encode("utf-8")))
            try:
                respuesta = llm.responder(instrucciones_intento, mensaje, esquema)
            except LimiteModelo as exc:
                medir(exc)
                raise
            except RespuestaEstructuradaAusente as exc:
                medir(exc)
                ultimo_error = exc
                if intento < config.reintentos_formato:
                    mensaje, instrucciones_intento = reparar(
                        "\n\nLa respuesta anterior no incluyó la salida "
                        "estructurada requerida. Volvé a intentarlo utilizando "
                        "el esquema y todas las secciones solicitadas."
                    )
                    continue
                break
            medir(respuesta)
            try:
                contenido = (
                    json.loads(respuesta.contenido)
                    if isinstance(respuesta.contenido, str)
                    else respuesta.contenido
                )
                contenido, cambios = _integrar_anclas_en_evidencias(contenido)
                minuta = tipo.model_validate(contenido)
                validar_evidencias(minuta, evidencias)
                normalizaciones_ancla += cambios
                return minuta
            except (ValidationError, ValueError, TypeError) as exc:
                ultimo_error = exc
                if intento < config.reintentos_formato:
                    detalle = _describir_error_validacion(exc)
                    mensaje, instrucciones_intento = reparar(
                        "\n\nLa respuesta anterior fue inválida. "
                        f"Corregí la respuesta según el esquema y los datos originales ({detalle}). "
                        "No inventes hechos ni identificadores."
                    )
        raise _FormatoAgotado(
            "El modelo no produjo una minuta estructuralmente válida "
            f"tras {config.reintentos_formato + 1} intentos ({type(ultimo_error).__name__})."
        ) from None

    def extraer(grupo: list[Intervencion], profundidad: int = 0,
                contador: list[int] | None = None, padre: Bloque | None = None) -> list[BaseModel]:
        nonlocal recuperaciones_extraccion, bloques_extraccion
        if contador is None:
            contador = [0]
        try:
            resultado = pedir(extraccion, representar_intervenciones(grupo), grupo)
            bloques_extraccion += 1
            if experimento is not None:
                experimento.registrar_bloque(grupo, padre)
            return [resultado]
        except LimiteModelo:
            if (profundidad >= _MAX_PROFUNDIDAD_EXTRACCION
                    or contador[0] >= _MAX_SUBDIVISIONES_POR_BLOQUE):
                raise LimiteModelo(
                    f"Se agotó la subdivisión de extracción por límite del modelo "
                    f"(profundidad {profundidad}, {contador[0]} subdivisiones del bloque)."
                ) from None
            if len(grupo) > 1:
                corte = len(grupo) // 2
                izquierda, derecha = grupo[:corte], grupo[corte:]
            else:
                original = grupo[0]
                corte = len(original.texto) // 2
                if corte == 0:
                    raise LimiteModelo("Una extracción mínima supera el límite del modelo.") from None
                izquierda = [original.model_copy(update={"texto": original.texto[:corte]})]
                derecha = [original.model_copy(update={"texto": original.texto[corte:]})]
                if experimento is not None:
                    experimento.registrar_fragmento(original, izquierda[0], 0)
                    experimento.registrar_fragmento(original, derecha[0], corte)
            contador[0] += 1
            recuperaciones_extraccion += 1
            return (extraer(izquierda, profundidad + 1, contador, padre)
                    + extraer(derecha, profundidad + 1, contador, padre))

    def recuperar_union(grupo: list[BaseModel], motivo: str) -> BaseModel:
        """Conservar listas; intentar una síntesis de resúmenes con esquema reducido."""
        nonlocal sintesis_resumen, alternativas_resumen, hash_prompt_resumen
        motivos_union[motivo] += 1
        union = _union_minutas(grupo, tipo_minuta)
        if "resumen" not in config.secciones:
            return union
        textos = list(dict.fromkeys(m.resumen for m in grupo))
        if len(textos) == 1:
            return union
        # No repetir la misma solicitud si el esquema original ya era solo resumen.
        if config.secciones == ("resumen",):
            alternativas_resumen += 1
            return union
        tipo = modelo_minuta(("resumen",))
        _, prompt, hashes = _preparar_prompts(("resumen",))
        cabe = _presupuesto(config, prompt, tipo.model_json_schema())
        pendientes = [tipo.model_validate({"resumen": t}) for t in textos]
        while len(pendientes) > 1:
            grupos_resumen = _agrupar_minutas(pendientes, cabe)
            if len(grupos_resumen) == len(pendientes):
                break
            siguiente = []
            for parte in grupos_resumen:
                if len(parte) == 1:
                    siguiente.append(parte[0])
                    continue
                hash_prompt_resumen = hashes[PROMPT_CONSOLIDACION_MINUTAS.name]
                try:
                    siguiente.append(pedir(prompt, _datos_minutas(parte), [], tipo))
                    sintesis_resumen += 1
                except (LimiteModelo, _FormatoAgotado):
                    siguiente.append(_union_minutas(parte, tipo))
                    alternativas_resumen += 1
            pendientes = siguiente
        if len(pendientes) > 1:
            alternativas_resumen += 1
        resumen = _union_minutas(pendientes, tipo).resumen
        return tipo_minuta.model_validate({**union.model_dump(), "resumen": resumen})

    try:
        grupos = (grupos_experimento if grupos_experimento is not None else
                  _fragmentar_intervenciones(intervenciones, cabe_extraccion, config.max_caracteres_bloque, experimento))
        parciales = [parcial for indice, grupo in enumerate(grupos)
                     for parcial in extraer(grupo, padre=experimento.plan[indice]
                                            if experimento and experimento.plan else None)]
        por_id = {i.id: i for i in intervenciones}
        while len(parciales) > 1:
            niveles_consolidacion += 1
            grupos_minutas = _agrupar_minutas(parciales, cabe_consolidacion)
            if len(grupos_minutas) == len(parciales):
                parciales = [recuperar_union(parciales, "presupuesto")]
                break
            siguientes: list[BaseModel] = []
            for grupo in grupos_minutas:
                if len(grupo) == 1:
                    siguientes.append(grupo[0])
                    continue
                cobertura = _cobertura(grupo, config.secciones)
                ids = set().union(*cobertura.values())
                try:
                    consolidada = pedir(consolidacion, _datos_minutas(grupo),
                                         [por_id[i] for i in sorted(ids)])
                except LimiteModelo:
                    siguientes.append(recuperar_union(grupo, "limite_modelo"))
                except _FormatoAgotado:
                    siguientes.append(recuperar_union(grupo, "formato"))
                else:
                    # No descartar ni trasladar evidencias entre categorías para hacer
                    # caber el resultado. No equivale a validar la cobertura semántica.
                    if _cobertura([consolidada], config.secciones) != cobertura:
                        siguientes.append(recuperar_union(grupo, "evidencias"))
                    else:
                        siguientes.append(consolidada)
            parciales = siguientes
        minuta_final = parciales[0]
        validar_evidencias(minuta_final, intervenciones)
        texto_json = minuta_final.model_dump_json(indent=2) + "\n"
        texto_markdown = a_markdown(minuta_final, todas)
        manifiesto = {
            "version_esquema": 1,
            "creado_utc": datetime.now(timezone.utc).isoformat(),
            "sha256_entrada": hashlib.sha256(bytes_origen).hexdigest(),
            "modelo": llm.nombre,
            "proveedor": llm.proveedor,
            "secciones": list(config.secciones),
            "configuracion": {k: v for k, v in asdict(config).items() if k != "destino_autorizado"},
            "destino": destino.tipo,
            "huella_destino": destino.huella,
            "prompts": hashes_prompts,
            "intervenciones": len(intervenciones),
            "intervenciones_sin_ubicacion_excluidas": len(todas) - len(intervenciones),
            "bloques_extraccion": bloques_extraccion,
            "consolidacion": {
                "version": VERSION_CONSOLIDACION,
                "bloques_iniciales": len(grupos),
                "subdivisiones_extraccion": recuperaciones_extraccion,
                "niveles": niveles_consolidacion,
                "uniones_locales": sum(motivos_union.values()),
                "motivos_union": motivos_union,
                "sintesis_resumen": sintesis_resumen,
                "concatenaciones_resumen": alternativas_resumen,
                "sha256_prompt_resumen": hash_prompt_resumen,
                "max_caracteres_enviados": max_caracteres_enviados,
                "max_bytes_enviados": max_bytes_enviados,
            },
            "llamadas_modelo": llamadas,
            "normalizaciones_ancla": normalizaciones_ancla,
            "tokens_entrada": tokens_entrada if medido_entrada else None,
            "tokens_salida": tokens_salida if medido_salida else None,
            "llamadas_con_tokens_entrada": medido_entrada,
            "llamadas_con_tokens_salida": medido_salida,
            "duracion_s": round(time.monotonic() - inicio, 3),
            "sha256_minuta_json": hashlib.sha256(texto_json.encode("utf-8")).hexdigest(),
        }
        _guardar_resultados(
            (
                (rutas.json, texto_json),
                (rutas.markdown, texto_markdown),
                (rutas.manifiesto, json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n"),
            ),
            sobrescribir=sobrescribir,
        )
        return ResultadoMinutas(
            json=rutas.json, markdown=rutas.markdown, manifiesto=rutas.manifiesto,
            llamadas_modelo=llamadas, duracion_s=manifiesto["duracion_s"],
        )
    finally:
        if llamadas and cliente is None and isinstance(llm, ClienteOllama):
            liberar_modelo_ollama(llm.nombre, destino=llm.destino)
