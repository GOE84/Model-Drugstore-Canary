"""
Synthetic data generator for testing Drugstore Canary system
Generates realistic pharmacy sales data with outbreak scenarios
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from config import (
    HAT_YAI_ZONES, 
    MEDICINE_CATEGORIES, 
    SYNTHETIC_DATA_CONFIG
)
from data.database import (
    init_db, get_session, Zone, Pharmacy, 
    MedicineType, PharmacySales, FloodData
)


class SyntheticDataGenerator:
    """Generate synthetic pharmacy sales data with realistic patterns"""
    
    def __init__(self, config: Dict = None):
        self.config = config or SYNTHETIC_DATA_CONFIG
        self.start_date = datetime.strptime(self.config["start_date"], "%Y-%m-%d")
        self.num_days = self.config["num_days"]
        self.base_sales = self.config["base_daily_sales"]
        self.noise_level = self.config["noise_level"]
        
    def generate_base_pattern(self, category: str, num_days: int) -> np.ndarray:
        """Generate base sales pattern with weekly seasonality"""
        base_value = self.base_sales.get(category, 15)
        
        # Create time series
        t = np.arange(num_days)
        
        # Weekly pattern (higher sales on weekends)
        weekly_pattern = 1 + 0.2 * np.sin(2 * np.pi * t / 7)
        
        # Monthly pattern (slight increase mid-month)
        monthly_pattern = 1 + 0.1 * np.sin(2 * np.pi * t / 30)
        
        # Random noise
        noise = 1 + np.random.normal(0, self.noise_level, num_days)
        
        # Combine patterns
        sales = base_value * weekly_pattern * monthly_pattern * noise
        
        return np.maximum(sales, 0)  # Ensure non-negative
    
    def inject_outbreak(self, sales: np.ndarray, outbreak: Dict) -> np.ndarray:
        """Inject outbreak pattern into sales data"""
        start_day = outbreak["start_day"]
        duration = outbreak["duration_days"]
        multiplier = outbreak["spike_multiplier"]
        
        # Create gradual increase and decrease
        outbreak_pattern = np.zeros(len(sales))
        
        # Ramp up (3 days)
        ramp_up_days = min(3, duration // 3)
        for i in range(ramp_up_days):
            day_idx = start_day + i
            if day_idx < len(sales):
                outbreak_pattern[day_idx] = multiplier * (i + 1) / ramp_up_days
        
        # Peak period
        peak_start = start_day + ramp_up_days
        peak_end = start_day + duration - ramp_up_days
        outbreak_pattern[peak_start:peak_end] = multiplier
        
        # Ramp down
        for i in range(ramp_up_days):
            day_idx = peak_end + i
            if day_idx < len(sales):
                outbreak_pattern[day_idx] = multiplier * (ramp_up_days - i) / ramp_up_days
        
        return sales * (1 + outbreak_pattern)
    
    def generate_pharmacy_sales(self, pharmacy_id: str, zone_id: str) -> pd.DataFrame:
        """Generate sales data for a single pharmacy"""
        data = []
        
        for category, medicines in MEDICINE_CATEGORIES.items():
            # Generate base pattern
            sales = self.generate_base_pattern(category, self.num_days)
            
            # Apply outbreak scenarios
            for outbreak in self.config["outbreak_scenarios"]:
                if zone_id in outbreak["affected_zones"] and category == outbreak["medicine_category"]:
                    sales = self.inject_outbreak(sales, outbreak)
            
            # Create records for each day
            for day_idx in range(self.num_days):
                date = self.start_date + timedelta(days=day_idx)
                quantity = int(np.round(sales[day_idx]))
                
                data.append({
                    "pharmacy_id": pharmacy_id,
                    "zone_id": zone_id,
                    "category": category,
                    "date": date,
                    "quantity_sold": quantity
                })
        
        return pd.DataFrame(data)
    
    def generate_flood_events(self) -> List[Dict]:
        """Generate synthetic flood event data"""
        flood_events = []
        
        # Simulate flood events that correlate with outbreak scenarios
        for outbreak in self.config["outbreak_scenarios"]:
            # Flood occurs 3-5 days before outbreak
            flood_start = outbreak["start_day"] - np.random.randint(3, 6)
            
            for zone_id in outbreak["affected_zones"]:
                flood_date = self.start_date + timedelta(days=flood_start)
                
                flood_events.append({
                    "zone_id": zone_id,
                    "date": flood_date,
                    "water_level_cm": np.random.uniform(30, 100),
                    "duration_hours": np.random.uniform(12, 48),
                    "severity": np.random.choice(["medium", "high"], p=[0.6, 0.4])
                })
        
        return flood_events
    
    def populate_database(self):
        """Populate database with synthetic data"""
        print("Initializing database...")
        init_db()
        session = get_session()
        
        try:
            # Create zones
            print("Creating zones...")
            for zone_id, zone_data in HAT_YAI_ZONES.items():
                zone = Zone(
                    id=zone_id,
                    name=zone_data["name"],
                    center_lat=zone_data["center_lat"],
                    center_lon=zone_data["center_lon"]
                )
                session.merge(zone)
            session.commit()
            
            # Create medicine types
            print("Creating medicine types...")
            medicine_map = {}
            for category, medicines in MEDICINE_CATEGORIES.items():
                for medicine_name in medicines:
                    med = MedicineType(
                        category=category,
                        name=medicine_name,
                        description=f"{medicine_name} in {category} category"
                    )
                    session.add(med)
                    session.flush()
                    medicine_map[f"{category}_{medicine_name}"] = med.id
            session.commit()
            
            # Create pharmacies
            print("Creating pharmacies...")
            all_pharmacies = []
            for zone_id, zone_data in HAT_YAI_ZONES.items():
                for pharmacy_id in zone_data["pharmacies"]:
                    # Random location near zone center
                    lat_offset = np.random.uniform(-0.01, 0.01)
                    lon_offset = np.random.uniform(-0.01, 0.01)
                    
                    pharmacy = Pharmacy(
                        id=pharmacy_id,
                        name=f"ร้านยา {pharmacy_id}",
                        zone_id=zone_id,
                        latitude=zone_data["center_lat"] + lat_offset,
                        longitude=zone_data["center_lon"] + lon_offset
                    )
                    session.merge(pharmacy)
                    all_pharmacies.append((pharmacy_id, zone_id))
            session.commit()
            
            # Generate sales data
            print(f"Generating sales data for {len(all_pharmacies)} pharmacies...")
            for pharmacy_id, zone_id in all_pharmacies:
                print(f"  Processing {pharmacy_id}...")
                df = self.generate_pharmacy_sales(pharmacy_id, zone_id)
                
                # Insert sales records
                for _, row in df.iterrows():
                    # Get medicine_id for first medicine in category
                    category = row["category"]
                    first_medicine = MEDICINE_CATEGORIES[category][0]
                    medicine_id = medicine_map.get(f"{category}_{first_medicine}")
                    
                    if medicine_id:
                        sale = PharmacySales(
                            pharmacy_id=row["pharmacy_id"],
                            medicine_id=medicine_id,
                            date=row["date"],
                            quantity_sold=row["quantity_sold"]
                        )
                        session.add(sale)
                
                # Commit in batches
                session.commit()
            
            # Generate flood events
            print("Generating flood events...")
            flood_events = self.generate_flood_events()
            for event in flood_events:
                flood = FloodData(**event)
                session.add(flood)
            session.commit()
            
            print(f"\n✅ Successfully generated synthetic data!")
            print(f"   - Zones: {len(HAT_YAI_ZONES)}")
            print(f"   - Pharmacies: {len(all_pharmacies)}")
            print(f"   - Days of data: {self.num_days}")
            print(f"   - Outbreak scenarios: {len(self.config['outbreak_scenarios'])}")
            print(f"   - Flood events: {len(flood_events)}")
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error generating data: {e}")
            raise
        finally:
            session.close()


if __name__ == "__main__":
    generator = SyntheticDataGenerator()
    generator.populate_database()
