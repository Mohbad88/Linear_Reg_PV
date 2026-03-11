import pandas as pd


def train_test_split_by_date(
    X: pd.DataFrame,
    y: pd.Series,
    split_date: str | pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Partition features/target according to a cutoff date.

    Records with index strictly before ``split_date`` go to the training set;
    the remainder form the test set.  The function assumes the index of ``X``
    and ``y`` is a :class:`~pandas.DatetimeIndex` that is already
    normalised (midnight).  ``split_date`` can be provided as a string or
    timestamp; it is normalised as well.

    Returns ``(X_train, X_test, y_train, y_test)``.
    """

    split_date = pd.to_datetime(split_date).normalize()

    if not isinstance(X.index, pd.DatetimeIndex) or not isinstance(
        y.index, pd.DatetimeIndex
    ):
        raise ValueError("Indices of X and y must be DatetimeIndex")

    X_train = X[X.index < split_date]
    X_test = X[X.index >= split_date]
    y_train = y[y.index < split_date]
    y_test = y[y.index >= split_date]

    return X_train, X_test, y_train, y_test