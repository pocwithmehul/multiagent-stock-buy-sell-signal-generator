"""
XGBoost-based Signal Classifier Module.

This module implements a machine learning classifier for predicting
BUY/SELL/HOLD trading signals based on technical indicators.

Library Dependencies:
    - os: Environment variables (https://docs.python.org/3/library/os.html)
    - numpy: Numerical computing (https://numpy.org/doc/stable/)
    - pandas: Data manipulation (https://pandas.pydata.org/docs/)
    - typing: Type hints (https://docs.python.org/3/library/typing.html)
    - datetime: Date/time handling (https://docs.python.org/3/library/datetime.html)
    - xgboost: Gradient boosting framework (https://xgboost.readthedocs.io/)
    - sklearn: Machine learning utilities (https://scikit-learn.org/stable/)
"""

# os: Operating system interface for environment variable access
# Used for: Checking ENABLE_XGBOOST environment variable
# Reference: https://docs.python.org/3/library/os.html
import os

# numpy: Numerical computing library
# Used for: Array operations, NaN handling, mathematical functions
# Reference: https://numpy.org/doc/stable/reference/
import numpy as np

# pandas: Data manipulation and analysis library
# Used for: DataFrame operations, rolling calculations, time series
# Reference: https://pandas.pydata.org/docs/reference/index.html
import pandas as pd

# typing: Type hints for code documentation and IDE support
# Dict: Dictionary type hint
# List: List type hint
# Optional: Indicates nullable type
# Tuple: Fixed-length sequence type hint
# Reference: https://docs.python.org/3/library/typing.html
from typing import Dict, List, Optional, Tuple

# datetime: Date and time handling
# datetime: Combined date and time class
# Reference: https://docs.python.org/3/library/datetime.html
from datetime import datetime


