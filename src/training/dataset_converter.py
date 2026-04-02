"""
공개 데이터셋 → YOLO 형식 변환기.

YOLO26x 프리트레인용 7클래스 공용 어휘(PRETRAIN_CLASSES)를 정의하고,
각 공개 데이터셋의 클래스를 이 어휘로 매핑한다.

지원 데이터셋:
- showui_desktop: showlab/ShowUI-desktop (HuggingFace, OmniAct 기반 데스크탑)
                  Windows/Mac/Linux 데스크탑 15개 앱 실제 스크린샷 + bbox
- rico_widget:    rootsautomation/RICO-WidgetCaptioning (HuggingFace, Android)
                  레거시 지원용. 구형 Windows 라인PC 환경에는 부적합.
- synthetic:      SyntheticGUIGenerator (테스트/시연용 합성 데이터)

프리트레인 7클래스 → OLED 12클래스 파인튜닝 매핑:
  button    → login_button, apply_button, save_button, register_button, recipe_button
  icon      → open_icon, axis_mark
  label     → mold_left_label, mold_right_label
  connector → connector_pin, pin_cluster
  input_field, checkbox, dropdown → 범용 GUI 요소 (파인튜닝 시 조정)
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# 프리트레인 클래스 어휘 (6개 고정)
# ---------------------------------------------------------------------------
PRETRAIN_CLASSES: List[str] = [
    "oled_inspection_top_view",        # 0
    "connector_pin_cluster_upper",     # 1
    "connector_pin_cluster_lower",     # 2
    "connector_pin_mold_left",         # 3
    "connector_pin_mold_right",        # 4
    "oled_panel_marker",               # 5
]

# ---------------------------------------------------------------------------
# ShowUI-Desktop (OmniAct 기반) 변환기
# Windows/Mac/Linux 데스크탑 앱 실제 스크린샷 — 구형 Windows GUI에 적합
# ---------------------------------------------------------------------------

# OmniAct Desktop 위젯 타입 → PRETRAIN_CLASSES 인덱스
# OmniAct 15종: button, checkbox, combobox, editbox, link, menu, menuitem,
#               pane, radiobutton, scrollbar, slider, statictext, tab, toolbar, treeitem
_OMNIACT_CLASS_MAP: Dict[str, int] = {
    # oled_inspection_top_view variants (class 0)
    "button": 0,
    "menuitem": 0,
    "menu": 0,
    "toolbar": 0,
    "tab": 0,
    "treeitem": 0,
    "radiobutton": 0,
    "link": 0,
    "splitbutton": 0,
    "editbox": 0,
    "textbox": 0,
    "inputfield": 4,
    "input_field": 4,

    # connector_pin_cluster_upper variants (class 1)
    "image": 1,
    "icon": 1,
    "picture": 1,

    # connector_pin_cluster_lower variants (class 2)
    "statictext": 2,
    "text": 2,
    "label": 2,
    "header": 2,
    "pane": 2,
    "title": 2,

    # connector_pin_mold_left (class 3)
    "connector": 3,
    "pin": 3,
    "pincluster": 3,

    # connector_pin_mold_right (class 4)
    "panel": 4,
    "mold": 4,
    "combobox": 4,
    "dropdown": 4,
    "listbox": 4,
    "spinner": 4,
    "slider": 4,

    # oled_panel_marker (class 5)
    "marker": 5,
    "labelmarker": 5,
    "checkbox": 5,
    "switch": 5,
    "toggle": 5,
}

# 설명 텍스트에서 element type 키워드 탐지용 (순서 중요 — 더 구체적인 것 먼저)
_KEYWORD_CLASS_MAP: List[Tuple[str, int]] = [
    ("connector", 3),
    ("pin", 3),
    ("cluster", 3),
    ("mold", 4),
    ("panel", 4),
    ("marker", 5),
    ("input", 4),
    ("label", 2),
    ("text", 2),
    ("icon", 1),
    ("image", 1),
    ("button", 0),
    ("menuitem", 0),
    ("menu", 0),
    ("toolbar", 0),
    ("tab", 0),
    ("link", 0),
]


def map_omniact_class(element_type: str) -> Optional[int]:
    """OmniAct/ShowUI element type → PRETRAIN_CLASSES 인덱스.

    element_type이 정확히 일치하지 않으면 소문자 키워드 검색으로 폴백.
    """
    key = element_type.lower().strip()
    if key in _OMNIACT_CLASS_MAP:
        return _OMNIACT_CLASS_MAP[key]
    # 부분 일치 키워드 검색
    for kw, cls_id in _KEYWORD_CLASS_MAP:
        if kw in key:
            return cls_id
    return None


def convert_showui_desktop_sample(
    sample: Dict[str, Any],
    min_box_size: float = 0.01,
) -> Tuple[Optional[np.ndarray], List[Dict[str, Any]]]:
    """showlab/ShowUI-desktop 샘플 → (BGR image, annotations).

    showlab/ShowUI-desktop는 OmniAct Desktop 기반.
    Windows/Mac/Linux 데스크탑 15개 앱 실제 스크린샷.

    Parameters
    ----------
    sample:       HuggingFace 데이터셋 샘플 dict.
    min_box_size: 최소 bbox 크기 (상대좌표, 0~1). 너무 작은 요소 제외.

    Returns
    -------
    (BGR ndarray, annotations)
    annotations: [{"label": str, "bbox": [x1, y1, x2, y2]}, ...]  (픽셀 절대좌표)
    이미지 로드 실패 시 (None, []) 반환.

    Notes
    -----
    bbox 형식: ShowUI-desktop은 상대좌표 [top_left_x, top_left_y, width, height] 또는
    [x1, y1, x2, y2] 형식을 사용. 두 형식 모두 처리.
    """
    # 이미지 로드 (여러 컬럼명 시도)
    pil_img = sample.get("image") or sample.get("screenshot") or sample.get("img")
    if pil_img is None:
        return None, []

    try:
        img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception:
        return None, []
    h, w = img_bgr.shape[:2]

    # bbox 추출 (여러 컬럼명 시도)
    raw_bbox = (
        sample.get("bbox")
        or sample.get("bounding_box")
        or sample.get("coordinates")
        or sample.get("box")
    )
    if raw_bbox is None:
        return img_bgr, []

    # bbox 파싱 (list/str/dict)
    if isinstance(raw_bbox, str):
        try:
            raw_bbox = json.loads(raw_bbox)
        except json.JSONDecodeError:
            return img_bgr, []

    # element type 추출 (여러 컬럼명 시도)
    elem_type = (
        sample.get("element_type")
        or sample.get("type")
        or sample.get("widget_type")
        or sample.get("element")
        or sample.get("element_name")
        or ""
    )
    if not isinstance(elem_type, str):
        elem_type = str(elem_type)

    class_id = map_omniact_class(elem_type)
    if class_id is None:
        class_id = 0  # 알 수 없는 타입은 button(0)으로 폴백

    annotations: List[Dict[str, Any]] = []

    # bbox 형식 자동 감지: [x1,y1,x2,y2] vs [tx,ty,w,h]
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
        coords = [float(v) for v in raw_bbox]
        # 값이 0~1 사이면 상대좌표
        if all(0 <= c <= 1 for c in coords):
            tx, ty, bw, bh = coords
            # w,h 형식인지 x2,y2 형식인지 판별 (w<1 기준으로 상대좌표 [tl_x,tl_y,w,h])
            # ShowUI: [top_left_x, top_left_y, width, height] in [0,1]
            if bw <= 1 and bh <= 1:  # [tl_x, tl_y, w, h] 상대좌표
                x1 = tx * w
                y1 = ty * h
                x2 = (tx + bw) * w
                y2 = (ty + bh) * h
            else:  # [x1,y1,x2,y2] 상대좌표
                x1 = tx * w
                y1 = ty * h
                x2 = bw * w
                y2 = bh * h
        else:
            # 절대 픽셀 좌표 [x1,y1,x2,y2] 또는 [x1,y1,w,h]
            tx, ty, bw, bh = coords
            if bw < w and bh < h and (tx + bw) <= w and (ty + bh) <= h:
                # [x1,y1,w,h] 픽셀
                x1, y1 = tx, ty
                x2, y2 = tx + bw, ty + bh
            else:
                # [x1,y1,x2,y2] 픽셀
                x1, y1, x2, y2 = tx, ty, bw, bh

        box_w_rel = abs(x2 - x1) / w
        box_h_rel = abs(y2 - y1) / h
        if box_w_rel >= min_box_size and box_h_rel >= min_box_size:
            annotations.append(
                {
                    "label": PRETRAIN_CLASSES[class_id],
                    "bbox": [
                        max(0.0, min(w, x1)),
                        max(0.0, min(h, y1)),
                        max(0.0, min(w, x2)),
                        max(0.0, min(h, y2)),
                    ],
                }
            )

    return img_bgr, annotations


# Android 위젯 클래스 이름 → PRETRAIN_CLASSES 인덱스
_ANDROID_CLASS_MAP: Dict[str, int] = {
    # button variants
    "Button": 0,
    "ImageButton": 0,
    "FloatingActionButton": 0,
    "AppCompatButton": 0,
    "MaterialButton": 0,
    # icon/image variants
    "ImageView": 1,
    "AppCompatImageView": 1,
    "ShapeableImageView": 1,
    # label/text variants
    "TextView": 2,
    "AppCompatTextView": 2,
    "MaterialTextView": 2,
    # input variants
    "EditText": 4,
    "AppCompatEditText": 4,
    "TextInputEditText": 4,
    # checkbox/toggle variants
    "CheckBox": 5,
    "Switch": 5,
    "AppCompatCheckBox": 5,
    "ToggleButton": 5,
    # dropdown/spinner variants
    "Spinner": 6,
    "AutoCompleteTextView": 6,
}


def map_android_class(full_class_name: str) -> Optional[int]:
    """Android 위젯 풀 클래스명 → PRETRAIN_CLASSES 인덱스 (매핑 없으면 None)."""
    short = full_class_name.split(".")[-1]
    return _ANDROID_CLASS_MAP.get(short)


# ---------------------------------------------------------------------------
# Rico WidgetCaptioning 변환기
# ---------------------------------------------------------------------------


def convert_rico_sample(
    sample: Dict[str, Any],
    min_box_size: int = 20,
) -> Tuple[Optional[np.ndarray], List[Dict[str, Any]]]:
    """Rico WidgetCaptioning 샘플 → (BGR image, annotations).

    Parameters
    ----------
    sample:        HuggingFace 데이터셋 샘플 dict.
    min_box_size:  픽셀 단위 최소 bbox 크기 (너무 작은 요소 제외).

    Returns
    -------
    (BGR ndarray, annotations)
    annotations 형식: [{"label": "button", "bbox": [x1, y1, x2, y2]}, ...]
    이미지 로드 실패 시 (None, []) 반환.
    """
    pil_img = sample.get("image")
    if pil_img is None:
        return None, []

    img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    h, w = img_bgr.shape[:2]

    raw_ann = sample.get("semantic_annotations", "{}")
    if isinstance(raw_ann, str):
        try:
            tree = json.loads(raw_ann)
        except json.JSONDecodeError:
            return img_bgr, []
    else:
        tree = raw_ann

    annotations: List[Dict[str, Any]] = []
    _collect_rico_nodes(tree, annotations, w, h, min_box_size, depth=0)
    return img_bgr, annotations


def _collect_rico_nodes(
    node: Dict[str, Any],
    out: List[Dict[str, Any]],
    img_w: int,
    img_h: int,
    min_size: int,
    depth: int,
) -> None:
    if depth > 10:
        return

    bounds = node.get("bounds")
    full_cls = node.get("class", "")
    if bounds and len(bounds) == 4:
        x1, y1, x2, y2 = bounds
        bw, bh = x2 - x1, y2 - y1
        # 전체 화면 크기와 동일한 루트 bbox 제외
        if (
            bw >= min_size
            and bh >= min_size
            and not (x1 == 0 and y1 == 0 and x2 == img_w)
        ):
            class_id = map_android_class(full_cls)
            if class_id is not None:
                out.append(
                    {
                        "label": PRETRAIN_CLASSES[class_id],
                        "bbox": [
                            max(0, x1),
                            max(0, y1),
                            min(img_w, x2),
                            min(img_h, y2),
                        ],
                    }
                )

    for child in node.get("children", []):
        _collect_rico_nodes(child, out, img_w, img_h, min_size, depth + 1)


# ---------------------------------------------------------------------------
# 합성 GUI 데이터 생성기 (테스트 및 파이프라인 시연용)
# ---------------------------------------------------------------------------
# ⛔ DEPRECATED: Synthetic GUI Generator (2026-04-01)
# ---------------------------------------------------------------------------
# Synthetic 데이터셋은 더 이상 Pretrain에 사용되지 않습니다.
# 대신 Tier A 실사 데이터셋 (MSD/SSGD/DeepPCB/Roboflow)을 사용하세요.
#
# SyntheticGUIGenerator는 테스트 목적으로만 유지됩니다 (폐기 예정).
# ---------------------------------------------------------------------------


class SyntheticGUIGenerator:
    """⛔ DEPRECATED: 테스트·시연용 합성 GUI 생성기 (더 이상 pretrain에 사용되지 않음)."""

    # 요소별 색상 (BGR) - 테스트 목적만
    _COLORS = {
        "button": (50, 120, 200),
        "icon": (80, 180, 80),
        "label": (180, 180, 60),
        "connector": (200, 80, 80),
        "input_field": (200, 200, 200),
        "checkbox": (120, 80, 200),
        "dropdown": (180, 120, 50),
    }

    def __init__(self, seed: int = 42) -> None:
        import warnings
        warnings.warn(
            "SyntheticGUIGenerator is deprecated and no longer used for pretrain. "
            "Use real datasets (MSD/SSGD/DeepPCB/Roboflow) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._rng = random.Random(seed)

    def generate(
        self,
        width: int = 1280,
        height: int = 800,
        n_elements: int = 8,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """⛔ DEPRECATED: 합성 화면 생성 (테스트 목적만)."""
        img = np.full((height, width, 3), 240, dtype=np.uint8)

        cols = 4
        cell_w = width // cols
        cell_h = height // (n_elements // cols + 1)

        annotations: List[Dict[str, Any]] = []
        classes = list(self._COLORS.keys())

        for idx in range(n_elements):
            col = idx % cols
            row = idx // cols
            cx = col * cell_w + cell_w // 2
            cy = row * cell_h + cell_h // 2

            cls = classes[idx % len(classes)]
            bw = self._rng.randint(60, cell_w - 20)
            bh = self._rng.randint(30, cell_h - 20)

            x1 = max(0, cx - bw // 2)
            y1 = max(0, cy - bh // 2)
            x2 = min(width, x1 + bw)
            y2 = min(height, y1 + bh)

            color = self._COLORS[cls]
            cv2.rectangle(img, (x1, y1), (x2, y2), color, -1)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), 1)
            cv2.putText(
                img,
                cls[:8],
                (x1 + 4, y1 + (y2 - y1) // 2 + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
            )

            class_index = map_omniact_class(cls) if isinstance(cls, str) else None
            if class_index is None:
                class_index = 0
            annotations.append({"label": PRETRAIN_CLASSES[class_index], "bbox": [x1, y1, x2, y2]})

        return img, annotations

    def generate_batch(
        self,
        n_images: int = 100,
        width: int = 1280,
        height: int = 800,
    ) -> List[Tuple[np.ndarray, List[Dict[str, Any]]]]:
        """n_images 장 합성 데이터 배치 생성."""
        return [
            self.generate(width, height, n_elements=self._rng.randint(4, 12))
            for _ in range(n_images)
        ]


# ---------------------------------------------------------------------------
# Train/Val 분할 유틸
# ---------------------------------------------------------------------------


def split_train_val(
    dataset_dir: Path,
    val_ratio: float = 0.2,
    seed: int = 42,
) -> Tuple[Path, Path]:
    """images/ labels/ 를 train/ val/ 서브디렉터리로 분할.

    Parameters
    ----------
    dataset_dir: DatasetManager가 생성한 루트 디렉터리.
    val_ratio:   검증 세트 비율 (0~1).
    seed:        재현성을 위한 랜덤 시드.

    Returns
    -------
    (train_dir, val_dir) — 각각 images/, labels/ 서브디렉터리 포함.
    """
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"

    image_files = [
        p
        for p in images_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}
    ]
    image_file_map = {p.stem: p for p in image_files}
    all_stems = sorted(
        p.stem
        for p in image_files
        if (labels_dir / f"{p.stem}.txt").exists()
    )
    rng = random.Random(seed)
    rng.shuffle(all_stems)

    n_val = max(1, int(len(all_stems) * val_ratio))
    val_stems = set(all_stems[:n_val])
    train_stems = set(all_stems[n_val:])

    for split_name, stems in [("train", train_stems), ("val", val_stems)]:
        split_dir = dataset_dir / split_name
        (split_dir / "images").mkdir(parents=True, exist_ok=True)
        (split_dir / "labels").mkdir(parents=True, exist_ok=True)

        for stem in stems:
            src_img = image_file_map.get(stem)
            src_lbl = labels_dir / f"{stem}.txt"
            if src_img is None:
                continue
            dst_img = split_dir / "images" / src_img.name
            dst_lbl = split_dir / "labels" / f"{stem}.txt"
            if not dst_img.exists():
                import shutil

                shutil.copy2(src_img, dst_img)
                shutil.copy2(src_lbl, dst_lbl)

    return dataset_dir / "train", dataset_dir / "val"
