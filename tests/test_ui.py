"""Teste de ponta a ponta da interface com o simulador (sem ecrã: plataforma Qt "offscreen").

Abre a janela principal, faz um Auto-Scan, compara com uma visita anterior, liga ao motor, lê avarias,
lê valores de medição, usa a paleta de comandos e desenha todos os widgets próprios. As definições e o
histórico vão para uma pasta temporária, nunca para as do utilizador."""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp()


def _env():
    os.environ["APPDATA"] = _TMP
    os.environ["RAD_SETTINGS_INI"] = os.path.join(_TMP, "settings.ini")
    os.environ["RAD_NO_UPDATE_CHECK"] = "1"          # os testes nunca vão à internet
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    _env()
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _wait(app, cond, timeout=15.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def _window():
    app = _app()
    from rad.ui.main_window import MainWindow
    w = MainWindow()
    w.resize(1300, 820)
    w.show()
    w.options.select_simulator()
    w.apply_config(w.options.config(), quiet=True)
    app.processEvents()
    return app, w


def test_full_flow_with_simulator():
    app, w = _window()
    from rad import history, vag_data
    try:
        # visita anterior do mesmo carro: 00522 foi resolvida, 01247 mantém-se
        history.save_session("autoscan", {"plate": "UI-00-01"}, [
            {"address": 1, "module": "Motor", "status": "ok", "info": {"part": "x", "component": "y"},
             "faults": [vag_data.decode_fault(1247, 0x1E), vag_data.decode_fault(522, 0x07)]}])
        # --- Auto-Scan
        w.home.vehicle_edits["plate"].setText("UI-00-01")
        w._home_go("autoscan_start")
        assert w.scan.running and w.scan.start_btn.text().endswith("Parar")
        assert _wait(app, lambda: not w.scan.running, 30), "Auto-Scan não terminou"
        golf = [0x01, 0x02, 0x03, 0x08, 0x15, 0x17, 0x46, 0x56]          # os controladores do Golf IV simulado
        assert sorted(i["address"] for i in w.scan.items) == golf
        # redesenho: na lista só os controladores com avarias; os outros numa linha "Sem avarias"
        with_faults = [i for i in w.scan.items if i.get("faults")]
        assert w.scan.tree.topLevelItemCount() == len(with_faults) and 0 < len(with_faults) < len(golf)
        assert "Sem avarias" in w.scan.ok_lbl.text() and "17" in w.scan.ok_lbl.text()
        assert w.scan.summary.text().startswith("UI-00-01") and "controlador" in w.scan.summary.text()
        assert "Ler de novo" in w.scan.start_btn.text()
        assert not hasattr(w.scan, "map") and not hasattr(w.scan, "ring")      # mapa e pontuação: só no relatório
        assert "alta" in w.scan.severity_lbl.text()                      # ABS: sensor de velocidade
        # comparação automática com a visita anterior
        d = w.scan.diff
        assert d is not None
        assert [f["vag"] for f in d["resolved"]] == ["00522"]
        assert [f["vag"] for f in d["persisting"]] == ["01247"]
        assert "00532" in [f["vag"] for f in d["new"]]
        assert not w.scan.banner.isHidden() and "resolvida" in w.scan.banner_lbl.text()
        # seleccionar uma avaria mostra o assistente
        engine = w.scan.tree.topLevelItem(0)
        w.scan.tree.setCurrentItem(engine.child(0))
        app.processEvents()
        assert not w.scan.advice.isHidden() and engine.child(0).text(2).startswith("NOVA")
        w.scan.tree.setCurrentItem(engine)
        app.processEvents()
        assert w.scan.advice.isHidden()

        # --- ligar ao motor e ler avarias
        w.connect_module(0x01)
        assert _wait(app, lambda: w.nav_btns["module"].isEnabled()), "não ligou ao motor"
        assert w.stack.currentWidget() is w.module and w.module.info["address"] == 0x01
        w.module._quick_faults()
        assert _wait(app, lambda: w.module.fault_table.rowCount() == 2)
        assert w.module.fault_table.item(0, 0).text().startswith("00532")
        assert "00532" in w.module.fault_advice.title.text()
        assert w.module.fault_table.item(1, 3).text() == "Média"

        # --- valores de medição: os mostradores recebem valores e animam
        w.module.tabs.setCurrentIndex(w.module.MVB_TAB)
        w.module._toggle_mvb()
        g = w.module.groups[0].cells[0]
        assert _wait(app, lambda: g.field is not None and len(g.hist) > 3), "sem valores de medição"
        assert g.label == "Rotação" and g.field["unit"] == "/min"
        assert _wait(app, lambda: abs(g.shown - g.target) < 0.01, 3)
        w.module.stop_live()
        assert w.worker.live_mode is None

        # --- paleta de comandos
        w.open_palette()
        app.processEvents()
        assert w.palette.isVisible() and w.palette.list.count() > 10
        w.palette.input.setText("ligar 17")
        assert w.palette.shown[0].title.startswith("Ligar a 17")
        w.palette.input.setText("00532")
        assert w.palette.shown[0].title.startswith("Avaria 00532")
        w.palette.input.setText("historico")
        w.palette.run_current()
        app.processEvents()
        assert not w.palette.isVisible() and w.stack.currentWidget() is w.hist
        assert w.hist.table.rowCount() >= 2 and w.hist.car_title.text() == "UI-00-01"

        # --- histórico: comparar a última visita com a anterior
        w.hist.table.selectRow(0)
        text = w.hist.compare_text(w.hist._selected_id())
        assert text and "Resolvidas: 1" in text and "00522" in text

        # --- desligar
        w.worker.submit("disconnect")
        assert _wait(app, lambda: not w.nav_btns["module"].isEnabled())
        for key in ("home", "modules", "autoscan", "history", "options"):
            w.show_page(key)
            app.processEvents()
        w.select.filter.setText("abs")
        sel = w.select                                  # depois do Auto-Scan os do carro estão em cartões

        def shown(a):
            return sel.cards[a].isVisibleTo(sel) or sel.mod_btns[a].isVisibleTo(sel)
        assert not sel.cards[0x03].isHidden() and sel.mod_btns[0x03].isHidden()
        assert shown(0x03) and not shown(0x01) and shown(0x44) is False
        w.select.filter.setText("")
    finally:
        w.close()
        app.processEvents()
    # as definições ficaram no ficheiro temporário, não no registo do Windows
    assert os.path.exists(os.environ["RAD_SETTINGS_INI"])


def test_simulator_car_choice_in_options():
    app, w = _window()
    from rad import simcars
    try:
        o = w.options
        assert not o.sim_box.isHidden() and not o.sim_car.isHidden()   # o cartão do simulador está sempre à vista
        assert "Simulador" in o.cable_title.text()
        o.sim_car.setCurrentIndex(o.sim_car.findData("golf5_can"))
        assert "CAN" in o.sim_car_desc.text()
        o._save()
        app.processEvents()
        assert os.environ.get(simcars.ENV) == "golf5_can"
        assert w.settings.value("simulator/car") == "golf5_can"
        w._home_go("autoscan_start")                                # Golf V: o cabo VAG não encontra nada
        assert _wait(app, lambda: not w.scan.running, 60), "Auto-Scan não terminou"
        assert not any(i.get("status") == "ok" for i in w.scan.items)
    finally:
        o.sim_car.setCurrentIndex(0)
        o._save()
        w.close()
    assert simcars.ENV not in os.environ


def test_saved_cable_port_that_is_unplugged_is_not_replaced():
    """O cabo guardado (ex.: COM3) não está ligado quando o programa abre: a escolha fica (marcada como não
    encontrada) em vez de passar sem aviso para o simulador e se perder ao guardar as opções."""
    app, w = _window()
    try:
        o = w.options
        old = w.settings.value("port")
        w.settings.setValue("port", "COM99")
        o.port.clear()
        o.refresh_ports()
        assert o.port.currentData() == "COM99" and "não encontrada" in o.port.currentText()
        assert o.config()["port"] == "COM99"
        w.settings.setValue("port", old)
    finally:
        w.close()


def test_clear_all_hides_the_advice_of_the_cleared_fault():
    app, w = _window()
    import rad.ui.pages.autoscan as autoscan_page
    ask = autoscan_page.ask
    autoscan_page.ask = lambda *a, **k: True          # responde «sim» à confirmação
    try:
        w._home_go("autoscan_start")
        assert _wait(app, lambda: not w.scan.running, 30), "Auto-Scan não terminou"
        engine = w.scan.tree.topLevelItem(0)
        w.scan.tree.setCurrentItem(engine.child(0))
        app.processEvents()
        assert not w.scan.advice.isHidden()
        w.scan._clear_all()
        assert _wait(app, lambda: w.scan.clear_all_btn.isEnabled(), 30), "não acabou de apagar"
        # como num carro: as avarias presentes voltam logo, só as intermitentes ficam apagadas
        left = sorted(f["vag"] for i in w.scan.items for f in i.get("faults", []))
        assert left == ["00283", "01247"], left
        assert w.scan.advice.isHidden(), "o assistente continuou a mostrar uma avaria já apagada"
    finally:
        autoscan_page.ask = ask
        w.close()


def test_changes_tab_records_writes_and_prepares_the_previous_value():
    app, w = _window()
    try:
        w.connect_module(0x01)
        assert _wait(app, lambda: w.nav_btns["module"].isEnabled()), "não ligou ao motor"
        m = w.module
        before = m.info["coding"]
        start = m.chg_table.rowCount()
        w.worker.submit("recode", 4102, 12345)
        assert _wait(app, lambda: m.chg_table.rowCount() == start + 1), "codificação não ficou no registo"
        assert m.info["coding"] == 4102
        w.worker.submit("adaptation_save", 1, 140, 12345)
        assert _wait(app, lambda: m.chg_table.rowCount() == start + 2), "adaptação não ficou no registo"
        assert m.chg_table.item(0, 1).text().startswith("Adaptação") and m.chg_table.item(0, 3).text() == "140"
        assert m.chg_table.item(1, 2).text() == f"{before:05d}"
        assert m.chg_original.text() == f"{before:05d}" and m.chg_original_btn.isEnabled()

        # repor: só prepara o valor, não grava
        m.tabs.setCurrentIndex(m.CHANGES_TAB)
        m.chg_table.selectRow(1)
        app.processEvents()
        assert m.chg_restore_btn.isEnabled()
        m._prepare_selected_change()
        assert m.tabs.currentIndex() == 5 and m.cod_new.text() == f"{before:05d}"
        assert m.info["coding"] == 4102
        m.tabs.setCurrentIndex(m.CHANGES_TAB)
        m.chg_table.selectRow(0)
        m._prepare_selected_change()
        assert m.tabs.currentIndex() == 4 and m.ad_channel.value() == 1 and m.ad_new.value() == 128
        # o relatório desta visita leva as duas alterações
        from rad import journal
        visit = journal.changes_for_visit(w._report_items("module"), simulated=True)
        assert [c["kind"] for c in visit][-2:] == ["coding", "adaptation"]
        assert w.options.scale.currentData() == "1"
        w.worker.submit("disconnect")
        assert _wait(app, lambda: not w.nav_btns["module"].isEnabled())
    finally:
        w.close()
        app.processEvents()


def test_license_demo_mode_and_update_notice():
    app, w = _window()
    from rad import ed25519, licensing, license_pubkey
    from PySide6.QtWidgets import QMessageBox
    secret = bytes(range(32))
    old = (license_pubkey.PUBLIC_KEY, licensing.DIRECTORY, QMessageBox.information, QMessageBox.warning)
    license_pubkey.PUBLIC_KEY = ed25519.public_key(secret).hex()
    licensing.DIRECTORY = tempfile.mkdtemp()
    import datetime
    licensing.set_trial_start(datetime.date.today() - datetime.timedelta(days=licensing.TRIAL_DAYS + 1))
    shown = []
    QMessageBox.information = staticmethod(lambda *a, **k: shown.append(a[2]) or QMessageBox.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: shown.append(a[2]) or QMessageBox.Ok)
    try:
        w.apply_license()
        assert not w.worker.licensed and w.demo_badge.isVisibleTo(w)
        assert "demonstração" in w.options.lic_state.text()
        # chave de outro PC: recusada e explicada
        w.options.lic_key.setPlainText(licensing.make_key(secret, "Oficina", "ZZZZ-ZZZZ-ZZZZ"))
        w.options._activate_license()
        assert shown and "outro PC" in shown[-1] and not w.worker.licensed
        # chave deste PC: activa e tira o aviso
        w.options.lic_key.setPlainText(licensing.make_key(secret, "Oficina Teste", licensing.machine_id()))
        w.options._activate_license()
        app.processEvents()
        assert w.worker.licensed and not w.demo_badge.isVisibleTo(w)
        # o botão está numa página que não é a actual: verifica-se o estado que show_license() lhe deu
        assert "Oficina Teste" in w.options.lic_state.text() and not w.options.lic_remove_btn.isHidden()

        w.options.update_done.emit({"available": True, "version": "9.9.9", "url": "https://example.com",
                                    "download": None, "notes": ""}, False)
        app.processEvents()
        assert w.update_btn.isVisibleTo(w) and "9.9.9" in w.update_btn.text()
        w.options.update_done.emit(__import__("rad.updates", fromlist=["x"]).UpdateError("Sem ligação"), False)
        app.processEvents()
        assert "Sem ligação" in w.options.upd_lbl.text()
    finally:
        license_pubkey.PUBLIC_KEY, licensing.DIRECTORY, QMessageBox.information, QMessageBox.warning = old
        w.close()
        app.processEvents()


def test_update_installs_by_itself_on_start_and_while_the_customer_has_not_started():
    app, w = _window()
    import main
    from rad import autoupdate
    old = (autoupdate.ready_on_start, autoupdate.install_on_start)
    calls = []
    autoupdate.ready_on_start = lambda mode=None: {"version": "9.9.9"}
    autoupdate.install_on_start = lambda launcher=None, **k: calls.append("start") or True
    try:
        assert main.update_on_start() and calls == ["start"]           # versão por instalar: instala antes da janela
        autoupdate.install_on_start = lambda launcher=None, **k: False
        assert not main.update_on_start()                              # não lançou: o programa abre normalmente
    finally:
        autoupdate.ready_on_start, autoupdate.install_on_start = old
    try:
        assert w._idle_for_update()                                    # ainda não começou: actualiza logo
        w.home.vehicle_edits["plate"].textEdited.emit("AA-00-AA")
        assert not w._idle_for_update()                                # escreveu: fica para quando fechar
        w._started_work = False
        w.show_page("history")
        assert not w._idle_for_update()
        w.show_page("home")
        w._apply_update_now()                                          # sem versão descarregada: não fecha
        assert w.isVisible()
        # voltou à versão anterior porque a nova não abriu: avisa uma vez
        from PySide6.QtWidgets import QMessageBox
        shown, old_warning, old_notice = [], QMessageBox.warning, autoupdate.rollback_notice
        QMessageBox.warning = staticmethod(lambda *a, **k: shown.append(a[2]) or QMessageBox.Ok)
        autoupdate.rollback_notice = lambda current=None: {"bad": "9.9.9", "version": "1.0.0"}
        try:
            w._after_update()
            assert _wait(app, lambda: shown, 4) and "9.9.9" in shown[0] and "voltou" in shown[0]
        finally:
            QMessageBox.warning, autoupdate.rollback_notice = old_warning, old_notice
        # o fornecedor retirou a versão já descarregada: deixa de a anunciar
        forgot = []
        old_forget = autoupdate.forget_withdrawn
        autoupdate.forget_withdrawn = lambda v: forgot.append(v) or True
        try:
            w.update_btn.show()
            w._update_checked({"available": False, "version": "1.0.0"}, False)
            assert forgot == ["1.0.0"] and w.update_btn.isHidden()
        finally:
            autoupdate.forget_withdrawn = old_forget
    finally:
        w.close()
        app.processEvents()


def test_english_interface_end_to_end():
    """Com o idioma em inglês: menu, módulo, avarias e relatório em inglês (a lógica é a mesma)."""
    from rad import i18n, report
    i18n.set_language("en")
    w = None
    try:
        app, w = _window()
        assert w.nav_btns["home"].text() == "Home" and w.nav_btns["options"].text() == "Options"
        w.connect_module(0x01)
        assert _wait(app, lambda: w.nav_btns["module"].isEnabled()), "did not connect to the engine"
        assert w.module.info["module"] == "Engine electronics"
        assert w.module.tabs.tabText(w.module.FAULTS_TAB).startswith("Faults")
        w.module._quick_faults()
        assert _wait(app, lambda: w.module.fault_table.rowCount() == 2)
        assert w.module.fault_table.item(1, 3).text() in ("High", "Medium", "Low")
        html = report.build_html({"name": "Garage"}, {"plate": "EN-00-01"}, w._report_items("module"))
        assert "Vehicle health" in html and "Customer" in html
        w.worker.submit("disconnect")
        assert _wait(app, lambda: not w.nav_btns["module"].isEnabled())
    finally:
        i18n.set_language("pt")                  # sempre, mesmo que a janela não abra
        if w is not None:
            w.close()
            app.processEvents()


def test_failed_connect_and_repeated_clicks():
    app, w = _window()
    from PySide6.QtWidgets import QMessageBox
    shown = []
    old = QMessageBox.warning
    QMessageBox.warning = staticmethod(lambda *a, **k: shown.append(a[2]) or QMessageBox.Ok)
    try:
        w.worker.submit("configure", w.options.config())
        assert _wait(app, lambda: not w.worker.is_busy)
        w.worker.submit("connect", 0x01)              # abre a porta; depois tira-se o eco
        assert _wait(app, lambda: w.nav_btns["module"].isEnabled())
        w.worker.submit("disconnect")
        assert _wait(app, lambda: not w.nav_btns["module"].isEnabled() and not w.worker.is_busy)
        w.worker.kl.ser.echo = False                  # agora o "cabo saiu do carro"
        w.toast.last = ("", "")
        w.connect_module(0x01)
        w.connect_module(0x17)                         # segundo clique enquanto liga: ignorado
        assert w.toast.last[0].startswith("Aguarde")
        assert _wait(app, lambda: shown and not w.worker.is_busy)
        app.processEvents()
        assert "ignição" in shown[0] and len(shown) == 1
        assert "eco" not in shown[0].lower().split()           # sem termos técnicos para o cliente
        assert "perdida" not in w.toast.last[0]        # nunca esteve ligado: não se "perdeu"
        assert not w.reconnect_btn.isVisible() and w.conn_lbl.text() == "Sem ligação"
        # Auto-Scan sem eco: pára logo e explica na página
        w._home_go("autoscan_start")
        assert _wait(app, lambda: not w.scan.running and not w.worker.is_busy)
        app.processEvents()
        assert "ignição" in w.scan.empty.text() and not w.scan.empty.isHidden()
        assert w.scan.tree.isHidden() and w.scan.ok_lbl.isHidden()
    finally:
        QMessageBox.warning = old
        w.close()
        app.processEvents()


def test_custom_widgets_paint():
    app = _app()
    from PySide6.QtWidgets import QWidget
    from rad import vag_data
    from rad.ui.widgets import (GaugeCell, HealthRing, HeroBanner, LiveChart, ModuleTile, PulseIndicator,
                                VehicleMap)
    from rad.ui.pages.common import FaultAdviceCard
    ok_item = {"address": 0x17, "module": "Painel", "status": "ok", "info": {"part": "1J0920926C"}, "faults": []}
    bad_item = {"address": 0x03, "module": "ABS", "status": "ok", "info": {"part": "1C0907379K"},
                "faults": [vag_data.decode_fault(283, 0x23)]}
    err_item = {"address": 0x42, "module": "Desconhecido", "status": "error", "error": "Sem resposta"}
    m = VehicleMap()
    m.resize(340, 560)
    m.set_scanning(True)
    m.set_probe(0x01)
    for it in (ok_item, bad_item, err_item, {"address": 0x08, "status": "absent"}):
        m.add_item(it)
    assert set(m.items) == {0x17, 0x03, 0x42}
    assert m._hit(m._pos(0x03)) == 0x03 and m._hit(m._pos(0x55)) is None    # só os lidos são clicáveis
    gauge = GaugeCell(1)
    gauge.resize(220, 240)
    for v in (0, 900, 4200, 7000, -5):
        gauge.set({"formula": 1, "unit": "/min", "a": 0, "b": 0, "value": str(v), "numeric": float(v)})
    assert gauge.hi >= 7000 and gauge.lo < 0 and gauge.peak == 7000
    gauge.set({"formula": 0x3F, "unit": "", "a": 0, "b": 0, "value": "ABC", "numeric": None})
    ring = HealthRing(96)
    ring.set_score(42)
    chart = LiveChart()
    for i in range(50):
        chart.add(i * 0.1, (i % 7) * 10.0)
    pulse = PulseIndicator()
    pulse.set_mode("on")
    hero = HeroBanner()
    hero.resize(1000, 230)
    card = FaultAdviceCard()
    card.set_fault(vag_data.decode_fault(1247, 0x1E), 0x01)
    assert "N75" in card.body.text()
    card.set_fault({"vag": "09999", "pcode": "", "desc": "?", "elab_code": 3, "intermittent": True}, None)
    widgets = [m, gauge, ring, chart, pulse, hero, card] + [ModuleTile(i) for i in (ok_item, bad_item, err_item)]
    for wd in widgets:
        if isinstance(wd, QWidget) and wd.width() < 50:
            wd.resize(260, 200)
        pm = wd.grab()                       # corre o paintEvent
        assert not pm.isNull()
    app.processEvents()


def test_recording_and_validation_from_the_interface():
    app, w = _window()
    from rad import capture
    from rad.ui.pages.validation import ValidationDialog
    try:
        assert w.options.capture_btn.text() == "Gravar comunicação"
        w.options.capture_btn.click()
        assert _wait(app, lambda: w.options.recording), "a gravação não começou"
        assert w.options.capture_btn.text() == "Parar gravação" and capture.active() is not None
        w.options.capture_btn.click()
        assert _wait(app, lambda: not w.options.recording), "a gravação não parou"
        assert capture.active() is None and capture.recent(1)
        dlg = ValidationDialog(w.worker, {"plate": "VA-11-DA"}, w)
        dlg.show()
        dlg.start()
        assert dlg.running and not dlg.close_btn.isEnabled()
        dlg.reject()                                     # não fecha a meio
        assert dlg.isVisible()
        assert _wait(app, lambda: not dlg.running, 30), "a validação não terminou"
        assert dlg.tree.topLevelItemCount() == 9 and dlg.report_btn.isEnabled()
        assert dlg.report["report_path"].endswith(".html") and dlg.verdict.text()
        dlg.reject()
        assert not dlg.isVisible()
    finally:
        w.close()
        app.processEvents()


def test_report_dialog_preview_and_vehicle_register():
    app, w = _window()
    from rad import history, vag_data
    from rad.ui.pages.report_dialog import ReportDialog, build_function
    try:
        items = [{"address": 0x03, "module": "ABS", "status": "ok",
                  "info": {"part": "1C0907379K", "component": "ABS", "protocol": "KWP2000", "baud": 10400,
                           "coding": 18719, "coding_digits": 7},
                  "faults": [vag_data.decode_fault(283, 0x23)]}]
        dlg = ReportDialog(build_function({"name": "Oficina"}, items, {"simulated": True}, None),
                           {"plate": "rp-12-34", "client": "Rui"}, "", None, w)
        text = dlg.preview.toPlainText()
        assert "Relatório de diagnóstico" in text and "estado 0x23" not in text
        dlg.tech_rb.setChecked(True)
        app.processEvents()
        assert dlg.variant == "technical" and "estado 0x23" in dlg.preview.toPlainText()
        dlg.edits["vin"].setText("wauzzz8l71a123456")
        dlg.refresh()
        assert dlg.vehicle()["plate"] == "RP-12-34" and dlg.vehicle()["vin"] == "WAUZZZ8L71A123456"
        dlg.reject()
        # registo de veículos: o diagnóstico guardado aparece em Histórico → Veículos e volta ao Início
        history.save_session("modulo", {"plate": "RP-12-34", "client": "Rui", "vin": "WAUZZZ8L71A123456"}, items)
        w.hist.refresh()
        w.hist.search.setText("123456")                       # pesquisa pelo VIN
        app.processEvents()
        assert w.hist.car_list.count() == 1 and w.hist.table.rowCount() == 1
        assert "WAUZZZ8L71A123456" in w.hist.car_sub.text()
        w.home.clear_vehicle()
        w.hist._use_vehicle()
        app.processEvents()
        assert w.home.vehicle()["client"] == "Rui" and "visita" in w.home.known_lbl.text()
        w.home.clear_vehicle()
        w.home.vehicle_edits["plate"].setText("rp12 34")
        assert w.home.fill_known("plate")["client"] == "Rui" and w.home.vehicle()["client"] == "Rui"
    finally:
        w.close()
        app.processEvents()



def test_demo_mode_limits_on_a_real_port():
    """Sem licença e numa porta real: só 2 avarias à vista, medição limitada, sem CSV/testes guiados."""
    app, w = _window()
    from rad import licensing, vag_data
    from PySide6.QtWidgets import QMessageBox
    old = (QMessageBox.information, w.worker.licensed, dict(w.worker.cfg))
    shown = []
    QMessageBox.information = staticmethod(lambda *a, **k: shown.append(a[2]) or QMessageBox.Ok)
    try:
        w.worker.licensed = False
        w.worker.cfg["port"] = "COM250"
        assert not w.worker.full_access()
        w.module.info = {"address": 1, "module": "Motor", "part": "", "component": ""}
        faults = [vag_data.decode_fault(c, 0x23) for c in (283, 522, 1247, 16683)]
        w.module.show_faults(faults)
        t = w.module.fault_table
        assert t.rowCount() == 4 and "4" in w.module.fault_count.text()
        assert "1247" not in t.item(2, 0).text() and "🔒" in t.item(2, 0).text()
        assert "1247" not in w.module.faults_text() and "16683" not in w.module.faults_text()
        w.module._toggle_csv()
        assert shown and "licença" in shown[-1] and not w.module.csv_writer
        w.module.demo_live_left = 0
        n = len(shown)
        w.module.groups[0].enable.setChecked(True)
        w.module._toggle_mvb()
        assert len(shown) == n + 1 and w.worker.live_mode != "read"
        # Auto-Scan: 2 avarias livres para o carro inteiro; relatório de texto, histórico e comparação aguentam
        w.scan.items, w.scan._demo_free = [], licensing.FREE_FAULTS
        info = {"part": "x", "component": "y"}
        w.scan.on_progress(1, 2, {"address": 1, "module": "Motor", "status": "ok", "info": info,
                                  "faults": faults[:1]})
        w.scan.on_progress(2, 2, {"address": 3, "module": "ABS", "status": "ok", "info": info,
                                  "faults": faults[1:]})
        hidden = [f for it in w.scan.items for f in it["faults"] if f.get("locked")]
        assert len(hidden) == 2 and sum(len(it["faults"]) for it in w.scan.items) == 4
        text = w.scan.report()
        assert "1247" not in text and "16683" not in text and "00283" in text
        from rad import history, report
        assert history.compare(w.scan.items, w.scan.items)["new"] == []
        for variant in ("client", "technical"):
            html = report.build_html({"name": "Oficina"}, {"plate": "AA-00-AA"}, w.scan.items, meta={"demo": True},
                                     variant=variant)
            assert "1247" not in html and "16683" not in html and "DEMONSTRAÇÃO" in html
        sid = history.save_session("autoscan", {"plate": "DEMO-01"}, w.scan.items)
        w.hist.refresh()
        w.hist.full_access = w.worker.full_access
        assert w.hist.select_session(sid)
        app.processEvents()
        assert w.hist.detail.topLevelItemCount() == 2
        history.delete_session(sid)
        # simulador: tudo à vista
        w.worker.cfg["port"] = old[2]["port"]
        assert w.worker.full_access()
        w.module.show_faults(faults)
        assert "1247" in w.module.fault_table.item(2, 0).text()
    finally:
        QMessageBox.information = old[0]
        w.worker.licensed = old[1]
        w.worker.cfg.clear()
        w.worker.cfg.update(old[2])
        w.close()
        app.processEvents()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)


