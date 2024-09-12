from collections.abc import Callable
from functools import partial
import ipaddress
import logging

from oscpy.server import OSCThreadServer

from osc_kreuz.coordinates import get_all_coordinate_formats
from osc_kreuz.renderer import Renderer, ViewClient
from osc_kreuz.soundobject import SoundObject
import osc_kreuz.str_keys_conventions as skc

log = logging.getLogger("OSCcomcenter")


class OSCComCenter:
    def __init__(
        self,
        soundobjects: list[SoundObject],
        receivers: list[Renderer],
        renderengines: list[str],
        n_sources: int,
        n_direct_sends: int,
        ip: str,
        port_ui: int,
        port_data: int,
        port_settings: int,
    ) -> None:
        self.soundobjects = soundobjects

        self.clientSubscriptions: dict[str, ViewClient] = {}
        self.receivers = receivers
        self.extendedOscInput = True
        self.verbosity = 0
        self.bPrintOSC = False

        self.renderengines = renderengines
        self.n_renderengines = len(renderengines)
        self.n_sources = n_sources
        self.n_direct_sends = n_direct_sends

        self.osc_ui_server = OSCThreadServer()
        self.osc_data_server = OSCThreadServer()
        self.osc_setting_server = OSCThreadServer()

        self.ip = ip
        self.port_ui = port_ui
        self.port_data = port_data
        self.port_settings = port_settings

    def setVerbosity(self, v: int):
        self.verbosity = v
        self.bPrintOSC = v >= 2
        Renderer.setVerbosity(v)
        log.debug("verbosity set to", v)

    def setupOscSettingsBindings(self):
        self.osc_setting_server.listen(
            address=self.ip, port=self.port_settings, default=True
        )

        # also allow oscrouter in settings path for backwards compatibility
        for base_path in ["oscrouter", "osckreuz"]:
            self.osc_setting_server.bind(
                f"/{base_path}/debug/osccopy".encode(), self.oscreceived_debugOscCopy
            )
            self.osc_setting_server.bind(
                f"/{base_path}/debug/verbose".encode(), self.oscreceived_verbose
            )
            self.osc_setting_server.bind(
                f"/{base_path}/subscribe".encode(), self.oscreceived_subscriptionRequest
            )
            self.osc_setting_server.bind(
                f"/{base_path}/unsubscribe".encode(), self.osc_handler_unsubscribe
            )
            self.osc_setting_server.bind(
                f"/{base_path}/ping".encode(), self.oscreceived_ping
            )
            self.osc_setting_server.bind(
                f"/{base_path}/pong".encode(), self.oscreceived_pong
            )
            self.osc_setting_server.bind(
                f"/{base_path}/dump".encode(), self.oscreceived_dump
            )

    def oscreceived_ping(self, *args):

        if self.checkPort(args[0]):
            self.osc_setting_server.answer(
                b"/oscrouter/pong", port=args[0], values=["osc-kreuz".encode()]
            )

    def oscreceived_pong(self, *args):

        try:
            clientName = args[0]
            self.clientSubscriptions[clientName].receivedIsAlive()
        except:
            if self.verbosity > 0:
                _name = ""
                if len(args) > 0:
                    _name = args[0]
                log.info("no renderer for pong message {}".format(_name))

    def oscreceived_subscriptionRequest(self, *args) -> None:
        """OSC Callback for subscription Requests.

        These requests follow the format:
        /oscrouter/subscribe myname 31441 xyz 0 5
        /oscrouter/subscribe [client_name] [client_port] [coordinate_format] [source index as value? (0 or 1)] [update rate]
        args[0] nameFor Client
        args[1] port client listens to
        args[2] format client expects
        args[3] send source index as value instead of inside the osc prefix
        args[4] source position update rate
        """

        viewClientInitValues = {}
        vCName = args[0]
        subArgs = len(args)
        if subArgs >= 2:
            if self.checkPort(args[1]):
                viewClientInitValues["port"] = args[1]

                _ip = self.osc_setting_server.get_sender()[1]

                viewClientInitValues["hostname"] = _ip

                # if subArgs>2:
                #     initKeys = ['dataformat', 'indexAsValue', 'updateintervall']
                #     for i in range(2, subArgs):
                #         viewClientInitValues[initKeys[i-2]] = args[i]
                try:
                    viewClientInitValues["dataformat"] = args[2].decode()
                except:
                    pass
                try:
                    viewClientInitValues["indexAsValue"] = args[3]
                except:
                    pass
                try:
                    viewClientInitValues["updateintervall"] = args[4]
                except:
                    pass
            newViewClient = ViewClient(vCName, **viewClientInitValues)

            self.clientSubscriptions[vCName] = newViewClient
            # TODO check if this is threadsafe (it probably isn't)
            self.receivers.append(newViewClient)
            newViewClient.checkAlive(self.deleteClient)

        else:
            if self.verbosity > 0:
                log.info("not enough arguments für view client")

    def osc_handler_unsubscribe(self, *args) -> None:
        """OSC Callback for unsubscribe Requests.

        These requests follow the format:
        /oscrouter/unsubscribe myname
        /oscrouter/unsubscribe [client_name]
        args[0] nameFor Client
        """
        log.info("unsubscribe request")
        subArgs = len(args)
        if len(args) >= 1:
            client_name = args[0]
            try:
                view_client = self.clientSubscriptions[client_name]
                self.deleteClient(view_client, client_name)

            except KeyError:
                log.warning(f"can't delete client {client_name}, it does not exist")
        else:
            log.warning("not enough arguments für view client")

    def oscreceived_dump(self, *args):
        pass
        # TODO: dump all source data to renderer

    def deleteClient(self, viewC, alias):
        # TODO check if this is threadsafe (it probably isn't)
        # TODO handle client with same name connection/reconnecting. maybe add ip as composite key?
        if self.verbosity > 0:
            log.info(f"deleting client {viewC}, {alias}")
        try:
            self.receivers.remove(viewC)
            del self.clientSubscriptions[alias]
            log.info(f"removed client {alias}")
        except (ValueError, KeyError):
            log.warning(f"tried to delete receiver {alias}, but it does not exist")

    def checkPort(self, port) -> bool:
        if type(port) == int and 1023 < port < 65535:
            return True
        else:
            if self.verbosity > 0:
                log.info(f"port {port} not legit")
            return False

    def checkIp(self, ip) -> bool:
        ipalright = True
        try:
            _ip = "127.0.0.1" if ip == "localhost" else ip
            _ = ipaddress.ip_address(_ip)
        except:
            ipalright = False
            if self.verbosity > 0:
                log.info(f"ip address {ip} not legit")

        return ipalright

    def checkIpAndPort(self, ip, port) -> bool:
        return self.checkIp(ip) and self.checkPort(port)

    def oscreceived_debugOscCopy(self, *args):
        ip = ""
        port = 0
        if len(args) == 2:
            ip = args[0].decode()
            port = args[1]
        elif len(args) == 1:
            ipport = args[0].decode().split(":")
            if len(ipport) == 2:
                ip = ipport[0]
                port = ipport[1]
        else:
            Renderer.debugCopy = False
            log.info("debug client: invalid message format")
            return
        try:
            ip = "127.0.0.1" if ip == "localhost" else ip
            osccopy_ip = ipaddress.ip_address(ip)
            osccopy_port = int(port)
        except:
            log.info("debug client: invalid ip or port")
            return
        log.info(f"debug client connected: {ip}:{port}")

        if 1023 < osccopy_port < 65535:
            Renderer.createDebugClient(str(osccopy_ip), osccopy_port)
            Renderer.debugCopy = True
            return

        Renderer.debugCopy = False

    def oscreceived_verbose(self, *args):
        vvvv = -1
        try:
            vvvv = int(args[0])
        except:
            self.setVerbosity(0)
            # verbosity = 0
            # Renderer.setVerbosity(0)
            log.error("wrong verbosity argument")
            return

        if 0 <= vvvv <= 2:
            self.setVerbosity(vvvv)
            # global verbosity
            # verbosity = vvvv
            # Renderer.setVerbosity(vvvv)
        else:
            self.setVerbosity(0)

    def build_osc_paths(
        self, osc_path_type: skc.OscPathType, value: str, idx: int | None = None
    ) -> list[str]:
        """Builds a list of all needed osc paths for a given osc path Type and the value.
        If idx is supplied, the extended path is used. Aliases for the value are handled

        Args:
            osc_path_type (skc.OscPathType): Osc Path Type
            value (str): value to be written into the OSC strings.
            idx (int | None, optional): Index of the source if the extended format should be used. Defaults to None.

        Raises:
            KeyError: Raised when the Osc Path Type does not exist

        Returns:
            list[str]: list of OSC path strings
        """
        if osc_path_type not in skc.osc_paths:
            raise KeyError(f"Invalid OSC Path Type: {osc_path_type}")
        try:
            aliases = skc.osc_aliases[value]
        except KeyError:
            aliases = [value]

        if idx is None:
            paths = skc.osc_paths[osc_path_type]["base"]
        else:
            paths = skc.osc_paths[osc_path_type]["extended"]

        return [path.format(val=alias, idx=idx) for alias in aliases for path in paths]

    def setupOscBindings(
        self,
    ):
        """Sets up all Osc Bindings"""
        self.setupOscSettingsBindings()

        self.osc_ui_server.listen(address=self.ip, port=self.port_ui, default=True)
        self.osc_data_server.listen(address=self.ip, port=self.port_data, default=True)

        log.info(
            f"listening on port {self.port_ui} for data, {self.port_settings} for settings"
        )

        # Setup OSC Callbacks for positional data
        for coordinate_format in get_all_coordinate_formats():

            for addr in self.build_osc_paths(
                skc.OscPathType.Position, coordinate_format
            ):
                self.bindToDataAndUiPort(
                    addr,
                    partial(self.osc_handler_position, coord_fmt=coordinate_format),
                )

            if self.extendedOscInput:
                for i in range(self.n_sources):
                    idx = i + 1
                    for addr in self.build_osc_paths(
                        skc.OscPathType.Position, coordinate_format, idx=idx
                    ):
                        self.bindToDataAndUiPort(
                            addr,
                            partial(
                                self.osc_handler_position,
                                coord_fmt=coordinate_format,
                                source_index=i,
                            ),
                        )

        # Setup OSC for Wonder Attribute Paths
        # TODO add path without attribute name
        for attribute in skc.SourceAttributes:
            for addr in self.build_osc_paths(
                skc.OscPathType.Properties, attribute.value
            ):
                log.info(f"WFS Attr path: {addr}")
                self.bindToDataAndUiPort(
                    addr,
                    # partial(self.oscReceived_setValueForAttribute, attribute),
                    partial(self.osc_handler_attribute, attribute=attribute),
                )

            for i in range(self.n_sources):
                idx = i + 1
                for addr in self.build_osc_paths(
                    skc.OscPathType.Properties, attribute.value, idx
                ):
                    self.bindToDataAndUiPort(
                        addr,
                        partial(
                            # self.oscreceived_setValueForSourceForAttribute,
                            self.osc_handler_attribute,
                            source_index=i,
                            attribute=attribute,
                        ),
                    )

        # sendgain input
        for spatGAdd in ["/source/send/spatial", "/send/gain", "/source/send"]:
            self.bindToDataAndUiPort(spatGAdd, partial(self.osc_handler_gain))

        # Setup OSC Callbacks for all render units
        for rendIdx, render_unit in enumerate(self.renderengines):
            # get aliases for this render unit, if none exist just use the base name

            # add callback to base paths for all all aliases
            for addr in self.build_osc_paths(skc.OscPathType.Gain, render_unit):
                self.bindToDataAndUiPort(
                    addr,
                    partial(self.osc_handler_gain, render_index=rendIdx),
                )

            # add callback to extended paths
            if self.extendedOscInput:
                for i in range(self.n_sources):
                    idx = i + 1
                    for addr in self.build_osc_paths(
                        skc.OscPathType.Gain, render_unit, idx
                    ):
                        self.bindToDataAndUiPort(
                            addr,
                            # partial(
                            #     self.oscreceived_setRenderGainForSourceForRenderer,
                            #     i,
                            #     rendIdx,
                            # ),
                            partial(
                                self.osc_handler_gain,
                                source_index=i,
                                render_index=rendIdx,
                            ),
                        )

        directSendAddr = "/source/send/direct"
        self.bindToDataAndUiPort(
            directSendAddr, partial(self.osc_handler_direct_send_gain)
        )

        # XXX can this be removed?
        # if extendedOscInput:
        #     for i in range(n_sources):
        #         idx = i + 1
        #         for addr in [
        #             ("/source/" + str(idx) + "/rendergain"),
        #             ("/source/" + str(idx) + "/send/spatial"),
        #             ("/source/" + str(idx) + "/spatial"),
        #             ("/source/" + str(idx) + "/sendspatial"),
        #         ]:

        #             bindToDataAndUiPort(
        #                 addr, partial(oscreceived_setRenderGainForSource, i)
        #             )

        #             # TODO fix whatever this is
        #             # This adds additional osc paths for the render engines by index
        #             # for j in range(len(renderengineClients)):
        #             #     addr2 = addr + "/" + str(j)
        #             #     bindToDataAndUiPort(
        #             #         addr2,
        #             #         partial(oscreceived_setRenderGainForSourceForRenderer, i, j),
        #             #     )

        #         for addr in [
        #             ("/source/" + str(idx) + "/direct"),
        #             ("/source/" + str(idx) + "/directsend"),
        #             ("/source/" + str(idx) + "/senddirect"),
        #             ("/source/" + str(idx) + "/send/direct"),
        #         ]:
        #             bindToDataAndUiPort(
        #                 addr, partial(oscreceived_setDirectSendForSource, idx)
        #             )

        #             for j in range(globalconfig["number_direct_sends"]):
        #                 addr2 = addr + "/" + str(j)
        #                 bindToDataAndUiPort(
        #                     addr2,
        #                     partial(oscreceived_setDirectSendForSourceForChannel, idx, j),
        #                 )

        if self.verbosity > 2:
            for add in self.osc_ui_server.addresses:
                log.info(add)

    def bindToDataAndUiPort(self, addr: str, func: Callable):
        log.debug(f"Adding OSC callback for {addr}")
        addrEnc = addr.encode()

        # if verbosity >= 2:
        self.osc_ui_server.bind(
            addrEnc, partial(self.printOSC, addr=addr, port=self.port_ui)
        )
        self.osc_data_server.bind(
            addrEnc, partial(self.printOSC, addr=addr, port=self.port_data)
        )

        self.osc_ui_server.bind(addrEnc, partial(func, fromUi=True))
        self.osc_data_server.bind(addrEnc, partial(func, fromUi=False))

    def sourceLegit(self, id: int) -> bool:
        indexInRange = 0 <= id < self.n_sources
        if self.verbosity > 0:
            if not indexInRange:
                if not type(id) == int:
                    log.warning("source index is no integer")
                else:
                    log.warning("source index out of range")
        return indexInRange

    def renderIndexLegit(self, id: int) -> bool:
        indexInRange = 0 <= id < self.n_renderengines
        if self.verbosity > 0:
            if not indexInRange:
                if not type(id) == int:
                    log.warning("renderengine index is no integer")
                else:
                    log.warning("renderengine index out of range")
        return indexInRange

    def directSendLegit(self, id: int) -> bool:
        indexInRange = 0 <= id < self.n_direct_sends
        if self.verbosity > 0:
            if not indexInRange:
                if not type(id) == int:
                    log.warning("direct send index is no integer")
                else:
                    log.warning("direct send index out of range")
        return indexInRange

    def osc_handler_position(
        self, *args, coord_fmt: str = "xyz", source_index=-1, fromUi=True
    ):
        args_index = 0

        if source_index == -1:
            try:
                source_index = int(args[args_index]) - 1
                args_index += 1
            except ValueError:
                return False

        if not self.sourceLegit(source_index):
            return False

        if self.soundobjects[source_index].setPosition(
            coord_fmt, *args[args_index:], fromUi=fromUi
        ):
            self.notifyRenderClientsForUpdate(
                "sourcePositionChanged", source_index, fromUi=fromUi
            )

    def osc_handler_gain(
        self, *args, source_index=-1, render_index=-1, fromUi: bool = True
    ) -> bool:

        args_index = 0

        if source_index == -1:
            try:
                source_index = int(args[args_index]) - 1
                args_index += 1
            except ValueError:
                return False

        if render_index == -1:
            try:
                render_index = int(args[args_index])
                args_index += 1
            except ValueError:
                return False

        try:
            gain = float(args[args_index])
        except ValueError:
            return False

        if not (self.sourceLegit(source_index) and self.renderIndexLegit(render_index)):
            return False

        if self.soundobjects[source_index].setRendererGain(render_index, gain, fromUi):
            self.notifyRenderClientsForUpdate(
                "sourceRenderGainChanged", source_index, render_index, fromUi=fromUi
            )
        return True

    def osc_handler_direct_send_gain(
        self, *args, source_index=-1, direct_send_index=-1, fromUi: bool = True
    ):
        args_index = 0
        if source_index == -1:
            try:
                source_index = int(args[args_index]) - 1
                args_index += 1
            except ValueError:
                return False

        if direct_send_index == -1:
            try:
                direct_send_index = int(args[args_index])
                args_index += 1
            except ValueError:
                return False

        try:
            gain = float(args[args_index])
        except ValueError:
            return False

        if not (
            self.sourceLegit(source_index) and self.directSendLegit(direct_send_index)
        ):
            return False

        if self.soundobjects[source_index].setDirectSend(
            direct_send_index, gain, fromUi
        ):
            self.notifyRenderClientsForUpdate(
                "sourceDirectSendChanged",
                source_index,
                direct_send_index,
                fromUi=fromUi,
            )
        return True

    def osc_handler_attribute(
        self,
        *args,
        source_index=-1,
        attribute: skc.SourceAttributes | None = None,
        fromUi: bool = True,
    ):
        args_index = 0
        if source_index == -1:
            try:
                source_index = int(args[args_index]) - 1
                args_index += 1
            except ValueError:
                return False

        if attribute == None:
            try:
                attribute = skc.SourceAttributes(args[args_index])
                args_index += 1
            except ValueError:
                return False

        try:
            value = float(args[args_index])
        except ValueError:
            return False

        if self.soundobjects[source_index].setAttribute(attribute, value, fromUi):
            self.notifyRenderClientsForUpdate(
                "sourceAttributeChanged", source_index, attribute, fromUi=fromUi
            )

    def notifyRenderClientsForUpdate(
        self, updateFunction: str, *args, fromUi: bool = True
    ):
        for receiver in self.receivers:
            updatFunc = getattr(receiver, updateFunction)
            updatFunc(*args)

    def printOSC(self, *args, addr: str = "", port: int = 0):
        if self.bPrintOSC:
            log.info("incoming OSC on Port", port, addr, args)
