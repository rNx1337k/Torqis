"""Licenças do Torqis — janela do fornecedor (NÃO vai no instalador).

Emitir uma licença a partir do ID do PC da oficina, ver todas as licenças emitidas, procurar, copiar outra vez a
chave ou a mensagem para o cliente e renovar. Usa a chave privada e o registo de tools/license_tool.py:
    %USERPROFILE%\\RootsAutoDoctor_licencas\\private.key           (nunca sai deste PC)
    %USERPROFILE%\\RootsAutoDoctor_licencas\\licencas_emitidas.csv (abre no Excel; copiado para D:\\Torqis_copia_chaves)

Abrir:  tools\\licencas.bat   (ou o atalho "Torqis — Licenças" no ambiente de trabalho)
"""
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import license_tool as lt  # noqa: E402
from rad import ed25519, licensing  # noqa: E402

from PySide6.QtCore import QDate, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QGuiApplication, QIcon  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView, QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

TITLE = "Torqis — Licenças"
VALIDITY = [("1 ano", 12), ("6 meses", 6), ("3 meses", 3), ("1 mês", 1), ("Sem data de fim", None),
            ("Escolher a data…", "data")]
COLUMNS = ["Emitida", "Oficina", "Contacto", "ID do PC", "Válida até", "Estado", "Notas"]


def _colors():
    from rad.ui.style import BAD, MUTED, OK, TEXT, WARN
    return {"Activa": OK, "Sem fim": OK, "A acabar": WARN, "Expirada": BAD, "Substituída": MUTED, "": TEXT}