class SignalClassifier:
    """
    XGBoost-based classifier for predicting BUY/SELL/HOLD signals.

    Uses technical indicators as features to classify trading signals.
    Falls back to RandomForest or rule-based prediction if XGBoost unavailable.

    Attributes:
        model: XGBClassifier or RandomForestClassifier instance
        feature_names (List[str]): Names of features used for prediction
        is_fitted (bool): Whether model has been trained
        feature_importance (Dict): Feature importance scores
    """

    def __init__(self):
        """
        Initialize the signal classifier.

        Sets up empty model, feature names, and tracking attributes.
        """
        # Model placeholder - will hold XGBClassifier or RandomForestClassifier
        self.model = None

        # List to store feature column names used during training
        # list type: Ordered collection of feature names
        self.feature_names = []

        # Flag to track if model has been trained
        # bool type: True after successful fit()
        self.is_fitted = False

        # Dictionary to store feature importance scores
        # dict type: Maps feature name to importance score
        self.feature_importance = {}

    @staticmethod
    def _xgboost_enabled() -> bool:
        """
        Check if XGBoost is enabled.

        XGBoost is enabled when either:
            1. ENABLE_XGBOOST env var is set to "true", "1", or "yes", OR
            2. The ml_analysis feature flag is ON (checked via FeatureFlagService).

        This ensures all ML components (LSTM + XGBoost + Ensemble) run together
        as a single atomic pipeline whenever the ml_analysis master flag is ON.

        Returns:
            bool: True if XGBoost should be used
        """
        # Explicit env var override takes precedence
        # os.getenv(key, default): Retrieve environment variable value
        # Reference: https://docs.python.org/3/library/os.html#os.getenv
        if os.getenv("ENABLE_XGBOOST", "").lower() in ("true", "1", "yes"):
            return True

        # Auto-enable when ml_analysis feature flag is ON.
        # When the user enables ml_analysis in Unleash/AppConfig, they expect
        # the full ML pipeline (LSTM + XGBoost + Ensemble) to run — not a
        # degraded RandomForest fallback due to a separate env var requirement.
        try:
            from infrastructure.feature_flags import is_feature_enabled, FeatureFlag
            return is_feature_enabled(FeatureFlag.ML_ANALYSIS, default=True)
        except Exception:
            # If feature flag system is unavailable, fall back to False so
            # RandomForest is used as the safe default.
            return False

    def _compute_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute technical indicator features from price data.

        Calculates various technical indicators including:
            - Returns (1-day, 5-day, 10-day)
            - Moving averages (SMA 5, 10, 20, 50)
            - Price ratios relative to MAs
            - RSI (Relative Strength Index)
            - MACD (Moving Average Convergence Divergence)
            - Bollinger Bands
            - Volatility
            - Volume ratio
            - Momentum

        Args:
            data (pd.DataFrame): DataFrame with OHLCV columns

        Returns:
            pd.DataFrame: Original data with added feature columns
        """
        # Create copy to avoid modifying original DataFrame
        # pd.DataFrame.copy(): Create a copy of DataFrame
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.copy.html
        df = data.copy()

        # ── Price Returns ──────────────────────────────────────────────
        # pct_change(): Percentage change from previous value
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.pct_change.html
        df['returns'] = df['Close'].pct_change()           # Daily returns
        df['returns_5d'] = df['Close'].pct_change(5)       # 5-day returns
        df['returns_10d'] = df['Close'].pct_change(10)     # 10-day returns

        # ── Simple Moving Averages ─────────────────────────────────────
        # rolling(window).mean(): Compute rolling window mean
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.rolling.html
        df['sma_5'] = df['Close'].rolling(5).mean()        # 5-day SMA
        df['sma_10'] = df['Close'].rolling(10).mean()      # 10-day SMA
        df['sma_20'] = df['Close'].rolling(20).mean()      # 20-day SMA
        df['sma_50'] = df['Close'].rolling(50).mean()      # 50-day SMA

        # ── Price Ratios Relative to Moving Averages ───────────────────
        # Ratios indicate price position relative to trend indicators
        df['price_sma5_ratio'] = df['Close'] / df['sma_5']    # Price/SMA5
        df['price_sma20_ratio'] = df['Close'] / df['sma_20']  # Price/SMA20
        df['sma5_sma20_ratio'] = df['sma_5'] / df['sma_20']   # Short/Long MA ratio

        # ── RSI (Relative Strength Index) ──────────────────────────────
        # RSI measures momentum on scale of 0-100
        # Formula: RSI = 100 - (100 / (1 + RS)) where RS = avg_gain / avg_loss

        # diff(): First discrete difference (today - yesterday)
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.diff.html
        delta = df['Close'].diff()

        # where(): Return elements based on condition
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.where.html
        # Extract gains (positive changes) and losses (negative changes)
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

        # Calculate Relative Strength and RSI
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # ── MACD (Moving Average Convergence Divergence) ───────────────
        # MACD = EMA(12) - EMA(26), Signal = EMA(9) of MACD

        # ewm(): Exponentially weighted moving window
        # span: Decay in terms of center of mass
        # adjust=False: Use recursive formula for EMA
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.ewm.html
        ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26                                    # MACD line
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean() # Signal line
        df['macd_histogram'] = df['macd'] - df['macd_signal']           # Histogram

        # ── Bollinger Bands ────────────────────────────────────────────
        # Bollinger Bands = SMA(20) +/- 2 * StdDev(20)
        # Used to identify overbought/oversold conditions

        df['bb_middle'] = df['Close'].rolling(20).mean()   # Middle band (SMA)

        # rolling().std(): Rolling standard deviation
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.core.window.rolling.Rolling.std.html
        bb_std = df['Close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * bb_std      # Upper band (+2 std)
        df['bb_lower'] = df['bb_middle'] - 2 * bb_std      # Lower band (-2 std)

        # Position within bands (0 = at lower, 1 = at upper)
        df['bb_position'] = (df['Close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # ── Volatility ─────────────────────────────────────────────────
        # 20-day rolling standard deviation of returns
        df['volatility'] = df['returns'].rolling(20).std()

        # ── Volume Features ────────────────────────────────────────────
        # Check if Volume column exists (some data sources may not have it)
        # 'in' operator: Check membership in DataFrame columns
        if 'Volume' in df.columns:
            df['volume_sma'] = df['Volume'].rolling(20).mean()  # 20-day avg volume
            df['volume_ratio'] = df['Volume'] / df['volume_sma'] # Today/average

        # ── Momentum ───────────────────────────────────────────────────
        # Price ratio to N days ago, minus 1 (percentage change)
        # shift(n): Shift values by n periods
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.shift.html
        df['momentum_5'] = df['Close'] / df['Close'].shift(5) - 1   # 5-day momentum
        df['momentum_10'] = df['Close'] / df['Close'].shift(10) - 1 # 10-day momentum

        return df

    def _create_labels(self, data: pd.DataFrame, lookahead: int = 5,
                       threshold: float = 0.02) -> pd.Series:
        """
        Create classification labels based on future price movement.

        Args:
            data (pd.DataFrame): DataFrame with 'Close' column
            lookahead (int): Number of days to look ahead for labeling
            threshold (float): Return threshold for BUY/SELL classification (2%)

        Returns:
            pd.Series: Labels (0=SELL, 1=HOLD, 2=BUY)
        """
        # Calculate future returns (lookahead days ahead)
        # shift(-n): Shift values backward (future values)
        # Formula: (future_price / current_price) - 1
        future_returns = data['Close'].shift(-lookahead) / data['Close'] - 1

        # Create empty Series with same index as data
        # pd.Series(): Create new Series with specified index and dtype
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.html
        labels = pd.Series(index=data.index, dtype=int)

        # Assign labels based on future return thresholds
        # Boolean indexing: labels[condition] = value
        # Reference: https://pandas.pydata.org/docs/user_guide/indexing.html#boolean-indexing
        labels[future_returns > threshold] = 2   # BUY: returns > 2%
        labels[future_returns < -threshold] = 0  # SELL: returns < -2%
        labels[(future_returns >= -threshold) & (future_returns <= threshold)] = 1  # HOLD

        return labels

    def fit(self, data: pd.DataFrame, lookahead: int = 5) -> Dict:
        """
        Train the classifier on historical data.

        Args:
            data (pd.DataFrame): DataFrame with OHLCV columns
            lookahead (int): Days to look ahead for label creation

        Returns:
            Dict: Training results including accuracy metrics
        """
        # Validate minimum data requirement
        # len(): Get length of DataFrame
        if len(data) < 100:
            return {"error": "Insufficient data for training (need at least 100 rows)"}

        try:
            # ── Feature Engineering ────────────────────────────────────
            # Compute technical indicators as features
            df = self._compute_features(data)

            # Create labels based on future price movement
            labels = self._create_labels(df, lookahead)

            # ── Feature Selection ──────────────────────────────────────
            # Define list of feature column names to use
            # list literal: Create ordered collection of feature names
            self.feature_names = [
                'returns', 'returns_5d', 'returns_10d',
                'price_sma5_ratio', 'price_sma20_ratio', 'sma5_sma20_ratio',
                'rsi', 'macd', 'macd_signal', 'macd_histogram',
                'bb_position', 'volatility', 'momentum_5', 'momentum_10'
            ]

            # Add volume ratio if available
            if 'volume_ratio' in df.columns:
                # list.append(): Add element to end of list
                # Reference: https://docs.python.org/3/library/stdtypes.html#list
                self.feature_names.append('volume_ratio')

            # ── Data Preparation ───────────────────────────────────────
            # Select feature columns and drop rows with NaN
            # DataFrame[list]: Select columns by name
            # dropna(): Remove rows with missing values
            # Reference: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.dropna.html
            X = df[self.feature_names].dropna()
            y = labels.loc[X.index].dropna()  # Align labels with X index

            # Find common indices between X and y
            # Index.intersection(): Set intersection of two indices
            # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Index.intersection.html
            common_idx = X.index.intersection(y.index)
            X = X.loc[common_idx]  # Filter to common indices
            y = y.loc[common_idx]

            # Remove any remaining NaN values
            # isna(): Check for NaN values
            # any(axis=1): Check if any True in each row
            # ~ operator: Boolean negation
            valid_idx = ~(X.isna().any(axis=1) | y.isna())
            X = X[valid_idx]
            y = y[valid_idx]

            # Check if enough valid samples remain
            if len(X) < 50:
                return {"error": "Insufficient valid samples after preprocessing"}

            # ── Model Selection ────────────────────────────────────────
            # Use XGBoost only if explicitly enabled
            if not self._xgboost_enabled():
                return self._fit_fallback(X, y)

            try:
                # Import XGBClassifier from xgboost library
                # XGBClassifier: Gradient boosting classifier
                # Reference: https://xgboost.readthedocs.io/en/stable/python/python_api.html#xgboost.XGBClassifier
                from xgboost import XGBClassifier

                # Create XGBoost classifier with parameters
                # n_estimators: Number of boosting rounds
                # max_depth: Maximum tree depth
                # learning_rate: Boosting learning rate (eta)
                # objective: Learning task (multi-class classification)
                # num_class: Number of classes (SELL, HOLD, BUY)
                # random_state: Seed for reproducibility
                # verbosity: Logging level (0=silent)
                self.model = XGBClassifier(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    objective='multi:softprob',
                    num_class=3,
                    random_state=42,
                    verbosity=0
                )

                # ── Train/Validation Split ─────────────────────────────
                # Split data 80/20 for training and validation
                # int(): Convert to integer index
                split_idx = int(len(X) * 0.8)
                X_train, X_val = X[:split_idx], X[split_idx:]  # Slice training/validation
                y_train, y_val = y[:split_idx], y[split_idx:]

                # ── Model Training ─────────────────────────────────────
                # fit(): Train the model on data
                # Reference: https://xgboost.readthedocs.io/en/stable/python/python_api.html#xgboost.XGBClassifier.fit
                self.model.fit(X_train, y_train)

                # ── Model Evaluation ───────────────────────────────────
                # score(): Return mean accuracy on given data
                # Reference: https://xgboost.readthedocs.io/en/stable/python/python_api.html#xgboost.XGBClassifier.score
                train_score = self.model.score(X_train, y_train)
                val_score = self.model.score(X_val, y_val)

                # ── Feature Importance ─────────────────────────────────
                # feature_importances_: Get feature importance scores
                # Reference: https://xgboost.readthedocs.io/en/stable/python/python_api.html#xgboost.XGBClassifier.feature_importances_
                importance = self.model.feature_importances_

                # Create dict mapping feature names to importance scores
                # zip(): Pair up feature names and importance values
                # dict(): Convert to dictionary
                self.feature_importance = dict(zip(self.feature_names, importance))

                self.is_fitted = True

                # Return training results
                # sorted(): Sort by importance (descending)
                # key=lambda x: x[1]: Sort by value (importance score)
                # [:5]: Get top 5 features
                return {
                    "status": "success",
                    "train_accuracy": round(train_score, 3),
                    "validation_accuracy": round(val_score, 3),
                    "samples_used": len(X),
                    "feature_importance": {k: round(v, 4) for k, v in
                                          sorted(self.feature_importance.items(),
                                                key=lambda x: x[1], reverse=True)[:5]}
                }

            except ImportError:
                # XGBoost not installed - fall back to sklearn
                return self._fit_fallback(X, y)

        except Exception as e:
            # Handle any training errors
            # str(e): Convert exception to string message
            return {"error": str(e)}

    def _fit_fallback(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """
        Fallback training using RandomForest if XGBoost not available.

        Args:
            X (pd.DataFrame): Feature matrix
            y (pd.Series): Target labels

        Returns:
            Dict: Training results
        """
        try:
            # Import RandomForestClassifier from sklearn
            # RandomForestClassifier: Ensemble of decision trees
            # Reference: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html
            from sklearn.ensemble import RandomForestClassifier

            # Create RandomForest classifier
            # n_estimators: Number of trees in forest
            # max_depth: Maximum depth of trees
            # random_state: Seed for reproducibility
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42
            )

            # Train/validation split (80/20)
            split_idx = int(len(X) * 0.8)
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]

            # Train the model
            # fit(): Train RandomForest on data
            # Reference: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html#sklearn.ensemble.RandomForestClassifier.fit
            self.model.fit(X_train, y_train)

            # Evaluate model
            # score(): Return mean accuracy
            # Reference: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html#sklearn.ensemble.RandomForestClassifier.score
            train_score = self.model.score(X_train, y_train)
            val_score = self.model.score(X_val, y_val)

            # Get feature importance
            # feature_importances_: Feature importance array
            # Reference: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html#sklearn.ensemble.RandomForestClassifier.feature_importances_
            importance = self.model.feature_importances_
            self.feature_importance = dict(zip(self.feature_names, importance))
            self.is_fitted = True

            return {
                "status": "success (RandomForest fallback)",
                "train_accuracy": round(train_score, 3),
                "validation_accuracy": round(val_score, 3),
                "samples_used": len(X)
            }

        except Exception as e:
            # Fall back to rule-based prediction
            self.is_fitted = True
            return {"error": str(e), "status": "Using rule-based fallback"}

    def predict(self, data: pd.DataFrame) -> Dict:
        """
        Predict signal for current data.

        Args:
            data (pd.DataFrame): Recent price data with OHLCV columns

        Returns:
            Dict: Prediction with signal, confidence, and probabilities
        """
        # Check minimum data requirement
        if len(data) < 60:
            return self._rule_based_predict(data)

        try:
            # Compute features from raw data
            df = self._compute_features(data)

            # Select feature columns and get last row
            # iloc[[-1]]: Select last row as DataFrame (not Series)
            # Reference: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iloc.html
            X = df[self.feature_names].iloc[[-1]]

            # Check for NaN values in features
            # isna().any().any(): Check if any NaN exists
            if X.isna().any().any():
                return self._rule_based_predict(data)

            # Check if model is available
            if self.model is None:
                return self._rule_based_predict(data)

            # ── Make Prediction ────────────────────────────────────────
            # predict_proba(): Get probability estimates for each class
            # Returns array of shape (n_samples, n_classes)
            # Reference for XGBoost: https://xgboost.readthedocs.io/en/stable/python/python_api.html#xgboost.XGBClassifier.predict_proba
            # Reference for sklearn: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html#sklearn.ensemble.RandomForestClassifier.predict_proba
            proba = self.model.predict_proba(X)[0]  # [0] gets first (only) sample

            # predict(): Get predicted class label
            # Reference: https://xgboost.readthedocs.io/en/stable/python/python_api.html#xgboost.XGBClassifier.predict
            prediction = self.model.predict(X)[0]

            # Map numeric prediction to signal string
            # dict literal: Create mapping of class to signal
            signal_map = {0: "SELL", 1: "HOLD", 2: "BUY"}
            signal = signal_map[prediction]

            # Return prediction results
            # max(proba): Get highest probability (confidence)
            # float(): Ensure Python float type
            return {
                "signal": signal,
                "confidence": round(float(max(proba)), 3),
                "probabilities": {
                    "SELL": round(float(proba[0]), 3),
                    "HOLD": round(float(proba[1]), 3),
                    "BUY": round(float(proba[2]), 3)
                },
                # Show top 5 feature values for interpretability
                "feature_values": {name: round(float(X[name].iloc[0]), 4)
                                  for name in self.feature_names[:5]},
                # Indicate which model type was used
                # str(type(self.model)): Get type name string
                # str.lower(): Convert to lowercase for comparison
                "model_type": "XGBoost" if "xgboost" in str(type(self.model)).lower()
                             else "RandomForest"
            }

        except Exception as e:
            # Fall back to rule-based prediction on any error
            return self._rule_based_predict(data)

    def _rule_based_predict(self, data: pd.DataFrame) -> Dict:
        """
        Rule-based fallback prediction using technical indicators.

        Uses simple scoring system based on RSI, MACD, SMA, and momentum.

        Args:
            data (pd.DataFrame): Price data with OHLCV columns

        Returns:
            Dict: Prediction with signal, confidence, and reasoning
        """
        # Check minimum data requirement
        if len(data) < 20:
            # Return neutral signal with equal probabilities
            return {
                "signal": "HOLD",
                "confidence": 0.5,
                "probabilities": {"SELL": 0.33, "HOLD": 0.34, "BUY": 0.33},
                "model_type": "Rule-based (insufficient data)"
            }

        # Compute technical indicators
        df = self._compute_features(data)

        # Get latest row of indicators
        # iloc[-1]: Get last row as Series
        latest = df.iloc[-1]

        # Initialize score and reasons tracking
        # int type: Cumulative score (positive=bullish, negative=bearish)
        # list type: Collect reasoning strings
        score = 0
        reasons = []

        # ── RSI Signal ─────────────────────────────────────────────────
        # Get RSI value with default of 50 (neutral) if missing
        # dict.get(key, default): Get value or default
        rsi = latest.get('rsi', 50)
        if rsi < 30:
            # RSI below 30 = oversold = bullish signal
            score += 2
            # f-string: Format string with variable
            # :.1f format: Float with 1 decimal place
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            # RSI above 70 = overbought = bearish signal
            score -= 2
            reasons.append(f"RSI overbought ({rsi:.1f})")

        # ── MACD Signal ────────────────────────────────────────────────
        # Positive histogram = bullish momentum
        macd_hist = latest.get('macd_histogram', 0)
        if macd_hist > 0:
            score += 1
            reasons.append("MACD bullish")
        elif macd_hist < 0:
            score -= 1
            reasons.append("MACD bearish")

        # ── Price vs SMA Signal ────────────────────────────────────────
        # Price above SMA20 = bullish trend
        price_sma_ratio = latest.get('price_sma20_ratio', 1)
        if price_sma_ratio > 1.02:  # Price 2% above SMA20
            score += 1
            reasons.append("Above SMA20")
        elif price_sma_ratio < 0.98:  # Price 2% below SMA20
            score -= 1
            reasons.append("Below SMA20")

        # ── Momentum Signal ────────────────────────────────────────────
        # Strong positive/negative momentum
        momentum = latest.get('momentum_5', 0)
        if momentum > 0.03:  # 3%+ 5-day gain
            score += 1
        elif momentum < -0.03:  # 3%+ 5-day loss
            score -= 1

        # ── Convert Score to Signal ────────────────────────────────────
        # Threshold-based signal assignment
        if score >= 2:
            signal = "BUY"
            # Confidence increases with score magnitude
            # min(): Cap confidence at 0.85
            confidence = min(0.85, 0.5 + score * 0.1)
        elif score <= -2:
            signal = "SELL"
            # abs(): Absolute value for negative scores
            confidence = min(0.85, 0.5 + abs(score) * 0.1)
        else:
            signal = "HOLD"
            confidence = 0.5 + abs(score) * 0.05

        # ── Calculate Probability Distribution ─────────────────────────
        # Create rough probability estimates based on signal
        total = abs(score) + 3  # Normalization factor
        if signal == "BUY":
            # High BUY probability, split remainder between HOLD and SELL
            proba = {"BUY": confidence, "HOLD": (1 - confidence) * 0.6, "SELL": (1 - confidence) * 0.4}
        elif signal == "SELL":
            # High SELL probability
            proba = {"SELL": confidence, "HOLD": (1 - confidence) * 0.6, "BUY": (1 - confidence) * 0.4}
        else:
            # Neutral - split evenly between BUY and SELL
            proba = {"HOLD": confidence, "BUY": (1 - confidence) / 2, "SELL": (1 - confidence) / 2}

        # Return rule-based prediction
        # dict comprehension: Round all probability values
        return {
            "signal": signal,
            "confidence": round(confidence, 3),
            "probabilities": {k: round(v, 3) for k, v in proba.items()},
            "reasons": reasons,
            "model_type": "Rule-based"
        }
