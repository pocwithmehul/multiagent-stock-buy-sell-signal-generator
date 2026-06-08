"""
LSTM-based Price Prediction Model.

This module implements a Long Short-Term Memory (LSTM) neural network
for predicting stock prices over a 5-day horizon.

Library Dependencies:
    - numpy: Numerical computing library (https://numpy.org/doc/stable/)
    - pandas: Data manipulation library (https://pandas.pydata.org/docs/)
    - typing: Type hints support (https://docs.python.org/3/library/typing.html)
    - datetime: Date/time handling (https://docs.python.org/3/library/datetime.html)
    - tensorflow.keras: Deep learning framework (https://www.tensorflow.org/api_docs/python/tf/keras)
    - sklearn: Machine learning utilities (https://scikit-learn.org/stable/documentation.html)
"""

# numpy: Numerical computing library for array operations
# Used for: array creation, reshaping, mathematical operations
# Reference: https://numpy.org/doc/stable/reference/
import numpy as np

# pandas: Data manipulation and analysis library
# Used for: DataFrame operations, time series handling, rolling calculations
# Reference: https://pandas.pydata.org/docs/reference/index.html
import pandas as pd

# typing: Type hints for better code documentation and IDE support
# Optional: Indicates value can be None
# Tuple: Fixed-length sequence of specific types
# List: Variable-length sequence
# Dict: Key-value mapping
# Reference: https://docs.python.org/3/library/typing.html
from typing import Optional, Tuple, List, Dict

# datetime: Core date/time handling classes
# datetime: Combined date and time
# timedelta: Duration between two datetime objects
# Reference: https://docs.python.org/3/library/datetime.html
from datetime import datetime, timedelta


