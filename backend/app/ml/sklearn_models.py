"""Factories for the two classic-ML models.

Each pipeline takes a pandas DataFrame with the columns sender / subject / body and does its own
text cleaning, so the saved .joblib file is self-contained: load it, call predict_proba(df), done.

NOTE: these functions are referenced by name inside the pickled files, so keep them at module level.
"""
from __future__ import annotations

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer

from .features import numeric_matrix
from .preprocessing import build_text


def texts_from_frame(df):
    return [build_text(s, su, b) for s, su, b in zip(df["sender"], df["subject"], df["body"])]


def _text_pipeline(max_features: int):
    return Pipeline([
        ("clean", FunctionTransformer(texts_from_frame, validate=False)),
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=max_features, sublinear_tf=True)),
    ])


def make_naive_bayes() -> Pipeline:
    """TF-IDF (1-2 grams) -> Multinomial Naive Bayes. Fast, strong text baseline."""
    return Pipeline([
        ("text", _text_pipeline(max_features=50_000)),
        ("clf", MultinomialNB(alpha=0.1)),
    ])


def make_random_forest(n_estimators: int = 300, random_state: int = 42) -> Pipeline:
    """TF-IDF (top 5k terms) + hand-made numeric features (URLs, urgency, sender mismatch ...) -> Random Forest."""
    features = FeatureUnion([
        ("text", _text_pipeline(max_features=5_000)),
        ("numeric", FunctionTransformer(numeric_matrix, validate=False)),
    ])
    return Pipeline([
        ("features", features),
        ("clf", RandomForestClassifier(n_estimators=n_estimators, class_weight="balanced_subsample",
                                       n_jobs=-1, random_state=random_state)),
    ])
