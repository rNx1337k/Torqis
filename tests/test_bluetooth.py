"""Adaptador OBD Bluetooth (ELM327 por perfil de porta série): a porta certa é reconhecida e escolhida, a ligação
abre uma só vez e espera pelas primeiras respostas, e um carro sem CAN na ficha (VAG até ~2004, só linha K) é
explicado logo, em vez de o Auto-Scan tentar todos os controladores. Sem hardware: o adaptador é simulado."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rad import cable, kline  # noqa: E402
from rad.errors import InterfaceError, KLineError  # noqa: E402
from rad.obd import elm327  # noqa: E402
from rad.obd.elm327 import AdapterNotResponding, Elm327Link  # noqa: E402
from rad.obd.sim_elm import SimElm327Serial  # noqa: E402

BT = "{00001101-0000-1000-8000-00805F9B34FB}"
OUT = "BTHENUM\\" + BT + r"_LOCALMFG&0002\7&2D3F11A&0&001D86001F95_C00000000"
IN = "BTHENUM\\" + BT + r"_LOCALMFG&0000\7&2D3F11A&0&000000000000_00000000"


def test_bluetooth_ports_are_told_apart():
    assert kline.bluetooth_kind("Standard Serial over Bluetooth link (COM5)", OUT) == "out"
    assert kline.bluetooth_kind("Ligação série padrão através de Bluetooth (COM6)", IN) == "in"
    assert kline.bluetooth_kind("USB Serial Port (COM3)", "USB VID:PID=0403:6001 SER=A5") is None
    assert "entrada" in kline._friendly_com("COM6", "Bluetooth", None, IN)
    assert kline._friendly_com("COM5", "Bluetooth", None, OUT).startswith("COM5 — Bluetooth")


def test_is_bluetooth_port_uses_the_last_listing():
    old = kline._bt_cache
    kline._bt_cache = {"COM5": ("out", "OBDII"), "COM6": ("in", None)}
    try:
        assert kline.is_bluetooth_port("COM5") and kline.is_bluetooth_port("COM6")
        assert not kline.is_bluetooth_port("COM3") and not kline.is_bluetooth_port("")
        assert kline.bluetooth_ports(refresh=False) == [("COM5", "OBDII")]
    finally:
        kline._bt_cache = old


def test_detect_cable_offers_the_paired_adapter():
    f = cable.bluetooth_findings([("COM5", "OBDII")])[0]
    assert f["com"] == "COM5" and f["level"] == "ok" and f["adapter"] == "elm327" and "OBDII" in f["title"]
    assert cable.plain(f) == f
    assert "Bluetooth em COM8" in cable.bluetooth_findings([("COM8", None)])[0]["title"]
    for name in ("OBDII", "OBD2", "V-LINK", "Android-Vlink", "Vgate iCar Pro", "KONNWEI"):
        assert cable.bluetooth_findings([("COM5", name)]), name
    assert cable.bluetooth_findings([("COM3", "JBL GO")]) == []       # uma coluna não é um cabo


class _SlowStart(SimElm327Serial):
    """Adaptador Bluetooth cuja ligação demora a estabilizar: as primeiras linhas perdem-se."""

    def __init__(self, lost, **kw):
        super().__init__(**kw)
        self.lost = lost

    def write(self, data):
        if self.lost > 0:
            self.lost -= data.count(b"\r")
            return len(data)
        return super().write(data)


def _bt_link(sim, opens):
    def factory(port, baud):
        opens.append(baud)
        return sim
    return Elm327Link("COM5", serial_factory=factory, bluetooth=True, timeout=0.5, search_timeout=1.0)


def test_bluetooth_opens_once_and_waits_for_the_first_answers():
    old = elm327.BT_ANSWER
    elm327.BT_ANSWER = 0.3
    try:
        opens = []
        link = _bt_link(_SlowStart(lost=2), opens)
        d = link.open()
        assert opens == [elm327.BAUDS[0]]                     # não muda de velocidade nem reabre a ligação
        assert d["bluetooth"] and "ELM327" in d["version"]
        assert link.timeout >= elm327.BT_TIMEOUT
        link.connect_vehicle()
        link.close()

        opens = []
        try:
            _bt_link(SimElm327Serial(mute=True), opens).open()
            raise AssertionError("um adaptador mudo não pode passar")
        except AdapterNotResponding as e:
            assert "Bluetooth" in str(e) and "escolha a outra" in str(e)
        assert opens == [elm327.BAUDS[0]]
    finally:
        elm327.BT_ANSWER = old


def test_bluetooth_port_that_does_not_connect_is_explained():
    def factory(port, baud):
        raise OSError("O tempo limite do semáforo expirou.")
    try:
        Elm327Link("COM5", serial_factory=factory, bluetooth=True).open()
        raise AssertionError("tinha de falhar")
    except KLineError as e:
        assert "Bluetooth" in str(e) and "telemóvel" in str(e)


def test_vag_controllers_on_a_car_without_can_stop_at_once():
    """Audi A3 8L / Golf IV: o ELM327 responde CAN ERROR (ninguém confirma as tramas)."""
    from rad.vagcan.elmcan import ElmCanBus, NoCanBus
    from rad.vagcan.kwp import VagCanKWP
    from tests.test_vagcan import FakeElmRawCan
    from rad.vagcan.simbus import SimVagCanBus

    class NoCan(FakeElmRawCan):
        def write(self, data):
            up = data.decode("ascii").strip().upper()
            if up and not up.startswith("AT") and not self.monitoring:
                self.commands.append(up)
                self.out += b"CAN ERROR\r\r>"
                return len(data)
            return super().write(data)

    fake = NoCan(SimVagCanBus())
    bus = ElmCanBus("COM5", serial_factory=lambda port, baud: fake)
    bus.open()
    try:
        VagCanKWP(bus, 0x01).start()
        raise AssertionError("tinha de falhar")
    except NoCanBus as e:
        assert isinstance(e, InterfaceError)                  # o Auto-Scan pára em vez de tentar os outros
        assert "linha K" in str(e) and "OBD" in str(e)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
