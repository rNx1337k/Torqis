APP_NAME = "Torqis"
VERSION = "1.25.0"

EXE_NAME = "Torqis.exe"
DATA_FOLDER = "Torqis"                 # %APPDATA%\Torqis: histórico, licença, registos, gravações, logótipo
# Até à versão 1.21 o programa tinha outro nome e guardava tudo em %APPDATA%\RootsAutoDoctor (e as definições no
# registo em Roots\RootsAutoDoctor). Estes nomes ficam só para trazer esses dados no primeiro arranque
# (migrate_legacy_data, rad.settings.migrate_legacy_settings) — não aparecem em lado nenhum ao cliente.
LEGACY_DATA_FOLDER = "RootsAutoDoctor"


def appdata_base(environ=None):
    import os
    environ = os.environ if environ is None else environ
    return environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")


def data_dir(*parts, environ=None):
    """Pasta de dados do programa (ou uma subpasta), sem a criar."""
    import os
    return os.path.join(appdata_base(environ), DATA_FOLDER, *parts)


def migrate_legacy_data(environ=None):
    """Primeiro arranque com o nome novo: copia a pasta de dados das versões antigas para a nova (histórico,
    clientes, licença, logótipo da oficina, gravações, actualizações por instalar). Copia em vez de mover, para que
    uma reposição da versão anterior continue a encontrar os seus dados. Devolve True se copiou. Nunca falha."""
    import os
    import shutil
    base = appdata_base(environ)
    old, new = os.path.join(base, LEGACY_DATA_FOLDER), os.path.join(base, DATA_FOLDER)
    if os.path.exists(new) or not os.path.isdir(old):
        return False
    try:
        shutil.copytree(old, new)
        return True
    except OSError:
        shutil.rmtree(new, ignore_errors=True)    # cópia a meio: tenta outra vez no próximo arranque
        return False


def technician_mode(argv=None, environ=None):
    """Modo técnico (só desenvolvimento e suporte): mostra o registo de comunicação e as opções avançadas da
    interface (velocidade, eco, protocolo, modo do cabo, simulador J2534). Liga-se com o argumento --tecnico ou
    com a variável RAD_TECNICO=1. O cliente nunca o vê: a interface normal usa só linguagem de oficina."""
    import os
    import sys
    argv = sys.argv if argv is None else argv
    environ = os.environ if environ is None else environ
    return "--tecnico" in argv or environ.get("RAD_TECNICO") == "1"
