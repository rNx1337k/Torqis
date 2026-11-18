"""Mudança de nome para Torqis (1.22.0): quem vem das versões com o nome antigo não pode perder nada — histórico,
clientes, licença, logótipo da oficina, definições — nem a possibilidade de voltar à versão anterior; e o ID do PC
(de que dependem as licenças já emitidas) não pode mudar.

Correr:  python tests/test_rename.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rad  # noqa: E402
from rad import autoupdate, ed25519, licensing  # noqa: E402


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def test_name_is_torqis_everywhere_the_customer_sees_it():
    assert rad.APP_NAME == "Torqis" and rad.EXE_NAME == "Torqis.exe" and rad.DATA_FOLDER == "Torqis"
    assert autoupdate.EXE_NAME == "Torqis.exe"


def test_old_data_folder_is_copied_once_and_kept():
    base = tempfile.mkdtemp()
    env = {"APPDATA": base}
    old = os.path.join(base, rad.LEGACY_DATA_FOLDER)
    _write(os.path.join(old, "historico", "2026-11-01.json"), "{}")
    _write(os.path.join(old, "licenca.txt"), "RAD1-XXXX")
    _write(os.path.join(old, "oficina_logo.png"), "png")
    assert rad.migrate_legacy_data(env) is True
    new = rad.data_dir(environ=env)
    assert new == os.path.join(base, "Torqis")
    for rel in (("historico", "2026-11-01.json"), ("licenca.txt",), ("oficina_logo.png",)):
        assert os.path.isfile(os.path.join(new, *rel)), rel
    assert os.path.isdir(old)                                    # copiado, não movido: a versão anterior ainda o lê
    _write(os.path.join(new, "licenca.txt"), "nova")
    assert rad.migrate_legacy_data(env) is False                 # só uma vez: nunca escreve por cima do que é novo
    assert open(os.path.join(new, "licenca.txt"), encoding="utf-8").read() == "nova"


def test_nothing_to_migrate_on_a_new_pc():
    base = tempfile.mkdtemp()
    assert rad.migrate_legacy_data({"APPDATA": base}) is False
    assert not os.path.exists(os.path.join(base, "Torqis"))


def test_old_settings_are_copied_when_there_are_none_yet():
    from PySide6.QtCore import QSettings
    from rad.settings import migrate_legacy_settings
    folder = tempfile.mkdtemp()
    old = QSettings(os.path.join(folder, "old.ini"), QSettings.IniFormat)
    old.setValue("port", "COM5")
    old.setValue("workshop/name", "Oficina Silva")
    old.setValue("ui/language", "en")
    old.sync()
    new = QSettings(os.path.join(folder, "new.ini"), QSettings.IniFormat)
    assert migrate_legacy_settings(new, old) == 3
    assert new.value("port") == "COM5" and new.value("workshop/name") == "Oficina Silva"
    new.setValue("port", "COM9")
    assert migrate_legacy_settings(new, old) == 0                # já tem definições: não volta a copiar
    assert new.value("port") == "COM9"


def test_machine_id_does_not_change_with_the_name():
    # o mesmo MachineGuid tem de dar o mesmo ID que nas versões antigas (senão as licenças emitidas deixam de valer)
    # valor calculado com o código da versão 1.21.0 (antes da mudança de nome)
    assert licensing.format_machine_id("1b2c3d4e-0000-1111-2222-333344445555") == "9PA5-E69N-QUBC"


def test_rollback_still_finds_the_installer_kept_by_the_old_version():
    base = tempfile.mkdtemp()
    old_env = os.environ.get("APPDATA")
    os.environ["APPDATA"] = base
    secret = bytes(range(32))
    old_key = autoupdate.public_key
    autoupdate.public_key = lambda: ed25519.public_key(secret)
    try:
        path = os.path.join(autoupdate.rollback_dir(), f"Setup_{rad.LEGACY_DATA_FOLDER}_1.21.0.exe")
        with open(path, "wb") as fh:
            fh.write(b"MZ instalador antigo")
        sig = autoupdate.make_signature(secret, path, "1.21.0")
        autoupdate._write(os.path.basename(path) + ".sig", sig)
        found, got_sig = autoupdate._kept_installer("1.21.0")
        assert found == path and got_sig == sig
        autoupdate._prune_installers({"1.21.0"})                 # a limpeza não o apaga
        assert os.path.exists(path)
        autoupdate._prune_installers({"1.22.0"})                 # mas sai quando já não é preciso
        assert not os.path.exists(path)
    finally:
        autoupdate.public_key = old_key
        if old_env is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = old_env


def test_installer_upgrades_old_installs_and_removes_the_old_program():
    iss = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "installer", "Torqis.iss"),
               encoding="utf-8").read()
    assert "AppId={{6B1E2C3A-9F44-4C1B-A7D2-5E0C8B9A7F10}" in iss          # o mesmo programa para o Windows
    assert "AppName=Torqis" in iss and "OutputBaseFilename=Setup_Torqis_" in iss
    assert '{app}\\RootsAutoDoctor.exe' in iss and "[InstallDelete]" in iss
    assert "UsePreviousGroup=no" in iss


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
