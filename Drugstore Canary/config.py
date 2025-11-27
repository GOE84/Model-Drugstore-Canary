"""
Configuration settings for Drugstore Canary system
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Database settings
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/data/drugstore_canary.db")

# Model settings
MODEL_CONFIG = {
    "prophet": {
        "changepoint_prior_scale": 0.05,
        "seasonality_prior_scale": 10.0,
        "seasonality_mode": "multiplicative",
        "yearly_seasonality": True,
        "weekly_seasonality": True,
        "daily_seasonality": False,
    },
    "lstm": {
        "lookback_days": 14,
        "lstm_units": [64, 32],
        "dropout_rate": 0.2,
        "learning_rate": 0.001,
        "epochs": 100,
        "batch_size": 32,
    },
    "ensemble": {
        "prophet_weight": 0.6,
        "lstm_weight": 0.4,
        "confidence_threshold": 0.7,
    }
}

# Anomaly detection thresholds
ANOMALY_THRESHOLDS = {
    "low": 1.5,      # 1.5 standard deviations
    "medium": 2.0,   # 2.0 standard deviations
    "high": 2.5,     # 2.5 standard deviations
    "critical": 3.0, # 3.0 standard deviations
}

# Alert settings
ALERT_CONFIG = {
    "min_anomaly_duration_days": 2,  # Require anomaly for 2+ consecutive days
    "cooldown_period_hours": 24,     # Don't re-alert for same zone within 24 hours
    "enable_notifications": True,
}

# Hat Yai zone definitions (simplified - can be expanded with real coordinates)
HAT_YAI_ZONES = {
    "zone_a": {
        "name": "ตัวเมืองหาดใหญ่",
        "center_lat": 7.0087,
        "center_lon": 100.4754,
        "pharmacies": ["pharmacy_001", "pharmacy_002", "pharmacy_003"],
    },
    "zone_b": {
        "name": "คลองแห",
        "center_lat": 7.0200,
        "center_lon": 100.4900,
        "pharmacies": ["pharmacy_004", "pharmacy_005"],
    },
    "zone_c": {
        "name": "คอหงส์",
        "center_lat": 6.9900,
        "center_lon": 100.4600,
        "pharmacies": ["pharmacy_006", "pharmacy_007", "pharmacy_008"],
    },
    "zone_d": {
        "name": "ควนลัง",
        "center_lat": 7.0400,
        "center_lon": 100.5000,
        "pharmacies": ["pharmacy_009", "pharmacy_010"],
    },
}

# Medicine categories for tracking
MEDICINE_CATEGORIES = {
    "fever": ["paracetamol", "ibuprofen", "aspirin"],
    "diarrhea": ["oral_rehydration_salts", "loperamide", "electrolyte_powder"],
    "skin_infection": ["antibiotic_ointment", "antifungal_cream", "antiseptic"],
    "allergy": ["antihistamine", "loratadine", "cetirizine"],
    "pain": ["analgesics", "muscle_relaxants"],
    "respiratory": ["cough_syrup", "decongestant", "throat_lozenges"],
}

# API settings
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "reload": True,
    "log_level": "info",
}

# LINE Notify settings (optional)
LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")

# Data generation settings (for synthetic data)
SYNTHETIC_DATA_CONFIG = {
    "num_pharmacies": 10,
    "start_date": "2024-01-01",
    "num_days": 365,
    "base_daily_sales": {
        "fever": 20,
        "diarrhea": 15,
        "skin_infection": 10,
        "allergy": 12,
        "pain": 25,
        "respiratory": 18,
    },
    "noise_level": 0.2,  # 20% random variation
    "outbreak_scenarios": [
        {
            "start_day": 180,
            "duration_days": 14,
            "affected_zones": ["zone_a", "zone_b"],
            "medicine_category": "diarrhea",
            "spike_multiplier": 3.5,
        },
        {
            "start_day": 250,
            "duration_days": 10,
            "affected_zones": ["zone_c"],
            "medicine_category": "skin_infection",
            "spike_multiplier": 4.0,
        },
    ]
}
