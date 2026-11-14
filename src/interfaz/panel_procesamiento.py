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
from dataclasses import asdict
from typing import Callable
import sys

from PySide6.QtCore import QProcess, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QSizePolicy,
                               QVBoxLayout, QComboBox, QCheckBox, QLineEdit, QPlainTextEdit, QDialog)

from .estilo import fuente, icono_estado, icono_pendiente

from ..minutas.contratos import SECCIONES_MINUTA
from ..minutas.generacion import ConfiguracionMinutas
from ..minutas.modelos import listar_modelos
from ..pipeline import consultar_reunion
from ..pipeline.ejecucion import _consentimiento
from ..asociacion.asociacion import asociar
from ..rutas import DIRECTORIO_PROYECTO, DIRECTORIO_RESULTADOS_PREDETERMINADO
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
        lay.addWidget(self._armar_opciones())
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
        g.addWidget(self.cb_dispositivo, 1, 4)
        self.secciones = {}
        opciones = QHBoxLayout()
        opciones.addWidget(QLabel("Secciones:"))
        for clave in SECCIONES_MINUTA:
            check = QCheckBox(clave.capitalize())
            check.setChecked(True)
            self.secciones[clave] = check
            opciones.addWidget(check)
        opciones.addStretch()
        g.addLayout(opciones, 2, 0, 1, 5)
        aviso = QLabel("Modelos experimentales de esta PoC; no determinan los modelos del producto definitivo.")
        aviso.setWordWrap(True)
        aviso.setObjectName("secundario")
        g.addWidget(aviso, 3, 0, 1, 5)
        self.controles_opciones = [destino, self.ed_resultados, self.cb_modelo, self.cb_whisper,
                                   self.cb_dispositivo, *self.secciones.values()]
        return caja

    def _elegir_destino(self):
        elegida = QFileDialog.getExistingDirectory(self, "Carpeta de la reunión", self.ed_resultados.text())
        if elegida:
            self.ed_resultados.setText(elegida)

    def _autorizacion_remota(self) -> bool:
        config = ConfiguracionMinutas(modelo=self.cb_modelo.currentData(), permitir_remoto=True,
                        secciones=tuple(k for k, c in self.secciones.items() if c.isChecked()))
        destino = _consentimiento(config)
        if destino == "ollama_local":
            return False
        respuesta = QMessageBox.question(
            self, "Modelo experimental externo",
            "El modelo elegido procesa la minuta en un servicio externo. Se enviarán la transcripción, "
            "los nombres identificados y las referencias temporales en los prompts; no se enviará el WAV "
            "desde el módulo de minutas. ¿Autorizar esta ejecución?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if respuesta != QMessageBox.StandardButton.Yes:
            raise PermissionError("No se autorizó enviar datos a un servicio externo.")
        return True

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
        if not self.archivos():
            self._agregar_ultima()
        archivos = self.archivos()
        if not archivos:
            return
        if not any(c.isChecked() for c in self.secciones.values()):
            self._mostrar_error("Seleccioná al menos una sección de minuta.", "")
            return
        try:
            permitir_remoto = self._autorizacion_remota()
        except (ValueError, PermissionError) as e:
            self.lbl.setText(str(e))
            return
        self._iniciar(archivos, permitir_remoto)

    def _iniciar(self, archivos: list[str], permitir_remoto: bool):
        destino = Path(self.ed_resultados.text()).expanduser().resolve()
        args = ["-u", "-m", "src.pipeline", "ejecutar", *archivos,
                "--salida", str(destino), "--esperar-identificacion",
                "--modelo", self.cb_modelo.currentData(),
                "--modelo-stt", self.cb_whisper.currentData(),
                "--dispositivo-diarizacion", self.cb_dispositivo.currentData(),
                "--secciones", ",".join(k for k, c in self.secciones.items() if c.isChecked())]
        if self.cb_dispositivo.currentData() != "auto":
            args.extend(["--dispositivo-stt", self.cb_dispositivo.currentData()])
        if permitir_remoto:
            args.append("--permitir-remoto")
        self._lanzar(args, destino, continuacion=False)
        self.mensaje.emit(f"Procesando {len(archivos)} archivo(s)…")

    def _lanzar(self, args: list[str], destino: Path, *, continuacion: bool, stdin: str | None = None):
        if not continuacion:
            self._reiniciar_etapas()
        self.buffer, self.errores, self.estado = b"", "", {}
        self.resultados = destino
        self._continuacion = continuacion
        self.proc = QProcess(self)
        self.proc.setWorkingDirectory(str(DIR_PROCESAMIENTO))
        self.proc.readyReadStandardOutput.connect(self._leer_eventos)
        self.proc.readyReadStandardError.connect(self._leer_errores)
        self.proc.finished.connect(self._terminado)
        self.t0 = time.monotonic()
        self.proc.start(str(PYTHON_PROCESAMIENTO), args)
        if not self.proc.waitForStarted(1500):
            self.proc = None
            self._mostrar_error("No se pudo iniciar el procesador.", str(PYTHON_PROCESAMIENTO))
            return
        if stdin is not None:
            self.proc.write(stdin.encode('utf-8'))
            self.proc.closeWriteChannel()
        self.reloj.start()
        self._tick()
        self._actualizar()
        self.ocupado.emit(True)

    def _continuar_con_fichas(self, _=False, *, reconfirmar=True):
        if self.resultados is None:
            return
        # Una reanudación tras cerrar la aplicación o un reetiquetado posterior
        # no reutiliza silenciosamente una autorización remota anterior.
        if reconfirmar:
            try:
                anterior = consultar_reunion(self.resultados)['solicitud']['minutas']
                config = ConfiguracionMinutas(**{**anterior, 'secciones': tuple(anterior['secciones'])})
                if _consentimiento(config) != 'ollama_local':
                    respuesta = QMessageBox.question(
                        self, 'Confirmar modelo externo',
                        'Esta continuación puede volver a enviar la transcripción al proveedor externo. '
                        '¿Autorizar esta ejecución?',
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No)
                    if respuesta != QMessageBox.StandardButton.Yes:
                        return
            except (ValueError, PermissionError, KeyError, TypeError) as error:
                self._mostrar_error('No se puede autorizar la continuación.', str(error))
                return
        try:
            consulta = consultar_reunion(self.resultados)
            if not {'diarization.json', 'asr.json'} <= consulta['artefactos'].keys():
                raise ValueError('Los insumos para identificación no están vigentes.')
            decision = etiquetar(asociar(self.resultados), self)
        except Exception as error:
            self._mostrar_error("No se pudieron abrir las fichas.", str(error))
            return
        if decision.accion == "cancelar":
            self.lbl.setText("Identificación cancelada. Podés reabrir la reunión para continuar.")
            return
        datos = json.dumps(asdict(decision), ensure_ascii=False)
        self._lanzar(["-u", "-m", "src.pipeline", "continuar", "--reunion",
                      str(self.resultados), "--decision-json", "-"], self.resultados,
                     continuacion=True, stdin=datos)

    def _abrir_reunion(self):
        elegida = QFileDialog.getExistingDirectory(self, "Abrir reunión existente", self.ed_resultados.text())
        if not elegida:
            return
        try:
            consulta = consultar_reunion(elegida)
        except Exception as exc:
            self._mostrar_error("No se puede abrir esta reunión.", str(exc))
            return
        self.resultados = Path(elegida)
        self.ed_resultados.setText(elegida)
        if consulta['estado'] in ('esperando_identificacion', 'cancelado', 'fallido') and \
           {'diarization.json', 'asr.json'} <= consulta['artefactos'].keys():
            self._continuar_con_fichas()
        else:
            self.lbl.setText(f"Reunión abierta: {consulta['estado']}.")
        self._actualizar()

    def _cancelar(self):
        if self.proc is not None:
            self.estado["cancelado"] = True
            self.proc.terminate()  # el padre detiene los procesos de inferencia descendientes
            QTimer.singleShot(3000, self._forzar_cancelacion)

    def _forzar_cancelacion(self):
        if self.proc is not None and self.proc.state() != QProcess.ProcessState.NotRunning:
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

    def _terminado(self, codigo: int, _estado):
        self._leer_eventos()
        self._leer_errores()
        self.reloj.stop()
        self.proc = None
        fin = self.estado.get("fin") or {}
        if fin.get("estado") == "esperando_identificacion" and codigo == 0:
            self.lbl.setText("Audio transcrito. Corresponde identificar los hablantes.")
            self.ocupado.emit(False)
            self._actualizar()
            QTimer.singleShot(0, lambda: self._continuar_con_fichas(reconfirmar=False))
            return
        if fin.get("estado") == "completado" and codigo == 0:
            self.lbl.setText("Minuta lista.")
            self.mensaje.emit(f"Minuta lista → {self.resultados}")
        elif fin.get("estado") == "cancelado" or self.estado.get("cancelado"):
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

    def _ver(self, nombre: str):
        if self.resultados is None:
            return
        try:
            consulta = consultar_reunion(self.resultados)
        except (OSError, ValueError, KeyError) as error:
            self._mostrar_error("No se pudo verificar este resultado.", str(error))
            return
        if self.procesando or nombre not in consulta['artefactos']:
            self._mostrar_error("Este resultado no está vigente.", "Comprobá el estado de la reunión.")
            return
        ventana = QDialog(self)
        ventana.setWindowTitle("Minuta" if nombre == MINUTA else "Transcripción")
        ventana.resize(850, 640)
        lay = QVBoxLayout(ventana)
        texto = QPlainTextEdit(ventana)
        texto.setReadOnly(True)
        texto.setPlainText(Path(consulta['artefactos'][nombre]).read_text(encoding='utf-8'))
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
        self.btn_procesar.setText("Cancelar" if procesando else "Procesar")
        self.btn_procesar.setEnabled(procesando or self.puede_procesar)
        for b in self.botones_archivos:
            b.setEnabled(not procesando)
        self.lista.setEnabled(not procesando)
        r = self.resultados
        self.btn_carpeta.setEnabled(r is not None and r.exists())
        archivos_validos = {}
        if r is not None and (r / "workflow.json").exists():
            try:
                archivos_validos = consultar_reunion(r)['artefactos']
            except (OSError, ValueError, KeyError):
                pass
        self.btn_minuta.setEnabled(not procesando and MINUTA in archivos_validos)
        self.btn_transcripcion.setEnabled(not procesando and TRANSCRIPCION in archivos_validos)
        self.btn_abrir_reunion.setEnabled(not procesando and self.puede_procesar)
        self.btn_fichas.setEnabled(not procesando and self.puede_procesar and
            'diarization.json' in archivos_validos and 'asr.json' in archivos_validos)
        for c in self.controles_opciones:
            c.setEnabled(not procesando)
