"""
Alert service for Drugstore Canary
Handles alert generation, notification, and management
"""
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from data.database import get_session, Alert, Zone
from config import ALERT_CONFIG, LINE_NOTIFY_TOKEN


class AlertService:
    """Manage alerts and notifications"""
    
    def __init__(self):
        self.session = get_session()
        self.config = ALERT_CONFIG
        
    def create_alert(
        self,
        zone_id: str,
        medicine_category: str,
        alert_level: str,
        anomaly_score: float,
        confidence: float,
        message: str
    ) -> Optional[Alert]:
        """
        Create a new alert if conditions are met
        
        Args:
            zone_id: Zone identifier
            medicine_category: Medicine category
            alert_level: Severity level
            anomaly_score: Anomaly score
            confidence: Confidence score
            message: Alert message
            
        Returns:
            Created Alert object or None
        """
        # Check cooldown period
        if not self._check_cooldown(zone_id, medicine_category):
            print(f"Alert cooldown active for {zone_id}/{medicine_category}")
            return None
        
        # Create alert
        alert = Alert(
            zone_id=zone_id,
            medicine_category=medicine_category,
            alert_level=alert_level,
            anomaly_score=anomaly_score,
            confidence=confidence,
            message=message,
            is_active=True
        )
        
        self.session.add(alert)
        self.session.commit()
        
        # Send notification
        if self.config["enable_notifications"]:
            self._send_notification(alert)
        
        return alert
    
    def _check_cooldown(self, zone_id: str, medicine_category: str) -> bool:
        """
        Check if cooldown period has passed since last alert
        
        Args:
            zone_id: Zone identifier
            medicine_category: Medicine category
            
        Returns:
            True if can create new alert, False if in cooldown
        """
        cooldown_hours = self.config["cooldown_period_hours"]
        cutoff_time = datetime.utcnow() - timedelta(hours=cooldown_hours)
        
        recent_alert = self.session.query(Alert).filter(
            Alert.zone_id == zone_id,
            Alert.medicine_category == medicine_category,
            Alert.detected_at >= cutoff_time
        ).first()
        
        return recent_alert is None
    
    def _send_notification(self, alert: Alert) -> bool:
        """
        Send notification via LINE Notify
        
        Args:
            alert: Alert object
            
        Returns:
            True if successful, False otherwise
        """
        if not LINE_NOTIFY_TOKEN:
            print("LINE Notify token not configured")
            return False
        
        try:
            # Get zone name
            zone = self.session.query(Zone).filter(
                Zone.id == alert.zone_id
            ).first()
            
            zone_name = zone.name if zone else alert.zone_id
            
            # Format message
            notification_message = (
                f"\n🚨 Drugstore Canary Alert\n"
                f"พื้นที่: {zone_name}\n"
                f"ประเภทยา: {alert.medicine_category}\n"
                f"ระดับ: {alert.alert_level}\n"
                f"ความมั่นใจ: {alert.confidence*100:.0f}%\n"
                f"เวลา: {alert.detected_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"\n{alert.message}"
            )
            
            # Send to LINE Notify
            headers = {"Authorization": f"Bearer {LINE_NOTIFY_TOKEN}"}
            data = {"message": notification_message}
            
            response = requests.post(
                "https://notify-api.line.me/api/notify",
                headers=headers,
                data=data
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"Error sending notification: {e}")
            return False
    
    def get_active_alerts(
        self,
        zone_id: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Alert]:
        """
        Get active alerts with optional filtering
        
        Args:
            zone_id: Optional zone filter
            category: Optional category filter
            
        Returns:
            List of active alerts
        """
        query = self.session.query(Alert).filter(Alert.is_active == True)
        
        if zone_id:
            query = query.filter(Alert.zone_id == zone_id)
        
        if category:
            query = query.filter(Alert.medicine_category == category)
        
        return query.order_by(Alert.detected_at.desc()).all()
    
    def resolve_alert(self, alert_id: int) -> bool:
        """
        Mark an alert as resolved
        
        Args:
            alert_id: Alert ID
            
        Returns:
            True if successful
        """
        alert = self.session.query(Alert).filter(Alert.id == alert_id).first()
        
        if not alert:
            return False
        
        alert.is_active = False
        alert.resolved_at = datetime.utcnow()
        self.session.commit()
        
        return True
    
    def auto_resolve_old_alerts(self, days: int = 7) -> int:
        """
        Automatically resolve alerts older than specified days
        
        Args:
            days: Number of days
            
        Returns:
            Number of alerts resolved
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        old_alerts = self.session.query(Alert).filter(
            Alert.is_active == True,
            Alert.detected_at < cutoff_date
        ).all()
        
        count = 0
        for alert in old_alerts:
            alert.is_active = False
            alert.resolved_at = datetime.utcnow()
            count += 1
        
        self.session.commit()
        
        return count
    
    def get_alert_summary(self) -> Dict:
        """
        Get summary of all alerts
        
        Returns:
            Dictionary with alert statistics
        """
        active_alerts = self.session.query(Alert).filter(
            Alert.is_active == True
        ).all()
        
        # Count by severity
        severity_counts = {}
        for alert in active_alerts:
            severity_counts[alert.alert_level] = severity_counts.get(alert.alert_level, 0) + 1
        
        # Count by zone
        zone_counts = {}
        for alert in active_alerts:
            zone_counts[alert.zone_id] = zone_counts.get(alert.zone_id, 0) + 1
        
        return {
            "total_active": len(active_alerts),
            "by_severity": severity_counts,
            "by_zone": zone_counts,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def close(self):
        """Close database session"""
        self.session.close()


if __name__ == "__main__":
    # Test alert service
    service = AlertService()
    
    # Get summary
    summary = service.get_alert_summary()
    print("Alert Summary:")
    print(f"  Total active: {summary['total_active']}")
    print(f"  By severity: {summary['by_severity']}")
    print(f"  By zone: {summary['by_zone']}")
    
    # Auto-resolve old alerts
    resolved = service.auto_resolve_old_alerts(days=7)
    print(f"\nAuto-resolved {resolved} old alerts")
    
    service.close()