class PricePredictor:
    """
    LSTM-based model for predicting stock prices.

    Predicts next 5-day price movement using historical OHLCV data.
    Falls back to momentum-based prediction if TensorFlow is unavailable.

    Attributes:
        sequence_length (int): Number of past days used for prediction
        model: Keras Sequential model (None if TensorFlow unavailable)
        scaler: MinMaxScaler for normalizing price data
        is_fitted (bool): Whether model has been trained
    """

    def __init__(self, sequence_length: int = 60):
        """
        Initialize the price predictor.

        Args:
            sequence_length (int): Number of past days to use for prediction.
                                   Default is 60 days (~3 months of trading).
        """
        # Store sequence length for LSTM input window
        # int type: Number of time steps in input sequence
        self.sequence_length = sequence_length

        # Keras Sequential model placeholder - initialized during fit()
        # Will hold tensorflow.keras.models.Sequential instance
        self.model = None

        # sklearn MinMaxScaler for data normalization - initialized during _prepare_data()
        # Scales features to [0, 1] range for neural network training
        self.scaler = None

        # Flag indicating if model has been trained
        # bool type: True after successful fit()
        self.is_fitted = False

    def _prepare_data(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare data for LSTM training.

        Transforms raw price DataFrame into sequences suitable for LSTM.

        Args:
            data (pd.DataFrame): DataFrame with 'Close' column containing prices

        Returns:
            Tuple[np.ndarray, np.ndarray]: (X, y) where:
                X: Input sequences of shape (samples, sequence_length)
                y: Target values of shape (samples, 5) for 5-day predictions
        """
        # Import MinMaxScaler from sklearn.preprocessing
        # Scales features to a given range (default [0, 1])
        # Reference: https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html
        from sklearn.preprocessing import MinMaxScaler

        # Extract 'Close' prices as numpy array and reshape to column vector
        # pd.DataFrame['column'].values: Get numpy array from Series
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.values.html
        # np.reshape(-1, 1): Reshape to (n_samples, 1) for sklearn
        # Reference: https://numpy.org/doc/stable/reference/generated/numpy.reshape.html
        prices = data['Close'].values.reshape(-1, 1)

        # Create MinMaxScaler instance with range [0, 1]
        # feature_range: Tuple specifying min and max of scaled values
        self.scaler = MinMaxScaler(feature_range=(0, 1))

        # Fit scaler to data and transform in one step
        # fit_transform(): Learn min/max and scale data
        # Reference: https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html#sklearn.preprocessing.MinMaxScaler.fit_transform
        scaled_data = self.scaler.fit_transform(prices)

        # Initialize lists for input sequences (X) and target values (y)
        X, y = [], []

        # Create sliding window sequences
        # Loop from sequence_length to (len - 5) to leave room for 5-day target
        # range(): Built-in iterator for integer sequences
        # Reference: https://docs.python.org/3/library/functions.html#func-range
        for i in range(self.sequence_length, len(scaled_data) - 5):
            # Extract input sequence: previous sequence_length days
            # Slicing scaled_data[start:end, column]
            # Reference: https://numpy.org/doc/stable/user/basics.indexing.html
            X.append(scaled_data[i - self.sequence_length:i, 0])

            # Extract target: next 5 days of prices
            # Used for multi-step ahead prediction
            y.append(scaled_data[i:i + 5, 0])

        # Convert lists to numpy arrays
        # np.array(): Create array from list
        # Reference: https://numpy.org/doc/stable/reference/generated/numpy.array.html
        return np.array(X), np.array(y)

    def _build_model(self, input_shape: Tuple) -> None:
        """
        Build the LSTM neural network model.

        Creates a Keras Sequential model with:
            - 2 LSTM layers with dropout for regularization
            - 2 Dense layers for output

        Args:
            input_shape (Tuple): Shape of input data (sequence_length, features)
        """
        try:
            # Import Keras components from TensorFlow
            # Sequential: Linear stack of layers
            # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/Sequential
            from tensorflow.keras.models import Sequential

            # LSTM: Long Short-Term Memory recurrent layer
            # Dense: Fully connected neural network layer
            # Dropout: Regularization layer to prevent overfitting
            # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/layers
            from tensorflow.keras.layers import LSTM, Dense, Dropout

            # Build Sequential model with list of layers
            # Sequential(): Keras model class for linear layer stacking
            # Reference: https://www.tensorflow.org/guide/keras/sequential_model
            self.model = Sequential([
                # First LSTM layer: 50 units, returns sequences for next LSTM
                # return_sequences=True: Output full sequence for stacking LSTM layers
                # input_shape: (time_steps, features) - required for first layer
                # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/layers/LSTM
                LSTM(50, return_sequences=True, input_shape=input_shape),

                # Dropout layer: Randomly set 20% of inputs to 0 during training
                # Prevents overfitting by reducing co-adaptation of neurons
                # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/layers/Dropout
                Dropout(0.2),

                # Second LSTM layer: 50 units, returns only last output
                # return_sequences=False (default): Output only final hidden state
                LSTM(50, return_sequences=False),

                # Second dropout layer for regularization
                Dropout(0.2),

                # Hidden dense layer: 25 units with default activation
                # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/layers/Dense
                Dense(25),

                # Output layer: 5 units for 5-day price prediction
                Dense(5)  # Predict 5 days
            ])

            # Compile model with optimizer, loss function, and metrics
            # optimizer='adam': Adam optimizer - adaptive learning rate
            # loss='mse': Mean Squared Error - standard for regression
            # metrics=['mae']: Mean Absolute Error for monitoring
            # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/Model#compile
            self.model.compile(optimizer='adam', loss='mse', metrics=['mae'])

        except ImportError:
            # TensorFlow not installed - fallback to simple model
            # Set model to None to trigger fallback prediction
            self.model = None

    def fit(self, data: pd.DataFrame, epochs: int = 10, verbose: int = 0) -> Dict:
        """
        Train the LSTM model on historical data.

        Args:
            data (pd.DataFrame): DataFrame with 'Close' column containing prices
            epochs (int): Number of complete passes through training data
            verbose (int): Verbosity mode (0=silent, 1=progress bar, 2=line per epoch)

        Returns:
            Dict: Training results containing status, loss, and MAE values
        """
        # Validate data length - need sufficient samples for training
        # len(): Built-in function returning sequence length
        # Reference: https://docs.python.org/3/library/functions.html#len
        if len(data) < self.sequence_length + 10:
            return {"error": "Insufficient data for training"}

        try:
            # Prepare training data - create sequences from raw prices
            X, y = self._prepare_data(data)

            # Check if preparation yielded valid data
            if len(X) == 0:
                return {"error": "Could not prepare training data"}

            # Reshape X for LSTM input: [samples, time_steps, features]
            # LSTM requires 3D input: (batch_size, sequence_length, num_features)
            # np.reshape(): Change array dimensions
            # X.shape[0]: Number of samples, X.shape[1]: Sequence length
            # Reference: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.reshape.html
            X = X.reshape((X.shape[0], X.shape[1], 1))

            # Build LSTM model architecture
            # input_shape is (sequence_length, 1) - 1 feature (close price)
            self._build_model((X.shape[1], 1))

            # Check if TensorFlow model was built successfully
            if self.model is None:
                # Use fallback prediction method
                self.is_fitted = True
                return {"status": "Using fallback model (TensorFlow not available)"}

            # Train the model using Keras fit()
            # model.fit(): Train model for fixed number of epochs
            # batch_size: Number of samples per gradient update
            # validation_split: Fraction of data for validation
            # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/Model#fit
            history = self.model.fit(
                X, y,                      # Training data and targets
                epochs=epochs,             # Number of training epochs
                batch_size=32,             # Samples per gradient update
                validation_split=0.1,      # 10% of data for validation
                verbose=verbose            # Output verbosity
            )

            # Mark model as trained
            self.is_fitted = True

            # Return training metrics from history object
            # history.history: Dict mapping metric names to lists of values
            # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/callbacks/History
            return {
                "status": "success",
                "final_loss": float(history.history['loss'][-1]),   # Last epoch loss
                "final_mae": float(history.history['mae'][-1])      # Last epoch MAE
            }

        except Exception as e:
            # Handle any training errors - allow fallback prediction
            self.is_fitted = True  # Allow fallback prediction
            return {"error": str(e), "status": "Using fallback model"}

    def predict(self, data: pd.DataFrame) -> Dict:
        """
        Predict next 5 days of prices.

        Args:
            data (pd.DataFrame): Recent price data (at least sequence_length days)

        Returns:
            Dict: Predictions including prices, trend, confidence, and analysis
        """
        # Check minimum data requirement
        if len(data) < self.sequence_length:
            # Insufficient data - use simpler fallback method
            return self._fallback_predict(data)

        try:
            # Check if LSTM model and scaler are available
            if self.model is None or self.scaler is None:
                return self._fallback_predict(data)

            # Prepare input data - get last sequence_length prices
            # pd.DataFrame['column'].values: Get numpy array
            # [-sequence_length:]: Slice last N elements
            # reshape(-1, 1): Convert to column vector for scaler
            prices = data['Close'].values[-self.sequence_length:].reshape(-1, 1)

            # Scale input using fitted scaler
            # scaler.transform(): Apply learned scaling (don't fit again)
            # Reference: https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html#sklearn.preprocessing.MinMaxScaler.transform
            scaled_input = self.scaler.transform(prices)

            # Reshape for LSTM: (1, sequence_length, 1) - single sample
            X = scaled_input.reshape(1, self.sequence_length, 1)

            # Make prediction using trained model
            # model.predict(): Generate output predictions
            # verbose=0: Suppress progress output
            # Reference: https://www.tensorflow.org/api_docs/python/tf/keras/Model#predict
            scaled_predictions = self.model.predict(X, verbose=0)

            # Inverse transform predictions back to original price scale
            # scaler.inverse_transform(): Undo scaling transformation
            # reshape(-1, 1): Reshape for inverse_transform input
            predictions = self.scaler.inverse_transform(scaled_predictions.reshape(-1, 1))

            # Get current price for comparison
            # pd.DataFrame.iloc[-1]: Get last row value
            # Reference: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.iloc.html
            current_price = float(data['Close'].iloc[-1])

            # Flatten predictions array to 1D list
            # np.ndarray.flatten(): Return 1D copy of array
            # .tolist(): Convert numpy array to Python list
            # Reference: https://numpy.org/doc/stable/reference/generated/numpy.ndarray.flatten.html
            predicted_prices = predictions.flatten().tolist()

            # Format and return predictions with analysis
            return self._format_predictions(current_price, predicted_prices, data)

        except Exception as e:
            # On any error, fall back to simpler prediction method
            return self._fallback_predict(data)

    def _fallback_predict(self, data: pd.DataFrame) -> Dict:
        """
        Fallback prediction using simple moving average and momentum.

        Used when TensorFlow is unavailable or insufficient data for LSTM.

        Args:
            data (pd.DataFrame): Price data with 'Close' column

        Returns:
            Dict: Predictions based on trend and momentum analysis
        """
        # Require minimum 20 days for SMA calculations
        if len(data) < 20:
            return {"error": "Insufficient data", "predictions": []}

        # Get current closing price
        # float(): Ensure Python float type
        current_price = float(data['Close'].iloc[-1])

        # Calculate 5-day and 20-day simple moving averages
        # pd.Series.rolling(window).mean(): Compute rolling mean
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.rolling.html
        sma_5 = data['Close'].rolling(5).mean().iloc[-1]
        sma_20 = data['Close'].rolling(20).mean().iloc[-1]

        # Calculate daily returns (percentage change)
        # pd.Series.pct_change(): Fractional change from previous value
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.pct_change.html
        # dropna(): Remove NaN values from result
        returns = data['Close'].pct_change().dropna()

        # Calculate mean return and volatility (standard deviation)
        # pd.Series.mean(): Arithmetic mean of values
        # pd.Series.std(): Standard deviation of values
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.Series.mean.html
        avg_return = returns.mean()
        volatility = returns.std()

        # Calculate trend as relative difference between short and long SMA
        # Positive trend = short-term SMA above long-term SMA (bullish)
        trend = (sma_5 - sma_20) / sma_20 if sma_20 != 0 else 0

        # Extrapolate 5-day momentum from average daily return
        momentum = avg_return * 5  # 5-day momentum

        # Generate 5-day price predictions
        predicted_prices = []
        price = current_price

        # Loop through days 1 to 5
        # range(1, 6): Generate integers 1, 2, 3, 4, 5
        for day in range(1, 6):
            # Calculate daily change combining trend and momentum
            # Factor (1 + (day - 3) * 0.1) adds slight acceleration/deceleration
            daily_change = (trend * 0.1 + momentum) * (1 + (day - 3) * 0.1)

            # Apply change to price
            price = price * (1 + daily_change)

            # Round to 2 decimal places and append
            # round(): Python built-in for rounding floats
            # Reference: https://docs.python.org/3/library/functions.html#round
            predicted_prices.append(round(price, 2))

        # Format and return predictions
        return self._format_predictions(current_price, predicted_prices, data)

    def _format_predictions(self, current_price: float, predicted_prices: List[float],
                            data: pd.DataFrame) -> Dict:
        """
        Format predictions with analysis metadata.

        Args:
            current_price (float): Current closing price
            predicted_prices (List[float]): List of 5 predicted prices
            data (pd.DataFrame): Original price data for support/resistance

        Returns:
            Dict: Formatted predictions with trend, confidence, and analysis
        """
        # Get current date for prediction dates
        # datetime.now(): Current local datetime
        # Reference: https://docs.python.org/3/library/datetime.html#datetime.datetime.now
        today = datetime.now()

        # Generate dates for next 5 trading days
        # timedelta(days=i+1): Duration of (i+1) days
        # strftime('%Y-%m-%d'): Format datetime as ISO date string
        # List comprehension for efficient list creation
        # Reference: https://docs.python.org/3/library/datetime.html#datetime.timedelta
        prediction_dates = [(today + timedelta(days=i + 1)).strftime('%Y-%m-%d')
                           for i in range(5)]

        # Calculate price change metrics
        # predicted_prices[-1]: Get last (5th day) prediction
        final_price = predicted_prices[-1]
        price_change = final_price - current_price
        price_change_pct = (price_change / current_price) * 100

        # Determine trend direction and confidence
        # Thresholds: >2% = BULLISH, <-2% = BEARISH, else NEUTRAL
        if price_change_pct > 2:
            trend = "BULLISH"
            # Confidence increases with price change magnitude
            # min(): Ensure confidence doesn't exceed 0.9
            # abs(): Absolute value of change percentage
            # Reference: https://docs.python.org/3/library/functions.html#min
            confidence = min(0.9, 0.5 + abs(price_change_pct) / 20)
        elif price_change_pct < -2:
            trend = "BEARISH"
            confidence = min(0.9, 0.5 + abs(price_change_pct) / 20)
        else:
            trend = "NEUTRAL"
            confidence = 0.5

        # Calculate support and resistance levels from recent data
        # pd.DataFrame.tail(n): Get last n rows
        # pd.Series.max() / min(): Get maximum/minimum values
        # Reference: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.tail.html
        recent_high = float(data['High'].tail(20).max())
        recent_low = float(data['Low'].tail(20).min())

        # Return formatted prediction dictionary
        return {
            "current_price": round(current_price, 2),
            # List of prediction objects with date and price
            # zip(): Pair up dates and prices
            # Reference: https://docs.python.org/3/library/functions.html#zip
            "predictions": [
                {"date": date, "price": round(price, 2)}
                for date, price in zip(prediction_dates, predicted_prices)
            ],
            "predicted_5d_price": round(final_price, 2),
            "predicted_change": round(price_change, 2),
            "predicted_change_pct": round(price_change_pct, 2),
            "trend": trend,
            "confidence": round(confidence, 2),
            "support": round(recent_low, 2),
            "resistance": round(recent_high, 2),
            # Indicate which model type was used
            "model_type": "LSTM" if self.model else "Momentum-based"
        }
