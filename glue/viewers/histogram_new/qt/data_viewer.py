from __future__ import absolute_import, division, print_function

from glue.utils import nonpartial
from glue.viewers.common.qt.mpl_toolbar import MatplotlibViewerToolbar
from glue.core.edit_subset_mode import EditSubsetMode
from glue.core import Data
from glue.core.util import update_ticks
from glue.core.roi import RangeROI
from glue.utils import defer_draw

from glue.viewers.common.qt.mpl_data_viewer import MatplotlibDataViewer
from glue.viewers.histogram_new.qt.layer_style_editor import HistogramLayerStyleEditor
from glue.viewers.histogram_new.layer_artist import HistogramLayerArtist
from glue.viewers.histogram_new.qt.options_widget import HistogramOptionsWidget
from glue.viewers.histogram_new.state import HistogramViewerState
from glue.viewers.histogram_new.compat import update_viewer_state

from glue.core.state import lookup_class_with_patches

__all__ = ['HistogramViewer']


class HistogramViewer(MatplotlibDataViewer):

    LABEL = 'New histogram viewer'
    _toolbar_cls = MatplotlibViewerToolbar
    _layer_style_widget_cls = HistogramLayerStyleEditor
    _state_cls = HistogramViewerState
    _options_cls = HistogramOptionsWidget
    _data_artist_cls = HistogramLayerArtist
    _subset_artist_cls = HistogramLayerArtist

    tools = ['select:xrange']

    def __init__(self, session, parent=None):
        super(HistogramViewer, self).__init__(session, parent)
        self.state.add_callback('xatt', nonpartial(self._update_axes))
        self.state.add_callback('log_x', nonpartial(self._update_axes))
        self.state.add_callback('normalize', nonpartial(self._update_axes))

    @defer_draw
    def _update_axes(self):

        if self.state.xatt is not None:

            # Update ticks, which sets the labels to categories if components are categorical
            update_ticks(self.axes, 'x', self.state._get_x_components(), False)

            if self.state.log_x:
                self.axes.set_xlabel('Log ' + self.state.xatt.label)
            else:
                self.axes.set_xlabel(self.state.xatt.label)

        if self.state.normalize:
            self.axes.set_ylabel('Normalized number')
        else:
            self.axes.set_ylabel('Number')

        self.axes.figure.canvas.draw()

    def apply_roi(self, roi):

        # TODO: move this to state class?

        # TODO: add back command stack here so as to be able to undo?
        # cmd = command.ApplyROI(client=self.client, roi=roi)
        # self._session.command_stack.do(cmd)

        # TODO Does subset get applied to all data or just visible data?

        # Expand roi to match bin edges
        # TODO: make this an option

        bins = self.state.bins

        x = roi.to_polygon()[0]
        lo, hi = min(x), max(x)

        if lo >= bins.min():
            lo = bins[bins <= lo].max()
        if hi <= bins.max():
            hi = bins[bins >= hi].min()

        roi_new = RangeROI(min=lo, max=hi, orientation='x')

        for layer_artist in self._layer_artist_container:

            if not isinstance(layer_artist.layer, Data):
                continue

            x_comp = layer_artist.layer.get_component(self.state.xatt)

            subset_state = x_comp.subset_from_roi(self.state.xatt, roi_new,
                                                  coord='x')

            mode = EditSubsetMode()
            mode.update(self._data, subset_state, focus_data=layer_artist.layer)

    def __gluestate__(self, context):
        return dict(state=self.state.__gluestate__(context),
                    session=context.id(self._session),
                    size=self.viewer_size,
                    pos=self.position,
                    layers=list(map(context.do, self.layers)),
                    _protocol=1)

    @classmethod
    def __setgluestate__(cls, rec, context):

        if rec.get('_protocol', 0) < 1:
            update_viewer_state(rec, context)

        session = context.object(rec['session'])
        viewer = cls(session)
        viewer.register_to_hub(session.hub)
        viewer.viewer_size = rec['size']
        x, y = rec['pos']
        viewer.move(x=x, y=y)

        viewer_state = HistogramViewerState.__setgluestate__(rec['state'], context)
        viewer.state.update_from_state(viewer_state)

        # Restore layer artists
        for l in rec['layers']:
            cls = lookup_class_with_patches(l.pop('_type'))
            layer_state = context.object(l['state'])
            print(type(layer_state))
            layer_artist = cls(axes=viewer.axes, viewer_state=viewer.state, layer_state=layer_state)
            viewer._layer_artist_container.append(layer_artist)

        return viewer
