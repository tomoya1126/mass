# -*- coding: utf-8 -*-
"""
Plotting functionality for PeakPicker GUI.

Handles all spectrum visualization and graph updates.
"""

import logging
import numpy as np
import matplotlib.pyplot as plt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import PeakPickerGUI


logger = logging.getLogger(__name__)


class PlottingMixin:
    """Mixin class providing plotting methods for GUI."""

    def update_plot(self: 'PeakPickerGUI'):
        """Update the spectrum plot."""
        if self.spectrum is None:
            return

        # Determine axis mode and data
        if self.axis_mode.get() == 'mz' and self.calibration is not None:
            x_data = np.array([self.calibration.tof_to_mz(t) for t in self.spectrum.tof])
            x_data = np.array([x if x is not None else np.nan for x in x_data])
            x_label = 'm/z'
            center_x = self.calibration.tof_to_mz(self.center_pos) if self.center_pos else None
        else:
            x_data = self.spectrum.tof
            x_label = 'Time of Flight (TOF)'
            center_x = self.center_pos

        y_data = self.spectrum.intensity

        # Calculate view range
        if center_x is not None:
            min_x = center_x - self.window_size / 2
            max_x = center_x + self.window_size / 2
            data_min, data_max = np.nanmin(x_data), np.nanmax(x_data)
            min_x = max(min_x, data_min)
            max_x = min(max_x, data_max)
        else:
            min_x, max_x = np.nanmin(x_data), np.nanmax(x_data)

        # Filter data in view
        mask = (x_data >= min_x) & (x_data <= max_x) & (~np.isnan(x_data))
        x_view = x_data[mask]
        y_view = y_data[mask]

        # Clear and redraw
        self.ax.cla()

        # Plot spectrum
        if len(x_view) > 0:
            self.ax.plot(x_view, y_view, label='Spectrum', color='navy', lw=1.0)

            # Set y limits with padding (scaled by wheel zoom if requested)
            raw_y_max = np.max(y_view)
            y_max = raw_y_max * self.y_scale_factor
            y_pad = raw_y_max * 0.05 * self.y_scale_factor if raw_y_max > 0 else 1.0
            self.ax.set_ylim(0, y_max + y_pad)
        else:
            self.ax.plot([], [], label='Spectrum', color='navy', lw=1.0)

        self.ax.set_xlim(min_x, max_x)

        # Draw peaks
        self._draw_peaks(x_label)

        # Draw range lines
        self._draw_range_lines(x_label)

        # Labels and title
        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel('Ion Count')

        title = f'Spectrum (Center: {center_x:.2f}, Width: {max_x - min_x:.2f})'
        if self.calibration:
            title += f' [Calibrated: R²={self.calibration.r_squared:.4f}]'
        self.ax.set_title(title)

        # Legend
        handles, labels = self.ax.get_legend_handles_labels()
        handles_filtered = [h for h, l in zip(handles, labels) if not l.startswith('_')]
        labels_filtered = [l for l in labels if not l.startswith('_')]
        if handles_filtered:
            self.ax.legend(handles_filtered, labels_filtered, loc='upper right')

        self.ax.grid(True, ls=':', alpha=0.6)

        self.canvas.draw_idle()

    def _draw_peaks(self: 'PeakPickerGUI', x_label: str):
        """Draw peak markers on the plot."""
        y_max = self.ax.get_ylim()[1]
        txt_y_default = y_max * 0.95

        for i, peak in enumerate(self.peaks):
            # Determine x position based on axis mode
            if x_label == 'm/z' and peak.center_mz is not None:
                x_pos = peak.center_mz
                label_text = f"{int(round(peak.center_mz))}" if peak.center_mz else "?"
            else:
                x_pos = peak.center_tof
                label_text = f"TOF:{peak.center_tof:.1f}"

            # Check if peak is in view
            x_min, x_max = self.ax.get_xlim()
            if x_min <= x_pos <= x_max:
                # Color/style based on selection and status
                color, linestyle, linewidth, alpha = self._style_for_peak(peak, is_selected=(i == self.selected_peak_index))

                # Draw vertical line
                line = self.ax.axvline(x=x_pos, color=color, ls=linestyle, lw=linewidth, alpha=alpha, label='_peak_line')

                # Draw label
                txt_y = peak.height * 1.05 if peak.height * 1.05 < txt_y_default else txt_y_default
                text = self.ax.text(x_pos, txt_y, label_text, color=color,
                                   ha='center', va='bottom', picker=5, label='_peak_text', alpha=alpha)

                # Store references
                peak.line = line
                peak.text = text

    def _style_for_peak(self: 'PeakPickerGUI', peak, is_selected: bool):
        """Return plotting style based on peak status/selection."""
        status = getattr(peak, 'status', 'proposed')

        if status == 'accepted':
            color = 'darkgreen'
            linestyle = '-'
            linewidth = 1.4
            alpha = 1.0
        elif status == 'rejected':
            color = 'gray'
            linestyle = ':'
            linewidth = 0.9
            alpha = 0.5
        else:
            color = 'royalblue'
            linestyle = '--'
            linewidth = 1.0
            alpha = 0.9

        if is_selected:
            color = 'darkorange'
            linewidth = max(linewidth, 1.6)
            alpha = 1.0

        return color, linestyle, linewidth, alpha

    def _draw_range_lines(self: 'PeakPickerGUI', x_label: str):
        """Draw range selection lines."""
        if not self.range_selection_points:
            return

        for tof_pos in self.range_selection_points:
            # Convert position if needed
            if x_label == 'm/z' and self.calibration is not None:
                x_pos = self.calibration.tof_to_mz(tof_pos)
                if x_pos is None:
                    continue
            else:
                x_pos = tof_pos

            x_min, x_max = self.ax.get_xlim()
            if x_min <= x_pos <= x_max:
                line = self.ax.axvline(x=x_pos, color='lime', ls='-.', lw=1.0, label='_range')
                self.range_lines.append(line)

    def zoom_in(self: 'PeakPickerGUI'):
        """Zoom in the plot."""
        if self.spectrum is None:
            return

        current_width = self.ax.get_xlim()[1] - self.ax.get_xlim()[0]
        self.window_size = max(10, current_width / 1.5)
        logger.debug(f"Zoom in: window_size={self.window_size:.2f}")
        self.update_plot()

    def zoom_out(self: 'PeakPickerGUI'):
        """Zoom out the plot."""
        if self.spectrum is None:
            return

        current_width = self.ax.get_xlim()[1] - self.ax.get_xlim()[0]

        # Calculate total width based on axis mode
        if self.axis_mode.get() == 'mz' and self.calibration:
            total_width = abs(
                self.calibration.tof_to_mz(self.spectrum.tof.max()) -
                self.calibration.tof_to_mz(self.spectrum.tof.min())
            )
        else:
            total_width = self.spectrum.tof.max() - self.spectrum.tof.min()

        self.window_size = min(total_width, current_width * 1.5)
        logger.debug(f"Zoom out: window_size={self.window_size:.2f}")
        self.update_plot()

    def full_view(self: 'PeakPickerGUI'):
        """Show the full spectrum."""
        if self.spectrum is None:
            return

        if self.axis_mode.get() == 'mz' and self.calibration:
            mz_min = self.calibration.tof_to_mz(self.spectrum.tof.min())
            mz_max = self.calibration.tof_to_mz(self.spectrum.tof.max())
            if mz_min and mz_max:
                self.center_pos = self.calibration.mz_to_tof((mz_min + mz_max) / 2)
                self.window_size = abs(mz_max - mz_min)
            else:
                # Fallback to TOF
                self.center_pos = (self.spectrum.tof.min() + self.spectrum.tof.max()) / 2
                self.window_size = self.spectrum.tof.max() - self.spectrum.tof.min()
        else:
            self.center_pos = (self.spectrum.tof.min() + self.spectrum.tof.max()) / 2
            self.window_size = self.spectrum.tof.max() - self.spectrum.tof.min()

        logger.debug("Full view")
        self.update_plot()

    def on_slider_move(self: 'PeakPickerGUI', value):
        """Handle slider movement."""
        if self.spectrum is None:
            return

        try:
            index = int(float(value))
            index = max(0, min(index, len(self.spectrum.tof) - 1))
            self.center_pos = self.spectrum.tof[index]
            self.update_plot()
        except Exception as e:
            logger.error(f"Slider move error: {e}")

    def on_plot_motion(self: 'PeakPickerGUI', event):
        """Handle mouse motion over plot (cursor info)."""
        if getattr(self, 'drag_start', None) is not None and event.inaxes == self.ax:
            current_tof = self._convert_axis_to_tof(event.xdata) if event.xdata is not None else None
            if current_tof is not None:
                self._update_drag_span(self.drag_start, current_tof)

        if event.inaxes != self.ax or self.spectrum is None:
            if self.cursor_text and self.cursor_text in self.ax.texts:
                try:
                    self.cursor_text.remove()
                except:
                    pass
                self.cursor_text = None
                self.canvas.draw_idle()
            return

        x_pos = event.xdata

        # Convert to TOF if in m/z mode
        if self.axis_mode.get() == 'mz' and self.calibration:
            tof_pos = self.calibration.mz_to_tof(x_pos)
            intensity = np.interp(tof_pos, self.spectrum.tof, self.spectrum.intensity)
            txt = f"m/z: {x_pos:.2f}\nCount: {intensity:.1f}"

            # Also show TOF
            txt += f"\nTOF: {tof_pos:.2f}"
        else:
            intensity = np.interp(x_pos, self.spectrum.tof, self.spectrum.intensity)
            txt = f"TOF: {x_pos:.2f}\nCount: {intensity:.1f}"

            # Show m/z if calibrated
            if self.calibration:
                mz = self.calibration.tof_to_mz(x_pos)
                if mz:
                    txt += f"\nm/z: {int(round(mz))}"

        # Position text near cursor
        x_offset = (self.ax.get_xlim()[1] - self.ax.get_xlim()[0]) * 0.02
        y_offset = (self.ax.get_ylim()[1] - self.ax.get_ylim()[0]) * 0.02

        if self.cursor_text and self.cursor_text in self.ax.texts:
            self.cursor_text.set_position((x_pos + x_offset, intensity - y_offset))
            self.cursor_text.set_text(txt)
        else:
            self.cursor_text = self.ax.text(
                x_pos + x_offset, intensity - y_offset, txt,
                color='k', ha='left', va='top',
                bbox=dict(boxstyle='round,pad=0.3', fc='lightyellow', alpha=0.8)
            )

        self.canvas.draw_idle()

    def _update_drag_span(self: 'PeakPickerGUI', start_tof: float, end_tof: float):
        """Draw or update a drag selection span."""
        start_x = self._convert_tof_to_axis(start_tof)
        end_x = self._convert_tof_to_axis(end_tof)
        if start_x is None or end_x is None:
            return

        if self.drag_span and self.drag_span in self.ax.patches:
            try:
                self.drag_span.remove()
            except Exception:
                pass

        x0, x1 = sorted([start_x, end_x])
        self.drag_span = self.ax.axvspan(x0, x1, color='skyblue', alpha=0.2, label='_drag_span')
        self.canvas.draw_idle()
