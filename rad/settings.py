"""Definições do programa (porta do cabo, oficina, janela...).

Ficam no registo do Windows. Com a variável RAD_SETTINGS_INI ficam num ficheiro .ini — é o que os
testes usam para não mexer nas definições reais."""
import os

from PySide6.QtCore import QSettings


ORGANIZATION, APPLICATION = "Torqis", "Torqis"
# onde as versões até 1.21 (com o nome antigo do programa) guardavam as definições — só para as trazer uma vez
LEGACY_ORGANIZATION, LEGACY_APPLICATION = "Roots", "RootsAutoDoctor"


def app_settings():
    path = os.environ.get("RAD_SETTINGS_INI")
    if path:
        return QSettings(path, QSettings.IniFormat)
    return QSettings(ORGANIZATION, APPLICATION)


def migrate_legacy_settings(new=None, old=None):
    """Primeiro arranque com o nome novo: copia as definições antigas (porta do cabo, dados da oficina, idioma,
    tamanho da janela...) se ainda não houver nenhuma. Devolve o número de definições copiadas. Nunca falha."""
    try:
        if new is None:
            if os.environ.get("RAD_SETTINGS_INI"):
                return 0                          # testes: definições num ficheiro à parte
            new = QSettings(ORGANIZATION, APPLICATION)
        if new.allKeys():
            return 0
        old = old if old is not None else QSettings(LEGACY_ORGANIZATION, LEGACY_APPLICATION)
        keys = old.allKeys()
        for k in keys:
            new.setValue(k, old.value(k))
        if keys:
            new.sync()
        return len(keys)
    except Exception:
        return 0


# Tamanho da interface (Opções → Ecrã). Aplica-se no arranque, antes de criar a QApplication, com o factor de
# escala do Qt: aumenta letras, botões e mostradores por igual, sem cortar textos.
UI_SCALES = ("1", "1.15", "1.3", "1.5")


def ui_scale(settings=None):
    value = str((settings or app_settings()).value("ui/scale", "1"))
    return value if value in UI_SCALES else "1"


def apply_ui_scale(environ=None):
    """Define QT_SCALE_FACTOR a partir das definições. Se o utilizador já definiu a variável, não mexe.
    Devolve o factor aplicado (ou None)."""
    environ = os.environ if environ is None else environ
    if environ.get("QT_SCALE_FACTOR"):
        return None
    try:
        scale = ui_scale()
    except Exception:                 # definições ilegíveis: arranca no tamanho normal
        return None
    if scale != "1":
        environ["QT_SCALE_FACTOR"] = scale
        return scale
    return None
