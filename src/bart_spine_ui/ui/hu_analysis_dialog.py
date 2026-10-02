"""CT attenuation profiles and descriptive statistics for planned screws."""
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def hu_statistics(result):
    values = np.asarray(result.hu, dtype=float)
    valid = values[np.isfinite(values)]
    coverage = np.asarray(result.coverage, dtype=float)
    coverage = coverage[np.isfinite(coverage)]
    return {
        "count": len(valid), "total": len(values),
        "mean": float(np.mean(valid)) if len(valid) else None,
        "median": float(np.median(valid)) if len(valid) else None,
        "quartiles": tuple(np.percentile(valid, [25, 75])) if len(valid) else None,
        "coverage": result.model_coverage,
        "sample_support": float(np.mean(coverage)) if len(coverage) else None,
    }


class HUPlot(QWidget):
    """Depth profile or histogram; profiles support tap and keyboard inspection."""
    sample_selected = Signal(int)

    def __init__(self, histogram=False, parent=None):
        super().__init__(parent)
        self.histogram = histogram
        self.result = None
        self.selected_index = None
        self.setMinimumSize(260, 230)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("HU distribution" if histogram else
                               "HU by depth; tap or use arrow keys to inspect samples")

    def set_result(self, result):
        self.result = result
        self.selected_index = None
        self.update()

    def plot_rect(self):
        return QRectF(66, 35, max(1, self.width()-88), max(1, self.height()-96))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#111b27"))
        p.setPen(QColor("#edf2fa"))
        p.drawText(16, 22, "Sample distribution" if self.histogram else "Attenuation along screw")
        if self.result is None:
            return
        hu = np.asarray(self.result.hu, dtype=float)
        depth = np.asarray(self.result.depth_mm, dtype=float)
        finite = np.isfinite(hu)
        box = self.plot_rect()
        if not finite.any():
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, "No valid HU samples")
            return
        values = hu[finite]
        if self.histogram:
            counts, edges = np.histogram(values, bins=min(12, max(1, int(np.sqrt(len(values))))))
            xmin, xmax = edges[0], edges[-1]
            ymin, ymax = 0., max(1., float(counts.max()))
        else:
            xmin, xmax = 0., max(1., float(depth[-1]))
            margin = max(50., float(np.ptp(values))*.12)
            ymin, ymax = float(values.min())-margin, float(values.max())+margin

        def xy(x, y):
            return QPointF(box.left()+(x-xmin)/(xmax-xmin)*box.width(),
                           box.bottom()-(y-ymin)/(ymax-ymin)*box.height())

        ticks = (np.unique(np.linspace(0, ymax, 5).astype(int)) if self.histogram
                 else np.linspace(ymin, ymax, 5))
        for tick in ticks:
            y = box.bottom()-(tick-ymin)/(ymax-ymin)*box.height()
            p.setPen(QPen(QColor("#304253"), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(box.left(), y), QPointF(box.right(), y))
            p.setPen(QColor("#c6d2df"))
            p.drawText(QRectF(0, y-10, 59, 20), Qt.AlignmentFlag.AlignRight,
                       f"{tick:.0f}")
        for fraction in np.linspace(0, 1, 5):
            x = box.left()+fraction*box.width()
            p.drawText(QRectF(x-28, box.bottom()+8, 56, 20), Qt.AlignmentFlag.AlignCenter,
                       f"{xmin+fraction*(xmax-xmin):.0f}")
        p.drawText(QRectF(box.left(), self.height()-28, box.width(), 20),
                   Qt.AlignmentFlag.AlignCenter,
                   "HU" if self.histogram else "Depth from entry (mm)")
        p.save()
        p.translate(15, box.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-80, -10, 160, 20), Qt.AlignmentFlag.AlignCenter,
                   "Sample count" if self.histogram else "HU")
        p.restore()
        if self.histogram:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ac91ff"))
            for count, left, right in zip(counts, edges[:-1], edges[1:]):
                top = xy(left, count)
                bottom = xy(right, 0)
                p.drawRect(QRectF(top.x()+2, top.y(), max(1, bottom.x()-top.x()-4),
                                  bottom.y()-top.y()))
        else:
            p.setPen(QPen(QColor("#ffbd59"), 2.5))
            # Preserve gaps: missing samples must not be interpolated on screen.
            for i in range(1, len(hu)):
                if finite[i-1] and finite[i]:
                    p.drawLine(xy(depth[i-1], hu[i-1]), xy(depth[i], hu[i]))
            p.setBrush(QColor("#ffbd59"))
            for i in np.flatnonzero(finite):
                p.drawEllipse(xy(depth[i], hu[i]), 2.5, 2.5)
            p.setPen(QPen(QColor("#ff7085"), 2))
            for i in np.flatnonzero(~finite):
                x = xy(depth[i], ymin).x()
                p.drawLine(QPointF(x-3, box.bottom()-5), QPointF(x+3, box.bottom()+1))
                p.drawLine(QPointF(x-3, box.bottom()+1), QPointF(x+3, box.bottom()-5))
            if self.selected_index is not None:
                x = xy(depth[self.selected_index], ymin).x()
                p.setPen(QPen(QColor("#62dfc4"), 2, Qt.PenStyle.DashLine))
                p.drawLine(QPointF(x, box.top()), QPointF(x, box.bottom()))

    def select_sample(self, index):
        if self.result is None or not len(self.result.hu) or self.histogram:
            return
        self.selected_index = int(np.clip(index, 0, len(self.result.hu)-1))
        self.sample_selected.emit(self.selected_index)
        self.update()

    def mousePressEvent(self, event):
        if self.result is None or self.histogram or not len(self.result.hu):
            return
        self.setFocus()
        box = self.plot_rect()
        depth = np.asarray(self.result.depth_mm)
        target = np.clip((event.position().x()-box.left())/box.width(), 0, 1)*max(1, depth[-1])
        self.select_sample(int(np.argmin(np.abs(depth-target))))

    def keyPressEvent(self, event):
        index = self.selected_index or 0
        if event.key() == Qt.Key.Key_Home:
            self.select_sample(0)
        elif event.key() == Qt.Key.Key_End and self.result is not None:
            self.select_sample(len(self.result.hu)-1)
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.select_sample(index + (1 if event.key() == Qt.Key.Key_Right else -1))
        else:
            super().keyPressEvent(event)


