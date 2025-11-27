/**
 * Drugstore Canary Dashboard JavaScript
 * Real-time monitoring and visualization
 */

const API_BASE_URL = 'http://localhost:8000/api';

// Global variables
let map;
let salesChart;
let anomalyChart;
let markers = {};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadZones();
    loadCategories();
    loadAlerts();
    loadZoneStatuses();
    
    // Auto-refresh every 30 seconds
    setInterval(() => {
        loadAlerts();
        loadZoneStatuses();
        updateHeaderStats();
    }, 30000);
});

// Initialize Leaflet map
function initMap() {
    // Center on Hat Yai
    map = L.map('map').setView([7.0087, 100.4754], 13);
    
    // Add tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
}

// Load zones and add markers
async function loadZones() {
    try {
        const response = await fetch(`${API_BASE_URL}/zones`);
        const zones = await response.json();
        
        // Populate zone selector
        const selector = document.getElementById('zoneSelector');
        zones.forEach(zone => {
            const option = document.createElement('option');
            option.value = zone.id;
            option.textContent = zone.name;
            selector.appendChild(option);
        });
        
        // Add markers to map
        zones.forEach(zone => {
            addZoneMarker(zone);
        });
        
    } catch (error) {
        console.error('Error loading zones:', error);
    }
}

// Add zone marker to map
function addZoneMarker(zone) {
    const marker = L.circleMarker([zone.center_lat, zone.center_lon], {
        radius: 15,
        fillColor: '#3b82f6',
        color: '#fff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.6
    }).addTo(map);
    
    marker.bindPopup(`
        <div class="map-popup">
            <h3>${zone.name}</h3>
            <p>Pharmacies: ${zone.num_pharmacies}</p>
            <p class="zone-id">Zone ID: ${zone.id}</p>
        </div>
    `);
    
    markers[zone.id] = marker;
}

// Update marker color based on alert level
function updateMarkerColor(zoneId, severity) {
    const marker = markers[zoneId];
    if (!marker) return;
    
    const colors = {
        'normal': '#3b82f6',
        'low': '#fbbf24',
        'medium': '#f97316',
        'high': '#ef4444',
        'critical': '#991b1b'
    };
    
    marker.setStyle({
        fillColor: colors[severity] || colors['normal'],
        radius: severity === 'critical' ? 20 : 15
    });
}

// Load medicine categories
async function loadCategories() {
    try {
        const response = await fetch(`${API_BASE_URL}/categories`);
        const categories = await response.json();
        
        const selector = document.getElementById('categorySelector');
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = formatCategory(category);
            selector.appendChild(option);
        });
        
    } catch (error) {
        console.error('Error loading categories:', error);
    }
}

// Load and display alerts
async function loadAlerts() {
    try {
        const response = await fetch(`${API_BASE_URL}/alerts?active_only=true&limit=20`);
        const alerts = await response.json();
        
        const feed = document.getElementById('alertsFeed');
        
        if (alerts.length === 0) {
            feed.innerHTML = '<div class="no-alerts">✅ No active alerts - All zones normal</div>';
            return;
        }
        
        feed.innerHTML = alerts.map(alert => createAlertCard(alert)).join('');
        
    } catch (error) {
        console.error('Error loading alerts:', error);
        document.getElementById('alertsFeed').innerHTML = 
            '<div class="error-message">❌ Error loading alerts</div>';
    }
}

// Create alert card HTML
function createAlertCard(alert) {
    const severityIcons = {
        'low': '⚠️',
        'medium': '🟠',
        'high': '🔴',
        'critical': '🚨'
    };
    
    const icon = severityIcons[alert.alert_level] || '⚠️';
    const time = new Date(alert.detected_at).toLocaleString('th-TH');
    
    return `
        <div class="alert-card severity-${alert.alert_level}">
            <div class="alert-header">
                <span class="alert-icon">${icon}</span>
                <span class="alert-severity">${alert.alert_level.toUpperCase()}</span>
                <span class="alert-time">${time}</span>
            </div>
            <div class="alert-body">
                <h3>${alert.zone_name}</h3>
                <p class="alert-category">${formatCategory(alert.medicine_category)}</p>
                <p class="alert-message">${alert.message}</p>
                <div class="alert-metrics">
                    <span>Score: ${alert.anomaly_score.toFixed(2)}</span>
                    <span>Confidence: ${(alert.confidence * 100).toFixed(0)}%</span>
                </div>
            </div>
        </div>
    `;
}

// Load zone statuses
async function loadZoneStatuses() {
    try {
        const response = await fetch(`${API_BASE_URL}/zones`);
        const zones = await response.json();
        
        const grid = document.getElementById('zoneGrid');
        const statusPromises = zones.map(zone => 
            fetch(`${API_BASE_URL}/zones/${zone.id}/status`).then(r => r.json())
        );
        
        const statuses = await Promise.all(statusPromises);
        
        grid.innerHTML = statuses.map(status => createZoneCard(status)).join('');
        
        // Update map markers
        statuses.forEach(status => {
            updateMarkerColor(status.zone_id, status.highest_severity);
        });
        
    } catch (error) {
        console.error('Error loading zone statuses:', error);
    }
}

// Create zone status card
function createZoneCard(status) {
    const statusClass = status.active_alerts > 0 ? 'at-risk' : 'normal';
    const riskCategories = status.categories_at_risk.map(c => formatCategory(c)).join(', ');
    
    return `
        <div class="zone-card ${statusClass}">
            <div class="zone-card-header">
                <h3>${status.zone_name}</h3>
                <span class="zone-badge severity-${status.highest_severity}">
                    ${status.highest_severity}
                </span>
            </div>
            <div class="zone-card-body">
                <div class="zone-stat">
                    <span class="zone-stat-label">Active Alerts:</span>
                    <span class="zone-stat-value">${status.active_alerts}</span>
                </div>
                ${status.categories_at_risk.length > 0 ? `
                    <div class="zone-risk-categories">
                        <strong>At Risk:</strong> ${riskCategories}
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

// Update header statistics
async function updateHeaderStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/alerts?active_only=true`);
        const alerts = await response.json();
        
        const uniqueZones = new Set(alerts.map(a => a.zone_id));
        
        document.getElementById('totalAlerts').textContent = alerts.length;
        document.getElementById('zonesAtRisk').textContent = uniqueZones.size;
        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString('th-TH');
        
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

// Format category name
function formatCategory(category) {
    const names = {
        'fever': 'ยาแก้ไข้',
        'diarrhea': 'ยาแก้ท้องเสีย',
        'skin_infection': 'ยารักษาโรคผิวหนัง',
        'allergy': 'ยาแก้แพ้',
        'pain': 'ยาแก้ปวด',
        'respiratory': 'ยาแก้หวัด/ไอ'
    };
    return names[category] || category;
}

// Refresh alerts manually
function refreshAlerts() {
    loadAlerts();
    loadZoneStatuses();
    updateHeaderStats();
    
    // Visual feedback
    const btn = document.querySelector('.refresh-btn');
    btn.classList.add('spinning');
    setTimeout(() => btn.classList.remove('spinning'), 1000);
}

// Update charts (placeholder - would need actual data)
function updateCharts() {
    const zoneId = document.getElementById('zoneSelector').value;
    if (!zoneId) return;
    
    // TODO: Fetch and display sales data for selected zone
    console.log('Updating charts for zone:', zoneId);
}

function updateAnomalyChart() {
    const category = document.getElementById('categorySelector').value;
    if (!category) return;
    
    // TODO: Fetch and display anomaly scores for selected category
    console.log('Updating anomaly chart for category:', category);
}

// Initialize on load
updateHeaderStats();
