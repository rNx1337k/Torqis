"""Opções: interface, oficina e ferramentas de suporte."""
import datetime
import logging
import os
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QScrollArea, QTabWidget, QVBoxLayout, QWidget,
)

from ... import APP_NAME, VERSION, i18n, licensing, simcars, technician_mode, updates
from ...kline import list_serial_ports
from ...settings import ui_scale
from ..style import BAD, MUTED, OK, WARN
from .common import lbl, btn, card
from ...i18n import tr

log = logging.getLogger(__name__)


FORM_LABEL_WIDTH = 170
MISSING_ROLE = Qt.UserRole + 1            # porta guardada que não está ligada agora


def _align_form(form):
    """Coluna das etiquetas com largura fixa e etiquetas centradas na vertical com o campo."""
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    form.setHorizontalSpacing(16)
    for row in range(form.rowCount()):
        item = form.itemAt(row, QFormLayout.LabelRole)
        field = form.itemAt(row, QFormLayout.FieldRole)
        if item is not None and item.widget() is not None:
            label = item.widget()
            label.setMinimumWidth(FORM_LABEL_WIDTH)
            if field is not None:                  # a etiqueta com a altura do campo, centrada com ele
                label.setMinimumHeight(min(field.sizeHint().height(), 48))
                label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

class _CheckRow(QWidget):
    """Uma linha da lista "Antes de ligar ao carro": marca (✔ ! ✖ ○), o passo, o pormenor e um botão opcional."""

    MARKS = {"ok": ("✔", OK), "warn": ("!", WARN), "bad": ("✖", BAD), "todo": ("○", MUTED), "info": ("•", MUTED)}

    def __init__(self, title, button=None):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(12)
        self.mark = lbl("○")
        self.mark.setFixedWidth(22)
        self.mark.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        h.addWidget(self.mark, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.title = lbl(title)
        self.title.setStyleSheet("font-weight: 600;")
        self.detail = lbl("", "muted", wrap=True)
        col.addWidget(self.title)
        col.addWidget(self.detail)
        h.addLayout(col, 1)
        self.button = button
        if button is not None:
            h.addWidget(button, 0, Qt.AlignVCenter)
        self.state = "todo"

    def set(self, state, detail=""):
        self.state = state
        mark, color = self.MARKS[state]
        self.mark.setText(mark)
        self.mark.setStyleSheet(f"color: {color}; font-weight: 800; font-size: 12pt;")
        self.detail.setText(detail)


class OptionsPage(QWidget):
    saved = Signal(dict)
    test_req = Signal()
    link_check_req = Signal()
    hex_mode_req = Signal(str)
    coverage_req = Signal()
    detect_done = Signal(object)          # resultado da procura do cabo (vem de uma thread à parte)
    license_changed = Signal()
    update_done = Signal(object, bool)    # (resultado ou excepção, procura manual?) — vem de uma thread à parte
    update_found = Signal(dict)
    capture_req = Signal(bool)            # gravar a comunicação: True começa, False pára
    validation_req = Signal()             # abrir a validação no carro (modo técnico)
    replay_done = Signal(object, str)     # resultado da verificação de uma gravação (vem de uma thread à parte)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._license_state = None
        self._findings = None             # resultado do último Detectar cabo (None: ainda não se procurou)
        self._latency_fixed = False
        # Opções avançadas da comunicação (velocidade, eco, protocolo, modo do cabo, registo detalhado,
        # compatibilidade): só no modo técnico. O cliente vê apenas o equipamento e a porta.
        self.technical = technician_mode()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 26, 32, 20)
        outer.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(lbl(tr("Opções"), "h1"))
        head.addStretch(1)
        head.addWidget(btn(tr("Guardar"), "primary", self._save), 0, Qt.AlignVCenter)
        outer.addLayout(head)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        def tab(title):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            body = QWidget()
            scroll.setWidget(body)
            lay = QVBoxLayout(body)
            lay.setContentsMargins(18, 18, 18, 18)
            lay.setSpacing(14)
            self.tabs.addTab(scroll, title)
            return lay

        # ================================================================ Cabo
        v = tab(tr("Cabo"))
        # --- estado do cabo: o que está escolhido e se está pronto
        st = card()
        sl = QHBoxLayout(st)
        sl.setContentsMargins(20, 16, 18, 16)
        sl.setSpacing(14)
        sv = QVBoxLayout()
        sv.setSpacing(2)
        self.cable_title = lbl("—", "h2")
        self.cable_sub = lbl("", "muted", wrap=True)
        sv.addWidget(self.cable_title)
        sv.addWidget(self.cable_sub)
        sl.addLayout(sv, 1)
        self.detect_btn = btn(tr("Detectar cabo"), "primary", self._detect_cable)
        self.detect_btn.setMinimumHeight(40)
        sl.addWidget(self.detect_btn, 0, Qt.AlignVCenter)
        v.addWidget(st)

        c = card()
        f = QFormLayout(c)
        f.setContentsMargins(20, 16, 20, 16)
        f.setVerticalSpacing(12)
        self.adapter = QComboBox()
        for t, d in [(tr("Cabo VAG — VW, Audi, Seat, Škoda até ~2005"), "kline"),
                     (tr("Adaptador OBD — VAG desde ~2004 e todas as marcas"), "elm327")]:
            self.adapter.addItem(t, d)
        self.adapter.currentIndexChanged.connect(self._adapter_changed)
        f.addRow(lbl(tr("Equipamento"), "muted"), self.adapter)
        prow = QHBoxLayout()
        self.port = QComboBox()
        self.port.setMinimumWidth(240)
        prow.addWidget(self.port, 1)
        prow.addWidget(btn(tr("Actualizar"), None, self.refresh_ports))
        f.addRow(lbl(tr("Porta do cabo"), "muted"), prow)
        self.port.currentIndexChanged.connect(self._port_changed)
        v.addWidget(c)

        # --- antes de ligar ao carro: o que já está confirmado e o que falta
        ck = card()
        cv = QVBoxLayout(ck)
        cv.setContentsMargins(20, 16, 20, 16)
        cv.setSpacing(10)
        cv.addWidget(lbl(tr("Antes de ligar ao carro"), "h2"))
        self.chk_cable = _CheckRow(tr("Cabo ligado ao PC e reconhecido"))
        self.chk_speed = _CheckRow(tr("Cabo ajustado para ler depressa"),
                                   btn(tr("Ajustar cabo"), None, lambda: self._fix_latency(self._slow_coms())))
        self.chk_car = _CheckRow(tr("Cabo na tomada OBD do carro e ignição ligada"))
        self.chk_car.set("info", tr("O motor pode estar desligado. A tomada fica por baixo do volante."))
        self.chk_test = _CheckRow(tr("Testar a ligação ao carro"),
                                  btn(tr("Testar ligação ao carro"), None, lambda: self.link_check_req.emit()))
        self.chk_test.set("info", tr("Mostra passo a passo até onde a ligação chega e o que fazer se parar."))
        for row in (self.chk_cable, self.chk_speed, self.chk_car, self.chk_test):
            cv.addWidget(row)
        self.chk_speed.hide()
        trow = QHBoxLayout()
        trow.setSpacing(8)
        trow.addWidget(btn(tr("Testar só o cabo"), None, self._test))
        if self.technical:
            trow.addWidget(btn(tr("Compatibilidade"), None, lambda: self.coverage_req.emit()))
        trow.addStretch(1)
        cv.addLayout(trow)
        v.addWidget(ck)

        # --- simulador: experimentar sem carro
        self.sim_box = card()
        smf = QFormLayout(self.sim_box)
        smf.setContentsMargins(20, 16, 20, 16)
        smf.setVerticalSpacing(10)
        smf.addRow(lbl(tr("Experimentar sem carro"), "h2"))
        self.sim_car = QComboBox()
        for key, name, desc in simcars.choices():
            self.sim_car.addItem(name, key)
            self.sim_car.setItemData(self.sim_car.count() - 1, desc, Qt.ToolTipRole)
        self.sim_car.currentIndexChanged.connect(self._sim_car_changed)
        self.sim_car_lbl = lbl(tr("Carro do simulador"), "muted")
        smf.addRow(self.sim_car_lbl, self.sim_car)
        self.sim_car_desc = lbl("", "muted", wrap=True)
        smf.addRow(QLabel(), self.sim_car_desc)
        self.sim_clone = QCheckBox(tr("Adaptador OBD simulado como um clone barato (lento, sem alguns comandos, "
                                      "perde respostas)"))
        smf.addRow(QLabel(), self.sim_clone)
        if not self.technical:
            smf.setRowVisible(self.sim_clone, False)
        simrow = QHBoxLayout()
        simrow.setSpacing(8)
        simrow.addWidget(btn(tr("Usar simulador VAG"), None, lambda: self.select_simulator("kline")))
        simrow.addWidget(btn(tr("Usar simulador OBD"), None, lambda: self.select_simulator("elm327")))
        simrow.addStretch(1)
        smf.addRow(QLabel(), simrow)
        v.addWidget(self.sim_box)

        # --- avançado (modo técnico): velocidade, eco, protocolo, registo detalhado, modo do cabo HEX
        self.adv_btn = btn(tr("Avançado ▸"), "ghost", self._toggle_advanced)
        self.adv_btn.setStyleSheet("QPushButton#ghost { text-align: left; padding-left: 4px; }")
        v.addWidget(self.adv_btn, 0, Qt.AlignLeft)
        self.adv_box = card()
        f = QFormLayout(self.adv_box)
        f.setContentsMargins(20, 16, 20, 16)
        f.setVerticalSpacing(12)
        self.elm_proto = QComboBox()
        for t, d in [(tr("Automático (o adaptador procura)"), "0"), (tr("ISO 15765-4 CAN 11 bits 500k"), "6"),
                     (tr("ISO 15765-4 CAN 29 bits 500k"), "7"), (tr("ISO 15765-4 CAN 11 bits 250k"), "8"),
                     (tr("ISO 15765-4 CAN 29 bits 250k"), "9"), (tr("ISO 14230-4 KWP rápido"), "5"),
                     (tr("ISO 14230-4 KWP 5 baud"), "4"), (tr("ISO 9141-2"), "3"), (tr("SAE J1850 VPW"), "2"),
                     (tr("SAE J1850 PWM"), "1")]:
            self.elm_proto.addItem(t, d)
        self.elm_proto_lbl = lbl(tr("Protocolo OBD"), "muted")
        f.addRow(self.elm_proto_lbl, self.elm_proto)
        self.baud = QComboBox()
        for t, d in [(tr("Automática"), "auto"), ("10400", "10400"), ("9600", "9600"), ("4800", "4800")]:
            self.baud.addItem(t, d)
        f.addRow(lbl(tr("Velocidade"), "muted"), self.baud)
        self.echo = QComboBox()
        for t, d in [(tr("Automático"), "auto"), (tr("Com eco (KKL normal)"), "on"), (tr("Sem eco"), "off")]:
            self.echo.addItem(t, d)
        f.addRow(lbl(tr("Eco da linha K"), "muted"), self.echo)
        self.raw = QCheckBox(tr("Registo detalhado: todos os blocos e bytes (para enviar quando houver problemas)"))
        f.addRow(lbl(tr("Debug"), "muted"), self.raw)
        hrow = QHBoxLayout()
        hrow.setSpacing(8)
        hrow.addWidget(btn(tr("Ler modo do cabo"), None, lambda: self._hex("read")))
        hrow.addWidget(btn(tr("Repor modo inteligente"), None, lambda: self._hex("smart")))
        hrow.addStretch(1)
        self.hex_lbl = lbl(tr("Cabo HEX"), "muted")
        f.addRow(self.hex_lbl, hrow)
        self._form, self._hex_row = f, hrow
        v.addWidget(self.adv_box)
        self.adv_box.hide()
        self.adv_btn.setVisible(self.technical)
        v.addWidget(lbl(tr("Cabo VAG: VW, Audi, Seat e Škoda até ~2005. Adaptador OBD (de preferência um "
                           "OBDLink): VAG de ~2004 em diante e avarias de qualquer marca na página OBD."),
                        "muted", wrap=True))
        v.addStretch(1)
        forms = [smf, self._form]
        cable_form = c.layout()

        # ================================================================ Oficina
        v = tab(tr("Oficina"))
        wc = card()
        wf = QFormLayout(wc)
        wf.setContentsMargins(20, 18, 20, 18)
        wf.setVerticalSpacing(10)
        wf.addRow(lbl(tr("Dados da oficina"), "h2"))
        wf.addRow(lbl(tr("Aparecem no cabeçalho do relatório para o cliente."), "muted"))
        self.ws_edits = {}
        for key, name in [("name", tr("Nome da oficina")), ("address", tr("Morada")), ("phone", tr("Telefone")),
                          ("email", tr("Email")), ("nif", tr("NIF"))]:
            e = QLineEdit()
            e.setPlaceholderText(name)
            self.ws_edits[key] = e
            wf.addRow(lbl(name, "muted"), e)
        lrow = QHBoxLayout()
        self.ws_logo_preview = QLabel()
        self.ws_logo_preview.setFixedSize(150, 60)
        self.ws_logo_preview.setAlignment(Qt.AlignCenter)
        self.ws_logo_preview.setStyleSheet("background: #0F1014; border: 1px dashed #3E424C; border-radius: 8px; "
                                           "color: #7C8BAD;")
        lrow.addWidget(self.ws_logo_preview)
        lrow.addWidget(btn(tr("Escolher imagem…"), None, self._pick_logo))
        lrow.addWidget(btn(tr("Remover"), None, self._remove_logo))
        lrow.addStretch(1)
        wf.addRow(lbl(tr("Logótipo da oficina"), "muted"), lrow)
        wf.addRow(lbl(tr("O logótipo aparece no relatório para o cliente e na barra lateral do programa."), "muted"))
        v.addWidget(wc)
        v.addStretch(1)

        # ================================================================ Licença
        v = tab(tr("Licença"))
        lc = card()
        lf = QFormLayout(lc)
        lf.setContentsMargins(20, 18, 20, 18)
        lf.setVerticalSpacing(10)
        lf.addRow(lbl(tr("Licença"), "h2"))
        self.lic_state = lbl("—", None, wrap=True)
        lf.addRow(lbl(tr("Estado"), "muted"), self.lic_state)
        mrow = QHBoxLayout()
        try:
            mid = licensing.machine_id()
        except Exception as e:
            log.warning("ID do PC: %s", e)
            mid = "—"
        self.lic_machine = lbl(mid, None)
        self.lic_machine.setStyleSheet("font-family: Consolas, monospace; font-size: 13pt; font-weight: 600; "
                                       "letter-spacing: 1px; color: white;")
        self.lic_machine.setTextInteractionFlags(Qt.TextSelectableByMouse)
        mrow.addWidget(self.lic_machine)
        mrow.addWidget(btn(tr("Copiar"), None, lambda: QGuiApplication.clipboard().setText(self.lic_machine.text())))
        mrow.addStretch(1)
        lf.addRow(lbl(tr("ID deste PC"), "muted"), mrow)
        self.lic_key = QPlainTextEdit()
        self.lic_key.setPlaceholderText(tr("Cole aqui a chave de licença (começa por RAD1-)"))
        self.lic_key.setFixedHeight(64)
        lf.addRow(lbl(tr("Chave"), "muted"), self.lic_key)
        krow = QHBoxLayout()
        krow.addWidget(btn(tr("Activar licença"), "primary", self._activate_license))
        self.lic_remove_btn = btn(tr("Remover licença"), None, self._remove_license)
        krow.addWidget(self.lic_remove_btn)
        krow.addStretch(1)
        lf.addRow(QLabel(), krow)
        lf.addRow(lbl(tr("Para comprar ou renovar, envie o ID deste PC ao fornecedor. A activação não precisa de "
                         "internet. Nos primeiros {days} dias está tudo desbloqueado. Depois, sem licença, o programa "
                         "liga ao carro e identifica os controladores, mas mostra só {faults} avarias por leitura e "
                         "{secs} s de valores de medição por controlador, e não escreve em carros reais (codificação, "
                         "adaptação, ajustes básicos, apagar avarias, teste de saídas). O OBD-II genérico e o "
                         "simulador funcionam sempre sem limites.", days=licensing.TRIAL_DAYS,
                         faults=licensing.FREE_FAULTS, secs=licensing.FREE_LIVE_SECONDS), "muted", wrap=True))
        v.addWidget(lc)
        v.addStretch(1)

        # ================================================================ Programa
        v = tab(tr("Programa"))
        uc = card()
        uf = QFormLayout(uc)
        uf.setContentsMargins(20, 18, 20, 18)
        uf.setVerticalSpacing(10)
        uf.addRow(lbl(tr("Actualizações"), "h2"))
        urow = QHBoxLayout()
        self.upd_btn = btn(tr("Procurar agora"), None, lambda: self.check_updates(manual=True))
        urow.addWidget(self.upd_btn)
        self.upd_lbl = lbl(tr("Versão instalada: {VERSION}", VERSION=VERSION), "muted", wrap=True)
        urow.addWidget(self.upd_lbl, 1)
        uf.addRow(lbl(tr("Versão"), "muted"), urow)
        if self.technical:                     # só no PC do fornecedor / de quem testa: o cliente nunca vê
            self.upd_beta = QCheckBox(tr("Receber versões de teste antes dos clientes"))
            self.upd_beta.setChecked(self.update_channel() == updates.BETA)
            self.upd_beta.toggled.connect(lambda on: self.settings.setValue(
                "updates/channel", updates.BETA if on else updates.STABLE))
            uf.addRow(lbl(tr("Testes"), "muted"), self.upd_beta)
        uf.addRow(lbl(tr("O programa actualiza-se sempre sozinho, também na versão portátil. Ao abrir (e de algumas "
                         "em algumas horas) procura uma versão nova e descarrega-a; se ainda não começou a trabalhar, "
                         "fecha, actualiza e volta a abrir; senão, instala-a quando fechar o programa. Os "
                         "diagnósticos, a licença e as definições ficam guardados. Se a instalação falhar, o programa "
                         "continua na versão actual. Sem internet não acontece nada."), "muted", wrap=True))
        v.addWidget(uc)

        sc = card()
        sf = QFormLayout(sc)
        sf.setContentsMargins(20, 18, 20, 18)
        sf.setVerticalSpacing(10)
        sf.addRow(lbl(tr("Ecrã"), "h2"))
        self.scale = QComboBox()
        for t, d in [(tr("Normal (100%)"), "1"), (tr("Grande (115%)"), "1.15"), (tr("Muito grande (130%)"), "1.3"),
                     (tr("Oficina — ver ao longe (150%)"), "1.5")]:
            self.scale.addItem(t, d)
        sf.addRow(lbl(tr("Tamanho da interface"), "muted"), self.scale)
        self.language = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.language.addItem(name, code)
        sf.addRow(lbl(tr("Idioma"), "muted"), self.language)
        sf.addRow(lbl(tr("O tamanho aumenta letras, botões e mostradores para se lerem a partir do carro. "
                         "O tamanho e o idioma aplicam-se quando o programa voltar a abrir."), "muted", wrap=True))
        v.addWidget(sc)

        rc = card()
        rf = QFormLayout(rc)
        rf.setContentsMargins(20, 18, 20, 18)
        rf.setVerticalSpacing(10)
        rf.addRow(lbl(tr("Suporte"), "h2"))
        srow = QHBoxLayout()
        srow.setSpacing(8)
        self.recording = False
        self.capture_btn = btn(tr("Gravar comunicação"), None, lambda: self.capture_req.emit(not self.recording))
        srow.addWidget(self.capture_btn)
        srow.addWidget(btn(tr("Pacote de suporte"), None, self._support_bundle))
        srow.addStretch(1)
        rf.addRow(lbl(tr("Enviar ao suporte"), "muted"), srow)
        self.capture_lbl = lbl(tr("Quando algo não funcionar num carro: carregue em Gravar comunicação, repita o que "
                                  "falhou, pare a gravação e envie o Pacote de suporte (leva as últimas gravações)."),
                               "muted", wrap=True)
        rf.addRow(self.capture_lbl)
        if self.technical:
            trow = QHBoxLayout()
            trow.setSpacing(8)
            trow.addWidget(btn(tr("Validação no carro"), "primary", lambda: self.validation_req.emit()))
            self.replay_btn = btn(tr("Verificar gravação…"), None, self._check_capture)
            trow.addWidget(self.replay_btn)
            trow.addWidget(btn(tr("Abrir pasta de registos"), None, self._open_logs))
            trow.addStretch(1)
            rf.addRow(lbl(tr("Técnico"), "muted"), trow)
        v.addWidget(rc)
        v.addStretch(1)
        # todos os cartões com a coluna das etiquetas da mesma largura
        for form in [cable_form, wf, lf, uf, sf, rf] + forms:
            _align_form(form)
        self._detecting = False
        self.detect_done.connect(self._detect_finished)
        self._checking = False
        self.update_done.connect(self._update_finished)
        self.replay_done.connect(self._replay_finished)
        self.refresh_ports()
        self._load()
        self._update_cable_status()

    def _toggle_advanced(self):
        on = self.adv_box.isHidden()
        self.adv_box.setVisible(on)
        self.adv_btn.setText(tr("Avançado ▾") if on else tr("Avançado ▸"))

    def _slow_coms(self):
        return [f["com"] for f in (self._findings or []) if f.get("fix") == "latency" and f.get("com")]

    def _update_cable_status(self):
        """Cartão do estado do cabo e a lista "Antes de ligar ao carro" a partir da porta escolhida e do último
        Detectar cabo."""
        from ...kline import is_simulated_port
        port = self.port.currentData() or ""
        kind = tr("Adaptador OBD") if self.adapter.currentData() == "elm327" else tr("Cabo VAG")
        found = bool(port) and not self.port.currentData(MISSING_ROLE)
        if is_simulated_port(port):
            self.cable_title.setText(tr("Simulador escolhido"))
            self.cable_title.setStyleSheet(f"color: {WARN};")
            self.cable_sub.setText(tr("O programa mostra um carro de demonstração. Para ligar a um carro, ligue o cabo "
                                      "ao PC e carregue em Detectar cabo."))
        elif not port:
            self.cable_title.setText(tr("Nenhum cabo escolhido"))
            self.cable_title.setStyleSheet(f"color: {WARN};")
            self.cable_sub.setText(tr("Ligue o cabo ao PC e carregue em Detectar cabo: o programa encontra-o e escolhe "
                                      "a porta sozinho."))
        elif not found:
            self.cable_title.setText(tr("{kind} não ligado ({port})", kind=kind, port=port))
            self.cable_title.setStyleSheet(f"color: {BAD};")
            self.cable_sub.setText(tr("Ligue o cabo à porta USB e carregue em Detectar cabo."))
        else:
            self.cable_title.setText(tr("{kind} em {port}", kind=kind, port=port))
            self.cable_title.setStyleSheet(f"color: {OK};")
            self.cable_sub.setText(self.port.currentText())
        sim = is_simulated_port(port)
        if self._findings is None:
            self.chk_cable.set("todo", tr("Carregue em Detectar cabo.") if not sim else
                               tr("Com o simulador não é preciso cabo."))
        elif any(f.get("com") for f in self._findings):
            self.chk_cable.set("ok", tr("Encontrado em {v}.", v=", ".join(f["com"] for f in self._findings
                                                                           if f.get("com"))))
        elif self._findings:
            self.chk_cable.set("bad", tr("Há um cabo ligado, mas ainda não está pronto: veja a mensagem do Detectar "
                                         "cabo."))
        else:
            self.chk_cable.set("bad", tr("Nenhum cabo encontrado. Experimente outra porta USB."))
        slow = self._slow_coms()
        if self._latency_fixed:
            self.chk_speed.set("todo", tr("Ajustado. Desligue o cabo do USB, volte a ligá-lo e carregue em Detectar "
                                          "cabo."))
            self.chk_speed.button.hide()
            self.chk_speed.show()
        elif slow:
            self.chk_speed.set("warn", tr("Funciona, mas lê mais devagar do que pode. Carregue em Ajustar cabo (o "
                                          "Windows pede autorização uma vez)."))
            self.chk_speed.button.show()
            self.chk_speed.show()
        else:
            self.chk_speed.hide()

    def refresh_ports(self):
        cur = self.port.currentData() or self.settings.value("port", "")
        self.port.clear()
        for dev, desc in list_serial_ports():
            self.port.addItem(desc, dev)
        i = self.port.findData(cur)
        if i < 0 and cur:
            # o cabo escolhido não está ligado agora: fica na lista, em vez de passar sem aviso para outra porta
            # (o simulador) e de se perder a escolha na próxima vez que as opções forem guardadas
            self.port.addItem(tr("{port} — não encontrada agora (cabo desligado?)", port=cur), cur)
            i = self.port.count() - 1
            self.port.setItemData(i, True, MISSING_ROLE)
        if i >= 0:
            self.port.setCurrentIndex(i)

    def _adapter_changed(self, *_):
        """Mostra só as opções que se aplicam à interface escolhida."""
        elm = self.adapter.currentData() == "elm327"
        form = getattr(self, "_form", None)
        if form is None:
            return
        form.setRowVisible(self.elm_proto, elm and self.technical)
        for row in (self.baud, self.echo, self._hex_row):
            form.setRowVisible(row, not elm and self.technical)
        self._update_cable_status()

    def _sim_car_changed(self, *_):
        self.sim_car_desc.setText(self.sim_car.currentData(Qt.ToolTipRole) or "")

    def _show_sim_rows(self):
        """O cartão do simulador está sempre à vista; aqui só se actualiza o estado do cabo."""
        if hasattr(self, "chk_cable"):
            self._update_cable_status()

    def _port_changed(self, *_):
        from ...kline import is_elm_sim_port
        self._show_sim_rows()
        if is_elm_sim_port(self.port.currentData() or ""):
            i = self.adapter.findData("elm327")
            if i >= 0 and self.adapter.currentIndex() != i:
                self.adapter.setCurrentIndex(i)

    def _load(self):
        for combo, key, default in ((self.port, "port", ""), (self.baud, "baud", "auto"), (self.echo, "echo", "auto"),
                                    (self.adapter, "adapter", "kline"), (self.elm_proto, "elm_protocol", "0")):
            i = combo.findData(self.settings.value(key, default))
            if i >= 0:
                combo.setCurrentIndex(i)
        self.raw.setChecked(self.settings.value("raw_log", "false") == "true")
        self.sim_car.setCurrentIndex(max(0, self.sim_car.findData(str(self.settings.value("simulator/car",
                                                                                            simcars.AUTO)))))
        self._sim_car_changed()
        self.sim_clone.setChecked(self.settings.value("simulator/clone", "false") == "true")
        self._show_sim_rows()
        self.scale.setCurrentIndex(max(0, self.scale.findData(ui_scale(self.settings))))
        lang = str(self.settings.value("ui/language", i18n.DEFAULT))
        self.language.setCurrentIndex(max(0, self.language.findData(lang if lang in i18n.LANGUAGES else
                                                                     i18n.DEFAULT)))
        self._adapter_changed()
        for k, e in self.ws_edits.items():
            e.setText(self.settings.value(f"workshop/{k}", "") or "")
        self._show_logo()

    @staticmethod
    def logo_file():
        from ...applog import log_dir
        return os.path.join(os.path.dirname(log_dir()), "oficina_logo.png")

    def workshop_logo(self):
        p = self.logo_file()
        return p if os.path.exists(p) else None

    def _show_logo(self):
        from PySide6.QtGui import QPixmap
        p = self.workshop_logo()
        if p:
            pm = QPixmap(p).scaled(140, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.ws_logo_preview.setPixmap(pm)
        else:
            self.ws_logo_preview.setPixmap(QPixmap())
            self.ws_logo_preview.setText(tr("Sem logótipo"))

    def _pick_logo(self):
        from PySide6.QtGui import QImage
        path, _ = QFileDialog.getOpenFileName(self, tr("Logótipo da oficina"), os.path.expanduser("~"),
                                              tr("Imagens (*.png *.jpg *.jpeg *.bmp *.webp)"))
        if not path:
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, APP_NAME, tr("Não foi possível abrir essa imagem."))
            return
        if img.width() > 800 or img.height() > 400:
            img = img.scaled(800, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if not img.save(self.logo_file(), "PNG"):
            QMessageBox.warning(self, APP_NAME, tr("Não foi possível guardar o logótipo."))
            return
        self._show_logo()
        self.saved.emit(self.config())

    def _remove_logo(self):
        try:
            os.remove(self.logo_file())
        except OSError:
            pass
        self._show_logo()
        self.saved.emit(self.config())
    def workshop(self):
        return {k: e.text().strip() for k, e in self.ws_edits.items()}

    def config(self):
        return {"port": self.port.currentData() or "", "baud": self.baud.currentData(),
                "echo": self.echo.currentData(), "raw_log": self.raw.isChecked(),
                "adapter": self.adapter.currentData() or "kline", "elm_protocol": self.elm_proto.currentData() or "0",
                "sim_car": self.sim_car.currentData() or simcars.AUTO, "sim_clone": self.sim_clone.isChecked()}

    def _save(self):
        c = self.config()
        self.settings.setValue("port", c["port"])
        self.settings.setValue("baud", c["baud"])
        self.settings.setValue("echo", c["echo"])
        self.settings.setValue("raw_log", "true" if c["raw_log"] else "false")
        self.settings.setValue("adapter", c["adapter"])
        self.settings.setValue("elm_protocol", c["elm_protocol"])
        self.settings.setValue("simulator/car", c["sim_car"])
        self.settings.setValue("simulator/clone", "true" if c["sim_clone"] else "false")
        for k, val in self.workshop().items():
            self.settings.setValue(f"workshop/{k}", val)
        restart = False
        scale = self.scale.currentData() or "1"
        if scale != ui_scale(self.settings):
            self.settings.setValue("ui/scale", scale)
            restart = True
        lang = self.language.currentData() or i18n.DEFAULT
        if lang != str(self.settings.value("ui/language", i18n.DEFAULT)):
            self.settings.setValue("ui/language", lang)
            restart = True
        if restart:
            QMessageBox.information(self, APP_NAME, tr("O tamanho e o idioma da interface aplicam-se quando voltar "
                                                       "a abrir o programa."))
        self._update_cable_status()
        self.saved.emit(c)

    # -------------------------------------------------------- actualizações
    def update_channel(self):
        """Canal de actualizações: versões de teste (escolhido uma vez no modo técnico) ou só as publicadas."""
        return updates.BETA if self.settings.value("updates/channel", updates.STABLE) == updates.BETA \
            else updates.STABLE

    def check_updates(self, manual=False):
        """Procura numa thread à parte (a rede pode demorar ou não existir)."""
        if self._checking:
            return
        self._checking = True
        self.upd_btn.setEnabled(False)
        if manual:
            self.upd_lbl.setText(tr("A procurar…"))

        channel = self.update_channel()

        def run():
            try:
                res = updates.check(channel=channel)
            except Exception as e:                     # UpdateError ou outro: nunca derrubar o programa
                res = e
            try:
                self.update_done.emit(res, manual)
            except RuntimeError:                       # a janela já foi fechada
                pass
        threading.Thread(target=run, daemon=True, name="updates").start()

    def _update_finished(self, res, manual):
        self._checking = False
        self.upd_btn.setEnabled(True)
        if isinstance(res, Exception):
            log.info("Actualizações: %s", res)
            text = str(res) if isinstance(res, updates.UpdateError) else tr("Erro: {res}", res=res)
            self.upd_lbl.setText(tr("Versão instalada: {VERSION}. {text}", VERSION=VERSION, text=text))
            if manual:
                QMessageBox.information(self, APP_NAME, tr("Não foi possível procurar actualizações.\n\n{text}",
                                                           text=text))
            return
        if res["available"]:
            self.upd_lbl.setText(tr("Versão instalada: {VERSION}. Nova versão disponível: {version}.",
                                    VERSION=VERSION, version=res['version']))
            self.update_found.emit(res)
        else:
            self.upd_lbl.setText(tr("Versão instalada: {VERSION}. É a versão mais recente.", VERSION=VERSION))
            if manual:
                QMessageBox.information(self, APP_NAME, tr("Tem a versão mais recente ({VERSION}).", VERSION=VERSION))

    # ------------------------------------------------------------- licença
    def show_license(self, st):
        self._license_state = st.get("state")
        color = {"licensed": OK, "demo": BAD, "trial": WARN}.get(st.get("state"), WARN)
        self.lic_state.setText(st.get("message", "—"))
        self.lic_state.setStyleSheet(f"color: {color};")
        self.lic_remove_btn.setVisible(bool(licensing.stored_key()))

    def _activate_license(self):
        text = self.lic_key.toPlainText().strip()
        if not text:
            QMessageBox.information(self, APP_NAME, tr("Cole primeiro a chave de licença."))
            return
        try:
            r = licensing.install(text)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, tr("Não foi possível guardar a licença:\n{e}", e=e))
            return
        if not r["valid"]:
            QMessageBox.warning(self, APP_NAME, r["reason"])
            return
        self.lic_key.clear()
        self.license_changed.emit()
        QMessageBox.information(self, APP_NAME, tr("Licença activada para {workshop}.", workshop=r['workshop']))

    def _remove_license(self):
        if QMessageBox.question(self, APP_NAME, tr("Remover a licença deste PC? O programa volta ao modo "
                                                   "demonstração.")) == QMessageBox.Yes:
            licensing.remove()
            self.license_changed.emit()

    def _detect_cable(self):
        """Procura o cabo numa thread à parte: o PowerShell pode demorar vários segundos e a janela não
        deve ficar congelada entretanto."""
        if self._detecting:
            return
        self._detecting = True
        self.detect_btn.setEnabled(False)
        self.detect_btn.setText(tr("A procurar…"))
        threading.Thread(target=self._detect_worker, name="detectar-cabo", daemon=True).start()

    def _detect_worker(self):
        from ... import cable
        try:
            res = (cable.detect(), cable.j2534_devices())
        except Exception as e:
            log.warning("Detectar cabo falhou", exc_info=True)
            res = e
        try:
            self.detect_done.emit(res)
        except RuntimeError:              # a janela já foi fechada
            pass

    def _detect_finished(self, res):
        self._detecting = False
        self.detect_btn.setEnabled(True)
        self.detect_btn.setText(tr("Detectar cabo"))
        if isinstance(res, Exception):
            QMessageBox.warning(self, APP_NAME, tr("Não foi possível procurar o cabo:\n{res}", res=res))
            return
        findings, j2534 = res
        if not self.technical:
            from ... import cable
            findings = [cable.plain(f) for f in findings]
        self._findings = findings
        self._latency_fixed = False
        self.refresh_ports()
        self._update_cable_status()
        colors = {"ok": OK, "warn": WARN, "bad": BAD}
        if not findings:
            html = (tr("<p><b>Nenhum cabo de diagnóstico encontrado.</b></p>"
                       "<p>Ligue o cabo à porta USB e volte a carregar em Detectar cabo. "
                       "Se continuar sem aparecer:</p>"
                       "<ul><li>Experimente outra porta USB (de preferência directamente no PC, sem hub).</li>"
                       "<li>Se o cabo é novo neste PC, ligue o PC à internet uma vez com o cabo ligado: o "
                       "Windows prepara-o sozinho.</li></ul>"))
        else:
            parts = []
            for f in findings:
                link = (tr("<br><a href='{driver_url}'>Página oficial do driver</a>", driver_url=f['driver_url'])
                        if f.get("driver_url") and self.technical else "")
                parts.append(f"<p><b style='color:{colors[f['level']]}'>{f['title']}</b><br>{f['detail']}{link}</p>")
            html = "".join(parts)
        if not self.technical:
            if j2534:
                html += tr("<p>Interfaces de diagnóstico instaladas neste PC: <b>{v}</b>. Pode escolhê-las em "
                           "Porta do cabo.</p>", v=", ".join(d["name"] for d in j2534))
        elif j2534:
            html += tr("<p><b>Interfaces J2534 (PassThru) instaladas:</b></p><ul>")
            for d in j2534:
                html += (tr("<li><b>{name}</b> — {vendor} ({view})<br>Protocolos: {v}<br><small>{dll}</small></li>",
                            name=d['name'], vendor=d['vendor'], view=d['view'], v=', '.join(d['protocols']) or '—',
                            dll=d['dll']))
            html += "</ul>"
        else:
            html += tr("<p>Nenhuma interface J2534 (PassThru) registada neste PC.</p>")
        ready = [f["com"] for f in findings if f.get("com")]
        if len(ready) == 1:
            i = self.port.findData(ready[0])
            if i >= 0:
                self.port.setCurrentIndex(i)
                self._save()
                html += tr("<p>O cabo foi escolhido e guardado automaticamente.</p>")
        box = QMessageBox(self)
        box.setWindowTitle(tr("Detectar cabo"))
        box.setTextFormat(Qt.RichText)
        box.setTextInteractionFlags(Qt.TextBrowserInteraction)
        box.setText(html)
        slow = [f["com"] for f in findings if f.get("fix") == "latency" and f.get("com")]
        fix = box.addButton(tr("Ajustar cabo"), QMessageBox.AcceptRole) if slow else None
        dm = box.addButton(tr("Abrir Gestor de Dispositivos"), QMessageBox.ActionRole) if self.technical else None
        box.addButton(QMessageBox.Ok)
        box.exec()
        if fix is not None and box.clickedButton() is fix:
            self._fix_latency(slow)
            return
        if dm is not None and box.clickedButton() is dm:
            try:
                os.startfile("devmgmt.msc")      # abre sem pedir administrador (só leitura)
            except Exception:
                pass

    def _fix_latency(self, coms):
        """Põe o Latency Timer do cabo FTDI a 1 ms (o Windows pede autorização)."""
        from ... import cable
        if cable.fix_latency(coms):
            self._latency_fixed = True
            self._update_cable_status()
            QMessageBox.information(self, APP_NAME, tr("Cabo ajustado. Desligue o cabo do USB, volte a ligá-lo e "
                                                       "carregue outra vez em Detectar cabo."))
        else:
            QMessageBox.warning(self, APP_NAME, tr("O cabo não foi ajustado (a autorização do Windows foi recusada "
                                                   "ou o cabo já não está ligado). O Torqis funciona na mesma, só "
                                                   "um pouco mais lento."))

    def _support_bundle(self):
        from ... import applog
        name = tr("Torqis_suporte_{v:%Y%m%d_%H%M}.zip", v=datetime.datetime.now())
        path, _ = QFileDialog.getSaveFileName(self, tr("Guardar pacote de suporte"),
                                              os.path.join(os.path.expanduser("~"), "Desktop", name), tr("Zip (*.zip)"))
        if not path:
            return
        try:
            applog.make_support_bundle(path, settings=self.settings, license_state=self._license_state)
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, tr("Não foi possível criar o pacote:\n{e}", e=e))
            return
        QMessageBox.information(self, APP_NAME, tr("Pacote de suporte guardado em:\n{path}\n\nEnvie este ficheiro ao "
                                                   "suporte. Contém os registos dos últimos dias, as últimas gravações "
                                                   "da comunicação e a informação do cabo e das actualizações. Não "
                                                   "leva o histórico, os dados da oficina nem a licença, e os números "
                                                   "de chassis e as matrículas são tirados dos registos.",
                                                   path=path))

    def set_recording(self, on, path=None):
        """Mostra o estado da gravação (chamado pela janela quando a thread confirma)."""
        self.recording = bool(on)
        self.capture_btn.setText(tr("Parar gravação") if on else tr("Gravar comunicação"))
        self.capture_btn.setObjectName("danger" if on else "")
        self.capture_btn.style().unpolish(self.capture_btn)
        self.capture_btn.style().polish(self.capture_btn)
        if on:
            self.capture_lbl.setText(tr("A gravar toda a comunicação com o carro. Repita o que falhou e depois "
                                        "carregue em Parar gravação."))
        elif path:
            self.capture_lbl.setText(tr("Gravação guardada: {path}\nEnvie-a com o Pacote de suporte.", path=path))

    def _check_capture(self):
        """Reproduz uma gravação com o código actual e diz se o resultado é o mesmo (modo técnico)."""
        from ... import capture
        path, _ = QFileDialog.getOpenFileName(self, tr("Verificar gravação"), capture.captures_dir(),
                                              tr("Gravações (*.radrec)"))
        if not path:
            return
        self.replay_btn.setEnabled(False)
        self.replay_btn.setText(tr("A verificar…"))

        def work():
            from ... import replay
            try:
                res = replay.run(path)
            except Exception as e:              # ficheiro estragado, versão antiga…
                log.warning("Verificar gravação %s", path, exc_info=True)
                res = e
            self.replay_done.emit(res, path)
        threading.Thread(target=work, daemon=True).start()

    def _replay_finished(self, res, path):
        self.replay_btn.setEnabled(True)
        self.replay_btn.setText(tr("Verificar gravação…"))
        name = os.path.basename(path)
        if isinstance(res, Exception):
            QMessageBox.warning(self, APP_NAME, tr("Não foi possível ler a gravação {name}:\n{e}", name=name, e=res))
            return
        if res["ok"]:
            QMessageBox.information(self, APP_NAME, tr("{name}: o programa actual repete a gravação sem diferenças "
                                                       "({commands} comandos, {results} resultados).",
                                                       name=name, commands=res["commands"], results=res["results"]))
            return
        lines = [tr("{name}: há diferenças em relação à gravação.", name=name), ""]
        lines += [tr("Bytes: {what} (evento {event})", what=d.get("what"), event=d.get("event", "—"))
                  for d in res["divergences"][:6]]
        lines += [tr("Resultado diferente em {cmd}", cmd=m.get("cmd")) for m in res["mismatches"][:6]]
        lines += [tr("Erro novo em {cmd}: {msg}", cmd=c, msg=m) for c, m in res["errors"][:4]]
        QMessageBox.warning(self, APP_NAME, "\n".join(lines))

    def _open_logs(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from ... import applog
        QDesktopServices.openUrl(QUrl.fromLocalFile(applog.log_dir()))

    def _hex(self, mode):
        self._save()
        self.hex_mode_req.emit(mode)

    def _test(self):
        self._save()
        self.test_req.emit()

    def select_simulator(self, kind="kline"):
        """kind: "kline" (simulador VAG) ou "elm327" (simulador OBD-II)."""
        from ...kline import SIM_ELM_PORT, SIM_PORT
        i = self.port.findData(SIM_ELM_PORT if kind == "elm327" else SIM_PORT)
        if i >= 0:
            self.port.setCurrentIndex(i)
        j = self.adapter.findData(kind)
        if j >= 0:
            self.adapter.setCurrentIndex(j)
        self._save()


# ---------------------------------------------------------------- histórico
