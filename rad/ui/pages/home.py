"""Página inicial: o carro que está na oficina e o botão para o diagnosticar, e os últimos carros (clicar num
reabre-o). O estado do cabo e da ligação fica numa linha por cima (o mesmo está sempre no menu); a configuração do
cabo, os controladores e o OBD estão no menu, por isso não se repetem aqui."""
from PySide6.QtCore import QSize, QStringListModel, Qt, Signal
from PySide6.QtWidgets import (
    QCompleter, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QScrollArea,
    QVBoxLayout, QWidget,
)

from ... import connstate
from ...errors import client_text
from ..style import BAD, BLUE, CYAN, LINE, MUTED, OK, WARN, pill_style
from ..widgets import glow, nav_icon
from .common import lbl, btn, card
from ...i18n import tr


# ------------------------------------------------------------------- início
class HomePage(QWidget):
    go = Signal(str)

    VEHICLE_FIELDS = [("client", tr("Cliente")), ("plate", tr("Matrícula")), ("model", tr("Marca / modelo")),
                      ("vin", "VIN"), ("km", tr("Quilómetros"))]

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        v = QVBoxLayout(body)
        v.setContentsMargins(32, 26, 32, 28)
        v.setSpacing(16)
        v.addWidget(lbl(tr("Início"), "h1"))

        # --- estado do cabo e do carro: uma linha só (o pormenor está no menu e em Opções)
        sb = QFrame()
        sb.setObjectName("card")
        sl = QHBoxLayout(sb)
        sl.setContentsMargins(18, 10, 14, 10)
        sl.setSpacing(10)
        self.status_dot = lbl("●")
        sl.addWidget(self.status_dot)
        self.link_iface = lbl(tr("Cabo por configurar"), None)
        self.link_iface.setStyleSheet("font-weight: 600;")
        sl.addWidget(self.link_iface)
        self.port_pill = lbl(tr("por configurar"), "pill")
        self.port_pill.setStyleSheet(pill_style(MUTED))
        self.port_pill.setToolTip(tr("Cabo"))
        sl.addWidget(self.port_pill)
        self.link_pill = lbl(connstate.LinkStatus(connstate.NO_DEVICE).label, "pill")
        self.link_pill.setStyleSheet(pill_style(MUTED))
        self.link_pill.setToolTip(tr("Carro"))
        sl.addWidget(self.link_pill)
        self.status_lbl = lbl(tr("Cabo por configurar"), "muted")
        sl.addWidget(self.status_lbl, 1)
        self.link_detail = lbl("", "muted")
        self.link_detail.hide()                          # o último resultado vai para o tooltip da linha
        self.sim_btn = btn(tr("Abrir simulador"), None, lambda: self.go.emit("sim"))
        self.sim_btn.setToolTip(tr("Experimente todas as funções sem carro (motor 1.9 TDI, ABS e painel)."))
        sl.addWidget(self.sim_btn)
        self.cable_btn = btn(tr("Configurar cabo"), None, lambda: self.go.emit("options"))
        sl.addWidget(self.cable_btn)
        self.status_bar = sb
        v.addWidget(sb)

        # --- o carro que está na oficina: matrícula em grande, os outros dados ao lado e o botão principal
        vc = QFrame()
        vc.setObjectName("cardGlow")
        vl = QVBoxLayout(vc)
        vl.setContentsMargins(24, 18, 24, 20)
        vl.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(lbl(tr("Carro na oficina"), "h2"))
        head.addSpacing(12)
        head.addWidget(lbl(tr("Estes dados aparecem no relatório para o cliente."), "muted"), 0, Qt.AlignBottom)
        head.addStretch(1)
        self.known_lbl = lbl("", None)
        self.known_lbl.setStyleSheet(f"color: {OK};")
        head.addWidget(self.known_lbl)
        head.addSpacing(10)
        head.addWidget(btn(tr("Novo carro"), None, self.clear_vehicle))
        vl.addLayout(head)
        self.vehicle_edits = {}
        for key, name in self.VEHICLE_FIELDS:
            e = QLineEdit()
            e.setPlaceholderText(name)
            self.vehicle_edits[key] = e
        plate = self.vehicle_edits["plate"]
        plate.setMaxLength(12)
        plate.setObjectName("plateBig")
        plate.setPlaceholderText(tr("Matrícula"))
        self.vehicle_edits["vin"].setMaxLength(17)
        self.vehicle_edits["vin"].setPlaceholderText(tr("VIN (opcional)"))
        row = QHBoxLayout()
        row.setSpacing(16)
        pcol = QVBoxLayout()
        pcol.setSpacing(4)
        pcol.addWidget(lbl(tr("Matrícula"), "muted"))
        pcol.addWidget(plate)
        pcol.addStretch(1)
        row.addLayout(pcol, 2)
        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(4)
        for i, key in enumerate(("model", "km", "client", "vin")):
            name = dict(self.VEHICLE_FIELDS)[key]
            form.addWidget(lbl(name, "muted"), (i // 2) * 2, i % 2)
            form.addWidget(self.vehicle_edits[key], (i // 2) * 2 + 1, i % 2)
        form.setColumnStretch(0, 3)
        form.setColumnStretch(1, 2)
        row.addLayout(form, 5)
        vl.addLayout(row)
        cta = QHBoxLayout()
        go_scan = btn(tr("  Iniciar Auto-Scan"), "primary", lambda: self.go.emit("autoscan_start"))
        go_scan.setIcon(nav_icon("autoscan", "#0C0F14"))
        go_scan.setIconSize(QSize(20, 20))
        go_scan.setMinimumHeight(50)
        go_scan.setMinimumWidth(260)
        glow(go_scan, CYAN, 36, 120)
        cta.addWidget(go_scan)
        cta.addSpacing(10)
        cta.addWidget(lbl(tr("Lê todos os controladores e mostra as avarias de cada um."), "muted"))
        cta.addStretch(1)
        vl.addLayout(cta)
        # Carros já conhecidos (rad/vehicles.py): a matrícula completa-se enquanto se escreve e, ao sair do campo
        # da matrícula ou do VIN, os campos vazios enchem-se com os dados guardados.
        self.plate_model = QStringListModel(self)
        completer = QCompleter(self.plate_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        plate.setCompleter(completer)
        completer.activated.connect(lambda _t: self.fill_known("plate"))
        plate.editingFinished.connect(lambda: self.fill_known("plate"))
        self.vehicle_edits["vin"].editingFinished.connect(lambda: self.fill_known("vin"))
        v.addWidget(vc)

        # --- últimos carros: clicar num reabre-o (os dados voltam para cima)
        rc = card()
        rl = QVBoxLayout(rc)
        rl.setContentsMargins(22, 16, 22, 16)
        rh = QHBoxLayout()
        rh.addWidget(lbl(tr("Últimos carros"), "h2"))
        rh.addSpacing(12)
        rh.addWidget(lbl(tr("Clique num carro para o voltar a abrir."), "muted"), 0, Qt.AlignBottom)
        rh.addStretch(1)
        rh.addWidget(btn(tr("Histórico completo"), None, lambda: self.go.emit("history")))
        rl.addLayout(rh)
        self.recent = QListWidget()
        self.recent.setMinimumHeight(120)
        self.recent.setCursor(Qt.PointingHandCursor)
        self.recent.setStyleSheet(f"QListWidget {{ border: none; background: transparent; }}"
                                  f"QListWidget::item {{ border-bottom: 1px solid {LINE}; }}"
                                  "QListWidget::item:hover { background: rgba(111, 168, 255, 0.06); }"
                                  "QListWidget::item:selected { background: rgba(111, 168, 255, 0.10); }")
        self.recent.itemClicked.connect(self._open_recent)
        rl.addWidget(self.recent, 1)
        self.recent_empty = lbl(tr("Os diagnósticos guardados aparecem aqui."), "muted")
        rl.addWidget(self.recent_empty)
        rl.addStretch(0)
        v.addWidget(rc, 1)

    def refresh_stats(self):
        """Actualiza a lista de últimos carros a partir do histórico."""
        from ... import history
        try:
            sessions = history.list_sessions()
        except Exception:
            sessions = []
        self.recent.clear()
        seen = set()
        for s in sessions:
            key = s["plate"] or s["id"]
            if key in seen:
                continue
            seen.add(key)
            when = s["date"][8:10] + "/" + s["date"][5:7] + "  " + s["date"][11:16]
            if not s["modules"]:
                state, tone = tr("nenhum controlador lido"), MUTED
            elif s["faults"] == 0:
                state, tone = tr("sem avarias nos lidos"), OK
            else:
                state, tone = tr("{faults} avaria(s)", faults=s['faults']), (BAD if s["faults"] >= 5 else WARN)
            if s.get("simulated") == 1:
                state += tr("   ·   simulação")
            self._add_recent(s["plate"] or tr("Carro sem matrícula"),
                             " · ".join(x for x in (s["model"], s["client"]) if x), when, state, tone,
                             vehicle={"plate": s["plate"] or "", "model": s["model"] or "",
                                      "client": s["client"] or ""})
            if len(seen) >= 6:
                break
        self.recent.setVisible(bool(seen))
        self.recent_empty.setVisible(not seen)
        self.refresh_known()

    def _add_recent(self, plate, who, when, state, tone, vehicle=None):
        """Uma linha da lista de últimos carros: matrícula e modelo/cliente/data à esquerda, o estado em cor."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(4, 8, 4, 8)
        h.setSpacing(10)
        left = QVBoxLayout()
        left.setSpacing(1)
        top = lbl(plate, None)
        top.setStyleSheet("font-weight: 600; color: white;")
        left.addWidget(top)
        left.addWidget(lbl("   ·   ".join(x for x in (who, when) if x), "muted"))
        h.addLayout(left, 1)
        st = lbl(state, None)
        st.setStyleSheet(f"color: {tone};")
        h.addWidget(st, 0, Qt.AlignVCenter)
        row.setAttribute(Qt.WA_TransparentForMouseEvents)
        it = QListWidgetItem()
        it.setData(Qt.UserRole, f"{plate} {who} {state}")
        it.setData(Qt.UserRole + 1, vehicle or {})
        it.setSizeHint(row.sizeHint())
        self.recent.addItem(it)
        self.recent.setItemWidget(it, row)

    def _open_recent(self, item):
        """Reabre um carro da lista: os dados voltam para "Carro na oficina" (os guardados completam o resto)."""
        vehicle = item.data(Qt.UserRole + 1) or {}
        if not vehicle:
            return
        self.clear_vehicle()
        self.set_vehicle(vehicle)
        if vehicle.get("plate"):
            self.fill_known("plate")
        self.vehicle_edits["plate"].setFocus()

    def set_interface(self, text):
        self.link_iface.setText(text)

    def set_link(self, status):
        """status: connstate.LinkStatus emitido pela thread de comunicação."""
        tone = {connstate.ECU_CONNECTED: OK, connstate.CONNECTING: WARN, connstate.OPEN_NO_ECU: BLUE,
                connstate.UNREACHABLE: BAD, connstate.ERROR: BAD}.get(status.state, MUTED)
        self.link_pill.setText(status.label)
        self.link_pill.setStyleSheet(pill_style(tone))
        self.link_detail.setText(client_text(status.message))
        self.status_bar.setToolTip(self.link_detail.text())

    def set_port(self, text, ok=False, sim=False):
        """Estado do cabo escolhido em Opções (ok = porta real escolhida; sim = simulador)."""
        self.status_lbl.setText(text)
        color = OK if ok else (CYAN if sim else MUTED)
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 9pt;")
        self.port_pill.setText(tr("escolhido") if ok else (tr("simulador") if sim else tr("por configurar")))
        self.port_pill.setStyleSheet(pill_style(color))
        self.sim_btn.setVisible(not sim)
        self.cable_btn.setVisible(not ok and not sim)          # sem cabo escolhido: o atalho para o configurar

    def vehicle(self):
        return {k: e.text().strip() for k, e in self.vehicle_edits.items()}

    def set_vehicle(self, vehicle):
        for k, e in self.vehicle_edits.items():
            value = str((vehicle or {}).get(k) or "")
            if e.text().strip() != value:
                e.setText(value)

    def clear_vehicle(self):
        for e in self.vehicle_edits.values():
            e.clear()
        self.known_lbl.setText("")

    def refresh_known(self):
        """Actualiza a lista de matrículas para completar o campo."""
        from ... import vehicles
        try:
            self.plate_model.setStringList(vehicles.plates())
        except Exception:
            self.plate_model.setStringList([])

    def fill_known(self, key):
        """Se a matrícula ou o VIN já são conhecidos, completa os campos vazios. Devolve o veículo (ou None)."""
        from ... import vehicles
        text = self.vehicle_edits[key].text().strip()
        if not text:
            self.known_lbl.setText("")
            return None
        try:
            known = vehicles.lookup(plate=text) if key == "plate" else vehicles.lookup(vin=text)
        except Exception:
            known = None
        if not known:
            self.known_lbl.setText("")
            return None
        for k, e in self.vehicle_edits.items():
            if not e.text().strip() and known.get(k):
                e.setText(str(known[k]))
        last = str(known.get("last") or "")[:10]
        self.known_lbl.setText(tr("Cliente conhecido · {n} visita(s) · última em {date}",
                                  n=known.get("visits") or 0, date=f"{last[8:10]}/{last[5:7]}/{last[:4]}"))
        return known


# ------------------------------------------------------- selecção de módulo
