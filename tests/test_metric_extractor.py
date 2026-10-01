"""Unit tests for MetricExtractor log parsing, JSON extraction, and sklearn report parsing."""

import json

from src.metric_extractor import MetricExtractor


def test_normalize_metric_names():
    extractor = MetricExtractor()

    assert extractor.normalize_metric_name("acc") == "accuracy"
    assert extractor.normalize_metric_name("test_acc") == "accuracy"
    assert extractor.normalize_metric_name("val_accuracy") == "accuracy"
    assert extractor.normalize_metric_name("roc_auc") == "auroc"
    assert extractor.normalize_metric_name("test_auc") == "auroc"
    assert extractor.normalize_metric_name("macro_f1") == "f1"
    assert extractor.normalize_metric_name("eval_loss") == "loss"
    assert extractor.normalize_metric_name("latency_ms") == "latency_ms"
    assert extractor.normalize_metric_name("inference_time") == "latency_ms"


def test_normalize_values():
    extractor = MetricExtractor()

    # Percentage string conversion
    assert extractor.normalize_value("accuracy", "95.5%") == 0.955
    # Bounded rate automatic scaling
    assert extractor.normalize_value("accuracy", "94.2") == 0.942
    assert extractor.normalize_value("accuracy", "0.942") == 0.942
    # Unbounded metrics should not be scaled down
    assert extractor.normalize_value("latency_ms", "24.5") == 24.5
    assert extractor.normalize_value("loss", "1.854") == 1.854


def test_extract_from_json():
    extractor = MetricExtractor()

    sample_log = (
        "Starting evaluation epoch 5...\n"
        "{'eval_loss': 0.1824, 'eval_accuracy': 0.9512, 'eval_runtime': 14.2}\n"
        "Evaluation finished.\n"
    )

    metrics = extractor.extract_metrics(sample_log)
    assert metrics["loss"] == 0.1824
    assert metrics["accuracy"] == 0.9512
    assert metrics["latency_ms"] == 14.2


def test_extract_from_sklearn_report():
    extractor = MetricExtractor()

    sample_report = """
              precision    recall  f1-score   support

           0       0.85      0.82      0.83        50
           1       0.78      0.89      0.83        50

    accuracy                           0.84       100
   macro avg       0.82      0.86      0.83       100
weighted avg       0.82      0.86      0.83       100
"""

    metrics = extractor.extract_metrics(sample_report)
    assert metrics["accuracy"] == 0.84
    assert metrics["f1"] == 0.83
    assert metrics["precision"] == 0.82
    assert metrics["recall"] == 0.86


def test_extract_from_framework_and_regex_logs():
    extractor = MetricExtractor()

    sample_log = """
[INFO] Loading checkpoint model.pt
[100] valid_0's auc: 0.8950
[200] valid_0's auc: 0.9125
Epoch 10: train_loss: 0.354, val_loss: 0.215
Final Test Results:
Test Accuracy: 93.8%
F1-Score: 0.931
Inference latency: 15.4ms
Throughput: 340.5
"""

    metrics = extractor.extract_metrics(sample_log)
    assert metrics["auroc"] == 0.9125
    assert metrics["accuracy"] == 0.938
    assert metrics["f1"] == 0.931
    assert metrics["latency_ms"] == 15.4
    assert metrics["throughput"] == 340.5


def test_extract_from_run_dir(tmp_path):
    extractor = MetricExtractor()
    run_dir = tmp_path / "run_output"
    run_dir.mkdir()

    # Write a stdout log file
    stdout_file = run_dir / "stdout.log"
    stdout_file.write_text(
        "Training finished.\n"
        "Accuracy: 0.9450\n"
        "Loss: 0.1230\n",
        encoding="utf-8",
    )

    metrics = extractor.extract_from_run_dir(run_dir)
    assert metrics["accuracy"] == 0.945
    assert metrics["loss"] == 0.123

    # Check that extracted_metrics.json was persisted
    saved_file = run_dir / "extracted_metrics.json"
    assert saved_file.exists()
    saved_data = json.loads(saved_file.read_text(encoding="utf-8"))
    assert saved_data["accuracy"] == 0.945


def test_extract_from_json_logs_unparseable_blocks(caplog):
    """Brace blocks that are not JSON are skipped with a debug trace, not silently."""
    extractor = MetricExtractor()
    text = "epoch done {not json at all} then {'accuracy': 0.91}"

    with caplog.at_level("DEBUG", logger="src.metric_extractor"):
        metrics = extractor.extract_from_json(text)

    assert [m.canonical_name for m in metrics] == ["accuracy"]
    assert any("not json at all" in r.getMessage() for r in caplog.records)