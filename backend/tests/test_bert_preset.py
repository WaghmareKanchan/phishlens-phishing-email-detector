"""BERT preset download: avoid the keras-hub Windows backslash bug by fetching the whole folder."""
import pytest

pytest.importorskip("keras_hub")


def test_preset_is_downloaded_as_one_folder_without_file_paths(monkeypatch, tmp_path):
    import kagglehub
    from ml_training.keras_models import _local_preset
    calls = []
    monkeypatch.setattr(kagglehub, "model_download", lambda *a, **k: calls.append((a, k)) or str(tmp_path))
    assert _local_preset("bert_tiny_en_uncased") == str(tmp_path)
    (args, kwargs), = calls
    assert len(args) == 1 and not kwargs                       # whole folder: NO per-file path argument
    assert args[0].startswith("keras/bert/keras/bert_tiny_en_uncased")   # 'kaggle://' prefix removed


def test_local_folder_and_none_are_left_alone(tmp_path):
    from ml_training.keras_models import _local_preset
    assert _local_preset(str(tmp_path)) == str(tmp_path)
    assert _local_preset(None) is None


def test_falls_back_to_normal_download_when_prefetch_fails(monkeypatch):
    import kagglehub
    from ml_training.keras_models import _local_preset
    monkeypatch.setattr(kagglehub, "model_download", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    assert _local_preset("bert_tiny_en_uncased") == "bert_tiny_en_uncased"
