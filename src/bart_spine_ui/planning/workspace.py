from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import vtk
from PySide6.QtCore import QEvent, QLineF, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QImage
from vtkmodules.util.numpy_support import numpy_to_vtk

from ..assets.model.src.bart_spine_implant_models import make_screw_actor, make_tulip_actor
from ..core import SliceOrientation
from ..imaging.models import MedicalVolume
from ..segmentation import SegmentationVolume
from ..ui.screw_adjustment_overlay import ScrewAdjustmentOverlay
from ..ui.trajectory_touch_overlay import TrajectoryTouchOverlay
from ..visualization import ImagingWorkspace
from .models import ScrewPlan, Side
from .slice_intersection import screw_slice_intersection


class PlanningWorkspace(ImagingWorkspace):
    """ImagingWorkspace plus entry-point picking and pedicle-screw overlays."""

    entry_point_picked = Signal(object)  # tuple[float, float, float] in LPS mm
    angles_changed = Signal(float, float)

    @property
    def mpr_views(self):
        """Planning intentionally uses only the axial and sagittal views."""

        return self.axial, self.sagittal

    def __init__(self, parent=None):
        super().__init__(parent)
        self._volume: MedicalVolume | None = None
        self._segmentation: SegmentationVolume | None = None
        self._marking_entry = False
        self._pending_entry_point: tuple[float, float, float] | None = None
        self._active_plan: ScrewPlan | None = None
        self._plans: dict[tuple[str, Side], ScrewPlan] = {}
        self._mpr_overlay_actors: dict[object, list[vtk.vtkProp]] = {
            panel: [] for panel in self.mpr_views
        }
        self._three_d_actors: list[vtk.vtkProp] = []

        self.screw_overlay = ScrewAdjustmentOverlay(self)
        self.screw_overlay.clear_plan()
        self.screw_overlay.show()

        for panel in self.panels:
            self._layout.removeWidget(panel)
        self.coronal.hide()
        self.three_d.hide()
        self.three_d.maximize_button.hide()
        self.three_d.model_toggle.hide()
        self._layout.setContentsMargins(9, 10, 9, 10)
        self._layout.setSpacing(9)
        self._layout.addWidget(self.axial, 0, 0)
        self._layout.addWidget(self.sagittal, 0, 1)
        self._layout.addWidget(self.screw_overlay, 1, 0, 1, 2)
        self._layout.setRowStretch(0, 1)
        self._layout.setRowStretch(1, 0)
        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1)

        self.axial_angle_control = TrajectoryTouchOverlay(
            "AXIAL ANGLE",
            "left",
            "right",
            self.axial.vtk_widget,
        )
        self.sagittal_angle_control = TrajectoryTouchOverlay(
            "SAGITTAL ANGLE",
            "down",
            "up",
            self.sagittal.vtk_widget,
        )
        self._angle_control_backgrounds = {
            panel: self._create_angle_control_background(panel)
            for panel in self.mpr_views
        }
        self._angle_control_background_state = {}
        self._angle_press = None
        for panel in self.mpr_views:
            panel.vtk_widget.installEventFilter(self)

        self.axial_angle_control.delta_requested.connect(
            lambda delta: self._adjust_active_angle("axial", delta)
        )
        self.sagittal_angle_control.delta_requested.connect(
            lambda delta: self._adjust_active_angle("sagittal", delta)
        )

        for panel in self.mpr_views:
            panel.interactor.AddObserver(
                "LeftButtonPressEvent",
                lambda _obj, _event, view=panel: self._on_left_click(view),
                1.0,
            )
            panel.slider.valueChanged.connect(
                lambda _value, view=panel: self._refresh_mpr_overlay(view)
            )

    def toggle_maximize(self, panel) -> None:
        if panel not in self.mpr_views:
            return
        if self._maximized_panel is panel:
            self._maximized_panel = None
            self._layout.removeWidget(panel)
            self._layout.addWidget(self.axial, 0, 0)
            self._layout.addWidget(self.sagittal, 0, 1)
            self.axial.show()
            self.sagittal.show()
            panel.set_maximized_state(False)
            return

        self._maximized_panel = panel
        for candidate in self.mpr_views:
            self._layout.removeWidget(candidate)
            candidate.setVisible(candidate is panel)
            candidate.set_maximized_state(candidate is panel)
        self._layout.addWidget(panel, 0, 0, 1, 2)

    def set_volume(self, volume: MedicalVolume) -> None:
        self._volume = volume
        super().set_volume(volume)

    def set_segmentation(self, segmentation: SegmentationVolume) -> None:
        self._segmentation = segmentation
        super().set_segmentation(segmentation)

    def focus_three_d_level(self, level: str, side: Side) -> None:
        if self._segmentation is None:
            return
        for label, name in self._segmentation.labels.items():
            if name == level:
                self.three_d.focus_on_segmentation_label(int(label), side)
                return

    def clear_segmentation(self) -> None:
        self._segmentation = None
        self._marking_entry = False
        self.clear_plans()
        super().clear_segmentation()

    def begin_entry_point_marking(self, enabled: bool = True) -> None:
        self._marking_entry = bool(enabled)
        cursor = Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor
        for panel in self.mpr_views:
            panel.vtk_widget.setCursor(cursor)

    def focus_on_physical_point(
        self,
        point_lps: tuple[float, float, float],
        *,
        parallel_scale_mm: float = 42.0,
    ) -> None:
        if self._volume is None:
            return
        point = np.asarray(point_lps, dtype=float)
        continuous_index = self._volume.sitk_image.TransformPhysicalPointToContinuousIndex(
            tuple(float(v) for v in point)
        )

        for panel in self.mpr_views:
            if panel.orientation is SliceOrientation.AXIAL:
                index = round(continuous_index[2])
            elif panel.orientation is SliceOrientation.CORONAL:
                index = round(continuous_index[1])
            else:
                index = round(continuous_index[0])
            index = max(panel.slider.minimum(), min(panel.slider.maximum(), index))
            panel.slider.setValue(index)
            self._center_panel_camera(panel, point, parallel_scale_mm)
            panel.render()
        self._position_angle_controls()

    def set_plans(
        self,
        plans: Mapping[tuple[str, Side], ScrewPlan],
        *,
        active_key: tuple[str, Side] | None = None,
    ) -> None:
        self._plans = dict(plans)
        self._active_plan = self._plans.get(active_key) if active_key is not None else None
        if self._active_plan is not None:
            self._pending_entry_point = None
        self._sync_angle_controls()
        self._refresh_all_overlays()

    def set_pending_entry_point(
        self,
        point: tuple[float, float, float] | None,
    ) -> None:
        self._pending_entry_point = point
        for panel in self.mpr_views:
            self._refresh_mpr_overlay(panel)

    def set_active_plan(self, plan: ScrewPlan | None) -> None:
        self._active_plan = plan
        if plan is not None:
            self._plans[(plan.level, plan.side)] = plan
        self._sync_angle_controls()
        self._refresh_all_overlays()

    def clear_plans(self) -> None:
        self._plans.clear()
        self._active_plan = None
        self._pending_entry_point = None
        self._sync_angle_controls()
        self._clear_mpr_overlays()
        self._clear_three_d_overlays()
        self.screw_overlay.clear_plan()
        self._position_angle_controls()

    def _sync_angle_controls(self) -> None:
        plan = self._active_plan
        self.axial_angle_control.set_angle(plan.axial_angle_deg if plan is not None else None)
        self.sagittal_angle_control.set_angle(
            plan.sagittal_angle_deg if plan is not None else None
        )
        self.axial_angle_control.hide()
        self.sagittal_angle_control.hide()

    def _adjust_active_angle(self, orientation: str, delta: float) -> None:
        plan = self._active_plan
        if plan is None:
            return
        axial = plan.axial_angle_deg + delta if orientation == "axial" else plan.axial_angle_deg
        sagittal = (
            plan.sagittal_angle_deg + delta
            if orientation == "sagittal"
            else plan.sagittal_angle_deg
        )
        self.angles_changed.emit(
            max(-45.0, min(45.0, axial)),
            max(-35.0, min(35.0, sagittal)),
        )

    @staticmethod
    def _create_angle_control_background(panel):
        """One RGBA image actor owns all controller pixels in the VTK framebuffer."""
        mapper = vtk.vtkImageMapper()
        mapper.SetColorWindow(255)
        mapper.SetColorLevel(127.5)
        actor = vtk.vtkActor2D()
        actor.SetMapper(mapper)
        actor.VisibilityOff()
        actor.PickableOff()
        panel.renderer.AddViewProp(actor)
        return actor, mapper

    def _update_angle_control_background(self, panel, control, x: int, y: int) -> bool:
        widget = panel.vtk_widget
        actor, mapper = self._angle_control_backgrounds[panel]
        visible = self._active_plan is not None
        render_width, render_height = widget.GetRenderWindow().GetSize()
        state = (x, y, render_width, render_height, control.value.text(), visible)
        if self._angle_control_background_state.get(panel) == state:
            return False
        if render_width <= 0 or render_height <= 0:
            actor.VisibilityOff()
            return False
        self._angle_control_background_state[panel] = state
        actor.SetVisibility(visible)
        if not visible:
            return True

        # Render a hidden Qt template into fresh transparent pixels, never a scan capture.
        control.ensurePolished()
        control.layout().activate()
        image = QImage(control.size(), QImage.Format.Format_RGBA8888)
        image.fill(Qt.GlobalColor.transparent)
        control.render(image)
        scale_x = render_width / widget.width()
        scale_y = render_height / widget.height()
        image = image.scaled(
            max(1, round(control.width() * scale_x)),
            max(1, round(control.height() * scale_y)),
        ).convertToFormat(QImage.Format.Format_RGBA8888)
        pixels = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(), image.bytesPerLine()
        )[:, :image.width() * 4].reshape(image.height(), image.width(), 4)
        pixels = np.ascontiguousarray(pixels[::-1]).reshape(-1, 4)
        data = vtk.vtkImageData()
        data.SetDimensions(image.width(), image.height(), 1)
        data.GetPointData().SetScalars(numpy_to_vtk(pixels, deep=True))
        mapper.SetInputData(data)
        actor.SetPosition(round(x * scale_x), render_height - round(y * scale_y) - image.height())
        return True

    def eventFilter(self, watched, event):
        for panel, control in (
            (getattr(self, "axial", None), getattr(self, "axial_angle_control", None)),
            (getattr(self, "sagittal", None), getattr(self, "sagittal_angle_control", None)),
        ):
            if control is None or watched is not panel.vtk_widget:
                continue
            if event.type() not in (
                QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            ) or event.button() != Qt.MouseButton.LeftButton:
                break
            local = event.position().toPoint() - control.pos()
            inside = self._active_plan is not None and control.rect().contains(local)
            if event.type() == QEvent.Type.MouseButtonPress and inside:
                self._angle_press = (watched, local)
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                pressed = getattr(self, "_angle_press", None)
                self._angle_press = None
                if pressed is not None and pressed[0] is watched:
                    for button in (control.negative_button, control.positive_button):
                        if inside and button.geometry().contains(local) and button.geometry().contains(
                            pressed[1]
                        ):
                            button.click()
                            break
                    return True
            if inside:
                return True
        return super().eventFilter(watched, event)

    def _position_angle_controls(self) -> None:
        """Position angle controls while avoiding the visible screw trajectory."""

        for panel, control in (
            (self.axial, self.axial_angle_control),
            (self.sagittal, self.sagittal_angle_control),
        ):
            widget = panel.vtk_widget

            if widget.width() <= 0 or widget.height() <= 0:
                continue

            screw_line = self._screw_screen_line(panel)

            control_w = control.width()
            control_h = control.height()

            margin = 12

            # Keep roughly the same vertical region as the original controller.
            preferred_y = max(
                margin,
                widget.height() // 2 - control_h - 48,
            )

            center_x = (widget.width() - control_w) // 2
            right_x = widget.width() - control_w - margin
            bottom_y = widget.height() - control_h - margin

            # Ordered from most desirable to least desirable.
            candidates = [
                # Original-style center position.
                (center_x, preferred_y),

                # Move horizontally first. This is especially useful for
                # the axial view where the screw is usually near the center.
                (margin, preferred_y),
                (right_x, preferred_y),

                # Upper positions.
                (center_x, margin),
                (margin, margin),
                (right_x, margin),

                # Lower positions as fallback.
                (center_x, bottom_y),
                (margin, bottom_y),
                (right_x, bottom_y),
            ]

            chosen = None

            for x, y in candidates:
                x = max(
                    margin,
                    min(x, widget.width() - control_w - margin),
                )
                y = max(
                    margin,
                    min(y, widget.height() - control_h - margin),
                )

                control_rect = QRectF(
                    float(x),
                    float(y),
                    float(control_w),
                    float(control_h),
                )

                if not self._control_intersects_screw(
                    control_rect,
                    screw_line,
                ):
                    chosen = (x, y)
                    break

            # Extremely unlikely fallback:
            # use the position farthest from the screw.
            if chosen is None:
                chosen = self._farthest_control_position(
                    panel,
                    candidates,
                    control_w,
                    control_h,
                    margin,
                    screw_line,
                )

            x, y = int(chosen[0]), int(chosen[1])
            moved = control.pos() != QPoint(x, y)
            background_changed = self._update_angle_control_background(
                panel, control, x, y
            )

            if moved or background_changed:
                control.hide()
            control.move(x, y)
            if moved or background_changed:
                panel.render()
            # The Qt template stays hidden; VTK renders its complete RGBA image.

    def _control_intersects_screw(
        self,
        control_rect: QRectF,
        screw_line: QLineF | None,
    ) -> bool:
        """Return True if a control would obscure the visible screw."""

        if screw_line is None:
            return False

        # Extra clearance around the controller so it does not sit directly
        # against the screw even when there is technically no intersection.
        clearance = 22.0

        protected_rect = control_rect.adjusted(
            -clearance,
            -clearance,
            clearance,
            clearance,
        )

        p1 = screw_line.p1()
        p2 = screw_line.p2()

        # Endpoint inside controller area.
        if protected_rect.contains(p1):
            return True

        if protected_rect.contains(p2):
            return True

        # Test screw line against all four sides of the protected rectangle.
        edges = (
            QLineF(
                protected_rect.topLeft(),
                protected_rect.topRight(),
            ),
            QLineF(
                protected_rect.topRight(),
                protected_rect.bottomRight(),
            ),
            QLineF(
                protected_rect.bottomRight(),
                protected_rect.bottomLeft(),
            ),
            QLineF(
                protected_rect.bottomLeft(),
                protected_rect.topLeft(),
            ),
        )

        for edge in edges:
            intersection_type, _point = screw_line.intersects(edge)

            if (
                intersection_type
                == QLineF.IntersectionType.BoundedIntersection
            ):
                return True

        return False

    def _screw_screen_line(
        self,
        panel,
    ) -> QLineF | None:
        """Return the currently active screw as a line in Qt widget coordinates."""

        plan = self._active_plan

        if plan is None:
            return None

        axes = panel.reslice.GetResliceAxes()

        if axes is None:
            return None

        inverse = vtk.vtkMatrix4x4()
        vtk.vtkMatrix4x4.Invert(axes, inverse)

        entry_local = self._project_patient_to_slice(
            inverse,
            plan.entry_point,
        )

        endpoint_local = self._project_patient_to_slice(
            inverse,
            plan.endpoint,
        )

        entry_screen = self._slice_to_widget_point(
            panel,
            entry_local,
        )

        endpoint_screen = self._slice_to_widget_point(
            panel,
            endpoint_local,
        )

        if entry_screen is None or endpoint_screen is None:
            return None

        return QLineF(
            entry_screen,
            endpoint_screen,
        )

    @staticmethod
    def _slice_to_widget_point(
        panel,
        point: tuple[float, float, float],
    ) -> QPointF | None:
        """Convert a VTK slice-space point into Qt widget coordinates."""

        renderer = panel.renderer
        widget = panel.vtk_widget

        renderer.SetWorldPoint(
            float(point[0]),
            float(point[1]),
            float(point[2]),
            1.0,
        )

        renderer.WorldToDisplay()

        display = renderer.GetDisplayPoint()

        if display is None:
            return None

        render_window = widget.GetRenderWindow()
        render_width, render_height = render_window.GetSize()

        if render_width <= 0 or render_height <= 0:
            return None

        # VTK uses bottom-left origin.
        # Qt widgets use top-left origin.
        x = (
            float(display[0])
            * float(widget.width())
            / float(render_width)
        )

        y_from_bottom = (
            float(display[1])
            * float(widget.height())
            / float(render_height)
        )

        y = float(widget.height()) - y_from_bottom

        return QPointF(x, y)

    def _farthest_control_position(
        self,
        panel,
        candidates,
        control_w: int,
        control_h: int,
        margin: int,
        screw_line: QLineF | None,
    ) -> tuple[int, int]:
        """Choose the candidate whose center is farthest from the screw."""

        if screw_line is None:
            return candidates[0]

        p1 = screw_line.p1()
        p2 = screw_line.p2()

        screw_mid = QPointF(
            (p1.x() + p2.x()) / 2.0,
            (p1.y() + p2.y()) / 2.0,
        )

        best_position = candidates[0]
        best_distance_sq = -1.0

        for x, y in candidates:
            x = max(
                margin,
                min(x, panel.vtk_widget.width() - control_w - margin),
            )

            y = max(
                margin,
                min(y, panel.vtk_widget.height() - control_h - margin),
            )

            cx = x + control_w / 2.0
            cy = y + control_h / 2.0

            dx = cx - screw_mid.x()
            dy = cy - screw_mid.y()

            distance_sq = dx * dx + dy * dy

            if distance_sq > best_distance_sq:
                best_distance_sq = distance_sq
                best_position = (x, y)

        return best_position

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_angle_controls()

    def _on_left_click(self, panel) -> None:
        if not self._marking_entry or self._segmentation is None:
            return
        x, y = panel.interactor.GetEventPosition()
        local = self._display_to_slice(panel.renderer, float(x), float(y))
        if local is None or not self._point_is_on_slice_image(panel, local):
            return
        axes = panel.reslice.GetResliceAxes()
        if axes is None:
            return
        patient = axes.MultiplyPoint((float(local[0]), float(local[1]), 0.0, 1.0))
        point = (float(patient[0]), float(patient[1]), float(patient[2]))
        self.set_pending_entry_point(point)
        self._marking_entry = False
        self.begin_entry_point_marking(False)
        self.entry_point_picked.emit(point)

    @staticmethod
    def _display_to_slice(
        renderer: vtk.vtkRenderer,
        x: float,
        y: float,
    ) -> tuple[float, float, float] | None:
        """Intersect a display-coordinate ray with the rendered MPR plane (Z=0)."""

        ray_points: list[np.ndarray] = []
        for depth in (0.0, 1.0):
            renderer.SetDisplayPoint(float(x), float(y), depth)
            renderer.DisplayToWorld()
            homogeneous = np.asarray(renderer.GetWorldPoint(), dtype=float)
            if abs(float(homogeneous[3])) < 1e-12:
                return None
            ray_points.append(homogeneous[:3] / homogeneous[3])

        start, end = ray_points
        dz = float(end[2] - start[2])
        if abs(dz) < 1e-12:
            return None
        fraction = -float(start[2]) / dz
        point = start + fraction * (end - start)
        return float(point[0]), float(point[1]), 0.0

    @staticmethod
    def _point_is_on_slice_image(panel, point: tuple[float, float, float]) -> bool:
        origin = panel.reslice.GetOutputOrigin()
        spacing = panel.reslice.GetOutputSpacing()
        extent = panel.reslice.GetOutputExtent()
        x_min = origin[0] + extent[0] * spacing[0]
        x_max = origin[0] + extent[1] * spacing[0]
        y_min = origin[1] + extent[2] * spacing[1]
        y_max = origin[1] + extent[3] * spacing[1]
        epsilon = 1e-6
        return (
            min(x_min, x_max) - epsilon <= point[0] <= max(x_min, x_max) + epsilon
            and min(y_min, y_max) - epsilon <= point[1] <= max(y_min, y_max) + epsilon
        )

    def _center_panel_camera(self, panel, patient_point: np.ndarray, scale: float) -> None:
        axes = panel.reslice.GetResliceAxes()
        if axes is None:
            return
        inverse = vtk.vtkMatrix4x4()
        vtk.vtkMatrix4x4.Invert(axes, inverse)
        local = inverse.MultiplyPoint(
            (float(patient_point[0]), float(patient_point[1]), float(patient_point[2]), 1.0)
        )
        camera = panel.renderer.GetActiveCamera()
        old_focal = np.asarray(camera.GetFocalPoint(), dtype=float)
        old_position = np.asarray(camera.GetPosition(), dtype=float)
        view_offset = old_position - old_focal
        new_focal = np.array([local[0], local[1], 0.0], dtype=float)
        camera.SetFocalPoint(*new_focal)
        camera.SetPosition(*(new_focal + view_offset))
        camera.ParallelProjectionOn()
        camera.SetParallelScale(float(scale))
        panel.renderer.ResetCameraClippingRange()

    def _refresh_all_overlays(self) -> None:
        for panel in self.mpr_views:
            self._refresh_mpr_overlay(panel)
        self._position_angle_controls()
        self._refresh_three_d_overlays()

    def _clear_mpr_overlays(self) -> None:
        for panel in self.mpr_views:
            for actor in self._mpr_overlay_actors[panel]:
                panel.renderer.RemoveViewProp(actor)
            self._mpr_overlay_actors[panel].clear()
            panel.render()

    def _refresh_mpr_overlay(self, panel) -> None:
        for actor in self._mpr_overlay_actors[panel]:
            panel.renderer.RemoveViewProp(actor)
        self._mpr_overlay_actors[panel].clear()

        axes = panel.reslice.GetResliceAxes()
        if axes is None:
            return
        inverse = vtk.vtkMatrix4x4()
        vtk.vtkMatrix4x4.Invert(axes, inverse)

        pending_actor = None
        if self._pending_entry_point is not None:
            pending = self._project_patient_to_slice(inverse, self._pending_entry_point)
            pending_marker = vtk.vtkRegularPolygonSource()
            pending_marker.SetNumberOfSides(4)
            pending_marker.SetRadius(3.2)
            pending_marker.SetCenter(pending[0], pending[1], 0.18)
            pending_marker.GeneratePolygonOff()
            pending_mapper = vtk.vtkPolyDataMapper()
            pending_mapper.SetInputConnection(pending_marker.GetOutputPort())
            pending_actor = vtk.vtkActor()
            pending_actor.SetMapper(pending_mapper)
            pending_actor.GetProperty().SetColor(1.0, 0.76, 0.15)
            pending_actor.GetProperty().SetLineWidth(3.0)
            pending_actor.PickableOff()
            panel.renderer.AddActor(pending_actor)
            self._mpr_overlay_actors[panel].append(pending_actor)

        plan = self._active_plan
        if plan is None:
            panel.render()
            return

        section, outline = screw_slice_intersection(plan, axes)
        # Draw only the envelope touching this slice, without projected guides.
        for geometry, opacity, depth in ((section, 0.25, 0.02), (outline, 1.0, 0.03)):
            if geometry.GetNumberOfCells() == 0:
                continue
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(geometry)
            mapper.ScalarVisibilityOff()
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            # Display-only offset avoids z-fighting with the CT slice.
            actor.SetPosition(0, 0, depth)
            actor.GetProperty().SetColor(0.20, 0.78, 1.0)
            actor.GetProperty().SetOpacity(opacity)
            actor.GetProperty().SetLineWidth(2.0)
            actor.GetProperty().LightingOff()
            actor.PickableOff()
            panel.renderer.AddActor(actor)
            self._mpr_overlay_actors[panel].append(actor)
        panel.render()

    @staticmethod
    def _project_patient_to_slice(
        inverse: vtk.vtkMatrix4x4,
        point: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        local = inverse.MultiplyPoint((float(point[0]), float(point[1]), float(point[2]), 1.0))
        return float(local[0]), float(local[1]), float(local[2])

    def _clear_three_d_overlays(self) -> None:
        for actor in self._three_d_actors:
            self.three_d.renderer.RemoveViewProp(actor)
        self._three_d_actors.clear()
        self.three_d.vtk_widget.GetRenderWindow().Render()

    def _refresh_three_d_overlays(self) -> None:
        self._clear_three_d_overlays()
        plan = self._active_plan
        if plan is not None:
            body = self._screw_actor(
                plan,
                color=(0.20, 0.78, 1.0),
                opacity=1.0,
            )
            self.three_d.renderer.AddActor(body)
            # Default planning orientation:
            # keep the tulip groove approximately superior-inferior (+Z in LPS),
            # while remaining perpendicular to the screw shank.
            shank = np.asarray(plan.direction, dtype=float)
            shank /= np.linalg.norm(shank)

            vertical = np.array([0.0, 0.0, 1.0], dtype=float)

            slot_direction = vertical - shank * np.dot(vertical, shank)

            if np.linalg.norm(slot_direction) < 1e-8:
                # Extremely unusual fallback if the screw is nearly vertical.
                slot_direction = np.array([0.0, 1.0, 0.0], dtype=float)
                slot_direction -= shank * np.dot(slot_direction, shank)

            slot_direction /= np.linalg.norm(slot_direction)

            tulip_actors = self._tulip_actors(
                plan,
                color=(1.0, 0.70, 0.16),
                opacity=1.0,
                slot_direction=slot_direction,
            )
            for actor in tulip_actors:
                self.three_d.renderer.AddActor(actor)
            self._three_d_actors.extend((body, *tulip_actors))
        self.three_d.renderer.ResetCameraClippingRange()
        self.three_d.vtk_widget.GetRenderWindow().Render()

    @staticmethod
    def _cylinder_actor(
        start: np.ndarray,
        end: np.ndarray,
        *,
        radius: float,
        color: tuple[float, float, float],
        opacity: float,
    ) -> vtk.vtkActor:
        vector = end - start
        length = float(np.linalg.norm(vector))
        if length < 1e-6:
            length = 0.01
            vector = np.array([0.0, 1.0, 0.0])
        direction = vector / length
        center = (start + end) / 2.0

        source = vtk.vtkCylinderSource()
        source.SetRadius(float(radius))
        source.SetHeight(length)
        source.SetResolution(28)
        source.CappingOn()

        y_axis = np.array([0.0, 1.0, 0.0])
        dot = float(np.clip(np.dot(y_axis, direction), -1.0, 1.0))
        angle = float(np.degrees(np.arccos(dot)))
        axis = np.cross(y_axis, direction)
        axis_norm = float(np.linalg.norm(axis))
        if axis_norm < 1e-8:
            axis = np.array([1.0, 0.0, 0.0])
        else:
            axis /= axis_norm

        transform = vtk.vtkTransform()
        transform.PostMultiply()
        if abs(angle) > 1e-6:
            transform.RotateWXYZ(angle, float(axis[0]), float(axis[1]), float(axis[2]))
        transform.Translate(float(center[0]), float(center[1]), float(center[2]))

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.SetUserTransform(transform)
        actor.GetProperty().SetColor(*color)
        actor.GetProperty().SetOpacity(float(opacity))
        actor.GetProperty().SetSpecular(0.25)
        actor.PickableOff()
        return actor

    @staticmethod
    def _screw_actor(plan: ScrewPlan, *, color, opacity: float) -> vtk.vtkActor:
        return make_screw_actor(
            plan.diameter_mm, plan.length_mm, plan.entry_point, plan.direction,
            color=color, opacity=opacity,
        )

    @staticmethod
    def _tulip_actors(
        plan: ScrewPlan,
        *,
        color: tuple[float, float, float],
        opacity: float,
        slot_direction: tuple[float, float, float] | np.ndarray | None = None,
    ) -> list[vtk.vtkActor]:
        return [make_tulip_actor(
            plan.entry_point, plan.direction, slot_direction, color=color, opacity=opacity,
        )]
