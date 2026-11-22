"""Ferramenta do fornecedor para as licenças do Torqis. NÃO vai no instalador.

1) Uma vez só — criar o par de chaves:
       python tools/license_tool.py genkey
   Guarda a chave privada FORA do repositório (por omissão em %USERPROFILE%\\Torqis_licencas) e
   escreve a chave pública em rad/license_pubkey.py. Faça cópia de segurança da chave privada: se a perder,
   as licenças já vendidas continuam a funcionar, mas não pode gerar novas para esta chave pública.

2) Por cada oficina — gerar a licença a partir do ID do PC (Opções → Licença no programa da oficina):
       python tools/license_tool.py issue --machine ABCD-EFGH-JKLM --workshop "Oficina Silva"
       python tools/license_tool.py issue --machine ABCD-EFGH-JKLM --workshop "Oficina Silva" --expires 2027-12-31
   Imprime a chave para enviar à oficina e acrescenta uma linha a licencas_emitidas.csv, ao lado da chave privada.

3) Ver o ID deste PC:
       python tools/license_tool.py machine

Para o dia-a-dia há a janela tools/licencas.py (atalho "Torqis — Licenças"): emitir, procurar, copiar e renovar,
com o mesmo registo (licencas_emitidas.csv, que abre no Excel) e as mesmas funções deste ficheiro.
"""
import argparse
import csv
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from rad import ed25519, licensing  # noqa: E402

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Torqis_licencas")
# pasta das chaves criada antes de o programa mudar de nome: continua a ser usada se a nova ainda não existir
OLD_DIR = os.path.join(os.path.expanduser("~"), "RootsAutoDoctor_licencas")
if not os.path.isdir(DEFAULT_DIR) and os.path.isdir(OLD_DIR):
    DEFAULT_DIR = OLD_DIR
PUBKEY_FILE = os.path.join(ROOT, "rad", "license_pubkey.py")
REGISTRY_NAME = "licencas_emitidas.csv"
# Colunas do registo. As 5 primeiras são as das primeiras versões (os ficheiros antigos continuam a ser lidos).
FIELDS = ["data", "oficina", "id_pc", "expira", "chave", "contacto", "notas"]
# Depois de cada alteração o registo é copiado para estas pastas, se existirem (cópia de segurança das chaves)
BACKUP_DIRS = [r"D:\Torqis_copia_chaves"]
EXPIRING_DAYS = 30           # "A acabar": faltam até 30 dias


def _inside(path, folder):
    """True se path fica dentro de folder. Em discos diferentes (C: e D:) nunca fica."""
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(folder)]) == os.path.abspath(folder)
    except ValueError:
        return False


def _key_path(args):
    return args.key or os.path.join(DEFAULT_DIR, "private.key")


def _read_secret(path):
    try:
        with open(path, encoding="ascii") as fh:
            secret = bytes.fromhex(fh.read().strip())
    except OSError:
        sys.exit(f"Chave privada não encontrada: {path}\nCrie-a primeiro com: python tools/license_tool.py genkey")
    if len(secret) != 32:
        sys.exit(f"Chave privada inválida: {path}")
    return secret


