"""Machine-learning code used at *serving* time (training scripts live in backend/ml_training).

preprocessing.py  clean + normalise raw e-mail text   (shared by training and serving -> no skew)
heuristics.py     rule-based EVIDENCE + highlighting  (explains the verdict; not the ML score)
features.py       numeric features for Random Forest
sklearn_models.py pipeline factories for Naive Bayes / Random Forest
predictors.py     loaders that wrap saved sklearn / Keras models behind one interface
registry.py       loads every available artifact once at start-up
ensemble.py       combines the models into one verdict
"""
