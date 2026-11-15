"""Panel «Procesar reunión» (paso 2 dentro de la interfaz).

Arma la lista ordenada de archivos y lanza `python -m src.pipeline` en un proceso
(del mismo entorno virtual, pero sin cargar PyTorch, pyannote ni Whisper en Qt). Muestra el avance
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
from dataclasses import asdict, replace
from typing import Callable
import sys

from PySide6.QtCore import QProcess, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
                               QVBoxLayout, QComboBox, QCheckBox, QLineEdit, QPlainTextEdit, QDialog, QSpinBox)

from .estilo import fuente, icono_estado, icono_pendiente

from ..minutas.contratos import SECCIONES_MINUTA
from ..minutas.generacion import ConfiguracionMinutas
from ..minutas.modelos import listar_modelos
from ..minutas.proveedores import resolver_destino
from ..pipeline import (SolicitudReunion, consultar_reunion, consultar_identificacion,
                        requiere_autorizacion_minutas, leer_resultado_texto)
from ..asociacion.etiquetado import Decision
from ..rutas import DIRECTORIO_PROYECTO, DIRECTORIO_RESULTADOS_PREDETERMINADO, directorio_reunion
from .fichas import etiquetar

DIR_PROCESAMIENTO = DIRECTORIO_PROYECTO
PYTHON_PROCESAMIENTO = Path(sys.executable)
# Archivos de resultados con los nombres del contrato del Hito 3 (Etapas 4 y 5)
MINUTA = "minutes.md"
TRANSCRIPCION = "transcription.json"

ETAPAS = [("preparar", "Preparación del audio"), ("diarizar", "Diarización (pyannote)"),
          ("transcribir", "Transcripción (Whisper)"), ("asociar", "Asociación temporal"),
          ("minuta", "Generación de minutas")]
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
        self._continuacion = False
        self._revision = 0
        self._restaurando = False
        self._cerrando = False
        self._minutas_base = ConfiguracionMinutas()
        self._fuentes_disponibles = {}
        self._texto_destino_modelo = ""
        self.puede_procesar = True
        self.t0 = 0.0
        self.reloj = QTimer(self)
        self.reloj.setInterval(500)
        self.reloj.timeout.connect(self._tick)
        self._armar()
        for combo in (self.cb_modelo, self.cb_whisper, self.cb_dispositivo, self.cb_dispositivo_stt):
            combo.currentIndexChanged.connect(self._opciones_cambiaron)
        self.sp_hablantes.valueChanged.connect(self._opciones_cambiaron)
        self.ed_resultados.textChanged.connect(self._opciones_cambiaron)
        for check in self.secciones.values():
            check.toggled.connect(self._opciones_cambiaron)
        self._reiniciar_etapas()
        self._opciones_cambiaron()

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
        lay.addWidget(self._armar_opciones())
        lay.addLayout(self._armar_etapas())
        lay.addLayout(self._armar_acciones())

    def _armar_archivos(self) -> QHBoxLayout:
        fila = QHBoxLayout()
        self.lista = QListWidget()
        self.lista.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lista.setMinimumHeight(4 * 30 + 6)
        self.lista.model().rowsMoved.connect(self._orden_cambiado)
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
        self.btn_nueva = QPushButton("Nueva reunión")
        self.btn_nueva.clicked.connect(self._nueva_reunion)
        botones.addWidget(self.btn_nueva)
        botones.addStretch()
        fila.addLayout(botones)
        return fila

    def _armar_opciones(self) -> QGroupBox:
        caja = QGroupBox("Opciones de procesamiento")
        g = QGridLayout(caja)
        self.ed_resultados = QLineEdit(str(DIRECTORIO_RESULTADOS_PREDETERMINADO))
        destino = QPushButton("Destino…")
        destino.clicked.connect(self._elegir_destino)
        g.addWidget(QLabel("Reunión:"), 0, 0)
        g.addWidget(self.ed_resultados, 0, 1, 1, 3)
        g.addWidget(destino, 0, 4)
        self.cb_modelo = QComboBox()
        for modelo in listar_modelos():
            self.cb_modelo.addItem(modelo.nombre, modelo.clave)
        self.cb_whisper = QComboBox()
        for modelo in ("tiny", "base", "small", "medium", "large"):
            self.cb_whisper.addItem(modelo, modelo)
        self.cb_whisper.setCurrentIndex(self.cb_whisper.findData("medium"))
        self.cb_dispositivo = QComboBox()
        for nombre in ("auto", "cpu", "cuda"):
            self.cb_dispositivo.addItem(nombre, nombre)
        g.addWidget(QLabel("Minutas:"), 1, 0)
        g.addWidget(self.cb_modelo, 1, 1)
        g.addWidget(QLabel("Whisper:"), 1, 2)
        g.addWidget(self.cb_whisper, 1, 3)
        self.cb_dispositivo_stt = QComboBox()
        for nombre in ("auto", "cpu", "cuda"):
            self.cb_dispositivo_stt.addItem(nombre, nombre)
        self.sp_hablantes = QSpinBox()
        self.sp_hablantes.setRange(0, 2147483647)
        self.sp_hablantes.setSpecialValueText("auto")
        g.addWidget(QLabel("Diarización:"), 2, 0)
        g.addWidget(self.cb_dispositivo, 2, 1)
        g.addWidget(QLabel("Dispositivo STT:"), 2, 2)
        g.addWidget(self.cb_dispositivo_stt, 2, 3)
        g.addWidget(QLabel("Hablantes:"), 3, 0)
        g.addWidget(self.sp_hablantes, 3, 1)
        self.secciones = {}
        opciones = QHBoxLayout()
        opciones.addWidget(QLabel("Secciones:"))
        for clave in SECCIONES_MINUTA:
            check = QCheckBox(clave.capitalize())
            check.setChecked(True)
            self.secciones[clave] = check
            opciones.addWidget(check)
        opciones.addStretch()
        g.addLayout(opciones, 4, 0, 1, 5)
        aviso = QLabel("Modelos experimentales de esta PoC; no determinan los modelos del producto definitivo.")
        aviso.setWordWrap(True)
        aviso.setObjectName("secundario")
        g.addWidget(aviso, 5, 0, 1, 5)
        self.lbl_destino_modelo = QLabel(objectName="secundario")
        self.lbl_destino_modelo.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_destino_modelo.setWordWrap(True)
        g.addWidget(self.lbl_destino_modelo, 6, 0, 1, 5)
        self.controles_opciones = [destino, self.ed_resultados, self.cb_modelo, self.cb_whisper,
                                   self.cb_dispositivo, self.cb_dispositivo_stt, self.sp_hablantes,
                                   *self.secciones.values()]
        return caja

    def _elegir_destino(self):
        self._revision += 1
        elegida = QFileDialog.getExistingDirectory(self, "Carpeta de la reunión", self.ed_resultados.text())
        if elegida:
            self.ed_resultados.setText(elegida)

    def _config_minutas(self) -> ConfiguracionMinutas:
        orden = tuple(dict.fromkeys((*self._minutas_base.secciones, *SECCIONES_MINUTA)))
        return replace(self._minutas_base, modelo=self.cb_modelo.currentData(),
                       secciones=tuple(k for k in orden if self.secciones[k].isChecked()),
                       permitir_remoto=False, destino_autorizado=None)

    @staticmethod
    def _args_minutas(config: ConfiguracionMinutas) -> list[str]:
        args = ["--modelo", config.modelo, "--secciones", ",".join(config.secciones)]
        for clave in ("temperatura", "max_tokens_salida", "reintentos_formato", "num_ctx", "max_caracteres_bloque"):
            args.extend(["--" + clave.replace("_", "-"), str(getattr(config, clave))])
        if config.permitir_remoto:
            args.append("--permitir-remoto")
        if config.destino_autorizado is not None:
            args.extend(["--destino-autorizado", config.destino_autorizado])
        return args

    def _opciones_cambiaron(self, *_):
        if self._restaurando:
            return
        self._revision += 1
        try:
            destino = resolver_destino(self.cb_modelo.currentData())
            modo = "ejecución local" if destino.tipo == "ollama_local" else "servicio externo"
            self._texto_destino_modelo = f"Destino del modelo: {modo} mediante {destino.descripcion}"
        except (OSError, ValueError) as error:
            self._texto_destino_modelo = f"Configuración del modelo no válida · {error}"
        self._actualizar()

    def _autorizacion_remota(self, destino) -> bool:
        respuesta = QMessageBox.question(
            self, "Modelo experimental externo",
            f"Destino de esta operación: servicio externo mediante {destino.descripcion}. "
            "Se enviarán la transcripción, los nombres identificados y las referencias temporales "
            "en los prompts y las respuestas necesarias para reintentos o consolidación; no se enviará "
            "el WAV desde el módulo de minutas. ¿Autorizar esta generación?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return respuesta == QMessageBox.StandardButton.Yes

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
        self.btn_minuta.clicked.connect(lambda: self._ver(MINUTA))
        self.btn_transcripcion = QPushButton("Ver transcripción")
        self.btn_transcripcion.clicked.connect(lambda: self._ver(TRANSCRIPCION))
        self.btn_fichas = QPushButton("Identificar de nuevo")
        self.btn_fichas.clicked.connect(self._continuar_con_fichas)
        self.btn_abrir_reunion = QPushButton("Abrir reunión…")
        self.btn_abrir_reunion.clicked.connect(self._abrir_reunion)
        self.btn_carpeta = QPushButton("Abrir resultados")
        self.btn_carpeta.clicked.connect(lambda: self._abrir(None))
        self.btn_procesar = QPushButton("Procesar")
        self.btn_procesar.clicked.connect(self._alternar)
        fila.addWidget(self.lbl, 1)
        for b in (self.btn_abrir_reunion, self.btn_fichas, self.btn_minuta, self.btn_transcripcion,
                  self.btn_carpeta, self.btn_procesar):
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
            self._cerrando = True
            self._revision += 1
            return True
        r = QMessageBox.question(self, "Procesar reunión", "Hay un procesamiento en curso. ¿Cancelarlo y salir? "
                                 "Los resultados de las etapas terminadas quedan guardados.")
        if r != QMessageBox.StandardButton.Yes:
            return False
        self._cerrando = True
        proc = self.proc
        self._cancelar()
        if self.proc is proc and not proc.waitForFinished(3000):
            self._forzar_cancelacion(proc)
            if self.proc is proc and not proc.waitForFinished(1000):
                self._cerrando = False
                return False
        return True

    def _nueva_reunion(self):
        if self.procesando or not self.puede_procesar:
            return
        self._restaurando = True
        try:
            self.resultados = None
            self.estado = {}
            self._fuentes_disponibles = {}
            self._minutas_base = ConfiguracionMinutas()
            self._poner_archivos([])
            self.ed_resultados.setText(str(DIRECTORIO_RESULTADOS_PREDETERMINADO))
            self.cb_modelo.setCurrentIndex(self.cb_modelo.findData(self._minutas_base.modelo))
            self.cb_whisper.setCurrentIndex(self.cb_whisper.findData("medium"))
            self.cb_dispositivo.setCurrentIndex(self.cb_dispositivo.findData("auto"))
            self.cb_dispositivo_stt.setCurrentIndex(self.cb_dispositivo_stt.findData("auto"))
            self.sp_hablantes.setValue(0)
            for clave, check in self.secciones.items():
                check.setChecked(clave in self._minutas_base.secciones)
            self._reiniciar_etapas()
            self.lbl.setText("Elegí los archivos de la nueva reunión.")
        finally:
            self._restaurando = False
        self._opciones_cambiaron()

    def _destino_reunion(self) -> Path:
        if not self.ed_resultados.text().strip():
            raise ValueError('Elegí una carpeta de resultados.')
        return directorio_reunion(self.ed_resultados.text(), fuentes=tuple(self.archivos()))

    def _insumos_seleccionados(self) -> dict:
        dispositivo_stt = self.cb_dispositivo_stt.currentData()
        return {'fuentes': [str(Path(p).expanduser().resolve()) for p in self.archivos()],
                'modelo_stt': self.cb_whisper.currentData(),
                'dispositivo_stt': None if dispositivo_stt == 'auto' else dispositivo_stt,
                'dispositivo_diarizacion': self.cb_dispositivo.currentData(),
                'num_speakers': self.sp_hablantes.value() or None}

    def _coinciden_insumos(self, consulta: dict) -> bool:
        solicitud = consulta.get('solicitud') or {}
        try:
            return (self._destino_reunion() == Path(consulta['carpeta']).resolve()
                    and all(solicitud.get(k) == v for k, v in self._insumos_seleccionados().items()))
        except (KeyError, ValueError, OSError):
            return False

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
        self._opciones_cambiaron()

    def _orden_cambiado(self, *_):
        self._numerar()
        self._opciones_cambiaron()

    def _numerar(self, *_):
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            ruta = it.data(Qt.ItemDataRole.UserRole)
            fuente = self._fuentes_disponibles.get(ruta, {})
            disponible = fuente.get('disponible', ruta)
            situacion = fuente.get('situacion')
            sufijo = {None: "", 'original': "", 'copia': " · copia conservada",
                      'no_disponible': " · fuente no disponible", 'modificada': " · original modificado",
                      'no_verificada': " · sin ingesta verificada"}.get(situacion, "")
            it.setText(f"{i + 1}. {Path(ruta).name}{sufijo}")
            detalle = f"\nCopia verificada: {disponible}" if disponible and disponible != ruta else ""
            if situacion == 'modificada':
                detalle = "\nEl original cambió. Continuar conserva el audio normalizado; Procesar incorpora el cambio."
            it.setToolTip(ruta + detalle)

    def _agregar(self):
        self._revision += 1
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
        elif estado == "esperando_identificacion":
            ico.setPixmap(icono_estado(None, 18).pixmap(18, 18))
            barra.setRange(0, 1000)
            barra.setValue(0)
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
        self._revision += 1
        archivos = self.archivos()
        if not archivos:
            self.lbl.setText("Elegí primero los archivos de la reunión.")
            return
        if not self.puede_procesar:
            return
        try:
            config = self._config_minutas()
            destino = self._destino_reunion()
            consulta = consultar_reunion(destino) if (destino / 'workflow.json').exists() else None
            if consulta and consulta['activa']:
                raise ValueError('Hay una ejecución activa en esta reunión.')
            anterior = consulta and consulta.get('solicitud')
            if anterior and anterior['fuentes'] != self._insumos_seleccionados()['fuentes']:
                if QMessageBox.question(self, "Modificar reunión",
                        "La carpeta ya corresponde a una reunión con fuentes distintas. ¿Reprocesarla con la nueva lista?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
            elif self.resultados is not None and self.resultados != destino:
                if QMessageBox.question(self, "Otro destino",
                        "Se utilizarán las opciones actuales para otra carpeta. ¿Procesar con estas opciones?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
            self._iniciar(archivos, destino, config)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self._mostrar_error("No se puede iniciar el procesamiento.", str(error))

    def _iniciar(self, archivos: list[str], destino: Path, config: ConfiguracionMinutas):
        insumos = self._insumos_seleccionados()
        args = ["-u", "-m", "src.pipeline", "ejecutar", *archivos,
                "--salida", str(destino), "--esperar-identificacion",
                "--modelo-stt", insumos['modelo_stt'],
                "--dispositivo-diarizacion", insumos['dispositivo_diarizacion'],
                *self._args_minutas(config)]
        if insumos['dispositivo_stt'] is not None:
            args.extend(["--dispositivo-stt", insumos['dispositivo_stt']])
        if insumos['num_speakers'] is not None:
            args.extend(["--num-speakers", str(insumos['num_speakers'])])
        self._lanzar(args, destino, continuacion=False)
        if self.procesando:
            self.mensaje.emit(f"Procesando {len(archivos)} archivo(s)…")

    def _lanzar(self, args: list[str], destino: Path, *, continuacion: bool, stdin: str | None = None):
        if not continuacion:
            self._reiniciar_etapas()
        self.buffer, self.errores, self.estado = b"", "", {}
        self.resultados = destino
        self._continuacion = continuacion
        self._revision += 1
        proc = self.proc = QProcess(self)
        proc.setWorkingDirectory(str(DIR_PROCESAMIENTO))
        proc.readyReadStandardOutput.connect(lambda: self._leer_eventos() if self.proc is proc else None)
        proc.readyReadStandardError.connect(lambda: self._leer_errores() if self.proc is proc else None)
        proc.finished.connect(lambda codigo, estado: self._terminado(codigo, estado, proc))
        self.t0 = time.monotonic()
        proc.start(str(PYTHON_PROCESAMIENTO), args)
        if not proc.waitForStarted(1500):
            if self.proc is proc:
                self.proc = None
                proc.kill()
                proc.waitForFinished(3000)
                proc.deleteLater()
                self._actualizar()
                self._mostrar_error("No se pudo iniciar el procesador.", str(PYTHON_PROCESAMIENTO))
            return
        if self.proc is not proc:
            return
        if stdin is not None:
            proc.write(stdin.encode('utf-8'))
            proc.closeWriteChannel()
        self.reloj.start()
        self._tick()
        self._actualizar()
        self.ocupado.emit(True)

    def _continuar_con_fichas(self, _=False):
        if self.resultados is None or self.procesando or not self.puede_procesar or self._cerrando:
            return
        self._revision += 1
        revision = self._revision
        carpeta = self.resultados
        try:
            config = self._config_minutas()
            asociacion, anterior, huella, consulta = consultar_identificacion(carpeta)
            if not self._coinciden_insumos(consulta):
                raise ValueError('Las fuentes o los parámetros de inferencia cambiaron. Usá Procesar para actualizar los insumos.')
            decision = etiquetar(asociacion, self, anterior=anterior)
            if self._cerrando or self.procesando or self._revision != revision or self.resultados != carpeta:
                return
            if decision.accion == "cancelar":
                if consulta['estado'] == 'esperando_identificacion':
                    # Cierra la espera sin publicar otra transcripción. Un reetiquetado
                    # abandonado de una reunión completada no altera su estado anterior.
                    self._lanzar_continuacion(carpeta, decision, config, huella)
                else:
                    self.lbl.setText("Identificación cancelada; se conservan los resultados anteriores.")
                return
            destino = resolver_destino(config.modelo)
            config = replace(config, destino_autorizado=destino.huella)
            if requiere_autorizacion_minutas(carpeta, decision, config, huella_fichas=huella):
                if not self._autorizacion_remota(destino):
                    self.lbl.setText("No se autorizó generar la minuta externa; podés continuar después.")
                    return
                config = replace(config, permitir_remoto=True)
            if self._cerrando or self.procesando or self._revision != revision or self.resultados != carpeta:
                return
            self._lanzar_continuacion(carpeta, decision, config, huella)
        except Exception as error:
            self._mostrar_error("No se pudo continuar la reunión.", str(error))

    def _lanzar_continuacion(self, carpeta, decision, config, huella):
        datos = json.dumps(asdict(decision), ensure_ascii=False)
        self._lanzar(["-u", "-m", "src.pipeline", "continuar", "--reunion", str(carpeta),
                      "--decision-json", "-", "--huella-fichas", huella, *self._args_minutas(config)],
                     carpeta, continuacion=True, stdin=datos)

    def _restaurar_reunion(self, consulta: dict):
        solicitud = consulta.get('solicitud')
        if not solicitud:
            raise ValueError('La carpeta no contiene una solicitud de reunión registrada.')
        datos = solicitud['minutas']
        config = ConfiguracionMinutas(**{**datos, 'secciones': tuple(datos['secciones']),
                                        'permitir_remoto': False, 'destino_autorizado': None})
        # Validar antes de tocar los controles; las opciones restauradas pueden
        # provenir de la API, no necesariamente de una reunión creada en Qt.
        if not isinstance(solicitud['fuentes'], list) or not all(isinstance(p, str) for p in solicitud['fuentes']):
            raise ValueError('La lista de fuentes guardada no es válida.')
        SolicitudReunion(fuentes=tuple(solicitud['fuentes']), salida=consulta['carpeta'],
                         minutas=config, modelo_stt=solicitud['modelo_stt'],
                         dispositivo_stt=solicitud['dispositivo_stt'],
                         dispositivo_diarizacion=solicitud['dispositivo_diarizacion'],
                         num_speakers=solicitud['num_speakers'], identificacion=solicitud['identificacion'])
        hablantes = solicitud['num_speakers'] or 0
        if not 0 <= hablantes <= self.sp_hablantes.maximum():
            raise ValueError('El número de hablantes guardado excede el rango de la interfaz.')
        self._restaurando = True
        try:
            self.resultados = Path(consulta['carpeta'])
            self.ed_resultados.setText(str(self.resultados))
            self._fuentes_disponibles = {f['original']: f for f in consulta.get('fuentes_disponibles', [])}
            self._poner_archivos(solicitud['fuentes'])
            self._minutas_base = config
            self.cb_modelo.setCurrentIndex(self.cb_modelo.findData(config.modelo))
            whisper = solicitud['modelo_stt']
            if self.cb_whisper.findData(whisper) < 0:
                self.cb_whisper.addItem(whisper, whisper)
            self.cb_whisper.setCurrentIndex(self.cb_whisper.findData(whisper))
            self.cb_dispositivo.setCurrentIndex(self.cb_dispositivo.findData(solicitud['dispositivo_diarizacion']))
            self.cb_dispositivo_stt.setCurrentIndex(self.cb_dispositivo_stt.findData(solicitud['dispositivo_stt'] or 'auto'))
            self.sp_hablantes.setValue(hablantes)
            for clave, check in self.secciones.items():
                check.setChecked(clave in config.secciones)
            self._restaurar_etapas(consulta)
            estados = {
                'completado': 'Reunión completada. Podés consultar sus resultados.',
                'esperando_identificacion': 'Identificación pendiente. Presioná Continuar.',
                'fallido': 'Procesamiento incompleto o fallido. Podés retomarlo.',
                'cancelado': 'Procesamiento cancelado. Podés retomarlo.',
                'pendiente': 'Reunión pendiente. Presioná Procesar.',
                'procesando': 'Hay una ejecución activa en otra instancia. Volvé a abrir la reunión para actualizar.',
            }
            self.lbl.setText(estados[consulta['estado']])
        finally:
            self._restaurando = False
        self._opciones_cambiaron()

    def _restaurar_etapas(self, consulta: dict):
        self._reiniciar_etapas()
        vigentes = set(consulta.get('etapas_vigentes') or [])
        for etapa in vigentes:
            self._poner_etapa(etapa, "ok", "Vigente")
        etapa = consulta.get('etapa')
        if etapa in self.filas and etapa not in vigentes:
            if consulta.get('activa'):
                self._poner_etapa(etapa, "en curso", "Otra ejecución")
            elif consulta['estado'] == 'esperando_identificacion':
                self._poner_etapa(etapa, "esperando_identificacion", "Identificación pendiente")
            elif consulta['estado'] == 'fallido':
                self._poner_etapa(etapa, "error", "No vigente")
            elif consulta['estado'] == 'cancelado':
                self._poner_etapa(etapa, "pendiente", "Cancelada")

    def _abrir_reunion(self):
        self._revision += 1
        elegida = QFileDialog.getExistingDirectory(self, "Abrir reunión existente", self.ed_resultados.text())
        if not elegida:
            return
        try:
            if not (Path(elegida) / 'workflow.json').is_file():
                raise ValueError('No existe workflow.json en la carpeta elegida.')
            self._restaurar_reunion(consultar_reunion(elegida, incluir_fuentes=True))
        except Exception as exc:
            self._mostrar_error("No se puede abrir esta reunión.", str(exc))

    def _cancelar(self):
        proc = self.proc
        if proc is not None:
            self.estado["cancelado"] = True
            proc.terminate()
            QTimer.singleShot(3000, self, lambda: self._forzar_cancelacion(proc))

    def _forzar_cancelacion(self, proc):
        if self.proc is proc and proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()

    def _fichas_pendientes(self, revision, carpeta):
        if (not self._cerrando and self.proc is None and self.puede_procesar
                and self._revision == revision and self.resultados == carpeta):
            self._continuar_con_fichas()

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
        """Eventos JSONL del núcleo: inicio, etapa, avance y fin."""
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

    def _terminado(self, codigo: int, _estado, proc):
        if self.proc is not proc:
            return
        self._leer_eventos()
        self._leer_errores()
        self.reloj.stop()
        self.proc = None
        proc.deleteLater()
        fin = self.estado.get("fin") or {}
        consulta = {}
        try:
            consulta = consultar_reunion(self.resultados, incluir_fuentes=True)
            self._fuentes_disponibles = {f['original']: f for f in consulta.get('fuentes_disponibles', [])}
            self._numerar()
            self._restaurar_etapas(consulta)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        efectivo = consulta.get('estado')
        if efectivo == "esperando_identificacion" and fin.get("estado") == efectivo and codigo == 0:
            self.lbl.setText("Audio transcrito. Corresponde identificar los hablantes.")
            self.ocupado.emit(False)
            self._actualizar()
            revision, carpeta = self._revision, self.resultados
            QTimer.singleShot(0, self, lambda: self._fichas_pendientes(revision, carpeta))
            return
        if efectivo == "completado" and fin.get("estado") == efectivo and codigo == 0:
            self.lbl.setText("Minuta lista.")
            self.mensaje.emit(f"Minuta lista → {self.resultados}")
        elif efectivo == "cancelado":
            self.lbl.setText("Procesamiento cancelado; quedan los resultados de las etapas terminadas.")
            self.mensaje.emit("Procesamiento cancelado.")
        elif consulta.get('activa'):
            self.lbl.setText("Todavía hay una ejecución activa. Volvé a abrir la reunión para actualizar.")
        else:
            error = consulta.get('error') or self.estado.get("error") or f"El proceso terminó con código {codigo}."
            self.lbl.setText("Error · " + error.splitlines()[0])
            self.mensaje.emit("Error en el procesamiento · " + error.splitlines()[0])
            if not self._cerrando:
                self._mostrar_error("El procesamiento no terminó. El audio y los resultados de las etapas "
                                    "terminadas quedan guardados cuando son íntegros.", error, self.errores[-4000:])
        self._actualizar()
        self.ocupado.emit(False)

    # --- resultados y estado de los botones ---------------------------------

    def _ver(self, nombre: str):
        if self.resultados is None:
            return
        if self.procesando:
            return
        try:
            contenido = leer_resultado_texto(self.resultados, nombre)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            self._mostrar_error("No se pudo verificar este resultado.", str(error))
            return
        ventana = QDialog(self)
        ventana.setWindowTitle("Minuta" if nombre == MINUTA else "Transcripción")
        ventana.resize(850, 640)
        lay = QVBoxLayout(ventana)
        texto = QPlainTextEdit(ventana)
        texto.setReadOnly(True)
        texto.setPlainText(contenido)
        lay.addWidget(texto)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(ventana.accept)
        lay.addWidget(cerrar)
        ventana.exec()

    def _abrir(self, nombre: str | None):
        if self.resultados is not None:
            if nombre:
                try:
                    artefactos = consultar_reunion(self.resultados)['artefactos']
                except (OSError, ValueError, KeyError) as error:
                    self._mostrar_error("No se pudo verificar este resultado.", str(error))
                    return
                if self.procesando or nombre not in artefactos:
                    self._mostrar_error("Este resultado no está vigente.", "Comprobá el estado de la reunión.")
                    return
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
        r = self.resultados
        consulta = {}
        if not procesando and r is not None and (r / "workflow.json").exists():
            try:
                consulta = consultar_reunion(r)
            except (OSError, ValueError, KeyError, TypeError):
                pass
        activa = bool(consulta.get('activa'))
        pendiente = False
        guardada = consulta.get('solicitud')
        if guardada and not activa:
            try:
                datos = guardada['minutas']
                config_guardada = ConfiguracionMinutas(**{**datos, 'secciones': tuple(datos['secciones']),
                                                           'permitir_remoto': False, 'destino_autorizado': None})
                pendiente = not self._coinciden_insumos(consulta) or self._config_minutas() != config_guardada
            except (ValueError, KeyError, TypeError):
                pendiente = True
        aviso = "\nLa selección aún no se aplicó; los resultados corresponden a la configuración guardada." if pendiente else ""
        self.lbl_destino_modelo.setText(self._texto_destino_modelo + aviso)
        editable = not (procesando or activa) and self.puede_procesar
        self.btn_procesar.setText("Cancelar" if procesando else "Procesar")
        self.btn_procesar.setEnabled(procesando or editable)
        for b in self.botones_archivos:
            b.setEnabled(editable)
        self.btn_nueva.setEnabled(not procesando and self.puede_procesar)
        self.lista.setEnabled(editable)
        self.btn_carpeta.setEnabled(r is not None and r.exists())
        archivos_validos = consulta.get('artefactos', {})
        self.btn_minuta.setEnabled(not procesando and MINUTA in archivos_validos)
        self.btn_transcripcion.setEnabled(not procesando and TRANSCRIPCION in archivos_validos)
        self.btn_abrir_reunion.setEnabled(not procesando and self.puede_procesar)
        insumos = {'diarization.json', 'asr.json'} <= archivos_validos.keys()
        self.btn_fichas.setText("Identificar de nuevo" if TRANSCRIPCION in archivos_validos and
                                consulta.get('estado') == 'completado' else "Continuar")
        self.btn_fichas.setEnabled(editable and insumos and self._coinciden_insumos(consulta))
        self.btn_fichas.setToolTip("" if self.btn_fichas.isEnabled() else
                                   "Usá Procesar si faltan insumos vigentes o cambiaste sus opciones.")
        for c in self.controles_opciones:
            c.setEnabled(editable)
