from osc_kreuz.renderer import (
    Update,
    GainUpdate,
    PositionUpdate,
    AttributeUpdate,
    DirectSendUpdate,
    wonderPlanewaveAttributeUpdate,
)

import osc_kreuz.renderer as r
from osc_kreuz.soundobject import SoundObject
import osc_kreuz.str_keys_conventions as skc


def test_update_classes():
    updates = set()
    u1 = Update(b"/", None)
    u2 = Update(b"/", None)

    for u in [u1, u2]:
        updates.add(u)

    assert len(updates) == 1

    for u in [
        GainUpdate(b"/", None, render_idx=1, source_index=1),
        GainUpdate(b"/", None, render_idx=1, source_index=2),
        GainUpdate(b"/", None, render_idx=2, source_index=2),
        GainUpdate(b"/", None, render_idx=2, source_index=2),
    ]:
        updates.add(u)
    assert len(updates) == 4

    for u in [
        PositionUpdate(b"/", None, coord_fmt=None, source_index=5),
        PositionUpdate(b"/", None, coord_fmt=None, source_index=5),
        PositionUpdate(b"/", None, coord_fmt=None, source_index=6),
        PositionUpdate(b"/", None, coord_fmt=None, source_index=6),
    ]:
        updates.add(u)
    assert len(updates) == 6

    for u in [
        AttributeUpdate("/", None, None),
        AttributeUpdate("/", None, None),
    ]:
        updates.add(u)

    assert len(updates) == 7

    for u in [
        DirectSendUpdate("/", None, None, source_index=1),
        DirectSendUpdate("/", None, None),
    ]:
        updates.add(u)

    assert len(updates) == 9

    for u in [
        wonderPlanewaveAttributeUpdate("/", None, None, source_index=1),
        wonderPlanewaveAttributeUpdate("/", None, None),
    ]:
        updates.add(u)

    assert len(updates) == 11


def prepare_renderer(conf: dict, disable_network: bool = True):

    global_conf = {
        "number_direct_sends": 2,
        "data_port_timeout": 0,
        "render_units": ["ambi", "wfs", "reverb"],
    }

    def function_override(*args, **kwargs):
        pass

    SoundObject.readGlobalConfig(global_conf)

    r.Renderer.numberOfSources = 1
    r.Renderer.sources = [SoundObject(), SoundObject()]
    r.Renderer.globalConfig = global_conf
    if disable_network:
        r.Renderer.scheduleSourceUpdateCheck = function_override
        r.Renderer.updateSource = function_override
    client = r.createRendererClient(conf)
    return client


def check_source_update(
    renderer: r.Renderer,
    update_type: str,
    source_idx,
    expected_path: list[bytes] | bytes,
    expected_output: list | list[list],
    param=None,
):
    if isinstance(expected_path, bytes):
        expected_path = [expected_path]
        expected_output = [expected_output]

    s = renderer.updateStack[source_idx]

    n_expected = len(expected_path)
    assert len(s) == 0

    match update_type:
        case "pos":
            renderer.sourcePositionChanged(source_idx)
        case "attr":
            renderer.sourceAttributeChanged(source_idx, param)
        case "gain":
            renderer.sourceRenderGainChanged(source_idx, param)
        case "send":
            renderer.sourceDirectSendChanged(source_idx, param)

    assert len(s) == n_expected

    for i in range(n_expected):
        u = s.pop()
        m = u.to_message()

        assert m.path in expected_path
        assert m.values in expected_output
        expected_path.remove(m.path)
        expected_output.remove(m.values)

    assert len(s) == 0


def test_wonder_renderer():
    conf = {"type": "Wonder", "hosts": [], "updateintervall": 5}
    c = prepare_renderer(conf)
    s = c.updateStack[0]
    so = c.sources[0]
    assert len(s) == 0
    assert isinstance(c, r.Wonder)

    check_source_update(
        c,
        "pos",
        0,
        b"/WONDER/source/position",
        [0, *so.getPosition(skc.CoordFormats.xy), c.interpolTime],
    )

    for attr, path, expected in [
        (skc.SourceAttributes.doppler, b"/WONDER/source/dopplerEffect", [0, 0]),
        (skc.SourceAttributes.planewave, b"/WONDER/source/type", [0, 1]),
        (
            skc.SourceAttributes.angle,
            b"/WONDER/source/angle",
            [0, so.getAttribute(skc.SourceAttributes.angle), c.interpolTime],
        ),
    ]:
        check_source_update(c, "attr", 0, path, expected, attr)


def test_audiomatrix_renderer():
    conf = {
        "type": "audiomatrix",
        "hosts": [],
        "paths": [
            {"path": "/source/gain/wfs", "renderer": "wfs", "type": "gain"},
            {"path": "/source/gain/ambi", "type": "gain", "renderer": "ambi"},
            {"path": "/source/pos", "type": "position", "format": "aed"},
            {"path": "/source/xyz", "type": "position", "format": "xyz"},
        ],
    }
    c = prepare_renderer(conf)
    s = c.updateStack[0]
    so = c.sources[0]
    assert len(s) == 0
    assert isinstance(c, r.AudioMatrix)

    check_source_update(
        c,
        "pos",
        0,
        [b"/source/pos", b"/source/xyz"],
        [
            [0, *so.getPosition(skc.CoordFormats.aed)],
            [0, *so.getPosition(skc.CoordFormats.xyz)],
        ],
    )

    for r_idx, path, expected in [
        (0, b"/source/gain/ambi", [0, 0]),
        (1, b"/source/gain/wfs", [0, 0]),
        (2, [], []),
    ]:
        check_source_update(c, "gain", 0, path, expected, r_idx)


def test_audiorouter_renderer():
    conf = {"type": "audiorouter", "hosts": [], "updateintervall": 5}
    c = prepare_renderer(conf)
    s = c.updateStack[0]
    so = c.sources[0]
    assert len(s) == 0
    assert isinstance(c, r.Audiorouter)

    check_source_update(
        c,
        "pos",
        0,
        [],
        [],
    )

    for r_idx, path, expected in [
        (0, b"/source/send/spatial", [0, 0, 0]),
        (1, [], []),
        (2, b"/source/reverb/gain", [0, 0]),
    ]:
        check_source_update(c, "gain", 0, path, expected, r_idx)


def test_audiorouterWFS_renderer():
    conf = {"type": "audiorouterWFS", "hosts": [], "updateintervall": 5}
    c = prepare_renderer(conf)
    s = c.updateStack[0]
    so = c.sources[0]
    assert len(s) == 0
    assert isinstance(c, r.AudiorouterWFS)

    check_source_update(
        c,
        "pos",
        0,
        [],
        [],
    )

    for r_idx, path, expected in [
        (0, [], []),
        (1, [b"/source/send/spatial"], [[0, 1, 0]]),
        (2, [], []),
    ]:
        check_source_update(c, "gain", 0, path, expected, r_idx)
