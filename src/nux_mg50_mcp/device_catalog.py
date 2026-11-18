"""Human-audited MG-50Li control catalogue.

This is descriptive rather than a protocol table. Unknown names are allowed so a new
NUX Audio/firmware release remains usable through the generic MCP surface.
"""

from __future__ import annotations

from typing import Any

from .catalog import canonical_module

PERCENT = {"type": "number", "min": 0, "max": 100}
BOOLEAN = {"type": "boolean"}

DEVICE_SURFACE: dict[str, Any] = {
    "presets": {"range": "1A-99C", "save_default": False},
    "preset_volume_db": {"type": "number", "min": -12, "max": 12},
    "scenes": [1, 2, 3],
    "tempo_bpm": {"type": "number", "min": 40, "max": 240},
    "stomp_switches": ["A", "B", "C"],
}


def percent(*names: str) -> dict[str, dict[str, Any]]:
    return {name: PERCENT for name in names}


def grouped(*groups: tuple[str, tuple[str, ...]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for names, parameters in groups:
        for name in names.split("|"):
            output[name] = percent(*parameters)
    return output


CATALOG: dict[str, Any] = {
    "routing": {
        "modes": ["serial", "parallel_merge", "split_outputs"],
        "parameters": {"split_mode": ["dual", "chain_a_b"], "a_level": PERCENT, "b_level": PERCENT},
    },
    "NG": {
        "models": {
            "Noise Gate": percent("sens", "decay"),
            "Hum Noise": {
                "freq": ["50hz", "60hz"],
                "harmo": ["odd", "even"],
                "mode": ["slight", "severe"],
            },
        }
    },
    "CMP": {
        "models": {
            "Rose Comp": percent("sustain", "level"),
            "K Comp": percent("sustain", "level", "clipping"),
            "Studio Comp": percent("thr", "ratio", "gain", "release"),
        }
    },
    "EFX": {
        "models": grouped(
            ("Distortion+", ("output", "sensitivity")),
            ("RC Boost|AC Boost", ("gain", "vol", "bass", "treble")),
            (
                "Dist One|T Screamer|Blues Drv|Red Dirt|Crunch|Screamer|Turbo OD|OD/Dist",
                ("level", "tone", "drive"),
            ),
            ("Morning Drv|Full-OD HP|Full-OD LP|British OD", ("volume", "drive", "tone")),
            ("Eat Dist", ("distortion", "filter", "volume")),
            ("Muff Fuzz", ("volume", "tone", "sustain")),
            ("Katana", ("boost", "volume")),
            ("Red Fuzz", ("gain", "tone", "output")),
            ("ST Singer", ("volume", "gain", "filter")),
            ("Touch Wah", ("type", "decay", "sens", "direction", "level")),
            ("Nob ODR", ("drive", "level", "spectrum")),
            ("Crazy Pro OD", ("volume", "drive", "bass", "treble")),
            ("Horseman OD", ("gain", "treble", "output")),
            ("Riv Blueflog Stack|Riv Blueflog Combo", ("level", "gain", "tone")),
            ("80s' Dist", ("level", "tone", "dist")),
            ("90s' Heavy Dist", ("level", "bass", "treble", "dist")),
            ("Oct Bassline", ("dry", "range", "sub")),
            ("Mono Octave", ("sub", "dry", "up")),
        )
    },
    "AMP": {
        "models": grouped(
            ("Jazz Clean|Twin Rvb", ("inputs", "bright", "gain", "bass", "middle", "treble")),
            (
                "Deluxe Rvb|Vib King|Mr.Z38|Princetone|Match D30",
                ("inputs", "gain", "bass", "treble"),
            ),
            ("Bassmate", ("inputs", "normal", "bright", "bass", "middle", "treble", "pres.")),
            ("Tweedy", ("inputs", "inst", "mic", "tone")),
            (
                "Hiwire",
                ("inputs", "normal", "bright", "bass", "middle", "treble", "master", "pres."),
            ),
            (
                "Cali Crunch",
                ("inputs", "vol1", "vol2", "bass", "middle", "treble", "master", "pres."),
            ),
            ("Class A15", ("inputs", "gain")),
            ("Class A30", ("inputs", "gain", "bass", "treble")),
            (
                "Plexi 100W|Plexi 45|1987 X 50W|Brit Blues",
                ("inputs", "normal", "bright", "bass", "middle", "treble", "pres."),
            ),
            ("Brit 800", ("inputs", "gain", "master", "bass", "middle", "treble", "pres.")),
            (
                "SLO 100|Die VH4|Brit 2000|Uber Higain|Vivo",
                ("gain", "master", "bass", "middle", "treble", "pres.", "deep"),
            ),
            ("Fireman HBE|Dual Rect", ("gain", "master", "bass", "middle", "treble", "pres.")),
            ("Budda", ("gain", "bass", "treble")),
            ("Lionstar", ("drive", "voice", "gain", "bass", "middle", "treble", "master", "pres.")),
            ("Stageman", ("gain", "bass", "middle", "treble")),
        )
    },
    "AMP_IMAGE": {
        "models": grouped(
            (
                "Deluxe Rvb|Class A30|Blues Jr Ltd|Super Cham Cln|Super Cham Lead|Twin Custom15|Hot Road Dlx Nor|Hot Road Dlx Drive|Match DC30|TK Fal Rhythm|TK Fal Lead|TK Gal60 Rhythm|TK Gal60 Lead|T-R Exo15",
                ("gain", "volume", "bass", "treble"),
            ),
            (
                "Fireman HBE|Mars JV410 Cln|Mars JV410 Crunch|MB Triple Rect Raw|MB Triple Rect Vintage|MB Triple Rect Modern|MB Cali 50 Nor|Ora Rock 50th Lead|T-R GMaster50 Cln|T-R GMaster50 Lead|T-R DraganLtd OD|T-R Studio Plus Cln|Claymore MkIII Cln|Claymore MkIII Juicy|Claymore MkIII Crush|Deezl VH4 HG|Mars VS 8100 HG|Mars Asto 50 HG|MB RA-100 HG|Ora Dual Dark CHA|Ora Dual Dark CHB|Randl Satan HG|Randl Satan HG Fat|Riv Knuckle Tre&Tre",
                ("gain", "volume", "bass", "middle", "treble"),
            ),
            ("PV 5150", ("gain", "volume", "bass", "middle", "treble", "pres.", "depth")),
            (
                "AGL DB700 Bass|AMG SVT Pro Bass|MB Walk Bass",
                ("gain", "volume", "bass", "middle", "mid freq", "treble"),
            ),
            (
                "XTC Blue|XTC Red",
                ("gain", "volume", "bass", "middle", "treble", "pres.", "depth", "level"),
            ),
        )
    },
    "POWER_AMP": {
        "models": {
            "Solid State": percent("level"),
            "EL84": percent("cut", "level"),
            "EL34": percent("bias", "level"),
            "6V6": percent("bias", "level"),
            "6L6": percent("bias", "level"),
        }
    },
    "IR": {
        "modes": ["mono", "stereo"],
        "microphones": ["B52", "C414", "C3000", "DYN421", "R121", "R122", "S57", "U87"],
        "positions": ["cone edge", "cone", "cap edge", "cap"],
        "distances": ['0"', '2"', '4"', '6"', '8"'],
        "parameters": ["level_db", "low_cut_hz", "high_cut_hz", "pan"],
        "slots": [
            "M1960+V30",
            "FBluesDeville112",
            "M425+G12C",
            "M1960+G12M",
            "M1974+G12M",
            "Budda112+AlnicoBlue",
            "MBMK2+EV12",
            "AC15+AlnicoSilver",
            "AC30+AlnicoBlue",
            "F112+V-Type",
            "Die412+V30",
            "MBOS412+V30",
            "Fire412+M75",
            "Hiwa412+Fane",
            "JC120",
            "MBLStar+AlnicoRub",
            "Match412+G12H30",
            "Dr. Z212+G12M",
            "M1960+G1250",
            "MSilverJubilee+G12T",
            "FPrince112+Ten30",
            "SLO412+G12M",
            "FSuperRvb410+CTS",
            "FDeluxe112+AlnicoB",
            "FTwinRvb+JENC12K",
            "BOG412+V-Type",
            "F112+EMIGA-SC64",
            "AVE Friedboy V30",
            "AVE Jeezus Pierce",
            "AVE Fuzz Chain",
            "AVE OD Chain",
            None,
            None,
            None,
            None,
            None,
            "AGL DB810",
            "AMP SV810",
            "MKB 410",
            "TRC 410",
            "AMP SV410",
            "Bassguy 410",
            "Eden 410",
            "AMP SV212",
            None,
            None,
            None,
            None,
            "G HBird",
            "G J-15",
            "M D45",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ],
    },
    "EQ": {
        "models": {
            "6-Band EQ": {
                name: {"min": -15, "max": 15, "unit": "dB"}
                for name in ("100", "220", "500", "1.2k", "2.6k", "6.4k", "level")
            },
            "Align EQ": {"hpf": [50, 80, 160]}
            | percent("110", "340", "660", "1300", "2600", "5000", "volume"),
            "10-Band EQ": {
                name: {"min": -12, "max": 12, "unit": "dB"}
                for name in (
                    "vol",
                    "31.25",
                    "62.5",
                    "125",
                    "250",
                    "500",
                    "1k",
                    "2k",
                    "4k",
                    "8k",
                    "16k",
                    "gain",
                )
            },
        }
    },
    "DLY": {
        "models": grouped(
            ("Analog Delay", ("repeat", "echo", "inten.")),
            ("Digi Delay", ("e.level", "f.back", "d.time")),
            ("Modulation", ("time", "level", "mod", "repeat")),
            ("Tape Echo", ("time", "level", "repeat")),
            ("Reverse", ("time", "mix", "f.back")),
            ("Pan Delay", ("time", "repeat", "d.level")),
            ("Phi Delay", ("mix", "repeats", "time")),
            ("Stereo Delay", ("l.level", "l.repeat", "l.time", "r.level", "r.repeat", "r.time")),
        )
    },
    "RVB": {
        "models": grouped(
            ("Room", ("decay", "tone", "level")),
            ("Hall", ("decay", "pre.d", "liveliness", "level")),
            ("Plate|Spring", ("decay", "level")),
            ("Shimmer", ("mix", "decay", "shim")),
            ("Damp", ("mix", "depth")),
        )
    },
    "S/R": {
        "models": {
            "S/R Ch 1": {
                "mode": ["branch", "serial"],
                "send 1": {"min": -15, "max": 15},
                "return 1": {"min": -15, "max": 15},
            }
        }
    },
    "WAH": {
        "models": {
            "Clyde": {},
            "Cry BB": {},
            "V847": {},
            "Horse Wah": percent("contour") | {"range": {"type": "integer", "min": 1, "max": 6}},
            "Octave-Shift": {"mode": ["up", "down"]},
        }
    },
    "MOD": {
        "models": grouped(
            ("CE-1", ("inten.", "depth", "rate")),
            ("CE-2", ("rate", "depth")),
            ("ST.Chorus", ("inten.", "width", "rate")),
            ("Vibrator|Tremolo", ("rate", "depth")),
            ("Detune", ("shift-l", "mix", "shift-r")),
            ("Flanger", ("level", "rate", "width", "f.back")),
            ("Phaser 90", ("speed",)),
            ("Phaser 100", ("intensity", "speed")),
            ("S.C.F", ("speed", "width", "mode", "inten.")),
            ("U-Vibe", ("speed", "volume", "inten.", "mode")),
            ("Rotary", ("balance", "speed")),
            ("Harmonist", ("key", "mode", "harmo", "blend")),
            ("SCH-1", ("rate", "depth", "tone")),
            ("Pan", ("rate", "depth", "waveform", "mix")),
        )
    },
    "PL": {"models": {"P.L": {"min": {"min": 0, "max": 50}, "max": {"min": 51, "max": 100}}}},
    "settings": {
        "input_trim": ["inst.1", "inst.2", "inst.3", "inst.4", "inst.5", "inst.6"],
        "output_mode": [
            "Studio Direct(Line/Phones)",
            "Combo Front",
            "Combo Rear",
            "Stack Front",
            "Stack Rear",
        ],
        "global_eq": [
            "enabled",
            "hpf",
            "100",
            "200",
            "500",
            "1.2k",
            "2.6k",
            "6.4k",
            "10k",
            "level",
            "lpf",
            "lpf_enabled",
        ],
        "display": ["home_display", "boot_up_picture"],
        "brightness": ["display", "footswitch"],
        "parameter_follow": ["enabled", "amp_connects_default_ir"],
        "output_console": [
            "phones",
            "phones_mute",
            "output",
            "output_mute",
            "xlr",
            "xlr_mute",
            "usb_in_1/2",
            "usb_in_1/2_mute",
            "usb_in_3/4",
            "usb_in_3/4_mute",
            "input_monitor",
            "usb_mode",
            "dry_in",
            "loopback",
        ],
        "midi": ["channel", "midi_in", "midi_out", "program_change"],
        "other": ["s3_scene", "tap", "phones", "patch_rolling", "patch_tail", "language"],
    },
}

# Parameters that are switches or selectors override the percent-based shorthand
# used for the predominantly numeric model catalogue above.
CATALOG["EFX"]["models"]["Katana"]["boost"] = BOOLEAN
CATALOG["EFX"]["models"]["Touch Wah"].update(
    {"type": ["cry", "vx", "full", "talk"], "direction": ["up", "down"]}
)
for amp_name in ("Jazz Clean", "Twin Rvb"):
    CATALOG["AMP"]["models"][amp_name].update({"inputs": [1, 2], "bright": BOOLEAN})
for amp_name in (
    "Deluxe Rvb",
    "Vib King",
    "Mr.Z38",
    "Princetone",
    "Match D30",
    "Class A15",
    "Class A30",
):
    CATALOG["AMP"]["models"][amp_name]["inputs"] = [1, 2]
for amp_name in ("Bassmate", "Hiwire", "Plexi 100W", "Plexi 45", "1987 X 50W", "Brit Blues"):
    CATALOG["AMP"]["models"][amp_name]["inputs"] = ["bri. 1", "bri. 2", "nor. 1", "nor. 2"]
CATALOG["AMP"]["models"]["Tweedy"]["inputs"] = ["inst. 1", "inst. 2", "mic. 1", "mic. 2"]
CATALOG["AMP"]["models"]["Cali Crunch"]["inputs"] = [1, 2]
CATALOG["AMP"]["models"]["Brit 800"]["inputs"] = [1, 2]
CATALOG["AMP"]["models"]["Lionstar"]["voice"] = BOOLEAN
CATALOG["MOD"]["models"]["S.C.F"]["mode"] = ["cho", "ch/fl"]
CATALOG["MOD"]["models"]["U-Vibe"]["mode"] = ["ch", "vib"]
CATALOG["MOD"]["models"]["Harmonist"]["mode"] = ["minor", "major"]


def capabilities(module: str | None = None) -> dict[str, Any]:
    if module is None:
        return {
            "device": DEVICE_SURFACE,
            "modules": list(CATALOG),
            "chain_modules": [
                "NG",
                "CMP",
                "EFX",
                "AMP",
                "AMP2",
                "IR",
                "EQ",
                "DLY",
                "RVB",
                "S/R",
                "WAH",
                "MOD",
                "PL",
            ],
            "sections": list(CATALOG),
            "catalog": CATALOG,
        }
    canonical = canonical_module(module)
    wanted = {"AMP2": "AMP"}.get(canonical, canonical)
    for name, data in CATALOG.items():
        if name.upper() == wanted:
            result = {"module": name, "capabilities": data}
            if name == "AMP":
                result["related"] = {
                    "image_models": CATALOG["AMP_IMAGE"],
                    "power_amp": CATALOG["POWER_AMP"],
                }
            return result
    return {
        "module": module,
        "capabilities": None,
        "note": "Unknown to bundled catalogue; use nux_snapshot and nux_set_control.",
    }
