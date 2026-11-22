"""Janela das licenças (tools/licencas.py) e registo das licenças emitidas (tools/license_tool.py).

Corre com uma chave privada de teste numa pasta temporária: nunca toca na chave nem no registo verdadeiros.
Correr:  python tests/test_license_window.py
"""
import datetime
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import license_tool as lt  # noqa: E402
from rad import ed25519, licensing, license_pubkey  # noqa: E402

SECRET = bytes(range(32))
TODAY = datetime.date(2026, 11, 22)


def _folder():
    d = tempfile.mkdtemp()
    key = os.path.join(d, "private.key")
    with open(key, "w", encoding="ascii") as fh:
        fh.write(SECRET.hex() + "\n")
    return d, key


def test_old_registry_rows_are_still_read_and_upgraded():
    d, _key = _folder()
    reg = os.path.join(d, lt.REGISTRY_NAME)
    with open(reg, "w", encoding="utf-8", newline="") as fh:          # formato das primeiras versões
        fh.write("data;oficina;id_pc;expira;chave\r\n2026-11-19;Oficina Velha;ABCD-EFGH-JKLM;;RAD1-x.y\r\n")
    rows = lt.read_registry(reg)
    assert rows[0]["oficina"] == "Oficina Velha" and rows[0]["contacto"] == "" and rows[0]["notas"] == ""
    row = lt.issue(SECRET, "Oficina Nova", "zzzz-yyyy-xxxx", None, "@oficina", "beta", registry=reg, today=TODAY)
    rows = lt.read_registry(reg)
    assert [r["oficina"] for r in rows] == ["Oficina Velha", "Oficina Nova"]
    assert rows[1]["contacto"] == "@oficina" and rows[1]["id_pc"] == "ZZZZ-YYYY-XXXX" == row["id_pc"]
    with open(reg, "rb") as fh:
        assert fh.read(3) == b"\xef\xbb\xbf"                              # BOM: o Excel mostra os acentos


def test_issued_keys_are_accepted_by_the_program_and_bad_input_is_explained():
    pub = ed25519.public_key(SECRET)
    row = lt.issue(SECRET, "Oficina Silva", "abcd-efgh-jklm", datetime.date(2027, 11, 22), today=TODAY)
    r = licensing.check_key(row["chave"], "ABCD-EFGH-JKLM", today=TODAY, public=pub)
    assert r["valid"] and r["workshop"] == "Oficina Silva" and r["expires"] == datetime.date(2027, 11, 22)
    for args, msg in ((("", "ABCD-EFGH-JKLM"), "oficina"), (("X", "ABCD-EFGH-JKL"), "ID do PC"),
                      (("X", "ABCD-EFGH-JKL0"), "ID do PC")):
        try:
            lt.issue(SECRET, *args, today=TODAY)
        except ValueError as e:
            assert msg in str(e)
        else:
            raise AssertionError(args)
    try:
        lt.issue(SECRET, "X", "ABCD-EFGH-JKLM", datetime.date(2026, 1, 1), today=TODAY)
    except ValueError as e:
        assert "passou" in str(e)


def test_status_renewal_and_message():
    rows = [{"data": "2025-01-01", "id_pc": "A", "expira": "2025-12-31"},
            {"data": "2026-01-01", "id_pc": "A", "expira": "2026-12-10"},
            {"data": "2026-02-01", "id_pc": "B", "expira": "2026-11-01"},
            {"data": "2026-03-01", "id_pc": "C", "expira": ""},
            {"data": "2026-03-01", "id_pc": "D", "expira": "2027-06-01"}]
    st = [lt.row_status(r, rows, TODAY)[0] for r in rows]
    assert st == ["Substituída", "A acabar", "Expirada", "Sem fim", "Activa"]
    # renovar conta a partir do fim actual se ainda não passou; senão a partir de hoje
    assert lt.renewal_date(rows[1], 12, TODAY) == datetime.date(2027, 12, 10)
    assert lt.renewal_date(rows[2], 12, TODAY) == datetime.date(2027, 11, 22)
    assert lt.add_months(datetime.date(2027, 1, 31), 1) == datetime.date(2027, 2, 28)
    msg = lt.customer_message({"oficina": "Oficina Silva", "chave": "RAD1-abc", "expira": "2027-11-22",
                               "id_pc": "ABCD-EFGH-JKLM"})
    assert "RAD1-abc" in msg and "22/11/2027" in msg and "Opções → Licença" in msg


