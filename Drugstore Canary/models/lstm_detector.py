"""
LSTM-based anomaly detection for Drugstore Canary
Uses LSTM neural network for sequential pattern learning and anomaly detection
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
except ImportError:
    print("Warning: TensorFlow not installed. Run: pip install tensorflow")
    tf = None
    keras = None
    layers = None

from config import MODEL_CONFIG, ANOMALY_THRESHOLDS


class LSTMDetector:
    """Anomaly detection using LSTM neural network"""
    
    def __init__(self, config: Dict = None):
        if tf is None:
            raise ImportError("TensorFlow is required. Install with: pip install tensorflow")
        
        self.config = config or MODEL_CONFIG["lstm"]
        self.model = None
        self.mean = 0
        self.std = 1
        self.lookback_days = self.config["lookback_days"]
        
    def build_model(self, input_shape: Tuple) -> None:
        """
        Build LSTM model architecture
        
        Args:
            input_shape: Shape of input data (lookback_days, features)
        """
        model = keras.Sequential([
            # First LSTM layer
            layers.LSTM(
                self.config["lstm_units"][0],
                return_sequences=True,
                input_shape=input_shape
            ),
            layers.Dropout(self.config["dropout_rate"]),
            
            # Second LSTM layer
            layers.LSTM(
                self.config["lstm_units"][1],
                return_sequences=False
            ),
            layers.Dropout(self.config["dropout_rate"]),
            
            # Dense layers
            layers.Dense(16, activation="relu"),
            layers.Dense(1)
        ])
        
        # Compile model
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.config["learning_rate"]),
            loss="mse",
            metrics=["mae"]
        )
        
        self.model = model
        
    def train(
        self, 
        X_train: np.ndarray, 
        y_train: np.ndarray,
        validation_split: float = 0.2,
        verbose: int = 0
    ) -> Dict:
        """
        Train LSTM model
        
        Args:
            X_train: Training sequences (n_samples, lookback_days, features)
            y_train: Training targets (n_samples, 1)
            validation_split: Fraction of data for validation
            verbose: Verbosity level
            
        Returns:
            Training history
        """
        if X_train.shape[0] == 0:
            raise ValueError("Insufficient training data")
        
        # Build model if not already built
        if self.model is None:
            input_shape = (X_train.shape[1], X_train.shape[2])
            self.build_model(input_shape)
        
        # Train model
        history = self.model.fit(
            X_train, y_train,
            epochs=self.config["epochs"],
            batch_size=self.config["batch_size"],
            validation_split=validation_split,
            verbose=verbose,
            callbacks=[
                keras.callbacks.EarlyStopping(
                    monitor="val_loss",
                    patience=10,
                    restore_best_weights=True
                )
            ]
        )
        
        return history.history
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Generate predictions
        
        Args:
            X: Input sequences (n_samples, lookback_days, features)
            
        Returns:
            Predictions (n_samples, 1)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        return self.model.predict(X, verbose=0)
    
    def detect_anomalies(
        self,
        X: np.ndarray,
        y_actual: np.ndarray,
        threshold_std: float = 2.0
    ) -> pd.DataFrame:
        """
        Detect anomalies using reconstruction error
        
        Args:
            X: Input sequences
            y_actual: Actual values
            threshold_std: Number of standard deviations for threshold
            
        Returns:
            DataFrame with anomaly detection results
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Generate predictions
        y_pred = self.predict(X)
        
        # Calculate reconstruction error
        errors = np.abs(y_actual - y_pred)
        
        # Calculate anomaly scores
        error_mean = np.mean(errors)
        error_std = np.std(errors) + 1e-8
        anomaly_scores = (errors - error_mean) / error_std
        
        # Create results DataFrame
        results = pd.DataFrame({
            "actual": y_actual.flatten(),
            "predicted": y_pred.flatten(),
            "error": errors.flatten(),
            "anomaly_score": anomaly_scores.flatten()
        })
        
        # Detect anomalies
        results["is_anomaly"] = results["anomaly_score"] > threshold_std
        
        # Classify severity
        results["severity"] = results["anomaly_score"].apply(
            lambda x: self._classify_severity(x)
        )
        
        return results
    
    def _classify_severity(self, anomaly_score: float) -> str:
        """Classify anomaly severity based on score"""
        if anomaly_score < ANOMALY_THRESHOLDS["low"]:
            return "normal"
        elif anomaly_score < ANOMALY_THRESHOLDS["medium"]:
            return "low"
        elif anomaly_score < ANOMALY_THRESHOLDS["high"]:
            return "medium"
        elif anomaly_score < ANOMALY_THRESHOLDS["critical"]:
            return "high"
        else:
            return "critical"
    
    def calculate_confidence(self, results: pd.DataFrame) -> float:
        """
        Calculate confidence score for anomaly detection
        
        Args:
            results: DataFrame from detect_anomalies()
            
        Returns:
            Confidence score (0-1)
        """
        if results.empty or "anomaly_score" not in results.columns:
            return 0.0
        
        # Recent anomalies (last 3 data points)
        recent = results.tail(3)
        recent_anomalies = recent[recent["is_anomaly"] == True]
        
        if recent_anomalies.empty:
            return 0.0
        
        # Average anomaly score
        avg_score = recent_anomalies["anomaly_score"].mean()
        
        # Consistency
        consecutive_count = self._count_consecutive_anomalies(results)
        
        # Confidence calculation
        score_confidence = min(avg_score / 5.0, 1.0)
        consistency_confidence = min(consecutive_count / 3.0, 1.0)
        
        confidence = (score_confidence * 0.6 + consistency_confidence * 0.4)
        
        return min(confidence, 1.0)
    
    def _count_consecutive_anomalies(self, results: pd.DataFrame) -> int:
        """Count consecutive anomalies at the end"""
        if results.empty:
            return 0
        
        count = 0
        for i in range(len(results) - 1, -1, -1):
            if results.iloc[i]["is_anomaly"]:
                count += 1
            else:
                break
        
        return count
    
    def save_model(self, filepath: str) -> None:
        """Save trained model"""
        if self.model is None:
            raise ValueError("No model to save")
        
        self.model.save(filepath)
        
        # Save config separately
        import json
        config_path = filepath.replace(".h5", "_config.json")
        with open(config_path, "w") as f:
            json.dump({
                "config": self.config,
                "mean": float(self.mean),
                "std": float(self.std),
                "lookback_days": self.lookback_days
            }, f)
    
    def load_model(self, filepath: str) -> None:
        """Load trained model"""
        import json
        
        self.model = keras.models.load_model(filepath)
        
        # Load config
        config_path = filepath.replace(".h5", "_config.json")
        with open(config_path, "r") as f:
            data = json.load(f)
            self.config = data["config"]
            self.mean = data["mean"]
            self.std = data["std"]
            self.lookback_days = data["lookback_days"]


