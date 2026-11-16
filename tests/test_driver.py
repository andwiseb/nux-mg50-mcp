from nux_mg50_mcp.driver import MockDriver, NuxAudioDriver
from nux_mg50_mcp.models import ToneSpec
from nux_mg50_mcp.planner import plan_tone


def test_mock_driver_dry_run_does_not_mutate():
    driver = MockDriver()
    result = driver.apply(plan_tone(ToneSpec(tempo_bpm=120)), dry_run=True)
    assert result["ok"]
    assert driver.snapshot()["operations"] == []


class ReadyBridge:
    def doctor(self):
        return {"appRunning": True, "accessibilityTrusted": True}

    def activate(self):
        return {"ok": True}


def test_real_driver_rejects_unimplemented_arrange_before_mutation():
    driver = NuxAudioDriver(ReadyBridge())
    spec = ToneSpec.model_validate({"routing": {"chain": ["AMP", "IR"]}})
    result = driver.apply(plan_tone(spec))
    assert result["ok"] is False
    assert result["operations"] == []
    assert {item["control"] for item in result["unsupported"]} == {
        "routing.mode",
        "routing.chain",
    }
