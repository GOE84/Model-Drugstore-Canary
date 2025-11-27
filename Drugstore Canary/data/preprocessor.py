"""
Data preprocessing pipeline for Drugstore Canary
Prepares sales data for anomaly detection models
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from data.database import get_session, PharmacySales, MedicineType, Pharmacy
from config import HAT_YAI_ZONES


class DataPreprocessor:
    """Preprocess pharmacy sales data for ML models"""
    
    def __init__(self):
        self.session = get_session()
    
    def get_zone_sales(
        self, 
        zone_id: str, 
        category: str, 
        start_date: datetime = None,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Get aggregated sales data for a zone and medicine category
        
        Args:
            zone_id: Zone identifier
            category: Medicine category (fever, diarrhea, etc.)
            start_date: Start date for data
            end_date: End date for data
            
        Returns:
            DataFrame with columns: date, quantity_sold
        """
        query = self.session.query(
            PharmacySales.date,
            PharmacySales.quantity_sold,
            MedicineType.category,
            Pharmacy.zone_id
        ).join(
            MedicineType, PharmacySales.medicine_id == MedicineType.id
        ).join(
            Pharmacy, PharmacySales.pharmacy_id == Pharmacy.id
        ).filter(
            Pharmacy.zone_id == zone_id,
            MedicineType.category == category
        )
        
        if start_date:
            query = query.filter(PharmacySales.date >= start_date)
        if end_date:
            query = query.filter(PharmacySales.date <= end_date)
        
        # Execute query and convert to DataFrame
        results = query.all()
        df = pd.DataFrame([
            {"date": r.date, "quantity_sold": r.quantity_sold}
            for r in results
        ])
        
        if df.empty:
            return pd.DataFrame(columns=["date", "quantity_sold"])
        
        # Aggregate by date (sum across all pharmacies in zone)
        df = df.groupby("date").agg({"quantity_sold": "sum"}).reset_index()
        df = df.sort_values("date")
        
        return df
    
    def prepare_for_prophet(
        self, 
        zone_id: str, 
        category: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> pd.DataFrame:
        """
        Prepare data in Prophet format (ds, y columns)
        
        Args:
            zone_id: Zone identifier
            category: Medicine category
            start_date: Start date
            end_date: End date
            
        Returns:
            DataFrame with columns: ds (date), y (value)
        """
        df = self.get_zone_sales(zone_id, category, start_date, end_date)
        
        if df.empty:
            return pd.DataFrame(columns=["ds", "y"])
        
        # Rename columns for Prophet
        df_prophet = df.rename(columns={"date": "ds", "quantity_sold": "y"})
        
        # Ensure daily frequency (fill missing dates with 0)
        df_prophet = self._fill_missing_dates(df_prophet)
        
        return df_prophet
    
    def prepare_for_lstm(
        self,
        zone_id: str,
        category: str,
        lookback_days: int = 14,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        """
        Prepare data for LSTM model with sliding window
        
        Args:
            zone_id: Zone identifier
            category: Medicine category
            lookback_days: Number of days to look back
            start_date: Start date
            end_date: End date
            
        Returns:
            Tuple of (X, y, original_df)
            X: Input sequences (n_samples, lookback_days, 1)
            y: Target values (n_samples, 1)
            original_df: Original data for reference
        """
        df = self.get_zone_sales(zone_id, category, start_date, end_date)
        
        if df.empty or len(df) < lookback_days + 1:
            return np.array([]), np.array([]), df
        
        # Fill missing dates
        df = self._fill_missing_dates(df.rename(columns={"date": "ds", "quantity_sold": "y"}))
        
        # Normalize data
        values = df["y"].values
        mean = np.mean(values)
        std = np.std(values)
        normalized = (values - mean) / (std + 1e-8)
        
        # Create sequences
        X, y = [], []
        for i in range(len(normalized) - lookback_days):
            X.append(normalized[i:i + lookback_days])
            y.append(normalized[i + lookback_days])
        
        X = np.array(X).reshape(-1, lookback_days, 1)
        y = np.array(y).reshape(-1, 1)
        
        # Store normalization parameters in df
        df["mean"] = mean
        df["std"] = std
        
        return X, y, df
    
    def add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add engineered features to the dataset
        
        Args:
            df: DataFrame with date and quantity columns
            
        Returns:
            DataFrame with additional features
        """
        df = df.copy()
        
        # Rolling statistics
        df["rolling_mean_7d"] = df["y"].rolling(window=7, min_periods=1).mean()
        df["rolling_std_7d"] = df["y"].rolling(window=7, min_periods=1).std()
        df["rolling_mean_14d"] = df["y"].rolling(window=14, min_periods=1).mean()
        
        # Lag features
        df["lag_1d"] = df["y"].shift(1)
        df["lag_7d"] = df["y"].shift(7)
        
        # Day of week
        df["day_of_week"] = pd.to_datetime(df["ds"]).dt.dayofweek
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        
        # Fill NaN values
        df = df.fillna(method="bfill").fillna(0)
        
        return df
    
    def _fill_missing_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing dates in time series with 0 values"""
        if df.empty:
            return df
        
        # Ensure ds is datetime
        df["ds"] = pd.to_datetime(df["ds"])
        
        # Create complete date range
        date_range = pd.date_range(
            start=df["ds"].min(),
            end=df["ds"].max(),
            freq="D"
        )
        
        # Reindex and fill missing values
        df = df.set_index("ds").reindex(date_range, fill_value=0).reset_index()
        df = df.rename(columns={"index": "ds"})
        
        return df
    
    def get_all_zone_category_pairs(self) -> List[Tuple[str, str]]:
        """Get all valid zone-category combinations"""
        from config import MEDICINE_CATEGORIES
        
        pairs = []
        for zone_id in HAT_YAI_ZONES.keys():
            for category in MEDICINE_CATEGORIES.keys():
                pairs.append((zone_id, category))
        
        return pairs
    
    def close(self):
        """Close database session"""
        self.session.close()


if __name__ == "__main__":
    # Test preprocessing
    preprocessor = DataPreprocessor()
    
    print("Testing data preprocessing...")
    
    # Test Prophet format
    df_prophet = preprocessor.prepare_for_prophet("zone_a", "diarrhea")
    print(f"\nProphet format data shape: {df_prophet.shape}")
    print(df_prophet.head())
    
    # Test LSTM format
    X, y, df_original = preprocessor.prepare_for_lstm("zone_a", "diarrhea", lookback_days=14)
    print(f"\nLSTM format:")
    print(f"  X shape: {X.shape}")
    print(f"  y shape: {y.shape}")
    
    # Test feature engineering
    df_features = preprocessor.add_features(df_prophet)
    print(f"\nFeature-enriched data columns: {df_features.columns.tolist()}")
    
    preprocessor.close()
