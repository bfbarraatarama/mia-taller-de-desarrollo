"""Grupo 6: diálogo de las fichas y reproducción (D8), sin pantalla ni audio.

La spec deja estos escenarios para la lista de chequeo manual (oír el fragmento, usar el mouse). Acá se prueba el
cableado entre los controles y el modelo, con Qt en modo `offscreen` y un reproductor falso que anota las llamadas.
Se saltean si no está PySide6 (entornos 3.12 de las otras etapas).
"""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="falta PySide6 (entorno de la interfaz)")

from asociacion import asociar  # noqa: E402
from conftest import crear_reunion, segmento  # noqa: E402
from etiquetado import Cierre, ModeloFichas  # noqa: E402
from fichas import DialogoFichas, Reproductor, tiempo_legible  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class AudioFalso:
    """Reemplaza soundfile.read, sounddevice.play y sounddevice.stop."""

    def __init__(self):
        self.lecturas, self.reproducidos, self.detenciones = [], [], 0

    def leer(self, ruta, start, stop, dtype):
        self.lecturas.append((start, stop))
        return np.zeros(stop - start, dtype=dtype), 16000

    def play(self, datos, fs):
        self.reproducidos.append((len(datos), fs))

    def stop(self):
        self.detenciones += 1


def dialogo(carpeta, audio=None):
    a = asociar(carpeta)
    audio = audio or AudioFalso()
    r = Reproductor(a.rutas.audio, leer=audio.leer, play=audio.play, stop=audio.stop, fs_salida=lambda fs: fs)
    return DialogoFichas(ModeloFichas(a), r), a, audio


@pytest.fixture
def dos(tmp_path):
    """SPEAKER_00 habla 21 s: tramos solos de 6, 6, 6, 1 y 1 s (media 4 s, mínimo 5 s: 3 candidatos).
    SPEAKER_01 nunca habla solo: su único turno (22 a 23 s) cae dentro de uno de SPEAKER_00."""
    turnos = [(0.0, 6.0, "SPEAKER_00"), (7.0, 13.0, "SPEAKER_00"), (14.0, 20.0, "SPEAKER_00"),
              (21.0, 24.0, "SPEAKER_00"), (22.0, 23.0, "SPEAKER_01")]
    return crear_reunion(tmp_path / "reunion", 25.0, turnos,
                         [segmento(("Hola", 1.0, 2.0), ("a", 2.0, 2.5)), segmento(("todos.", 22.2, 22.8))])


def test_ocho_fichas(app, tmp_path):
    etiquetas = [f"SPEAKER_{k:02d}" for k in range(8)]
    turnos = [(1.0 + 2 * k, 2.5 + 2 * k, e) for k, e in enumerate(etiquetas)]
    carpeta = crear_reunion(tmp_path, 20.0, turnos, [segmento(("hola", 1.2, 1.8))])
    d, _, _ = dialogo(carpeta)
    assert [t.etiqueta for t in d.tarjetas] == [f.etiqueta for f in d.modelo.fichas]
    assert len(d.tarjetas) == 8 and d.area.widgetResizable()
    assert d.isModal()


def test_ficha_muestra_el_modelo(app, dos):
    d, _, _ = dialogo(dos)
    t0, t1 = d.tarjetas
    assert t0.etiqueta == "SPEAKER_00" and "21 s" in t0.title()
    assert t0.contador.text().startswith("fragmento 1 de 3")
    assert t0.aviso.isHidden() and not t1.aviso.isHidden()  # SPEAKER_01 nunca habla solo
    assert t1.texto.text() == "«todos.»"


def test_otro_fragmento_actualiza_la_ficha(app, dos):
    d, _, _ = dialogo(dos)
    t0 = d.tarjetas[0]
    t0.boton_otro.click()
    assert t0.contador.text().startswith("fragmento 2 de 3")
    assert d.modelo.ficha("SPEAKER_00").indice == 1


def test_reproduce_solo_el_fragmento(app, dos):
    d, _, audio = dialogo(dos)
    t0 = d.tarjetas[0]
    f = d.modelo.ficha("SPEAKER_00").fragmento
    t0.boton_reproducir.click()
    assert audio.lecturas == [(round(f.start * 16000), round(f.end * 16000))]
    assert t0.boton_reproducir.text() == "■ Detener"


