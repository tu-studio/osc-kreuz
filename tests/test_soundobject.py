from osc_kreuz.soundobject import SoundObject
import osc_kreuz.str_keys_conventions as skc
import numpy as np


def test_scaling():
    global_conf = {
        "number_direct_sends": 2,
        "data_port_timeout": 0,
        "render_units": ["ambi", "wfs", "reverb"],
        "send_changes_only": False,
        "min_dist": 0,
    }

    SoundObject.readGlobalConfig(global_conf)
    for scaling, input_format, input_pos, output_xyz, output_aed in [
        (0.5, skc.aed, (90, 0, 1), (0, 0.5, 0), (90, 0, 0.5)),
        (2, skc.xyz, (1, 0, 0), (2, 0, 0), (0, 0, 2)),
    ]:
        so = SoundObject(coordinate_scaling_factor=scaling)
        so.setPosition(input_format, *input_pos)
        assert np.allclose(so.getPosition(skc.CoordFormats.xyz), output_xyz)
        assert np.allclose(so.getPosition(skc.CoordFormats.aed), output_aed)
