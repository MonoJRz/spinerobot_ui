from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import vtk
from PySide6.QtCore import Qt, Signal

from ..core import SliceOrientation
from ..imaging.models import MedicalVolume
from ..segmentation import SegmentationVolume
from ..ui.screw_adjustment_overlay import ScrewAdjustmentOverlay
from ..ui.trajectory_touch_overlay import TrajectoryTouchOverlay
from ..visualization import ImagingWorkspace
from .models import ScrewPlan, Side


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
            "AXIAL ANGLE", "↶", "↷", self.axial.vtk_widget
        )
        self.sagittal_angle_control = TrajectoryTouchOverlay(
            "SAGITTAL ANGLE", "↓", "↑", self.sagittal.vtk_widget
        )
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

    def set_plans(
        self,
        plans: Mapping[tuple[str, Side], ScrewPlan],
        *,
        active_key: tuple[str, Side] | None = None,
    ) -> None:
        self._plans = dict(plans)
        self._active_plan = self._plans.get(active_key) if active_key is not None else None
        self._sync_angle_controls()
        self._refresh_all_overlays()

    def set_active_plan(self, plan: ScrewPlan | None) -> None:
        self._active_plan = plan
        if plan is not None:
            self._plans[(plan.level, plan.side)] = plan
        self._sync_angle_controls()
        self._refresh_all_overlays()

    def clear_plans(self) -> None:
        self._plans.clear()
        self._active_plan = None
        self._sync_angle_controls()
        self._clear_mpr_overlays()
        self._clear_three_d_overlays()
        self.screw_overlay.clear_plan()

    def _sync_angle_controls(self) -> None:
        plan = self._active_plan
        self.axial_angle_control.set_angle(plan.axial_angle_deg if plan is not None else None)
        self.sagittal_angle_control.set_angle(
            plan.sagittal_angle_deg if plan is not None else None
        )
        self._position_angle_controls()

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

    def _position_angle_controls(self) -> None:
        for panel, control in (
            (self.axial, self.axial_angle_control),
            (self.sagittal, self.sagittal_angle_control),
        ):
            x = max(10, (panel.vtk_widget.width() - control.width()) // 2)
            y = max(10, panel.vtk_widget.height() // 2 - control.height() - 48)
            control.move(x, y)
            control.raise_()

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

        plan = self._active_plan
        if plan is None:
            panel.render()
            return

        axes = panel.reslice.GetResliceAxes()
        if axes is None:
            return
        inverse = vtk.vtkMatrix4x4()
        vtk.vtkMatrix4x4.Invert(axes, inverse)

        entry = self._project_patient_to_slice(inverse, plan.entry_point)
        endpoint = self._project_patient_to_slice(inverse, plan.endpoint)

        direction = np.asarray(plan.direction, dtype=float)
        guide_start = np.asarray(plan.entry_point, dtype=float) - direction * 70.0
        guide_end = np.asarray(plan.entry_point, dtype=float) + direction * 130.0
        guide_start_local = self._project_patient_to_slice(inverse, tuple(guide_start))
        guide_end_local = self._project_patient_to_slice(inverse, tuple(guide_end))
        guide = vtk.vtkLineSource()
        guide.SetPoint1(guide_start_local[0], guide_start_local[1], 0.08)
        guide.SetPoint2(guide_end_local[0], guide_end_local[1], 0.08)
        guide_mapper = vtk.vtkPolyDataMapper()
        guide_mapper.SetInputConnection(guide.GetOutputPort())
        guide_actor = vtk.vtkActor()
        guide_actor.SetMapper(guide_mapper)
        guide_actor.GetProperty().SetColor(1.0, 0.16, 0.12)
        guide_actor.GetProperty().SetLineWidth(2.0)
        guide_actor.PickableOff()
        panel.renderer.AddActor(guide_actor)

        line = vtk.vtkLineSource()
        line.SetPoint1(entry[0], entry[1], 0.0)
        line.SetPoint2(endpoint[0], endpoint[1], 0.0)
        tube = vtk.vtkTubeFilter()
        tube.SetInputConnection(line.GetOutputPort())
        tube.SetRadius(max(0.7, plan.diameter_mm * 0.22))
        tube.SetNumberOfSides(16)
        tube.CappingOn()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(tube.GetOutputPort())
        body = vtk.vtkActor()
        body.SetMapper(mapper)
        body.GetProperty().SetColor(0.20, 0.78, 1.0)
        body.GetProperty().SetOpacity(0.90)
        body.PickableOff()
        panel.renderer.AddActor(body)

        marker = vtk.vtkRegularPolygonSource()
        marker.SetNumberOfSides(32)
        marker.SetRadius(max(2.0, plan.diameter_mm * 0.7))
        marker.SetCenter(entry[0], entry[1], 0.15)
        marker.GeneratePolygonOff()
        marker_mapper = vtk.vtkPolyDataMapper()
        marker_mapper.SetInputConnection(marker.GetOutputPort())
        entry_actor = vtk.vtkActor()
        entry_actor.SetMapper(marker_mapper)
        entry_actor.GetProperty().SetColor(1.0, 0.78, 0.22)
        entry_actor.GetProperty().SetLineWidth(2.5)
        entry_actor.PickableOff()
        panel.renderer.AddActor(entry_actor)

        self._mpr_overlay_actors[panel].extend((guide_actor, body, entry_actor))
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
            body = self._cylinder_actor(
                np.asarray(plan.entry_point, dtype=float),
                np.asarray(plan.endpoint, dtype=float),
                radius=max(0.5, plan.diameter_mm / 2.0),
                color=(0.20, 0.78, 1.0),
                opacity=1.0,
            )
            direction = np.asarray(plan.direction, dtype=float)
            head_length = max(3.0, plan.diameter_mm * 0.8)
            head_end = np.asarray(plan.entry_point, dtype=float) - direction * head_length
            head = self._cylinder_actor(
                head_end,
                np.asarray(plan.entry_point, dtype=float),
                radius=max(2.5, plan.diameter_mm * 0.85),
                color=(1.0, 0.70, 0.16),
                opacity=1.0,
            )
            self.three_d.renderer.AddActor(body)
            self.three_d.renderer.AddActor(head)
            self._three_d_actors.extend((body, head))
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
