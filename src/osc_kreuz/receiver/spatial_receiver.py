from .base_receiver import BaseReceiver
from .updates import PositionUpdate


class SpatialReceiver(BaseReceiver):
    def sourcePositionChanged(self, source_idx):
        self.add_update(
            source_idx,
            PositionUpdate(
                path=self.oscpath_position,
                soundobject=self.sources[source_idx],
                coord_fmt=self.posFormat,
                source_index=source_idx,
            ),
        )
