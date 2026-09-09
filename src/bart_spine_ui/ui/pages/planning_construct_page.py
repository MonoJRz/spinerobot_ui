from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import vtk
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...planning.collision import ScrewCollision, collisions_for_key, find_screw_collisions
from ...planning.models import Side
from ...planning.rod import (
    FIT_CAUTION_MM,
    FIT_WARNING_MM,
    RodPlan,
    build_rod_plan,
)
from ...planning.service import LEVEL_ORDER
from .planning_page import PlanningPage as BasePlanningPage


class ConstructReviewWidget(QFrame):
    """Full-width construct-review UI shown after the final screw is accepted."""

    back_requested = Signal()
    confirm_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConstructReview")
        self._three_d_view: QWidget | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        header = QFrame()
        header.setObjectName("ConstructHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("CONSTRUCT REVIEW")
        title.setObjectName("ConstructTitle")
        subtitle = QLabel("Review bilateral screw-head alignment and planned rod contour before confirmation")
        subtitle.setObjectName("ConstructSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)
        self.mode_badge = QLabel("RESEARCH PLANNING")
        self.mode_badge.setObjectName("ResearchBadge")
        self.mode_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.mode_badge)
        root.addWidget(header)

        self.collision_banner = QLabel("")
        self.collision_banner.setObjectName("CollisionBanner")
        self.collision_banner.setWordWrap(True)
        self.collision_banner.hide()
        root.addWidget(self.collision_banner)

        body = QHBoxLayout()
        body.setSpacing(10)

        self.level_card = QFrame()
        self.level_card.setObjectName("ConstructCard")
        self.level_card.setFixedWidth(215)
        level_layout = QVBoxLayout(self.level_card)
        level_layout.setContentsMargins(14, 14, 14, 14)
        level_layout.setSpacing(10)
        level_title = QLabel("LEVELS")
        level_title.setObjectName("ConstructSectionTitle")
        level_layout.addWidget(level_title)
        level_rule = QFrame()
        level_rule.setObjectName("ConstructRule")
        level_layout.addWidget(level_rule)
        self.level_grid = QGridLayout()
        self.level_grid.setHorizontalSpacing(12)
        self.level_grid.setVerticalSpacing(10)
        level_layout.addLayout(self.level_grid)
        level_layout.addStretch(1)
        note = QLabel("● accepted screw\n○ not accepted")
        note.setObjectName("ConstructHint")
        level_layout.addWidget(note)
        body.addWidget(self.level_card)

        self.three_d_card = QFrame()
        self.three_d_card.setObjectName("Construct3DCard")
        self.three_d_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_layout = QVBoxLayout(self.three_d_card)
        center_layout.setContentsMargins(8, 8, 8, 8)
        center_layout.setSpacing(7)
        view_header = QHBoxLayout()
        view_label = QLabel("3D CONSTRUCT")
        view_label.setObjectName("ConstructSectionTitle")
        view_header.addWidget(view_label)
        view_header.addStretch(1)
        legend = QLabel("SCREWS  •  LEFT ROD  •  RIGHT ROD")
        legend.setObjectName("ConstructLegend")
        view_header.addWidget(legend)
        center_layout.addLayout(view_header)
        self.three_d_host = QVBoxLayout()
        self.three_d_host.setContentsMargins(0, 0, 0, 0)
        self.three_d_host.setSpacing(0)
        center_layout.addLayout(self.three_d_host, 1)
        body.addWidget(self.three_d_card, 1)

        rod_scroll = QScrollArea()
        rod_scroll.setObjectName("RodReviewScroll")
        rod_scroll.setWidgetResizable(True)
        rod_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rod_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rod_scroll.setFixedWidth(330)
        rod_content = QWidget()
        rod_content.setObjectName("RodReviewContent")
        rod_layout = QVBoxLayout(rod_content)
        rod_layout.setContentsMargins(0, 0, 0, 0)
        rod_layout.setSpacing(10)
        self.left_rod = _RodCard("LEFT ROD")
        self.right_rod = _RodCard("RIGHT ROD")
        rod_layout.addWidget(self.left_rod)
        rod_layout.addWidget(self.right_rod)
        rod_layout.addStretch(1)
        rod_scroll.setWidget(rod_content)
        body.addWidget(rod_scroll)
        root.addLayout(body, 1)

        footer = QFrame()
        footer.setObjectName("ConstructFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 10, 12, 10)
        self.back_button = QPushButton("←  BACK TO SCREWS")
        self.back_button.setObjectName("ConstructBack")
        self.confirm_button = QPushButton("CONFIRM CONSTRUCT  →")
        self.confirm_button.setObjectName("ConstructConfirm")
        footer_layout.addWidget(self.back_button)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.confirm_button)
        root.addWidget(footer)

        self.back_button.clicked.connect(self.back_requested)
        self.confirm_button.clicked.connect(self.confirm_requested)
        self.setStyleSheet(_CONSTRUCT_STYLE)

    def attach_three_d(self, view: QWidget) -> None:
        self._three_d_view = view
        view.setMinimumHeight(430)
        view.setMaximumHeight(16777215)
        self.three_d_host.addWidget(view, 1)
        view.show()

    def set_construct(
        self,
        levels: list[str],
        accepted: set[tuple[str, Side]],
        rods: Mapping[Side, RodPlan | None],
        collisions: list[ScrewCollision] | None = None,
    ) -> None:
        self._populate_levels(levels, accepted)
        self.left_rod.set_plan(rods.get("left"))
        self.right_rod.set_plan(rods.get("right"))
        self.set_confirmed(False)
        self.set_collisions(collisions or [])

    def set_collisions(self, collisions: list[ScrewCollision]) -> None:
        if not collisions:
            self.collision_banner.hide()
            self.mode_badge.setText("RESEARCH PLANNING")
            self.confirm_button.setEnabled(True)
            return
        rows = []
        for collision in collisions[:4]:
            a = f"{collision.first_key[0]} {collision.first_key[1][0].upper()}"
            b = f"{collision.second_key[0]} {collision.second_key[1][0].upper()}"
            rows.append(f"{a} ↔ {b}: {collision.overlap_mm:.1f} mm shaft overlap")
        suffix = f"  (+{len(collisions)-4} more)" if len(collisions) > 4 else ""
        self.collision_banner.setText(
            "⚠ SCREW COLLISION — adjust trajectories before confirming: "
            + "   •   ".join(rows) + suffix
        )
        self.collision_banner.show()
        self.mode_badge.setText("COLLISION DETECTED")
        self.confirm_button.setEnabled(False)

    def set_confirmed(self, confirmed: bool) -> None:
        if confirmed:
            self.confirm_button.setText("✓  CONSTRUCT CONFIRMED")
            self.confirm_button.setEnabled(False)
        else:
            self.confirm_button.setText("CONFIRM CONSTRUCT  →")
            self.confirm_button.setEnabled(not self.collision_banner.isVisible())

    def _populate_levels(
        self,
        levels: list[str],
        accepted: set[tuple[str, Side]],
    ) -> None:
        while self.level_grid.count():
            item = self.level_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for column, text in ((1, "L"), (2, "R")):
            label = QLabel(text)
            label.setObjectName("ConstructColumnHeader")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.level_grid.addWidget(label, 0, column)

        for row, level in enumerate(levels, start=1):
            label = QLabel(level)
            label.setObjectName("ConstructLevel")
            self.level_grid.addWidget(label, row, 0)
            for column, side in ((1, "left"), (2, "right")):
                dot = QLabel("●" if (level, side) in accepted else "○")
                dot.setObjectName("ConstructAccepted" if (level, side) in accepted else "ConstructPending")
                dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.level_grid.addWidget(dot, row, column)


class _RodCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("RodCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 13, 14, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("RodTitle")
        layout.addWidget(title_label)

        self.spec = QLabel("—")
        self.spec.setObjectName("RodSpec")
        layout.addWidget(self.spec)

        rule = QFrame()
        rule.setObjectName("ConstructRule")
        layout.addWidget(rule)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self.length = self._metric(grid, 0, "Selected length")
        self.max_gap = self._metric(grid, 1, "Max tulip reduction")
        self.radius = self._metric(grid, 2, "Min bend radius")
        layout.addLayout(grid)

        self.status = QLabel("NO ROD")
        self.status.setObjectName("RodStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

        self.warning = QLabel("")
        self.warning.setObjectName("RodWarning")
        self.warning.setWordWrap(True)
        self.warning.hide()
        layout.addWidget(self.warning)

    @staticmethod
    def _metric(grid: QGridLayout, row: int, key: str) -> QLabel:
        left = QLabel(key)
        left.setObjectName("RodMetricKey")
        value = QLabel("—")
        value.setObjectName("RodMetricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(left, row, 0)
        grid.addWidget(value, row, 1)
        return value

    def set_plan(self, plan: RodPlan | None) -> None:
        if plan is None:
            self.spec.setText("Need ≥2 screws on this side")
            for label in (
                self.length,
                self.max_gap,
                self.radius,
            ):
                label.setText("—")
            self.status.setText("NO ROD")
            self.status.setStyleSheet("color:#8ea9ba; border-color:#345063;")
            self.warning.hide()
            return

        self.spec.setText(f"{plan.material}  ·  Ø{plan.diameter_mm:.1f} mm")
        self.length.setText(f"{plan.length_mm:.0f} mm")
        self.max_gap.setText(f"{plan.max_seat_gap_mm:.1f} mm")
        self.radius.setText(
            f"{plan.minimum_bend_radius_mm:.0f} mm"
            if plan.minimum_bend_radius_mm is not None
            else "Straight"
        )
        self.status.setText(f"●  {plan.fit_state}")
        if plan.max_seat_gap_mm > FIT_WARNING_MM:
            self.status.setStyleSheet("color:#ff8b91; border-color:#8f4149; background:#3b2025;")
        elif plan.max_seat_gap_mm > FIT_CAUTION_MM:
            self.status.setStyleSheet("color:#f1c96b; border-color:#846b35; background:#342d1e;")
        else:
            self.status.setStyleSheet("color:#7ee787; border-color:#39704a; background:#173326;")

        if plan.warning:
            self.warning.setText("▲  " + plan.warning)
            self.warning.show()
        else:
            self.warning.hide()


class PlanningPage(BasePlanningPage):
    """Existing screw planner plus a full-width post-planning construct review."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.construct_review = ConstructReviewWidget(self)
        self.construct_review.hide()
        self.layout().addWidget(self.construct_review, 1)
        self.construct_review.back_requested.connect(self._back_to_screws)
        self.construct_review.confirm_requested.connect(self._confirm_construct)
        self._rod_plans: dict[Side, RodPlan | None] = {"left": None, "right": None}

    def _activate_target(self) -> None:
        super()._activate_target()
        self._refresh_current_collision_status()

    def _entry_point_picked(self, point_lps) -> None:
        super()._entry_point_picked(point_lps)
        self._refresh_current_collision_status()

    def _trajectory_angles_changed(
        self,
        axial_angle_deg: float,
        sagittal_angle_deg: float,
    ) -> None:
        super()._trajectory_angles_changed(axial_angle_deg, sagittal_angle_deg)
        self._refresh_current_collision_status()

    def _update_current_dimensions(
        self,
        *,
        diameter_mm: float | None = None,
        length_mm: float | None = None,
    ) -> None:
        super()._update_current_dimensions(
            diameter_mm=diameter_mm,
            length_mm=length_mm,
        )
        self._refresh_current_collision_status()

    def _refresh_current_collision_status(self) -> None:
        if not self._queue or not hasattr(self, "workspace"):
            return
        key = self._queue[self._target_index]
        if key not in self.plans:
            return
        collisions = collisions_for_key(self.plans, key)
        if not collisions:
            return

        other_rows = []
        for collision in collisions:
            other = collision.second_key if collision.first_key == key else collision.first_key
            other_rows.append(f"{other[0]} {other[1]} ({collision.overlap_mm:.1f} mm overlap)")
        self.left_sidebar.set_status(
            "⚠ Screw collision with " + ", ".join(other_rows) + ". Adjust angle or length.",
            "error",
        )
        self.status_changed.emit(f"Screw collision — {key[0]} {key[1]}")
        self._render_collision_context(key, collisions)

    def _render_collision_context(
        self,
        active_key: tuple[str, Side],
        collisions: list[ScrewCollision],
    ) -> None:
        """Overlay conflicting screws in red beside the active planning screw."""

        renderer = self.workspace.three_d.renderer
        shown: set[tuple[str, Side]] = set()
        for collision in collisions:
            other_key = (
                collision.second_key
                if collision.first_key == active_key
                else collision.first_key
            )
            if other_key in shown:
                continue
            shown.add(other_key)
            plan = self.plans.get(other_key)
            if plan is None:
                continue
            entry = np.asarray(plan.entry_point, dtype=float)
            endpoint = np.asarray(plan.endpoint, dtype=float)
            body = self.workspace._cylinder_actor(
                entry,
                endpoint,
                radius=max(0.5, plan.diameter_mm / 2.0),
                color=(0.95, 0.25, 0.30),
                opacity=0.82,
            )
            tulip_actors = self.workspace._tulip_actors(
                plan,
                color=(1.0, 0.34, 0.25),
                opacity=0.90,
            )
            renderer.AddActor(body)
            for actor in tulip_actors:
                renderer.AddActor(actor)
            self.workspace._three_d_actors.extend((body, *tulip_actors))
        renderer.ResetCameraClippingRange()
        self.workspace.three_d.vtk_widget.GetRenderWindow().Render()

    def _accept_and_next(self) -> None:
        # Refuse acceptance when the current screw shaft geometrically intersects
        # another planned screw. This is a geometry guard, not a clinical clearance rule.
        if self._queue:
            key = self._queue[self._target_index]
            collisions = collisions_for_key(self.plans, key)
            if collisions:
                details = []
                for collision in collisions:
                    other = collision.second_key if collision.first_key == key else collision.first_key
                    details.append(
                        f"{other[0]} {other[1]} (shaft overlap {collision.overlap_mm:.1f} mm)"
                    )
                message = (
                    f"{key[0]} {key[1]} intersects " + ", ".join(details)
                    + ". Adjust the trajectory or screw length before accepting."
                )
                self.left_sidebar.set_status(message, "error")
                self.status_changed.emit("Screw collision detected — acceptance blocked")
                QMessageBox.warning(self, "Screw collision", message)
                return

        # Let the existing planner perform its normal accept/save/navigation logic,
        # then decide whether the whole construct is complete.
        super()._accept_and_next()
        if self._all_screws_accepted():
            self._show_construct_review()

    def _all_screws_accepted(self) -> bool:
        return bool(self._queue) and all(
            key in self.plans and key in self.accepted for key in self._queue
        )

    def _show_construct_review(self) -> None:
        if not self.plans:
            return
        self.workspace.begin_entry_point_marking(False)
        self.left_sidebar.set_marking(False)

        self._rod_plans = {
            "left": build_rod_plan(self.plans, "left"),
            "right": build_rod_plan(self.plans, "right"),
        }
        collisions = find_screw_collisions(self.plans)

        # Give the review screen the existing VTK view. Adding a QWidget to a new
        # layout reparents it, so there is still only one OpenGL/VTK context.
        self.left_sidebar.hide()
        self.workspace.hide()
        self.screw_table.hide()
        self.construct_review.attach_three_d(self.workspace.three_d)
        self.construct_review.set_construct(
            self.levels_of_interest,
            self.accepted,
            self._rod_plans,
            collisions,
        )
        self.construct_review.show()
        self._restore_review_segmentation()
        self._render_construct()
        self.status_changed.emit("Construct review — inspect bilateral rod fit and screw-head alignment")

    def _back_to_screws(self) -> None:
        self.construct_review.hide()
        self.left_sidebar.set_three_d_view(self.workspace.three_d)
        self.left_sidebar.show()
        self.workspace.show()
        self.screw_table.show()
        if self._queue:
            key = self._queue[self._target_index]
            self.workspace.set_plans(
                self.plans,
                active_key=key if key in self.plans else None,
            )
            if key in self.plans:
                self.workspace.focus_three_d_level(key[0], key[1])
        self.status_changed.emit("Returned to screw planning")

    def _confirm_construct(self) -> None:
        collisions = find_screw_collisions(self.plans)
        if collisions:
            self.construct_review.set_collisions(collisions)
            QMessageBox.warning(
                self,
                "Screw collision",
                "Construct confirmation is blocked because one or more planned screw shafts intersect. "
                "Return to screw planning and adjust the trajectories.",
            )
            return
        self.construct_review.set_confirmed(True)
        self.status_changed.emit(
            "Construct confirmed — rod geometry values are research-prototype planning aids"
        )

    def _restore_review_segmentation(self) -> None:
        """Restore all planned vertebrae after per-level screw focus replaced the surface."""

        panel = self.workspace.three_d
        full_surface = getattr(panel, "_full_segmentation_surface", None)
        segmentation = self.current_segmentation
        if full_surface is None or segmentation is None:
            return

        requested_labels = [
            int(label)
            for label, name in segmentation.labels.items()
            if name in set(self.levels_of_interest)
        ]
        if not requested_labels:
            requested_labels = [int(label) for label in segmentation.labels]

        append = vtk.vtkAppendPolyData()
        for label in requested_labels:
            threshold = vtk.vtkThreshold()
            threshold.SetInputData(full_surface)
            threshold.SetInputArrayToProcess(
                0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS, "VertebraLabel"
            )
            threshold.SetLowerThreshold(float(label))
            threshold.SetUpperThreshold(float(label))
            threshold.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_BETWEEN)
            geometry = vtk.vtkGeometryFilter()
            geometry.SetInputConnection(threshold.GetOutputPort())
            geometry.Update()
            piece = vtk.vtkPolyData()
            piece.ShallowCopy(geometry.GetOutput())
            if piece.GetNumberOfPoints() > 0:
                append.AddInputData(piece)

        append.Update()
        review_surface = vtk.vtkPolyData()
        review_surface.ShallowCopy(append.GetOutput())
        panel.segmentation_contour.RemoveAllInputs()
        panel.segmentation_contour.AddInputData(review_surface)
        panel.segmentation_contour.Update()
        panel.segmentation_actor.GetProperty().SetOpacity(0.38)
        panel.segmentation_actor.ForceOpaqueOff()
        panel.segmentation_actor.SetVisibility(True)
        panel.volume_actor.SetVisibility(False)

    def _render_construct(self) -> None:
        # PlanningWorkspace normally displays only the active screw. In this mode
        # intentionally use its overlay actor collection to render the full construct.
        self.workspace._clear_three_d_overlays()
        renderer = self.workspace.three_d.renderer

        screw_actors: list[vtk.vtkProp] = []
        collisions = find_screw_collisions(self.plans)
        collision_keys = {
            key
            for collision in collisions
            for key in (collision.first_key, collision.second_key)
        }
        ordered_items = sorted(
            self.plans.items(),
            key=lambda item: (
                LEVEL_ORDER.index(item[1].level),
                0 if item[1].side == "left" else 1,
            ),
        )
        ordered_plans = [plan for _key, plan in ordered_items]
        tulip_slot_directions = {
            (level, side): direction
            for side, rod in self._rod_plans.items()
            if rod is not None
            for level, direction in rod.tulip_slot_directions_lps.items()
        }
        for key, plan in ordered_items:
            entry = np.asarray(plan.entry_point, dtype=float)
            endpoint = np.asarray(plan.endpoint, dtype=float)
            body = self.workspace._cylinder_actor(
                entry,
                endpoint,
                radius=max(0.5, plan.diameter_mm / 2.0),
                color=(0.95, 0.30, 0.34) if key in collision_keys else (0.64, 0.78, 0.86),
                opacity=1.0,
            )
            tulip_actors = self.workspace._tulip_actors(
                plan,
                color=(1.00, 0.36, 0.25) if key in collision_keys else (0.95, 0.66, 0.20),
                opacity=1.0,
                slot_direction=tulip_slot_directions.get(key),
            )
            renderer.AddActor(body)
            for actor in tulip_actors:
                renderer.AddActor(actor)
            screw_actors.extend((body, *tulip_actors))

        rod_actors: list[vtk.vtkProp] = []
        rod_colors = {
            "left": (0.18, 0.78, 1.00),
            "right": (0.38, 0.86, 0.58),
        }
        for side in ("left", "right"):
            rod = self._rod_plans.get(side)
            if rod is None:
                continue
            centerline = np.asarray(rod.centerline_lps_mm, dtype=float)
            actor = self._tube_actor(
                centerline,
                radius=rod.diameter_mm / 2.0,
                color=rod_colors[side],
            )
            renderer.AddActor(actor)
            rod_actors.append(actor)

            # Explicitly visualize the smooth-rod-to-head mismatch at each screw.
            for level in rod.levels:
                gap = rod.seat_gap_mm[level]
                if gap < 0.15:
                    continue
                seat = np.asarray(rod.seat_points_lps_mm[level], dtype=float)
                projection = np.asarray(rod.seat_projection_lps_mm[level], dtype=float)
                color = (
                    (0.92, 0.30, 0.32)
                    if gap > FIT_WARNING_MM
                    else (0.95, 0.72, 0.25)
                    if gap > FIT_CAUTION_MM
                    else (0.42, 0.85, 0.50)
                )
                gap_actor = self.workspace._cylinder_actor(
                    seat,
                    projection,
                    radius=0.35,
                    color=color,
                    opacity=0.95,
                )
                renderer.AddActor(gap_actor)
                rod_actors.append(gap_actor)

        self.workspace._three_d_actors.extend(screw_actors + rod_actors)

        # Frame the planned construct rather than the entire T1-L5 segmentation.
        construct_points: list[np.ndarray] = []
        for plan in ordered_plans:
            construct_points.append(np.asarray(plan.entry_point, dtype=float))
            construct_points.append(np.asarray(plan.endpoint, dtype=float))
        for rod in self._rod_plans.values():
            if rod is not None:
                construct_points.extend(np.asarray(rod.centerline_lps_mm, dtype=float))
        if construct_points:
            cloud = np.vstack(construct_points)
            minimum = cloud.min(axis=0) - 18.0
            maximum = cloud.max(axis=0) + 18.0
            try:
                renderer.ResetCamera(
                    float(minimum[0]), float(maximum[0]),
                    float(minimum[1]), float(maximum[1]),
                    float(minimum[2]), float(maximum[2]),
                )
            except TypeError:
                renderer.ResetCamera()
        else:
            renderer.ResetCamera()
        renderer.ResetCameraClippingRange()
        self.workspace.three_d.vtk_widget.GetRenderWindow().Render()

    @staticmethod
    def _tube_actor(
        points_array: np.ndarray,
        *,
        radius: float,
        color: tuple[float, float, float],
    ) -> vtk.vtkActor:
        vtk_points = vtk.vtkPoints()
        for point in points_array:
            vtk_points.InsertNextPoint(float(point[0]), float(point[1]), float(point[2]))

        polyline = vtk.vtkPolyLine()
        polyline.GetPointIds().SetNumberOfIds(len(points_array))
        for index in range(len(points_array)):
            polyline.GetPointIds().SetId(index, index)

        cells = vtk.vtkCellArray()
        cells.InsertNextCell(polyline)
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(vtk_points)
        polydata.SetLines(cells)

        tube = vtk.vtkTubeFilter()
        tube.SetInputData(polydata)
        tube.SetRadius(float(radius))
        tube.SetNumberOfSides(28)
        tube.CappingOn()
        tube.Update()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(tube.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*color)
        actor.GetProperty().SetSpecular(0.35)
        actor.GetProperty().SetSpecularPower(20.0)
        actor.PickableOff()
        return actor


_CONSTRUCT_STYLE = r"""
QFrame#ConstructReview {
    background: #0b1014;
}
QFrame#ConstructHeader, QFrame#ConstructFooter {
    background: #101820;
    border: 1px solid #294b61;
    border-radius: 8px;
}
QLabel#ConstructTitle {
    color: #eef5f8;
    font-size: 21px;
    font-weight: 900;
    letter-spacing: 1px;
}
QLabel#ConstructSubtitle {
    color: #8fa9b9;
    font-size: 11px;
}
QLabel#CollisionBanner {
    background: #3b2025;
    color: #ff9a9f;
    border: 1px solid #8f4149;
    border-radius: 7px;
    padding: 9px 12px;
    font-size: 11px;
    font-weight: 800;
}
QLabel#ResearchBadge {
    background: #342d1e;
    color: #e8bd5d;
    border: 1px solid #6d5a30;
    border-radius: 12px;
    padding: 5px 10px;
    font-size: 10px;
    font-weight: 800;
}
QFrame#ConstructCard, QFrame#Construct3DCard, QFrame#RodCard {
    background: #141b20;
    border: 1px solid #2b5068;
    border-radius: 8px;
}
QLabel#ConstructSectionTitle, QLabel#RodTitle {
    color: #dce9f0;
    font-size: 14px;
    font-weight: 900;
}
QFrame#ConstructRule {
    background: #294356;
    min-height: 1px;
    max-height: 1px;
}
QLabel#ConstructColumnHeader, QLabel#ConstructHint, QLabel#RodMetricKey {
    color: #8ea9ba;
    font-size: 11px;
}
QLabel#ConstructLevel {
    color: #e4edf1;
    font-size: 13px;
    font-weight: 800;
}
QLabel#ConstructAccepted {
    color: #7ee787;
    font-size: 16px;
}
QLabel#ConstructPending {
    color: #617682;
    font-size: 16px;
}
QLabel#ConstructLegend {
    color: #77a7c2;
    font-size: 10px;
    font-weight: 700;
}
QScrollArea#RodReviewScroll, QWidget#RodReviewContent {
    background: #0b1014;
    border: none;
}
QLabel#RodSpec {
    color: #9fd3ea;
    font-size: 12px;
    font-weight: 800;
}
QLabel#RodMetricValue {
    color: #e5edf1;
    font-size: 12px;
    font-weight: 800;
}
QLabel#RodStatus {
    border: 1px solid #39704a;
    border-radius: 6px;
    padding: 7px 8px;
    font-size: 12px;
    font-weight: 900;
}
QLabel#RodGapDetail {
    color: #a9c0ce;
    font-size: 10px;
}
QLabel#RodWarning {
    color: #e8bd5d;
    font-size: 10px;
}
QPushButton#ConstructBack, QPushButton#ConstructConfirm {
    min-height: 48px;
    min-width: 190px;
    padding: 0 16px;
    border-radius: 7px;
    font-size: 13px;
    font-weight: 900;
}
QPushButton#ConstructBack {
    background: #172b38;
    color: #b9d6e6;
    border: 1px solid #315a72;
}
QPushButton#ConstructBack:hover {
    background: #20445a;
    border-color: #4c83a2;
}
QPushButton#ConstructConfirm {
    background: #123f2b;
    color: #7ee787;
    border: 1px solid #2e7b50;
}
QPushButton#ConstructConfirm:hover {
    background: #1b5a3c;
}
QPushButton#ConstructConfirm:disabled {
    background: #173326;
    color: #7ee787;
    border-color: #39704a;
}
"""
