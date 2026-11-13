"""Tareas 4.3 y 4.4: diarizar() con un pipeline y un torch falsos (sin modelo ni GPU)."""

import gc
import hashlib
import json
import os
import types
import weakref

import pytest

import diarizar as modulo
from contrato import validar_diarizacion, validar_par
from errores import DiarizacionError
from resultados import NOMBRE_ERROR, NOMBRE_JSON, NOMBRE_META

TURNOS = [(0.5, 4.2, "SPEAKER_00"), (3.9, 8.1, "SPEAKER_01"), (8.5, 9.9999, "SPEAKER_00")]


class PipelineFalso:
    """Registra lo que le hacen en `registro` (no en sí mismo), para poder comprobar con weakref que
    diarizar() no deja referencias al pipeline."""

    def __init__(self, registro, turnos=TURNOS, falla=None):
        self.registro, self.turnos, self.falla = registro, turnos, falla

    def to(self, dispositivo):
        self.registro.dispositivos.append(dispositivo)
        return self

    def __call__(self, ruta, **kwargs):
        self.registro.llamadas.append((ruta, kwargs))
        if self.falla is not None:
            # Instancia nueva en cada llamada, como el modelo real: la plantilla `self.falla` la guarda la
            # prueba, y si se lanzara ella misma su traceback mantendría vivo a este pipeline.
            raise type(self.falla)(*self.falla.args)
        anotacion = [(types.SimpleNamespace(start=s, end=e), h) for s, e, h in self.turnos]
        return types.SimpleNamespace(speaker_diarization=anotacion)


@pytest.fixture
def entorno(monkeypatch, torch_falso, sin_token, tmp_path):
    """Instala un torch falso y un cargador de pipeline falso; devuelve un objeto para configurarlos."""
    monkeypatch.chdir(tmp_path)  # sin .env: el token queda en None salvo que la prueba lo defina
    estado = types.SimpleNamespace(creados=0, refs=[], dispositivos=[], llamadas=[], falla=None, falla_carga=None,
                                   torch=None, tokens=[], turnos=TURNOS)

    def preparar(cuda=False):
        estado.torch = torch_falso(cuda=cuda)
        return estado

    def cargar(token):
        estado.tokens.append(token)
        if estado.falla_carga is not None:
            raise estado.falla_carga
        p = PipelineFalso(estado, turnos=estado.turnos, falla=estado.falla)
        estado.creados += 1
        estado.refs.append(weakref.ref(p))
        return p

    monkeypatch.setattr(modulo, "_cargar_pipeline", cargar)
    estado.preparar = preparar
    return estado


