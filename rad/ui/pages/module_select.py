"""Escolha do controlador a ligar.

Um só campo: escreve-se o endereço (01, 17…) ou parte do nome (motor, abs…) — a lista filtra enquanto se escreve e
Enter abre. Depois de um Auto-Scan, os controladores que responderam aparecem em cartões no topo ("Neste carro"),
com as avarias de cada um; os outros ficam numa lista compacta, arrumada por sistema do carro."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ... import vag_data, APP_NAME
from ..style import BAD, DISPLAY_FONT, LINE, OK, WARN, pill_style
from .common import btn, lbl
from ...i18n import tr

CARD_COLUMNS = 4
GROUP_COLUMNS = 3

# sistemas do carro (endereços VAG); um controlador que não esteja em nenhum vai para o último
SYSTEMS = [
    (tr("Motor e transmissão"), [0x01, 0x02, 0x11, 0x22, 0x41, 0x18, 0x61]),
    (tr("Travões, direcção e suspensão"), [0x03, 0x44, 0x53, 0x65, 0x14, 0x16, 0x34, 0x13]),
    (tr("Segurança e acesso"), [0x15, 0x25, 0x35, 0x05, 0x45]),
    (tr("Conforto e carroçaria"), [0x08, 0x09, 0x46, 0x76, 0x55, 0x29, 0x39, 0x26, 0x36, 0x06, 0x52, 0x62, 0x72,
                                   0x69]),
    (tr("Painel, som e comunicação"), [0x17, 0x19, 0x56, 0x37, 0x47, 0x07, 0x57, 0x67, 0x75, 0x77]),
]


class ModuleCard(QPushButton):
    """Cartão de um controlador que respondeu no Auto-Scan: endereço em grande, nome e estado."""

    def __init__(self, addr):
        super().__init__()
        self.setObjectName("module")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(104)
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(4)
        a = lbl(f"{addr:02X}", None)
        a.setStyleSheet(f"font-family: {DISPLAY_FONT}; font-size: 18pt; font-weight: 700; color: white;")
        v.addWidget(a)
        name = lbl(vag_data.module_name(addr), None, wrap=True)
        v.addWidget(name)
        self.pill = lbl("", "pill")
        v.addWidget(self.pill, 0, Qt.AlignLeft)
        for w in (a, name, self.pill):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_state(self, color, tag):
        self.pill.setText(tag)
        self.pill.setStyleSheet(pill_style(color))
        self.setStyleSheet(f"QPushButton#module {{ border: 1px solid {color if color != OK else LINE}; }}")


class ModuleSelectPage(QWidget):
    connect_req = Signal(int)

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(32, 26, 32, 24)
        v.setSpacing(16)
        v.addWidget(lbl(tr("Controladores"), "h1"))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("Endereço ou nome — ex.: 01, motor, abs, 17"))
        self.filter.setClearButtonEnabled(True)
        self.filter.setMinimumHeight(42)
        self.filter.textChanged.connect(self._filter)
        self.filter.returnPressed.connect(self._go_manual)
        self.addr = self.filter                       # compatibilidade: antes havia dois campos
        row.addWidget(self.filter, 1)
        open_btn = btn(tr("Abrir"), "primary", self._go_manual)
        open_btn.setMinimumHeight(42)
        row.addWidget(open_btn)
        v.addLayout(row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(16)

        # --- neste carro (depois de um Auto-Scan)
        self.in_car_box = QWidget()
        iv = QVBoxLayout(self.in_car_box)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(10)
        ih = QHBoxLayout()
        ih.addWidget(lbl(tr("Neste carro"), "h2"))
        ih.addSpacing(10)
        self.in_car_lbl = lbl("", "muted")
        ih.addWidget(self.in_car_lbl, 0, Qt.AlignBottom)
        ih.addStretch(1)
        iv.addLayout(ih)
        self.card_grid = QGridLayout()
        self.card_grid.setSpacing(12)
        for c in range(CARD_COLUMNS):
            self.card_grid.setColumnStretch(c, 1)
        iv.addLayout(self.card_grid)
        lay.addWidget(self.in_car_box)

        # --- os outros, em lista compacta por sistema
        self.others = QFrame()
        self.others.setObjectName("card")
        ov = QVBoxLayout(self.others)
        ov.setContentsMargins(16, 14, 16, 14)
        ov.setSpacing(6)
        oh = QHBoxLayout()
        self.others_title = lbl(tr("Todos os controladores"), "h2")
        oh.addWidget(self.others_title)
        oh.addStretch(1)
        self.others_lbl = lbl(tr("os que o carro pode ter"), "muted")
        oh.addWidget(self.others_lbl)
        ov.addLayout(oh)
        self.group_grid = QGridLayout()
        self.group_grid.setHorizontalSpacing(18)
        self.group_grid.setVerticalSpacing(10)
        for c in range(GROUP_COLUMNS):
            self.group_grid.setColumnStretch(c, 1)
        ov.addLayout(self.group_grid)
        lay.addWidget(self.others)
        self.no_match = lbl(tr("Nenhum controlador com esse endereço ou nome."), "muted")
        self.no_match.hide()
        lay.addWidget(self.no_match)
        lay.addStretch(1)
        scroll.setWidget(inner)
        v.addWidget(scroll, 1)

        known = {a for _t, addrs in SYSTEMS for a in addrs}
        systems = [(t, [a for a in addrs if a in vag_data.VAG_MODULES]) for t, addrs in SYSTEMS]
        systems[-1][1].extend(a for a in sorted(vag_data.VAG_MODULES) if a not in known)
        self.order = [a for _t, addrs in systems for a in addrs]
        self.mod_btns = {}                 # linha da lista compacta de cada controlador
        self.cards = {}                    # cartão de cada controlador (só aparece se respondeu no Auto-Scan)
        self.groups = []                   # (caixa, título, endereços)
        for i, (title, addrs) in enumerate(systems):
            box = QWidget()
            bv = QVBoxLayout(box)
            bv.setContentsMargins(0, 0, 0, 0)
            bv.setSpacing(0)
            head = lbl(title.upper(), "cellName")
            head.setContentsMargins(10, 6, 0, 4)
            bv.addWidget(head)
            for addr in addrs:
                b = btn(self._label(addr), "ghost", lambda _=False, a=addr: self.connect_req.emit(a))
                b.setStyleSheet("QPushButton#ghost { text-align: left; padding: 7px 10px; font-weight: 500; "
                                "color: #C9CED9; }")
                b.setToolTip(tr("Ligar ao controlador {addr:02X} — {name}", addr=addr,
                                name=vag_data.module_name(addr)))
                bv.addWidget(b)
                self.mod_btns[addr] = b
                c = ModuleCard(addr)
                c.setParent(self.in_car_box)       # nunca fica solto (um widget sem pai abriria como janela)
                c.hide()
                c.clicked.connect(lambda _=False, a=addr: self.connect_req.emit(a))
                c.setToolTip(b.toolTip())
                self.cards[addr] = c
            bv.addStretch(1)
            self.groups.append((box, addrs))
            self.group_grid.addWidget(box, i // GROUP_COLUMNS, i % GROUP_COLUMNS, Qt.AlignTop)
        self.scan = {}                     # endereço → (cor, etiqueta) do último Auto-Scan (só os que responderam)
        self.scan_note = ""
        self._place()

    @staticmethod
    def _label(addr):
        return f"{addr:02X}    {vag_data.module_name(addr)}"

    def _matches(self, addr):
        q = self.filter.text().strip().lower()
        return not q or q in f"{addr:02x} {vag_data.module_name(addr)} {vag_data.VAG_MODULES[addr]}".lower()

    def _place(self):
        """Os que responderam no Auto-Scan em cartões ("Neste carro"), os outros na lista; o filtro esconde os
        que não interessam."""
        while self.card_grid.count():
            self.card_grid.takeAt(0)
        in_car = [a for a in self.order if a in self.scan]
        # os com avarias primeiro (é por aí que se continua o diagnóstico)
        in_car.sort(key=lambda a: (self.scan[a][0] == OK, self.order.index(a)))
        shown = [a for a in in_car if self._matches(a)]
        for n, a in enumerate(shown):
            self.card_grid.addWidget(self.cards[a], n // CARD_COLUMNS, n % CARD_COLUMNS)
        for a, c in self.cards.items():
            c.setVisible(a in shown)
        self.in_car_box.setVisible(bool(shown))
        self.in_car_lbl.setText(self.scan_note)
        any_other = False
        for box, addrs in self.groups:
            vis = [a for a in addrs if a not in self.scan and self._matches(a)]
            for a in addrs:
                self.mod_btns[a].setVisible(a in vis)
            box.setVisible(bool(vis))
            any_other = any_other or bool(vis)
        self.others.setVisible(any_other)
        self.others_title.setText(tr("Outros controladores") if self.scan else tr("Todos os controladores"))
        self.no_match.setVisible(not shown and not any_other)

    def _filter(self, _text):
        self._place()

    def mark_scan(self, items):
        """Mostra o resultado do último Auto-Scan: os controladores que responderam passam para "Neste carro"."""
        self.scan = {}
        for it in items:
            addr = it["address"]
            if addr not in self.mod_btns or it.get("status") not in ("ok", "error"):
                continue
            if it["status"] == "ok":
                n = len(it.get("faults", []))
                color, tag = (OK, tr("sem avarias")) if n == 0 else (WARN, tr("{n} avaria(s)", n=n))
            else:
                color, tag = BAD, tr("erro")
            self.scan[addr] = (color, tag)
            self.cards[addr].set_state(color, tag)
        self.scan_note = tr("último Auto-Scan · {n} controlador(es)", n=len(self.scan)) if self.scan else ""
        self._place()

    def _go_manual(self):
        """Enter / Abrir: um endereço válido liga logo; um nome que só corresponde a um controlador também."""
        text = self.filter.text().strip()
        if not text:
            QMessageBox.information(self, APP_NAME, tr("Escreva o endereço (ex.: 01) ou parte do nome (ex.: motor)."))
            return
        if len(text) <= 2:
            try:
                a = int(text, 16)
            except ValueError:
                a = None
            if a is not None:
                if 0 < a < 0x80:
                    self.connect_req.emit(a)
                    return
                if not any(self._matches(x) for x in self.order):
                    QMessageBox.warning(self, APP_NAME, tr("O endereço tem de estar entre 01 e 7F."))
                    return
        matches = [a for a in self.order if self._matches(a)]
        if len(matches) == 1:
            self.connect_req.emit(matches[0])
        elif not matches:
            QMessageBox.warning(self, APP_NAME, tr("Nenhum controlador com esse endereço ou nome. Exemplos: 01, 17, "
                                                   "46, motor, abs."))
        else:
            QMessageBox.information(self, APP_NAME, tr("Há {n} controladores com esse nome: escolha um na lista.",
                                                       n=len(matches)))
