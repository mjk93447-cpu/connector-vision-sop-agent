from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.sop_generation import SOPGenerationService

try:
    from PyQt6.QtWidgets import (
        QComboBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )

    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    QWidget = object  # type: ignore[assignment,misc]


class SOPGeneratePanel(QWidget):  # type: ignore[misc]
    """Document-to-SOP workflow for canonical generation and runtime compile/apply."""

    def __init__(
        self,
        generation_service: SOPGenerationService,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._service = generation_service
        self._canonical: Optional[Dict[str, Any]] = None
        self._answer_widgets: Dict[str, Any] = {}
        self._setup_ui()
        self._refresh_runtime_readiness()

    def _setup_ui(self) -> None:
        if not _QT_AVAILABLE:
            return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel("SOP Generate")
        header.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        self._status = QLabel("1. Upload a PDF, PPTX, TXT, or MD document to generate a canonical SOP.")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._runtime_status = QLabel("")
        self._runtime_status.setWordWrap(True)
        layout.addWidget(self._runtime_status)

        upload_box = QGroupBox("1. Upload")
        upload_layout = QHBoxLayout(upload_box)
        self._btn_upload = QPushButton("Upload Document")
        self._btn_upload.clicked.connect(self._on_upload)
        self._btn_import = QPushButton("Import SOP Package")
        self._btn_import.clicked.connect(self._on_import_package)
        upload_layout.addWidget(self._btn_upload)
        upload_layout.addWidget(self._btn_import)
        upload_layout.addStretch()
        layout.addWidget(upload_box)

        preview_box = QGroupBox("2. Analysis Preview")
        preview_layout = QVBoxLayout(preview_box)
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        preview_layout.addWidget(self._preview)
        layout.addWidget(preview_box, stretch=1)

        question_box = QGroupBox("3. Questions")
        question_layout = QVBoxLayout(question_box)
        self._question_scroll = QScrollArea()
        self._question_scroll.setWidgetResizable(True)
        self._question_container = QWidget()
        self._question_form = QFormLayout(self._question_container)
        self._question_scroll.setWidget(self._question_container)
        question_layout.addWidget(self._question_scroll)
        self._btn_apply_answers = QPushButton("Apply Answers")
        self._btn_apply_answers.clicked.connect(self._on_apply_answers)
        question_layout.addWidget(self._btn_apply_answers)
        layout.addWidget(question_box, stretch=1)

        action_box = QGroupBox("4. Finalize / Apply / Export")
        action_layout = QHBoxLayout(action_box)
        self._btn_finalize = QPushButton("Finalize")
        self._btn_finalize.clicked.connect(self._on_finalize)
        self._btn_apply_now = QPushButton("Apply now")
        self._btn_apply_now.clicked.connect(self._on_apply_now)
        self._btn_save_canonical = QPushButton("Save canonical only")
        self._btn_save_canonical.clicked.connect(self._on_save_canonical)
        self._btn_save_both = QPushButton("Save canonical + compiled")
        self._btn_save_both.clicked.connect(self._on_save_both)
        self._btn_export = QPushButton("Export package")
        self._btn_export.clicked.connect(self._on_export_package)
        for button in [
            self._btn_finalize,
            self._btn_apply_now,
            self._btn_save_canonical,
            self._btn_save_both,
            self._btn_export,
        ]:
            action_layout.addWidget(button)
        action_layout.addStretch()
        layout.addWidget(action_box)

    def _refresh_runtime_readiness(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            readiness = self._service.generation_readiness()
            self._runtime_status.setText(f"Runtime ready: {readiness}")
            self._btn_upload.setEnabled(True)
        except Exception as exc:  # noqa: BLE001
            self._runtime_status.setText(f"SOP Generate unavailable: {exc}")
            self._btn_upload.setEnabled(False)

    def set_status(self, text: str) -> None:
        if _QT_AVAILABLE:
            self._status.setText(text)

    def set_canonical(self, canonical: Dict[str, Any]) -> None:
        self._canonical = canonical
        self._render_preview()
        self._render_questions()

    def _render_preview(self) -> None:
        if not _QT_AVAILABLE:
            return
        if not self._canonical:
            self._preview.clear()
            return
        compile_result = self._canonical.get("compile_result", {})
        workflow_steps = self._canonical.get("workflow", {}).get("steps", [])
        preview = {
            "title": self._canonical.get("metadata", {}).get("title"),
            "status": self._canonical.get("metadata", {}).get("status"),
            "source_type": self._canonical.get("source_document", {}).get("source_type"),
            "source_refs": len(self._canonical.get("source_document", {}).get("refs", [])),
            "workflow_steps": len(workflow_steps),
            "questions": len(self._canonical.get("questions_asked", [])),
            "supported_steps": compile_result.get("supported_steps", []),
            "unsupported_steps": compile_result.get("unsupported_steps", []),
            "warnings": compile_result.get("warnings", []),
        }
        self._preview.setPlainText(json.dumps(preview, ensure_ascii=False, indent=2))

    def _render_questions(self) -> None:
        if not _QT_AVAILABLE:
            return
        self._answer_widgets = {}
        while self._question_form.rowCount():
            self._question_form.removeRow(0)
        if not self._canonical:
            return
        answers = self._canonical.get("answers", {})
        for question in self._canonical.get("questions_asked", []):
            if not isinstance(question, dict):
                continue
            qid = str(question.get("id") or "")
            prompt = str(question.get("prompt") or qid)
            options = question.get("options") or []
            if options:
                widget = QComboBox()
                widget.addItem("")
                for option in options:
                    widget.addItem(str(option))
                current_value = str(answers.get(qid, ""))
                if current_value:
                    index = widget.findText(current_value)
                    if index >= 0:
                        widget.setCurrentIndex(index)
            else:
                widget = QLineEdit()
                widget.setText(str(answers.get(qid, "")))
            self._answer_widgets[qid] = widget
            self._question_form.addRow(prompt, widget)

    def _collect_answers(self) -> Dict[str, Any]:
        answers: Dict[str, Any] = {}
        for qid, widget in self._answer_widgets.items():
            if hasattr(widget, "currentText"):
                value = widget.currentText().strip()
            else:
                value = widget.text().strip()
            if value:
                answers[qid] = value
        return answers

    def _on_upload(self) -> None:
        if not _QT_AVAILABLE:
            return
        try:
            self.set_status(self._service.generation_readiness())
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Generation Runtime Unavailable", str(exc))
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SOP Source Document",
            "",
            "Supported SOP Docs (*.pdf *.pptx *.txt *.md)",
        )
        if not path:
            return
        try:
            canonical = self._service.generate_from_document(path)
            self.set_canonical(canonical)
            self.set_status("Analysis ready. Review the preview and answer the generated questions.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Generation Failed", str(exc))

    def _on_apply_answers(self) -> None:
        if not _QT_AVAILABLE or not self._canonical:
            return
        answers = self._collect_answers()
        try:
            canonical = self._service.answer_generation_questions(self._canonical, answers)
            self.set_canonical(canonical)
            self.set_status("Answers applied to the canonical SOP.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Answer Apply Failed", str(exc))

    def _on_finalize(self) -> None:
        if not _QT_AVAILABLE or not self._canonical:
            return
        try:
            finalized = self._service.finalize_canonical_sop(self._canonical)
            self.set_canonical(finalized)
            self.set_status("Canonical SOP finalized.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Finalize Failed", str(exc))

    def _on_apply_now(self) -> None:
        if not _QT_AVAILABLE or not self._canonical:
            return
        try:
            finalized = self._service.finalize_canonical_sop(self._canonical)
            compile_result = self._service.compile_to_runtime_json(
                finalized,
                self._service.build_runtime_profile(),
            )
            if not compile_result.runtime_json.get("steps"):
                raise ValueError("No automatable runtime steps were produced. Use save/export only.")
            self.set_canonical(finalized)
            parent = self.parent()
            if parent is None or not hasattr(parent, "apply_generated_runtime"):
                raise RuntimeError("MainWindow runtime apply API is unavailable.")
            parent.apply_generated_runtime(compile_result)  # type: ignore[union-attr]
            self.set_status("Generated runtime SOP was applied to the current session.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Apply Failed", str(exc))

    def _on_save_canonical(self) -> None:
        if not _QT_AVAILABLE or not self._canonical:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Canonical SOP",
            str(Path.cwd() / "generated.sop.json"),
            "Canonical SOP (*.sop.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            Path(path).write_text(
                json.dumps(self._canonical, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.set_status(f"Saved canonical SOP to {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save Failed", str(exc))

    def _on_save_both(self) -> None:
        if not _QT_AVAILABLE or not self._canonical:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Canonical SOP",
            str(Path.cwd() / "generated.sop.json"),
            "Canonical SOP (*.sop.json);;JSON (*.json)",
        )
        if not path:
            return
        try:
            finalized = self._service.finalize_canonical_sop(self._canonical)
            compile_result = self._service.compile_to_runtime_json(
                finalized,
                self._service.build_runtime_profile(),
            )
            canonical_path = Path(path)
            runtime_path = canonical_path.with_name(canonical_path.stem + ".compiled.json")
            canonical_path.write_text(json.dumps(finalized, ensure_ascii=False, indent=2), encoding="utf-8")
            runtime_path.write_text(
                json.dumps(compile_result.runtime_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.set_canonical(finalized)
            self.set_status(f"Saved canonical and compiled runtime JSON to {canonical_path.parent}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save Failed", str(exc))

    def _on_export_package(self) -> None:
        if not _QT_AVAILABLE or not self._canonical:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export SOP Package",
            str(Path.cwd() / "generated_sop_package.zip"),
            "ZIP Package (*.zip)",
        )
        if not path:
            return
        try:
            finalized = self._service.finalize_canonical_sop(self._canonical)
            compile_result = self._service.compile_to_runtime_json(
                finalized,
                self._service.build_runtime_profile(),
            )
            self._service.save_sop_package(finalized, compile_result, path)
            self.set_canonical(finalized)
            self.set_status(f"Exported SOP package to {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export Failed", str(exc))

    def _on_import_package(self) -> None:
        if not _QT_AVAILABLE:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import SOP Package",
            "",
            "ZIP Package (*.zip)",
        )
        if not path:
            return
        try:
            data = self._service.import_sop_package(path)
            self.set_canonical(data["canonical"])
            self.set_status("Imported SOP package. Review and apply or export as needed.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Import Failed", str(exc))
