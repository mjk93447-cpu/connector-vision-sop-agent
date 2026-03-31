from __future__ import annotations

from pathlib import Path

from src.training.annotation_queue import AnnotationQueue


class TestAnnotationQueue:
    def test_load_filters_and_deduplicates_images(self, tmp_path: Path) -> None:
        paths = [
            tmp_path / "b.png",
            tmp_path / "a.jpg",
            tmp_path / "b.png",
            tmp_path / "ignore.txt",
        ]
        for p in paths[:2]:
            p.write_bytes(b"data")

        q = AnnotationQueue()
        count = q.load(paths)

        assert count == 2
        assert q.position() == (1, 2)
        assert q.current() is not None
        assert q.current().name == "a.jpg"

    def test_navigation_moves_through_queue(self, tmp_path: Path) -> None:
        for name in ("a.png", "b.png", "c.png"):
            (tmp_path / name).write_bytes(b"data")

        q = AnnotationQueue()
        q.load([tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"])
        assert q.current().name == "a.png"
        assert q.next().name == "b.png"
        assert q.next().name == "c.png"
        assert q.next().name == "c.png"
        assert q.prev().name == "b.png"
