from nux_mg50_mcp.device_catalog import CATALOG, DEVICE_SURFACE, capabilities


def test_catalog_covers_all_ir_slots_and_known_global_controls():
    assert len(CATALOG["IR"]["slots"]) == 60
    assert CATALOG["IR"]["slots"][0] == "M1960+V30"
    assert CATALOG["IR"]["slots"][31] is None
    assert CATALOG["IR"]["slots"][48] == "G HBird"

    global_eq = CATALOG["settings"]["global_eq"]
    assert {"6.4k", "10k", "lpf", "lpf_enabled"} <= set(global_eq)
    console = CATALOG["settings"]["output_console"]
    assert {"usb_in_1/2", "usb_in_3/4", "phones_mute", "xlr_mute"} <= set(console)


def test_catalog_describes_non_numeric_model_controls():
    assert CATALOG["EFX"]["models"]["Touch Wah"]["direction"] == ["up", "down"]
    assert CATALOG["AMP"]["models"]["Jazz Clean"]["bright"] == {"type": "boolean"}
    assert CATALOG["WAH"]["models"]["Horse Wah"]["range"]["max"] == 6
    assert capabilities("AMP")["capabilities"] == CATALOG["AMP"]
    assert capabilities("AMP2")["related"]["image_models"] == CATALOG["AMP_IMAGE"]
    assert capabilities("send return")["module"] == "S/R"
    assert capabilities()["device"] == DEVICE_SURFACE
    assert DEVICE_SURFACE["tempo_bpm"] == {"type": "number", "min": 40, "max": 240}
