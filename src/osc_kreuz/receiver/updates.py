from ..soundobject import SoundObject
from typing import Any, Iterable
import osc_kreuz.str_keys_conventions as skc
class OSCMessage:
    def __init__(self, path: str, values: Any) -> None:
        self.path: str = path
        if isinstance(values, str) or not isinstance(values, Iterable):
            values = [values]
        else:
            values = list(values)
        self.values: list[Any] = values

class Update:
    """Base Class for an Update sent via OSC. Updates with specific requirements should inherit from this one"""

    def __init__(
        self,
        path: str,
        soundobject: SoundObject,
        source_index: int | None = None,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        """Construct a new Update.
        The values of the Message created out of this Update will look like this, values in <brackets> are optional:
        [<source_index>, <pre_arg>, value, <**values>,..., <post_arg>]


        Args:
            path (str): OSC Path this update should be sent to
            soundobject (SoundObject): the Soundobject this Update belongs to, usually the get_value() function needs this
            source_index (int | None, optional): source index of this Soundobject. Needed when the source index . Defaults to None.
            pre_arg (Any, optional): argument that should be added to OSC Message before the actual values. Defaults to None.
            post_arg (Any, optional): argument that should be added to OSC Message at the end. Defaults to None.
        """
        self.soundobject = soundobject
        self.pre_arg = pre_arg
        self.post_arg = post_arg
        self.path = path
        self.source_index = source_index

    def get_value(self):
        """Override this function!

        Raises:
            NotImplementedError: Seemds like you didn't override this function!
        """
        raise NotImplementedError

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                isinstance(other, self.__class__)
                and self.source_index == other.source_index
                and self.path == other.path
            )
        return False

    def __hash__(self):
        """for use with sets"""
        return hash(tuple(sorted(self.__dict__.items())))

    def to_message(self) -> OSCMessage:
        values: list[str | int | float] = []

        # add source index to list if it exists
        if self.source_index is not None:
            values.append(self.source_index)

        # sometimes needed as first argument
        if self.pre_arg is not None:
            values.append(self.pre_arg)

        # add value or values returned by the callback to the list
        ret_value = self.get_value()
        if isinstance(ret_value, str) or not isinstance(ret_value, Iterable):
            values.append(ret_value)
        else:
            values.extend(ret_value)

        # sometimes needed as a last argument
        if self.post_arg is not None:
            values.append(self.post_arg)

        return OSCMessage(self.path, values)


class PositionUpdate(Update):
    def __init__(
        self,
        path: str,
        soundobject: SoundObject,
        coord_fmt: str,
        source_index: int | None = None,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        super().__init__(path, soundobject, source_index, pre_arg, post_arg)
        self.coord_fmt = coord_fmt

    def get_value(self):
        return self.soundobject.getPosition(self.coord_fmt)


class GainUpdate(Update):
    def __init__(
        self,
        path: str,
        soundobject: SoundObject,
        render_idx: int,
        source_index: int | None = None,
        pre_arg: Any = None,
        post_arg: Any = None,
        include_render_idx=False,
    ):
        super().__init__(path, soundobject, source_index, pre_arg, post_arg)
        self.render_idx = render_idx
        if include_render_idx:
            self.pre_arg = render_idx

    def get_value(self):
        return self.soundobject.getRenderGain(self.render_idx)


class DirectSendUpdate(Update):
    def __init__(
        self,
        path: str,
        soundobject: SoundObject,
        send_index: int,
        source_index: int | None = None,
        include_send_idx=False,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        super().__init__(path, soundobject, source_index, pre_arg, post_arg)
        self.send_index = send_index
        if include_send_idx:
            self.pre_arg = send_index

    def get_value(self):
        return self.soundobject.getDirectSend(self.send_index)


class AttributeUpdate(Update):
    def __init__(
        self,
        path: str,
        attribute: skc.SourceAttributes,
        soundobject: SoundObject,
        source_index: int | None = None,
        include_attribute_name=False,
        pre_arg: Any = None,
        post_arg: Any = None,
    ):
        super().__init__(path, soundobject, source_index, pre_arg, post_arg)
        self.attribute = attribute
        if include_attribute_name:
            self.pre_arg = attribute.value

    def get_value(self):
        return self.soundobject.getAttribute(self.attribute)