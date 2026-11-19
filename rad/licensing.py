"""Licença por oficina, com ativação offline.

Cada PC tem um código (ID do PC) tirado do identificador do Windows. A oficina envia esse código, o
fornecedor gera uma chave com `tools/license_tool.py issue` e a oficina cola-a em Opções → Licença. A chave
é assinada (Ed25519) com a chave privada do fornecedor; o programa só tem a chave pública, por isso não é
possível fabricar uma licença a partir do programa. Não é precisa internet em nenhum passo.

Num PC novo há um período de teste de 14 dias com tudo desbloqueado. Depois, sem licença válida, o programa
funciona em modo demonstração, que serve para confirmar que o cabo e o carro comunicam, mas não para trabalhar:
  - liga aos controladores, identifica-os e o Auto-Scan diz que módulos têm avarias e quantas;
  - mostra só as primeiras 2 avarias VAG por leitura (as outras aparecem como "avaria oculta");
  - valores de medição VAG só durante 60 s por ligação ao controlador, sem gravação CSV nem testes guiados;
  - não escreve em controladores reais (codificação, adaptação, ajustes básicos, apagar avarias, teste de saídas);
  - os relatórios saem marcados;
  - o OBD-II genérico lê tudo (há aplicações grátis que já o fazem) e o simulador funciona sem limites.

Nota: num programa em Python a verificação pode ser contornada por quem altere o código; a licença serve
para controlar a distribuição normal, não é uma protecção contra cópia determinada."""
import base64
import datetime
import hashlib
import json
import logging
import os
import platform
import uuid

from . import ed25519
from .i18n import tr
from . import DATA_FOLDER, LEGACY_DATA_FOLDER

log = logging.getLogger(__name__)

PREFIX = "RAD1-"
FILE_NAME = "licenca.txt"
DIRECTORY = None             # pasta alternativa (testes); None = %APPDATA%\Torqis

TRIAL_DAYS = 14             # período de teste com tudo desbloqueado, contado desde o primeiro arranque neste PC
FREE_FAULTS = 2             # avarias VAG visíveis por leitura em modo demonstração
FREE_LIVE_SECONDS = 60      # valores de medição VAG por ligação ao controlador em modo demonstração
TRIAL_FILE = "inicio.dat"
_TRIAL_REG_KEY = r"Software\Torqis"     # cópia do início do teste no registo (apagar a pasta não reinicia o teste)
_TRIAL_REG_VALUE = "Inicio"

# Comandos que escrevem no controlador ou no veículo: bloqueados em modo demonstração (fora do simulador).
WRITE_COMMANDS = frozenset({"recode", "adaptation_test", "adaptation_save", "service_reset", "clear_faults",
                            "clear_all", "obd_clear", "output_test", "basic_setting"})


def _public_key():
    from .license_pubkey import PUBLIC_KEY
    return bytes.fromhex(PUBLIC_KEY) if PUBLIC_KEY else None


def _b64e(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ------------------------------------------------------------------ ID do PC
def _windows_machine_guid():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                             winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0))
        try:
            return str(winreg.QueryValueEx(key, "MachineGuid")[0])
        finally:
            winreg.CloseKey(key)
    except Exception:
        return None


# Sal do ID do PC. Fica igual ao das primeiras versões (o nome antigo do programa): mudá-lo mudaria o ID de todos
# os PCs e invalidaria as licenças já emitidas. Nunca aparece ao cliente.
MACHINE_ID_SALT = LEGACY_DATA_FOLDER + "|"


def format_machine_id(raw):
    """Código curto e legível ao telefone: 12 caracteres em 3 grupos (sem 0/O/1/I)."""
    digest = hashlib.sha256((MACHINE_ID_SALT + raw).encode()).digest()
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    n = int.from_bytes(digest[:10], "big")
    chars = []
    for _ in range(12):
        n, r = divmod(n, len(alphabet))
        chars.append(alphabet[r])
    code = "".join(chars)
    return f"{code[:4]}-{code[4:8]}-{code[8:]}"


def machine_id():
    raw = _windows_machine_guid() or f"{platform.node()}|{uuid.getnode():012x}"
    return format_machine_id(raw)


def normalize_machine_id(text):
    t = "".join(c for c in (text or "").upper() if c.isalnum())
    return f"{t[:4]}-{t[4:8]}-{t[8:12]}" if len(t) == 12 else (text or "").strip().upper()