def test_home_leads_with_the_car_and_shows_recent_cars_in_colour():
    """Página Início (redesenho): uma linha com o estado do cabo e do carro, o carro na oficina com o botão do
    Auto-Scan, e os últimos carros com a matrícula e o estado em cor; clicar num carro reabre-o."""
    app = _app()
    from rad.ui.pages.home import HomePage
    from rad.ui.style import BAD, OK, WARN
    from rad import connstate
    h = HomePage()
    h.resize(1200, 800)
    h.show()
    app.processEvents()
    assert not hasattr(h, "stat_lbls")                                   # sem estatísticas do mês
    h.set_port("Escolha a porta do cabo em Opções")
    assert h.cable_btn.isVisibleTo(h) and h.sim_btn.isVisibleTo(h)      # sem cabo: atalho para o configurar
    h.set_port("Cabo escolhido: COM3", ok=True)
    assert h.port_pill.text() == "escolhido" and h.sim_btn.isVisibleTo(h) and not h.cable_btn.isVisibleTo(h)
    h.set_port("Modo de simulação", sim=True)
    assert h.port_pill.text() == "simulador" and not h.sim_btn.isVisibleTo(h)
    h.set_link(connstate.LinkStatus(connstate.ECU_CONNECTED, "Ligado a 01"))
    assert h.link_pill.text() == connstate.LABELS[connstate.ECU_CONNECTED]
    for n, (faults, tone) in enumerate(((0, OK), (2, WARN), (7, BAD))):
        h._add_recent(f"AA-0{n}-AA", "Golf IV", "12/11  10:00", f"{faults} avaria(s)", tone,
                      vehicle={"plate": f"AA-0{n}-AA", "model": "VW Golf IV", "client": "Rui"})
    assert h.recent.count() == 3
    row = h.recent.itemWidget(h.recent.item(2))
    texts = [lb.text() for lb in row.findChildren(type(h.link_pill))]
    assert "AA-02-AA" in texts and any(BAD in lb.styleSheet() for lb in row.findChildren(type(h.link_pill)))
    h.vehicle_edits["km"].setText("123")
    h._open_recent(h.recent.item(1))                                     # reabrir um carro da lista
    v = h.vehicle()
    assert v["plate"] == "AA-01-AA" and v["model"] == "VW Golf IV" and v["client"] == "Rui" and v["km"] == ""
    h.close()



