"""OBD-II / EOBD multimarca: ligação passo a passo, avarias, dados actuais, prontidão e identificação UDS.

Tudo o que aparece aqui vem da resposta do veículo (ou do simulador, sempre identificado). Os parâmetros
disponíveis são só os que a centralina declarou suportar; as descrições das avarias mostram a origem.
"""
import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from ... import APP_NAME, technician_mode
from ...errors import client_text, is_technical
from ...kline import port_label
from ...obd import pids as pidmod
from ..style import BAD, MUTED, OK, WARN, pill_style
from ..widgets import LiveChart
from .common import FaultAdviceCard, btn, card, lbl
from ...i18n import decimal, tr, tr_data

MAX_LIVE = 10                     # parâmetros em simultâneo (cada um é um pedido ao veículo)
KIND_COLORS = {"memorizada": BAD, "pendente": WARN, "permanente": "#B98CFF"}
# o tipo vem do motor OBD em português; aqui passa pelo catálogo (antes "memorizada" ficava por traduzir)
KIND_TEXT = {"memorizada": tr("memorizada"), "pendente": tr("pendente"), "permanente": tr("permanente")}


def _item(text, color=None, data=None):
    it = QTableWidgetItem(str(text))
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    if color:
        from PySide6.QtGui import QBrush, QColor
        it.setForeground(QBrush(QColor(color)))
    if data is not None:
        it.setData(Qt.UserRole, data)
    return it


def _table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setStretchLastSection(True)
    return t


