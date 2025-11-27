"""
Prophet-based anomaly detection for Drugstore Canary
Uses Facebook Prophet for time-series forecasting and anomaly detection
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

try:
    from prophet import Prophet
except ImportError:
    print("Warning: Prophet not installed. Run: pip install prophet")
    Prophet = None

from config import MODEL_CONFIG, ANOMALY_THRESHOLDS


class ProphetDetector:
    """Anomaly detection using Facebook Prophet"""
    
    def __init__(self, config: Dict = None):
        if Prophet is None:
            raise ImportError("Prophet is required. Install with: pip install prophet")
        
        self.config = config or MODEL_CONFIG["prophet"]
        self.model = None
        self.forecast = None
        self.mean = 0
        self.std = 1
        
    def train(self, df: pd.DataFrame) -> None:
        """
        Train Prophet model on historical data
        
        Args:
            df: DataFrame with columns 'ds' (date) and 'y' (value)
        """
        if df.empty or len(df) < 2:
            raise ValueError("Insufficient data for training")
        
        # Store statistics for normalization
        self.mean = df["y"].mean()
        self.std = df["y"].std() + 1e-8
        
        # Initialize Prophet model
        self.model = Prophet(
            changepoint_prior_scale=self.config["changepoint_prior_scale"],
            seasonality_prior_scale=self.config["seasonality_prior_scale"],
            seasonality_mode=self.config["seasonality_mode"],
            yearly_seasonality=self.config["yearly_seasonality"],
            weekly_seasonality=self.config["weekly_seasonality"],
            daily_seasonality=self.config["daily_seasonality"],
        )
        
        # Fit model
        self.model.fit(df)
        
    def predict(self, periods: int = 30) -> pd.DataFrame:
        """
        Generate forecast for future periods
        
        Args:
            periods: Number of days to forecast
            
        Returns:
            DataFrame with forecast results
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Create future dataframe
        future = self.model.make_future_dataframe(periods=periods)
        
        # Generate forecast
        self.forecast = self.model.predict(future)
        
        return self.forecast
    
    def detect_anomalies(
        self, 
        df: pd.DataFrame,
        threshold_std: float = 2.0
    ) -> pd.DataFrame:
        """
        Detect anomalies in the data
        
        Args:
            df: DataFrame with actual values (ds, y)
            threshold_std: Number of standard deviations for anomaly threshold
            
        Returns:
            DataFrame with anomaly detection results
        """
        if self.model is None:
            # Train if not already trained
            self.train(df)
        
        # Generate forecast for the same period
        forecast = self.model.predict(df[["ds"]])
        
        # Merge actual and predicted
        results = df.copy()
        results["yhat"] = forecast["yhat"]
        results["yhat_lower"] = forecast["yhat_lower"]
        results["yhat_upper"] = forecast["yhat_upper"]
        
        # Calculate residuals
        results["residual"] = results["y"] - results["yhat"]
        results["residual_abs"] = np.abs(results["residual"])
        
        # Calculate anomaly score (normalized residual)
        residual_std = results["residual"].std() + 1e-8
        results["anomaly_score"] = results["residual_abs"] / residual_std
        
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
    
    def get_recent_anomalies(
        self, 
        results: pd.DataFrame, 
        days: int = 7
    ) -> pd.DataFrame:
        """
        Get anomalies from recent days
        
        Args:
            results: DataFrame from detect_anomalies()
            days: Number of recent days to check
            
        Returns:
            DataFrame with recent anomalies
        """
        if results.empty:
            return results
        
        # Get recent data
        cutoff_date = results["ds"].max() - timedelta(days=days)
        recent = results[results["ds"] >= cutoff_date]
        
        # Filter anomalies
        anomalies = recent[recent["is_anomaly"] == True]
        
        return anomalies
    
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
        
        # Recent anomalies
        recent_anomalies = self.get_recent_anomalies(results, days=3)
        
        if recent_anomalies.empty:
            return 0.0
        
        # Average anomaly score
        avg_score = recent_anomalies["anomaly_score"].mean()
        
        # Consistency (how many consecutive days)
        consecutive_days = self._count_consecutive_anomalies(results)
        
        # Confidence based on score and consistency
        score_confidence = min(avg_score / 5.0, 1.0)  # Normalize to 0-1
        consistency_confidence = min(consecutive_days / 3.0, 1.0)  # 3+ days = high confidence
        
        # Combined confidence
        confidence = (score_confidence * 0.6 + consistency_confidence * 0.4)
        
        return min(confidence, 1.0)
    
    def _count_consecutive_anomalies(self, results: pd.DataFrame) -> int:
        """Count consecutive anomaly days at the end of the series"""
        if results.empty:
            return 0
        
        # Sort by date
        results = results.sort_values("ds", ascending=False)
        
        # Count consecutive anomalies from most recent
        count = 0
        for _, row in results.iterrows():
            if row["is_anomaly"]:
                count += 1
            else:
                break
        
        return count
    
    def save_model(self, filepath: str) -> None:
        """Save trained model to file"""
        import pickle
        
        if self.model is None:
            raise ValueError("No model to save")
        
        with open(filepath, "wb") as f:
            pickle.dump({
                "model": self.model,
                "config": self.config,
                "mean": self.mean,
                "std": self.std
            }, f)
    
    def load_model(self, filepath: str) -> None:
        """Load trained model from file"""
        import pickle
        
        with open(filepath, "rb") as f:
            data = pickle.load(f)
            self.model = data["model"]
            self.config = data["config"]
            self.mean = data["mean"]
            self.std = data["std"]


if __name__ == "__main__":
    # Test Prophet detector
    print("Testing Prophet Anomaly Detector...")
    
    # Create sample data
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    values = 20 + 5 * np.sin(np.arange(100) * 2 * np.pi / 7) + np.random.normal(0, 2, 100)
    
    # Inject anomaly
    values[80:85] = values[80:85] * 3
    
    df = pd.DataFrame({"ds": dates, "y": values})
    
    # Train and detect
    detector = ProphetDetector()
    detector.train(df)
    results = detector.detect_anomalies(df)
    
    print(f"\nDetected {results['is_anomaly'].sum()} anomalies")
    print(f"Confidence: {detector.calculate_confidence(results):.2f}")
    
    # Show recent anomalies
    recent_anomalies = detector.get_recent_anomalies(results, days=30)
    if not recent_anomalies.empty:
        print(f"\nRecent anomalies:")
        print(recent_anomalies[["ds", "y", "yhat", "anomaly_score", "severity"]].tail())