# ------------------------------------------------------------- chave de licença
def make_key(secret, workshop, machine, expires=None, edition="pro", issued=None):
    """Cria a chave de licença (usado pela ferramenta do fornecedor, nunca pelo programa)."""
    payload = {"v": 1, "workshop": workshop.strip(), "machine": normalize_machine_id(machine),
               "edition": edition, "issued": (issued or datetime.date.today()).isoformat(),
               "expires": expires.isoformat() if expires else None}
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return PREFIX + _b64e(data) + "." + _b64e(ed25519.sign(secret, data))


def check_key(text, machine=None, today=None, public=None):
    """Valida uma chave. Devolve {"valid", "reason", "workshop", "expires", "edition", "machine"}."""
    out = {"valid": False, "reason": "", "workshop": "", "expires": None, "edition": "", "machine": ""}
    public = public if public is not None else _public_key()
    text = "".join((text or "").split())
    if public is None:
        out["reason"] = tr("O licenciamento ainda não está configurado nesta versão.")
        return out
    if not text.startswith(PREFIX) or "." not in text:
        out["reason"] = tr("Isto não é uma chave de licença do Torqis.")
        return out
    try:
        body, sig = text[len(PREFIX):].split(".", 1)
        data, signature = _b64d(body), _b64d(sig)
    except Exception:
        out["reason"] = tr("A chave está incompleta ou foi mal copiada.")
        return out
    if not ed25519.verify(public, data, signature):
        out["reason"] = tr("A chave não é válida (assinatura errada ou chave alterada).")
        return out
    try:
        payload = json.loads(data.decode())
    except Exception:
        out["reason"] = tr("A chave não é válida.")
        return out
    out.update(workshop=payload.get("workshop", ""), edition=payload.get("edition", ""),
               machine=payload.get("machine", ""))
    if payload.get("expires"):
        out["expires"] = datetime.date.fromisoformat(payload["expires"])
    machine = machine or machine_id()
    if normalize_machine_id(payload.get("machine")) != normalize_machine_id(machine):
        out["reason"] = tr("Esta licença é de outro PC ({other}). O ID deste PC é {machine}.",
                           other=payload.get("machine"), machine=machine)
        return out
    today = today or datetime.date.today()
    if out["expires"] and today > out["expires"]:
        out["reason"] = tr("A licença expirou em {date}.", date=f"{out['expires']:%d/%m/%Y}")
        return out
    out["valid"] = True
    return out


# ----------------------------------------------------------------- ficheiro
def license_dir():
    if DIRECTORY:
        return DIRECTORY
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, DATA_FOLDER)
    os.makedirs(path, exist_ok=True)
    return path


def _path():
    return os.path.join(license_dir(), FILE_NAME)


def stored_key():
    try:
        with open(_path(), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def install(text, machine=None):
    """Valida e guarda a chave. Devolve o resultado de check_key (só guarda se for válida)."""
    r = check_key(text, machine)
    if r["valid"]:
        with open(_path(), "w", encoding="utf-8") as fh:
            fh.write("".join(text.split()) + "\n")
    return r


def remove():
    try:
        os.remove(_path())
    except OSError:
        pass


# ------------------------------------------------------------ período de teste
def _parse_date(text):
    try:
        return datetime.date.fromisoformat(str(text).strip()[:10])
    except (TypeError, ValueError):
        return None


def _use_registry():
    # fora do Windows, nos testes (DIRECTORY) e com definições num ficheiro (RAD_SETTINGS_INI: testes, cópias de
    # desenvolvimento) o início do teste fica só no ficheiro
    return not DIRECTORY and os.name == "nt" and not os.environ.get("RAD_SETTINGS_INI")


def _trial_reg(value=None):
    """Lê (value=None) ou grava o início do teste no registo do utilizador. Só no Windows e fora dos testes."""
    if not _use_registry():
        return None
    try:
        import winreg
        if value is None:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TRIAL_REG_KEY)
            try:
                return str(winreg.QueryValueEx(key, _TRIAL_REG_VALUE)[0])
            finally:
                winreg.CloseKey(key)
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _TRIAL_REG_KEY)
        try:
            winreg.SetValueEx(key, _TRIAL_REG_VALUE, 0, winreg.REG_SZ, value)
        finally:
            winreg.CloseKey(key)
    except OSError:
        return None
    return None


