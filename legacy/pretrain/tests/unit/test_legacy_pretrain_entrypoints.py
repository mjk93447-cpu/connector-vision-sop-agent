from __future__ import annotations

import pytest

import legacy.pretrain.run_pretrain as run_pretrain
import legacy.pretrain.run_pretrain_compact as run_pretrain_compact


@pytest.mark.parametrize(
    "module",
    [run_pretrain, run_pretrain_compact],
)
def test_legacy_pretrain_entrypoints_fail_with_clear_deprecation_message(
    module, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "DEPRECATED" in captured.out
    assert "run_pretrain_local.py" in captured.out
