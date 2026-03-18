"""
YOLO26x 프리트레인 파이프라인.

공개 GUI/공장 데이터셋으로 YOLO26x를 프리트레인한 뒤,
별도 검증 세트로 mAP50을 측정하고 리포트를 출력한다.

학습 흐름
---------
1. 데이터셋 다운로드 (HuggingFace 또는 합성 데이터)
2. YOLO 형식 변환 + train/val 80/20 분할
3. YOLO26x 학습 (pretrain_data/ 저장)
4. 검증 세트로 model.val() → mAP50 측정
5. 결과를 PRETRAIN_REPORT.md 로 저장

사용 예
-------
  from src.training.pretrain_pipeline import PretrainPipeline

  pipeline = PretrainPipeline(output_dir="pretrain_data")
  pipeline.build_showui_desktop_dataset(max_samples=500)
  metrics = pipeline.train_and_evaluate(epochs=20, batch=4)
  pipeline.save_report(metrics)

CLI:
  python scripts/run_pretrain.py --source showui_desktop --max-samples 500 --epochs 20

지원 데이터 소스
---------------
- "showui_desktop"   : showlab/ShowUI-desktop (HuggingFace, OmniAct 기반 데스크탑)
                       Windows/Mac/Linux 데스크탑 앱 실제 스크린샷. 권장.
- "synthetic"        : 합성 GUI 데이터 (테스트·시연용, 의존성 없음)
- "rico_widget"      : rootsautomation/RICO-WidgetCaptioning (HuggingFace, Android)
                       레거시 지원. 구형 Windows 환경 사용 시 showui_desktop 권장.
- "pcb_components"   : Roboflow PCB-Components 데이터셋
                       (roboflow Python 패키지 + ROBOFLOW_API_KEY 환경변수 필요)
                       커넥터/저항/캐패시터 등 산업 PCB 컴포넌트 포함.
                       YOLO26x가 산업 시각 특징을 학습하기에 유용한 Tier-1 소스.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from src.training.dataset_converter import (
    PRETRAIN_CLASSES,
    SyntheticGUIGenerator,
    convert_rico_sample,
    convert_showui_desktop_sample,
    split_train_val,
)
from src.training.dataset_manager import DatasetManager

_DEFAULT_OUTPUT_DIR = Path("pretrain_data")
_PRETRAIN_WEIGHTS = Path("assets/models/yolo26x_pretrained.pt")


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------


@dataclass
class PretrainConfig:
    """프리트레인 파이프라인 설정."""

    output_dir: Path = field(default_factory=lambda: _DEFAULT_OUTPUT_DIR)
    base_model: str = "yolo26x.pt"  # COCO pretrained → 프리트레인 시작점
    pretrained_weights: Path = field(default_factory=lambda: _PRETRAIN_WEIGHTS)
    epochs: int = 20
    batch: int = 4
    image_size: int = 640
    val_ratio: float = 0.20
    random_seed: int = 42
    device: str = "cpu"

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.pretrained_weights = Path(self.pretrained_weights)


# ---------------------------------------------------------------------------
# 파이프라인 본체
# ---------------------------------------------------------------------------


class PretrainPipeline:
    """YOLO26x 프리트레인 오케스트레이터.

    Parameters
    ----------
    output_dir:  학습 데이터 및 결과 저장 루트.
    config:      PretrainConfig (기본값으로 생성됨).
    """

    def __init__(
        self,
        output_dir: str | Path = _DEFAULT_OUTPUT_DIR,
        config: Optional[PretrainConfig] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.cfg = config or PretrainConfig(output_dir=self.output_dir)
        self.cfg.output_dir = self.output_dir
        self._dm = DatasetManager(data_root=self.output_dir)
        # images/labels dirs (flat, before train/val split)
        self._images_dir = self.output_dir / "images"
        self._labels_dir = self.output_dir / "labels"
        self._images_dir.mkdir(parents=True, exist_ok=True)
        self._labels_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1단계: 데이터셋 구축
    # ------------------------------------------------------------------

    def build_synthetic_dataset(
        self,
        n_images: int = 200,
        width: int = 1280,
        height: int = 800,
    ) -> int:
        """합성 GUI 데이터셋 생성 후 DatasetManager에 추가.

        Parameters
        ----------
        n_images:  생성할 이미지 수.
        width, height: 이미지 해상도 (픽셀).

        Returns
        -------
        저장된 이미지 수.
        """
        gen = SyntheticGUIGenerator(seed=self.cfg.random_seed)
        batch = gen.generate_batch(n_images=n_images, width=width, height=height)

        for idx, (img, anns) in enumerate(batch):
            self._save_pretrain_sample(f"synthetic_{idx:05d}", img, anns)

        print(
            f"[PretrainPipeline] 합성 데이터 {n_images}장 생성 완료 → {self.output_dir}"
        )
        return n_images

    def build_showui_desktop_dataset(
        self,
        max_samples: int = 500,
    ) -> int:
        """showlab/ShowUI-desktop 데이터셋 다운로드 및 변환 (권장 소스).

        OmniAct Desktop 기반으로 Windows/Mac/Linux 데스크탑 15개 앱
        실제 스크린샷 + UI 요소 bbox를 포함한다.
        Rico(Android) 대비 구형 Windows GUI와 훨씬 유사한 특성.

        Parameters
        ----------
        max_samples: 최대 이미지 수 (여러 행이 하나의 이미지를 공유하므로
                     실제 저장 이미지 수는 max_samples 이하가 될 수 있음).

        Returns
        -------
        실제 저장된 이미지 수.
        """
        # Offline guard — YOLO_OFFLINE=1 or ULTRALYTICS_OFFLINE=1 skips download
        import os as _os  # noqa: PLC0415

        if (
            _os.environ.get("YOLO_OFFLINE") == "1"
            or _os.environ.get("ULTRALYTICS_OFFLINE") == "1"
        ):
            print(
                "[PretrainPipeline] Offline mode detected — "
                "skipping ShowUI-Desktop download, using synthetic fallback."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        try:
            from datasets import load_dataset  # noqa: PLC0415
        except ImportError:
            print(
                "[PretrainPipeline] 'datasets' package not installed — "
                "falling back to synthetic dataset."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        print(
            f"[PretrainPipeline] ShowUI-Desktop 로딩 (최대 이미지 {max_samples}개)..."
        )
        try:
            ds = load_dataset(
                "showlab/ShowUI-desktop",
                split="train",
                streaming=True,
                trust_remote_code=False,
            )
        except Exception as _e:  # noqa: BLE001
            print(
                f"[PretrainPipeline] ShowUI-Desktop 다운로드 실패 ({_e}) — "
                "synthetic 데이터로 대체합니다."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        # 동일 이미지의 여러 행을 하나로 병합 (이미지 해시 키)
        # ShowUI-desktop: 100 스크린샷 × N 요소/쿼리 = 수천 행
        import hashlib  # noqa: PLC0415

        img_map: dict = {}  # image_hash → (img_bgr, [annotations])
        seen_order: list = []  # 삽입 순서 유지

        for sample in ds:
            if len(img_map) >= max_samples:
                break

            img, ann = convert_showui_desktop_sample(sample)
            if img is None:
                continue

            # 이미지 동일성 판별 (shape + 첫 행 해시)
            key = hashlib.md5(img[:4].tobytes()).hexdigest()  # 빠른 해시

            if key not in img_map:
                if len(img_map) >= max_samples:
                    break
                img_map[key] = (img, [])
                seen_order.append(key)

            img_map[key][1].extend(ann)

        saved = 0
        for key in seen_order:
            img, anns = img_map[key]
            if not anns:
                continue
            self._save_pretrain_sample(f"showui_{saved:05d}", img, anns)
            saved += 1
            if saved % 20 == 0:
                print(f"  ... {saved} 이미지 저장 완료")

        print(f"[PretrainPipeline] ShowUI-Desktop {saved}장 저장 완료")
        return saved

    def build_rico_dataset(
        self,
        max_samples: int = 500,
    ) -> int:
        """Rico WidgetCaptioning 데이터셋 다운로드 및 변환.

        Parameters
        ----------
        max_samples: 최대 샘플 수 (대규모 다운로드 방지).

        Returns
        -------
        실제 변환된 이미지 수.
        """
        # Offline guard
        import os as _os  # noqa: PLC0415

        if (
            _os.environ.get("YOLO_OFFLINE") == "1"
            or _os.environ.get("ULTRALYTICS_OFFLINE") == "1"
        ):
            print(
                "[PretrainPipeline] Offline mode detected — "
                "skipping Rico download, using synthetic fallback."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        try:
            from datasets import load_dataset  # noqa: PLC0415
        except ImportError:
            print(
                "[PretrainPipeline] 'datasets' package not installed — "
                "falling back to synthetic dataset."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        print(
            f"[PretrainPipeline] Rico WidgetCaptioning 로딩 (최대 {max_samples}개)..."
        )
        try:
            ds = load_dataset(
                "rootsautomation/RICO-WidgetCaptioning",
                split="train",
                streaming=True,
                trust_remote_code=False,
            )
        except Exception as _e:  # noqa: BLE001
            print(
                f"[PretrainPipeline] Rico 다운로드 실패 ({_e}) — "
                "synthetic 데이터로 대체합니다."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        saved = 0
        for sample in ds:
            if saved >= max_samples:
                break
            img, annotations = convert_rico_sample(sample)
            if img is None or not annotations:
                continue
            self._save_pretrain_sample(f"rico_{saved:05d}", img, annotations)
            saved += 1
            if saved % 50 == 0:
                print(f"  ... {saved}/{max_samples} 변환 완료")

        print(f"[PretrainPipeline] Rico 데이터 {saved}장 저장 완료")
        return saved

    def build_pcb_components_dataset(
        self,
        max_samples: int = 500,
        api_key: Optional[str] = None,
    ) -> int:
        """Roboflow PCB-Components 데이터셋 다운로드 및 변환.

        YOLO26x가 산업 PCB 컴포넌트(커넥터·저항·캐패시터 등)의 시각 특징을
        학습하도록 하여, OLED 라인 파인튜닝 시 수렴 속도를 높인다.

        Requirements
        ------------
        - `pip install roboflow` 설치 필요.
        - `ROBOFLOW_API_KEY` 환경변수 또는 api_key 파라미터 필요.

        Parameters
        ----------
        max_samples: 최대 이미지 수.
        api_key:     Roboflow API 키 (없으면 환경변수 ROBOFLOW_API_KEY 사용).

        Returns
        -------
        실제 변환된 이미지 수.
        """
        import os  # noqa: PLC0415

        # Offline guard
        if (
            os.environ.get("YOLO_OFFLINE") == "1"
            or os.environ.get("ULTRALYTICS_OFFLINE") == "1"
        ):
            print(
                "[PretrainPipeline] Offline mode detected — "
                "skipping Roboflow PCB download, using synthetic fallback."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        try:
            from roboflow import Roboflow  # noqa: PLC0415
        except ImportError:
            print(
                "[PretrainPipeline] 'roboflow' package not installed — "
                "falling back to synthetic dataset."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        key = api_key or os.environ.get("ROBOFLOW_API_KEY", "")
        if not key:
            print(
                "[PretrainPipeline] ROBOFLOW_API_KEY not set — "
                "falling back to synthetic dataset."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        print(
            f"[PretrainPipeline] Roboflow PCB-Components 로딩 (최대 {max_samples}개)..."
        )
        try:
            rf = Roboflow(api_key=key)
            project = rf.workspace("roboflow-100").project("pcb-components-4x9w5")
            dataset = project.version(1).download(
                "yolov5pytorch",  # YOLO26x 규칙 준수 — yolov8 금지, 동일 txt 포맷
                location=str(self.output_dir / "_roboflow_pcb"),
            )
        except Exception as _e:  # noqa: BLE001
            print(
                f"[PretrainPipeline] Roboflow 다운로드 실패 ({_e}) — "
                "synthetic 데이터로 대체합니다."
            )
            return self.build_synthetic_dataset(max_samples=min(max_samples, 200))

        # PCB dataset은 YOLO 포맷으로 제공됨 — 이미지·레이블을 pretrain 디렉터리로 복사
        import cv2  # noqa: PLC0415
        import shutil  # noqa: PLC0415

        src_images = Path(dataset.location) / "train" / "images"
        src_labels = Path(dataset.location) / "train" / "labels"
        # PCB class id → pretrain "connector" index mapping
        # PCB-Components v1 classes (partial): 0=capacitor, 1=connector, 2=ic, 3=resistor, ...
        _PCB_CONNECTOR_CLASS_IDS = {1}  # connector class in PCB dataset

        saved = 0
        if src_images.exists():
            for img_file in sorted(src_images.glob("*.jpg")) + sorted(
                src_images.glob("*.png")
            ):
                if saved >= max_samples:
                    break
                lbl_file = src_labels / (img_file.stem + ".txt")
                if not lbl_file.exists():
                    continue

                img = cv2.imread(str(img_file))
                if img is None:
                    continue

                anns = []
                h, w = img.shape[:2]
                for line in lbl_file.read_text().splitlines():
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    class_id = int(parts[0])
                    cx, cy, bw, bh = (
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3]),
                        float(parts[4]),
                    )
                    # Map PCB connector → pretrain "connector" class
                    label = (
                        "connector"
                        if class_id in _PCB_CONNECTOR_CLASS_IDS
                        else "button"
                    )
                    x1 = (cx - bw / 2) * w
                    y1 = (cy - bh / 2) * h
                    x2 = (cx + bw / 2) * w
                    y2 = (cy + bh / 2) * h
                    anns.append({"label": label, "bbox": [x1, y1, x2, y2]})

                if not anns:
                    continue

                self._save_pretrain_sample(f"pcb_{saved:05d}", img, anns)
                saved += 1
                if saved % 50 == 0:
                    print(f"  ... {saved}/{max_samples} 변환 완료")

        # Cleanup downloaded roboflow dir
        shutil.rmtree(str(self.output_dir / "_roboflow_pcb"), ignore_errors=True)

        print(f"[PretrainPipeline] PCB-Components {saved}장 저장 완료")
        return saved

    # ------------------------------------------------------------------
    # 2단계: dataset.yaml 생성 + train/val 분할
    # ------------------------------------------------------------------

    def prepare_dataset_yaml(self) -> Path:
        """프리트레인용 dataset.yaml 생성 (PRETRAIN_CLASSES 사용).

        DatasetManager.save_dataset_yaml() 은 OLED_CLASSES를 사용하므로
        여기서는 PRETRAIN_CLASSES로 별도 생성한다.
        """
        # train/val 분할 실행
        split_train_val(
            self.output_dir, val_ratio=self.cfg.val_ratio, seed=self.cfg.random_seed
        )

        yaml_path = self.output_dir / "pretrain_dataset.yaml"
        train_path = (self.output_dir / "train" / "images").resolve()
        val_path = (self.output_dir / "val" / "images").resolve()
        content = (
            f"path: {self.output_dir.resolve()}\n"
            f"train: {train_path}\n"
            f"val: {val_path}\n"
            f"nc: {len(PRETRAIN_CLASSES)}\n"
            f"names: {json.dumps(PRETRAIN_CLASSES, ensure_ascii=False)}\n"
        )
        yaml_path.write_text(content, encoding="utf-8")
        print(f"[PretrainPipeline] dataset.yaml 생성 → {yaml_path}")
        return yaml_path

    # ------------------------------------------------------------------
    # 3단계: 학습 + 평가
    # ------------------------------------------------------------------

    def train_and_evaluate(
        self,
        epochs: Optional[int] = None,
        batch: Optional[int] = None,
        progress_cb: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """프리트레인 학습 실행 후 mAP50 평가.

        Parameters
        ----------
        epochs:      학습 에포크 수 (기본: cfg.epochs).
        batch:       배치 크기 (기본: cfg.batch).
        progress_cb: (epoch, total) 콜백.

        Returns
        -------
        {
          "map50": float,
          "map50_95": float,
          "precision": float,
          "recall": float,
          "classes": {cls: map50_per_class},
          "weights": str,
          "epochs": int,
          "n_train": int,
          "n_val": int,
          "elapsed_sec": float,
        }
        """
        from ultralytics import YOLO  # noqa: PLC0415

        epochs = epochs or self.cfg.epochs
        batch = batch or self.cfg.batch

        # 데이터셋 준비
        if self._image_count() == 0:
            raise RuntimeError(
                "데이터셋이 비어 있습니다. build_*_dataset() 먼저 실행하세요."
            )

        yaml_path = self.prepare_dataset_yaml()

        # 이미지 수 카운트
        n_train = len(list((self.output_dir / "train" / "images").glob("*.png")))
        n_val = len(list((self.output_dir / "val" / "images").glob("*.png")))
        print(
            f"[PretrainPipeline] 학습 시작 — train:{n_train}, val:{n_val}, epochs:{epochs}"
        )

        t0 = time.perf_counter()

        # 시작 가중치: 기존 프리트레인 파일 있으면 이어서, 없으면 COCO base
        start_weights = (
            str(self.cfg.pretrained_weights)
            if self.cfg.pretrained_weights.exists()
            else self.cfg.base_model
        )
        model = YOLO(start_weights)

        if progress_cb is not None:

            def _cb(trainer: object) -> None:  # noqa: ANN001
                epoch = getattr(trainer, "epoch", 0) + 1
                progress_cb(epoch, epochs)

            model.add_callback("on_train_epoch_end", _cb)

        train_results = model.train(
            data=str(yaml_path),
            epochs=epochs,
            imgsz=self.cfg.image_size,
            batch=batch,
            device=self.cfg.device,
            verbose=False,
            plots=False,
        )

        # 최적 가중치 복사
        best_pt = self._find_best_weights(train_results)
        if best_pt and best_pt.exists():
            import shutil

            self.cfg.pretrained_weights.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_pt, self.cfg.pretrained_weights)
            print(f"[PretrainPipeline] 가중치 저장 → {self.cfg.pretrained_weights}")

        # 검증 (mAP50 측정)
        val_model = YOLO(str(self.cfg.pretrained_weights))
        val_results = val_model.val(
            data=str(yaml_path),
            imgsz=self.cfg.image_size,
            batch=batch,
            device=self.cfg.device,
            verbose=False,
            plots=False,
        )

        elapsed = time.perf_counter() - t0

        metrics = self._extract_metrics(val_results, elapsed, n_train, n_val, epochs)
        return metrics

    # ------------------------------------------------------------------
    # 4단계: 리포트 저장
    # ------------------------------------------------------------------

    def save_report(self, metrics: Dict[str, Any], path: Optional[Path] = None) -> Path:
        """mAP50 결과를 PRETRAIN_REPORT.md로 저장.

        Parameters
        ----------
        metrics: train_and_evaluate() 반환값.
        path:    저장 경로 (기본: 프로젝트 루트/PRETRAIN_REPORT.md).

        Returns
        -------
        저장된 파일 경로.
        """
        report_path = path or Path("PRETRAIN_REPORT.md")

        map50 = metrics.get("map50", 0.0)
        map50_95 = metrics.get("map50_95", 0.0)
        precision = metrics.get("precision", 0.0)
        recall = metrics.get("recall", 0.0)
        n_train = metrics.get("n_train", 0)
        n_val = metrics.get("n_val", 0)
        epochs = metrics.get("epochs", 0)
        elapsed = metrics.get("elapsed_sec", 0.0)
        weights = metrics.get("weights", "N/A")
        classes_map = metrics.get("classes", {})

        lines = [
            "# YOLO26x Pretrain Report",
            "",
            f"생성일: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"베이스 모델: `{self.cfg.base_model}` (COCO pretrained)",
            f"출력 가중치: `{weights}`",
            "",
            "## 데이터셋 요약",
            "",
            "| 구분 | 이미지 수 |",
            "|------|-----------|",
            f"| 학습 | {n_train} |",
            f"| 검증 | {n_val} |",
            f"| 합계 | {n_train + n_val} |",
            "",
            "## 평가 지표 (검증 세트)",
            "",
            "| 지표 | 값 |",
            "|------|-----|",
            f"| **mAP50** | **{map50:.4f}** |",
            f"| mAP50-95 | {map50_95:.4f} |",
            f"| Precision | {precision:.4f} |",
            f"| Recall | {recall:.4f} |",
            f"| Epochs | {epochs} |",
            f"| 학습 시간 | {elapsed:.1f}s ({elapsed/60:.1f}분) |",
            "",
        ]

        if classes_map:
            lines += [
                "## 클래스별 mAP50",
                "",
                "| 클래스 | mAP50 |",
                "|--------|-------|",
            ]
            for cls_name, cls_map50 in sorted(classes_map.items(), key=lambda x: -x[1]):
                lines.append(f"| {cls_name} | {cls_map50:.4f} |")
            lines.append("")

        lines += [
            "## 프리트레인 클래스 어휘 → OLED 파인튜닝 매핑",
            "",
            "| 프리트레인 클래스 | OLED 12클래스 매핑 |",
            "|-------------------|---------------------|",
            "| button | login_button, apply_button, save_button, register_button, recipe_button |",
            "| icon | open_icon, axis_mark |",
            "| label | mold_left_label, mold_right_label |",
            "| connector | connector_pin, pin_cluster |",
            "| input_field | (파인튜닝 시 조정) |",
            "| checkbox | (파인튜닝 시 조정) |",
            "| dropdown | (파인튜닝 시 조정) |",
            "",
            "## 다음 단계",
            "",
            "1. `assets/models/yolo26x_pretrained.pt` → OLED 라인 파인튜닝 시작 가중치로 사용",
            "2. GUI Tab7 Training Panel에서 `기반 모델: yolo26x_pretrained.pt` 선택",
            "3. OLED 스크린샷 + 어노테이션 수집 후 로컬 파인튜닝 실행",
        ]

        report_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"[PretrainPipeline] 리포트 저장 → {report_path}")
        return report_path

    # ------------------------------------------------------------------
    # 내부 헬퍼: 프리트레인 전용 이미지/레이블 저장
    # ------------------------------------------------------------------

    def _save_pretrain_sample(
        self,
        stem: str,
        img: Any,
        anns: list,
    ) -> None:
        """PRETRAIN_CLASSES 인덱스로 YOLO 레이블을 직접 기록.

        DatasetManager._label_to_id()는 OLED_CLASSES 기준이므로
        PRETRAIN_CLASSES 레이블을 인식하지 못한다.
        이 메서드는 PRETRAIN_CLASSES를 기준으로 class_id를 결정하고
        images/ labels/ 에 직접 저장한다.
        """
        import cv2  # noqa: PLC0415

        img_path = self._images_dir / f"{stem}.png"
        lbl_path = self._labels_dir / f"{stem}.txt"

        cv2.imwrite(str(img_path), img)

        h, w = img.shape[:2]
        lines = []
        for ann in anns:
            label = ann.get("label", "")
            if label not in PRETRAIN_CLASSES:
                continue
            class_id = PRETRAIN_CLASSES.index(label)
            x1, y1, x2, y2 = [float(v) for v in ann["bbox"][:4]]
            cx = (x1 + x2) / 2.0 / w
            cy = (y1 + y2) / 2.0 / h
            bw = abs(x2 - x1) / w
            bh = abs(y2 - y1) / h
            lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        lbl_path.write_text("\n".join(lines), encoding="utf-8")

    def _image_count(self) -> int:
        """images/ 디렉터리의 이미지 수 반환."""
        return len(list(self._images_dir.glob("*.png")))

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _find_best_weights(self, results: object) -> Optional[Path]:
        save_dir = getattr(results, "save_dir", None)
        if save_dir is not None:
            best = Path(save_dir) / "weights" / "best.pt"
            if best.exists():
                return best
        for candidate in Path("runs").rglob("best.pt"):
            return candidate
        return None

    def _extract_metrics(
        self,
        val_results: object,
        elapsed: float,
        n_train: int,
        n_val: int,
        epochs: int,
    ) -> Dict[str, Any]:
        """ultralytics val() 결과 → 표준 metrics dict."""
        box = getattr(val_results, "box", None)

        def _safe(attr: str, default: float = 0.0) -> float:
            if box is None:
                return default
            val = getattr(box, attr, None)
            if val is None:
                return default
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        # 클래스별 mAP50
        classes_map: Dict[str, float] = {}
        if box is not None:
            maps = getattr(box, "maps", None)  # per-class mAP50-95
            ap50 = getattr(box, "ap50", None)  # per-class mAP50
            names = getattr(val_results, "names", {})
            per_class = ap50 if ap50 is not None else maps
            if per_class is not None and hasattr(per_class, "__iter__"):
                for i, v in enumerate(per_class):
                    cls_name = names.get(
                        i, PRETRAIN_CLASSES[i] if i < len(PRETRAIN_CLASSES) else str(i)
                    )
                    try:
                        classes_map[cls_name] = float(v)
                    except (TypeError, ValueError):
                        classes_map[cls_name] = 0.0

        return {
            "map50": _safe("map50"),
            "map50_95": _safe("map"),
            "precision": _safe("mp"),
            "recall": _safe("mr"),
            "classes": classes_map,
            "weights": str(self.cfg.pretrained_weights),
            "epochs": epochs,
            "n_train": n_train,
            "n_val": n_val,
            "elapsed_sec": elapsed,
        }
