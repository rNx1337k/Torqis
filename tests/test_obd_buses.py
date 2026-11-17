"""OBD-II fora do CAN e adaptadores imperfeitos, contra o ELM327 simulado: linha K (ISO 9141-2, ISO 14230-4
com init a 5 baud e rápido), SAE J1850 PWM/VPW, tempos de resposta de um ELM real e os defeitos dos clones
baratos. Sem hardware nem Qt; o veículo simulado é fictício (VIN RADSML…).

Correr:  python tests/test_obd_buses.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rad.errors import NoResponse  # noqa: E402
from rad.obd.elm327 import ELM_SIM_PORT, Elm327Link  # noqa: E402
from rad.obd.j1979 import Obd2  # noqa: E402
from rad.obd.link import NegativeResponse  # noqa: E402
from rad.obd.sim_elm import SimElm327Serial, j1850_crc, non_can_messages  # noqa: E402
from rad.obd.simvehicle import SIM_VIN, SimVehicle  # noqa: E402

NON_CAN = {"iso9141": "3", "kwp5baud": "4", "kwp": "5", "j1850pwm": "1", "j1850vpw": "2"}


def _elm(vehicle=None, timeout=1.0, search_timeout=1.0, protocol="0", **kw):
    sim = SimElm327Serial(vehicle or SimVehicle(), **kw)
    link = Elm327Link(ELM_SIM_PORT, serial_factory=lambda port, baud: sim, timeout=timeout,
                      search_timeout=search_timeout, protocol=protocol)
    return link, sim


def _connected(vehicle=None, **kw):
    link, sim = _elm(vehicle, **kw)
    link.open()
    link.connect_vehicle()
    obd = Obd2(link)
    obd.discover()
    return link, sim, obd


def test_j1850_crc_matches_the_published_example():
    # valor de verificação do catálogo de CRC (CRC-8/SAE-J1850): "123456789" → 0x4B
    assert j1850_crc(b"123456789") == 0x4B


def test_non_can_formats_follow_the_norm():
    # avarias: 3 por mensagem, com enchimento 00 00, sem o byte do número de avarias (que só existe em CAN)
    msgs = non_can_messages(bytes([0x43, 4, 0x04, 0x01, 0x20, 0x02, 0x03, 0x00, 0x01, 0x71]))
    assert msgs == [bytes([0x43, 0x04, 0x01, 0x20, 0x02, 0x03, 0x00]), bytes([0x43, 0x01, 0x71, 0, 0, 0, 0])]
    assert non_can_messages(bytes([0x43, 0])) == [bytes([0x43, 0, 0, 0, 0, 0, 0])]
    # VIN: 5 blocos de 4 bytes numerados, alinhado à direita (3 bytes 00 no início)
    vin = non_can_messages(bytes([0x49, 0x02, 0x01]) + SIM_VIN.encode())
    assert len(vin) == 5 and [m[2] for m in vin] == [1, 2, 3, 4, 5] and vin[0][3:6] == b"\0\0\0"


def test_every_non_can_bus_reads_everything_a_workshop_needs():
    for bus, proto in NON_CAN.items():
        v = SimVehicle(engine_running=True)
        v.engine.stored = ["P0401", "P2002", "P0299", "P0171"]       # 4 avarias: obriga a 2 mensagens
        link, sim, obd = _connected(v, bus=bus)
        assert link.proto == proto and not link.is_can, bus
        assert list(obd.supported) == ["10", "18"], (bus, obd.supported)    # motor e caixa
        assert obd.primary_ecu() == "10"
        assert obd.vin() == (SIM_VIN, "10"), bus
        assert obd.ecu_names()["10"] == "ECM-EngineControl", bus
        vals = obd.read_pids([0x0C, 0x05, 0x42])
        assert 700 < vals[0x0C]["numeric"] < 1000 and vals[0x42]["value"] == 14.1, (bus, vals)
        assert obd.read_dtcs("stored") == {"10": ["P0401", "P2002", "P0299", "P0171"], "18": []}, bus
        try:
            obd.read_dtcs("permanent")                               # o modo 0A só existe em CAN
            raise AssertionError(f"{bus}: o modo 0A não existe fora do CAN")
        except Exception as e:
            assert type(e).__name__ == "NotSupported", (bus, e)
        try:
            obd.clear_dtcs()                                         # motor a trabalhar → recusa
            raise AssertionError("tinha de recusar")
        except NegativeResponse as e:
            assert e.nrc == 0x22
        v.engine_running = False
        assert set(obd.clear_dtcs()) == {"10", "18"}, bus
        assert obd.read_dtcs("stored") == {"10": [], "18": []}, bus


def test_kline_bus_with_ignition_off_says_bus_init_error():
    link, _ = _elm(SimVehicle(ignition=False), bus="iso9141", protocol="3")
    link.open()
    try:
        link.connect_vehicle()
        raise AssertionError("sem ignição não pode ligar")
    except NoResponse as e:
        assert "ignição" in str(e)


def test_forcing_can_on_a_kline_car_fails_with_an_explanation():
    link, _ = _elm(bus="iso9141", protocol="6")
    link.open()
    try:
        link.connect_vehicle()
        raise AssertionError("CAN forçado num carro de linha K não pode ligar")
    except NoResponse as e:
        assert "CAN" in str(e)


def test_real_adapter_timing_is_within_the_program_timeouts():
    """Com os tempos de um ELM real (procura com init a 5 baud ~4 s, ~150 ms por pedido na linha K) e os
    tempos de espera do programa (os de origem do Elm327Link), tudo funciona — e demora o que deve demorar."""
    for bus, min_search in (("iso9141", 4.0), ("can", 1.2)):
        sim = SimElm327Serial(SimVehicle(engine_running=True), bus=bus, timing="real")
        link = Elm327Link(ELM_SIM_PORT, serial_factory=lambda port, baud, s=sim: s)
        link.open()
        t = time.monotonic()
        link.connect_vehicle()
        assert time.monotonic() - t >= min_search, bus
        obd = Obd2(link)
        obd.discover()
        t = time.monotonic()
        vals = obd.read_pids([0x0C])
        took = time.monotonic() - t
        assert vals[0x0C]["numeric"] > 0 and took >= (0.15 if bus == "iso9141" else 0.04), (bus, took)
        link.close()


def test_cheap_clone_with_echo_stuck_on_and_missing_commands():
    link, sim, obd = _connected(SimVehicle(engine_running=True), clone=True)
    assert link.version == "ELM327 v2.1"
    assert sim.echo is True                                  # disse OK ao ATE0, mas o eco continua
    assert "ATAT1" in sim.commands and link.device is None    # comandos opcionais recusados sem estragar nada
    assert obd.vin() == (SIM_VIN, "7E8")
    assert obd.read_dtcs("stored")["7E8"] == ["P0401", "P2002"]
    assert obd.read_pids([0x0C])[0x0C]["numeric"] > 0
    link, sim, obd = _connected(SimVehicle(engine_running=True), bus="kwp", clone=True)
    assert obd.vin() == (SIM_VIN, "10") and obd.read_dtcs("stored")["10"] == ["P0401", "P2002"]


def test_clone_that_loses_answers_is_asked_again():
    """Um clone que perde 1 resposta em cada 3: o programa pergunta outra vez e nada se perde — nem PIDs na
    procura inicial, nem avarias, nem valores em tempo real."""
    v = SimVehicle(engine_running=True)
    ref_link, _ref_sim, ref = _connected(SimVehicle(engine_running=True))
    link, sim, obd = _connected(v, clone=True, drop_every=3)
    assert obd.supported == ref.supported                      # nenhum PID perdido na procura
    assert obd.read_dtcs("stored") == {"7E8": ["P0401", "P2002"], "7E9": []}
    asked = sim.obd_requests
    for _ in range(12):
        vals = obd.read_pids([0x0C, 0x05])
        assert all("error" not in r for r in vals.values()), vals
    assert sim.obd_requests > asked + 12                       # houve pedidos repetidos
    link, sim, obd = _connected(SimVehicle(), bus="iso9141")
    try:
        obd.read_dtcs("permanent")                             # "NO DATA" a sério: repete uma vez e desiste
        raise AssertionError("o modo 0A não existe na linha K")
    except Exception as e:
        assert type(e).__name__ == "NotSupported"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