def test_una_reproduccion_a_la_vez(app, dos):
    d, _, audio = dialogo(dos)
    t0, t1 = d.tarjetas
    t0.boton_reproducir.click()
    t1.boton_reproducir.click()
    assert audio.detenciones >= 1 and len(audio.reproducidos) == 2
    assert t0.boton_reproducir.text() == "▶ Reproducir" and t1.boton_reproducir.text() == "■ Detener"


def test_detener(app, dos):
    d, _, audio = dialogo(dos)
    t0 = d.tarjetas[0]
    t0.boton_reproducir.click()
    t0.boton_reproducir.click()
    assert t0.boton_reproducir.text() == "▶ Reproducir" and d.reproductor.sonando is None


def test_fin_del_fragmento_vuelve_a_reproducir(app, dos):
    d, _, _ = dialogo(dos)
    t0 = d.tarjetas[0]
    t0.boton_reproducir.click()
    d.reproductor.terminar(d.reproductor.turno)  # lo que dispara el temporizador al terminar el fragmento
    assert t0.boton_reproducir.text() == "▶ Reproducir"


def test_otro_fragmento_detiene_la_reproduccion(app, dos):
    d, _, _ = dialogo(dos)
    t0 = d.tarjetas[0]
    t0.boton_reproducir.click()
    t0.boton_otro.click()
    assert d.reproductor.sonando is None and t0.boton_reproducir.text() == "▶ Reproducir"


def test_autocompletado_en_el_dialogo(app, dos):
    d, _, _ = dialogo(dos)
    t0, t1 = d.tarjetas
    t0.nombre.setText("Luisa")
    t0.nombre.textEdited.emit("Luisa")
    assert t1.completer.model().stringList() == ["Luisa"]
    assert t0.completer.model().stringList() == []


def test_confirmar(app, dos):
    d, _, _ = dialogo(dos)
    d.tarjetas[0].nombre.setText("  Luisa ")
    d.tarjetas[0].nombre.textEdited.emit("  Luisa ")
    d.boton_confirmar.click()
    assert d.decision.accion == "escribir" and d.decision.etiquetado.nombres["SPEAKER_00"] == "Luisa"
    assert d.result() == QtWidgets.QDialog.DialogCode.Accepted


def test_confirmar_con_aviso_de_tildes(app, dos):
    d, _, _ = dialogo(dos)
    vistos = []
    d.confirmar_tildes = lambda pares: vistos.append(pares) or False  # el usuario vuelve a las fichas
    for t, n in zip(d.tarjetas, ("Martín", "Martin")):
        t.nombre.setText(n)
        t.nombre.textEdited.emit(n)
    d.boton_confirmar.click()
    assert vistos == [[("Martín", "Martin")]] and d.decision is None
    d.confirmar_tildes = lambda pares: True  # confirma igual
    d.boton_confirmar.click()
    assert d.decision.etiquetado.nombres == {"SPEAKER_00": "Martín", "SPEAKER_01": "Martin"}


@pytest.mark.parametrize("opcion, accion", [(Cierre.SIN_NOMBRES, "escribir"), (Cierre.CANCELAR, "cancelar")])
def test_cerrar_sin_confirmar(app, dos, opcion, accion):
    d, _, audio = dialogo(dos)
    d.preguntar_cierre = lambda: opcion
    d.tarjetas[0].boton_reproducir.click()
    d.reject()  # Esc o la X de la ventana
    assert d.decision.accion == accion and d.result() == QtWidgets.QDialog.DialogCode.Rejected
    assert d.reproductor.sonando is None


def test_volver_a_las_fichas_desde_el_dialogo(app, dos):
    d, _, _ = dialogo(dos)
    d.preguntar_cierre = lambda: Cierre.VOLVER
    d.tarjetas[0].nombre.setText("Luisa")
    d.tarjetas[0].nombre.textEdited.emit("Luisa")
    d.show()
    d.reject()
    assert d.decision is None and d.isVisible() and d.tarjetas[0].nombre.text() == "Luisa"
    d.hide()


def test_remuestreo_si_la_salida_no_acepta_16_khz(app, dos):
    a = asociar(dos)
    audio = AudioFalso()
    r = Reproductor(a.rutas.audio, leer=audio.leer, play=audio.play, stop=audio.stop, fs_salida=lambda fs: 48000)
    r.reproducir("SPEAKER_00", 0.0, 1.0)
    assert audio.reproducidos == [(48000, 48000)]


@pytest.mark.parametrize("segundos, texto", [(18.0, "18 s"), (65.4, "1 min 05 s"), (3600.0, "60 min 00 s")])
def test_tiempo_legible(segundos, texto):
    assert tiempo_legible(segundos) == texto
