"""
Ensemble model combining Prophet and LSTM detectors
Provides more robust anomaly detection through weighted voting
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from models.prophet_detector import ProphetDetector
from models.lstm_detector import LSTMDetector
from config import MODEL_CONFIG, ANOMALY_THRESHOLDS


class EnsembleDetector:
    """Ensemble anomaly detector combining Prophet and LSTM"""
    
    def __init__(self, config: Dict = None):
        self.config = config or MODEL_CONFIG["ensemble"]
        self.prophet_detector = ProphetDetector()
        self.lstm_detector = LSTMDetector()
        self.prophet_weight = self.config["prophet_weight"]
        self.lstm_weight = self.config["lstm_weight"]
        
    def train(
        self,
        df_prophet: pd.DataFrame,
        X_lstm: np.ndarray,
        y_lstm: np.ndarray
    ) -> Dict:
        """
        Train both models
        
        Args:
            df_prophet: Prophet format data (ds, y)
            X_lstm: LSTM input sequences
            y_lstm: LSTM target values
            
        Returns:
            Training results
        """
        results = {}
        
        # Train Prophet
        print("Training Prophet model...")
        self.prophet_detector.train(df_prophet)
        results["prophet"] = "trained"
        
        # Train LSTM
        print("Training LSTM model...")
        lstm_history = self.lstm_detector.train(X_lstm, y_lstm, verbose=0)
        results["lstm"] = lstm_history
        
        return results
    
    def detect_anomalies(
        self,
        df_prophet: pd.DataFrame,
        X_lstm: np.ndarray,
        y_lstm: np.ndarray,
        threshold_std: float = 2.0
    ) -> pd.DataFrame:
        """
        Detect anomalies using ensemble approach
        
        Args:
            df_prophet: Prophet format data
            X_lstm: LSTM input sequences
            y_lstm: LSTM actual values
            threshold_std: Anomaly threshold
            
        Returns:
            DataFrame with ensemble anomaly detection results
        """
        # Get Prophet results
        prophet_results = self.prophet_detector.detect_anomalies(
            df_prophet, 
            threshold_std=threshold_std
        )
        
        # Get LSTM results
        lstm_results = self.lstm_detector.detect_anomalies(
            X_lstm,
            y_lstm,
            threshold_std=threshold_std
        )
        
        # Align results (LSTM has fewer samples due to lookback)
        lookback = self.lstm_detector.lookback_days
        prophet_aligned = prophet_results.iloc[lookback:].reset_index(drop=True)
        
        # Combine anomaly scores
        ensemble_score = (
            prophet_aligned["anomaly_score"].values * self.prophet_weight +
            lstm_results["anomaly_score"].values * self.lstm_weight
        )
        
        # Create ensemble results
        results = pd.DataFrame({
            "ds": prophet_aligned["ds"].values,
            "actual": prophet_aligned["y"].values,
            "prophet_score": prophet_aligned["anomaly_score"].values,
            "lstm_score": lstm_results["anomaly_score"].values,
            "ensemble_score": ensemble_score,
            "prophet_anomaly": prophet_aligned["is_anomaly"].values,
            "lstm_anomaly": lstm_results["is_anomaly"].values
        })
        
        # Ensemble anomaly detection
        results["is_anomaly"] = results["ensemble_score"] > threshold_std
        
        # Classify severity
        results["severity"] = results["ensemble_score"].apply(
            lambda x: self._classify_severity(x)
        )
        
        # Calculate agreement
        results["model_agreement"] = (
            results["prophet_anomaly"] == results["lstm_anomaly"]
        ).astype(int)
        
        return results
    
    def _classify_severity(self, anomaly_score: float) -> str:
        """Classify anomaly severity"""
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
        Calculate ensemble confidence score
        
        Args:
            results: DataFrame from detect_anomalies()
            
        Returns:
            Confidence score (0-1)
        """
        if results.empty:
            return 0.0
        
        # Get individual confidences
        prophet_conf = self._calculate_model_confidence(
            results["prophet_score"].values,
            results["prophet_anomaly"].values
        )
        
        lstm_conf = self._calculate_model_confidence(
            results["lstm_score"].values,
            results["lstm_anomaly"].values
        )
        
        # Model agreement factor
        recent_agreement = results.tail(3)["model_agreement"].mean()
        
        # Weighted ensemble confidence
        base_confidence = (
            prophet_conf * self.prophet_weight +
            lstm_conf * self.lstm_weight
        )
        
        # Boost confidence if models agree
        final_confidence = base_confidence * (0.7 + 0.3 * recent_agreement)
        
        return min(final_confidence, 1.0)
    
    def _calculate_model_confidence(
        self,
        scores: np.ndarray,
        anomalies: np.ndarray
    ) -> float:
        """Calculate confidence for a single model"""
        if len(scores) == 0:
            return 0.0
        
        # Recent anomalies
        recent_scores = scores[-3:]
        recent_anomalies = anomalies[-3:]
        
        if not recent_anomalies.any():
            return 0.0
        
        # Average score
        avg_score = recent_scores[recent_anomalies].mean() if recent_anomalies.any() else 0
        
        # Consecutive anomalies
        consecutive = 0
        for i in range(len(anomalies) - 1, -1, -1):
            if anomalies[i]:
                consecutive += 1
            else:
                break
        
        # Confidence
        score_conf = min(avg_score / 5.0, 1.0)
        consistency_conf = min(consecutive / 3.0, 1.0)
        
        return (score_conf * 0.6 + consistency_conf * 0.4)
    
    def get_alert_message(
        self,
        results: pd.DataFrame,
        zone_id: str,
        category: str
    ) -> Dict:
        """
        Generate alert message with details
        
        Args:
            results: Anomaly detection results
            zone_id: Zone identifier
            category: Medicine category
            
        Returns:
            Alert message dictionary
        """
        recent_anomalies = results[results["is_anomaly"]].tail(3)
        
        if recent_anomalies.empty:
            return None
        
        latest = recent_anomalies.iloc[-1]
        confidence = self.calculate_confidence(results)
        
        # Check if confidence meets threshold
        if confidence < self.config["confidence_threshold"]:
            return None
        
        alert = {
            "zone_id": zone_id,
            "category": category,
            "severity": latest["severity"],
            "ensemble_score": float(latest["ensemble_score"]),
            "confidence": float(confidence),
            "model_agreement": bool(latest["model_agreement"]),
            "detected_at": latest["ds"].isoformat() if hasattr(latest["ds"], "isoformat") else str(latest["ds"]),
            "message": self._generate_message(zone_id, category, latest["severity"], confidence)
        }
        
        return alert
    
    def _generate_message(
        self,
        zone_id: str,
        category: str,
        severity: str,
        confidence: float
    ) -> str:
        """Generate human-readable alert message"""
        from config import HAT_YAI_ZONES
        
        zone_name = HAT_YAI_ZONES.get(zone_id, {}).get("name", zone_id)
        
        category_thai = {
            "fever": "ยาแก้ไข้",
            "diarrhea": "ยาแก้ท้องเสีย/เกลือแร่",
            "skin_infection": "ยารักษาโรคผิวหนัง",
            "allergy": "ยาแก้แพ้",
            "pain": "ยาแก้ปวด",
            "respiratory": "ยาแก้หวัด/ไอ"
        }.get(category, category)
        
        severity_thai = {
            "low": "ต่ำ",
            "medium": "ปานกลาง",
            "high": "สูง",
            "critical": "วิกฤต"
        }.get(severity, severity)
        
        message = (
            f"⚠️ แจ้งเตือน: ยอดขาย{category_thai}ในพื้นที่{zone_name} "
            f"เพิ่มสูงผิดปกติ (ระดับ: {severity_thai}, "
            f"ความมั่นใจ: {confidence*100:.0f}%) "
            f"อาจบ่งชี้การระบาดของโรค กรุณาติดตามสถานการณ์"
        )
        
        return message


