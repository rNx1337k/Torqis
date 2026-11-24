"""Classificação dos cabos a partir da lista de dispositivos USB do Windows."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rad import cable

FTDI_COM = {"name": "USB Serial Port (COM5)", "id": "FTDIBUS\\VID_0403+PID_6001+A5\\0000", "status": "OK",
            "cls": "Ports"}
FTDI_USB = {"name": "USB Serial Converter", "id": "USB\\VID_0403&PID_6001\\A5", "status": "OK", "cls": "USB"}
CH340 = {"name": "USB-SERIAL CH340 (COM7)", "id": "USB\\VID_1A86&PID_7523\\5&1", "status": "OK", "cls": "Ports"}
HEX = {"name": "Ross-Tech Direct USB Interface", "id": "USB\\VID_0403&PID_FA24\\RT1", "status": "OK", "cls": "USB"}
NODRV = {"name": "USB Serial", "id": "USB\\VID_1A86&PID_7523\\x", "status": "Error", "cls": ""}
MOUSE = {"name": "Mouse", "id": "USB\\VID_046D&PID_C077\\x", "status": "OK", "cls": "HIDClass"}


def levels(devs, lat=None):
    return [(f["level"], f.get("com")) for f in cable.classify(devs, lat or {})]


def test_ftdi_ready_and_latency():
    assert levels([FTDI_COM, FTDI_USB], {"COM5": 1}) == [("ok", "COM5")]
    assert levels([FTDI_COM, FTDI_USB], {"COM5": 16}) == [("warn", "COM5")]


def test_ftdi_without_vcp():
    assert levels([FTDI_USB]) == [("warn", None)]


def test_ch340_and_missing_driver():
    assert levels([CH340]) == [("ok", "COM7")]
    assert levels([NODRV]) == [("warn", None)]


def test_hex_clone_and_ignored_devices():
    # clone HEX-USB (chip FTDI) sem serviço de driver: pede o WinUSB (ver test_usb_transports)
    assert levels([HEX, MOUSE]) == [("warn", None)]
    assert levels([MOUSE]) == []


def test_autocom_named_correctly():
    dev = {"name": "Autocom CDP+ USB", "id": "USB\\VID_0403&PID_D6DA\\X", "status": "OK", "cls": "USB"}
    f = cable.classify([dev])
    assert f[0]["level"] == "bad" and "Autocom" in f[0]["title"] and "Ross-Tech" not in f[0]["detail"]


def test_slow_ftdi_offers_the_one_click_fix_also_to_the_customer():
    f = cable.classify([FTDI_COM, FTDI_USB], {"COM5": 16})[0]
    assert f["fix"] == "latency" and "Ajustar cabo" in f["detail"]
    p = cable.plain(f)
    assert p["fix"] == "latency" and p["level"] == "warn" and "Ajustar cabo" in p["detail"]
    assert "Latency" not in p["title"] + p["detail"]
    ok = cable.classify([FTDI_COM, FTDI_USB], {"COM5": 1})[0]
    assert "fix" not in ok and cable.plain(ok)["level"] == "ok"


def test_fix_latency_only_touches_slow_cables_and_reports_refusal():
    key5 = cable.FTDI_ENUM + "\\VID_0403+PID_6001+A5\\0000\\Device Parameters"
    key6 = cable.FTDI_ENUM + "\\VID_0403+PID_6001+B6\\0000\\Device Parameters"
    keys = {"COM5": (16, key5), "COM6": (1, key6)}
    calls = []
    assert cable.fix_latency(keys=keys, runner=lambda exe, args: calls.append((exe, args)) or True)
    exe, args = calls[0]
    assert exe == "cmd.exe" and args.startswith("/c reg add ")
    assert f'"HKLM\\{key5}"' in args and key6 not in args
    assert "/v LatencyTimer /t REG_DWORD /d 1 /f" in args
    assert not cable.fix_latency(["COM6"], keys=keys, runner=lambda *a: True)     # já está a 1 ms
    assert not cable.fix_latency(keys=keys, runner=lambda *a: False)              # autorização recusada
    assert not cable.fix_latency(keys=keys, runner=lambda *a: 1 / 0)              # erro: não rebenta


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)


def test_powershell_output_is_read_as_utf8():
    # nomes como "Porta série USB (COM5)" chegavam corrompidos (página de código OEM lida como ANSI)
    calls = []

    class Out:
        stdout = '{"FriendlyName": "Porta série USB (COM5)", "InstanceId": "FTDIBUS\\\\VID_0403+PID_6001+A5\\\\0000"}'

    def fake_run(args, **kw):
        calls.append((args, kw))
        return Out()

    old = cable.subprocess.run
    cable.subprocess.run = fake_run
    try:
        devs = cable.list_usb_devices()
    finally:
        cable.subprocess.run = old
    args, kw = calls[0]
    assert kw.get("encoding") == "utf-8" and "OutputEncoding" in args[-1] and "UTF8" in args[-1]
    assert devs[0]["name"] == "Porta série USB (COM5)"