def set_trial_start(date):
    """Grava o início do período de teste (na pasta de dados e no registo)."""
    text = date.isoformat()
    try:
        with open(os.path.join(license_dir(), TRIAL_FILE), "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except OSError as e:
        log.warning("Não foi possível gravar o início do teste: %s", e)
    _trial_reg(text)


def trial_start(today=None):
    """Data do primeiro arranque neste PC (começa hoje se não houver). Fica a mais antiga das duas cópias."""
    today = today or datetime.date.today()
    try:
        with open(os.path.join(license_dir(), TRIAL_FILE), encoding="utf-8") as fh:
            from_file = _parse_date(fh.read())
    except OSError:
        from_file = None
    from_reg = _parse_date(_trial_reg())
    found = [d for d in (from_file, from_reg) if d]
    start = min(found) if found else today
    if start > today:                         # relógio andou para trás ou data mexida: não dá dias a mais
        start = today - datetime.timedelta(days=TRIAL_DAYS)
    if from_file != start or (from_reg != start and _use_registry()):
        set_trial_start(start)
    return start


def trial_days_left(today=None):
    today = today or datetime.date.today()
    return max(0, TRIAL_DAYS - (today - trial_start(today)).days)


def status(machine=None, today=None):
    """Estado actual: {"state": "unconfigured" | "licensed" | "trial" | "demo", "licensed", "message", ...}.
    unconfigured = versão sem chave pública (desenvolvimento): tudo funciona.
    trial = sem chave, dentro do período de teste: tudo funciona ("licensed" True), com "days_left"."""
    if _public_key() is None:
        return {"state": "unconfigured", "licensed": True, "workshop": "", "expires": None,
                "message": tr("Licenciamento não configurado (versão de desenvolvimento).")}
    key = stored_key()
    if not key:
        left = trial_days_left(today)
        if left > 0:
            return {"state": "trial", "licensed": True, "workshop": "", "expires": None, "days_left": left,
                    "message": tr("Período de teste: tudo desbloqueado durante mais {n} dia(s). Depois, sem licença, "
                                  "o programa passa a modo demonstração.", n=left)}
        return {"state": "demo", "licensed": False, "workshop": "", "expires": None,
                "message": tr("Modo demonstração: o período de teste terminou e não há licença activada neste PC.")}
    r = check_key(key, machine, today)
    if not r["valid"]:
        return {"state": "demo", "licensed": False, "workshop": r["workshop"], "expires": r["expires"],
                "message": tr("Modo demonstração: {reason}", reason=r["reason"])}
    if r["expires"]:
        message = tr("Licenciado a {workshop}, válida até {date}.", workshop=r["workshop"],
                     date=f"{r['expires']:%d/%m/%Y}")
    else:
        message = tr("Licenciado a {workshop}, sem data de fim.", workshop=r["workshop"])
    return {"state": "licensed", "licensed": True, "workshop": r["workshop"], "expires": r["expires"],
            "message": message}


def demo_feature_message():
    """Recusa de uma função de leitura que o modo demonstração não inclui."""
    return tr("Modo demonstração: esta função precisa de uma licença. Active a licença em Opções → Licença "
              "(o simulador funciona sem limites).")


def locked_fault(severity="na"):
    """Linha que substitui uma avaria escondida em modo demonstração (mostra que existe, sem dizer qual é)."""
    return {"vag": "🔒 •••••", "pcode": "", "code": None,
            "desc": tr("Avaria oculta no modo demonstração — active a licença para a ver"),
            "elab": "-", "elab_code": 0, "intermittent": False, "status": None, "locked": True,
            "severity": severity}


def redact_faults(faults, free, address=None):
    """Devolve (avarias a mostrar, quantas ficaram livres): as primeiras `free` ficam, as outras são trocadas por
    linhas "avaria oculta" com a mesma gravidade. As OBD-II genéricas (obd_kind) nunca se escondem."""
    from . import fault_advice
    out = []
    for f in faults or []:
        if f.get("obd_kind") or f.get("locked"):
            out.append(f)
        elif free > 0:
            out.append(f)
            free -= 1
        else:
            out.append(locked_fault(fault_advice.advice(f, address)["severity"]))
    return out, free


def redact_items(items, free=None):
    """Itens de Auto-Scan/relatório com as avarias acima do limite gratuito escondidas (cópia; o original fica)."""
    free = FREE_FAULTS if free is None else free
    out = []
    for it in items or []:
        it = dict(it)
        if it.get("faults"):
            it["faults"], free = redact_faults(it["faults"], free, it.get("address"))
        out.append(it)
    return out


def demo_block_message():
    """Mensagem de recusa em modo demonstração (no idioma escolhido). A janela compara com esta função."""
    return tr("Modo demonstração: esta função escreve no veículo e precisa de uma licença. "
              "Active a licença em Opções → Licença (o simulador funciona sem limites).")