def _fmt(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return ""


class LicencesWindow(QMainWindow):
    def __init__(self, key_path=None, today=None):
        super().__init__()
        from rad.ui.pages.common import btn, card, lbl
        self._btn, self._card, self._lbl = btn, card, lbl
        self.key_path = key_path or os.path.join(lt.DEFAULT_DIR, "private.key")
        self.registry = lt.registry_path(self.key_path)
        self.today = today
        self.secret = None
        self.last = None
        self._prefilled = None
        self.setWindowTitle(TITLE)
        self.resize(1180, 720)
        from rad.ui.style import QSS
        self.setStyleSheet(QSS)                       # o mesmo aspecto do Torqis (fundo escuro, botões, tabela)
        central = QWidget()
        central.setObjectName("root")
        central.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(central)
        v = QVBoxLayout(central)
        v.setContentsMargins(20, 18, 20, 16)
        head = QHBoxLayout()
        head.addWidget(lbl(TITLE, "h1"))
        head.addStretch(1)
        self.key_lbl = lbl("", "muted")
        head.addWidget(self.key_lbl)
        v.addLayout(head)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_issue(), "Emitir licença")
        self.tabs.addTab(self._build_list(), "Licenças emitidas")
        v.addWidget(self.tabs, 1)
        self._load_secret()
        self.refresh()

    # ------------------------------------------------------------------ chave privada
    def _today(self):
        return self.today or datetime.date.today()

    def _load_secret(self):
        try:
            with open(self.key_path, encoding="ascii") as fh:
                secret = bytes.fromhex(fh.read().strip())
            if len(secret) != 32:
                raise ValueError
            self.secret = secret
            # confirma que a chave privada é a do programa publicado (senão as chaves não seriam aceites)
            from rad import license_pubkey
            ours = ed25519.public_key(secret).hex()
            if license_pubkey.PUBLIC_KEY and license_pubkey.PUBLIC_KEY != ours:
                self.key_lbl.setText("⚠ A chave privada não corresponde à do programa: as licenças não funcionariam.")
                self.secret = None
            else:
                self.key_lbl.setText(f"Chave privada: {self.key_path}")
        except (OSError, ValueError):
            self.secret = None
            self.key_lbl.setText(f"⚠ Chave privada não encontrada em {self.key_path}: não é possível emitir.")
        self.gen_btn.setEnabled(self.secret is not None)

    # ------------------------------------------------------------------ separador "Emitir"
    def _build_issue(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 14, 0, 0)
        h.setSpacing(16)
        form_card = self._card()
        f = QFormLayout(form_card)
        f.setContentsMargins(20, 18, 20, 18)
        f.setVerticalSpacing(12)
        f.addRow(self._lbl("Dados da oficina", "h2"))
        self.e_machine = QLineEdit()
        self.e_machine.setPlaceholderText("ABCD-EFGH-JKLM  (Opções → Licença no programa da oficina)")
        self.e_machine.textChanged.connect(self._machine_changed)
        f.addRow(self._lbl("ID do PC", "muted"), self.e_machine)
        self.machine_hint = self._lbl("", "muted", wrap=True)
        f.addRow(QLabel(), self.machine_hint)
        self.e_workshop = QLineEdit()
        self.e_workshop.setPlaceholderText("Aparece no programa do cliente: \"Licenciado a …\"")
        f.addRow(self._lbl("Oficina", "muted"), self.e_workshop)
        self.e_contact = QLineEdit()
        self.e_contact.setPlaceholderText("Instagram, telefone ou email (opcional)")
        f.addRow(self._lbl("Contacto", "muted"), self.e_contact)
        vr = QHBoxLayout()
        self.e_validity = QComboBox()
        for text, _ in VALIDITY:
            self.e_validity.addItem(text)
        self.e_validity.currentIndexChanged.connect(self._validity_changed)
        vr.addWidget(self.e_validity, 1)
        self.e_date = QDateEdit()
        self.e_date.setCalendarPopup(True)
        self.e_date.setDisplayFormat("dd/MM/yyyy")
        self.e_date.setVisible(False)
        vr.addWidget(self.e_date, 1)
        f.addRow(self._lbl("Validade", "muted"), vr)
        self.validity_lbl = self._lbl("", "muted")
        f.addRow(QLabel(), self.validity_lbl)
        self.e_notes = QLineEdit()
        self.e_notes.setPlaceholderText("Ex.: pago por MB Way em 22/11, beta, oferta… (opcional)")
        f.addRow(self._lbl("Notas", "muted"), self.e_notes)
        self.gen_btn = self._btn("Gerar licença", "primary", self._generate)
        f.addRow(QLabel(), self.gen_btn)
        h.addWidget(form_card, 1)

        out_card = self._card()
        o = QVBoxLayout(out_card)
        o.setContentsMargins(20, 18, 20, 18)
        o.addWidget(self._lbl("Chave para enviar", "h2"))
        self.out_info = self._lbl("Preencha os dados e carregue em Gerar licença.", "muted", wrap=True)
        o.addWidget(self.out_info)
        self.out_key = QPlainTextEdit()
        self.out_key.setReadOnly(True)
        self.out_key.setMaximumHeight(110)
        o.addWidget(self.out_key)
        row = QHBoxLayout()
        self.copy_key_btn = self._btn("Copiar chave", None, lambda: self._copy(self.last, "chave"))
        self.copy_msg_btn = self._btn("Copiar mensagem para o cliente", "primary",
                                      lambda: self._copy(self.last, "mensagem"))
        row.addWidget(self.copy_key_btn)
        row.addWidget(self.copy_msg_btn)
        row.addStretch(1)
        o.addLayout(row)
        o.addWidget(self._lbl("Mensagem para o cliente", "muted"))
        self.out_msg = QPlainTextEdit()
        self.out_msg.setReadOnly(True)
        o.addWidget(self.out_msg, 1)
        for b in (self.copy_key_btn, self.copy_msg_btn):
            b.setEnabled(False)
        h.addWidget(out_card, 1)
        self._validity_changed(0)
        return w

    def _machine_changed(self, text):
        m = licensing.normalize_machine_id(text)
        if self._prefilled and (self.e_workshop.text(), self.e_contact.text()) == self._prefilled:
            self.e_workshop.clear()                   # dados preenchidos por outro PC: não passam para este
            self.e_contact.clear()
        self._prefilled = None
        if not text.strip():
            self.machine_hint.setText("")
            return
        ok = len(m) == 14 and set(m.replace("-", "")) <= set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
        if not ok:
            self.machine_hint.setText("⚠ O ID tem 12 letras e números (sem 0, O, 1 nem I).")
            return
        same = [r for r in lt.read_registry(self.registry) if r["id_pc"] == m]
        if same:
            last = same[-1]
            st, _ = lt.row_status(last, same, self._today())
            self.machine_hint.setText(f"✔ {m} · já tem licença: {last['oficina']} ({st.lower()}"
                                      + (f", até {_fmt(last['expira'])}" if last["expira"] else "") + ")")
            if not self.e_workshop.text().strip():
                self.e_workshop.setText(last["oficina"])
                self.e_contact.setText(last.get("contacto", ""))
                self._prefilled = (self.e_workshop.text(), self.e_contact.text())
        else:
            self.machine_hint.setText(f"✔ {m}")

    def _validity_changed(self, i):
        months = VALIDITY[i][1]
        self.e_date.setVisible(months == "data")
        if months == "data":
            d = lt.add_months(self._today(), 12)
            self.e_date.setMinimumDate(QDate(self._today().year, self._today().month, self._today().day))
            self.e_date.setDate(QDate(d.year, d.month, d.day))
            self.validity_lbl.setText("")
        elif months is None:
            self.validity_lbl.setText("A licença nunca expira.")
        else:
            self.validity_lbl.setText(f"Válida até {lt.add_months(self._today(), months):%d/%m/%Y}")

    def expires(self):
        months = VALIDITY[self.e_validity.currentIndex()][1]
        if months is None:
            return None
        if months == "data":
            d = self.e_date.date()
            return datetime.date(d.year(), d.month(), d.day())
        return lt.add_months(self._today(), months)

    def _generate(self):
        if self.secret is None:
            QMessageBox.warning(self, TITLE, self.key_lbl.text())
            return
        try:
            row = lt.issue(self.secret, self.e_workshop.text(), self.e_machine.text(), self.expires(),
                           self.e_contact.text(), self.e_notes.text(), registry=self.registry, today=self._today())
        except ValueError as e:
            QMessageBox.warning(self, TITLE, str(e))
            return
        except OSError as e:
            QMessageBox.warning(self, TITLE, f"Não foi possível gravar o registo:\n{e}")
            return
        self.show_result(row)
        self.refresh()
        for e in (self.e_machine, self.e_workshop, self.e_contact, self.e_notes):   # pronto para a próxima
            e.clear()

    def show_result(self, row):
        self.last = row
        self.out_key.setPlainText(row["chave"])
        self.out_msg.setPlainText(lt.customer_message(row))
        end = f"até {_fmt(row['expira'])}" if row["expira"] else "sem data de fim"
        self.out_info.setText(f"✔ Licença de {row['oficina']} ({row['id_pc']}), {end}. Ficou no registo.")
        for b in (self.copy_key_btn, self.copy_msg_btn):
            b.setEnabled(True)

    # ------------------------------------------------------------------ separador "Licenças emitidas"
    def _build_list(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 14, 0, 0)
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Procurar por oficina, ID do PC, contacto ou notas…")
        self.search.textChanged.connect(self._fill)
        top.addWidget(self.search, 1)
        self.only = QComboBox()
        self.only.addItems(["Todas", "Em vigor", "A acabar", "Expiradas", "Substituídas"])
        self.only.currentIndexChanged.connect(self._fill)
        top.addWidget(self.only)
        v.addLayout(top)
        self.summary = self._lbl("", "muted")
        v.addWidget(self.summary)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        hh = self.table.horizontalHeader()
        for c in range(len(COLUMNS)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(lambda _i: self._copy(self.selected(), "mensagem"))
        v.addWidget(self.table, 1)
        row = QHBoxLayout()
        row.addWidget(self._btn("Copiar chave", None, lambda: self._copy(self.selected(), "chave")))
        row.addWidget(self._btn("Copiar mensagem", None, lambda: self._copy(self.selected(), "mensagem")))
        row.addWidget(self._btn("Renovar…", "primary", self._renew))
        row.addWidget(self._btn("Editar contacto/notas…", None, self._edit))
        row.addStretch(1)
        row.addWidget(self._btn("Abrir no Excel", None, self._open_excel))
        row.addWidget(self._btn("Abrir pasta", None,
                                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.registry)))))
        v.addLayout(row)
        return w

    def refresh(self):
        self.rows = lt.read_registry(self.registry)
        self._fill()

    def _fill(self, *_):
        colors = _colors()
        today = self._today()
        query = self.search.text().strip().lower()
        only = self.only.currentText()
        self.table.setRowCount(0)
        self.visible = []
        counts = {}
        for row in reversed(self.rows):                       # mais recentes primeiro
            st, left = lt.row_status(row, self.rows, today)
            counts[st] = counts.get(st, 0) + 1
            if query and query not in " ".join(row.get(f, "") for f in
                                               ("oficina", "id_pc", "contacto", "notas")).lower():
                continue
            if only == "Em vigor" and st not in ("Activa", "Sem fim", "A acabar"):
                continue
            if only == "A acabar" and st != "A acabar":
                continue
            if only == "Expiradas" and st != "Expirada":
                continue
            if only == "Substituídas" and st != "Substituída":
                continue
            label = st
            if st == "A acabar":
                label = f"A acabar ({left} dia{'s' if left != 1 else ''})"
            elif st == "Expirada":
                label = f"Expirada há {-left} dia{'s' if left != -1 else ''}"
            values = [_fmt(row["data"]), row["oficina"], row.get("contacto", ""), row["id_pc"],
                      _fmt(row["expira"]) or "Sem fim", label, row.get("notas", "")]
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, text in enumerate(values):
                it = QTableWidgetItem(text)
                if c == 5:
                    it.setForeground(QBrush(QColor(colors.get(st, colors[""]))))
                self.table.setItem(r, c, it)
            self.visible.append(row)
        active = counts.get("Activa", 0) + counts.get("Sem fim", 0) + counts.get("A acabar", 0)
        self.summary.setText(f"{len(self.rows)} licença(s) emitida(s) · {active} em vigor · "
                             f"{counts.get('A acabar', 0)} a acabar · {counts.get('Expirada', 0)} expirada(s)"
                             f"   —   registo: {self.registry}")

    def selected(self):
        r = self.table.currentRow()
        return self.visible[r] if 0 <= r < len(self.visible) else None

    def _copy(self, row, what):
        if row is None:
            QMessageBox.information(self, TITLE, "Escolha primeiro uma licença.")
            return
        QGuiApplication.clipboard().setText(row["chave"] if what == "chave" else lt.customer_message(row))

    def _renew(self):
        row = self.selected()
        if row is None:
            QMessageBox.information(self, TITLE, "Escolha na lista a licença a renovar.")
            return
        if self.secret is None:
            QMessageBox.warning(self, TITLE, self.key_lbl.text())
            return
        options = [(f"{label} (até {lt.renewal_date(row, m, self._today()):%d/%m/%Y})", m)
                   for label, m in VALIDITY if isinstance(m, int)] + [("Sem data de fim", None)]
        dlg = QDialog(self)
        dlg.setWindowTitle("Renovar licença")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"{row['oficina']} · {row['id_pc']}\nA renovação conta a partir do fim da licença "
                             "actual, se ainda não acabou."))
        combo = QComboBox()
        for text, _ in options:
            combo.addItem(text)
        lay.addWidget(combo)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if not dlg.exec():
            return
        months = options[combo.currentIndex()][1]
        expires = None if months is None else lt.renewal_date(row, months, self._today())
        new = lt.issue(self.secret, row["oficina"], row["id_pc"], expires, row.get("contacto", ""),
                       "Renovação", registry=self.registry, today=self._today())
        self.refresh()
        self.show_result(new)
        self.tabs.setCurrentIndex(0)

    def _edit(self):
        row = self.selected()
        if row is None:
            QMessageBox.information(self, TITLE, "Escolha primeiro uma licença.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Contacto e notas")
        f = QFormLayout(dlg)
        contact, notes = QLineEdit(row.get("contacto", "")), QLineEdit(row.get("notas", ""))
        f.addRow(f"{row['oficina']} · {row['id_pc']}", QLabel())
        f.addRow("Contacto", contact)
        f.addRow("Notas", notes)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if not dlg.exec():
            return
        row["contacto"], row["notas"] = contact.text().strip(), notes.text().strip()
        lt.write_registry(self.registry, self.rows)
        self._fill()

    def _open_excel(self):
        if not os.path.exists(self.registry):
            QMessageBox.information(self, TITLE, "Ainda não há licenças emitidas.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.registry))


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Torqis.Licencas")
    except (AttributeError, OSError):
        pass
    from rad.ui.style import QSS
    from rad.ui.widgets import asset_path
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    app.setWindowIcon(QIcon(asset_path("icon.ico")))
    w = LicencesWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