def _sha(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def test_exito_escribe_el_par(entorno, wav):
    entorno.preparar(cuda=False)
    audio = wav("2026_11_07_10_00_00.wav", segundos=10)
    r = modulo.diarizar(audio)
    carpeta = audio.parent / "2026_11_07_10_00_00"
    assert r["carpeta"] == str(carpeta) and r["dispositivo"] == "cpu" and r["hablantes"] == 2
    datos = json.loads((carpeta / NOMBRE_JSON).read_text(encoding="utf-8"))
    assert set(datos) == {"segments"} and validar_diarizacion(datos, 10.0) == []
    assert datos["segments"][2] == {"start": 8.5, "end": 10.0, "speaker": "SPEAKER_00"}
    assert validar_par(carpeta / NOMBRE_JSON, carpeta / NOMBRE_META) == []
    meta = json.loads((carpeta / NOMBRE_META).read_text(encoding="utf-8"))
    assert meta["dispositivo"] == "cpu" and meta["modo_dispositivo"] == "auto" and meta["gpu"] is None
    assert meta["audio"]["duracion_s"] == 10.0 and meta["audio"]["sha256"] == _sha(audio)
    assert meta["modelo"] == "pyannote/speaker-diarization-community-1"
    assert meta["num_speakers"] is None and meta["tolerancia_fin_s"] == 0.05
    assert meta["exceso_fin_max_s"] == 0.0 and meta["segmentos_corregidos"] == 0
    assert (meta["hablantes"], meta["segmentos"]) == (2, 3)
    assert entorno.dispositivos[0] == "cpu"
    assert entorno.llamadas == [(str(audio.absolute()), {})]  # ruta del audio, sin num_speakers
    assert entorno.torch.llamadas["empty_cache"] == 0  # en CPU no se vacía la caché de CUDA


def test_regresion_meta_con_el_ultimo_tramo_recortado(entorno, wav):
    """Tarea 2.4: el caso de la grabación interrumpida 2026_11_08_11_41_26.wav con un pipeline falso."""
    entorno.preparar()
    entorno.turnos = [(26.5922, 32.5997, "SPEAKER_00"), (0.3685, 2.3091, "SPEAKER_00"), (40.0, 41.0, "SPEAKER_00")]
    audio = wav("interrumpida.wav", segundos=32.5)  # 520 000 cuadros
    r = modulo.diarizar(audio)
    carpeta = audio.parent / "interrumpida"
    datos = json.loads((carpeta / NOMBRE_JSON).read_text(encoding="utf-8"))
    assert datos == {"segments": [{"start": 0.368, "end": 2.309, "speaker": "SPEAKER_00"},
                                  {"start": 26.592, "end": 32.5, "speaker": "SPEAKER_00"}]}
    assert validar_diarizacion(datos, 32.5) == []
    assert validar_par(carpeta / NOMBRE_JSON, carpeta / NOMBRE_META) == []
    meta = json.loads((carpeta / NOMBRE_META).read_text(encoding="utf-8"))
    assert (meta["segmentos"], meta["segmentos_corregidos"], meta["segmentos_descartados"]) == (2, 1, 1)
    assert meta["exceso_fin_max_s"] == pytest.approx(0.0997, abs=1e-4)
    assert meta["tolerancia_fin_s"] == 0.05  # heredado: no impidió conservar un exceso de 0,0997 s
    assert r["meta"]["exceso_fin_max_s"] == meta["exceso_fin_max_s"]


def test_num_speakers_llega_al_pipeline_y_al_meta(entorno, wav):
    entorno.preparar()
    audio = wav("a.wav", segundos=10)
    sin = modulo.diarizar(audio, salida=audio.parent / "sin")
    con = modulo.diarizar(audio, salida=audio.parent / "con", num_speakers=2)
    assert entorno.llamadas[1][1] == {"num_speakers": 2}
    assert con["meta"]["num_speakers"] == 2 and sin["meta"]["num_speakers"] is None
    a = json.loads((audio.parent / "sin" / NOMBRE_JSON).read_text(encoding="utf-8"))
    b = json.loads((audio.parent / "con" / NOMBRE_JSON).read_text(encoding="utf-8"))
    assert set(a) == set(b) == {"segments"}
    assert {k for s in a["segments"] for k in s} == {k for s in b["segments"] for k in s} == {"start", "end", "speaker"}


def test_exito_en_cuda_libera_y_registra_la_gpu(entorno, wav):
    entorno.preparar(cuda=True)
    r = modulo.diarizar(wav("a.wav", segundos=10))
    assert r["dispositivo"] == "cuda" and entorno.dispositivos[0] == "cuda"
    assert r["meta"]["gpu"] == "GPU falsa" and r["meta"]["vram_pico_mib"] == 1536.0
    assert entorno.torch.llamadas["empty_cache"] == 1
    gc.collect()
    assert entorno.refs[0]() is None  # no quedan referencias al pipeline


def _par_previo(entorno, audio):
    modulo.diarizar(audio)
    carpeta = audio.parent / audio.stem
    return carpeta, {n: (carpeta / n).read_bytes() for n in (NOMBRE_JSON, NOMBRE_META)}


def _verificar_fallo(e, carpeta, antes, audio, sha_audio, etapa):
    assert e.etapa == etapa
    assert {n: (carpeta / n).read_bytes() for n in (NOMBRE_JSON, NOMBRE_META)} == antes
    assert _sha(audio) == sha_audio
    error = json.loads((carpeta / NOMBRE_ERROR).read_text(encoding="utf-8"))
    assert error["etapa"] == etapa and error["resultado_anterior_conservado"] is True
    assert error["run_id_anterior"] == json.loads(antes[NOMBRE_META])["run_id"]
    assert e.archivo_error == carpeta / NOMBRE_ERROR
    return error


def test_fallo_al_publicar_conserva_el_par_y_registra_escritura(entorno, wav, monkeypatch):
    """Tarea 4.6: si falla la publicación del meta, diarizar() restaura el par y registra la etapa escritura."""
    from test_resultados import replace_que_falla

    entorno.preparar(cuda=False)
    audio = wav("a.wav", segundos=10)
    carpeta, antes = _par_previo(entorno, audio)
    sha_audio = _sha(audio)
    replace_que_falla(monkeypatch, {2})  # 1: JSON publicado; 2: falla el meta; 3: se restaura el JSON
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(audio)
    error = _verificar_fallo(e.value, carpeta, antes, audio, sha_audio, "escritura")
    assert error["tipo"] == "OSError" and "#2" in error["mensaje"]
    assert validar_par(carpeta / NOMBRE_JSON, carpeta / NOMBRE_META) == []
    assert not list(carpeta.glob("*.tmp")) and not list(carpeta.glob("*.bak"))


def test_runtime_error_en_cpu(entorno, wav):
    entorno.preparar(cuda=False)
    audio = wav("a.wav", segundos=10)
    carpeta, antes = _par_previo(entorno, audio)
    sha_audio = _sha(audio)
    entorno.falla = RuntimeError("fallo interno del modelo")
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(audio)
    error = _verificar_fallo(e.value, carpeta, antes, audio, sha_audio, "ejecucion")
    assert error["tipo"] == "RuntimeError" and "fallo interno" in error["mensaje"]
    assert entorno.torch.llamadas["empty_cache"] == 0
    gc.collect()
    assert all(ref() is None for ref in entorno.refs)


def test_sin_memoria_en_cuda(entorno, wav):
    torch = entorno.preparar(cuda=True).torch
    audio = wav("a.wav", segundos=10)
    carpeta, antes = _par_previo(entorno, audio)
    sha_audio = _sha(audio)
    llamadas_previas = torch.llamadas["empty_cache"]
    entorno.falla = torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB")
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(audio)
    error = _verificar_fallo(e.value, carpeta, antes, audio, sha_audio, "ejecucion")
    assert error["tipo"] == "OutOfMemoryError" and "--device cpu" in error["mensaje"]
    assert torch.llamadas["empty_cache"] == llamadas_previas + 1  # liberada también al fallar
    gc.collect()
    assert all(ref() is None for ref in entorno.refs)
    assert e.value.__context__ is None and e.value.__cause__ is None  # sin la excepción original viva


def test_error_de_ffmpeg(entorno, wav):
    entorno.preparar()
    audio = wav("a.wav", segundos=10)
    carpeta, antes = _par_previo(entorno, audio)
    entorno.falla = RuntimeError("Could not load libtorchcodec. FFmpeg libraries not found")
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(audio)
    error = _verificar_fallo(e.value, carpeta, antes, audio, _sha(audio), "decodificacion")
    assert "FFmpeg" in error["mensaje"] and "README" in error["mensaje"]


def test_error_al_cargar_sin_token(entorno, wav):
    entorno.preparar()
    entorno.falla_carga = OSError("401 Client Error: Unauthorized")
    audio = wav("a.wav", segundos=10)
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(audio)
    assert e.value.etapa == "token" and entorno.tokens == [None]
    assert "huggingface.co/settings/tokens" in e.value.mensaje
    assert not (audio.parent / "a" / NOMBRE_JSON).exists()


def test_el_token_no_aparece_en_ningun_mensaje(entorno, wav):
    entorno.preparar()
    os.environ["HF_TOKEN"] = "hf_secreto_de_prueba"
    entorno.falla_carga = OSError("403 Forbidden para hf_secreto_de_prueba")
    audio = wav("a.wav", segundos=10)
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(audio)
    assert e.value.etapa == "modelo" and entorno.tokens == ["hf_secreto_de_prueba"]
    contenido = (audio.parent / "a" / NOMBRE_ERROR).read_text(encoding="utf-8")
    assert "hf_secreto_de_prueba" not in e.value.mensaje and "hf_secreto_de_prueba" not in contenido
    assert "***" in e.value.mensaje


def test_cuda_pedida_sin_gpu_registra_el_error(entorno, wav):
    entorno.preparar(cuda=False)
    audio = wav("a.wav", segundos=10)
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(audio, device="cuda")
    assert e.value.etapa == "dispositivo" and entorno.creados == 0
    assert not (audio.parent / "a" / NOMBRE_JSON).exists()
    assert json.loads((audio.parent / "a" / NOMBRE_ERROR).read_text(encoding="utf-8"))["etapa"] == "dispositivo"


def test_audio_inexistente_y_parametros_no_crean_archivos(entorno, tmp_path):
    entorno.preparar()
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(tmp_path / "no_existe.wav")
    assert e.value.etapa == "audio" and not (tmp_path / "no_existe").exists()
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(tmp_path / "no_existe.wav", num_speakers=0)
    assert e.value.etapa == "parametros"


def test_formato_invalido_registra_el_error_y_no_toca_el_audio(entorno, wav):
    entorno.preparar()
    audio = wav("48k.wav", hz=48000)
    sha = _sha(audio)
    with pytest.raises(DiarizacionError) as e:
        modulo.diarizar(audio)
    assert e.value.etapa == "audio" and _sha(audio) == sha
    assert (audio.parent / "48k" / NOMBRE_ERROR).is_file() and entorno.creados == 0


def test_exito_despues_de_un_fallo_borra_el_error(entorno, wav):
    entorno.preparar()
    audio = wav("a.wav", segundos=10)
    entorno.falla = RuntimeError("primero falla")
    with pytest.raises(DiarizacionError):
        modulo.diarizar(audio)
    assert (audio.parent / "a" / NOMBRE_ERROR).is_file()
    entorno.falla = None
    modulo.diarizar(audio)
    assert not (audio.parent / "a" / NOMBRE_ERROR).exists()
    assert (audio.parent / "a" / NOMBRE_JSON).is_file()


def test_main_exitoso_muestra_el_resumen(entorno, wav, capsys):
    entorno.preparar()
    audio = wav("a.wav", segundos=10)
    assert modulo.main([str(audio)]) == 0
    salida = capsys.readouterr().out
    assert "2 hablantes" in salida and "SPEAKER_00:" in salida and "SPEAKER_01:" in salida