def test_module_field_opens_by_address_or_by_a_single_name():
    from rad.ui.pages.module_select import ModuleSelectPage
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    page = ModuleSelectPage()
    opened = []
    page.connect_req.connect(opened.append)
    page.filter.setText("17")
    page._go_manual()
    page.filter.setText("airbag")
    assert [a for a in page.order if page._matches(a)] == [0x15]
    page._go_manual()
    assert opened == [0x17, 0x15]
    page.mark_scan([{"address": 0x01, "status": "ok", "faults": [{}]}, {"address": 0x17, "status": "ok",
                                                                        "faults": []}])
    page.filter.setText("")
    assert not page.cards[0x01].isHidden() and page.mod_btns[0x01].isHidden()
    assert "1 avaria" in page.cards[0x01].pill.text() and page.others_title.text() == "Outros controladores"


def test_shortcuts_open_the_right_options_tab_and_plateless_visits_stay_apart():
    app, w = _window()
    from rad import history
    try:
        w.options.show_tab("program")
        w.demo_badge.click()
        assert w.stack.currentWidget() is w.options and w.options.tabs.currentIndex() == 2      # Licença
        w._home_go("options")
        assert w.options.tabs.currentIndex() == 0                                              # Cabo
        a = history.save_session("obd", {"plate": "", "client": "Ana Semplaca", "model": "Clio"}, [])
        b = history.save_session("obd", {"plate": "", "client": "Rui Semplaca", "model": "Golf"}, [])
        w.hist.refresh()
        w.hist.search.setText("Rui Semplaca")
        assert w.hist.car_list.count() == 1 and "Ana Semplaca" not in w.hist.car_sub.text()
        assert not w.hist.use_btn.isEnabled()                    # sem matrícula não há carro para reabrir
        w.hist.search.clear()
        history.delete_session(a)
        history.delete_session(b)
    finally:
        w.close()
        app.processEvents()
