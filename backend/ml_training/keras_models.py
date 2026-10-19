"""LSTM and BERT definitions (Keras 3 on TensorFlow). Each is saved as ONE .keras file that already
contains its own text vectoriser / tokenizer, so the API only has to call model.predict(strings)."""
from __future__ import annotations

import numpy as np


def _keras():
    import os
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
    import keras
    return keras


def class_weights(y) -> dict:
    y = np.asarray(y)
    n, k = len(y), 2
    return {c: n / (k * max(1, int((y == c).sum()))) for c in (0, 1)}


def build_lstm(train_texts, max_tokens: int = 20_000, seq_len: int = 256, embed_dim: int = 128, units: int = 64):
    """text -> TextVectorization -> Embedding -> BiLSTM -> Dropout -> sigmoid (P(phishing))."""
    keras = _keras()
    vec = keras.layers.TextVectorization(max_tokens=max_tokens, output_sequence_length=seq_len,
                                         standardize="lower_and_strip_punctuation")
    vec.adapt(np.asarray(train_texts, dtype=object))        # vocabulary from TRAIN only (no leakage)
    inp = keras.Input(shape=(), dtype="string")
    x = vec(inp)
    x = keras.layers.Embedding(max_tokens, embed_dim, mask_zero=True)(x)
    x = keras.layers.Bidirectional(keras.layers.LSTM(units))(x)
    x = keras.layers.Dropout(0.3)(x)
    out = keras.layers.Dense(1, activation="sigmoid")(x)
    model = keras.Model(inp, out, name="phishlens_lstm")
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="binary_crossentropy", metrics=["accuracy"])
    return model


def _local_preset(preset: str | None) -> str | None:
    """Download a BERT preset as ONE folder and return its local path.

    Windows bug in keras-hub: when it loads a preset by name it asks Kaggle for single files using the
    Windows path 'assets\\tokenizer\\vocabulary.txt' (backslashes), which Kaggle answers with 404, giving
    "FileNotFoundError: `assets\\tokenizer\\vocabulary.txt` doesn't exist in preset directory kaggle://...".
    Downloading the whole preset folder first (no per-file path) and loading it from disk avoids that.
    Anything that is not a built-in preset name (a local folder, a full handle) is returned unchanged."""
    import os
    if not preset or os.path.isdir(preset) or "://" in preset:
        return preset
    import keras_hub
    try:
        handle = keras_hub.models.BertBackbone.presets[preset]["kaggle_handle"]
        import kagglehub
        return kagglehub.model_download(handle.removeprefix("kaggle://"))
    except Exception as exc:  # noqa: BLE001  fall back to keras-hub's own download
        print(f"[warn] could not pre-download preset '{preset}' as one folder ({type(exc).__name__}: {exc}); "
              "trying keras-hub's normal download instead")
        return preset


def build_bert(train_texts, preset: str | None = "bert_tiny_en_uncased", seq_len: int = 128, lr: float | None = None):
    """BERT text classifier.

    preset="bert_tiny_en_uncased" (default; 4 M params, CPU friendly) or "bert_small_en_uncased" /
    "bert_base_en_uncased" (better, much slower). The weights are downloaded once by keras-hub.

    preset=None builds a tiny UNTRAINED-from-scratch BERT with a vocabulary learned from your data.
    That is only for offline smoke tests: without pre-training it is not a real BERT.
    """
    keras = _keras()
    import keras_hub

    if preset:
        preset = _local_preset(preset)
        pre = keras_hub.models.BertTextClassifierPreprocessor.from_preset(preset, sequence_length=seq_len)
        model = keras_hub.models.BertTextClassifier.from_preset(preset, num_classes=2, activation="softmax",
                                                                preprocessor=pre)
        lr = lr or 3e-5
    else:
        reserved = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
        import tensorflow as tf
        # NB: a plain list of str would be treated as FILE NAMES, so wrap the texts in a Dataset.
        data = tf.data.Dataset.from_tensor_slices(list(train_texts)).batch(256)
        vocab = keras_hub.tokenizers.compute_word_piece_vocabulary(
            data, vocabulary_size=8000, lowercase=True, reserved_tokens=reserved)
        tok = keras_hub.tokenizers.BertTokenizer(vocabulary=vocab, lowercase=True)
        pre = keras_hub.models.BertTextClassifierPreprocessor(tok, sequence_length=seq_len)
        backbone = keras_hub.models.BertBackbone(vocabulary_size=len(vocab), num_layers=2, num_heads=4,
                                                 hidden_dim=64, intermediate_dim=128, max_sequence_length=seq_len)
        model = keras_hub.models.BertTextClassifier(backbone, num_classes=2, activation="softmax", preprocessor=pre)
        lr = lr or 1e-3
    model.compile(optimizer=keras.optimizers.Adam(lr), loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    return model


def fit(model, x_train, y_train, x_val, y_val, epochs: int, batch_size: int):
    keras = _keras()
    stop = keras.callbacks.EarlyStopping(monitor="val_loss", patience=2, restore_best_weights=True)
    return model.fit(np.asarray(x_train, dtype=object), np.asarray(y_train), validation_data=(
        np.asarray(x_val, dtype=object), np.asarray(y_val)), epochs=epochs, batch_size=batch_size,
        class_weight=class_weights(y_train), callbacks=[stop], verbose=2)
