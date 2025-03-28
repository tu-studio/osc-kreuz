

import logging
from threading import Timer
from osc_kreuz.renderer.spatial_renderer import SpatialRenderer
from osc_kreuz.renderer.updates import AttributeUpdate, DirectSendUpdate, GainUpdate, PositionUpdate
import osc_kreuz.str_keys_conventions as skc

log = logging.getLogger("renderer")
verbosity = 0

class ViewClient(SpatialRenderer):
    def my_type(self) -> str:
        return f"{super().my_type()}_{self.alias}"

    def __init__(self, aliasname: str, **kwargs):
        self.alias = aliasname

        super(ViewClient, self).__init__(**kwargs)

        self.pingCounter = 0

        self.indexAsValue = False
        if "indexAsValue" in kwargs.keys():
            self.indexAsValue = kwargs["indexAsValue"]

        # TODO initialize variables only once, and with a consistent type pl0x
        self.oscpath_position_with_index = [""] * self.numberOfSources
        self.oscpath_gain_with_index = [
            ["" for j in range(self.globalConfig["n_renderengines"])]
            for i in range(self.numberOfSources)
        ]

        self.createOscPrefixes()

        self.pingTimer: Timer | None = None

        # send current state to viewclient
        self.dump_source_positions()
        self.dump_source_gains()

    def createOscPrefixes(self):
        for i in range(self.numberOfSources):
            self.oscpath_position_with_index[i] = f"/source/{i+1}/{self.posFormat}"

            try:
                render_units = self.globalConfig["render_units"]
            except KeyError:
                render_units = []

            renderList = [""] * self.globalConfig["n_renderengines"]
            if (
                "ambi" in render_units
                and "wfs" in render_units
                and "reverb" in render_units
            ):
                renderList[render_units.index("ambi")] = f"/source/{i+1}/ambi"
                renderList[render_units.index("wfs")] = f"/source/{i+1}/wfs"
                renderList[render_units.index("reverb")] = f"/source/{i+1}/reverb"
            else:
                for j in range(self.globalConfig["n_renderengines"]):
                    self.oscpath_gain_with_index[i][j] = f"/source/{i+1}/send/{j}"
            self.oscpath_gain_with_index[i] = renderList

    def checkAlive(self, deleteClient):
        self.pingTimer = Timer(2.0, self.checkAlive, args=(deleteClient,))
        self.pingTimer.name = f"pingtimer {self.alias}"

        if self.pingCounter < 6:
            try:
                # get first receiver tuple, get actual receiver
                self.receivers[0][1].send_message(
                    # TODO change ping path to constant defined somewhere else
                    "/oscrouter/ping",
                    [self.globalConfig[skc.inputport_settings]],
                )
            except Exception as e:
                log.warning(e)
                log.warning(f"error while pinging client { self.alias }, removing")
                self.pingTimer.cancel()
                deleteClient(self, self.alias)

            self.pingCounter += 1
            self.pingTimer.start()
        else:
            deleteClient(self, self.alias)

    def receivedIsAlive(self):
        self.pingCounter = 0

    def sourcePositionChanged(self, source_idx):
        if self.indexAsValue:
            path = self.oscpath_position_with_index[source_idx]
            source_index_for_update = None
        else:
            path = self.oscpath_position
            source_index_for_update = source_idx
        self.add_update(
            source_idx,
            PositionUpdate(
                path=path,
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_index_for_update,
            ),
        )

    def sourceRenderGainChanged(self, source_idx, render_idx):
        # TODO option to send named paths instead
        if self.indexAsValue:
            path = self.oscpath_gain_with_index[source_idx][render_idx]
            source_index_for_update = None
        else:
            path = "/source/send"
            source_index_for_update = source_idx
        self.add_update(
            source_idx,
            GainUpdate(
                path,
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_index_for_update,
                include_render_idx=True,
            ),
        )

    def sourceDirectSendChanged(self, source_idx, send_idx):
        path = "/source/direct"
        self.add_update(
            source_idx,
            DirectSendUpdate(
                path,
                soundobject=self.sources[source_idx],
                send_index=send_idx,
                source_index=source_idx,
                include_send_idx=True,
            ),
        )

    def sourceAttributeChanged(self, source_idx, attribute):
        path = "/source/attribute"
        self.add_update(
            source_idx,
            AttributeUpdate(
                path,
                attribute,
                soundobject=self.sources[source_idx],
                source_index=source_idx,
                include_attribute_name=True,
            ),
        )