"""Carros do simulador (Opções → Carro do simulador): cada carro tem de aparecer igual nos três simuladores —
cabo VAG (linha K), VAG por CAN e adaptador OBD — e com o que esse carro tem na realidade.

Correr:  python tests/test_simcars.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APPDATA", tempfile.mkdtemp())
os.environ.setdefault("RAD_SETTINGS_INI", os.path.join(tempfile.mkdtemp(), "s.ini"))

from rad import simcars, simulator  # noqa: E402
from rad.errors import NoResponse  # noqa: E402
from rad.kline import KLine, SIM_PORT  # noqa: E402
from rad.obd.elm327 import ELM_SIM_PORT, Elm327Link  # noqa: E402
from rad.obd.j1979 import Obd2  # noqa: E402
from rad.session import ECUSession  # noqa: E402
from rad.vagcan.simbus import SimVagCanBus  # noqa: E402

VAG_ADDRESSES = (0x01, 0x02, 0x03, 0x08, 0x15, 0x17, 0x46, 0x56)


def _with_car(key, fn, clone=False):
    saved = {k: os.environ.get(k) for k in (simcars.ENV, simcars.ADAPTER_ENV)}
    simcars.apply(key, clone=clone)
    try:
        return fn()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _kline_modules():
    kl = KLine(SIM_PORT)
    kl.open()
    found = {}
    for addr in VAG_ADDRESSES:
        s = ECUSession(kl)
        try:
            s.connect(addr)
        except NoResponse:
            continue
        found[addr] = [f["vag"] for f in s.read_faults()]
        s.disconnect()
    kl.close()
    return found


def _obd():
    sim = simcars.elm_serial(timing="fast")
    link = Elm327Link(ELM_SIM_PORT, serial_factory=lambda port, baud: sim, timeout=1.0, search_timeout=1.0)
    link.open()
    try:
        link.connect_vehicle()
    except NoResponse as e:
        return None, str(e), sim
    obd = Obd2(link)
    obd.discover()
    return link, obd, sim


def test_catalogue_matches_the_simulator():
    assert set(simcars.CARS) - {simcars.AUTO} == set(simulator.CARS)
    assert [k for k, _n, _d in simcars.choices()][0] == simcars.AUTO


def test_apply_sets_and_clears_the_environment():
    env = {}
    simcars.apply("golf5_can", clone=True, environ=env)
    assert env == {simcars.ENV: "golf5_can", simcars.ADAPTER_ENV: "clone"}
    assert simcars.current(env) == "golf5_can"
    simcars.apply(simcars.AUTO, environ=env)
    assert env == {} and simcars.current(env) == simcars.AUTO
    simcars.apply("não existe", environ=env)
    assert env == {}


def test_golf_iv_on_every_simulator():
    def run():
        mods = _kline_modules()
        assert sorted(mods) == list(VAG_ADDRESSES) and sum(len(f) for f in mods.values()) == 5
        assert SimVagCanBus().profiles == {}                     # o Golf IV não tem diagnóstico por CAN
        link, err, _sim = _obd()
        assert link is None and "cabo VAG" in err                # nem OBD normal: o programa explica
    _with_car("golf4_tdi", run)


def test_repaired_golf_iv_has_no_faults():
    def run():
        mods = _kline_modules()
        assert sorted(mods) == list(VAG_ADDRESSES) and all(f == [] for f in mods.values())
    _with_car("golf4_clean", run)


def test_golf_v_is_can_only():
    def run():
        assert _kline_modules() == {}                            # o cabo KKL não encontra nada
        assert 0x01 in SimVagCanBus().profiles and 0x19 in SimVagCanBus().profiles
        link, obd, _sim = _obd()
        assert link.is_can and obd.read_dtcs("stored")["7E8"] == ["P0401", "P2002"]
    _with_car("golf5_can", run)


def test_petrol_cars_on_other_buses():
    for key, proto, ecus, dtcs in (("eobd_kline", "3", ["10"], ["P0171"]),
                                   ("eobd_kwp", "5", ["10"], ["P0420"]),
                                   ("us_j1850", "1", ["10", "18"], ["P0420", "P0442"])):
        def run():
            assert _kline_modules() == {} and SimVagCanBus().profiles == {}
            link, obd, _sim = _obd()
            assert link.proto == proto, key
            assert list(obd.supported) == ecus, (key, obd.supported)
            assert obd.read_dtcs("stored")["10"] == dtcs, key
            vals = obd.read_pids([0x51, 0x07, 0x0E])
            assert vals[0x51]["value"] == "Gasolina", (key, vals)
            assert "error" not in vals[0x07] and "error" not in vals[0x0E], (key, vals)
            mon = obd.monitor_status()["10"]
            assert "gasolina" in mon["ignition"] and mon["mil"], (key, mon)
        _with_car(key, run)


def test_lean_mixture_shows_in_the_fuel_trim():
    def run():
        link, obd, sim = _obd()
        sim.vehicle.engine_running = True
        assert obd.read_pids([0x07])[0x07]["numeric"] > 20      # P0171: correcção longa muito positiva
    _with_car("eobd_kline", run)


def test_clone_adapter_choice():
    def run():
        link, obd, sim = _obd()
        assert sim.clone and link.version == "ELM327 v2.1" and obd.vin()[0]
    _with_car("golf5_can", run, clone=True)


def test_j2534_bridge_in_another_process_follows_the_choice():
    from rad import j2534

    def connect_abs():
        link = j2534.J2534Link("J2534:SIMULADOR-J2534")
        link.open()
        try:
            s = ECUSession(link)
            s.connect(0x03)
            faults = [f["vag"] for f in s.read_faults()]
            s.disconnect()
            return faults
        except NoResponse:
            return None
        finally:
            link.close()
    assert _with_car("golf4_tdi", connect_abs) == ["00283"]
    assert _with_car("golf5_can", connect_abs) is None          # carro só CAN: ninguém responde na linha K


def test_default_keeps_every_simulator_as_before():
    def run():
        assert sorted(_kline_modules()) == list(VAG_ADDRESSES)
        assert 0x01 in SimVagCanBus().profiles
        link, obd, _sim = _obd()
        assert link.is_can and list(obd.supported) == ["7E8", "7E9"]
    _with_car(simcars.AUTO, run)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
