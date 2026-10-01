import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
from PySide6.QtWidgets import QApplication, QLabel

from bart_spine_ui.planning.assessment import ScrewAssessment
from bart_spine_ui.planning.service import LEVEL_ORDER, parse_levels_of_interest
from bart_spine_ui.segmentation.totalsegmentator_service import (
    FULL_SPINE_ROIS,
    TotalSegmentatorService,
    rois_for_case,
)
from bart_spine_ui.ui.pages.planning_construct_page import ConstructReviewWidget
from bart_spine_ui.ui.screw_assessment_panel import DensityStrip
from bart_spine_ui.ui.spine_level_selector import SpineLevelSelector


def test_full_spine_selection_roundtrip():
    app = QApplication.instance() or QApplication([])
    selector = SpineLevelSelector(['L3', 'L5'])
    changed = []
    selector.selection_changed.connect(lambda: changed.append(True))
    selector.buttons['C1'].click()
    selector.buttons['S1'].click()
    selector.buttons['L3'].click()
    assert selector.selected_levels() == ['C1', 'L5', 'S1']
    assert parse_levels_of_interest(', '.join(selector.selected_levels())) == selector.selected_levels()
    assert len(parse_levels_of_interest('C1-S1')) == 25
    assert list(selector.buttons) == list(LEVEL_ORDER)
    assert len(changed) == 3
    assert set(rois_for_case('Spine', selector.selected_levels())) <= set(FULL_SPINE_ROIS)
    assert TotalSegmentatorService._validate_rois(('vertebrae_C1', 'vertebrae_S1')) == (
        'vertebrae_C1', 'vertebrae_S1')
    selector.close()
    app.processEvents()


def test_construct_density_and_rod_controls(tmp_path):
    app = QApplication.instance() or QApplication([])
    review = ConstructReviewWidget()
    review.resize(1350, 850)
    review.attach_three_d(QLabel('3D construct'))
    review.set_construct(['L3'], {('L3','left')}, {})
    result = ScrewAssessment(2.4, 'C', np.array([0., 10., 20.]),
                             np.array([100., 400., np.nan]), np.array([1., 1., 0.]))
    panel = review.assessment_panel
    panel.set_results({('L3', 'left'): result})
    assert not panel.findChildren(DensityStrip)
    panel.hu_confirmed.setChecked(True)
    review.show()
    app.processEvents()
    strips = panel.findChildren(DensityStrip)
    assert len(strips) == 1
    assert strips[0].isVisible()
    toggled = []
    review.rods_toggled.connect(toggled.append)
    review.rods_visible.click()
    assert toggled == [False]
    assert review.grab().save(str(tmp_path/'construct.png'))
    review.close()
    app.processEvents()


def test_touch_hu_legend_and_persistent_tap_readout():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from bart_spine_ui.ui.screw_assessment_panel import ScrewAssessmentPanel, hu_color

    app = QApplication.instance() or QApplication([])
    panel = ScrewAssessmentPanel()
    panel.resize(330, 700)
    result = ScrewAssessment(0, 'A', np.array([0., 10., 20.]),
                             np.array([100., 400., np.nan]), np.array([1., .5, 0.]))
    panel.set_results({('L3', 'left'): result})
    panel.show()
    app.processEvents()
    assert panel.hu_confirmed.height() >= 56
    assert panel.hu_confirmed.width() >= 250
    assert not panel.hu_legend.isVisible()
    QTest.mouseClick(panel.hu_confirmed, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert panel.hu_legend.isVisible()
    assert 'Hide' in panel.hu_confirmed.text()
    strip = panel.findChildren(DensityStrip)[0]
    assert strip.height() >= 56
    QTest.mouseClick(strip, Qt.MouseButton.LeftButton, pos=QPoint(strip.width()//2, 25))
    labels = [label.text() for label in panel.findChildren(QLabel)]
    assert any('400 HU · 10.0 mm' in label and '50%' in label for label in labels)
    assert strip.selected_index == 1
    QTest.keyClick(strip, Qt.Key.Key_End)
    labels = [label.text() for label in panel.findChildren(QLabel)]
    assert any('No sample · 20.0 mm' in label for label in labels)
    # Exact readings remain unbounded even though the fixed display scale clips.
    assert hu_color(-100) == hu_color(0)
    assert hu_color(1500) == hu_color(1000)
    assert hu_color(np.nan) != hu_color(0)
    panel.close()


def test_entry_band_is_fixed_and_has_no_adjustment_controls():
    from PySide6.QtWidgets import QPushButton

    from bart_spine_ui.planning.assessment import DEFAULT_ENTRY_EXCLUSION_MM
    from bart_spine_ui.ui.screw_assessment_panel import ScrewAssessmentPanel

    app = QApplication.instance() or QApplication([])
    panel = ScrewAssessmentPanel()
    assert DEFAULT_ENTRY_EXCLUSION_MM == 5
    assert not hasattr(panel, 'band_plus')
    assert not hasattr(panel, 'band_minus')
    assert [button.text() for button in panel.findChildren(QPushButton)] == ['Show CT values · HU']
    # assert any('First 10 mm excluded' in label.text() for label in panel.findChildren(QLabel))
    panel.close()
    app.processEvents()


def test_worker_uses_fixed_entry_band(monkeypatch):
    from bart_spine_ui.ui.screw_assessment_panel import AssessmentWorker

    observed = []

    def assess(self, plan, volume, *, entry_exclusion_mm):
        observed.append(entry_exclusion_mm)
        return 'result'

    monkeypatch.setattr('bart_spine_ui.ui.screw_assessment_panel.ScrewAssessmentService.assess', assess)
    worker = AssessmentWorker(None, None, {('L3', 'left'): object()})
    results = []
    worker.completed.connect(results.append)
    worker.run()
    assert observed == [10]
    assert results == [{('L3', 'left'): 'result'}]


def test_breach_location_control_distinguishes_depth_from_breach():
    from PySide6.QtWidgets import QPushButton

    from bart_spine_ui.ui.screw_assessment_panel import ScrewAssessmentPanel

    app = QApplication.instance() or QApplication([])
    panel = ScrewAssessmentPanel()
    result = ScrewAssessment(.3, 'B', np.array([0., 20.]), np.array([100., 200.]),
                             np.ones(2), breach_point_lps=(12.3, 20., 30.),
                             bone_point_lps=(12., 20., 30.), breach_depth_mm=15.,
                             voxel_spacing_mm=(.8, .8, 1.))
    panel.set_results({('L3', 'left'): result})
    labels = [label.text() for label in panel.findChildren(QLabel)]
    assert any('0.3 mm' in text for text in labels)
    assert 'At 15.0 mm from entry' in labels
    assert any('Below voxel spacing' in text for text in labels)
    located = []
    panel.locate_breach_requested.connect(located.append)
    button = next(button for button in panel.findChildren(QPushButton) if button.text() == 'Locate breach')
    button.click()
    assert located == [('L3', 'left')]
    assert button.minimumHeight() >= 56
    panel.close()
    app.processEvents()