class HUDetailDialog(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CT attenuation · Hounsfield-unit analysis")
        self.resize(1000, 650)
        self.setMinimumSize(720, 520)
        self.results = results
        self.setStyleSheet("""
            QDialog { background:#0c1420; }
            QLabel { color:#dce5ef; font-size:14px; }
            QAbstractButton,
    QComboBox, QPushButton { background:#233448; color:#f0f5ff;
                padding:9px; border:1px solid #627991; border-radius:6px; }
            QComboBox QAbstractItemView { background:#233448; color:#f0f5ff; }
            QLabel#HUStat { background:#1e2c3d; border-radius:8px; padding:12px;
                color:#f5f1ff; font-size:16px; }
        """)
        layout = QVBoxLayout(self)
        title = QLabel("HOUNSFIELD-UNIT ANALYSIS")
        title.setStyleSheet("font-size:20px; font-weight:700;")
        layout.addWidget(title)
        header = QHBoxLayout()
        header.addWidget(QLabel("Screw"))
        self.selector = QComboBox()
        from ..planning.service import LEVEL_ORDER
        self.keys = sorted(results, key=lambda k: (LEVEL_ORDER.index(k[0]), k[1]))
        for key in self.keys:
            self.selector.addItem(f"{key[0]} · {key[1].upper()}", key)
        header.addWidget(self.selector, 1)
        layout.addLayout(header)
        self.review_note = QLabel()
        self.review_note.setWordWrap(True)
        self.review_note.setStyleSheet("color:#ffbd59; font-size:14px;")
        layout.addWidget(self.review_note)
        stats = QGridLayout()
        self.stat_labels = []
        for i in range(4):
            label = QLabel()
            label.setObjectName("HUStat")
            label.setWordWrap(True)
            stats.addWidget(label, 0, i)
            stats.setColumnStretch(i, 1)
            self.stat_labels.append(label)
        layout.addLayout(stats)
        plots = QHBoxLayout()
        self.profile = HUPlot()
        self.histogram = HUPlot(histogram=True)
        plots.addWidget(self.profile, 3)
        plots.addWidget(self.histogram, 2)
        layout.addLayout(plots, 1)
        legend = QLabel("Orange: HU · Purple: count · Pink ×: missing")
        legend.setWordWrap(True)
        layout.addWidget(legend)
        self.readout = QLabel()
        self.readout.setStyleSheet("color:#62dfc4; font-size:16px; font-weight:700;")
        self.readout.setWordWrap(True)
        layout.addWidget(self.readout)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)
        self.profile.sample_selected.connect(self._sample_selected)
        self.selector.currentIndexChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self):
        result = self.results.get(self.keys[self.selector.currentIndex()]) if self.keys else None
        self.profile.set_result(result)
        self.histogram.set_result(result)
        if result is None:
            self.readout.setText("No HU measurements available")
            return
        flags = review_reasons(result)
        self.review_note.setText(" · ".join(flags) if flags else "G–R A · full sampled 3D containment")
        stats = hu_statistics(result)
        def hu(value):
            return "No samples" if value is None else f"{value:.0f} HU"
        quartiles = stats["quartiles"]
        texts = [f"Mean\n{hu(stats['mean'])}", f"Median\n{hu(stats['median'])}",
                 "Middle 50%\n" + (f"{quartiles[0]:.0f}–{quartiles[1]:.0f} HU" if quartiles else "No samples"),
                 "Coverage\n" + (f"{stats['coverage']:.0%}" if stats['coverage'] is not None else "No samples")]
        for label, text in zip(self.stat_labels, texts):
            label.setText(text)
        self.summary.setText(f"{stats['count']} / {stats['total']} valid depth samples · "
                             "Missing samples excluded")
        self.readout.setText("Select a depth on the orange profile")
        if len(result.hu):
            self.profile.select_sample(0)

    def _sample_selected(self, index):
        result = self.results[self.keys[self.selector.currentIndex()]]
        value = result.hu[index]
        text = f"{value:.0f} HU" if np.isfinite(value) else "No sample"
        coverage = result.coverage[index]
        coverage_text = f"{coverage:.0%}" if np.isfinite(coverage) else "unavailable"
        self.readout.setText(f"{result.depth_mm[index]:.1f} mm from entry · {text} · "
                             f"CT sample support {coverage_text}")


