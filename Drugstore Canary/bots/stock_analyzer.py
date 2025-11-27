"""
Stock availability analyzer
Analyzes stockout patterns from bot scraping results
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np


class StockAnalyzer:
    """Analyze stock availability data for anomaly detection"""
    
    def __init__(self, results_dir: str = None):
        if results_dir is None:
            results_dir = Path(__file__).parent.parent / "bot_results"
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
    
    def load_results(self, days_back: int = 7) -> List[Dict]:
        """
        Load scraping results from the last N days
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of result dictionaries
        """
        results = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for file_path in self.results_dir.glob("stock_check_*.json"):
            try:
                # Extract timestamp from filename
                timestamp_str = file_path.stem.replace("stock_check_", "")
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                if file_date >= cutoff_date:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        results.append(data)
            
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                continue
        
        return sorted(results, key=lambda x: x[0].get("timestamp", ""))
    
    def calculate_stockout_rate(
        self,
        results: List[Dict],
        category: str = None,
        platform: str = None
    ) -> Dict:
        """
        Calculate stockout rate from results
        
        Args:
            results: List of scraping results
            category: Optional category filter
            platform: Optional platform filter
            
        Returns:
            Dictionary with stockout statistics
        """
        total_checks = 0
        total_sold_out = 0
        item_stats = {}
        
        for result_set in results:
            for platform_result in result_set:
                # Filter by platform if specified
                if platform and platform_result.get("platform") != platform:
                    continue
                
                # Extract items from different result structures
                items = []
                if "pharmacies" in platform_result:
                    for pharmacy in platform_result["pharmacies"]:
                        if "items" in pharmacy:
                            items.extend(pharmacy["items"])
                elif "items" in platform_result:
                    items = platform_result["items"]
                
                # Process items
                for item in items:
                    # Filter by category if specified
                    if category and item.get("category") != category:
                        continue
                    
                    total_checks += 1
                    
                    if not item.get("is_available", True):
                        total_sold_out += 1
                    
                    # Track per-item stats
                    item_name = item.get("product_name", "Unknown")
                    if item_name not in item_stats:
                        item_stats[item_name] = {
                            "total_checks": 0,
                            "sold_out_count": 0,
                            "category": item.get("category", "Unknown"),
                            "platform": item.get("platform", "Unknown")
                        }
                    
                    item_stats[item_name]["total_checks"] += 1
                    if not item.get("is_available", True):
                        item_stats[item_name]["sold_out_count"] += 1
        
        # Calculate rates
        overall_rate = (total_sold_out / total_checks * 100) if total_checks > 0 else 0
        
        # Calculate per-item rates
        for item_name, stats in item_stats.items():
            stats["stockout_rate"] = (
                stats["sold_out_count"] / stats["total_checks"] * 100
                if stats["total_checks"] > 0 else 0
            )
        
        # Sort items by stockout rate
        high_risk_items = sorted(
            item_stats.items(),
            key=lambda x: x[1]["stockout_rate"],
            reverse=True
        )[:10]  # Top 10
        
        return {
            "total_checks": total_checks,
            "total_sold_out": total_sold_out,
            "overall_stockout_rate": overall_rate,
            "high_risk_items": [
                {
                    "item_name": name,
                    **stats
                }
                for name, stats in high_risk_items
            ],
            "category_filter": category,
            "platform_filter": platform
        }
    
    def detect_anomalies(
        self,
        results: List[Dict],
        threshold_std: float = 2.0
    ) -> List[Dict]:
        """
        Detect anomalous stockout patterns
        
        Args:
            results: Scraping results
            threshold_std: Standard deviation threshold
            
        Returns:
            List of anomalies detected
        """
        # Convert to time series
        df = self._results_to_dataframe(results)
        
        if df.empty:
            return []
        
        anomalies = []
        
        # Group by category
        for category in df["category"].unique():
            category_df = df[df["category"] == category]
            
            # Calculate baseline stockout rate
            baseline_rate = category_df["stockout_rate"].mean()
            std_dev = category_df["stockout_rate"].std()
            
            # Detect anomalies
            threshold = baseline_rate + (threshold_std * std_dev)
            
            anomalous_points = category_df[category_df["stockout_rate"] > threshold]
            
            for _, row in anomalous_points.iterrows():
                anomalies.append({
                    "timestamp": row["timestamp"],
                    "category": category,
                    "stockout_rate": row["stockout_rate"],
                    "baseline_rate": baseline_rate,
                    "threshold": threshold,
                    "anomaly_score": (row["stockout_rate"] - baseline_rate) / (std_dev + 1e-8),
                    "severity": self._classify_severity(
                        (row["stockout_rate"] - baseline_rate) / (std_dev + 1e-8)
                    )
                })
        
        return sorted(anomalies, key=lambda x: x["anomaly_score"], reverse=True)
    
    def _results_to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        """Convert results to pandas DataFrame"""
        rows = []
        
        for result_set in results:
            timestamp = result_set[0].get("timestamp", datetime.now().isoformat())
            
            for platform_result in result_set:
                items = []
                if "pharmacies" in platform_result:
                    for pharmacy in platform_result["pharmacies"]:
                        if "items" in pharmacy:
                            items.extend(pharmacy["items"])
                elif "items" in platform_result:
                    items = platform_result["items"]
                
                # Group by category
                category_stats = {}
                for item in items:
                    category = item.get("category", "Unknown")
                    if category not in category_stats:
                        category_stats[category] = {"total": 0, "sold_out": 0}
                    
                    category_stats[category]["total"] += 1
                    if not item.get("is_available", True):
                        category_stats[category]["sold_out"] += 1
                
                # Create rows
                for category, stats in category_stats.items():
                    rows.append({
                        "timestamp": timestamp,
                        "category": category,
                        "platform": platform_result.get("platform", "Unknown"),
                        "total_items": stats["total"],
                        "sold_out": stats["sold_out"],
                        "stockout_rate": (stats["sold_out"] / stats["total"] * 100) if stats["total"] > 0 else 0
                    })
        
        return pd.DataFrame(rows)
    
    def _classify_severity(self, anomaly_score: float) -> str:
        """Classify anomaly severity"""
        if anomaly_score < 1.5:
            return "low"
        elif anomaly_score < 2.5:
            return "medium"
        elif anomaly_score < 3.5:
            return "high"
        else:
            return "critical"
    
    def generate_report(self, days_back: int = 7) -> Dict:
        """
        Generate comprehensive stock analysis report
        
        Args:
            days_back: Days to analyze
            
        Returns:
            Report dictionary
        """
        results = self.load_results(days_back)
        
        if not results:
            return {
                "error": "No results found",
                "days_back": days_back
            }
        
        # Overall statistics
        overall_stats = self.calculate_stockout_rate(results)
        
        # Per-category statistics
        category_stats = {}
        for category in ["diarrhea", "skin_infection", "fever", "respiratory"]:
            category_stats[category] = self.calculate_stockout_rate(
                results,
                category=category
            )
        
        # Anomaly detection
        anomalies = self.detect_anomalies(results)
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "days_analyzed": days_back,
            "total_result_files": len(results),
            "overall_statistics": overall_stats,
            "category_statistics": category_stats,
            "anomalies_detected": anomalies,
            "alert_level": self._determine_alert_level(overall_stats, anomalies)
        }
        
        return report
    
    def _determine_alert_level(self, overall_stats: Dict, anomalies: List[Dict]) -> str:
        """Determine overall alert level"""
        stockout_rate = overall_stats["overall_stockout_rate"]
        critical_anomalies = sum(1 for a in anomalies if a["severity"] == "critical")
        
        if stockout_rate > 50 or critical_anomalies > 0:
            return "critical"
        elif stockout_rate > 30 or len(anomalies) > 2:
            return "high"
        elif stockout_rate > 15 or len(anomalies) > 0:
            return "medium"
        else:
            return "low"


if __name__ == "__main__":
    analyzer = StockAnalyzer()
    
    # Generate report
    report = analyzer.generate_report(days_back=7)
    
    # Print report
    print("\n" + "="*60)
    print("STOCK AVAILABILITY ANALYSIS REPORT")
    print("="*60)
    print(f"\nGenerated: {report['generated_at']}")
    print(f"Days analyzed: {report['days_analyzed']}")
    print(f"Alert level: {report['alert_level'].upper()}")
    
    print(f"\nOverall Statistics:")
    overall = report["overall_statistics"]
    print(f"  Total checks: {overall['total_checks']}")
    print(f"  Sold out: {overall['total_sold_out']}")
    print(f"  Stockout rate: {overall['overall_stockout_rate']:.1f}%")
    
    if overall.get("high_risk_items"):
        print(f"\nHigh Risk Items:")
        for item in overall["high_risk_items"][:5]:
            print(f"  - {item['item_name']}: {item['stockout_rate']:.1f}% ({item['sold_out_count']}/{item['total_checks']})")
    
    if report["anomalies_detected"]:
        print(f"\nAnomalies Detected: {len(report['anomalies_detected'])}")
        for anomaly in report["anomalies_detected"][:3]:
            print(f"  - {anomaly['category']}: {anomaly['stockout_rate']:.1f}% (severity: {anomaly['severity']})")
    
    print("\n" + "="*60)
    
    # Save report
    report_path = Path("stock_analysis_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Full report saved to: {report_path}")
