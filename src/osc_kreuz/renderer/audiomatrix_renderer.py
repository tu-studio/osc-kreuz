from collections.abc import Iterable
import logging

from typing import Any

from .updates import GainUpdate, PositionUpdate

from .base_renderer import BaseRenderer
from ..config import read_config_option

log = logging.getLogger("renderer")
verbosity = 0





class AudioMatrix(BaseRenderer):
    def __init__(self, paths: Iterable[dict[str, Any]], **kwargs):
        super().__init__(**kwargs)
        self.gain_paths: dict[int, list[str]] = {}
        self.pos_paths: list[tuple[str, str]] = []

        # this dict is used to translate between render unit index and render unit name
        self.render_unit_indices = {}

        # prepare gain path with all render unit indices
        for index, render_unit in enumerate(self.globalConfig["render_units"]):
            self.render_unit_indices[index] = render_unit
            self.render_unit_indices[render_unit] = index
            self.gain_paths[index] = []

        # add all configured paths from the yaml file to either the correct gain path index,
        # or to the position_path list
        for path in paths:
            osc_path: str = path["path"]
            path_type = path["type"]

            if path_type == "gain":
                renderer = path["renderer"]
                renderer_index = self.render_unit_indices[renderer]
                self.gain_paths[renderer_index].append(osc_path)
            elif path_type in ["position", "pos"]:
                coord_fmt = read_config_option(path, "dataformat", str, "xyz")

                self.pos_paths.append((osc_path, coord_fmt))

        log.debug("Audio Matrix initialized")

    def sourceRenderGainChanged(self, source_idx, render_idx):
        if render_idx in self.gain_paths:
            for path in self.gain_paths[render_idx]:
                self.add_update(
                    source_idx,
                    GainUpdate(
                        path=path,
                        soundobject=self.sources[source_idx],
                        render_idx=render_idx,
                        source_index=source_idx,
                    ),
                )

    def sourcePositionChanged(self, source_idx):
        for path, coord_fmt in self.pos_paths:
            self.add_update(
                source_idx,
                PositionUpdate(
                    path=path,
                    soundobject=self.sources[source_idx],
                    coord_fmt=coord_fmt,
                    source_index=source_idx,
                ),
            )
