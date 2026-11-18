from nux_mg50_mcp.bridge import AccessibilityBridge, UINode


class FakeBridge(AccessibilityBridge):
    def __init__(self):
        self.calls = []

    def nodes(self):
        return [
            UINode(
                1,
                "AXGroup",
                "INPUTS\nBRIGHT\nGAIN\nBASS\nMIDDLE\nTREBLE",
                "",
                "",
                100,
                100,
                600,
                160,
            ),
            UINode(2, "AXStaticText", "", "", "25", 350, 130, 60, 70),
            UINode(3, "AXStaticText", "", "", "45", 430, 130, 60, 70),
            UINode(4, "AXStaticText", "", "", "65", 510, 130, 60, 70),
            UINode(5, "AXStaticText", "", "", "45", 590, 130, 60, 70),
        ]

    def run(self, *args):
        self.calls.append(args)
        return {"ok": True}


def test_set_parameter_targets_matching_readout_and_delta():
    bridge = FakeBridge()
    readout = bridge.set_parameter("middle", 60)
    assert readout.index == 4
    assert bridge.calls == [("scroll-screen", 540.0, 165.0, -1, 5)]


def test_set_parameter_supports_unit_values_and_wrapped_settings_grid():
    bridge = FakeBridge()
    bridge.nodes = lambda: (
        [
            UINode(
                1,
                "AXGroup",
                "Input Trim:\nINST.1\nINST.2\nINST.3\nINST.4\nINST.5\nINST.6",
                "",
                "",
                0,
                0,
                420,
                398,
            ),
        ]
        + [
            UINode(2 + i, "AXStaticText", "", "", "0dB", x, y, 71, 82)
            for i, (x, y) in enumerate(
                ((43, 107), (135, 107), (227, 107), (319, 107), (135, 224), (227, 224))
            )
        ]
    )
    readout = bridge.set_parameter("INST.5", -3)
    assert readout.index == 6
    assert bridge.calls[-1][-2:] == (-1, 3)


def test_bounded_readout_saturates_then_walks_to_absolute_target():
    bridge = FakeBridge()
    readout = UINode(2, "AXTextField", "", "", "stale", 100, 100, 60, 30)

    bridge.set_bounded_numeric_readout(readout, 43, minimum=40, maximum=240)

    assert bridge.calls == [
        ("scroll-screen", 130.0, 115.0, -1, 100),
        ("scroll-screen", 130.0, 115.0, -1, 100),
        ("scroll-screen", 130.0, 115.0, 1, 3),
    ]


def test_boolean_module_switch_is_dragged_to_an_absolute_pole():
    bridge = FakeBridge()

    bridge.set_parameter("bright", False)

    assert bridge.calls == [("drag-screen", 287.5, 180.0, 287.5, 195.0)]
