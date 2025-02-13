from time import time

import numpy as np

from osc_kreuz.coordinates import (
    Coordinate,
    CoordinateCartesian,
    CoordinatePolar,
    CoordinatePolarRadians,
    CoordinateSystemType,
    parse_coordinate_format,
)
import osc_kreuz.str_keys_conventions as skc

_tt = "time"
_uiBlock = "_uiDidBlock"


class SoundObjectException(Exception):
    pass


class SoundObject(object):

    globalConfig: dict = {}
    number_renderer = 1
    send_change_only = False

    preferUi = True
    dataPortTimeOut = 1.0

    @classmethod
    def readGlobalConfig(cls, config: dict):
        cls.globalConfig = config
        cls.preferUi = bool(not config["data_port_timeout"] == 0)
        cls.dataPortTimeOut = float(config["data_port_timeout"])

    def __init__(self, objectID: int = 0, coordinate_scaling_factor: float = 1):

        # XXX this is currently not used
        self.objectID = objectID

        # initialize coordinate dict
        self.position: dict[CoordinateSystemType, Coordinate] = {
            CoordinateSystemType.Cartesian: CoordinateCartesian(1, 0, 0),
            CoordinateSystemType.Polar: CoordinatePolar(0, 0, 1),
            CoordinateSystemType.PolarRadians: CoordinatePolarRadians(0, 0, 1),
        }

        self.coordinate_scaling_factor = coordinate_scaling_factor

        # initialize attributes
        self._sourceattributes = {
            skc.SourceAttributes.planewave: 0,
            skc.SourceAttributes.doppler: 1,
            skc.SourceAttributes.angle: 0.0,
        }

        # get the number of renderers
        if "render_units" in self.globalConfig:
            self.number_renderer = len(self.globalConfig["render_units"])

        # setup direct and renderer send gains
        self._torendererSends = [float(0.0) for _ in range(self.number_renderer)]
        self._directSends = [0.0] * self.globalConfig["number_direct_sends"]

        # setup dict that hold information whether some value was blocked by the ui port
        self.uiBlockingDict = {}
        self.uiBlockingDict["position"] = self.createBlockingDict()

        self.uiBlockingDict["attribute"] = self.createBlockingDict()

        self.uiBlockingDict["rendergain"] = []
        for _ in range(self.number_renderer):
            self.uiBlockingDict["rendergain"].append(self.createBlockingDict())
        self.uiBlockingDict["directsend"] = []
        for _ in range(self.globalConfig["number_direct_sends"]):
            self.uiBlockingDict["directsend"].append(self.createBlockingDict())

    def createBlockingDict(self) -> dict:
        return {_tt: time(), _uiBlock: False}

    def setPosition(
        self, coordinate_format_str: str, *values: float, fromUi: bool = True
    ) -> bool:
        """Sets the position in the specified format, updates all coordinate formats

        Args:
            coordinate_format_str (str): string describing the coordinate format
            *values (Iterable[int]):
            fromUi (bool, optional): _description_. Defaults to True.

        Returns:
            bool: True if something changed
        """
        if not self.shouldProcessInput(self.uiBlockingDict["position"], fromUi):
            return False

        coordinate_format, coordinate_keys = parse_coordinate_format(
            coordinate_format_str
        )

        # set the coordinates in the received format
        position_has_changed = self.position[coordinate_format].set_coordinates(
            coordinate_keys, values, self.coordinate_scaling_factor
        )

        # set the coordinates for all other formats
        if position_has_changed:
            for c_fmt in self.position:
                if c_fmt == coordinate_format:
                    continue
                self.position[c_fmt].set_all(
                    *(self.position[coordinate_format].convert_to(c_fmt))
                )

        # if set send position even if it did not change
        if not self.globalConfig[skc.send_changes_only]:
            position_has_changed = True
        return position_has_changed

    def getPosition(self, coordinate_format_str: str) -> list[float]:
        coordinate_format, coordinate_keys = parse_coordinate_format(
            coordinate_format_str
        )
        return self.position[coordinate_format].get_coordinates(coordinate_keys)

    def setAttribute(self, attribute, value, fromUi: bool = True) -> bool:

        if not self.shouldProcessInput(self.uiBlockingDict["attribute"], fromUi):
            return False

        if not self._sourceattributes[attribute] == value:
            self._sourceattributes[attribute] = value
            return True
        else:
            return False

    def getAttribute(self, attribute: skc.SourceAttributes):
        return self._sourceattributes[attribute]

    def setRendererGain(self, rendIdx: int, gain: float, fromUi: bool = True) -> bool:

        if not self.shouldProcessInput(
            self.uiBlockingDict["rendergain"][rendIdx], fromUi
        ):
            return False

        _gain = np.clip(gain, a_min=0, a_max=self.globalConfig[skc.max_gain])

        if self.globalConfig[skc.send_changes_only]:
            if self._torendererSends[rendIdx] == _gain:
                return False

        self._torendererSends[rendIdx] = _gain
        return True

    def setDirectSend(self, directIdx: int, gain: float, fromUi: bool = True) -> bool:
        if not self.shouldProcessInput(
            self.uiBlockingDict["directsend"][directIdx], fromUi
        ):
            return False

        _gain = np.clip(gain, a_min=0, a_max=self.globalConfig[skc.max_gain])

        if self.globalConfig[skc.send_changes_only]:
            if self._directSends[directIdx] == _gain:
                return False

        self._directSends[directIdx] = _gain
        return True

    def getAllRendererGains(self) -> list[float]:
        return self._torendererSends

    def getRenderGain(self, rIdx: int) -> float:
        return float(self._torendererSends[rIdx])

    def getAllDirectSends(self) -> list[float]:
        return self._directSends

    def getDirectSend(self, cIdx: int) -> float:
        return float(self._directSends[cIdx])

    def shouldProcessInput(
        self,
        blockDict: dict,
        fromUi: bool = True,
    ) -> bool:
        if fromUi:
            self.gotUiInput(blockDict)
            return True
        elif self.preferUi and self.dataPortStillBlocked(blockDict):
            return False
        else:
            return True

    def gotUiInput(self, blockDict: dict):
        blockDict[_uiBlock] = True
        blockDict[_tt] = time()

    def dataPortStillBlocked(self, blockDict: dict) -> bool:
        if blockDict[_uiBlock]:
            if time() - blockDict[_tt] > self.dataPortTimeOut:
                blockDict[_uiBlock] = False

        return blockDict[_uiBlock]
