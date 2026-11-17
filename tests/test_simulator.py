"""Testes de ponta a ponta dos protocolos contra o simulador (sem Qt, sem carro).

Correr:  python -m pytest tests   ou   python tests/test_simulator.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rad.kline import KLine, SIM_PORT
from rad.session import ECUSession
from rad.errors import NoResponse, RequestRejected


def make(log=None):
    kl = KLine(SIM_PORT, echo="auto", log=log)
    kl.open()
    return kl


def test_engine_kw1281():
    kl = make()
    s = ECUSession(kl)
    info = s.connect(0x01)
    assert info["protocol"] == "KW1281"
    assert info["part"] == "038906019FN"
    assert info["coding"] == 2 and info["wsc"] == 12345
    assert kl.echo is True

    faults = s.read_faults()
    assert [f["vag"] for f in faults] == ["00532", "01247"]
    assert faults[0]["intermittent"] and faults[0]["elab_code"] == 7

    g = s.read_group(1)
    assert len(g["fields"]) == 4
    assert g["fields"][0]["unit"] == "/min"
    assert g["fields"][3]["unit"] == "°C" and 15 <= g["fields"][3]["numeric"] <= 30    # arranque a frio

    try:
        s.read_group(99)
        assert False, "grupo inexistente devia dar NAK"
    except RequestRejected:
        pass
    assert s.connected
    s.keep_alive()

    a = s.adaptation_read(1)
    assert a["value"] == 128
    assert s.adaptation_test(1, 140)["status"] == "ok"
    assert s.adaptation_save(1, 140, 12345)["status"] == "ok"
    assert s.adaptation_read(1)["value"] == 140

    assert s.login(12233, 12345)["status"] == "sent"      # o KW1281 não confirma se o código está certo
    r = s.recode(10002, 54321)
    assert r["status"] == "ok"
    assert r["info"]["coding"] == 10002 and r["info"]["wsc"] == 54321

    steps = []
    while True:
        st = s.output_test()
        if st is None:
            break
        steps.append(st["vag"])
    assert steps == ["01259", "01265", "01247", "00626"]

    # a N75 está com o circuito aberto: volta logo depois de apagar; a 00532 (intermitente) não
    assert [f["vag"] for f in s.clear_faults()] == ["01247"]
    s.disconnect()


def test_cluster_baud_autodetect():
    kl = make()
    s = ECUSession(kl)
    info = s.connect(0x17)
    assert info["baud"] == 9600
    assert info["coding"] == 4211
    assert s.read_faults() == []
    s.disconnect()


def test_abs_kwp2000():
    kl = make()
    s = ECUSession(kl)
    info = s.connect(0x03)
    assert info["protocol"] == "KWP2000"
    assert info["part"] == "1C0907379K"
    faults = s.read_faults()
    assert faults[0]["vag"] == "00283"
    g = s.read_group(1)
    assert g["fields"][0]["unit"] == "km/h"
    s.keep_alive()
    assert s.basic_setting(1)["fields"][0]["unit"] == "km/h"       # ajuste básico (rotina 31 B8/BA 00 <grupo>)
    assert [f["vag"] for f in s.clear_faults()] == ["00283"]           # sensor sem sinal: avaria presente
    s.disconnect()


def test_absent_module():
    kl = make()
    s = ECUSession(kl)
    try:
        s.connect(0x45)
        assert False
    except NoResponse:
        pass


def test_golf_iv_answers_with_all_its_modules():
    kl = make()
    found = {}
    for addr in (0x01, 0x02, 0x03, 0x08, 0x15, 0x17, 0x46, 0x56):
        s = ECUSession(kl)
        info = s.connect(addr)
        found[addr] = (info["part"], [f["vag"] for f in s.read_faults()])
        s.disconnect()
    assert found[0x02][0] == "01M927733JT" and found[0x02][1] == []
    assert found[0x15][1] == ["00588"] and found[0x46][1] == ["01331"]
    assert sum(len(v[1]) for v in found.values()) == 5


def test_engine_warms_up_and_idle_drops():
    kl = make()
    s = ECUSession(kl)
    s.connect(0x01)
    car = kl.ser.car
    cold = s.read_group(1)["fields"]
    car.t0 -= 900                                   # 15 minutos depois
    kl.ser.ecu.t0 = time.monotonic()                # e ao ralenti (o ciclo começa no ralenti)
    warm = s.read_group(1)["fields"]
    assert cold[3]["numeric"] < 30 and 88 <= warm[3]["numeric"] <= 90
    assert cold[0]["numeric"] > warm[0]["numeric"] + 100      # ralenti mais alto a frio
    s.disconnect()


def test_cleared_faults_and_coding_stay_in_the_ecu_memory():
    kl = make()
    s = ECUSession(kl)
    s.connect(0x01)
    s.clear_faults()
    s.recode(10002, 54321)
    s.disconnect()
    s = ECUSession(kl)                              # nova ligação ao mesmo carro
    info = s.connect(0x01)
    assert [f["vag"] for f in s.read_faults()] == ["01247"]    # a intermitente não voltou
    assert info["coding"] == 10002
    s.disconnect()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
