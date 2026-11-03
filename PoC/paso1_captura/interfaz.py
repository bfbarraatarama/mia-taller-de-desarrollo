"""Ventana principal de la PoC, con estética Windows Vista.

Paso 1 (grabar micrófono + audio del sistema) se maneja acá; paso 2 (procesar la reunión) vive en
panel_procesamiento.py. Estética en estilo.py y widgets dibujados a mano en widgets.py.

Uso:  python interfaz.py
"""

from __future__ import annotations

import json
import math
import re
import sys
import threading
import time
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import QObject, QSettings, QSize, Qt, QTemporaryDir, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPalette
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox,
                               QFileDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
                               QRadioButton, QScrollArea, QSizePolicy, QSpinBox, QStatusBar, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

import captura as cap
from estilo import _flechas, fuente, hoja_estilo, icono_estado
from panel_procesamiento import PanelProcesamiento
from widgets import BarraTransporte, Encabezado, Medidor, Orbe

# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class Puente(QObject):
    """Señales para volver al hilo de la interfaz desde los hilos de trabajo."""
    detectado = Signal(object)
    iniciado = Signal(object)
    terminado = Signal(object)
    error = Signal(str)


class Ventana(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Captura de reuniones")
        self.setWindowIcon(self._icono_app())
        self.config = QSettings("UdeSA-MIA", "captura-minutas")
        self.puente = Puente()
        self.puente.detectado.connect(self._al_detectar)
        self.puente.iniciado.connect(self._al_iniciar)
        self.puente.terminado.connect(self._al_terminar)
        self.puente.error.connect(self._al_error)
        self.sesion: cap.Sesion | None = None
        self.estado = "listo"
        self.cerrar_al_terminar = False
        self.ultima_carpeta: Path | None = None
        self.t_tick = time.monotonic()
        self.reloj = QTimer(self)
        self.reloj.setInterval(40)
        self.reloj.timeout.connect(self._tick)

        self._armar()
        self._cargar_dispositivos()
        self._cargar_config()
        self._poner_estado("listo")
        pantalla = QApplication.primaryScreen().availableGeometry()
        self.resize(min(960, pantalla.width()), min(1240, pantalla.height() - 90))

    # --- armado -----------------------------------------------------------

    def _icono_app(self) -> QIcon:
        o = Orbe()
        o.resize(74, 74)
        return QIcon(o.grab())

    def _armar(self):
        central = QWidget()
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        raiz.addWidget(Encabezado("Captura de reuniones", "Paso 1 · grabar micrófono + sistema   ·   Paso 2 · transcripción y minuta"))

        cuerpo = QWidget(objectName="cuerpo")
        lay = QVBoxLayout(cuerpo)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(8)
        instr = QLabel("Elegí las fuentes y presioná el botón para grabar.", objectName="instruccion")
        instr.setFont(fuente(12))
        lay.addWidget(instr)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        fila.addWidget(self._grupo_fuentes(), 4)
        fila.addWidget(self._grupo_opciones(), 3)
        lay.addLayout(fila)
        lay.addWidget(self._grupo_niveles())
        lay.addWidget(self._transporte())
        lay.addWidget(self._grupo_resultado())
        self.panel = PanelProcesamiento(lambda: Path(self.ed_salida.text() or Path(__file__).parent / "grabaciones"))
        self.panel.ocupado.connect(lambda _: self._poner_estado(self.estado))
        self.panel.mensaje.connect(self._mostrar_mensaje)
        lay.addWidget(self.panel, 1)
        desplazable = QScrollArea()
        desplazable.setWidget(cuerpo)
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QFrame.Shape.NoFrame)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        raiz.addWidget(desplazable, 1)
        self.setCentralWidget(central)

        barra = QStatusBar()
        self.lbl_estado = QLabel()
        self.lbl_estado.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        barra.addWidget(self.lbl_estado, 1)
        barra.addPermanentWidget(QLabel(f"sounddevice {sd.__version__} · {sd.get_portaudio_version()[1].split(',')[0]}"))
        self.setStatusBar(barra)

    def _grupo_fuentes(self) -> QGroupBox:
        g = QGroupBox("Fuentes de audio")
        lay = QGridLayout(g)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(7)
        self.rb_auto = QRadioButton("Automático (PipeWire)")
        self.rb_manual = QRadioButton("Manual")
        grupo = QButtonGroup(self)
        grupo.addButton(self.rb_auto)
        grupo.addButton(self.rb_manual)
        self.rb_auto.toggled.connect(self._actualizar_modo)
        self.btn_detectar = QPushButton("Detectar")
        self.btn_detectar.clicked.connect(self._detectar)
        modo = QHBoxLayout()
        modo.setSpacing(18)
        modo.addWidget(self.rb_auto)
        modo.addWidget(self.rb_manual)
        modo.addStretch()
        modo.addWidget(self.btn_detectar)
        lay.addLayout(modo, 0, 0, 1, 3)

        self.cb_mic, self.cb_sis = QComboBox(), QComboBox()
        self.ed_can_mic, self.ed_can_sis = QLineEdit(), QLineEdit()
        for i, (nombre, cb, ed) in enumerate([("Micrófono", self.cb_mic, self.ed_can_mic),
                                              ("Sistema", self.cb_sis, self.ed_can_sis)]):
            cb.setMinimumWidth(220)
            cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(18)
            ed.setPlaceholderText("0,1")
            ed.setFixedWidth(76)
            ed.setToolTip("Canales del dispositivo, separados por coma")
            cb.currentTextChanged.connect(cb.setToolTip)
            lay.addWidget(QLabel(f"{nombre}:"), 1 + i, 0)
            lay.addWidget(cb, 1 + i, 1)
            lay.addWidget(ed, 1 + i, 2)
        self.lbl_deteccion = QLabel(objectName="secundario")
        self.lbl_deteccion.setWordWrap(True)
        self.lbl_deteccion.setFont(fuente(8.5))
        lay.addWidget(self.lbl_deteccion, 3, 0, 1, 3)
        lay.setColumnStretch(1, 1)
        return g

    def _grupo_opciones(self) -> QGroupBox:
        g = QGroupBox("Opciones")
        lay = QGridLayout(g)
        lay.setHorizontalSpacing(8)
        lay.setVerticalSpacing(7)
        self.sp_duracion = QSpinBox()
        self.sp_duracion.setRange(0, 6 * 3600)
        self.sp_duracion.setSuffix(" s")
        self.sp_duracion.setSpecialValueText("Sin límite")
        self.sp_duracion.setToolTip("0 = graba hasta presionar detener")
        self.cb_fs = QComboBox()
        for texto, valor in [("Del dispositivo", 0), ("16 000 Hz", 16000), ("44 100 Hz", 44100), ("48 000 Hz", 48000)]:
            self.cb_fs.addItem(texto, valor)
        self.sp_umbral = QDoubleSpinBox()
        self.sp_umbral.setRange(-120, 0)
        self.sp_umbral.setDecimals(0)
        self.sp_umbral.setSuffix(" dBFS")
        self.sp_umbral.setToolTip("RMS mínimo para considerar que una fuente registró señal")
        self.ck_tono = QCheckBox("Tono de prueba (1 kHz)")
        self.ck_tono.setToolTip("Reproduce un tono a 1 s para verificar que se captura el audio del sistema")
        self.ed_salida = QLineEdit()
        self.ed_salida.textChanged.connect(self.ed_salida.setToolTip)
        btn_examinar = QPushButton("Examinar…")
        btn_examinar.clicked.connect(self._examinar)
        self._btn_examinar = btn_examinar

        lay.addWidget(QLabel("Duración:"), 0, 0)
        lay.addWidget(self.sp_duracion, 0, 1)
        lay.addWidget(QLabel("Frecuencia:"), 1, 0)
        lay.addWidget(self.cb_fs, 1, 1)
        lay.addWidget(QLabel("Umbral silencio:"), 2, 0)
        lay.addWidget(self.sp_umbral, 2, 1)
        lay.addWidget(self.ck_tono, 3, 0, 1, 2)
        carpeta = QHBoxLayout()
        carpeta.addWidget(self.ed_salida, 1)
        carpeta.addWidget(btn_examinar)
        lay.addWidget(QLabel("Carpeta:"), 4, 0)
        lay.addLayout(carpeta, 4, 1)
        lay.setColumnStretch(1, 1)
        return g

    def _grupo_niveles(self) -> QGroupBox:
        g = QGroupBox("Niveles")
        lay = QGridLayout(g)
        lay.setVerticalSpacing(8)
        self.medidores, self.lbl_db = {}, {}
        for i, (clave, nombre) in enumerate([("mic", "Micrófono"), ("sistema", "Sistema")]):
            self.medidores[clave] = Medidor()
            self.lbl_db[clave] = QLabel("—")
            self.lbl_db[clave].setFixedWidth(104)
            self.lbl_db[clave].setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.lbl_db[clave].setFont(fuente(9))
            lay.addWidget(QLabel(nombre), i, 0)
            lay.addWidget(self.medidores[clave], i, 1)
            lay.addWidget(self.lbl_db[clave], i, 2)
        escala = QHBoxLayout()
        for texto, alineacion in [("−60 dBFS", Qt.AlignmentFlag.AlignLeft),
                                  ("RMS con caída · la marca oscura es el pico de los últimos 1,5 s",
                                   Qt.AlignmentFlag.AlignHCenter),
                                  ("0 dBFS", Qt.AlignmentFlag.AlignRight)]:
            lbl = QLabel(texto, objectName="secundario")
            lbl.setFont(fuente(8))
            lbl.setAlignment(alineacion)
            escala.addWidget(lbl, 1 if alineacion == Qt.AlignmentFlag.AlignHCenter else 0)
        lay.addLayout(escala, 2, 1)
        lay.setColumnStretch(1, 1)
        return g

    def _transporte(self) -> QWidget:
        barra = BarraTransporte()
        barra.setFixedHeight(100)
        lay = QHBoxLayout(barra)
        lay.setContentsMargins(14, 8, 16, 8)
        lay.setSpacing(16)
        self.orbe = Orbe()
        self.orbe.clicked.connect(self._alternar)
        lay.addWidget(self.orbe)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        self.lbl_tiempo = QLabel("00:00:00")
        self.lbl_tiempo.setFont(fuente(22, QFont.Weight.Light))
        self.lbl_tiempo.setStyleSheet("color: #9fe3ff; background: transparent;")
        self.lbl_transporte = QLabel()
        self.lbl_transporte.setFont(fuente(9))
        self.lbl_transporte.setStyleSheet("color: #c9d3dc; background: transparent;")
        textos.addStretch()
        textos.addWidget(self.lbl_tiempo)
        textos.addWidget(self.lbl_transporte)
        textos.addStretch()
        lay.addLayout(textos, 1)
        self.btn_carpeta = QPushButton("Abrir carpeta")
        self.btn_carpeta.clicked.connect(self._abrir_carpeta)
        lay.addWidget(self.btn_carpeta)
        return barra

    def _grupo_resultado(self) -> QGroupBox:
        g = QGroupBox("Resultado de la última grabación")
        lay = QVBoxLayout(g)
        self.lbl_resumen = QLabel("Todavía no hay grabaciones en esta sesión.", objectName="secundario")
        lay.addWidget(self.lbl_resumen)
        self.lista = QListWidget()
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lista.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.lista.setMinimumHeight(3 * 34 + 4)
        self.lista.setIconSize(QSize(22, 22))
        lay.addWidget(self.lista, 3)
        self.tabla = QTableWidget(0, 8)
        self.tabla.setHorizontalHeaderLabels(["Fuente", "fs (Hz)", "Duración (s)", "Overflows",
                                              "Faltante (s)", "Desfase (s)", "RMS (dBFS)", "Pico (dBFS)"])
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setDefaultSectionSize(34)
        self.tabla.setFixedHeight(38 + 2 * 34 + 4)
        self.tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabla.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(self.tabla)
        return g

    # --- dispositivos y configuración -------------------------------------

    # Los índices de PortAudio cambian cuando aparecen o desaparecen clientes JACK: la selección se
    # recuerda por nombre (rol NOMBRE) y el índice se resuelve al momento de grabar.
    NOMBRE = Qt.ItemDataRole.UserRole + 1

    def _cargar_dispositivos(self, refrescar: bool = False):
        if refrescar:
            sd._terminate()
            sd._initialize()
        hostapis = sd.query_hostapis()
        for cb in (self.cb_mic, self.cb_sis):
            previo = cb.currentData(self.NOMBRE)
            cb.clear()
            for d in sd.query_devices():
                if d["max_input_channels"] > 0:
                    api = hostapis[d["hostapi"]]["name"].replace(" Audio Connection Kit", "")
                    cb.addItem(f"{d['index']} · {d['name']} ({api}) — {d['max_input_channels']} can.", d["index"])
                    cb.setItemData(cb.count() - 1, f"{d['name']} ({api})", self.NOMBRE)
            self._elegir(cb, previo)

    def _elegir(self, cb: QComboBox, nombre: str | None):
        if nombre and (i := cb.findData(nombre, self.NOMBRE)) >= 0:
            cb.setCurrentIndex(i)

    def _cargar_config(self):
        c = self.config
        (self.rb_manual if c.value("modo", "auto") == "manual" else self.rb_auto).setChecked(True)
        self.sp_duracion.setValue(int(c.value("duracion", 0)))
        self.cb_fs.setCurrentIndex(max(0, self.cb_fs.findData(int(c.value("fs", 0)))))
        self.sp_umbral.setValue(float(c.value("umbral", -60.0)))
        self.ck_tono.setChecked(c.value("tono", "false") in (True, "true"))
        self.ed_salida.setText(str(c.value("salida", Path(__file__).parent / "grabaciones")))
        for clave, cb, ed in [("mic", self.cb_mic, self.ed_can_mic), ("sis", self.cb_sis, self.ed_can_sis)]:
            self._elegir(cb, c.value(f"{clave}_disp"))
            ed.setText(str(c.value(f"{clave}_canales", "")))
        self._actualizar_modo()

    def _guardar_config(self):
        c = self.config
        c.setValue("modo", "auto" if self.rb_auto.isChecked() else "manual")
        c.setValue("duracion", self.sp_duracion.value())
        c.setValue("fs", self.cb_fs.currentData())
        c.setValue("umbral", self.sp_umbral.value())
        c.setValue("tono", self.ck_tono.isChecked())
        c.setValue("salida", self.ed_salida.text())
        for clave, cb, ed in [("mic", self.cb_mic, self.ed_can_mic), ("sis", self.cb_sis, self.ed_can_sis)]:
            c.setValue(f"{clave}_disp", cb.currentData(self.NOMBRE))
            c.setValue(f"{clave}_canales", ed.text())

    def _actualizar_modo(self):
        manual = self.rb_manual.isChecked() and self.estado == "listo"
        for w in (self.cb_mic, self.cb_sis, self.ed_can_mic, self.ed_can_sis):
            w.setEnabled(manual)

    def _spec(self, cb: QComboBox, ed: QLineEdit, nombre: str) -> str:
        canales = ed.text().replace(" ", "")
        if canales and not re.fullmatch(r"\d+(,\d+)*", canales):
            raise cap.ErrorCaptura(f"Canales de {nombre} inválidos: {canales!r} (usar, por ejemplo, 0,1)")
        return f"{cb.currentData()}:{canales}" if canales else str(cb.currentData())

    # --- acciones ---------------------------------------------------------

    def _en_hilo(self, fn, senal):
        def correr():
            try:
                senal.emit(fn())
            except cap.ErrorCaptura as e:
                self.puente.error.emit(str(e))
            except Exception as e:  # noqa: BLE001 — se muestra al usuario
                self.puente.error.emit(f"{type(e).__name__}: {e}")
        threading.Thread(target=correr, daemon=True).start()

    def _detectar(self):
        self._cargar_dispositivos(refrescar=True)
        self._poner_estado("detectando")
        self._en_hilo(cap.detectar_pipewire, self.puente.detectado)

    def _al_detectar(self, fuentes):
        self._mostrar_fuentes(fuentes)
        for f, cb, ed in zip(fuentes, (self.cb_mic, self.cb_sis), (self.ed_can_mic, self.ed_can_sis)):
            if (i := cb.findData(f.dispositivo)) >= 0:
                cb.setCurrentIndex(i)
            ed.setText(",".join(map(str, f.canales)))
        self._poner_estado("listo", "Detección completa.")

    def _mostrar_fuentes(self, fuentes):
        lineas = []
        for f in fuentes:
            nombre = "Micrófono" if f.nombre == "mic" else "Sistema"
            puertos = ", ".join(sorted({p.split(":")[0] for p in f.origen.values()})) if f.origen else ""
            lineas.append(f"<b>{nombre}</b>: disp. {f.dispositivo}, can. {','.join(map(str, f.canales))}"
                          + (f" ← {puertos}" if puertos else ""))
        self.lbl_deteccion.setText("<br>".join(lineas))

    def _alternar(self):
        if self.estado == "listo":
            self._iniciar()
        elif self.estado == "grabando":
            self._detener()

    def _iniciar(self):
        try:
            mic = sis = None
            if self.rb_manual.isChecked():
                self._cargar_dispositivos(refrescar=True)
                mic = self._spec(self.cb_mic, self.ed_can_mic, "micrófono")
                sis = self._spec(self.cb_sis, self.ed_can_sis, "sistema")
        except cap.ErrorCaptura as e:
            self._al_error(str(e))
            return
        self._guardar_config()
        salida = self.ed_salida.text() or str(Path(__file__).parent / "grabaciones")
        fs = self.cb_fs.currentData() or None
        tono, umbral = self.ck_tono.isChecked(), self.sp_umbral.value()
        self._reiniciar_medidores()
        self._poner_estado("iniciando")

        def fn():
            fuentes, modo = cap.resolver_fuentes(mic, sis)
            sesion = cap.Sesion(fuentes, modo, salida, fs, tono, umbral)
            sesion.iniciar()
            return sesion

        self._en_hilo(fn, self.puente.iniciado)

    def _reiniciar_medidores(self):
        for clave, m in self.medidores.items():
            m.reiniciar()
            self.lbl_db[clave].setText("—")

    def _al_iniciar(self, sesion):
        self.sesion = sesion
        self._mostrar_fuentes(sesion.fuentes)
        self.t_tick = time.monotonic()
        self.reloj.start()
        self._poner_estado("grabando", f"Escribiendo {sesion.archivo} · " + " | ".join(sesion.descripcion()))
        self.lbl_transporte.setText(f"● Grabando → {sesion.archivo.name}"
                                    + (f" · se detiene a los {self.sp_duracion.value()} s" if self.sp_duracion.value() else ""))

    def _tick(self):
        s = self.sesion
        if s is None:
            return
        ahora = time.monotonic()
        dt, self.t_tick = ahora - self.t_tick, ahora
        s.avanzar()
        t = s.transcurrido()
        self.lbl_tiempo.setText(time.strftime("%H:%M:%S", time.gmtime(t)) + f".{int(t * 10) % 10}")
        for clave, (rms, pico) in s.niveles_vivo().items():
            self.medidores[clave].poner(rms, pico, dt)
            db = 20 * math.log10(max(rms, 1e-6))
            self.lbl_db[clave].setText("−∞ dBFS" if db <= -119 else f"{db:.1f} dBFS".replace("-", "−"))
        if self.sp_duracion.value() and t >= self.sp_duracion.value():
            self._detener()

    def _detener(self):
        if self.estado != "grabando":
            return
        self.reloj.stop()
        for m in self.medidores.values():
            m.activo = False
            m.update()
        self._poner_estado("procesando")
        sesion = self.sesion

        def fn():
            sesion.detener()
            return sesion.procesar()

        self._en_hilo(fn, self.puente.terminado)

    def _al_terminar(self, reporte):
        self.ultima_carpeta = self.sesion.salida
        archivo = self.sesion.archivo
        self.panel.grabacion_terminada(archivo)  # queda lista para «Procesar» (happy path)
        self.sesion = None
        self._reiniciar_medidores()
        self._mostrar_reporte(reporte)
        ok = sum(p["ok"] for p in reporte["pruebas"])
        self._poner_estado("listo", f"Guardado: {archivo} — {ok}/{len(reporte['pruebas'])} pruebas OK")
        if self.cerrar_al_terminar:
            self.close()

    def _al_error(self, mensaje: str):
        self.reloj.stop()
        if self.sesion is not None and self.estado in ("grabando", "procesando"):
            self.ultima_carpeta = self.sesion.salida
        self.sesion = None
        self._poner_estado("listo", "Error: " + mensaje.splitlines()[0])
        caja = QMessageBox(QMessageBox.Icon.Warning, "Captura de reuniones", "No se pudo completar la operación.",
                           QMessageBox.StandardButton.Ok, self)
        caja.setInformativeText(mensaje)
        caja.exec()
        self.cerrar_al_terminar = False

    def _mostrar_reporte(self, rep: dict):
        self.lista.clear()
        for p in rep["pruebas"]:
            texto = p["prueba"][0].upper() + p["prueba"][1:]
            item = QListWidgetItem(icono_estado(p["ok"], 22), texto)
            item.setToolTip(json.dumps(p["detalle"], indent=2, ensure_ascii=False))
            self.lista.addItem(item)
        self.tabla.setRowCount(len(rep["fuentes"]))
        for fila, (nombre, v) in enumerate(rep["fuentes"].items()):
            valores = ["Micrófono" if nombre == "mic" else "Sistema", v["fs_original_hz"], f"{v['duracion_muestras_s']:.2f}",
                       v["overflows"], f"{v['faltante_s']:.3f}", f"{v['desfase_inicio_s']:.4f}",
                       f"{v['rms_dbfs']:.1f}", f"{v['pico_dbfs']:.1f}"]
            for col, val in enumerate(valores):
                it = QTableWidgetItem(str(val).replace("-inf", "−∞"))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setToolTip(v["dispositivo"])
                self.tabla.setItem(fila, col, it)
        ok = sum(p["ok"] for p in rep["pruebas"])
        self.lbl_resumen.setText(f"<b>{rep['archivo']}</b> · {rep['duracion_total_s']:.1f} s · "
                                 f"{ok}/{len(rep['pruebas'])} pruebas OK · modo {rep['modo']} · "
                                 f"pasá el mouse sobre una prueba para ver el detalle")

    def _examinar(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de grabaciones", self.ed_salida.text())
        if d:
            self.ed_salida.setText(d)

    def _abrir_carpeta(self):
        destino = self.ultima_carpeta or Path(self.ed_salida.text())
        destino.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(destino)))

    # --- estado -----------------------------------------------------------

    def _mostrar_mensaje(self, mensaje: str):
        self.lbl_estado.setText(mensaje)
        self.lbl_estado.setToolTip(mensaje)

    def _poner_estado(self, estado: str, mensaje: str | None = None):
        self.estado = estado if estado != "detectando" else "listo"
        ocupado = estado in ("iniciando", "procesando", "detectando")
        quieto = estado == "listo"
        for w in (self.rb_auto, self.rb_manual, self.sp_duracion, self.cb_fs, self.sp_umbral, self.ck_tono,
                  self.ed_salida, self._btn_examinar):
            w.setEnabled(quieto)
        self.btn_detectar.setEnabled(quieto and estado != "detectando")
        # Una reunión a la vez (3.1.5): no se graba mientras se procesa.
        self.orbe.setEnabled(estado == "grabando" or (estado == "listo" and not self.panel.procesando))
        self.orbe.grabando = estado == "grabando"
        self.orbe.setToolTip("Detener" if estado == "grabando" else "Grabar")
        self.orbe.update()
        self.btn_carpeta.setEnabled(not ocupado)
        self._actualizar_modo()
        self.panel.permitir(estado == "listo")
        textos = {
            "listo": "Listo para grabar",
            "detectando": "Detectando fuentes…",
            "iniciando": "Abriendo dispositivos…",
            "grabando": "● Grabando" + (f" · se detiene a los {self.sp_duracion.value()} s" if self.sp_duracion.value() else ""),
            "procesando": "Procesando: remuestreo, mezcla y pruebas…",
        }
        self.lbl_transporte.setText(textos[estado])
        self.lbl_estado.setText(mensaje or textos[estado])
        self.lbl_estado.setToolTip(mensaje or textos[estado])
        if estado == "detectando":
            self.btn_detectar.setEnabled(False)
            self.orbe.setEnabled(False)

    def closeEvent(self, e):
        if self.estado == "grabando":
            r = QMessageBox.question(self, "Captura de reuniones",
                                     "Hay una grabación en curso. ¿Detenerla, guardarla y salir?")
            if r == QMessageBox.StandardButton.Yes:
                self.cerrar_al_terminar = True
                self._detener()
            e.ignore()
            return
        if self.estado in ("iniciando", "procesando"):
            self.cerrar_al_terminar = self.estado == "procesando"
            e.ignore()
            return
        if not self.panel.confirmar_cierre():
            e.ignore()
            return
        self._guardar_config()
        e.accept()


def crear_app() -> tuple[QApplication, QTemporaryDir]:
    app = QApplication(sys.argv)
    app.setApplicationName("Captura de reuniones")
    app.setDesktopFileName("captura-reuniones")
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#3399ff"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    app.setPalette(pal)
    app.setFont(fuente(9.5))
    tmp = QTemporaryDir()
    app.setStyleSheet(hoja_estilo(_flechas(Path(tmp.path()))))
    return app, tmp


def main():
    app, _tmp = crear_app()
    v = Ventana()
    v.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