def review_reasons(result):
    """Display measurement flags, without inventing density or clinical cutoffs."""
    reasons = []
    if result.grade != "A":
        reasons.append(f"G–R {result.grade}: {result.breach_text}" if result.grade != "—"
                       else "Breach measurement unavailable")
    if result.model_coverage is None:
        reasons.append(result.model_coverage_reason or "Coverage unavailable")
    elif result.model_coverage < 1 - 1e-9:
        reasons.append("Some sampled screw surface lies outside the vertebra mesh")
    if not len(result.hu) or not np.all(np.isfinite(result.hu)):
        reasons.append("Missing CT samples")
    if result.reason:
        reasons.append(result.reason)
    return reasons


class HUScrewCard(QAbstractButton):
    """One large touch target with mean HU, geometric coverage and a sparkline."""
    def __init__(self, key, result, limits, *, skipped=False, parent=None):
        super().__init__(parent)
        self.key, self.result, self.limits = key, result, limits
        self.skipped = skipped
        self.setMinimumSize(285, 154)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.flags = review_reasons(result) if result is not None else []
        self.setEnabled(result is not None and not skipped)
        stats = hu_statistics(result) if result is not None else {}
        mean = stats.get("mean")
        coverage = stats.get("coverage")
        self.mean_text = "— HU" if mean is None else f"{mean:.0f} HU"
        self.coverage_text = "—" if coverage is None else (
            "<100%" if coverage < 1 and round(coverage*100) == 100 else f"{coverage:.0%}")
        self.status_text = "⚠ REVIEW" if self.flags else "✓ G–R A"
        label = "Skipped" if skipped else "No measurements" if result is None else (
            f"{self.mean_text}, Coverage {self.coverage_text}, {self.status_text}")
        self.setAccessibleName(f"{key[0]} {key[1]}: {label}")
        self.setToolTip("\n".join(self.flags) if self.flags else "Tap for the full depth profile")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        accent = QColor("#ffbd59" if self.flags else "#63dec0")
        if not self.isEnabled():
            accent = QColor("#76899d")
        p.setBrush(QColor("#23394b" if self.hasFocus() or self.isDown() else "#152535"))
        p.setPen(QPen(QColor("#f2f6ff") if self.hasFocus() else accent, 2))
        p.drawRoundedRect(rect, 12, 12)

        def write(box, text, size, color, alignment=Qt.AlignmentFlag.AlignLeft):
            font = p.font()
            font.setPixelSize(size)
            font.setBold(True)
            p.setFont(font)
            p.setPen(color)
            p.drawText(box, alignment | Qt.AlignmentFlag.AlignVCenter, text)

        if not self.isEnabled():
            write(rect, "SKIPPED" if self.skipped else "NO DATA", 24, accent,
                  Qt.AlignmentFlag.AlignCenter)
            return
        write(QRectF(18, 10, self.width()-160, 42), self.mean_text, 30, QColor("#f2f6ff"))
        write(QRectF(self.width()-138, 10, 120, 36), self.coverage_text, 28, accent,
              Qt.AlignmentFlag.AlignRight)
        write(QRectF(self.width()-140, 43, 122, 18), "Coverage", 11, QColor("#becbda"),
              Qt.AlignmentFlag.AlignRight)
        box = QRectF(18, 67, self.width()-36, max(20, self.height()-111))
        p.setPen(QPen(QColor("#32495d"), 1))
        p.drawLine(box.bottomLeft(), box.bottomRight())
        hu = np.asarray(self.result.hu, dtype=float)
        depth = np.asarray(self.result.depth_mm, dtype=float)
        finite = np.isfinite(hu)
        low, high = self.limits
        length = max(1., float(depth[-1])) if len(depth) else 1.

        def point(i):
            return QPointF(box.left()+depth[i]/length*box.width(),
                           box.bottom()-(hu[i]-low)/(high-low)*box.height())

        p.setPen(QPen(QColor("#ffbd59"), 2.7))
        for i in range(1, len(hu)):
            if finite[i-1] and finite[i]:
                p.drawLine(point(i-1), point(i))
        p.setBrush(QColor("#ffbd59"))
        for i in np.flatnonzero(finite):
            p.drawEllipse(point(i), 1.6, 1.6)
        p.setPen(QPen(QColor("#ff7085"), 3))
        for i in np.flatnonzero(~finite):
            x = box.left()+depth[i]/length*box.width()
            p.drawLine(QPointF(x-2, box.bottom()-4), QPointF(x+2, box.bottom()))
            p.drawLine(QPointF(x+2, box.bottom()-4), QPointF(x-2, box.bottom()))
        if not finite.any():
            write(box, "NO CT SAMPLES", 16, QColor("#ff7085"), Qt.AlignmentFlag.AlignCenter)
        write(QRectF(18, self.height()-35, self.width()-36, 25), self.status_text, 17, accent)
        write(QRectF(self.width()-116, self.height()-35, 98, 25), "DETAILS ›", 12,
              QColor("#becbda"), Qt.AlignmentFlag.AlignRight)