if __name__ == "__main__":
    # Test ensemble detector
    print("Testing Ensemble Anomaly Detector...")
    
    # Create sample data
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    values = 20 + 5 * np.sin(np.arange(100) * 2 * np.pi / 7) + np.random.normal(0, 2, 100)
    
    # Inject anomaly
    values[80:85] = values[80:85] * 3
    
    # Prophet format
    df_prophet = pd.DataFrame({"ds": dates, "y": values})
    
    # LSTM format
    lookback = 14
    normalized = (values - values.mean()) / values.std()
    X, y = [], []
    for i in range(len(normalized) - lookback):
        X.append(normalized[i:i + lookback])
        y.append(normalized[i + lookback])
    X = np.array(X).reshape(-1, lookback, 1)
    y = np.array(y).reshape(-1, 1)
    
    # Train ensemble
    ensemble = EnsembleDetector()
    ensemble.train(df_prophet, X, y)
    
    # Detect anomalies
    results = ensemble.detect_anomalies(df_prophet, X, y)
    
    print(f"\nDetected {results['is_anomaly'].sum()} anomalies")
    print(f"Confidence: {ensemble.calculate_confidence(results):.2f}")
    print(f"Model agreement rate: {results['model_agreement'].mean():.2%}")
    
    # Generate alert
    alert = ensemble.get_alert_message(results, "zone_a", "diarrhea")
    if alert:
        print(f"\nAlert generated:")
        print(f"  {alert['message']}")
        print(f"  Severity: {alert['severity']}")
        print(f"  Confidence: {alert['confidence']:.2f}")
