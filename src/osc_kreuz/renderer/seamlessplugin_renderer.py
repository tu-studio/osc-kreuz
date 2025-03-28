from collections.abc import Iterable
import logging

from osc_kreuz.renderer.spatial_renderer import SpatialRenderer
from osc_kreuz.renderer.updates import GainUpdate, PositionUpdate
import osc_kreuz.str_keys_conventions as skc

log = logging.getLogger("renderer")
verbosity = 0













# class Oscar(SpatialRenderer):
#     def __init__(self, **kwargs):
#         if not "dataformat" in kwargs.keys():
#             kwargs["dataformat"] = "aed"
#         super(Oscar, self).__init__(**kwargs)

#         self.sourceAttributes = (
#             skc.SourceAttributes.doppler,
#             skc.SourceAttributes.planewave,
#         )

#         # self.posAddrs = []

#         self.oscPosPre = []
#         self.oscAttrPre = []
#         self.oscRenderPre = []
#         self.oscDirectPre = []

#         for i in range(self.numberOfSources):
#             sourceAddrs = {}
#             for kk in skc.fullformat[self.posFormat]:
#                 addrStr = "/source/" + str(i + 1) + "/" + kk
#                 sourceAddrs[kk] = addrStr.encode()
#             self.oscPosPre.append(sourceAddrs)

#             attrDic = {}
#             for key in self.sourceAttributes:
#                 oscStr = "/source" + str(i + 1) + "/" + key.value
#                 attrDic[key] = oscStr.encode()
#             self.oscAttrPre.append(attrDic)

#             renderGainOscs = []
#             for rId in range(self.globalConfig["n_renderengines"]):
#                 riOsc = "/source/" + str(i + 1) + "/render/" + str(rId)
#                 renderGainOscs.append(riOsc.encode())
#             self.oscRenderPre.append(renderGainOscs)

#             channelSend = []
#             for cId in range(self.globalConfig["number_direct_sends"]):
#                 csOsc = "/source/" + str(i + 1) + "/direct/" + str(cId)
#                 channelSend.append(csOsc.encode())
#             self.oscDirectPre.append(channelSend)

#             # self.posAddrs.append(sourceAddrs)

#         self.validPosKeys = {skc.dist}

#     def sourcePositionChanged(self, source_idx):
#         for key in skc.fullformat[self.posFormat.value]:
#             self.add_update(
#                 source_idx,
#                 PositionUpdate(
#                     self.oscPosPre[source_idx][key],
#                     soundobject=self.sources[source_idx],
#                     coord_fmt=skc.CoordFormats(key),
#                 ),
#             )

#     def sourceAttributeChanged(self, source_idx, attribute):
#         self.add_update(
#             source_idx,
#             AttributeUpdate(
#                 path=self.oscAttrPre[source_idx][attribute],
#                 soundobject=self.sources[source_idx],
#                 attribute=attribute,
#             ),
#         )

#     def sourceDirectSendChanged(self, source_idx, send_idx):
#         self.add_update(
#             source_idx,
#             DirectSendUpdate(
#                 path=self.oscDirectPre[source_idx][send_idx],
#                 soundobject=self.sources[source_idx],
#                 send_index=send_idx,
#             ),
#         )

#     def sourceRenderGainChanged(self, source_idx, render_idx):
#         self.add_update(
#             source_idx,
#             GainUpdate(
#                 path=self.oscRenderPre[source_idx][render_idx],
#                 soundobject=self.sources[source_idx],
#                 render_idx=render_idx,
#             ),
#         )


class SeamlessPlugin(SpatialRenderer):

    def __init__(self, **kwargs):
        if "dataformat" not in kwargs.keys():
            kwargs["dataformat"] = "xyz"
        super(SeamlessPlugin, self).__init__(**kwargs)

        self.sourceAttributes = (
            skc.SourceAttributes.doppler,
            skc.SourceAttributes.planewave,
        )

        self.oscAddrs: dict = {}

        self.oscAddrs[self.posFormat] = f"/source/pos/{self.posFormat}"

        for vv in self.sourceAttributes:
            self.oscAddrs[vv.value] = "/{}".format(vv.value)

        self.oscAddrs["renderGain"] = "/send/gain"

    def composeSourceUpdateMessage(
        self, values, sIdx: int = 0, *args
    ) -> list[tuple[bytes, Iterable]]:
        osc_pre = args[0]
        if osc_pre == self.oscAddrs["renderGain"]:
            return [(osc_pre, [sIdx + 1, args[1], values])]
        else:
            return [(osc_pre, [sIdx + 1, values])]

    def sourceAttributeChanged(self, source_idx, attribute):
        pass

    def sourceRenderGainChanged(self, source_idx, render_idx):
        self.add_update(
            source_idx,
            GainUpdate(
                self.oscAddrs["renderGain"],
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_idx + 1,
                include_render_idx=True,
            ),
        )

    def sourcePositionChanged(self, source_idx):
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.oscAddrs[self.posFormat],
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_idx + 1,
            ),
        )