from collections.abc import Callable
from functools import partial
import ipaddress
import logging
from threading import Semaphore, Thread
from typing import Any

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

from osc_kreuz.coordinates import get_all_coordinate_formats
from osc_kreuz.renderer import BaseRenderer, RendererException, TWonder, ViewClient
from osc_kreuz.soundobject import SoundObject
import osc_kreuz.str_keys_conventions as skc

log = logging.getLogger("OSCcomcenter")
# log.setLevel(logging.DEBUG)


class OSCComCenter:
    def __init__(
        self,
        soundobjects: list[SoundObject],
        receivers: list[BaseRenderer],
        renderengines: list[str],
        n_sources: int,
        n_direct_sends: int,
        ip: str,
        port_ui: int,
        port_data: int,
        port_settings: int,
    ) -> None:
        self.soundobjects = soundobjects

        self.subscribed_clients: dict[str, ViewClient] = {}
        self.receivers = receivers
        self.extendedOscInput = True
        self.verbosity = 0
        self.bPrintOSC = False

        self.renderengines = renderengines
        self.n_renderengines = len(renderengines)
        self.n_sources = n_sources
        self.n_direct_sends = n_direct_sends

        self.osc_ui_dispatcher = Dispatcher()
        self.osc_data_dispatcher = Dispatcher()
        self.osc_setting_dispatcher = Dispatcher()

        self.ip = ip
        self.port_ui = port_ui
        self.port_data = port_data
        self.port_settings = port_settings

        self.osc_ui_server = BlockingOSCUDPServer(
            (self.ip, self.port_ui), self.osc_ui_dispatcher
        )
        self.osc_data_server = BlockingOSCUDPServer(
            (self.ip, self.port_data), self.osc_data_dispatcher
        )
        self.osc_setting_server = BlockingOSCUDPServer(
            (self.ip, self.port_settings), self.osc_setting_dispatcher
        )

        self.connection_semaphore = Semaphore()

    def start(self):
        Thread(
            target=self.osc_ui_server.serve_forever, args=(0.1,), name="osc ui"
        ).start()
        Thread(
            target=self.osc_data_server.serve_forever, args=(0.1,), name="osc data"
        ).start()
        Thread(
            target=self.osc_setting_server.serve_forever,
            args=(0.1,),
            name="osc setting",
        ).start()

    def shutdown(self):
        self.osc_ui_server.shutdown()
        self.osc_data_server.shutdown()
        self.osc_setting_server.shutdown()
        for c in self.subscribed_clients.values():
            if c.pingTimer is not None:
                c.pingTimer.cancel()

    def setVerbosity(self, v: int):
        self.verbosity = v
        self.bPrintOSC = v >= 2
        BaseRenderer.setVerbosity(v)
        log.debug(f"verbosity set to {v}")

    def setupOscSettingsBindings(self):

        # also allow oscrouter in settings path for backwards compatibility
        for base_path in ["oscrouter", "osckreuz"]:
            self.osc_setting_dispatcher.map(
                f"/{base_path}/debug/osccopy", self.osc_handler_osccopy
            )
            self.osc_setting_dispatcher.map(
                f"/{base_path}/debug/verbose", self.osc_handler_verbose
            )
            self.osc_setting_dispatcher.map(
                f"/{base_path}/subscribe", self.osc_handler_subscribe
            )
            self.osc_setting_dispatcher.map(
                f"/{base_path}/unsubscribe", self.osc_handler_unsubscribe
            )
            self.osc_setting_dispatcher.map(f"/{base_path}/ping", self.osc_handler_ping)
            self.osc_setting_dispatcher.map(f"/{base_path}/pong", self.osc_handler_pong)
            self.osc_setting_dispatcher.map(f"/{base_path}/dump", self.osc_handler_dump)

        # handler for twonder connection
        self.osc_setting_dispatcher.map(
            "/WONDER/stream/render/connect", self.osc_handler_twonder_connect
        )

    def osc_handler_ping(self, address: str, *args):
        pass
        # TODO fix
        # if self.checkPort(args[0]):
        #     self.osc_setting_server.answer(
        #         b"/oscrouter/pong", port=args[0], values=["osc-kreuz"]
        #     )

    def osc_handler_pong(self, address: str, *args):

        try:
            clientName = args[0]
            self.subscribed_clients[clientName].receivedIsAlive()
        except Exception:
            if self.verbosity > 0:
                _name = ""
                if len(args) > 0:
                    _name = args[0]
                log.info("no renderer for pong message {}".format(_name))

    def osc_handler_subscribe(self, address: str, *args) -> None:
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
        client_init_dict = {}
        client_name = args[0]
        if len(args) >= 2:
            if self.checkPort(args[1]):
                client_init_dict["port"] = int(args[1])
                client_infos = self.osc_setting_server.get_request()[1]

                client_init_dict["hostname"] = str(client_infos[0])

                try:
                    client_init_dict["dataformat"] = args[2]
                except KeyError:
                    pass
                try:
                    client_init_dict["indexAsValue"] = args[3]
                except KeyError:
                    pass
                try:
                    client_init_dict["updateintervall"] = args[4]
                except KeyError:
                    pass
            # make sure clients that try to connect rapidly don't accidentally overwrite themselves
            with self.connection_semaphore:
                # check if this client is already connected
                if client_name in self.subscribed_clients:
                    if (
                        self.subscribed_clients[client_name].receivers[0][0]
                        == client_init_dict["hostname"]
                        and self.subscribed_clients[client_name].receivers[0][1]._port
                        == client_init_dict["port"]
                    ):
                        log.info(f"client {client_name} tried to reconnect")
                        return
                    else:
                        log.warning(f"client {client_name} exists already")
                        return
                newViewClient = ViewClient(client_name, **client_init_dict)

                self.subscribed_clients[client_name] = newViewClient
                self.receivers.append(newViewClient)
                newViewClient.checkAlive(self.deleteClient)

        else:
            if self.verbosity > 0:
                log.info("not enough arguments für view client")

    def osc_handler_twonder_connect(self, address: str, *args) -> None:

        # get name of twonder (only sent to osc path with signature "s")
        # TODO do something useful with the name
        name = "default_twonder"
        if len(args) == 1:
            name = args[0]

        # parse hostname and port
        if len(args) == 2:
            hostname = args[0]
            port = args[1]
        else:
            # get hostname and port from the request information
            client_infos = self.osc_setting_server.get_request()[1]

            hostname = client_infos[0]
            port = client_infos[1]

        if not self.checkPort(port) or not isinstance(hostname, str):
            log.warning(f"Invalid twonder connection request by {name}")
            return

        with self.connection_semaphore:
            # get twonder from receivers list if it already exists
            twonder = next(
                (
                    receiver
                    for receiver in self.receivers
                    if isinstance(receiver, TWonder)
                ),
                None,
            )
            if twonder is not None:
                twonder.add_receiver(hostname, port)
                log.info(f"new twonder {name} connected to receiver")
            else:
                try:
                    twonder = TWonder(hostname=hostname, port=port, updateintervall=50)
                except RendererException as e:
                    log.error(e)
                    return

                self.receivers.append(twonder)
                log.info(f"twonder {name} connected")

        # send initialization infos to twonder
        twonder.send_room_information(hostname, port)

    def osc_handler_unsubscribe(self, address: str, *args) -> None:
        """OSC Callback for unsubscribe Requests.

        These requests follow the format:
        /oscrouter/unsubscribe myname
        /oscrouter/unsubscribe [client_name]
        args[0] nameFor Client
        """
        log.info("unsubscribe request")
        if len(args) >= 1:
            client_name = args[0]
            try:
                view_client = self.subscribed_clients[client_name]
                self.deleteClient(view_client, client_name)

            except KeyError:
                log.warning(f"can't delete client {client_name}, it does not exist")
        else:
            log.warning("not enough arguments für view client")

    def osc_handler_dump(self, address: str, *args):
        pass
        # TODO: dump all source data to renderer

    def deleteClient(self, viewC, alias):
        # TODO check if this is threadsafe (it probably isn't)
        # TODO handle client with same name connection/reconnecting. maybe add ip as composite key?
        if self.verbosity > 0:
            log.info(f"deleting client {viewC}, {alias}")
        try:
            self.receivers.remove(viewC)
            del self.subscribed_clients[alias]
            log.info(f"removed client {alias}")
        except (ValueError, KeyError):
            log.warning(f"tried to delete receiver {alias}, but it does not exist")

    def checkPort(self, port) -> bool:
        """returns true when the port is of type int and in the valid range

        Args:
            port (Any): port to be checked

        Returns:
            bool: True if port is valid
        """
        if type(port) is int and 1023 < port < 65535:
            return True
        else:
            if self.verbosity > 0:
                log.info(f"port {port} not legit")
            return False

    def osc_handler_osccopy(self, address: str, *args):
        ip = ""
        port = 0
        if len(args) == 2:
            ip = args[0]
            port = args[1]
        elif len(args) == 1:
            ipport = args[0].split(":")
            if len(ipport) == 2:
                ip = ipport[0]
                port = ipport[1]
        else:
            BaseRenderer.debugCopy = False
            log.info("debug client: invalid message format")
            return
        try:
            ip = "127.0.0.1" if ip == "localhost" else ip
            osccopy_ip = ipaddress.ip_address(ip)
            osccopy_port = int(port)
        except Exception:
            log.info("debug client: invalid ip or port")
            return
        log.info(f"debug client connected: {ip}:{port}")

        if 1023 < osccopy_port < 65535:
            BaseRenderer.createDebugClient(str(osccopy_ip), osccopy_port)
            BaseRenderer.debugCopy = True
            return

        BaseRenderer.debugCopy = False

    def osc_handler_verbose(self, address: str, *args):
        vvvv = -1
        try:
            vvvv = int(args[0])
        except Exception:
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
    ) -> None:
        """Sets up all Osc Bindings"""
        self.setupOscSettingsBindings()

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
            for add in self.osc_ui_dispatcher._map.keys():
                log.info(add)

    def bindToDataAndUiPort(self, addr: str, func: Callable):
        log.debug(f"Adding OSC callback for {addr}")

        if self.verbosity >= 2:
            self.osc_ui_dispatcher.map(addr, partial(self.printOSC, port=self.port_ui))
            self.osc_data_dispatcher.map(
                addr, partial(self.printOSC, port=self.port_data)
            )

        self.osc_ui_dispatcher.map(addr, partial(func, fromUi=True))
        self.osc_data_dispatcher.map(addr, partial(func, fromUi=False))

    def sourceLegit(self, id: int) -> bool:
        indexInRange = 0 <= id < self.n_sources
        if self.verbosity > 0:
            if not indexInRange:
                if type(id) is not int:
                    log.warning("source index is no integer")
                else:
                    log.warning("source index out of range")
        return indexInRange

    def renderIndexLegit(self, id: int) -> bool:
        indexInRange = 0 <= id < self.n_renderengines
        if self.verbosity > 0:
            if not indexInRange:
                if type(id) is not int:
                    log.warning("renderengine index is no integer")
                else:
                    log.warning("renderengine index out of range")
        return indexInRange

    def directSendLegit(self, id: int) -> bool:
        indexInRange = 0 <= id < self.n_direct_sends
        if self.verbosity > 0:
            if not indexInRange:
                if type(id) is not int:
                    log.warning("direct send index is no integer")
                else:
                    log.warning("direct send index out of range")
        return indexInRange

    def osc_handler_position(
        self, address: str, *args, coord_fmt: str = "xyz", source_index=-1, fromUi=True
    ):
        args_index = 0

        if source_index == -1:
            try:
                source_index = int(args[args_index]) - 1
                args_index += 1
            except ValueError:
                log.warning(
                    f"tried to set position invalid source index type: {args[args_index]}"
                )
                return

        if not self.sourceLegit(source_index):
            log.warning(
                f"tried to set position for invalid source index {source_index}"
            )
            return

        if self.soundobjects[source_index].setPosition(
            coord_fmt, *args[args_index:], fromUi=fromUi
        ):
            self.notifyRenderClientsForUpdate(
                "sourcePositionChanged", source_index, fromUi=fromUi
            )

    def osc_handler_gain(
        self, address: str, *args, source_index=-1, render_index=-1, fromUi: bool = True
    ):

        args_index = 0

        if source_index == -1:
            try:
                source_index = int(args[args_index]) - 1
                args_index += 1
            except ValueError:
                log.warning(
                    f"Failed to parse source index for message to {address} with args {args}"
                )
                return

        if render_index == -1:
            try:
                render_index = int(args[args_index])
                args_index += 1
            except ValueError:
                log.warning(
                    f"Failed to parse render index for message to {address} with args {args}"
                )
                return

        try:
            gain = float(args[args_index])
        except ValueError:
            log.warning(
                f"Failed to parse gain for message to {address} with args {args}"
            )

            return

        if not (self.sourceLegit(source_index) and self.renderIndexLegit(render_index)):
            log.warning(
                f"invalid source or render index in message to {address} with args {args}"
            )
            return

        if self.soundobjects[source_index].setRendererGain(render_index, gain, fromUi):
            self.notifyRenderClientsForUpdate(
                "sourceRenderGainChanged", source_index, render_index, fromUi=fromUi
            )

    def osc_handler_direct_send_gain(
        self,
        address: str,
        *args,
        source_index=-1,
        direct_send_index=-1,
        fromUi: bool = True,
    ):
        args_index = 0
        if source_index == -1:
            try:
                source_index = int(args[args_index]) - 1
                args_index += 1
            except ValueError:
                return

        if direct_send_index == -1:
            try:
                direct_send_index = int(args[args_index])
                args_index += 1
            except ValueError:
                return

        try:
            gain = float(args[args_index])
        except ValueError:
            return

        if not (
            self.sourceLegit(source_index) and self.directSendLegit(direct_send_index)
        ):
            return

        if self.soundobjects[source_index].setDirectSend(
            direct_send_index, gain, fromUi
        ):
            self.notifyRenderClientsForUpdate(
                "sourceDirectSendChanged",
                source_index,
                direct_send_index,
                fromUi=fromUi,
            )
        return

    def osc_handler_attribute(
        self,
        address: str,
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
                return

        if attribute is None:
            try:
                attribute = skc.SourceAttributes(args[args_index])
                args_index += 1
            except ValueError:
                return

        try:
            value = float(args[args_index])
        except ValueError:
            return

        if self.soundobjects[source_index].setAttribute(attribute, value, fromUi):
            self.notifyRenderClientsForUpdate(
                "sourceAttributeChanged", source_index, attribute, fromUi=fromUi
            )
        return

    def notifyRenderClientsForUpdate(
        self, updateFunction: str, *args, fromUi: bool = True
    ) -> None:
        for receiver in self.receivers:
            updatFunc = getattr(receiver, updateFunction)
            updatFunc(*args)

    def printOSC(self, addr: str, *args: Any, port: int = 0) -> None:
        if self.bPrintOSC:
            log.info("incoming OSC on Port", port, addr, args)
