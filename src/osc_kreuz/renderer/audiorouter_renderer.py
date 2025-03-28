import logging

from .base_renderer import BaseRenderer
from .updates import DirectSendUpdate, GainUpdate

log = logging.getLogger("renderer")
verbosity = 0





class Audiorouter(BaseRenderer):
    oscpath_gain_renderer = "/source/send/spatial"
    oscpath_gain_reverb = "/source/reverb/gain"
    oscpath_gain_direct = "/source/send/direct"

    def print_self_information(self, print_pos_format=False):
        super().print_self_information(print_pos_format=print_pos_format)

    def sourceDirectSendChanged(self, source_idx, send_idx):
        self.add_update(
            source_idx,
            DirectSendUpdate(
                self.oscpath_gain_direct,
                soundobject=self.sources[source_idx],
                send_index=send_idx,
                source_index=source_idx,
                include_send_idx=True,
            ),
        )

    def sourceRenderGainChanged(self, source_idx, render_idx):
        if render_idx == 1:
            return

        if render_idx == 2:
            path = self.oscpath_gain_reverb
            include_render_idx = False
        else:
            path = self.oscpath_gain_renderer
            include_render_idx = True

        self.add_update(
            source_idx,
            GainUpdate(
                path=path,
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_idx,
                include_render_idx=include_render_idx,
            ),
        )


class AudiorouterWFS(Audiorouter):
    def sourceRenderGainChanged(self, source_idx, render_idx):
        if render_idx != 1:
            return

        self.add_update(
            source_idx,
            GainUpdate(
                path=self.oscpath_gain_renderer,
                soundobject=self.sources[source_idx],
                render_idx=render_idx,
                source_index=source_idx,
                include_render_idx=True,
            ),
        )
