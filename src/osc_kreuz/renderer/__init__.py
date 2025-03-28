from email.mime import base
from . import wonder_renderer, viewclient_renderer, supercolliderengine_renderer, audiomatrix_renderer, audiorouter_renderer, spatial_renderer, base_renderer, seamlessplugin_renderer

renderer_name_dict = {
    "wonder": wonder_renderer.Wonder,
    "twonder": wonder_renderer.TWonder,
    # "panoramix": Panoramix,
    "viewclient": viewclient_renderer.ViewClient,
    # "oscar": Oscar,
    "scengine": supercolliderengine_renderer.SuperColliderEngine,
    "audiorouter": audiorouter_renderer.Audiorouter,
    "seamlessplugin": seamlessplugin_renderer.SeamlessPlugin,
    "audiorouterwfs": audiorouter_renderer.AudiorouterWFS,
    "audiomatrix": audiomatrix_renderer.AudioMatrix,
    "spatial": spatial_renderer.SpatialRenderer
}

def createRendererClient(config: dict) -> base_renderer.BaseRenderer:

    # (probably) a workaround for OSCAR, removed for now
    # if "dataformat" in config:
    #     tmp_dataFormat = config["dataformat"]
    #     if not tmp_dataFormat in skc.posformat.keys():
    #         if len(tmp_dataFormat.split("_")) == 2:
    #             preStr = ""
    #             if tmp_dataFormat.split("_")[0] == "normcartesian":
    #                 preStr = "n"

    #             dFo = preStr + tmp_dataFormat.split("_")[1]
    #             config["dataformat"] = dFo
    #         else:
    #             log.warn("unknown position format")
    #             del config["dataformat"]

    if "type" not in config:
        raise base_renderer.RendererException("Type of receiver unspecified")

    renderer_type = config["type"].lower()
    del config["type"]

    if renderer_type not in renderer_name_dict:
        raise base_renderer.RendererException(f"Invalid receiver type: {renderer_type}")

    return renderer_name_dict[renderer_type](**config)
