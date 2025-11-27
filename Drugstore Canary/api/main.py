"""
FastAPI backend for Drugstore Canary
Provides REST API for data ingestion, anomaly detection, and alerts
"""
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from data.database import get_session, PharmacySales, MedicineType, Pharmacy, Zone, Alert
from data.preprocessor import DataPreprocessor
from models.ensemble_model import EnsembleDetector
from config import API_CONFIG, HAT_YAI_ZONES, MEDICINE_CATEGORIES

# Initialize FastAPI app
app = FastAPI(
    title="Drugstore Canary API",
    description="Epidemic Early Warning System based on Pharmacy Sales Data",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class SalesData(BaseModel):
    pharmacy_id: str
    medicine_category: str
    date: datetime
    quantity_sold: int

class AlertResponse(BaseModel):
    id: int
    zone_id: str
    zone_name: str
    medicine_category: str
    alert_level: str
    anomaly_score: float
    confidence: float
    detected_at: datetime
    message: str
    is_active: bool

class ZoneStatus(BaseModel):
    zone_id: str
    zone_name: str
    active_alerts: int
    highest_severity: str
    categories_at_risk: List[str]

class PredictionRequest(BaseModel):
    zone_id: str
    category: str
    days_back: Optional[int] = 90

class PredictionResponse(BaseModel):
    zone_id: str
    category: str
    is_anomaly: bool
    severity: str
    confidence: float
    ensemble_score: float
    message: Optional[str]


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Drugstore Canary API",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/api/sales")
async def add_sales_data(sales: SalesData, background_tasks: BackgroundTasks):
    """
    Add new sales data and trigger anomaly detection
    """
    session = get_session()
    
    try:
        # Get medicine_id
        medicine = session.query(MedicineType).filter(
            MedicineType.category == sales.medicine_category
        ).first()
        
        if not medicine:
            raise HTTPException(status_code=400, detail="Invalid medicine category")
        
        # Add sales record
        sale = PharmacySales(
            pharmacy_id=sales.pharmacy_id,
            medicine_id=medicine.id,
            date=sales.date,
            quantity_sold=sales.quantity_sold
        )
        session.add(sale)
        session.commit()
        
        # Trigger background anomaly detection
        pharmacy = session.query(Pharmacy).filter(
            Pharmacy.id == sales.pharmacy_id
        ).first()
        
        if pharmacy:
            background_tasks.add_task(
                run_anomaly_detection,
                pharmacy.zone_id,
                sales.medicine_category
            )
        
        return {
            "status": "success",
            "message": "Sales data added successfully",
            "pharmacy_id": sales.pharmacy_id,
            "date": sales.date
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.get("/api/alerts", response_model=List[AlertResponse])
async def get_alerts(
    zone_id: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50
):
    """
    Get alerts with optional filtering
    """
    session = get_session()
    
    try:
        query = session.query(Alert, Zone).join(Zone, Alert.zone_id == Zone.id)
        
        if zone_id:
            query = query.filter(Alert.zone_id == zone_id)
        
        if active_only:
            query = query.filter(Alert.is_active == True)
        
        query = query.order_by(Alert.detected_at.desc()).limit(limit)
        
        results = query.all()
        
        alerts = []
        for alert, zone in results:
            alerts.append(AlertResponse(
                id=alert.id,
                zone_id=alert.zone_id,
                zone_name=zone.name,
                medicine_category=alert.medicine_category,
                alert_level=alert.alert_level,
                anomaly_score=alert.anomaly_score,
                confidence=alert.confidence or 0.0,
                detected_at=alert.detected_at,
                message=alert.message or "",
                is_active=alert.is_active
            ))
        
        return alerts
        
    finally:
        session.close()

@app.get("/api/zones/{zone_id}/status", response_model=ZoneStatus)
async def get_zone_status(zone_id: str):
    """
    Get current status for a specific zone
    """
    if zone_id not in HAT_YAI_ZONES:
        raise HTTPException(status_code=404, detail="Zone not found")
    
    session = get_session()
    
    try:
        # Get active alerts for zone
        alerts = session.query(Alert).filter(
            Alert.zone_id == zone_id,
            Alert.is_active == True
        ).all()
        
        if not alerts:
            return ZoneStatus(
                zone_id=zone_id,
                zone_name=HAT_YAI_ZONES[zone_id]["name"],
                active_alerts=0,
                highest_severity="normal",
                categories_at_risk=[]
            )
        
        # Determine highest severity
        severity_order = ["normal", "low", "medium", "high", "critical"]
        highest_severity = max(
            [a.alert_level for a in alerts],
            key=lambda x: severity_order.index(x)
        )
        
        # Get categories at risk
        categories_at_risk = list(set([a.medicine_category for a in alerts]))
        
        return ZoneStatus(
            zone_id=zone_id,
            zone_name=HAT_YAI_ZONES[zone_id]["name"],
            active_alerts=len(alerts),
            highest_severity=highest_severity,
            categories_at_risk=categories_at_risk
        )
        
    finally:
        session.close()

@app.post("/api/predict", response_model=PredictionResponse)
async def predict_anomaly(request: PredictionRequest):
    """
    Run anomaly detection for a specific zone and category
    """
    if request.zone_id not in HAT_YAI_ZONES:
        raise HTTPException(status_code=404, detail="Zone not found")
    
    if request.category not in MEDICINE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid medicine category")
    
    try:
        # Prepare data
        preprocessor = DataPreprocessor()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=request.days_back)
        
        # Prophet format
        df_prophet = preprocessor.prepare_for_prophet(
            request.zone_id,
            request.category,
            start_date,
            end_date
        )
        
        if df_prophet.empty or len(df_prophet) < 30:
            raise HTTPException(
                status_code=400,
                detail="Insufficient data for prediction"
            )
        
        # LSTM format
        X_lstm, y_lstm, _ = preprocessor.prepare_for_lstm(
            request.zone_id,
            request.category,
            lookback_days=14,
            start_date=start_date,
            end_date=end_date
        )
        
        if len(X_lstm) == 0:
            raise HTTPException(
                status_code=400,
                detail="Insufficient data for LSTM prediction"
            )
        
        # Run ensemble detection
        ensemble = EnsembleDetector()
        ensemble.train(df_prophet, X_lstm, y_lstm)
        results = ensemble.detect_anomalies(df_prophet, X_lstm, y_lstm)
        
        # Get latest result
        latest = results.iloc[-1]
        confidence = ensemble.calculate_confidence(results)
        
        # Generate alert if needed
        alert_data = ensemble.get_alert_message(
            results,
            request.zone_id,
            request.category
        )
        
        preprocessor.close()
        
        return PredictionResponse(
            zone_id=request.zone_id,
            category=request.category,
            is_anomaly=bool(latest["is_anomaly"]),
            severity=latest["severity"],
            confidence=float(confidence),
            ensemble_score=float(latest["ensemble_score"]),
            message=alert_data["message"] if alert_data else None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/zones")
async def get_zones():
    """Get all zones"""
    zones = []
    for zone_id, zone_data in HAT_YAI_ZONES.items():
        zones.append({
            "id": zone_id,
            "name": zone_data["name"],
            "center_lat": zone_data["center_lat"],
            "center_lon": zone_data["center_lon"],
            "num_pharmacies": len(zone_data["pharmacies"])
        })
    return zones

@app.get("/api/categories")
async def get_categories():
    """Get all medicine categories"""
    return list(MEDICINE_CATEGORIES.keys())


# Background tasks

async def run_anomaly_detection(zone_id: str, category: str):
    """
    Background task to run anomaly detection and create alerts
    """
    try:
        preprocessor = DataPreprocessor()
        session = get_session()
        
        # Get recent data (last 90 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        # Prepare data
        df_prophet = preprocessor.prepare_for_prophet(
            zone_id, category, start_date, end_date
        )
        
        if df_prophet.empty or len(df_prophet) < 30:
            return
        
        X_lstm, y_lstm, _ = preprocessor.prepare_for_lstm(
            zone_id, category, 14, start_date, end_date
        )
        
        if len(X_lstm) == 0:
            return
        
        # Run detection
        ensemble = EnsembleDetector()
        ensemble.train(df_prophet, X_lstm, y_lstm)
        results = ensemble.detect_anomalies(df_prophet, X_lstm, y_lstm)
        
        # Check for alert
        alert_data = ensemble.get_alert_message(results, zone_id, category)
        
        if alert_data:
            # Create alert in database
            alert = Alert(
                zone_id=zone_id,
                medicine_category=category,
                alert_level=alert_data["severity"],
                anomaly_score=alert_data["ensemble_score"],
                confidence=alert_data["confidence"],
                message=alert_data["message"],
                is_active=True
            )
            session.add(alert)
            session.commit()
        
        preprocessor.close()
        session.close()
        
    except Exception as e:
        print(f"Error in anomaly detection: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        reload=API_CONFIG["reload"],
        log_level=API_CONFIG["log_level"]
    )
