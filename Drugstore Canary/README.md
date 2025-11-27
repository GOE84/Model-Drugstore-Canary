# Drugstore Canary 🏥
## ระบบเตือนภัยโรคระบาดจากยอดขายยา

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)](https://fastapi.tiangolo.com/)
[![Prophet](https://img.shields.io/badge/Prophet-1.1-orange.svg)](https://facebook.github.io/prophet/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.15-red.svg)](https://www.tensorflow.org/)

**Epidemic Early Warning System** ที่ใช้ Machine Learning วิเคราะห์ยอดขายยาจากร้านขายยาและร้านสะดวกซื้อ เพื่อตรวจจับสัญญาณการระบาดของโรคก่อนที่จะปรากฏในสถิติของกระทรวงสาธารณสุข **1-2 สัปดาห์**

## 🎯 Core Concept

> **Key Insight**: ผู้ป่วยมักซื้อยาแก้ปวด ยาแก้แพ้ หรือผงเกลือแร่จากร้านยาก่อนไปโรงพยาบาล → **ยอดขายคือสัญญาณเตือนภัยล่วงหน้า**

## ✨ Features

- 🤖 **Dual ML Models**: Prophet (time-series) + LSTM (deep learning) with ensemble voting
- 📊 **Real-time Monitoring**: Live dashboard with geographic heatmap
- 🚨 **Smart Alerts**: Multi-level severity classification with confidence scoring
- 🗺️ **Zone-based Analysis**: Hat Yai divided into monitoring zones
- 📱 **LINE Notify Integration**: Instant notifications for critical alerts
- 🔄 **Auto-refresh**: 30-second update cycle for real-time detection

## 🏗️ Architecture

```
Drugstore Canary/
├── data/
│   ├── database.py          # SQLAlchemy models
│   ├── data_generator.py    # Synthetic data generator
│   └── preprocessor.py      # Data preprocessing pipeline
├── models/
│   ├── prophet_detector.py  # Prophet-based anomaly detection
│   ├── lstm_detector.py     # LSTM-based anomaly detection
│   └── ensemble_model.py    # Ensemble detector
├── api/
│   ├── main.py             # FastAPI application
│   └── alert_service.py    # Alert management
├── dashboard/
│   ├── index.html          # Dashboard UI
│   ├── dashboard.js        # Frontend logic
│   └── styles.css          # Styling
├── config.py               # Configuration
├── requirements.txt        # Dependencies
└── README.md              # This file
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or navigate to project directory
cd "Drugstore Canary"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Generate Synthetic Data

```bash
# Initialize database and generate test data
python data/data_generator.py
```

This will create:
- 4 zones in Hat Yai (ตัวเมือง, คลองแห, คอหงส์, ควนลัง)
- 10 pharmacies across zones
- 365 days of sales data
- 2 outbreak scenarios (post-flood patterns)

### 3. Start API Server

```bash
# Run FastAPI backend
python api/main.py
```

API will be available at: `http://localhost:8000`

API Documentation: `http://localhost:8000/docs`

### 4. Open Dashboard

```bash
# Serve dashboard (simple HTTP server)
cd dashboard
python -m http.server 8080
```

Open browser: `http://localhost:8080`

## 📊 ML Models

### Prophet Detector
- **Algorithm**: Facebook Prophet
- **Features**: Seasonality detection (weekly, monthly)
- **Strengths**: Handles missing data, robust to outliers
- **Use Case**: Baseline trend analysis

### LSTM Detector
- **Algorithm**: 2-layer LSTM Neural Network
- **Architecture**: LSTM(64) → LSTM(32) → Dense(16) → Dense(1)
- **Features**: 14-day lookback window
- **Strengths**: Captures complex patterns, non-linear relationships

### Ensemble Model
- **Strategy**: Weighted voting (Prophet: 60%, LSTM: 40%)
- **Confidence Scoring**: Based on model agreement and anomaly consistency
- **Alert Threshold**: Confidence > 70%

## 🎯 Usage Examples

### API Endpoints

#### Get Active Alerts
```bash
curl http://localhost:8000/api/alerts?active_only=true
```

#### Check Zone Status
```bash
curl http://localhost:8000/api/zones/zone_a/status
```

#### Run Prediction
```bash
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "zone_id": "zone_a",
    "category": "diarrhea",
    "days_back": 90
  }'
```

#### Add Sales Data
```bash
curl -X POST http://localhost:8000/api/sales \
  -H "Content-Type: application/json" \
  -d '{
    "pharmacy_id": "pharmacy_001",
    "medicine_category": "fever",
    "date": "2024-11-28T00:00:00",
    "quantity_sold": 45
  }'
```

### Python Usage

```python
from data.preprocessor import DataPreprocessor
from models.ensemble_model import EnsembleDetector
from datetime import datetime, timedelta

# Prepare data
preprocessor = DataPreprocessor()
df_prophet = preprocessor.prepare_for_prophet("zone_a", "diarrhea")
X_lstm, y_lstm, _ = preprocessor.prepare_for_lstm("zone_a", "diarrhea")

# Train ensemble
ensemble = EnsembleDetector()
ensemble.train(df_prophet, X_lstm, y_lstm)

# Detect anomalies
results = ensemble.detect_anomalies(df_prophet, X_lstm, y_lstm)

# Get alert
alert = ensemble.get_alert_message(results, "zone_a", "diarrhea")
if alert:
    print(alert['message'])
```

## 🔧 Configuration

Edit `config.py` to customize:

- **Model Parameters**: Adjust Prophet/LSTM hyperparameters
- **Anomaly Thresholds**: Set sensitivity levels
- **Alert Settings**: Configure cooldown periods
- **Zone Definitions**: Add/modify Hat Yai zones
- **Medicine Categories**: Define tracked medicine types

## 📈 Medicine Categories

| Category | Thai Name | Outbreak Indicator |
|----------|-----------|-------------------|
| `fever` | ยาแก้ไข้ | Flu, Dengue |
| `diarrhea` | ยาแก้ท้องเสีย | Water-borne diseases |
| `skin_infection` | ยารักษาโรคผิวหนัง | Post-flood infections |
| `allergy` | ยาแก้แพ้ | Seasonal allergies |
| `pain` | ยาแก้ปวด | General illness |
| `respiratory` | ยาแก้หวัด/ไอ | Respiratory infections |

## 🚨 Alert Levels

- **Low** (⚠️): Anomaly score 1.5-2.0 σ
- **Medium** (🟠): Anomaly score 2.0-2.5 σ
- **High** (🔴): Anomaly score 2.5-3.0 σ
- **Critical** (🚨): Anomaly score > 3.0 σ

## 🧪 Testing

```bash
# Test individual components
python data/preprocessor.py
python models/prophet_detector.py
python models/lstm_detector.py
python models/ensemble_model.py

# Run API tests
pytest tests/
```

## 📱 LINE Notify Setup (Optional)

1. Get LINE Notify token: https://notify-bot.line.me/
2. Set environment variable:
```bash
export LINE_NOTIFY_TOKEN="your_token_here"
```

## 🎨 Dashboard Features

- **Interactive Map**: Leaflet.js with zone markers
- **Real-time Alerts**: Auto-refresh every 30 seconds
- **Severity Color Coding**: Visual risk indicators
- **Zone Status Cards**: At-a-glance monitoring
- **Responsive Design**: Mobile-friendly interface

## 📊 Performance Metrics

Target Performance:
- ✅ Anomaly detection accuracy: >85%
- ✅ Lead time: 7-14 days before official reports
- ✅ False positive rate: <15%
- ✅ API response time: <500ms
- ✅ Dashboard update latency: <2s

## 🔮 Future Enhancements

- [ ] Integration with real pharmacy POS systems
- [ ] Weather data correlation (rainfall, temperature)
- [ ] Social media sentiment analysis
- [ ] Mobile app (iOS/Android)
- [ ] Multi-city expansion
- [ ] Advanced visualization (3D heatmaps)

## 🤝 Use Cases

### 1. Public Health Authorities
- Early outbreak detection
- Resource allocation planning
- Epidemic trend monitoring

### 2. Pharmacy Chains
- Inventory optimization
- Demand forecasting
- Supply chain management

### 3. Hospitals
- Patient surge preparation
- Staff scheduling
- Medical supply planning

## 📝 License

This project is for educational and research purposes.

## 👥 Contributors

Built with ❤️ for epidemic prevention in Hat Yai and beyond.

## 📞 Support

For questions or issues, please check the API documentation at `/docs` when running the server.

---

**⚠️ Disclaimer**: This system is designed as an early warning tool and should be used in conjunction with official health surveillance systems, not as a replacement.
