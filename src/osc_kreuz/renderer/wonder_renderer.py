import logging


from osc_kreuz.config import add_renderer_to_state_file
import osc_kreuz.str_keys_conventions as skc

from .base_renderer import RendererException
from .spatial_renderer import SpatialRenderer
from .updates import AttributeUpdate, PositionUpdate, OSCMessage

log = logging.getLogger("renderer")
verbosity = 0


class wonderPlanewaveAttributeUpdate(AttributeUpdate):
    def get_value(self):
        # for the planewave attribute, the value has to be inverted
        return int(not super().get_value())


class Wonder(SpatialRenderer):
    oscpath_position = "/WONDER/source/position"
    attributeOsc = {
        skc.SourceAttributes.doppler: "/WONDER/source/dopplerEffect",
        skc.SourceAttributes.planewave: "/WONDER/source/type",
        skc.SourceAttributes.angle: "/WONDER/source/angle",
    }

    def __init__(self, **kwargs):
        if "dataformat" not in kwargs:
            kwargs["dataformat"] = "xy"
        if "sourceattributes" not in kwargs:
            kwargs["sourceattributes"] = (
                skc.SourceAttributes.doppler,
                skc.SourceAttributes.planewave,
            )
        if "updateintervall" not in kwargs:
            kwargs["updateintervall"] = 50
        self.interpolTime = int(kwargs["updateintervall"]) / 1000
        self.linkPositionAndAngle = True

        super(Wonder, self).__init__(**kwargs)

    def sourcePositionChanged(self, source_idx):
        # Add position Update to update stack
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.oscpath_position,
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_idx,
                post_arg=self.interpolTime,
            ),
        )

        # optionally update angle if the wave is planar
        if self.linkPositionAndAngle and self.sources[source_idx].getAttribute(
            skc.SourceAttributes.planewave
        ):
            self.sourceAttributeChanged(source_idx, skc.SourceAttributes.angle)

    def sourceAttributeChanged(self, source_idx, attribute: skc.SourceAttributes):
        if attribute == skc.SourceAttributes.planewave:
            # planewave has special update type
            self.add_update(
                source_idx,
                wonderPlanewaveAttributeUpdate(
                    path=self.attributeOsc[attribute],
                    soundobject=self.sources[source_idx],
                    source_index=source_idx,
                    attribute=attribute,
                ),
            )

            if self.sources[source_idx].getAttribute(attribute):
                self.update_auto_angle(source_idx)
        elif attribute == skc.SourceAttributes.angle:
            # angle needs interpolation time as additional param
            self.add_update(
                source_idx,
                AttributeUpdate(
                    path=self.attributeOsc[attribute],
                    soundobject=self.sources[source_idx],
                    source_index=source_idx,
                    attribute=attribute,
                    post_arg=self.interpolTime,
                ),
            )
        else:
            self.add_update(
                source_idx,
                AttributeUpdate(
                    path=self.attributeOsc[attribute],
                    soundobject=self.sources[source_idx],
                    source_index=source_idx,
                    attribute=attribute,
                ),
            )

    def update_auto_angle(self, source_idx: int):
        # TODO take into account the user specified angle
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.attributeOsc[skc.SourceAttributes.angle],
                soundobject=self.sources[source_idx],
                source_index=source_idx,
                coord_fmt="azim",
                post_arg=self.interpolTime,
            ),
        )


class TWonder(Wonder):
    oscpath_n_sources = "/WONDER/global/maxNoSources"
    oscpath_room_polygon = "/WONDER/global/renderpolygon"
    oscpath_activate_source = "/WONDER/source/activate"

    def __init__(self, **kwargs):
        # automatically extract this info from the supplied addresses
        self.is_multicast = bool(kwargs.pop("multicast", False))
        super().__init__(**kwargs)

        # send 3D positions if xyz format
        if self.posFormat == "xyz":
            self.oscpath_position += "3D"

    def add_twonder(self, hostname: str, port: int) -> None:
        """Initialize a new receiving twonder.
        if multicast is being used just send the initialization over, but don't save it
        if multicast is not being used also add the twonder using add_receiver()

        Args:
            hostname (str): hostname of the twonder
            port (int): port of the twonder

        Raises:
            RendererException: raised when the configuration does not allow for proper cwonder replacement
        """
        # check that osc-kreuz is ready to function as cwonder replacement
        if "room_polygon" not in self.globalConfig:
            raise RendererException(
                "Can't connect twonder because no room_polygon was specified in config"
            )
        if not self.is_multicast:
            self.add_receiver(hostname, port)

        self.send_room_information(hostname, port)

        # find a way to do this without multicasting to every connected twonder
        # self.dump_source_positions()

    def add_receiver(self, hostname: str, port: int):

        # check that osc-kreuz is ready to function as cwonder replacement
        if "room_polygon" not in self.globalConfig:
            log.warning(
                "Room polygon was not specified in config, the connected twonder might behave in unexpected ways"
            )

        # make sure every twonder is only added once
        if (hostname, port) not in (
            (hostname, receiver._port) for hostname, receiver in self.receivers
        ):
            super().add_receiver(hostname, port)
            if not self.is_multicast:
                add_renderer_to_state_file("twonder", hostname, port)

    def send_room_information(self, hostname: str, port: int):
        """send status information for renderer to twonder

        Args:
            hostname (str): hostname of the receiving twonder
            port (int): port of the receiving twonder
        """
        msgs = []

        # send number of sources
        msgs.append(OSCMessage(self.oscpath_n_sources, self.numberOfSources))

        # send activation information
        for i in range(self.numberOfSources):
            msgs.append(OSCMessage(self.oscpath_activate_source, i))
        self.send_updates(msgs, hostname, port)

        # send room polygon
        self.dump_room_polygon(self.oscpath_room_polygon, hostname, port)
