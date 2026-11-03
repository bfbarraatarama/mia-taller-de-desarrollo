"""Panel «Procesar reunión» (paso 2 dentro de la interfaz).

Arma la lista ordenada de archivos, lanza `paso2_procesamiento/procesar.py --jsonl` en otro proceso
(con su propio Python: PyTorch, pyannote y Whisper no se cargan en la interfaz) y muestra el avance
de cada etapa a partir de los eventos JSON que ese proceso escribe en stdout.

La ventana principal se comunica con el panel así:
  panel.grabacion_terminada(ruta)  → agrega la grabación recién guardada si la lista está vacía
  panel.permitir(bool)             → habilita o no el botón Procesar (no se procesa mientras se graba)
  panel.procesando                 → True mientras corre el proceso (la ventana no deja grabar)
  panel.confirmar_cierre()         → pregunta si cancelar un procesamiento en curso antes de salir
  señales ocupado(bool) y mensaje(str)
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QProcess, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
                               QVBoxLayout)

from estilo import fuente, icono_estado, icono_pendiente

DIR_PROCESAMIENTO = Path(__file__).resolve().parent.parent / "paso2_procesamiento"
PYTHON_PROCESAMIENTO = DIR_PROCESAMIENTO / ".venv" / "bin" / "python"
ETAPAS = [("preparar", "Preparación del audio"), ("diarizar", "Diarización (pyannote)"),
          ("transcribir", "Transcripción (Whisper)"), ("asociar", "Asociación temporal"),
          ("minuta", "Minuta (Qwen2.5)")]
EXTENSIONES_AUDIO = "Audio (*.wav *.flac *.mp3 *.m4a *.ogg *.opus *.webm *.mp4);;Todos (*)"
PATRON_GRABACION = "????_??_??_??_??_??.wav"


def mmss(segundos: float) -> str:
    return time.strftime("%M:%S", time.gmtime(segundos))


class PanelProcesamiento(QGroupBox):
    ocupado = Signal(bool)
    mensaje = Signal(str)

    def __init__(self, carpeta_grabaciones: Callable[[], Path]):
        super().__init__("Procesar reunión")
        self.carpeta_grabaciones = carpeta_grabaciones
        self.proc: QProcess | None = None
        self.buffer = b""
        self.errores = ""
        self.estado: dict = {}
        self.resultados: Path | None = None
        self.ultima_grabacion: Path | None = None
        self.puede_procesar = True
        self.t0 = 0.0
        self.reloj = QTimer(self)
        self.reloj.setInterval(500)
        self.reloj.timeout.connect(self._tick)
        self._armar()
        self._reiniciar_etapas()
        self._actualizar()

    @property
    def procesando(self) -> bool:
        return self.proc is not None

    # --- armado -------------------------------------------------------------

    def _armar(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lbl = QLabel("Archivos de la reunión en orden; varios se procesan como una sola reunión "
                     "(arrastrá para reordenar).", objectName="secundario")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        lay.addLayout(self._armar_archivos())
        lay.addLayout(self._armar_etapas())
        lay.addLayout(self._armar_acciones())

    def _armar_archivos(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        self.lista = QListWidget()
        self.lista.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lista.setMinimumHeight(4 * 30 + 6)
        self.lista.model().rowsMoved.connect(self._numerar)
        fila.addWidget(self.lista, 1)
        botones = QVBoxLayout()
        botones.setSpacing(5)
        self.botones_archivos = []
        for texto, fn in [("Agregar…", self._agregar), ("Última grabación", self._agregar_ultima),
                          ("Subir", lambda: self._mover(-1)), ("Bajar", lambda: self._mover(1)),
                          ("Quitar", self._quitar)]:
            b = QPushButton(texto)
            b.clicked.connect(fn)
            botones.addWidget(b)
            self.botones_archivos.append(b)
        botones.addStretch()
        fila.addLayout(botones)
        return fila

    def _armar_etapas(self) -> QGridLayout:
        grilla = QGridLayout()
        grilla.setHorizontalSpacing(10)
        grilla.setVerticalSpacing(6)
        self.filas = {}
        for i, (clave, nombre) in enumerate(ETAPAS):
            ico = QLabel()
            barra = QProgressBar()
            barra.setRange(0, 1000)
            barra.setTextVisible(False)
            barra.setFixedHeight(15)
            det = QLabel(objectName="secundario")
            det.setFont(fuente(8.5))
            det.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            grilla.addWidget(ico, i, 0)
            grilla.addWidget(QLabel(nombre), i, 1)
            grilla.addWidget(barra, i, 2)
            grilla.addWidget(det, i, 3)
            self.filas[clave] = (ico, barra, det)
        grilla.setColumnStretch(2, 2)
        grilla.setColumnStretch(3, 3)
        return grilla

    def _armar_acciones(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        self.lbl = QLabel("Elegí los archivos y presioná Procesar.", objectName="secundario")
        self.lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.btn_minuta = QPushButton("Ver minuta")
        self.btn_minuta.clicked.connect(lambda: self._abrir("minuta.md"))
        self.btn_transcripcion = QPushButton("Ver transcripción")
        self.btn_transcripcion.clicked.connect(lambda: self._abrir("transcripcion.md"))
        self.btn_carpeta = QPushButton("Abrir resultados")
        self.btn_carpeta.clicked.connect(lambda: self._abrir(None))
        self.btn_procesar = QPushButton("Procesar")
        self.btn_procesar.clicked.connect(self._alternar)
        fila.addWidget(self.lbl, 1)
        for b in (self.btn_minuta, self.btn_transcripcion, self.btn_carpeta, self.btn_procesar):
            fila.addWidget(b)
        return fila

    # --- interfaz con la ventana principal ----------------------------------

    def grabacion_terminada(self, ruta: Path):
        self.ultima_grabacion = ruta
        if self.lista.count() == 0 and not self.procesando:
            self._poner_archivos([str(ruta)])

    def permitir(self, si: bool):
        self.puede_procesar = si
        self._actualizar()

    def confirmar_cierre(self) -> bool:
        if not self.procesando:
            return True
        r = QMessageBox.question(self, "Procesar reunión", "Hay un procesamiento en curso. ¿Cancelarlo y salir? "
                                 "Los resultados de las etapas terminadas quedan guardados.")
        if r != QMessageBox.StandardButton.Yes:
            return False
        self._cancelar()
        self.proc and self.proc.waitForFinished(3000)
        return True

    # --- lista de archivos ----------------------------------------------------

    def archivos(self) -> list[str]:
        return [self.lista.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.lista.count())]

    def _poner_archivos(self, rutas: list[str]):
        self.lista.clear()
        for r in rutas:
            it = QListWidgetItem()
            it.setData(Qt.ItemDataRole.UserRole, r)
            it.setToolTip(r)
            self.lista.addItem(it)
        self._numerar()

    def _numerar(self, *_):
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            it.setText(f"{i + 1}. {Path(it.data(Qt.ItemDataRole.UserRole)).name}")

    def _agregar(self):
        rutas, _ = QFileDialog.getOpenFileNames(self, "Archivos de la reunión", str(self.carpeta_grabaciones()),
                                                EXTENSIONES_AUDIO)
        if rutas:
            self._poner_archivos(self.archivos() + sorted(rutas))

    def _agregar_ultima(self):
        ultima = self.ultima_grabacion
        if ultima is None:
            grabaciones = sorted(self.carpeta_grabaciones().glob(PATRON_GRABACION))
            ultima = grabaciones[-1] if grabaciones else None
        if ultima is None:
            self.lbl.setText("No hay grabaciones en la carpeta elegida.")
        elif str(ultima) not in self.archivos():
            self._poner_archivos(self.archivos() + [str(ultima)])

    def _mover(self, delta: int):
        i, rutas = self.lista.currentRow(), self.archivos()
        if 0 <= i < len(rutas) and 0 <= i + delta < len(rutas):
            rutas[i], rutas[i + delta] = rutas[i + delta], rutas[i]
            self._poner_archivos(rutas)
            self.lista.setCurrentRow(i + delta)

    def _quitar(self):
        i, rutas = self.lista.currentRow(), self.archivos()
        if 0 <= i < len(rutas):
            del rutas[i]
            self._poner_archivos(rutas)

    # --- filas de etapas -----------------------------------------------------

    def _reiniciar_etapas(self):
        for ico, barra, det in self.filas.values():
            ico.setPixmap(icono_pendiente(18).pixmap(18, 18))
            barra.setRange(0, 1000)
            barra.setValue(0)
            det.setText("")
            det.setToolTip("")

    def _poner_etapa(self, clave: str, estado: str, detalle: str | None = None, fraccion: float | None = None):
        ico, barra, det = self.filas[clave]
        if estado == "en curso":
            ico.setPixmap(icono_estado(None, 18).pixmap(18, 18))
            if fraccion is None:
                barra.setRange(0, 0)  # sin avance medible: barra animada
            else:
                barra.setRange(0, 1000)
                barra.setValue(int(fraccion * 1000))
        elif estado in ("ok", "error"):
            ico.setPixmap(icono_estado(estado == "ok", 18).pixmap(18, 18))
            barra.setRange(0, 1000)
            if estado == "ok":
                barra.setValue(1000)
        if detalle is not None:
            det.setText(detalle)
            det.setToolTip(detalle)

    # --- proceso externo ------------------------------------------------------

    def _alternar(self):
        if self.procesando:
            r = QMessageBox.question(self, "Procesar reunión", "¿Cancelar el procesamiento en curso? "
                                     "Los resultados de las etapas terminadas quedan guardados.")
            if r == QMessageBox.StandardButton.Yes:
                self._cancelar()
            return
        if not self.archivos():
            self._agregar_ultima()
        archivos = self.archivos()
        if not archivos:
            return
        if not PYTHON_PROCESAMIENTO.exists():
            self._mostrar_error(f"Falta el entorno de procesamiento ({PYTHON_PROCESAMIENTO}).",
                                "Instalarlo con las instrucciones del paso 2 (PoC/paso2_procesamiento).")
            return
        self._iniciar(archivos)

    def _iniciar(self, archivos: list[str]):
        self._reiniciar_etapas()
        self.buffer, self.errores, self.estado, self.resultados = b"", "", {}, None
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(str(DIR_PROCESAMIENTO))
        self.proc.readyReadStandardOutput.connect(self._leer_eventos)
        self.proc.readyReadStandardError.connect(self._leer_errores)
        self.proc.finished.connect(self._terminado)
        self.t0 = time.monotonic()
        # --t-pedido: la latencia de 2.3 se mide desde que se pide procesar, no desde que arranca Python.
        self.proc.start(str(PYTHON_PROCESAMIENTO),
                        ["-u", "procesar.py", "--jsonl", "--t-pedido", f"{time.time():.3f}", *archivos])
        self.reloj.start()
        self._tick()
        self._actualizar()
        self.ocupado.emit(True)
        self.mensaje.emit(f"Procesando {len(archivos)} archivo(s)…")

    def _cancelar(self):
        if self.proc is not None:
            self.estado["cancelado"] = True
            self.proc.kill()

    def _tick(self):
        if self.procesando:
            nombre = dict(ETAPAS).get(self.estado.get("etapa_actual"), "Iniciando")
            self.lbl.setText(f"Procesando · {mmss(time.monotonic() - self.t0)} · {nombre}")

    def _leer_errores(self):
        if self.proc is not None:
            self.errores = (self.errores + bytes(self.proc.readAllStandardError()).decode(errors="replace"))[-8000:]

    def _leer_eventos(self):
        if self.proc is None:
            return
        self.buffer += bytes(self.proc.readAllStandardOutput())
        *lineas, self.buffer = self.buffer.split(b"\n")
        for linea in lineas:
            try:
                self._evento(json.loads(linea))
            except json.JSONDecodeError:
                continue
        self._actualizar()

    def _evento(self, ev: dict):
        """Eventos que emite procesar.py --jsonl: inicio, etapa, avance y fin."""
        tipo = ev.get("evento")
        if tipo == "inicio":
            self.resultados = Path(ev["carpeta"])
        elif tipo == "etapa":
            if ev["estado"] == "en curso":
                self.estado["etapa_actual"] = ev["etapa"]
            if ev["estado"] == "error":
                self.estado["error"] = ev.get("detalle")
            detalle = ev.get("detalle") or ""
            if "segundos" in ev:
                detalle = f"{ev['segundos']:.1f} s" + (f" · {detalle}" if detalle else "")
            self._poner_etapa(ev["etapa"], ev["estado"], detalle)
        elif tipo == "avance":
            texto = f"{ev.get('paso', '')} · {ev['fraccion']:.0%}".strip(" ·")
            self._poner_etapa(ev["etapa"], "en curso", texto, ev["fraccion"])
        elif tipo == "fin":
            self.estado["fin"] = ev

    def _terminado(self, codigo: int, _estado):
        self._leer_eventos()
        self._leer_errores()
        self.reloj.stop()
        self.proc = None
        fin = self.estado.get("fin") or {}
        if fin.get("estado") == "completa":
            lat = mmss(fin.get("latencia_s") or 0)
            self.lbl.setText(f"Minuta lista en {lat} desde el pedido.")
            self.mensaje.emit(f"Minuta lista en {lat} → {self.resultados}")
        elif self.estado.get("cancelado"):
            self.lbl.setText("Procesamiento cancelado; quedan los resultados de las etapas terminadas.")
            self.mensaje.emit("Procesamiento cancelado.")
        else:
            error = self.estado.get("error") or f"El proceso terminó con código {codigo}."
            self.lbl.setText("Error: " + error.splitlines()[0])
            self.mensaje.emit("Error en el procesamiento: " + error.splitlines()[0])
            self._mostrar_error("El procesamiento no terminó. El audio y los resultados de las etapas "
                                "terminadas quedan guardados.", error, self.errores[-4000:])
        self._actualizar()
        self.ocupado.emit(False)

    # --- resultados y estado de los botones ---------------------------------

    def _abrir(self, nombre: str | None):
        if self.resultados is not None:
            destino = self.resultados / nombre if nombre else self.resultados
            if destino.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(destino)))

    def _mostrar_error(self, texto: str, informativo: str, detalle: str = ""):
        caja = QMessageBox(QMessageBox.Icon.Warning, "Procesar reunión", texto, QMessageBox.StandardButton.Ok, self)
        caja.setInformativeText(informativo)
        if detalle:
            caja.setDetailedText(detalle)
        caja.exec()

    def _actualizar(self):
        procesando = self.procesando
        self.btn_procesar.setText("Cancelar" if procesando else "Procesar")
        self.btn_procesar.setEnabled(procesando or self.puede_procesar)
        for b in self.botones_archivos:
            b.setEnabled(not procesando)
        self.lista.setEnabled(not procesando)
        r = self.resultados
        self.btn_carpeta.setEnabled(r is not None and r.exists())
        self.btn_minuta.setEnabled(r is not None and (r / "minuta.md").exists())
        self.btn_transcripcion.setEnabled(r is not None and (r / "transcripcion.md").exists())
