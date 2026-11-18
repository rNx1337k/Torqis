"""Instala a identidade visual Torqis no programa a partir do kit da marca (variante B · Minimal premium).

O kit (símbolo, ícone em todos os tamanhos, logótipo e capa) é desenhado à parte, com as regras da marca: anel
claro com escala, ponteiro azul (#3D7BFF → #5AA8FF) e fundo grafite. Este script só o copia para os sítios que o
programa e o README usam:

    icone.ico            → rad/assets/icon.ico      (janela, barra de tarefas, instalador)
    icone_512/64/32/16   → rad/assets/logo*.png     (barra lateral, splash, relatório sem logótipo da oficina)
    icone.svg            → rad/assets/logo.svg
    capa_1500x500.png    → docs/banner.png          (topo do README)

Correr:  .venv\\Scripts\\python.exe tools\\make_brand.py <pasta do kit>
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "rad", "assets")
DOCS = os.path.join(ROOT, "docs")

FILES = {
    "icone.ico": os.path.join(ASSETS, "icon.ico"),
    "icone_512.png": os.path.join(ASSETS, "logo.png"),
    "icone_64.png": os.path.join(ASSETS, "logo_64.png"),
    "icone_32.png": os.path.join(ASSETS, "logo_32.png"),
    "icone_16.png": os.path.join(ASSETS, "logo_16.png"),
    "icone.svg": os.path.join(ASSETS, "logo.svg"),
    "capa_1500x500.png": os.path.join(DOCS, "banner.png"),
}


def install(kit, log=print):
    missing = [name for name in FILES if not os.path.isfile(os.path.join(kit, name))]
    if missing:
        raise SystemExit(f"Faltam ficheiros no kit {kit}: {', '.join(missing)}")
    for name, dest in FILES.items():
        shutil.copyfile(os.path.join(kit, name), dest)
        log(f"{name} -> {os.path.relpath(dest, ROOT)}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    install(argv[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
