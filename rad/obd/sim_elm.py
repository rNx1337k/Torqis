"""ELM327 simulado (porta "ELM327:SIMULADOR") — SÓ para testes e demonstração.

Imita a porta série de um ELM327 v1.5: comandos AT, eco, prompt ">", procura automática de protocolo e as
respostas do SimVehicle, formatadas como o ELM as mostra com os cabeçalhos ligados.

Barramentos (`bus`), como nos carros reais:
  "can"       ISO 15765-4 CAN 11 bits / 500 kbit/s (tramas ISO-TP com o byte PCI) — a maioria desde ~2004
  "iso9141"   ISO 9141-2, linha K com init a 5 baud (48 6B <ecu> … checksum) — gasolina europeus ~2001–2006
  "kwp5baud"  ISO 14230-4 KWP2000, init a 5 baud (8L F1 <ecu> … checksum)
  "kwp"       ISO 14230-4 KWP2000, init rápido
  "j1850pwm"  SAE J1850 PWM (41 6B <ecu> … CRC) — Ford até ~2007
  "j1850vpw"  SAE J1850 VPW (48 6B <ecu> … CRC) — GM / Chrysler até ~2007
Fora do CAN, as respostas longas vêm em várias mensagens como na norma: avarias 3 por linha com enchimento
00 00 e o modo 09 em blocos de 4 bytes numerados; os modos que só existem em CAN (0A, UDS) não respondem.

Tempos (`timing="real"`): o adaptador demora o que um ELM demora a responder (CAN ~40 ms; linha K ~150 ms e a
procura com init a 5 baud ~4 s; J1850 ~60 ms). Por omissão responde logo, para os testes rápidos.

Defeitos de clones baratos (`clone=True`): diz-se "ELM327 v2.1", não conhece alguns comandos AT opcionais
(responde "?"), ignora o ATE0 (o eco fica ligado) e, com `drop_every=N`, perde de vez em quando uma resposta do
carro (responde "NO DATA" a 1 de cada N pedidos). Também simula: ignição desligada, dispositivo que não é um
ELM327, adaptador que deixa de responder.
"""
import time

from . import isotp
from .simvehicle import SimVehicle

BUS_PROTOCOL = {"can": "6", "j1850pwm": "1", "j1850vpw": "2", "iso9141": "3", "kwp5baud": "4", "kwp": "5"}
PROTOCOL_NAME = {"1": "SAE J1850 PWM", "2": "SAE J1850 VPW", "3": "ISO 9141-2", "4": "ISO 14230-4 (KWP 5BAUD)",
                 "5": "ISO 14230-4 (KWP FAST)", "6": "ISO 15765-4 (CAN 11/500)"}
KLINE = {"3", "4", "5"}
J1850 = {"1", "2"}
ECU_ADDRESS = {0x7E8: 0x10, 0x7E9: 0x18}          # endereço de cada centralina fora do CAN (motor, caixa)
# serviços OBD que existem em linha K e J1850 (o modo 0A e o UDS só existem em CAN)
NON_CAN_SERVICES = {0x01, 0x02, 0x03, 0x04, 0x07, 0x09}
CLONE_UNSUPPORTED = {"@1", "AT1"}                  # AT@1 e ATAT1 (tempos adaptativos): "?" num clone
LATENCY = {"6": 0.04, "1": 0.06, "2": 0.06, "3": 0.15, "4": 0.15, "5": 0.12}
SEARCH = {"6": 1.2, "1": 1.5, "2": 1.5, "3": 4.0, "4": 4.0, "5": 1.5}
LINE_GAP = 0.06                                    # linha K / J1850: intervalo entre mensagens de uma resposta


def j1850_crc(data):
    """CRC-8 do SAE J1850 (polinómio 0x1D, início 0xFF, complemento no fim)."""
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1D) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc ^ 0xFF


