from enum import Enum


class OscPathType(Enum):
    Position = 1
    Properties = 2
    Gain = 3


# This dict contains all the required osc path blueprints. The outermost key is the type of data sent to this path (position, gain, properties).
# each type has two different kinds of paths, base (source index is sent as parameter) and extended (source index is part of the path)
osc_paths = {
    OscPathType.Position: {
        "base": [
            "/source/{val}",
            "/source/pos/{val}",
            "/source/position/{val}",
        ],
        "extended": [
            "/source/{idx}/{val}",
            "/source/{idx}/pos/{val}",
            "/source/{idx}/position/{val}",
        ],
    },
    OscPathType.Properties: {
        "base": ["/source/{val}"],
        "extended": ["/source/{idx}/{val}"],
    },
    OscPathType.Gain: {
        "base": [
            "/source/send/{val}",
            "/source/send/{val}/gain",
            "/send/{val}",
            "/send/{val}/gain",
            "/source/{val}",
            "/source/{val}/gain",
        ],
        "extended": [
            "/source/{idx}/send/{val}",
            "/source/{idx}/send/{val}/gain",
            "/send/{idx}/{val}",
            "/send/{idx}/{val}/gain",
            "/source/{idx}/{val}",
            "/source/{idx}/{val}/gain",
        ],
    },
}

osc_aliases = {
    "ambi": ["hoa", "ambi", "ambisonics"],
    "wfs": ["wfs", "wavefieldsynthesis"],
    "reverb": ["reverb", "rev"],
}

# TODO merge with SourceAttributes
doppler = "doppler"
planewave = "planewave"
angle = "angle"

knownAttributes = {planewave, doppler, angle}


class SourceAttributes(Enum):
    planewave = "planewave"
    doppler = "doppler"
    angle = "angle"


# global config keywords
globalconfig = "global"
inputport_data = "port_data"
inputport_ui = "port_ui"
inputport_settings = "port_settings"
number_sources = "number_sources"
max_gain = "max_gain"
send_changes_only = "send_changes_only"
data_port_timeout = "data_port_timeout"

renderengine = "renderengine"
