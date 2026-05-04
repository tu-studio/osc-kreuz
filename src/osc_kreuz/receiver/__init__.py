from . import (
    wonder,
    viewclient,
    supercolliderengine,
    audiomatrix,
    audiorouter,
    spatial_receiver,
    base_receiver,
    seamlessplugin,
)

receiver_name_dict = {
    "wonder": wonder.Wonder,
    "twonder": wonder.TWonder,
    # "panoramix": Panoramix,
    "viewclient": viewclient.ViewClient,
    # "oscar": Oscar,
    "scengine": supercolliderengine.SuperColliderEngine,
    "audiorouter": audiorouter.Audiorouter,
    "seamlessplugin": seamlessplugin.SeamlessPlugin,
    "audiorouterwfs": audiorouter.AudiorouterWFS,
    "audiomatrix": audiomatrix.AudioMatrix,
    "spatial": spatial_receiver.SpatialReceiver,
}


def createReceiverClient(config: dict) -> base_receiver.BaseReceiver:

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
        raise base_receiver.ReceiverException("Type of receiver unspecified")

    receiver_type = config["type"].lower()
    del config["type"]

    if receiver_type not in receiver_name_dict:
        raise base_receiver.ReceiverException(f"Invalid receiver type: {receiver_type}")

    return receiver_name_dict[receiver_type](**config)
