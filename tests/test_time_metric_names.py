"""A metric is judged as a time metric by the words of its name, not by letters inside other words (#447)."""

import pytest

from src.scoring import Tier2MetricsEvaluator, is_time_metric


@pytest.mark.parametrize("name", ["rmse", "RMSE", "num_params", "n_items", "terms", "arms_pulled", "forms", "alarms"])
def test_a_name_that_only_contains_the_letters_ms_is_not_a_time_metric(name):
    # claimed 0.5, reproduced 0.54: 8 % relative error, but 0.04 absolute for a value between 0 and 1 (matches under the rate rule)
    _, details, _ = Tier2MetricsEvaluator.evaluate({name: 0.5}, {name: 0.54})
    assert is_time_metric(name) is False
    assert details[name]["matches"] is True


@pytest.mark.parametrize("name", ["inference_latency_sec", "latency_ms", "inferenceMs", "runtime", "training_time", "wall_time_s",
                                  "duration", "tune_train_predict_seconds", "fit_secs", "ms_per_epoch", "msec"])
def test_the_names_of_real_time_metrics_still_use_the_relative_rule_only(name):
    _, details, _ = Tier2MetricsEvaluator.evaluate({name: 0.5}, {name: 0.54})
    assert is_time_metric(name) is True
    assert details[name]["matches"] is False and details[name]["points"] == 0.5  # 8 % is within 2 x 5 %