class HUAnalysisDialog(QDialog):
    """Anatomical overview first; full charts are one tap away."""
    PAGE_SIZE = 3

    def __init__(self, results, parent=None, *, levels=None, skipped=None):
        super().__init__(parent)
        from ..planning.service import LEVEL_ORDER
        self.results = results
        self.skipped = set(skipped or ())
        self.levels = sorted(set(levels or ()) | {key[0] for key in results}, key=LEVEL_ORDER.index)
        self.page = 0
        self.detail_dialog = None
        self.setWindowTitle("CT overview · level and side")
        self.setMinimumSize(760, 660)
        self.resize(1100, 760)
        self.setStyleSheet("""
            QDialog { background:#0c1420; }
            QLabel { color:#dce5ef; font-size:15px; }
            QPushButton { background:#24384d; color:#f0f5ff; padding:8px 16px;
                border:1px solid #68849f; border-radius:8px; font-size:17px; font-weight:700; }
            QPushButton:disabled { color:#65788c; border-color:#35485a; }
            QPushButton:focus { border:2px solid #f0f5ff; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("CT OVERVIEW")
        title.setStyleSheet("font-size:25px; font-weight:800;")
        header.addWidget(title, 1)
        self.info_button = QPushButton("ⓘ Metrics")
        self.info_button.setMinimumHeight(48)
        self.info_button.clicked.connect(self._show_metrics)
        header.addWidget(self.info_button)
        layout.addLayout(header)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(10)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(2, 1)
        layout.addLayout(self.grid, 1)
        all_values = [np.asarray(result.hu)[np.isfinite(result.hu)] for result in results.values()]
        values = np.concatenate(all_values) if all_values else np.array([])
        if len(values):
            margin = max(20., float(np.ptp(values))*.08)
            self.limits = (float(values.min())-margin, float(values.max())+margin)
        else:
            self.limits = (0., 1000.)
        footer = QHBoxLayout()
        self.previous = QPushButton("← Previous")
        self.next = QPushButton("Next →")
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previous.clicked.connect(lambda: self._change_page(-1))
        self.next.clicked.connect(lambda: self._change_page(1))
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        for button in (self.previous, self.next, self.close_button):
            button.setMinimumHeight(52)
        footer.addWidget(self.previous)
        footer.addWidget(self.page_label, 1)
        footer.addWidget(self.next)
        footer.addSpacing(16)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)
        self._populate()

    def _populate(self):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget:
                widget.hide()
                widget.deleteLater()
        self.cards = {}
        for column, text in enumerate(("LEFT", "VERTEBRA", "RIGHT")):
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color:#bdd0e3; font-size:15px; font-weight:700;")
            self.grid.addWidget(label, 0, column)
        for row, level in enumerate(self.levels[self.page*3:(self.page+1)*3], 1):
            label = QLabel(level)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size:29px; font-weight:800; color:#f3f6ff;")
            self.grid.addWidget(label, row, 1)
            for side, column in (("left", 0), ("right", 2)):
                key = (level, side)
                card = HUScrewCard(key, self.results.get(key), self.limits,
                                   skipped=key in self.skipped)
                card.clicked.connect(lambda checked=False, key=key: self.open_detail(key))
                self.grid.addWidget(card, row, column)
                self.cards[key] = card
        if not self.levels:
            self.grid.addWidget(QLabel("No measurements"), 1, 0, 1, 3)
        pages = max(1, (len(self.levels)+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.previous.setEnabled(self.page > 0)
        self.next.setEnabled(self.page+1 < pages)
        self.page_label.setText(f"{self.page+1} / {pages}")

    def _change_page(self, direction):
        self.page = max(0, min(self.page+direction, max(0, (len(self.levels)-1)//self.PAGE_SIZE)))
        self._populate()

    def focus_target(self, key):
        if key[0] in self.levels:
            self.page = self.levels.index(key[0])//self.PAGE_SIZE
            self._populate()
            if key in self.cards:
                self.cards[key].setFocus()

    def open_detail(self, key):
        if key not in self.results or key in self.skipped:
            return
        if self.detail_dialog is not None:
            self.detail_dialog.close()
            self.detail_dialog.deleteLater()
        self.detail_dialog = HUDetailDialog({key: self.results[key]}, self)
        self.detail_dialog.setWindowTitle(f"{key[0]} {key[1].upper()} · CT profile")
        self.detail_dialog.show()

    def _show_metrics(self):
        QMessageBox.information(self, "Metric definitions",
            "HU: mean of valid depth samples in the 1 mm bone shell around the screw. "
            "Low HU does not reduce Coverage.\n\n"
            "Coverage: area-weighted estimate of screw surface inside the raw vertebra mesh, "
            "after the same entry exclusion used for grading. It is not bone density or fixation strength. "
            "An incomplete mesh is shown as unavailable.\n\n"
            "REVIEW: breach finding, sampled surface outside the mesh, or missing measurements. "
            "✓ G–R A: grade A, full sampled containment and complete CT profile; not clinical clearance.\n\n"
            "Orange: CT profile. Pink ×: missing sample. Tap a card for measurements and details.")

    def done(self, result):
        if self.detail_dialog is not None:
            self.detail_dialog.close()
        super().done(result)

    def closeEvent(self, event):
        if self.detail_dialog is not None:
            self.detail_dialog.close()
        super().closeEvent(event)