if __name__ == "__main__":
    # Test LSTM detector
    print("Testing LSTM Anomaly Detector...")
    
    # Create sample data
    np.random.seed(42)
    n_samples = 100
    lookback = 14
    
    # Generate synthetic time series
    t = np.arange(n_samples)
    values = 20 + 5 * np.sin(t * 2 * np.pi / 7) + np.random.normal(0, 2, n_samples)
    
    # Inject anomaly
    values[80:85] = values[80:85] * 3
    
    # Normalize
    mean = np.mean(values)
    std = np.std(values)
    normalized = (values - mean) / std
    
    # Create sequences
    X, y = [], []
    for i in range(len(normalized) - lookback):
        X.append(normalized[i:i + lookback])
        y.append(normalized[i + lookback])
    
    X = np.array(X).reshape(-1, lookback, 1)
    y = np.array(y).reshape(-1, 1)
    
    # Split train/test
    split = int(0.7 * len(X))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    # Train detector
    detector = LSTMDetector()
    print("\nTraining LSTM model...")
    history = detector.train(X_train, y_train, verbose=1)
    
    # Detect anomalies
    results = detector.detect_anomalies(X_test, y_test)
    
    print(f"\nDetected {results['is_anomaly'].sum()} anomalies")
    print(f"Confidence: {detector.calculate_confidence(results):.2f}")
    
    if results["is_anomaly"].any():
        print("\nAnomaly details:")
        print(results[results["is_anomaly"]][["actual", "predicted", "anomaly_score", "severity"]])