def test_registry_is_copied_to_the_backup_folder():
    d, _key = _folder()
    backup = tempfile.mkdtemp()
    old = lt.BACKUP_DIRS
    lt.BACKUP_DIRS = [backup, os.path.join(backup, "nao_existe")]
    try:
        lt.issue(SECRET, "Oficina", "ABCD-EFGH-JKLM", registry=os.path.join(d, lt.REGISTRY_NAME), today=TODAY)
    finally:
        lt.BACKUP_DIRS = old
    assert lt.read_registry(os.path.join(backup, lt.REGISTRY_NAME))[0]["oficina"] == "Oficina"


def test_window_issues_lists_searches_and_renews():
    from PySide6.QtWidgets import QApplication, QDialog
    app = QApplication.instance() or QApplication([])
    d, key = _folder()
    old_pub, old_backup = license_pubkey.PUBLIC_KEY, lt.BACKUP_DIRS
    license_pubkey.PUBLIC_KEY = ed25519.public_key(SECRET).hex()
    lt.BACKUP_DIRS = []
    import licencas
    try:
        w = licencas.LicencesWindow(key_path=key, today=TODAY)
        assert w.gen_btn.isEnabled() and "private.key" in w.key_lbl.text()
        w.e_machine.setText("abcd efgh jklm")
        assert "✔" in w.machine_hint.text()
        w.e_workshop.setText("Oficina Silva")
        w.e_contact.setText("@oficinasilva")
        w.e_validity.setCurrentIndex(2)                                # 3 meses
        assert w.expires() == datetime.date(2027, 2, 22) and "22/02/2027" in w.validity_lbl.text()
        w._generate()
        assert w.last and licensing.check_key(w.last["chave"], "ABCD-EFGH-JKLM", today=TODAY,
                                              public=ed25519.public_key(SECRET))["valid"]
        assert w.last["chave"] in w.out_msg.toPlainText() and w.copy_msg_btn.isEnabled()
        # o mesmo PC outra vez: avisa que já tem licença e preenche a oficina
        w.e_workshop.clear()
        w.e_machine.setText("ABCD-EFGH-JKLM")
        assert "já tem licença" in w.machine_hint.text() and w.e_workshop.text() == "Oficina Silva"
        # lista, pesquisa e filtro
        w.e_machine.setText("WXYZ-WXYZ-WXYZ")
        w.e_workshop.setText("Auto Costa")
        w.e_validity.setCurrentIndex(4)                                # sem data de fim
        w._generate()
        assert w.table.rowCount() == 2 and w.table.item(0, 1).text() == "Auto Costa"
        w.search.setText("silva")
        assert w.table.rowCount() == 1 and w.table.item(0, 2).text() == "@oficinasilva"
        assert w.table.item(0, 5).text() == "Activa"
        # renovar: escolhe "1 ano" na janela de renovação
        w.table.selectRow(0)
        orig_exec = QDialog.exec
        QDialog.exec = lambda self: 1
        try:
            w._renew()
        finally:
            QDialog.exec = orig_exec
        rows = lt.read_registry(w.registry)
        assert len(rows) == 3 and rows[-1]["id_pc"] == "ABCD-EFGH-JKLM" and rows[-1]["expira"] == "2028-02-22"
        w.search.clear()
        w.only.setCurrentText("Substituídas")
        assert w.table.rowCount() == 1 and w.table.item(0, 1).text() == "Oficina Silva"
        w.close()
        # sem chave privada: não deixa emitir e explica
        w2 = licencas.LicencesWindow(key_path=os.path.join(d, "nao_existe.key"), today=TODAY)
        assert not w2.gen_btn.isEnabled() and "não encontrada" in w2.key_lbl.text()
        w2.close()
        app.processEvents()
    finally:
        license_pubkey.PUBLIC_KEY, lt.BACKUP_DIRS = old_pub, old_backup


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
