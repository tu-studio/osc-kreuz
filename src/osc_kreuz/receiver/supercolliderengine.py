from .spatial_receiver import SpatialReceiver


class SuperColliderEngine(SpatialReceiver):
    oscpath_position = "/source/pos/aed"

    def __init__(self, **kwargs):
        if "dataformat" not in kwargs.keys():
            kwargs["dataformat"] = "aed"
        super(SuperColliderEngine, self).__init__(**kwargs)
