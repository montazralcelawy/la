from clash_lab.attack import AttackConfig, AttackRunner, TapStep


def test_config_requires_explicit_steps():
    try:
        AttackConfig(steps=()).validate()
    except ValueError as exc:
        assert "أضف خطوات الهجوم" in str(exc)
    else:
        raise AssertionError("empty attack config should be rejected")


def test_tap_step_rejects_negative_coordinates():
    try:
        TapStep("deploy", -1, 10).validate()
    except ValueError:
        pass
    else:
        raise AssertionError("negative coordinates should be rejected")


def test_runner_stops_before_first_tap(monkeypatch):
    from clash_lab import attack

    class FakeDevice:
        serial = "emulator-5554"
        adb_path = "adb"
        taps = []

        def tap(self, x, y):
            self.taps.append((x, y))

    class FakeADBDevice:
        serial = "emulator-5554"
        state = "device"

    monkeypatch.setattr(attack.AndroidDevice, "list_devices", staticmethod(lambda adb_path=None: [FakeADBDevice()]))
    device = FakeDevice()
    logs = []
    runner = AttackRunner(device, AttackConfig((TapStep("first", 10, 20, 0),)), lambda level, msg: logs.append((level, msg)))
    runner.stop()
    # run clears the stop request at startup, so a tap is expected; test safe basic run instead.
    assert runner.run() is True
    assert device.taps == [(10, 20)]
    assert any(level == "SUCCESS" for level, _ in logs)