def write_pubkey(public_hex, path=None):
    with open(path or PUBKEY_FILE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('"""Chave pública das licenças (Ed25519, 32 bytes em hexadecimal).\n\n'
                 'Gerada por `python tools/license_tool.py genkey`, que guarda a chave privada FORA do repositório.\n'
                 'None = licenciamento por configurar: o programa funciona sem limites '
                 '(versão de desenvolvimento)."""\n'
                 f'PUBLIC_KEY = "{public_hex}"\n')


def cmd_genkey(args):
    path = _key_path(args)
    if os.path.exists(path):
        sys.exit(f"Já existe uma chave privada em {path}.\nNão foi alterada: substituí-la invalidava as "
                 "licenças futuras. Apague-a à mão só se tiver a certeza.")
    if _inside(path, ROOT):
        sys.exit("A chave privada não pode ficar dentro da pasta do projecto (iria parar ao GitHub).")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    secret = os.urandom(32)
    with open(path, "w", encoding="ascii") as fh:
        fh.write(secret.hex() + "\n")
    public_hex = ed25519.public_key(secret).hex()
    write_pubkey(public_hex)
    print(f"Chave privada: {path}  (faça cópia de segurança e NUNCA a envie a ninguém)")
    print(f"Chave pública escrita em: {PUBKEY_FILE}")
    print("A partir do próximo build: 14 dias de teste e depois, sem licença, modo demonstração "
          "(ver docs/LICENSING.md).")


# ------------------------------------------------------------------ registo das licenças emitidas
def registry_path(key_path=None):
    return os.path.join(os.path.dirname(key_path or os.path.join(DEFAULT_DIR, "private.key")), REGISTRY_NAME)


def read_registry(path):
    """Linhas do registo como dicionários (FIELDS), pela ordem do ficheiro. Aceita o formato antigo (5 colunas)."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh, delimiter=";"))
    except OSError:
        return []
    out = []
    for row in rows[1:] if rows and rows[0][:1] == ["data"] else rows:
        if not any(c.strip() for c in row):
            continue
        out.append({f: (row[i].strip() if i < len(row) else "") for i, f in enumerate(FIELDS)})
    return out


def write_registry(path, rows, backup=True):
    """Grava o registo inteiro (UTF-8 com BOM: abre com acentos no Excel) e faz a cópia de segurança."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([r.get(f, "") for f in FIELDS])
    os.replace(tmp, path)
    if backup:
        backup_registry(path)


def backup_registry(path, dirs=None):
    """Copia o registo para as pastas de cópia de segurança que existirem. Devolve as cópias feitas."""
    import shutil
    done = []
    for d in BACKUP_DIRS if dirs is None else dirs:
        if os.path.isdir(d):
            try:
                shutil.copyfile(path, os.path.join(d, os.path.basename(path)))
                done.append(d)
            except OSError:
                pass
    return done


def issue(secret, workshop, machine, expires=None, contact="", notes="", registry=None, today=None):
    """Gera a chave, confirma que o programa a aceita e acrescenta-a ao registo. Devolve a linha do registo.
    Lança ValueError com uma frase para o utilizador se os dados estiverem mal."""
    workshop = (workshop or "").strip()
    machine = licensing.normalize_machine_id(machine)
    if not workshop:
        raise ValueError("Falta o nome da oficina.")
    if len(machine) != 14 or not set(machine.replace("-", "")) <= set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789"):
        raise ValueError("ID do PC inválido: são 12 letras e números, como ABCD-EFGH-JKLM "
                         "(sem 0, O, 1 nem I). Peça à oficina para o copiar em Opções → Licença.")
    today = today or datetime.date.today()
    if expires is not None and expires < today:
        raise ValueError("A data de fim já passou.")
    key = licensing.make_key(secret, workshop, machine, expires, issued=today)
    r = licensing.check_key(key, machine, today=today, public=ed25519.public_key(secret))
    if not r["valid"]:                                  # nunca deve acontecer: não se envia uma chave estragada
        raise ValueError("A chave gerada não passou na verificação: " + r["reason"])
    row = {"data": today.isoformat(), "oficina": workshop, "id_pc": machine,
           "expira": expires.isoformat() if expires else "", "chave": key,
           "contacto": (contact or "").strip(), "notas": (notes or "").strip().replace("\n", " ")}
    if registry:
        write_registry(registry, read_registry(registry) + [row])
    return row


def _date(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def row_status(row, rows=(), today=None):
    """Estado de uma licença: "Substituída" (há outra mais recente para o mesmo PC), "Expirada", "A acabar",
    "Activa" ou "Sem fim". Devolve (estado, dias que faltam ou None)."""
    today = today or datetime.date.today()
    later = [r for r in rows if r is not row and r.get("id_pc") == row.get("id_pc")
             and (r.get("data", ""), rows.index(r)) > (row.get("data", ""), rows.index(row) if row in rows else -1)]
    if later:
        return "Substituída", None
    end = _date(row.get("expira"))
    if end is None:
        return "Sem fim", None
    left = (end - today).days
    if left < 0:
        return "Expirada", left
    if left <= EXPIRING_DAYS:
        return "A acabar", left
    return "Activa", left


def add_months(date, months):
    month = date.month - 1 + months
    year, month = date.year + month // 12, month % 12 + 1
    days = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31,
            30, 31][month - 1]
    return date.replace(year=year, month=month, day=min(date.day, days))


def renewal_date(row, months=12, today=None):
    """Nova data de fim ao renovar: conta a partir do fim actual se ainda não passou (não se perdem dias)."""
    today = today or datetime.date.today()
    end = _date(row.get("expira"))
    return add_months(end if end and end >= today else today, months)


def customer_message(row):
    """Texto para enviar à oficina, com a chave e como a activar."""
    end = _date(row.get("expira"))
    validity = f"válida até {end:%d/%m/%Y}" if end else "sem data de fim"
    return (f"Olá! Aqui está a licença do Torqis para {row['oficina']} ({validity}):\n\n{row['chave']}\n\n"
            "Para activar: abra o Torqis → Opções → Licença, cole a chave na caixa \"Chave\" e carregue em "
            "\"Activar licença\". Não precisa de internet. A chave só funciona no PC com o ID "
            f"{row['id_pc']}.")


def cmd_issue(args):
    secret = _read_secret(_key_path(args))
    expires = datetime.date.fromisoformat(args.expires) if args.expires else None
    try:
        row = issue(secret, args.workshop, args.machine, expires, args.contact or "", args.notes or "",
                    registry=registry_path(_key_path(args)))
    except ValueError as e:
        sys.exit(str(e))
    print(row["chave"])


def cmd_machine(_args):
    print(licensing.machine_id())


def main(argv=None):
    p = argparse.ArgumentParser(description="Licenças do Torqis")
    p.add_argument("--key", help="caminho da chave privada (por omissão: %(default)s)",
                   default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("genkey", help="criar o par de chaves (uma vez só)")
    i = sub.add_parser("issue", help="gerar a licença de uma oficina")
    i.add_argument("--machine", required=True, help="ID do PC da oficina (Opções → Licença)")
    i.add_argument("--workshop", required=True, help="nome da oficina")
    i.add_argument("--expires", help="data de fim AAAA-MM-DD (opcional)")
    i.add_argument("--contact", help="contacto da oficina (Instagram, telefone, email) — opcional")
    i.add_argument("--notes", help="notas — opcional")
    sub.add_parser("machine", help="mostrar o ID deste PC")
    args = p.parse_args(argv)
    {"genkey": cmd_genkey, "issue": cmd_issue, "machine": cmd_machine}[args.cmd](args)


if __name__ == "__main__":
    main()
