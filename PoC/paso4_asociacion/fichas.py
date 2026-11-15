"""Diálogo de las fichas del etiquetado (D8): muestra el modelo de `etiquetado.py` y reproduce los fragmentos.

- `QDialog` modal con `QScrollArea`: una ficha por etiqueta, sea cual sea su cantidad. Mientras está abierto, la
  ventana principal no responde (no se puede grabar ni procesar).
- Reproducción con sounddevice: se lee del WAV solo el fragmento (`soundfile.read(start=, stop=)`); suena uno a la
  vez y el botón alterna entre reproducir y detener. Si la salida no acepta 16 kHz, se remuestrea.
- Cerrar sin confirmar (Esc o la X) pregunta: «Volver a las fichas» (por defecto), «Seguir sin nombres» o
  «Cancelar».

Uso manual (lista de chequeo, tarea 10.1), desde PoC/paso4_asociacion/:
    python fichas.py CARPETA_DE_LA_REUNION
Código de salida: 0 si escribió, 1 si falló, 2 si se canceló sin escribir nada.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QStringListModel, Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QCompleter, QDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from asociacion import asociar
from contrato import FS
from errores import AsociacionError
from etiquetado import Cierre, Decision, ModeloFichas, aplicar
from salida import registrar_error

MARGEN_FIN_MS = 200  # espera extra antes de dar por terminado un fragmento


def tiempo_legible(segundos: float) -> str:
    m, s = divmod(round(segundos), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


def mmss(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    return f"{m}:{s:02d}"


# ---------- reproducción ----------


def _leer(ruta, start, stop, dtype):
    import soundfile
    return soundfile.read(str(ruta), start=start, stop=stop, dtype=dtype)


def _play(datos, fs):
    import sounddevice
    sounddevice.play(datos, fs)


def _stop():
    import sounddevice
    sounddevice.stop()


def _fs_salida(fs: int) -> int:
    """`fs` si la salida predeterminada la acepta; si no, la frecuencia predeterminada del dispositivo."""
    import sounddevice
    try:
        sounddevice.check_output_settings(samplerate=fs, channels=1, dtype="float32")
        return fs
    except Exception:
        return int(sounddevice.query_devices(kind="output")["default_samplerate"])


class Reproductor(QObject):
    """Un solo fragmento sonando a la vez. `cambio` emite la clave que suena, o None al detenerse o terminar."""

    cambio = Signal(object)

    def __init__(self, audio: str | Path, *, leer=_leer, play=_play, stop=_stop, fs_salida=_fs_salida,
                 parent: QObject | None = None):
        super().__init__(parent)
        self.audio = Path(audio)
        self._leer, self._play, self._stop, self._fs_salida = leer, play, stop, fs_salida
        self.sonando: str | None = None
        self.turno = 0  # invalida el temporizador de una reproducción anterior

    def reproducir(self, clave: str, start: float, end: float) -> None:
        self.detener()
        datos, fs = self._leer(self.audio, start=round(start * FS), stop=round(end * FS), dtype="float32")
        salida = self._fs_salida(fs)
        if salida != fs:
            from scipy.signal import resample_poly
            g = math.gcd(salida, fs)
            datos = resample_poly(datos, salida // g, fs // g).astype("float32")
        self._play(datos, salida)
        self.sonando = clave
        self.turno += 1
        turno = self.turno
        QTimer.singleShot(round(len(datos) / salida * 1000) + MARGEN_FIN_MS, self, lambda: self.terminar(turno))
        self.cambio.emit(clave)

    def alternar(self, clave: str, start: float, end: float) -> None:
        if self.sonando == clave:
            self.detener()
        else:
            self.reproducir(clave, start, end)

    def detener(self) -> None:
        if self.sonando is None:
            return
        self._stop()
        self.sonando = None
        self.turno += 1
        self.cambio.emit(None)

    def terminar(self, turno: int) -> None:
        """El fragmento `turno` terminó de sonar (si no se detuvo o reemplazó antes)."""
        if turno == self.turno and self.sonando is not None:
            self.sonando = None
            self.cambio.emit(None)


# ---------- ficha ----------


class TarjetaFicha(QGroupBox):
    def __init__(self, ficha, parent: QWidget | None = None):
        super().__init__(f"{ficha.etiqueta} · {tiempo_legible(ficha.tiempo_habla_s)} de habla", parent)
        self.ficha = ficha
        self.etiqueta = ficha.etiqueta

        self.boton_reproducir = QPushButton("▶ Reproducir")
        self.boton_reproducir.setMinimumWidth(self.boton_reproducir.sizeHint().width())  # no salta al alternar
        self.boton_otro = QPushButton("Otro fragmento")
        if len(ficha.fragmentos.secuencia) == 1:
            self.boton_otro.setEnabled(False)
            self.boton_otro.setToolTip("No hay otro fragmento candidato para este hablante")
        self.contador = QLabel()
        self.contador.setObjectName("secundario")
        fila = QHBoxLayout()
        fila.addWidget(self.boton_reproducir)
        fila.addWidget(self.boton_otro)
        fila.addWidget(self.contador)
        fila.addStretch()

        self.aviso = QLabel("⚠ En este fragmento se oye otra voz: este hablante nunca habla solo.")
        self.aviso.setStyleSheet("color: #9c5700;")
        self.texto = QLabel()
        self.texto.setWordWrap(True)
        self.texto.setObjectName("secundario")
        self.texto.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Nombre (opcional)")
        self.sugeridos = QStringListModel(self)  # con padre: si no, Python lo libera y el completer queda vacío
        self.completer = QCompleter(self.sugeridos, self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.nombre.setCompleter(self.completer)
        fila_nombre = QHBoxLayout()
        fila_nombre.addWidget(QLabel("Nombre:"))
        fila_nombre.addWidget(self.nombre, 1)

        caja = QVBoxLayout(self)
        caja.addLayout(fila)
        caja.addWidget(self.aviso)
        caja.addWidget(self.texto)
        caja.addLayout(fila_nombre)
        self.actualizar()

    def actualizar(self) -> None:
        f = self.ficha.fragmento
        self.contador.setText(f"{self.ficha.contador} · {mmss(f.start)} a {mmss(f.end)}")
        self.aviso.setVisible(self.ficha.aviso_superposicion)
        self.texto.setText(f"«{f.texto}»" if f.texto else "(sin texto transcrito en este fragmento)")

    def mostrar_sonando(self, sonando: bool) -> None:
        self.boton_reproducir.setText("■ Detener" if sonando else "▶ Reproducir")


# ---------- diálogo ----------


class DialogoFichas(QDialog):
    """Al cerrarse, `decision` tiene la `Decision` del modelo (escribir con o sin nombres, o cancelar)."""

    def __init__(self, modelo: ModeloFichas, reproductor: Reproductor, parent: QWidget | None = None):
        super().__init__(parent)
        self.modelo = modelo
        self.reproductor = reproductor
        self.decision: Decision | None = None
        # Preguntas al usuario; las pruebas las reemplazan
        self.preguntar_cierre = self._preguntar_cierre
        self.confirmar_tildes = self._confirmar_tildes

        self.setWindowTitle("Nombrar a los hablantes")
        self.setModal(True)
        self.resize(640, 560)

        instruccion = QLabel("Escuchá un fragmento de cada hablante y escribí su nombre. Podés dejarlo vacío.")
        instruccion.setObjectName("instruccion")
        instruccion.setWordWrap(True)

        contenedor = QWidget()
        lista = QVBoxLayout(contenedor)
        self.tarjetas = [TarjetaFicha(f) for f in modelo.fichas]
        for t in self.tarjetas:
            lista.addWidget(t)
            t.boton_reproducir.clicked.connect(lambda _=False, t=t: self._alternar(t))
            t.boton_otro.clicked.connect(lambda _=False, t=t: self._otro(t))
            t.nombre.textChanged.connect(lambda texto, t=t: self._nombre(t, texto))
        lista.addStretch()
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setWidget(contenedor)

        self.boton_confirmar = QPushButton("Confirmar")
        self.boton_confirmar.setAutoDefault(False)  # Enter en un nombre no confirma todo el diálogo
        self.boton_confirmar.clicked.connect(self._confirmar)
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(self.boton_confirmar)

        caja = QVBoxLayout(self)
        caja.addWidget(instruccion)
        caja.addWidget(self.area, 1)
        caja.addLayout(botones)

        reproductor.cambio.connect(self._sonando)

    # --- acciones ---

    def _alternar(self, t: TarjetaFicha) -> None:
        f = t.ficha.fragmento
        try:
            self.reproductor.alternar(t.etiqueta, f.start, f.end)
        except Exception as e:  # dispositivo de audio ocupado o ausente, WAV ilegible
            QMessageBox.warning(self, "Nombrar a los hablantes", f"No se pudo reproducir el fragmento:\n{e}")

    def _otro(self, t: TarjetaFicha) -> None:
        if self.reproductor.sonando == t.etiqueta:
            self.reproductor.detener()
        self.modelo.otro_fragmento(t.etiqueta)
        t.actualizar()

    def _nombre(self, t: TarjetaFicha, texto: str) -> None:
        self.modelo.escribir_nombre(t.etiqueta, texto)
        for otra in self.tarjetas:
            otra.completer.model().setStringList(self.modelo.sugerencias(otra.etiqueta))

    def _sonando(self, clave) -> None:
        for t in self.tarjetas:
            t.mostrar_sonando(t.etiqueta == clave)

    def _confirmar(self) -> None:
        pares = self.modelo.avisos_tildes()
        if pares and not self.confirmar_tildes(pares):
            return
        self.reproductor.detener()
        self.decision = self.modelo.confirmar()
        self.accept()

    def reject(self) -> None:
        """Esc o la X de la ventana: pregunta antes de cerrar."""
        opcion = self.preguntar_cierre()
        if opcion is Cierre.VOLVER:
            return
        self.reproductor.detener()
        self.decision = self.modelo.cerrar_sin_confirmar(opcion)
        super().reject()

    # --- preguntas ---

    def _preguntar_cierre(self) -> Cierre:
        caja = QMessageBox(QMessageBox.Icon.Question, "Nombrar a los hablantes",
                           "Todavía no confirmaste los nombres.", parent=self)
        caja.setInformativeText("«Seguir sin nombres»: la minuta usa las etiquetas (SPEAKER_00, …).\n"
                                "«Cancelar»: se detiene el procesamiento; lo ya transcrito se conserva.")
        volver = caja.addButton(Cierre.VOLVER.value, QMessageBox.ButtonRole.AcceptRole)
        sin_nombres = caja.addButton(Cierre.SIN_NOMBRES.value, QMessageBox.ButtonRole.DestructiveRole)
        caja.addButton(Cierre.CANCELAR.value, QMessageBox.ButtonRole.RejectRole)
        caja.setDefaultButton(volver)
        caja.setEscapeButton(volver)
        caja.exec()
        if caja.clickedButton() is volver:
            return Cierre.VOLVER
        return Cierre.SIN_NOMBRES if caja.clickedButton() is sin_nombres else Cierre.CANCELAR

    def _confirmar_tildes(self, pares: list[tuple[str, str]]) -> bool:
        lista = "\n".join(f"• {a} / {b}" for a, b in pares)
        caja = QMessageBox(QMessageBox.Icon.Warning, "Nombrar a los hablantes",
                           "Estos nombres difieren solo en tildes y van a quedar como personas distintas:",
                           parent=self)
        caja.setInformativeText(lista)
        volver = caja.addButton(Cierre.VOLVER.value, QMessageBox.ButtonRole.RejectRole)
        caja.addButton("Confirmar igual", QMessageBox.ButtonRole.AcceptRole)
        caja.setDefaultButton(volver)
        caja.setEscapeButton(volver)
        caja.exec()
        return caja.clickedButton() is not volver


def etiquetar(asociacion, parent: QWidget | None = None) -> Decision:
    """Muestra las fichas y devuelve la decisión. Sin etiquetas (diarización vacía), saltea el etiquetado."""
    modelo = ModeloFichas(asociacion)
    if not modelo.hay_fichas:
        return Decision("escribir")
    dialogo = DialogoFichas(modelo, Reproductor(asociacion.rutas.audio), parent)
    dialogo.exec()
    return dialogo.decision or Decision("cancelar")


def _crear_app() -> QApplication:
    """Para el uso manual: con la estética del paso 1 si está disponible."""
    app = QApplication.instance() or QApplication(sys.argv)
    paso1 = Path(__file__).resolve().parents[1] / "paso1_captura"
    if (paso1 / "estilo.py").is_file():
        sys.path.insert(0, str(paso1))
        from PySide6.QtCore import QTemporaryDir
        from estilo import _flechas, fuente, hoja_estilo
        app.setStyle("Fusion")
        app.setFont(fuente(9.5))
        app._tmp = QTemporaryDir()  # las flechas de la hoja de estilo viven ahí
        app.setStyleSheet(hoja_estilo(_flechas(Path(app._tmp.path()))))
    return app


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Uso: python fichas.py CARPETA_DE_LA_REUNION", file=sys.stderr)
        return 1
    carpeta = Path(argv[0])
    _crear_app()
    try:
        a = asociar(carpeta)
        ruta = aplicar(a, etiquetar(a))
    except AsociacionError as e:
        registrar_error(carpeta, e)
        print(f"Etapa 4 · {e.paso}: {e.mensaje}", file=sys.stderr)
        return 1
    if ruta is None:
        print("Etapa 4 · etiquetado cancelado: no se escribió nada")
        return 2
    print(f"Etapa 4 · {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
