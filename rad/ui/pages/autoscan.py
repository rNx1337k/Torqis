"""Auto-Scan: lê todos os controladores e mostra só as avarias, agrupadas por controlador; os que não têm avarias
ficam numa linha. A pontuação de saúde do veículo fica no relatório para o cliente."""
import datetime
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QMessageBox, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from ... import fault_advice, licensing, vag_data, APP_NAME, VERSION
from ..style import BAD, CYAN, MUTED, OK, WARN, severity_color
from .common import FaultAdviceCard, lbl, btn, ask
from ...errors import client_text
from ...i18n import tr, tr_data
from ...kline import port_label


class AutoScanPage(QWidget):
    connect_req = Signal(int)
    report_req = Signal()

    def __init__(self, worker):
        super().__init__()
        self.w = worker
        self.items = []
        self.diff = None
        self.meta = {}                     # interface, simulação e cobertura do último Auto-Scan
        self.session_id = None             # sessão do histórico onde ficou gravado
        self.addresses = list(vag_data.AUTOSCAN_ADDRESSES)
        v = QVBoxLayout(self)
        v.setContentsMargins(30, 24, 30, 20)
        v.setSpacing(12)
        # cabeçalho: o título e, por baixo, o resumo ("AA-00-AA · 3 avarias em 2 controladores")
        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(lbl(tr("Auto-Scan"), "h1"))
        srow = QHBoxLayout()
        srow.setSpacing(12)
        self.summary = lbl(tr("Lê a identificação e as avarias de todos os controladores."), "muted", wrap=True)
        srow.addWidget(self.summary, 1)
        self.severity_lbl = lbl("", None)
        srow.addWidget(self.severity_lbl)
        head.addLayout(srow)
        v.addLayout(head)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.start_btn = btn(tr("▶  Iniciar Auto-Scan"), "primary", self._toggle)
        self.start_btn.setMinimumHeight(40)
        row.addWidget(self.start_btn)
        self.clear_all_btn = btn(tr("Apagar avarias"), "danger", self._clear_all)
        self.clear_all_btn.setToolTip(tr("Apaga as avarias em todos os controladores que as têm"))
        row.addWidget(self.clear_all_btn)
        row.addWidget(btn(tr("Relatório para o cliente"), None, lambda: self.report_req.emit()))
        row.addStretch(1)
        v.addLayout(row)

        prow = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(8)
        self.progress.hide()                       # só durante a leitura
        prow.addWidget(self.progress, 1)
        self.current = lbl("", "muted")
        self.current.setMinimumWidth(240)
        self.current.hide()
        prow.addWidget(self.current)
        v.addLayout(prow)

        self.banner = QFrame()
        self.banner.setObjectName("banner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(14, 10, 14, 10)
        self.banner_lbl = lbl("", None, wrap=True)
        self.banner_lbl.setTextFormat(Qt.RichText)
        bl.addWidget(self.banner_lbl, 1)
        self.banner.hide()
        v.addWidget(self.banner)

        self.empty = lbl(tr("Ainda não há resultados. Ligue a ignição e carregue em Iniciar Auto-Scan."), "muted")
        v.addWidget(self.empty)
        # só os controladores com avarias (ou sem comunicação), cada um com as suas avarias por baixo
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("Endereço"), tr("Controlador / avaria"), tr("Estado")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.setToolTip(tr("Duas vezes num controlador para o abrir."))
        self.tree.itemSelectionChanged.connect(self._show_advice)
        self.tree.itemDoubleClicked.connect(self._open_from_tree)
        self.tree.setMinimumHeight(200)
        self.tree.hide()
        v.addWidget(self.tree, 5)
        # os controladores sem avarias, numa linha
        self.ok_lbl = lbl("", "muted", wrap=True)
        self.ok_lbl.hide()
        v.addWidget(self.ok_lbl)
        self.advice = FaultAdviceCard(tr("Seleccione uma avaria na lista para ver as causas prováveis."))
        self.advice.setMaximumHeight(330)         # a lista das avarias fica com o resto (o texto rola no cartão)
        v.addWidget(self.advice, 3)
        self.advice.hide()
        self.ok_modules = []
        self.running = False

    # ------------------------------------------------------------- acções
    def _clear_all(self):
        addrs = [i["address"] for i in self.items if i.get("status") == "ok" and i.get("faults")]
        if self.running:
            return
        if not addrs:
            QMessageBox.information(self, APP_NAME, tr("Não há avarias para apagar. Faça primeiro um Auto-Scan."))
            return
        names = ", ".join(f"{a:02X}" for a in addrs)
        if not ask(self, APP_NAME, tr("Apagar a memória de avarias em {v} controlador(es) ({names})?\n\nRecomenda-se "
                                      "gravar ou imprimir o relatório antes.",
                                      v=len(addrs), names=names)):
            return
        self.clear_all_btn.setEnabled(False)
        self.current.show()
        self.current.setText(tr("A apagar avarias…"))
        self.w.submit("clear_all", addrs)

    def update_health(self):
        """A avaria mais grave, ao lado do resumo (a pontuação de saúde fica só no relatório)."""
        sev = fault_advice.worst_severity(self.items)
        if sev:
            self.severity_lbl.setText(tr("Avaria mais grave: {v}", v=tr_data(fault_advice.SEVERITY_SHORT[sev]).lower()))
            self.severity_lbl.setStyleSheet(f"color: {severity_color(sev)};")
        else:
            self.severity_lbl.setText("")

    def apply_clear_results(self, results):
        """Actualiza os resultados do Auto-Scan depois de apagar as avarias."""
        self.clear_all_btn.setEnabled(True)
        by_addr = {r["address"]: r for r in results}
        for it in self.items:
            r = by_addr.get(it["address"])
            if r and r["status"] == "ok":
                it["faults"] = r["faults"]
        self.rebuild()
        left = sum(len(r.get("faults", [])) for r in results if r["status"] == "ok")
        errs = sum(1 for r in results if r["status"] == "error")
        unknown = sum(1 for r in results if r["status"] == "unknown")
        self.current.show()
        self.current.setText(tr("Avarias apagadas") + (tr(" — {left} voltaram", left=left) if left else "")
                             + (tr(" — {errs} sem comunicação", errs=errs) if errs else "")
                             + (tr(" — {unknown} por confirmar", unknown=unknown) if unknown else ""))
        return left, errs, unknown

    def rebuild(self):
        items, self.items = self.items, []
        self._demo_free = licensing.FREE_FAULTS
        self.tree.clear()                  # não emite itemSelectionChanged: o assistente ficaria na avaria antiga
        self.advice.hide()
        self._reset_ok()
        total = max(self.progress.maximum(), 1)
        for it in items:
            self.on_progress(total, total, it)
        self._summarise()
        self.update_health()

    def _summarise(self, aborted=False):
        nf = sum(len(i.get("faults", [])) for i in self.items)
        with_faults = sum(1 for i in self.items if i.get("faults"))
        sim = any((i.get("info") or {}).get("simulated") for i in self.items)
        plate = (self.vehicle() or {}).get("plate", "").strip()
        if nf:
            text = tr("{nf} avaria(s) em {n} controlador(es)", nf=nf, n=with_faults)
        else:
            text = tr("Sem avarias")
        text += tr(" · {v} controlador(es) lido(s)", v=len(self.items))
        if plate:
            text = f"{plate}  ·  {text}"
        self.summary.setText(text + (tr("  (interrompido)") if aborted else "") + (tr("  · SIMULAÇÃO") if sim else ""))
        self.summary.setStyleSheet("font-weight: 600;" if self.items else "")
        if self.items and not self.running:
            self.start_btn.setText(tr("↻  Ler de novo"))

    @staticmethod
    def vehicle():
        """Substituída pela janela: os dados do carro da página Início (para a matrícula no resumo)."""
        return {}

    def _reset_ok(self):
        self.ok_modules = []
        self.ok_lbl.setText("")
        self.ok_lbl.hide()

    def _add_ok(self, item):
        self.ok_modules.append(f"{item['address']:02X} {item['module']}")
        self.ok_lbl.setText(tr("<b style='color:{c}'>Sem avarias:</b> {v}", c=OK, v=" · ".join(self.ok_modules)))
        self.ok_lbl.show()

    def _toggle(self):
        if self.running:
            self.w.abort_scan = True
            self.start_btn.setText(tr("A parar…"))
            return
        if self.w.is_busy:
            self.current.setText(tr("Aguarde — ainda a comunicar com o carro"))
            return
        self.items = []
        self._demo_free = licensing.FREE_FAULTS
        self.diff = None
        self.meta = {}
        self.session_id = None
        self.banner.hide()
        self.tree.clear()
        self.tree.hide()
        self._reset_ok()
        self.advice.hide()
        self.empty.hide()
        self.severity_lbl.setText("")
        self.progress.setValue(0)
        self.progress.show()
        self.current.show()
        self.summary.setText(tr("A ler os controladores…"))
        self.summary.setStyleSheet("")
        self.running = True
        self.start_btn.setText(tr("■  Parar"))
        self.w.submit("autoscan", self.addresses)

    def on_progress(self, i, total, item):
        self.progress.setMaximum(total)
        self.progress.setValue(i)
        self.current.setText(f"{i}/{total}  ·  {item['address']:02X} {item['module']}")
        if item["status"] == "absent":
            return
        if item.get("faults") and not self.w.full_access():
            # modo demonstração: só as primeiras avarias do carro inteiro ficam visíveis (relatório e histórico
            # também só recebem estas — o resto fica "avaria oculta", com a contagem e a gravidade certas)
            item = dict(item)
            item["faults"], self._demo_free = licensing.redact_faults(
                item["faults"], getattr(self, "_demo_free", licensing.FREE_FAULTS), item.get("address"))
        self.items.append(item)
        self._add_tree_item(item)

    def _fault_tag(self, address, f):
        if not self.diff:
            return ""
        if any(d["address"] == address and d.get("vag") == f.get("vag") for d in self.diff["new"]):
            return tr("NOVA")
        return ""

    def _add_tree_item(self, item):
        if item["status"] == "ok" and not item["faults"]:
            self._add_ok(item)                          # sem avarias: só o nome, na linha de baixo
            return
        self.tree.show()
        top = QTreeWidgetItem([f"{item['address']:02X}", "", ""])
        if item["status"] == "ok":
            info = item["info"]
            top.setText(1, f"{item['module']}  —  {info['part']}  {info['component']}")
            top.setToolTip(1, tr("Duas vezes para abrir este controlador"))
            n = len(item["faults"])
            top.setText(2, tr("OK") if n == 0 else tr("{n} avaria(s)", n=n))
            top.setForeground(2, QBrush(QColor(OK if n == 0 else WARN)))
            for f in item["faults"]:
                a = fault_advice.advice(f, item["address"])
                state = tr("Intermitente") if f["intermittent"] else a["severity_text"]
                tag = self._fault_tag(item["address"], f)
                elab = f"  —  {f['elab']}" if f["elab"] not in ("-", "") else ""
                child = QTreeWidgetItem(top, ["", f"{f['vag']}  {f['desc']}{elab}", f"{tag}  {state}".strip()])
                child.setForeground(2, QBrush(QColor(CYAN if tag else severity_color(a["severity"]))))
                child.setData(0, Qt.UserRole, (item["address"], f))
                child.setToolTip(1, tr("Seleccione para ver as causas prováveis"))
        else:
            top.setText(1, item["module"])
            top.setText(2, tr("Erro: ") + client_text(item.get("error", "")))
            top.setForeground(2, QBrush(QColor(BAD)))
        self.tree.addTopLevelItem(top)
        top.setExpanded(True)

    def _open_from_tree(self, item, _col=0):
        top = item.parent() or item
        try:
            self.connect_req.emit(int(top.text(0), 16))
        except ValueError:
            pass

    def _show_advice(self):
        it = self.tree.currentItem()
        data = it.data(0, Qt.UserRole) if it is not None else None
        if not data:
            self.advice.hide()
            return
        address, f = data
        self.advice.set_fault(f, address)
        self.advice.show()

    def _select_first_fault(self):
        """No fim, a primeira avaria fica escolhida: o assistente aparece logo com as causas prováveis."""
        if self.tree.currentItem() is not None:
            return
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top.childCount():
                self.tree.setCurrentItem(top.child(0))
                return

    def done(self, aborted, error=None):
        self.running = False
        self.progress.hide()
        self.update_health()
        self.current.setText("" if not aborted
                             else (tr("Não foi possível ler") if error else tr("Interrompido")))
        self.current.setVisible(bool(self.current.text()))
        if not self.items:
            self.empty.setText(error or tr("Nenhum controlador respondeu. Confirme a ignição, o cabo e a porta nas "
                                           "Opções."))
            self.empty.setWordWrap(True)
            self.empty.show()
        self.start_btn.setText(tr("▶  Iniciar Auto-Scan"))
        self._select_first_fault()
        if error and not self.items:
            self.summary.setText(tr("Sem comunicação — veja a explicação abaixo."))
        else:
            self._summarise(aborted)

    def show_compare(self, prev_date, diff):
        """Mostra o que mudou desde o último diagnóstico do mesmo veículo e marca as avarias novas."""
        self.diff = diff
        when = f"{prev_date[8:10]}/{prev_date[5:7]}/{prev_date[0:4]}" if prev_date else tr("a última visita")
        n_new, n_res, n_keep = len(diff["new"]), len(diff["resolved"]), len(diff["persisting"])
        if not (n_new or n_res or n_keep):
            text = tr("Desde {when}: sem avarias em nenhum dos diagnósticos.", when=when)
        else:
            parts = []
            parts.append(tr("<b style='color:{v}'>{n_new} nova(s)</b>", v=CYAN if n_new else MUTED, n_new=n_new))
            parts.append(tr("<b style='color:{v}'>{n_res} resolvida(s)</b>", v=OK if n_res else MUTED, n_res=n_res))
            parts.append(tr("<b style='color:{v}'>{n_keep} mantêm-se</b>", v=WARN if n_keep else MUTED, n_keep=n_keep))
            text = tr("Comparação com a visita de <b>{when}</b>:", when=when) + "&nbsp;&nbsp;" \
                + "&nbsp;·&nbsp;".join(parts)
            if n_res:
                text += tr("<br><span style='color:%s'>Resolvidas: %s</span>") % (
                    MUTED, ", ".join(f"{r['address']:02X} {r['vag']}" for r in diff["resolved"][:6]))
        self.banner_lbl.setText(text)
        self.banner.show()
        # marcar as avarias novas na lista
        self.tree.clear()
        self._reset_ok()
        for it in self.items:
            self._add_tree_item(it)

    # ------------------------------------------------------------ relatório
    def report(self):
        lines = [tr("{APP_NAME} v{VERSION} — Auto-Scan {v:%d/%m/%Y %H:%M}",
                    APP_NAME=APP_NAME, VERSION=VERSION, v=datetime.datetime.now())]
        if self.meta.get("interface"):
            lines.append(tr("Interface: {interface}", interface=port_label(self.meta['interface'])))
        if self.meta.get("simulated") or any((i.get("info") or {}).get("simulated") for i in self.items):
            lines.append(tr("*** DADOS SIMULADOS — não correspondem a nenhum veículo real ***"))
        if self.meta.get("aborted"):
            lines.append(tr("Auto-Scan interrompido: {v} de {v2} controladores verificados (resultado parcial)",
                            v=self.meta.get('scanned'), v2=self.meta.get('total')))
        lines.append("-" * 60)
        for it in self.items:
            lines.append(tr("Endereço {address:02X}: {module}", address=it['address'], module=it['module']))
            if it["status"] == "ok":
                info = it["info"]
                lines.append(tr("   Peça: {part}   Componente: {component}",
                                part=info['part'], component=info['component']))
                if info.get("coding") is not None:
                    wsc = f"{info['wsc']:05d}" if info.get("wsc") is not None else "—"
                    lines.append(tr("   Codificação: {coding:05d}   WSC: {wsc}", coding=info['coding'], wsc=wsc))
                fl = it["faults"]
                lines.append(tr("   {v} avaria(s)", v=len(fl)))
                for f in fl:
                    lines.append(f"   {f['vag']} - {f['desc']}")
                    if f.get("locked"):
                        continue
                    intermittent = " - Intermitente" if f["intermittent"] else ""
                    lines.append(f"      {f['elab_code']:02d} - {f['elab']}{intermittent}")
            else:
                lines.append(tr("   Erro: {v}", v=client_text(it.get('error', ''))))
            lines.append("-" * 60)
        return "\n".join(lines)

    def _copy(self):
        QGuiApplication.clipboard().setText(self.report())

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Guardar relatório"),
            os.path.join(os.path.expanduser("~"), f"AutoScan_{datetime.datetime.now():%Y%m%d_%H%M}.txt"),
            tr("Texto (*.txt)"))
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.report())
