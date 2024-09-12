import numpy as np

from osc_kreuz.soundobject import SoundObject


def test_scaling():
    global_conf = {
        "number_direct_sends": 2,
        "data_port_timeout": 0,
        "render_units": ["ambi", "wfs", "reverb"],
        "send_changes_only": False,
    }

    SoundObject.readGlobalConfig(global_conf)
    for scaling, input_format, input_pos, output_xyz, output_aed in [
        (0.5, "aed", (90, 0, 1), (0, 0.5, 0), (90, 0, 0.5)),
        (0.7, "aed", (45, 45, 3), (1.05, 1.05, 1.48492424), (45, 45, 2.1)),
        (0.7, "aed", (-45, -45, 3), (1.05, -1.05, -1.48492424), (-45, -45, 2.1)),
        (2, "xyz", (1, 0, 0), (2, 0, 0), (0, 0, 2)),
        (2.565, "xyz", (5, 0, 0), (12.825, 0, 0), (0, 0, 12.825)),
        (25.65, "xyz", (0.5, 0, 0), (12.825, 0, 0), (0, 0, 12.825)),
    ]:
        so = SoundObject(coordinate_scaling_factor=scaling)
        so.setPosition(input_format, *input_pos)
        print(so.getPosition("xyz"))
        print(output_xyz)
        assert np.allclose(so.getPosition("xyz"), output_xyz)
        assert np.allclose(so.getPosition("aed"), output_aed)


def test_distance():
    global_conf = {
        "number_direct_sends": 2,
        "data_port_timeout": 0,
        "render_units": ["ambi", "wfs", "reverb"],
        "send_changes_only": False,
    }

    SoundObject.readGlobalConfig(global_conf)

    so = SoundObject()
    so.setPosition("xyz", *(2, 0, 0))
    assert np.allclose([2.0], [so.getPosition("dist")])
    so.setPosition("xyz", *(3, 0, 0))

    assert np.allclose([3.0], [so.getPosition("d")])

    so.setPosition("aed", *(0, 0, 2.5))
    assert np.allclose([2.5], [so.getPosition("distance")])

    so.setPosition("xyz", *(2, 0, 0))
    assert np.allclose([2.0], [so.getPosition("distance")])


if __name__ == "__main__":
    test_scaling()
