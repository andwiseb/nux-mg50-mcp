"""Stable MG-50Li concepts and aliases.

Model lists are discovered from the installed NUX Audio UI at runtime. Keeping this file
small avoids baking one editor/firmware version into the public API.
"""

MODULE_ALIASES: dict[str, tuple[str, ...]] = {
    "NG": ("NG", "GATE", "NOISE GATE"),
    "CMP": ("CMP", "COMP", "COMPRESSOR"),
    "EFX": ("EFX", "DRIVE", "DISTORTION", "BOOST"),
    "AMP": ("AMP", "AMP1"),
    "AMP2": ("AMP2",),
    "EQ": ("EQ",),
    "S/R": ("S/R", "SR", "SEND RETURN"),
    "IR": ("IR", "CAB", "CABINET"),
    "DLY": ("DLY", "DELAY"),
    "RVB": ("RVB", "REVERB"),
    "WAH": ("WAH",),
    "MOD": ("MOD", "MODULATION"),
    "PL": ("PL", "PEDAL", "VOLUME"),
}


def canonical_module(name: str) -> str:
    wanted = name.strip().upper()
    for canonical, aliases in MODULE_ALIASES.items():
        if wanted in aliases:
            return canonical
    return wanted
