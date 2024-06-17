import numpy as np
import osc_kreuz.str_keys_conventions as skc
import osc_kreuz.conversionsTools as ct
from functools import partial
from time import time

_tt = "time"
_uiBlock = "_uiDidBlock"


class SoundObject(object):

    globalConfig: dict = {}
    # data_port_timeout = 0.5
    number_renderer = 1
    # maxGain = 2.
    send_change_only = False
    #
    preferUi = True
    dataPortTimeOut = 1.0
    conversionMap = {
        skc.polar: {
            (False, True, True): (ct.conv_ncart2pol, skc.CoordFormats.nxyzd),
            (False, True, False): (ct.conv_cart2pol, skc.CoordFormats.xyz),
            (False, False, True): (ct.conv_ncart2pol, skc.CoordFormats.nxyzd),
        },
        skc.cartesian: {
            (True, False, True): (ct.conv_ncart2cart, skc.CoordFormats.nxyzd),
            (True, False, False): (ct.conv_pol2cart, skc.CoordFormats.aed),
            (False, False, True): (ct.conv_ncart2cart, skc.CoordFormats.nxyzd),
        },
        skc.normcartesian: {
            (True, True, False): (ct.conv_cart2ncart, skc.CoordFormats.xyz),
            (True, False, False): (ct.conv_pol2ncart, skc.CoordFormats.aed),
            (False, True, False): (ct.conv_cart2ncart, skc.CoordFormats.xyz),
        },
    }

    @classmethod
    def readGlobalConfig(cls, config: dict):
        cls.globalConfig = config
        cls.preferUi = bool(not config["data_port_timeout"] == 0)
        cls.dataPortTimeOut = float(config["data_port_timeout"])
        # cls.number_renderer =

    def __init__(self, objectID: int = 0, coordinate_scaling_factor: float = 1):

        self.objectID = objectID

        self._position: dict[str, float] = {
            skc.x: 0.0,
            skc.y: 1.0,
            skc.z: 0.0,
            skc.azim: 0.0,
            skc.elev: 0.0,
            skc.dist: 1.0,
            skc.angle: 0.0,
            skc.nx: 0.0,
            skc.ny: 1.0,
            skc.nz: 0.0,
            skc.az_rad: 0.0,
            skc.el_rad: 0.0,
        }
        self.coordinate_scaling_factor = coordinate_scaling_factor
        self._sourceattributes = {
            skc.SourceAttributes.planewave: 0,
            skc.SourceAttributes.doppler: 0,
            skc.SourceAttributes.angle: 0.0,
        }

        if "render_units" in self.globalConfig:
            self.number_renderer = len(self.globalConfig["render_units"])

        self._torendererSends = [float(0.0) for _ in range(self.number_renderer)]
        self._changedSends: set = set()
        self._directSends = [0.0] * self.globalConfig["number_direct_sends"]
        self._changedDirSends = set()

        self._positionIsSet = {
            skc.polar: False,
            skc.cartesian: True,
            skc.normcartesian: True,
            skc.polar_rad: False,
        }
        self._lastUpdateKey = ""

        self._contState = skc.sControl_state.auto_switch_control

        self.uiBlockingDict = {}
        self.uiBlockingDict["position"] = self.createBlockingDict()

        self.uiBlockingDict["attribute"] = self.createBlockingDict()

        self.uiBlockingDict["rendergain"] = []
        for i in range(self.number_renderer):
            self.uiBlockingDict["rendergain"].append(self.createBlockingDict())
        self.uiBlockingDict["directsend"] = []
        for i in range(self.globalConfig["number_direct_sends"]):
            self.uiBlockingDict["directsend"].append(self.createBlockingDict())

        # self.t_renderGain = [time()] * self.number_renderer

        # self._uiDidSetRenderGain = [False] * self.number_renderer
        # self.t_directSend = [time()] * self.globalConfig['number_direct_sends']
        # self._uiDidSetDirectSend = [False] * self.globalConfig['number_direct_sends']

    def createBlockingDict(self) -> dict:
        return {_tt: time(), _uiBlock: False}

    def _getPositionValuesForKey(self, key: skc.CoordFormats) -> list[float]:
        vals = []
        for kk in skc.posformat[key.value][1]:
            vals.append(self._position[kk])

        return vals

    def setControlState(self, state: skc.sControl_state):
        self._contState = state

    def updateCoordinateFormat(self, updateFormat):

        # if updateFormat =
        calcRad = False
        calcDeg = False
        if updateFormat == skc.polar_rad:
            if self._positionIsSet[skc.polar]:
                _convert = False
            else:
                _convert = True
            updateFormat = skc.polar
            calcRad = True

        elif updateFormat == skc.polar and self._positionIsSet[skc.polar_rad]:
            calcDeg = True
            _convert = False

        else:
            calcRad = False
            _convert = True

        if _convert:
            statusTupel = (
                self._positionIsSet[skc.polar],
                self._positionIsSet[skc.cartesian],
                self._positionIsSet[skc.normcartesian],
            )

            convert_metadata = self.conversionMap[updateFormat][statusTupel]
            conversion = partial(
                convert_metadata[0]
            )  # , skc.posformat[convert_metadata[1]])

            updatedCoo = conversion(*self._getPositionValuesForKey(convert_metadata[1]))
            for idx, coo in enumerate(skc.fullformat[updateFormat]):
                self._position[coo] = updatedCoo[idx]

        if calcRad:
            self._position[skc.az_rad] = np.deg2rad(self._position[skc.azim])
            self._position[skc.el_rad] = np.deg2rad(self._position[skc.elev])
            # [self._position[skc.az_rad], self._position[skc.el_rad]] = (
            #     ct.convert_deg_angleToRad_correctMath(
            #         self._position[skc.azim], self._position[skc.elev]
            #     )
            # )
            self._positionIsSet[skc.polar_rad] = True
        elif calcDeg:
            self._position[skc.azim] = np.rad2deg(self._position[skc.az_rad])
            self._position[skc.elev] = np.rad2deg(self._position[skc.el_rad])

        self._positionIsSet[updateFormat] = True

    def setPosition(self, coordinate_key: str, *values, fromUi: bool = True) -> bool:
        """This function is called to set the position of this sound object.

        Args:
            coordinate_key (str): _description_
            fromUi (bool, optional): _description_. Defaults to True.

        Returns:
            bool: True if the position was changed
        """
        if not self.shouldProcessInput(self.uiBlockingDict["position"], fromUi):
            return False

        coordinateType = skc.posformat[coordinate_key][0]
        sthChanged = False

        # handle formats that are not full where coordinates are
        # currently not present in the right format
        if (
            not self._positionIsSet[coordinateType]
            and not skc.posformat[coordinate_key][2]
        ):
            self.updateCoordinateFormat(coordinateType)
            sthChanged = True

        # reset positionIsSet for all coordinate types
        for key in self._positionIsSet.keys():
            self._positionIsSet[key] = False

        self._lastUpdateKey = coordinate_key

        # TODO:copy old position

        # here the Position is set
        for idx, key in enumerate(skc.posformat[coordinate_key][1]):
            newValue = values[idx]

            # don't let distance become zero. coordinate_scaling also happens here
            # TODO find better solution, this just works for aed, not for xyz coordinates
            if key == skc.dist:
                newValue = newValue * self.coordinate_scaling_factor
                newValue = np.maximum(self.globalConfig["min_dist"], newValue)
            elif coordinateType == skc.cartesian or key == skc.nd:
                newValue *= self.coordinate_scaling_factor

            if self.globalConfig[skc.send_changes_only]:
                if not newValue == self._position[key]:
                    sthChanged = True
                    self._position[key] = newValue
            else:
                self._position[key] = newValue
                sthChanged = True

        self._positionIsSet[coordinateType] = True

        # TODO: compare new Position with old position for return
        return sthChanged

    def getSingleValueUpdate(self, keys):
        if self._lastUpdateKey in keys:
            return (self._lastUpdateKey, self._position[self._lastUpdateKey])
        else:
            return False

    def getPosition(self, pos_key: skc.CoordFormats) -> list[float] | float:
        """Get Position of this sound object in the format specified in pos_key

        Args:
            pos_key (str): str key of the desired position format

        Returns:
            list[float]: desired coordinates in a list. ATTENTION: If only one coordinate is requested, it is instead returned as a float.
        """
        coordinateType = skc.posformat[pos_key.value][0]

        if not self._positionIsSet[coordinateType]:
            self.updateCoordinateFormat(coordinateType)

        coords = []  # np.array([], dtype=float)
        for key in skc.posformat[pos_key.value][1]:
            coords.append(float(self._position[key]))
        # float_coords = coords.
        if len(coords) == 1:
            return coords[0]
        else:
            return coords

    def setAttribute(self, attribute, value, fromUi: bool = True) -> bool:

        if not self.shouldProcessInput(self.uiBlockingDict["attribute"], fromUi):
            return False

        # if self.preferUi:
        #     if not fromUi and self._uiDidSetAttribute:
        #         if self.dataPortStillBlocked(self.t_setAttribute):
        #             return False
        #         else:
        #             self._uiDidSetAttribute = False
        #     else:
        #         self.t_position = time()
        #         self._uiDidSetAttribute = True

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

        # if self.preferUi:
        #     if not fromUi and self._uiDidSetRenderGain[rendIdx]:
        #         if self.dataPortStillBlocked(self.t_renderGain[rendIdx]):
        #             return False
        #         else:
        #             self._uiDidSetRenderGain[rendIdx] = False
        #     else:
        #         self.t_position = time()
        #         self._uiDidSetRenderGain[rendIdx] = True

        _gain = np.clip(gain, a_min=0, a_max=self.globalConfig[skc.max_gain])

        if self.globalConfig[skc.send_changes_only]:
            if self._torendererSends[rendIdx] == _gain:
                return False

        self._torendererSends[rendIdx] = _gain
        # self._changedSends.add(rendIdx)
        return True

    def setDirectSend(self, directIdx: int, gain: float, fromUi: bool = True) -> bool:
        # TODO: replace the fromUi thing with a function
        if not self.shouldProcessInput(
            self.uiBlockingDict["directsend"][directIdx], fromUi
        ):
            return False

        # if self.preferUi:
        #     if not fromUi and self._uiDidSetDirectSend[directIdx]:
        #         if self.dataPortStillBlocked(self.t_directSend[directIdx]):
        #             return False
        #         else:
        #             self._uiDidSetDirectSend[directIdx] = False
        #     else:
        #         self.t_position = time()
        #         self._uiDidSetDirectSend[directIdx] = True

        _gain = np.clip(gain, a_min=0, a_max=self.globalConfig[skc.max_gain])

        if self.globalConfig[skc.send_changes_only]:
            if self._directSends[directIdx] == _gain:
                return False

        self._directSends[directIdx] = _gain
        # self._changedDirSends.add(directIdx)
        return True

    def checkIsBlocked(self, *args):
        pass

    def getBoolAndTime(self, *args):
        pass

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