def non_can_messages(msg):
    """Uma resposta no formato CAN (mensagem inteira) → as mensagens que o carro manda fora do CAN."""
    sid = msg[0]
    if sid in (0x43, 0x47) and len(msg) >= 2:
        codes = bytes(msg[2:])                        # sem o byte do número de avarias, que só existe em CAN
        chunks = [codes[i:i + 6] for i in range(0, len(codes), 6)] or [b""]
        return [bytes([sid]) + c.ljust(6, b"\0") for c in chunks]
    if sid == 0x49 and len(msg) >= 2:
        it = msg[1]
        if it % 0x20 == 0:                            # PIDs suportados: um bloco com o contador 01
            return [bytes([0x49, it, 0x01]) + bytes(msg[2:6])]
        data = bytes(msg[3:])                         # sem o número de itens
        pad = (-len(data)) % 4
        data = (b"\0" * pad + data) if it == 0x02 else (data + b"\0" * pad)   # o VIN é alinhado à direita
        return [bytes([0x49, it, n + 1]) + data[i:i + 4] for n, i in enumerate(range(0, len(data), 4))]
    return [bytes(msg)]


class SimElm327Serial:
    simulated = True

    def __init__(self, vehicle=None, version=None, mute=False, die_after=None, baud=38400, bus="can",
                 timing="fast", clone=False, drop_every=None, unsupported=None):
        self.vehicle = vehicle or SimVehicle()
        self.clone = clone
        self.version = version or ("ELM327 v2.1" if clone else "ELM327 v1.5")
        self.mute = mute                  # True: nada responde (porta de outro dispositivo)
        self.die_after = die_after        # deixa de responder depois de N comandos (cabo arrancado)
        self.native_baud = baud
        self.baudrate = baud
        self.timeout = 0.05
        self.bus = BUS_PROTOCOL[bus]       # protocolo do carro
        self.real_timing = timing == "real"
        self.drop_every = drop_every
        self.unsupported = set(unsupported if unsupported is not None else (CLONE_UNSUPPORTED if clone else ()))
        self.obd_requests = 0
        self._in = bytearray()
        self._out = bytearray()
        self._later = []                   # (instante em que fica disponível, bytes): tempos de um ELM real
        self.commands = []
        self.closed = False
        self._reset_state()

    def _reset_state(self):
        self.echo = True
        self.headers = False
        self.spaces = True
        self.linefeeds = True
        self.protocol = "0"
        self.active = None                 # protocolo em uso depois da procura
        self.header = 0x7DF

    # ------------------------------------------------------------------ interface pyserial
    def _release(self):
        now = time.monotonic()
        while self._later and self._later[0][0] <= now:
            self._out += self._later.pop(0)[1]

    @property
    def in_waiting(self):
        self._release()
        return len(self._out)

    def reset_input_buffer(self):
        self._release()
        self._out.clear()

    def write(self, data):
        if self.closed:
            raise OSError("porta fechada")
        if self.mute:
            return len(data)
        self._in += data
        while b"\r" in self._in:
            i = self._in.index(b"\r")
            line, self._in = bytes(self._in[:i]), self._in[i + 1:]
            self._handle(line.decode("ascii", "replace").strip())
        return len(data)

    def read(self, n=1):
        if self.closed:
            raise OSError("porta fechada")
        self._release()
        if not self._out:
            time.sleep(min(self.timeout or 0, 0.005))
            return b""
        out, self._out = bytes(self._out[:n]), self._out[n:]
        return out

    def close(self):
        self.closed = True

    # ------------------------------------------------------------------ ELM327
    def _emit(self, *lines, delay=0.0):
        nl = "\r\n" if self.linefeeds else "\r"
        body = ("".join(ln + nl for ln in lines) + nl + ">").encode("ascii")
        if self.real_timing and delay > 0:
            start = max([time.monotonic()] + [t for t, _b in self._later])
            self._later.append((start + delay, body))
        else:
            self._out += body

    def _handle(self, cmd):
        if self.die_after is not None:
            if self.die_after <= 0:
                return                        # deixou de responder
            self.die_after -= 1
        if self.baudrate != self.native_baud:
            self._out += bytes([0xFF, 0x3F])  # lixo: velocidade errada
            return
        self.commands.append(cmd)
        if self.echo and cmd:
            self._out += (cmd + "\r").encode("ascii")
        if not cmd:
            self._out += b">"
            return
        u = cmd.upper().replace(" ", "")
        if u.startswith("AT"):
            return self._at(u[2:])
        try:
            payload = bytes.fromhex(u)
        except ValueError:
            return self._emit("?")
        self._obd(payload)

    def _at(self, c):
        if c in self.unsupported:
            return self._emit("?")
        if c == "Z":
            self._reset_state()
            return self._emit("", self.version, delay=0.5)
        if c == "WS":
            return self._emit("", self.version)
        if c == "I":
            return self._emit(self.version)
        if c == "@1":
            return self._emit("OBDII to RS232 Interpreter (simulado)")
        if c == "RV":
            return self._emit(f"{self.vehicle.battery:.1f}V" if self.vehicle.ignition else "11.9V")
        flags = {"E0": ("echo", False), "E1": ("echo", True), "H0": ("headers", False), "H1": ("headers", True),
                 "S0": ("spaces", False), "S1": ("spaces", True), "L0": ("linefeeds", False),
                 "L1": ("linefeeds", True)}
        if c in flags:
            if not (self.clone and c == "E0"):      # o clone diz OK mas continua a fazer eco
                setattr(self, *flags[c])
            return self._emit("OK")
        if c.startswith("SP") and len(c) == 3:
            self.protocol = c[2]
            self.active = None
            return self._emit("OK")
        if c.startswith("SH"):
            try:
                self.header = int(c[2:], 16)
            except ValueError:
                return self._emit("?")
            return self._emit("OK")
        if c in ("AT0", "AT1", "AT2", "PC", "CAF1", "D"):
            if c == "PC":
                self.active = None
            return self._emit("OK")
        if c == "DPN":
            if self.active is None:
                return self._emit(self.protocol)
            return self._emit(("A" if self.protocol == "0" else "") + self.active)
        if c == "DP":
            if not self.active:
                return self._emit("AUTO")
            return self._emit(("AUTO, " if self.protocol == "0" else "") + PROTOCOL_NAME[self.active])
        return self._emit("?")

    def _fmt(self, bs):
        return (" " if self.spaces else "").join(f"{b:02X}" for b in bs)

    def _frame(self, resp_id, data):
        """Uma mensagem fora do CAN, com cabeçalho e checksum/CRC, como o ELM a mostra com ATH1."""
        src = ECU_ADDRESS.get(resp_id, 0x10 + (resp_id & 0x07))
        if self.active in J1850:
            raw = bytes([0x41 if self.active == "1" else 0x48, 0x6B, src]) + data
            return raw + bytes([j1850_crc(raw)])
        if self.active == "3":
            raw = bytes([0x48, 0x6B, src]) + data
        else:
            raw = bytes([0x80 | len(data), 0xF1, src]) + data
        return raw + bytes([sum(raw) & 0xFF])

    def _obd(self, payload):
        lines = []
        delay = LATENCY.get(self.bus, 0.05)
        if self.active is None:
            want = self.protocol
            if want == "0":
                lines.append("SEARCHING...")
            elif want != self.bus:
                if want in KLINE:
                    return self._emit("BUS INIT: ...ERROR", delay=SEARCH["3"])
                return self._emit("CAN ERROR" if want not in J1850 else "NO DATA", delay=SEARCH["1"])
            elif want in KLINE:
                lines.append("BUS INIT: ...OK")
            if not self.vehicle.ignition:
                if want in KLINE:
                    return self._emit("BUS INIT: ...ERROR", delay=SEARCH[want])
                return self._emit(*lines, "UNABLE TO CONNECT", delay=sum(SEARCH.values()) if want == "0" else 1.0)
            self.active = self.bus
            delay += SEARCH[self.bus] if want == "0" else (SEARCH[self.bus] if want in KLINE else 0)
        self.obd_requests += 1
        if self.drop_every and self.obd_requests > 1 and self.obd_requests % self.drop_every == 0:
            return self._emit(*lines, "NO DATA", delay=delay + 0.3)          # resposta perdida (clone barato)
        can = self.active == "6"
        if not can and payload[:1] and payload[0] not in NON_CAN_SERVICES:
            return self._emit(*lines, "NO DATA", delay=delay)
        answers = self.vehicle.handle(0x7DF if not can else self.header, payload)
        if not answers:
            return self._emit(*lines, "NO DATA", delay=delay)
        for resp_id, msg in answers:
            if not can:
                parts = non_can_messages(msg)
                for data in parts:
                    lines.append(self._fmt(self._frame(resp_id, data) if self.headers else data))
                delay += LINE_GAP * (len(parts) - 1)
                continue
            for fr in isotp.segment(msg, pad=None):
                if self.headers:
                    lines.append(f"{resp_id:03X}" + (" " if self.spaces else "") + self._fmt(fr))
                elif len(msg) <= 7:
                    lines.append(self._fmt(msg))
                    break
                else:
                    lines.append(self._fmt(fr))
        self._emit(*lines, delay=delay)
