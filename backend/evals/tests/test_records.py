"""RunRecord JSONL round-trip and schema-version enforcement."""

import json

import pytest

from evals.records import CallMetrics, RunRecord, append_records, read_records


def _record() -> RunRecord:
    record = RunRecord(
        scenario="generation",
        arm="grounded",
        model_eval_id="deepseek-v4-flash",
        provider="deepseek",
        model="deepseek-v4-flash",
        config={"batch_size": 30, "trial": 0},
    )
    record.calls = [
        CallMetrics(kind="chat", model="deepseek-v4-flash", latency_ms=1200)
    ]
    record.success = True
    return record


def test_jsonl_round_trip(tmp_path):
    path = tmp_path / "runs.jsonl"
    append_records(path, [_record(), _record()])
    rows = read_records(path)
    assert len(rows) == 2
    assert rows[0]["scenario"] == "generation"
    assert rows[0]["calls"][0]["latency_ms"] == 1200
    assert rows[0]["fingerprint"]["pricing_as_of"]


def test_unknown_schema_version_fails_loud(tmp_path):
    path = tmp_path / "runs.jsonl"
    row = json.loads(_record().to_json())
    row["schema_version"] = 99
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="schema_version"):
        read_records(path)
