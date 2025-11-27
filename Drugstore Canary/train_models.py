"""
Training script for Drugstore Canary models
Trains Prophet, LSTM, and Ensemble models on all zone-category pairs
"""
import sys
from pathlib import Path
import numpy as np
from datetime import datetime

sys.path.append(str(Path(__file__).parent))

from data.preprocessor import DataPreprocessor
from models.prophet_detector import ProphetDetector
from models.lstm_detector import LSTMDetector
from models.ensemble_model import EnsembleDetector
from config import HAT_YAI_ZONES, MEDICINE_CATEGORIES


def train_all_models(save_models: bool = True):
    """
    Train models for all zone-category combinations
    
    Args:
        save_models: Whether to save trained models to disk
    """
    print("=" * 60)
    print("Drugstore Canary - Model Training")
    print("=" * 60)
    
    preprocessor = DataPreprocessor()
    results = []
    
    # Get all zone-category pairs
    pairs = preprocessor.get_all_zone_category_pairs()
    total_pairs = len(pairs)
    
    print(f"\nTraining models for {total_pairs} zone-category combinations...")
    print(f"Zones: {len(HAT_YAI_ZONES)}")
    print(f"Categories: {len(MEDICINE_CATEGORIES)}\n")
    
    for idx, (zone_id, category) in enumerate(pairs, 1):
        zone_name = HAT_YAI_ZONES[zone_id]["name"]
        print(f"\n[{idx}/{total_pairs}] Training: {zone_name} - {category}")
        print("-" * 60)
        
        try:
            # Prepare data
            print("  📊 Preparing data...")
            df_prophet = preprocessor.prepare_for_prophet(zone_id, category)
            
            if df_prophet.empty or len(df_prophet) < 30:
                print(f"  ⚠️  Insufficient data ({len(df_prophet)} days), skipping...")
                continue
            
            X_lstm, y_lstm, _ = preprocessor.prepare_for_lstm(
                zone_id, category, lookback_days=14
            )
            
            if len(X_lstm) == 0:
                print(f"  ⚠️  Insufficient LSTM data, skipping...")
                continue
            
            print(f"  ✓ Data prepared: {len(df_prophet)} days")
            
            # Train Prophet
            print("  🔮 Training Prophet model...")
            prophet = ProphetDetector()
            prophet.train(df_prophet)
            prophet_results = prophet.detect_anomalies(df_prophet)
            prophet_conf = prophet.calculate_confidence(prophet_results)
            print(f"  ✓ Prophet trained (confidence: {prophet_conf:.2f})")
            
            # Train LSTM
            print("  🧠 Training LSTM model...")
            lstm = LSTMDetector()
            lstm.train(X_lstm, y_lstm, verbose=0)
            lstm_results = lstm.detect_anomalies(X_lstm, y_lstm)
            lstm_conf = lstm.calculate_confidence(lstm_results)
            print(f"  ✓ LSTM trained (confidence: {lstm_conf:.2f})")
            
            # Train Ensemble
            print("  🎯 Training Ensemble model...")
            ensemble = EnsembleDetector()
            ensemble.train(df_prophet, X_lstm, y_lstm)
            ensemble_results = ensemble.detect_anomalies(df_prophet, X_lstm, y_lstm)
            ensemble_conf = ensemble.calculate_confidence(ensemble_results)
            print(f"  ✓ Ensemble trained (confidence: {ensemble_conf:.2f})")
            
            # Detect anomalies
            anomalies = ensemble_results[ensemble_results["is_anomaly"]].tail(5)
            if not anomalies.empty:
                print(f"  🚨 Recent anomalies detected: {len(anomalies)}")
                for _, row in anomalies.iterrows():
                    print(f"     - {row['ds']}: {row['severity']} (score: {row['ensemble_score']:.2f})")
            else:
                print(f"  ✅ No anomalies detected")
            
            # Save models if requested
            if save_models:
                models_dir = Path(__file__).parent / "trained_models"
                models_dir.mkdir(exist_ok=True)
                
                model_prefix = f"{zone_id}_{category}"
                prophet.save_model(str(models_dir / f"{model_prefix}_prophet.pkl"))
                lstm.save_model(str(models_dir / f"{model_prefix}_lstm.h5"))
                print(f"  💾 Models saved to trained_models/")
            
            # Store results
            results.append({
                "zone_id": zone_id,
                "zone_name": zone_name,
                "category": category,
                "prophet_confidence": prophet_conf,
                "lstm_confidence": lstm_conf,
                "ensemble_confidence": ensemble_conf,
                "anomalies_detected": len(anomalies),
                "data_points": len(df_prophet)
            })
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
    
    preprocessor.close()
    
    # Print summary
    print("\n" + "=" * 60)
    print("Training Summary")
    print("=" * 60)
    
    if results:
        print(f"\nSuccessfully trained: {len(results)}/{total_pairs} combinations\n")
        
        # Average confidences
        avg_prophet = np.mean([r["prophet_confidence"] for r in results])
        avg_lstm = np.mean([r["lstm_confidence"] for r in results])
        avg_ensemble = np.mean([r["ensemble_confidence"] for r in results])
        
        print(f"Average Confidence Scores:")
        print(f"  Prophet:  {avg_prophet:.2f}")
        print(f"  LSTM:     {avg_lstm:.2f}")
        print(f"  Ensemble: {avg_ensemble:.2f}")
        
        # Total anomalies
        total_anomalies = sum([r["anomalies_detected"] for r in results])
        print(f"\nTotal Anomalies Detected: {total_anomalies}")
        
        # High-risk zones
        high_risk = [r for r in results if r["anomalies_detected"] > 0]
        if high_risk:
            print(f"\nZones with Anomalies ({len(high_risk)}):")
            for r in high_risk:
                print(f"  - {r['zone_name']} ({r['category']}): {r['anomalies_detected']} anomalies")
    else:
        print("\n⚠️  No models were successfully trained")
    
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train Drugstore Canary models")
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save trained models to disk"
    )
    
    args = parser.parse_args()
    
    results = train_all_models(save_models=not args.no_save)
