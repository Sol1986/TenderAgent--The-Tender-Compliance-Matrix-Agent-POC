"""The dashboard's live runner calls the package matrix workflow."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dashboard.api import runner
from dashboard.api.config import Settings
from dashboard.api.store import RunStore


def test_live_runner_produces_one_run_scoped_excel_file(
    tmp_path: Path, monkeypatch: Any
) -> None:
    settings = Settings(sample_path=tmp_path / "package", output_root=tmp_path / "runs")
    settings.sample_path.mkdir()
    (settings.sample_path / "tender.pdf").write_bytes(b"%PDF-sample")
    store = RunStore(settings)
    monkeypatch.setattr("langchain_openai.ChatOpenAI", lambda **_kwargs: object())
    monkeypatch.setattr(runner, "matrix_requirements", lambda _report: list(range(18)))

    def package_pipeline(**kwargs: Any) -> SimpleNamespace:
        assert kwargs["package_path"] == settings.sample_path
        kwargs["observe"]("stage.started", stage="extract", summary="Extracting.")
        kwargs["observe"]("stage.completed", stage="extract", summary="Extracted.")
        output = kwargs["spreadsheet_output_path"]
        output.parent.mkdir(parents=True)
        output.write_bytes(b"xlsx")
        return SimpleNamespace()

    monkeypatch.setattr(runner, "run_compliance_solicitation_package", package_pipeline)
    executor = runner.RunExecutor(settings, store)
    try:
        run_id = store.create("one")[0].run_id
        executor._execute(run_id)
        snapshot = store.snapshot(run_id)
        assert snapshot.status == "completed"
        assert snapshot.metrics.final_requirements == 18
        assert store.download_path(run_id).read_bytes() == b"xlsx"
    finally:
        executor.close()
