"""Carros do simulador (Opções → Carro do simulador) — SÓ para experimentar e testar sem carro.

Cada carro decide o que respondem os três simuladores: o cabo VAG (linha K, rad/simulator.py), o VAG por CAN
(rad/vagcan/simbus.py) e o adaptador OBD (rad/obd/sim_elm.py). Um carro de outra marca não tem nada no cabo VAG,
e um Golf IV não tem diagnóstico por CAN — como na realidade, para o programa ser testado também nesses casos.
Os carros são fictícios (números de peça plausíveis, VIN a começar por RADSML) e tudo o que mostram é sempre
identificado como simulação.

A escolha passa aos simuladores pela variável de ambiente RAD_SIM_CAR, que também chega às pontes J2534 e
D2XX (outro processo). Sem escolha ("auto"), cada simulador mantém o seu carro de sempre.
"""
import os

from . import simulator
from .i18n import tr_data

AUTO = "auto"
ENV = simulator.CAR_ENV
ADAPTER_ENV = "RAD_SIM_ELM"            # "clone": o adaptador OBD simulado porta-se como um clone barato

# chave → (nome, o que tem). Os textos estão em português e passam pelo tr_data() quando se mostram.
CARS = {
    AUTO: ("Automático", "Golf IV no cabo VAG, Golf V no VAG por CAN e um diesel com avarias no adaptador OBD"),
    "golf4_tdi": ("VW Golf IV 1.9 TDI (2002)", "8 controladores na linha K, 5 avarias; não tem OBD normal"),
    "golf4_clean": ("VW Golf IV 1.9 TDI sem avarias", "O mesmo carro, depois de reparado: nenhuma avaria"),
    "golf5_can": ("VW Golf V 2.0 TDI (2006)", "Só CAN: controladores VAG por CAN e OBD em CAN; o cabo VAG não "
                                              "encontra nada"),
    "eobd_kline": ("Gasolina europeu (2003), OBD por linha K", "ISO 9141-2, só a centralina do motor, mistura "
                                                               "pobre (P0171)"),
    "eobd_kwp": ("Gasolina europeu (2005), OBD por KWP2000", "ISO 14230-4 com init rápido, catalisador (P0420)"),
    "us_j1850": ("Gasolina americano (2004), OBD J1850", "SAE J1850 PWM, motor e caixa automática, catalisador "
                                                         "e fuga EVAP"),
}
assert set(CARS) - {AUTO} == set(simulator.CARS), "rad/simulator.py e rad/simcars.py têm de ter os mesmos carros"

# adaptador OBD de cada carro: barramento e veículo (rad.obd.simvehicle.SimVehicle)
_OBD = {
    AUTO: {"bus": "can", "vehicle": {}},
    "golf4_tdi": {"bus": None},                                     # sem OBD normal: o adaptador não liga
    "golf4_clean": {"bus": None},
    "golf5_can": {"bus": "can", "vehicle": {}},
    "eobd_kline": {"bus": "iso9141", "vehicle": {"fuel": "petrol", "stored": ["P0171"], "pending": ["P0300"],
                                                 "tcm": False, "ltft": 21.9, "uds": False}},
    "eobd_kwp": {"bus": "kwp", "vehicle": {"fuel": "petrol", "stored": ["P0420"], "tcm": False, "uds": False}},
    "us_j1850": {"bus": "j1850pwm", "vehicle": {"fuel": "petrol", "stored": ["P0420", "P0442"],
                                                "pending": ["P0455"], "uds": False}},
}


def current(environ=None):
    key = (environ if environ is not None else os.environ).get(ENV) or AUTO
    return key if key in CARS else AUTO


def apply(key, clone=False, environ=None):
    """Põe a escolha nas variáveis de ambiente (os simuladores lêem-nas quando se ligam)."""
    env = os.environ if environ is None else environ
    if key == AUTO or key not in CARS:
        env.pop(ENV, None)
    else:
        env[ENV] = key
    if clone:
        env[ADAPTER_ENV] = "clone"
    else:
        env.pop(ADAPTER_ENV, None)


def choices():
    """[(chave, nome, descrição)] traduzidos, para a lista das Opções."""
    return [(k, tr_data(n), tr_data(d)) for k, (n, d) in CARS.items()]


def elm_serial(environ=None, timing="real"):
    """O ELM327 simulado do carro escolhido, com os tempos de um adaptador real (timing="fast" nos testes)."""
    from .obd.sim_elm import SimElm327Serial
    from .obd.simvehicle import SimVehicle
    env = os.environ if environ is None else environ
    cfg = _OBD[current(env)]
    clone = env.get(ADAPTER_ENV) == "clone"
    extra = {"clone": True, "drop_every": 15} if clone else {}   # o clone perde 1 resposta em cada 15
    if cfg["bus"] is None:                    # carro sem OBD normal: o adaptador funciona, o carro não responde
        return SimElm327Serial(SimVehicle(ignition=False), timing=timing, **extra)
    return SimElm327Serial(SimVehicle(**cfg["vehicle"]), bus=cfg["bus"], timing=timing, **extra)