class SummaryTile(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(2)
        v.addWidget(lbl(title.upper(), "cellName"))
        self.value = lbl("—", "h2", wrap=True)
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(self.value)
        self.sub = lbl("", "muted", wrap=True)
        v.addWidget(self.sub)

    def set(self, value, sub="", color=None, alert=False):
        self.value.setText(value)
        self.value.setStyleSheet(f"color: {color};" if color else "")
        self.sub.setText(sub)
        # luz de avaria acesa: o cartão fica com contorno vermelho, vê-se de longe
        self.setStyleSheet("QFrame#card { border: 1px solid rgba(255, 59, 78, 0.55); "
                           "background: rgba(255, 59, 78, 0.07); }" if alert else "")


class ObdPage(QWidget):
    report_req = Signal()
    vin_found = Signal(str)

    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.info = None
        self.dtcs = None
        self.connected = False
        self.live_on = False
        self.chart_pid = None
        self._live_rows = {}
        self._min_max = {}

        v = QVBoxLayout(self)
        v.setContentsMargins(32, 26, 32, 18)
        v.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(lbl(tr("OBD — todas as marcas"), "h1"))
        head.addSpacing(12)
        self.sim_pill = lbl(tr("SIMULAÇÃO"), "pill")
        self.sim_pill.setStyleSheet(pill_style(WARN))
        self.sim_pill.setToolTip(tr("Os dados vêm do simulador OBD, não de um veículo."))
        self.sim_pill.hide()
        head.addWidget(self.sim_pill, 0, Qt.AlignVCenter)
        head.addStretch(1)
        v.addLayout(head)

        # --- linha de estado: uma linha só, com os botões da ligação
        bar = card()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(18, 10, 14, 10)
        bl.setSpacing(10)
        self.state_dot = lbl("●")
        bl.addWidget(self.state_dot)
        self.state_lbl = lbl(tr("Sem ligação ao veículo"), None)
        bl.addWidget(self.state_lbl)
        self.state_sub = lbl(tr("Escolha o adaptador OBD (ou o simulador) em Opções e carregue em Ligar."),
                             "muted")
        bl.addWidget(self.state_sub, 1)
        self.connect_btn = btn(tr("Ligar ao veículo"), "primary", self._connect)
        self.disconnect_btn = btn(tr("Desligar"), None, self._disconnect)
        self.disconnect_btn.setEnabled(False)
        self.report_btn = btn(tr("Relatório"), None, lambda: self.report_req.emit())
        self.report_btn.setEnabled(False)
        bl.addWidget(self.report_btn)
        bl.addWidget(self.disconnect_btn)
        bl.addWidget(self.connect_btn)
        v.addWidget(bar)

        # --- passos da ligação: só aparecem quando a ligação falha (onde parou e o que fazer)
        self.steps_box = card()
        sl = QVBoxLayout(self.steps_box)
        sl.setContentsMargins(18, 10, 18, 10)
        sl.setSpacing(2)
        sl.addWidget(lbl(tr("ONDE A LIGAÇÃO PAROU"), "cellName"))
        self.steps_lbl = lbl("", None, wrap=True)
        self.steps_lbl.setTextFormat(Qt.RichText)
        sl.addWidget(self.steps_lbl)
        self.steps_box.hide()
        v.addWidget(self.steps_box)

        # --- resumo: o VIN e a luz de avaria (o resto fica na linha de estado)
        grid = QGridLayout()
        grid.setSpacing(12)
        self.technical = technician_mode()
        self.t_vin = SummaryTile("VIN")
        self.t_mil = SummaryTile(tr("Luz de avaria"))
        self.t_proto = SummaryTile(tr("Protocolo"))
        self.t_ecus = SummaryTile(tr("Centralinas"))
        self.t_volt = SummaryTile(tr("Tensão da bateria"))
        grid.addWidget(self.t_vin, 0, 0)
        grid.addWidget(self.t_mil, 0, 1)
        grid.setColumnStretch(0, 13)
        grid.setColumnStretch(1, 10)
        if self.technical:
            grid.addWidget(self.t_proto, 0, 2)
            grid.setColumnStretch(2, 8)
        else:
            self.t_proto.hide()
        self.t_ecus.hide()              # o número de centralinas e a tensão vão para a linha de estado
        self.t_volt.hide()
        v.addLayout(grid)

        # --- separadores
        self.tabs = QTabWidget()
        self.tabs.addTab(self._faults_tab(), tr("Avarias"))
        self.tabs.addTab(self._live_tab(), tr("Valores em tempo real"))
        self.tabs.addTab(self._ready_tab(), tr("Prontidão para a inspecção"))
        self.tabs.addTab(self._ecus_tab(), tr("Centralinas"))
        v.addWidget(self.tabs, 1)
        self._set_connected(False)
        self._paint_state(None)

    # ------------------------------------------------------------------ separadores
    def _faults_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        row = QHBoxLayout()
        self.read_btn = btn(tr("Ler de novo"), None, lambda: self._submit("obd_dtcs"))
        self.freeze_btn = btn(tr("Imagem congelada"), None, lambda: self._submit("obd_freeze"))
        self.clear_btn = btn(tr("Apagar avarias…"), "danger", self._clear)
        row.addWidget(self.read_btn)
        row.addWidget(self.freeze_btn)
        row.addStretch(1)
        row.addWidget(self.clear_btn)
        v.addLayout(row)
        split = QSplitter(Qt.Horizontal)
        self.fault_table = _table([tr("Código"), tr("Tipo"), tr("Descrição"), tr("Centralina")])
        hh = self.fault_table.horizontalHeader()
        hh.setStretchLastSection(False)
        for c in (0, 1, 3):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        self.fault_table.itemSelectionChanged.connect(self._fault_selected)
        split.addWidget(self.fault_table)
        self.advice = FaultAdviceCard(tr("Seleccione uma avaria para ver a categoria, a origem da descrição e o que "
                                         "verificar."))
        split.addWidget(self.advice)
        split.setSizes([640, 420])
        v.addWidget(split, 1)
        self.faults_note = lbl("", "muted", wrap=True)
        v.addWidget(self.faults_note)
        return w

    def _live_tab(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(14, 14, 14, 14)
        h.setSpacing(12)
        left = QVBoxLayout()
        left.addWidget(lbl(tr("Parâmetros suportados (até {MAX_LIVE})", MAX_LIVE=MAX_LIVE), "cellName"))
        self.pid_list = QListWidget()
        self.pid_list.setMinimumWidth(270)
        self.pid_list.itemChanged.connect(self._pid_toggled)
        left.addWidget(self.pid_list, 1)
        self.live_btn = btn(tr("Iniciar leitura"), "primary", self._toggle_live)
        left.addWidget(self.live_btn)
        h.addLayout(left)
        right = QVBoxLayout()
        self.live_table = _table([tr("Parâmetro"), tr("Valor"), tr("Unidade"), tr("Mín."), tr("Máx.")])
        self.live_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.live_table.itemSelectionChanged.connect(self._live_selected)
        self.live_table.setMinimumHeight(190)
        right.addWidget(self.live_table, 3)
        self.chart_title = lbl(tr("Seleccione um parâmetro na tabela para ver o gráfico."), "muted")
        right.addWidget(self.chart_title)
        self.chart = LiveChart(maxlen=600)
        self.chart.setMinimumSize(420, 170)
        right.addWidget(self.chart, 2)
        h.addLayout(right, 1)
        return w

    def _ready_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        self.ready_lbl = lbl(tr("Os monitores de prontidão dizem se os auto-testes de emissões já correram desde o "
                                "último apagar de avarias (importante para a inspecção)."), "muted", wrap=True)
        v.addWidget(self.ready_lbl)
        self.ready_table = _table([tr("Centralina"), tr("Monitor"), tr("Tipo"), tr("Estado")])
        self.ready_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        v.addWidget(self.ready_table, 1)
        return w

    def _ecus_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        cols = [tr("Centralina"), tr("Parâmetros"), tr("Calibração")]
        self.ecu_table = _table(cols + [tr("Pedido UDS")] if self.technical else cols)
        self.ecu_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        v.addWidget(self.ecu_table, 1)
        row = QHBoxLayout()
        self.uds_btn = btn(tr("Ler identificação detalhada da centralina seleccionada"), None, self._uds)
        row.addWidget(self.uds_btn)
        row.addStretch(1)
        v.addLayout(row)
        self.uds_out = QPlainTextEdit()
        self.uds_out.setReadOnly(True)
        self.uds_out.setPlaceholderText(tr("Identificação detalhada da centralina (números de peça e de software) e "
                                           "avarias com o tipo de falha. Disponível nos veículos mais recentes."))
        self.uds_out.setMaximumHeight(200)
        v.addWidget(self.uds_out)
        return w

    # ------------------------------------------------------------------ acções
    def _submit(self, cmd, *args):
        if self.worker.is_busy:
            self.state_sub.setText(tr("Aguarde — ainda a comunicar com o veículo…"))
            return
        self.worker.submit(cmd, *args)

    def _connect(self):
        self.stop_live()
        self.state_lbl.setText(tr("A ligar…"))
        self._paint_state(WARN)
        self.state_sub.setText(tr("A ligar ao veículo (pode demorar até 20 s na primeira vez)."))
        self.connect_btn.setEnabled(False)
        self._submit("obd_connect")

    def _disconnect(self):
        self.stop_live()
        self._submit("obd_disconnect")

    def _clear(self):
        if not self.connected:
            return
        box = QMessageBox(self)
        box.setWindowTitle(tr("Apagar avarias"))
        box.setIcon(QMessageBox.Warning)
        box.setTextFormat(Qt.RichText)
        box.setText(tr("<p><b>Vai pedir a TODAS as centralinas que apaguem as avarias.</b></p>"
                       "<ul><li>Apaga também as imagens congeladas e repõe os monitores de prontidão "
                       "(o carro pode chumbar na inspecção até completar um ciclo de condução).</li>"
                       "<li>Ignição ligada e <b>motor desligado</b> — muitas centralinas recusam com o motor a "
                       "trabalhar.</li>"
                       "<li>As avarias permanentes não se apagam por este pedido.</li></ul>"
                       "<p>Depois do pedido, o programa volta a ler as avarias para confirmar.</p>"))
        yes = box.addButton(tr("Apagar avarias"), QMessageBox.DestructiveRole)
        box.addButton(tr("Cancelar"), QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is yes:
            self.stop_live()
            self._submit("obd_clear")

    def _uds(self):
        rows = self.ecu_table.selectionModel().selectedRows()
        if not rows:
            self.uds_out.setPlainText(tr("Seleccione uma centralina na tabela."))
            return
        target = self.ecu_table.item(rows[0].row(), 0).data(Qt.UserRole)
        if not target:
            self.uds_out.setPlainText(tr("A identificação detalhada não está disponível para esta centralina."))
            return
        self.uds_out.setPlainText(tr("A ler a identificação da centralina {target}…", target=target))
        self._submit("obd_uds", target)

    # ------------------------------------------------------------------ dados actuais
    def _pid_toggled(self, _item):
        checked = self._checked_pids()
        if len(checked) > MAX_LIVE:
            _item.setCheckState(Qt.Unchecked)
            self.state_sub.setText(tr("No máximo {MAX_LIVE} parâmetros ao mesmo tempo (cada um é um pedido ao "
                                      "veículo).",
                                      MAX_LIVE=MAX_LIVE))
            return
        if self.live_on:
            self.worker.set_live("obd", checked)
            self._build_live_rows(checked)

    def _checked_pids(self):
        out = []
        for i in range(self.pid_list.count()):
            it = self.pid_list.item(i)
            if it.checkState() == Qt.Checked:
                out.append(it.data(Qt.UserRole))
        return out

    def _toggle_live(self):
        if self.live_on:
            self.stop_live()
            return
        sel = self._checked_pids()
        if not sel:
            self.state_sub.setText(tr("Marque pelo menos um parâmetro na lista."))
            return
        if self.worker.is_busy:
            self.state_sub.setText(tr("Aguarde — ainda a comunicar com o veículo…"))
            return
        self._build_live_rows(sel)
        self.live_on = True
        self.live_btn.setText(tr("Parar leitura"))
        self.worker.set_live("obd", sel)

    def stop_live(self):
        if self.live_on:
            self.worker.set_live(None, [])
        self.live_on = False
        self.live_btn.setText(tr("Iniciar leitura"))

    def _build_live_rows(self, sel):
        self.live_table.setRowCount(len(sel))
        self._live_rows = {}
        for r, pid in enumerate(sel):
            self._live_rows[pid] = r
            self.live_table.setItem(r, 0, _item(pidmod.name(pid), data=pid))
            for c in range(1, 5):
                self.live_table.setItem(r, c, _item("—"))

    def _live_selected(self):
        rows = self.live_table.selectionModel().selectedRows()
        if not rows:
            return
        pid = self.live_table.item(rows[0].row(), 0).data(Qt.UserRole)
        if pid != self.chart_pid:
            self.chart_pid = pid
            self.chart.clear()
            p = pidmod.TABLE.get(pid)
            self.chart_title.setText(f"{pidmod.name(pid)}" + (f" ({p.unit})" if p and p.unit else ""))

    def on_live(self, data):
        if not self.live_on:
            return
        t = data.get("t", 0)
        for pid, val in data.get("values", {}).items():
            r = self._live_rows.get(pid)
            if r is None:
                continue
            if "error" in val:
                self.live_table.item(r, 1).setText(val["error"])
                continue
            v = val["value"]
            txt = decimal(f"{v:g}") if isinstance(v, (int, float)) else str(v)
            self.live_table.item(r, 1).setText(txt)
            self.live_table.item(r, 2).setText(val.get("unit", ""))
            num = val.get("numeric")
            if num is not None:
                lo, hi = self._min_max.get(pid, (num, num))
                lo, hi = min(lo, num), max(hi, num)
                self._min_max[pid] = (lo, hi)
                self.live_table.item(r, 3).setText(f"{lo:g}")
                self.live_table.item(r, 4).setText(f"{hi:g}")
                if pid == self.chart_pid:
                    self.chart.add(t, num)

    # ------------------------------------------------------------------ estado
    def _set_connected(self, on):
        self.connected = on
        for b in (self.read_btn, self.freeze_btn, self.clear_btn, self.live_btn, self.uds_btn, self.disconnect_btn):
            b.setEnabled(on)
        self.report_btn.setEnabled(on and self.dtcs is not None)
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText(tr("Voltar a ligar") if on else tr("Ligar ao veículo"))
        if not on:
            self.stop_live()

    def _paint_state(self, color):
        """Cor do ponto e do texto da linha de estado (verde ligado, âmbar a ligar, vermelho falhou)."""
        self.state_dot.setStyleSheet(f"color: {color or MUTED};")
        self.state_lbl.setStyleSheet("font-weight: 700;" + (f" color: {color};" if color else ""))

    def set_adapter_text(self, text):
        if not self.connected:
            self.state_sub.setText(text)

    def show_steps(self, steps):
        if not steps:
            self.steps_box.hide()
            return
        if all(ok for _n, ok, _d in steps):
            # tudo confirmado: os passos não ocupam espaço (ficam na dica da linha de estado)
            self.state_lbl.setToolTip("\n".join(f"✔ {n}" + (f" — {d}" if self.technical or not is_technical(d)
                                                             else "") for n, _ok, d in steps))
            self.steps_box.hide()
            return
        self.steps_lbl.setToolTip("")
        if not self.technical:          # o pormenor técnico de cada passo fica só no registo
            steps = [(n, ok, ("" if is_technical(d) else d) if ok else client_text(d)) for n, ok, d in steps]
        rows = []
        for name, ok, detail in steps:
            color = OK if ok else BAD
            mark = "✔" if ok else "✖"
            rows.append(f"<span style='color:{color}'><b>{mark}</b></span>&nbsp; <b>{html.escape(name)}</b>"
                        + (f" <span style='color:{MUTED}'>— {html.escape(str(detail))}</span>" if detail else ""))
        self.steps_lbl.setText("<br>".join(rows))
        self.steps_box.show()

    def on_connected(self, info):
        self.info = info
        self.dtcs = None
        self._min_max = {}
        self._set_connected(True)
        sim = bool(info.get("simulated"))
        self.sim_pill.setVisible(sim)
        self.state_lbl.setText(tr("Ligado ao veículo") + (tr(" (simulação)") if sim else ""))
        self._paint_state(OK)
        ad = info.get("adapter") or {}
        if self.technical:
            self.state_sub.setText(f"{ad.get('version') or 'Adaptador'} · {info.get('interface', '')} · "
                                   f"{info.get('protocol', '')}")
        else:
            self.state_sub.setText(tr("Adaptador OBD · {port}", port=port_label(info.get("interface", ""))))
        self.show_steps(info.get("steps"))
        vin = info.get("vin")
        self.t_vin.set(vin or tr("não disponível"), tr("declarado pela centralina ") + info["vin_ecu"] if vin else
                       tr("o veículo não indicou o VIN"))
        self.t_proto.set(info.get("protocol", "—"))
        self.t_mil.set(tr("ACESA") if info.get("mil") else tr("apagada"),
                       tr("{v} avaria(s) declarada(s) pelas centralinas", v=info.get('dtc_count', 0)),
                       BAD if info.get("mil") else OK, alert=bool(info.get("mil")))
        self.t_ecus.set(str(len(info.get("ecus", []))), ", ".join(e["ecu"] for e in info.get("ecus", [])))
        volt = ad.get("voltage")
        n_ecus = len(info.get("ecus", []))
        extra = [tr("{n} centralina(s)", n=n_ecus)]
        if volt is not None:
            extra.append(tr("bateria {v}", v=decimal(f"{volt:.1f} V")))
        self.state_sub.setText(self.state_sub.text() + " · " + " · ".join(extra))
        self.t_volt.set(decimal(f"{volt:.1f} V") if volt is not None else "—",
                        tr("medida pelo adaptador") if volt is not None else tr("não medida"))
        # parâmetros suportados pela centralina principal
        self.pid_list.blockSignals(True)
        self.pid_list.clear()
        primary = info.get("primary")
        sup = next((e["pids"] for e in info.get("ecus", []) if e["ecu"] == primary), [])
        live = [p for p in sup if p in pidmod.TABLE and p not in pidmod.INFO_PIDS and p != 0x01]
        for pid in live:
            p = pidmod.TABLE[pid]
            it = QListWidgetItem(f"{p.short}" + (f"  ({p.unit})" if p.unit else ""))
            it.setToolTip(tr("PID {pid:02X} — {name}", pid=pid, name=p.name) if self.technical else p.name)
            it.setData(Qt.UserRole, pid)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if pid in (0x0C, 0x05, 0x0D, 0x42) else Qt.Unchecked)
            self.pid_list.addItem(it)
        self.pid_list.blockSignals(False)
        if not live:
            it = QListWidgetItem(tr("A centralina não declarou parâmetros que o programa saiba interpretar."))
            it.setFlags(Qt.NoItemFlags)
            self.pid_list.addItem(it)
        self._fill_readiness(info)
        self._fill_ecus(info)
        self.fault_table.setRowCount(0)
        self.advice.clear()
        self.faults_note.setText(tr("A ler as avarias…"))
        if vin:
            self.vin_found.emit(vin)
        self.worker.submit("obd_dtcs")          # a fila da thread garante a ordem; não é um clique repetido

    def _fill_readiness(self, info):
        rows = []
        for e in info.get("ecus", []):
            st = e.get("status")
            if not st:
                continue
            for m in st["monitors"]:
                if not m["supported"]:
                    continue
                rows.append((e["ecu"], m["name"], tr("contínuo") if m["continuous"] else tr("não contínuo"),
                             tr("completo") if m["complete"] else tr("incompleto")))
        self.ready_table.setRowCount(len(rows))
        for r, (ecu, name, kind, state) in enumerate(rows):
            self.ready_table.setItem(r, 0, _item(ecu))
            self.ready_table.setItem(r, 1, _item(name))
            self.ready_table.setItem(r, 2, _item(kind))
            self.ready_table.setItem(r, 3, _item(state, OK if state == "completo" else WARN))
        if not rows:
            self.ready_lbl.setText(tr("Nenhuma centralina indicou o estado dos monitores de prontidão."))

    def _fill_ecus(self, info):
        ecus = info.get("ecus", [])
        self.ecu_table.setRowCount(len(ecus))
        for r, e in enumerate(ecus):
            self.ecu_table.setItem(r, 0, _item(e["label"], data=e.get("uds_target")))
            self.ecu_table.setItem(r, 1, _item(str(len(e["pids"]))))
            self.ecu_table.setItem(r, 2, _item(", ".join(e.get("calibration") or []) or "—"))
            if self.technical:
                self.ecu_table.setItem(r, 3, _item(e.get("uds_target") or "—"))
        if ecus:
            self.ecu_table.selectRow(0)

    def on_dtcs(self, d):
        self.dtcs = d
        self.report_btn.setEnabled(self.connected)
        rows = []
        for kind in ("stored", "pending", "permanent"):
            rows += d.get(kind, [])
        self.fault_table.setRowCount(len(rows))
        for r, f in enumerate(rows):
            fault = self._as_fault(f)
            self.fault_table.setItem(r, 0, _item(f["code"], data=fault))
            kind = KIND_TEXT.get(f["kind"], tr_data(f["kind"]))
            self.fault_table.setItem(r, 1, _item(kind, KIND_COLORS.get(f["kind"])))
            desc = f["desc"] or tr("Sem descrição na base instalada — {category}", category=f['category'])
            self.fault_table.setItem(r, 2, _item(desc, None if f["desc"] else MUTED))
            self.fault_table.setItem(r, 3, _item(f["ecu"], MUTED))
        self.tabs.setTabText(0, tr("Avarias ({n})", n=len(rows)) if rows else tr("Avarias"))
        notes = []
        if not rows:
            notes.append(tr("Nenhuma avaria nas centralinas que responderam (") + ", ".join(d.get("ecus", [])) + ").")
        if d.get("unsupported"):
            names = {"pending": tr("pendentes"), "permanent": tr("permanentes")}
            notes.append(tr("Não suportado pelo veículo: {kinds}.",
                            kinds=", ".join(names.get(k, k) for k in d["unsupported"])))
        notes.append(tr("Descrições: os códigos comuns a todas as marcas têm descrição completa; os códigos próprios "
                        "de cada marca mostram apenas a categoria."))
        self.faults_note.setText(" ".join(notes))
        if rows:
            self.fault_table.selectRow(0)
        else:
            self.advice.clear()

    @staticmethod
    def _as_fault(f):
        kinds = {"memorizada": "stored", "pendente": "pending", "permanente": "permanent"}
        return {"vag": f["code"], "pcode": f["code"], "code": None, "obd_kind": kinds.get(f["kind"], "stored"),
                "desc": f["desc"] or tr("Sem descrição na base instalada ({category})", category=f['category']),
                "intermittent": f["kind"] == "pendente"}

    def _fault_selected(self):
        rows = self.fault_table.selectionModel().selectedRows()
        if not rows:
            self.advice.clear()
            return
        self.advice.set_fault(self.fault_table.item(rows[0].row(), 0).data(Qt.UserRole))

    def on_clear(self, r):
        self.on_dtcs(r["after"])
        if r.get("info"):
            self.info = r["info"]
            self.t_mil.set(tr("ACESA") if self.info.get("mil") else tr("apagada"),
                           tr("depois de apagar"), BAD if self.info.get("mil") else OK,
                           alert=bool(self.info.get("mil")))
            self._fill_readiness(self.info)

    def on_freeze(self, ff):
        if not ff:
            QMessageBox.information(self, APP_NAME, tr("Nenhuma imagem congelada guardada na centralina principal."))
            return
        rows = "".join(f"<tr><td>{html.escape(v['name'])}</td><td><b>{decimal(format(v['value'], 'g'))}</b> "
                       f"{html.escape(v['unit'])}</td></tr>"
                       if isinstance(v["value"], (int, float)) else
                       f"<tr><td>{html.escape(v['name'])}</td><td><b>{html.escape(str(v['value']))}</b></td></tr>"
                       for v in ff["values"].values())
        box = QMessageBox(self)
        box.setWindowTitle(tr("Imagem congelada"))
        box.setTextFormat(Qt.RichText)
        box.setText(tr("<p>Condições no momento em que a avaria <b>{dtc}</b> foi registada "
                       "(centralina {ecu}):</p>", dtc=html.escape(ff['dtc']), ecu=html.escape(ff['ecu']))
                    + f"<table cellspacing='6'>{rows or '<tr><td>—</td></tr>'}</table>")
        box.exec()

    def on_uds(self, r):
        lines = [tr("Centralina {target} — identificação detalhada", target=r['target']), ""]
        for did, v in r["ident"].items():
            prefix = f"{did:04X}  " if self.technical else ""
            lines.append(f"  {prefix}{v['name']}: {v['value']}")
        lines.append("")
        if r.get("dtc_error"):
            lines.append(tr("Avarias: não disponíveis ({dtc_error})", dtc_error=client_text(r['dtc_error'])))
        elif not r["dtcs"]:
            lines.append(tr("Avarias: nenhuma presente, pendente ou confirmada"))
        else:
            lines.append(tr("Avarias:"))
            for d in r["dtcs"]:
                lines.append(f"  {d['code']}-{d['ftb']:02X}  {d['desc'] or tr('(sem descrição)')} — {d['ftb_text']}; "
                             f"{', '.join(d['status_text'])}")
        self.uds_out.setPlainText("\n".join(lines))

    def on_error(self, cmd, msg):
        if cmd == "obd_connect":
            self._set_connected(False)
            self.state_lbl.setText(tr("Sem ligação ao veículo"))
            self._paint_state(BAD)
            self.state_sub.setText(client_text(msg))
        elif cmd == "obd_uds":
            self.uds_out.setPlainText(client_text(msg))
        else:
            self.state_sub.setText(client_text(msg))

    def _mark_stale(self):
        """Depois de desligar: os valores ficam como última leitura, sem o alarme vermelho nem a contagem."""
        self.tabs.setTabText(0, tr("Avarias"))
        if self.info is not None:
            self.t_mil.setStyleSheet("")
            self.t_mil.sub.setText(tr("última leitura, antes de desligar"))

    def on_lost(self, reason):
        self._set_connected(False)
        self._mark_stale()
        self.sim_pill.hide()
        self.state_lbl.setText(tr("Ligação ao veículo perdida"))
        self._paint_state(BAD)
        self.state_sub.setText(client_text(reason))

    def on_disconnected(self):
        self._set_connected(False)
        self._mark_stale()
        self.sim_pill.hide()
        self.state_lbl.setText(tr("Sem ligação ao veículo"))
        self._paint_state(None)
        self.state_sub.setText(tr("Ligação fechada."))

    def report_items(self):
        """Itens para o relatório/histórico (formato do Auto-Scan)."""
        if not self.info or self.dtcs is None:
            return []
        from ...obd.session import report_items
        return report_items(self.info, self.dtcs)
