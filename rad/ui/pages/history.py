"""Histórico: os carros que passaram pela oficina (à esquerda) e as visitas do carro escolhido (à direita).

Antes eram duas tabelas soltas (Diagnósticos e Veículos). Agora escolhe-se o carro e vê-se tudo dele: os dados, as
visitas, e os controladores e as avarias da visita seleccionada. Apagar fica no menu ⋯ (raramente se usa)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QMessageBox, QSplitter, QTableWidget, QTableWidgetItem, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from ... import APP_NAME, licensing
from ..style import BAD, CYAN, MUTED, OK, WARN, pill_style
from .common import lbl, btn, card, ask
from ...i18n import tr

NO_PLATE = "\x00"                 # chave do grupo das visitas guardadas sem matrícula


class _CarRow(QWidget):
    """Linha da lista de carros: matrícula e avarias da última visita; por baixo o modelo e o cliente."""

    def __init__(self, car):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        plate = lbl(car["plate"] or tr("Sem matrícula"), None)
        plate.setStyleSheet("font-weight: 700; font-size: 11.5pt;")
        top.addWidget(plate)
        top.addStretch(1)
        n = car["faults"]
        pill = lbl(tr("sem avarias") if n == 0 else tr("{n} avaria(s)", n=n), "pill")
        pill.setStyleSheet(pill_style(OK if n == 0 else WARN))
        top.addWidget(pill)
        v.addLayout(top)
        sub = " · ".join(x for x in (car["model"], car["client"]) if x) or tr("{n} visita(s)", n=car["visits"])
        v.addWidget(lbl(sub, "muted"))
        for w in self.findChildren(QWidget):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)


class HistoryPage(QWidget):
    report_req = Signal(object)
    vehicle_req = Signal(dict)            # usar este veículo no diagnóstico (preenche os dados no Início)

    # traduzidas ao importar: o idioma é escolhido antes de criar a janela (main.py)
    COLS = [tr("Data"), tr("Tipo"), tr("Controladores"), tr("Avarias"), tr("Origem")]
    ORIGIN = {1: tr("Simulação"), 0: tr("Carro"), None: "—"}   # None: gravado antes da v1.3 (desconhecido)

    def __init__(self):
        super().__init__()
        from ... import history
        self.history = history
        self.sessions = []
        self.cars = []                    # grupos por matrícula, os mais recentes primeiro
        self.visits = []                  # visitas do carro escolhido
        v = QVBoxLayout(self)
        v.setContentsMargins(32, 26, 32, 24)
        v.setSpacing(14)
        v.addWidget(lbl(tr("Histórico"), "h1"))

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        v.addWidget(split, 1)

        # --- esquerda: procurar e escolher o carro
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 8, 0)
        lv.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Procurar matrícula, VIN, cliente ou modelo"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill)
        lv.addWidget(self.search)
        self.car_list = QListWidget()
        self.car_list.setSpacing(2)
        self.car_list.currentRowChanged.connect(self._car_selected)
        self.car_list.itemDoubleClicked.connect(lambda *_: self._use_vehicle())
        lv.addWidget(self.car_list, 1)
        self.count_lbl = lbl("", "muted")
        lv.addWidget(self.count_lbl)
        split.addWidget(left)

        # --- direita: o carro, as visitas e a visita seleccionada
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)
        rv.setSpacing(12)
        head = card()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(20, 14, 16, 14)
        hl.setSpacing(10)
        hv = QVBoxLayout()
        hv.setSpacing(2)
        self.car_title = lbl("—", "h1")
        self.car_title.setStyleSheet("font-size: 19pt;")
        self.car_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.car_sub = lbl("", "muted", wrap=True)
        self.car_sub.setTextInteractionFlags(Qt.TextSelectableByMouse)
        hv.addWidget(self.car_title)
        hv.addWidget(self.car_sub)
        hl.addLayout(hv, 1)
        self.use_btn = btn(tr("Usar no diagnóstico"), "primary", self._use_vehicle)
        self.use_btn.setToolTip(tr("Preenche os dados deste carro no Início."))
        hl.addWidget(self.use_btn, 0, Qt.AlignVCenter)
        rv.addWidget(head)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(lbl(tr("Visitas"), "h2"))
        bar.addStretch(1)
        self.report_btn = btn(tr("Relatório"), None, self._report)
        self.compare_btn = btn(tr("Comparar com a anterior"), None, self._compare)
        bar.addWidget(self.report_btn)
        bar.addWidget(self.compare_btn)
        more = QToolButton()
        more.setText(tr("Mais") + "  ▾")
        more.setPopupMode(QToolButton.InstantPopup)
        more.setCursor(Qt.PointingHandCursor)
        more.setStyleSheet("QToolButton { padding: 8px 14px; border: 1px solid #2A2E38; border-radius: 9px; "
                           "background: #1B1E26; font-weight: 600; } QToolButton:hover { border-color: #3D7BFF; } "
                           "QToolButton::menu-indicator { image: none; }")
        menu = QMenu(more)
        menu.addAction(tr("Apagar esta visita…"), self._delete)
        menu.addAction(tr("Abrir pasta do histórico"), self._open_dir)
        more.setMenu(menu)
        bar.addWidget(more)
        rv.addLayout(bar)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        hh = self.table.horizontalHeader()
        for i in range(len(self.COLS)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self._show_detail)
        self.table.cellDoubleClicked.connect(lambda *_: self._report())
        self.table.setMaximumHeight(210)
        rv.addWidget(self.table, 2)
        self.detail_lbl = lbl(tr("Controladores e avarias desta visita"), "cellName")
        rv.addWidget(self.detail_lbl)
        self.detail = QTreeWidget()
        self.detail.setHeaderLabels([tr("Endereço"), tr("Controlador / avaria"), tr("Estado")])
        self.detail.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.detail.header().setSectionResizeMode(1, QHeaderView.Stretch)
        rv.addWidget(self.detail, 3)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 5)
        split.setSizes([330, 820])
        self.right = right

        self.empty = QFrame()
        self.empty.setObjectName("card")
        el = QVBoxLayout(self.empty)
        el.setContentsMargins(24, 22, 24, 22)
        el.addWidget(lbl(tr("Ainda não há diagnósticos guardados"), "h2"))
        el.addWidget(lbl(tr("Faça um Auto-Scan a partir do Início: cada visita fica guardada aqui, com o carro, as "
                            "avarias e o relatório."), "muted", wrap=True))
        v.addWidget(self.empty)
        self.empty.hide()

    # ------------------------------------------------------------------ dados
    def refresh(self):
        try:
            self.sessions = self.history.list_sessions()
        except Exception:
            self.sessions = []
        self._fill()

    def _vehicles(self):
        """Registo de veículos por matrícula (VIN e quilómetros, que as sessões não guardam na lista)."""
        from ... import vehicles
        try:
            return {self.history.plate_key(v["plate"]): v for v in vehicles.search(limit=5000) if v.get("plate")}
        except Exception:
            return {}

    def _group(self):
        regs = self._vehicles()
        groups = {}
        for s in self.sessions:                       # já vêm das mais recentes para as mais antigas
            key = self.history.plate_key(s["plate"]) or NO_PLATE
            g = groups.get(key)
            if g is None:
                reg = regs.get(key, {})
                g = groups[key] = {"key": key, "plate": s["plate"] or "", "model": s["model"] or reg.get("model") or "",
                                   "client": s["client"] or reg.get("client") or "", "vin": reg.get("vin") or "",
                                   "km": reg.get("km") or "", "faults": s["faults"], "last": s["date"],
                                   "sessions": []}
            g["sessions"].append(s)
            g["model"] = g["model"] or s["model"] or ""
            g["client"] = g["client"] or s["client"] or ""
        for g in groups.values():
            g["visits"] = len(g["sessions"])
        return list(groups.values())

    def _visible_cars(self):
        q = self.search.text().strip().lower()
        cars = self._group()
        if not q:
            return cars
        qk = self.history.plate_key(q)
        return [c for c in cars
                if q in f"{c['plate']} {c['client']} {c['model']} {c['vin']}".lower()
                or (qk and len(qk) >= 2 and qk in c["key"])]

    def _fill(self, *_):
        current = self._current_car()
        keep = current["key"] if current else None
        self.cars = self._visible_cars()
        self.car_list.blockSignals(True)
        self.car_list.clear()
        for car in self.cars:
            it = QListWidgetItem()
            row = _CarRow(car)
            it.setSizeHint(row.sizeHint())
            it.setData(Qt.UserRole, car["key"])
            self.car_list.addItem(it)
            self.car_list.setItemWidget(it, row)
        self.car_list.blockSignals(False)
        has_any = bool(self.sessions)
        self.empty.setVisible(not has_any)
        self.right.setEnabled(bool(self.cars))
        self.count_lbl.setText(tr("{n} carro(s)", n=len(self.cars)) if has_any else "")
        idx = next((i for i, c in enumerate(self.cars) if c["key"] == keep), 0)
        if self.cars:
            self.car_list.setCurrentRow(idx)
            self._car_selected(idx)
        else:
            self._car_selected(-1)

    def _current_car(self):
        r = self.car_list.currentRow() if hasattr(self, "car_list") else -1
        return self.cars[r] if 0 <= r < len(self.cars) else None

    def _car_selected(self, _row=None):
        car = self._current_car()
        self.table.setRowCount(0)
        self.detail.clear()
        self.visits = car["sessions"] if car else []
        if car is None:
            self.car_title.setText("—")
            self.car_sub.setText(tr("Nenhum carro encontrado.") if self.sessions else "")
            return
        self.car_title.setText(car["plate"] or tr("Sem matrícula"))
        parts = [car["model"], car["client"]]
        if car["vin"]:
            parts.append(f"VIN {car['vin']}")
        if car["km"]:
            parts.append(tr("{km} km", km=car["km"]))
        parts.append(tr("{n} visita(s)", n=car["visits"]))
        self.car_sub.setText("  ·  ".join(p for p in parts if p))
        self.use_btn.setEnabled(car["key"] != NO_PLATE)
        for s in self.visits:
            r = self.table.rowCount()
            self.table.insertRow(r)
            kind = {"autoscan": "Auto-Scan", "obd": "OBD"}.get(s["kind"], tr("Controlador"))
            origin = s.get("simulated")
            vals = [s["date"].replace("T", "  ")[:17], kind, str(s["modules"]),
                    tr("sem avarias") if s["faults"] == 0 else str(s["faults"]), self.ORIGIN.get(origin, "—")]
            for c, t in enumerate(vals):
                it = QTableWidgetItem(t)
                if c == 0:
                    it.setData(Qt.UserRole, s["id"])
                if c == 3:
                    it.setForeground(QBrush(QColor(OK if s["faults"] == 0 else WARN)))
                if c == 4:
                    it.setForeground(QBrush(QColor(WARN if origin == 1 else MUTED)))
                    if origin is None:
                        it.setToolTip(tr("Sessão gravada por uma versão anterior, que não registava o equipamento: "
                                         "não se sabe se veio do simulador ou do carro."))
                self.table.setItem(r, c, it)
        if self.visits:
            self.table.selectRow(0)          # a última visita aberta: a lista de avarias por baixo nunca fica vazia
        self.compare_btn.setEnabled(len(self.visits) > 1)

    def select_session(self, sid):
        """Mostra o carro e a visita com este id (limpa a pesquisa se for preciso)."""
        for _ in range(2):
            for ci, car in enumerate(self.cars):
                for ri, s in enumerate(car["sessions"]):
                    if s["id"] == sid:
                        self.car_list.setCurrentRow(ci)
                        self.table.selectRow(ri)
                        return True
            self.search.clear()
        return False

    def _selected_id(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        it = self.table.item(r, 0)
        return it.data(Qt.UserRole) if it else None

    @staticmethod
    def full_access():
        """Substituída pela janela (Worker.full_access): sem licença, as avarias acima do limite ficam ocultas."""
        return True

    def _show_detail(self):
        sid = self._selected_id()
        self.detail.clear()
        if not sid:
            return
        try:
            data = self.history.load_session(sid)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, tr("Não foi possível abrir o registo: {e}", e=e))
            return
        items = data.get("items", [])
        if not self.full_access() and not (data.get("meta") or {}).get("simulated"):
            items = licensing.redact_items(items)     # modo demonstração: as mesmas avarias que o ecrã mostrou
        # os controladores com avarias primeiro: é o que a oficina procura
        items = sorted(items, key=lambda i: (i.get("status") != "error" and not i.get("faults"), i["address"]))
        for item in items:
            top = QTreeWidgetItem([f"{item['address']:02X}", item.get("module", ""), ""])
            if item.get("status") == "ok":
                n = len(item.get("faults", []))
                top.setText(2, tr("sem avarias") if n == 0 else tr("{n} avaria(s)", n=n))
                top.setForeground(2, QBrush(QColor(OK if n == 0 else WARN)))
                for f in item.get("faults", []):
                    elab = f"  —  {f['elab']}" if f.get("elab") not in ("-", "", None) else ""
                    QTreeWidgetItem(top, ["", f"{f['vag']}  {f['desc']}{elab}",
                                          tr("Intermitente") if f.get("intermittent") else ""])
            else:
                top.setText(2, tr("Erro"))
                top.setForeground(2, QBrush(QColor(BAD)))
            self.detail.addTopLevelItem(top)
            top.setExpanded(bool(item.get("faults")))      # só se pode abrir depois de estar na árvore

    # ------------------------------------------------------------------ acções
    def _use_vehicle(self):
        car = self._current_car()
        if car is None or car["key"] == NO_PLATE:
            QMessageBox.information(self, APP_NAME, tr("Escolha um carro da lista."))
            return
        self.vehicle_req.emit({"plate": car["plate"], "vin": car["vin"], "client": car["client"],
                               "model": car["model"], "km": str(car["km"] or "")})

    def _report(self):
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, APP_NAME, tr("Escolha uma visita da lista."))
            return
        self.report_req.emit(self.history.load_session(sid))

    def compare_text(self, sid):
        """Texto (HTML) com o que mudou entre esta sessão e a anterior do mesmo veículo, ou None."""
        data = self.history.load_session(sid)
        plate = data.get("vehicle", {}).get("plate", "")
        prev = self.history.previous_for_plate(plate, before=sid)
        if prev is None:
            return None
        diff = self.history.compare(prev.get("items", []), data.get("items", []))

        from html import escape

        def block(title, color, faults):
            if not faults:
                return f"<p><b style='color:{color}'>{title}: 0</b></p>"
            rows = "".join(f"<li><b>{f['address']:02X}</b> {escape(str(f.get('vag', '')))} — "
                           f"{escape(str(f.get('desc', '')))}</li>" for f in faults)
            return f"<p><b style='color:{color}'>{title}: {len(faults)}</b></p><ul>{rows}</ul>"

        d0, d1 = prev["date"], data["date"]
        head = (tr("<p><b>{v}</b>: visita de {v2}/{v3}/{v4} comparada com {v5}/{v6}/{v7}.<br><span "
                   "style='color:{MUTED}'>Só entram os controladores lidos nas duas visitas.</span></p>",
                   v=escape(plate), v2=d1[8:10], v3=d1[5:7], v4=d1[:4], v5=d0[8:10], v6=d0[5:7], v7=d0[:4],
                   MUTED=MUTED))
        return (head + block(tr("Novas"), CYAN, diff["new"]) + block(tr("Resolvidas"), OK, diff["resolved"])
                + block(tr("Mantêm-se"), WARN, diff["persisting"]))

    def _compare(self):
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, APP_NAME, tr("Escolha uma visita da lista."))
            return
        try:
            text = self.compare_text(sid)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, tr("Não foi possível comparar: {e}", e=e))
            return
        if text is None:
            QMessageBox.information(self, APP_NAME, tr("Não há uma visita anterior com a mesma matrícula para "
                                                       "comparar."))
            return
        box = QMessageBox(self)
        box.setWindowTitle(tr("Comparar com a visita anterior"))
        box.setTextFormat(Qt.RichText)
        box.setText(text)
        box.exec()

    def _delete(self):
        sid = self._selected_id()
        if sid and ask(self, APP_NAME, tr("Apagar esta visita do histórico? Não se pode desfazer.")):
            self.history.delete_session(sid)
            self.refresh()

    def _open_dir(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.history.history_dir()))
