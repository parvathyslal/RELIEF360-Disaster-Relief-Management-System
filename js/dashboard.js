/**
 * RELIEF360 - Emergency Operations Center (EOC)
 * Dashboard Telemetry, Leaflet Map & Chart.js Integration
 */



const DashboardController = {
  map: null,

  init: function() {
    this.renderMetrics();
    this.initLeafletMap();
    this.initOccupancyChart();
    this.renderAlerts();
    this.renderResources();
    this.renderActivityFeed();
  },

  /**
   * Render 6 Metric Cards
   */
  renderMetrics: function() {
    const data = window.Relief360Data.metrics;

    const elActiveDisasters = document.getElementById('metricActiveDisasters');
    const elOpenCamps       = document.getElementById('metricOpenCamps');
    const elShelteredVictims= document.getElementById('metricShelteredVictims');
    const elVolunteers      = document.getElementById('metricVolunteers');
    const elMissingPersons  = document.getElementById('metricMissingPersons');
    const elCriticalAlerts  = document.getElementById('metricCriticalAlerts');

    if (elActiveDisasters)  elActiveDisasters.textContent = data.activeDisasters.toLocaleString();
    if (elOpenCamps)        elOpenCamps.textContent       = data.openReliefCamps.toLocaleString();
    if (elShelteredVictims) elShelteredVictims.textContent = data.shelteredVictims.toLocaleString();
    if (elVolunteers)       elVolunteers.textContent      = data.deployedVolunteers.toLocaleString();
    if (elMissingPersons)   elMissingPersons.textContent  = data.missingPersons.toLocaleString();
    if (elCriticalAlerts)   elCriticalAlerts.textContent  = data.criticalAlerts.toLocaleString();
  },

  /**
   * Leaflet Tactical Relief Map (Kerala Sector)
   */
  initLeafletMap: function() {
    const mapContainer = document.getElementById('eocMap');
    if (!mapContainer) return;
    if (typeof L === 'undefined') { mapContainer.innerHTML='<p class="p-3">Map unavailable offline. Camp and disaster locations remain available in their directories.</p>';return; }

    // Center map on Kerala State
    this.map = L.map('eocMap', {
      center: [10.4500, 76.2500],
      zoom: 8,
      zoomControl: true
    });

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 19,
    attribution: 'Tiles &copy; Esri and its data providers | RELIEF360 EOC'
}).addTo(this.map);

    // Custom Icon Creators
    const createCustomMarker = (color, iconClass) => {
      return L.divIcon({
        className: 'custom-map-pin',
        html: `
          <div style="
            background-color: ${color};
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            box-shadow: 0 3px 8px rgba(0,0,0,0.3);
            border: 2px solid white;
            font-size: 14px;
          ">
            <i class="${iconClass}"></i>
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      });
    };

    const disasterIcon = createCustomMarker('#DC2626', 'fas fa-triangle-exclamation');
    const campIcon     = createCustomMarker('#2563EB', 'fas fa-campground');

    // Add Disaster Pins
    window.Relief360Data.disasters.forEach(item => {
      const marker = L.marker(item.coordinates, { icon: disasterIcon }).addTo(this.map);
      
      const popupContent = `
        <div class="map-popup-card">
          <span class="badge bg-danger mb-1">${item.severity} Emergency</span>
          <h6>${item.name}</h6>
          <p class="mb-1"><strong>Location:</strong> ${item.location} (${item.district})</p>
          <p class="mb-1"><strong>Affected:</strong> ~${item.affectedPopulation.toLocaleString()} victims</p>
          <p class="mb-0 text-muted"><strong>Status:</strong> ${item.status}</p>
        </div>
      `;
      marker.bindPopup(popupContent);
    });

    // Add Relief Camp Pins
    window.Relief360Data.camps.forEach(item => {
      const marker = L.marker(item.coordinates, { icon: campIcon }).addTo(this.map);
      
      const occPercent = Math.round((item.occupancy / item.capacity) * 100);
      const badgeClass = occPercent > 80 ? 'bg-warning text-dark' : 'bg-success';

      const popupContent = `
        <div class="map-popup-card">
          <span class="badge ${badgeClass} mb-1">${occPercent}% Capacity (${item.occupancy}/${item.capacity})</span>
          <h6>${item.name}</h6>
          <p class="mb-1"><strong>Location:</strong> ${item.location}, ${item.district}</p>
          <p class="mb-1"><strong>In-Charge:</strong> ${item.manager} (${item.phone})</p>
          <p class="mb-0"><strong>Facilities:</strong> ${item.facilities.join(', ')}</p>
        </div>
      `;
      marker.bindPopup(popupContent);
    });
  },

  /**
   * Chart.js Relief Camp Occupancy Telemetry
   */
  initOccupancyChart: function() {
    const canvas = document.getElementById('campOccupancyChart');
    if (!canvas) return;
    if (typeof Chart === 'undefined') { canvas.parentElement.innerHTML='<p>Chart unavailable offline. See <a href="analytics.html">live occupancy reports</a>.</p>';return; }

    const camps = window.Relief360Data.occupancyCamps;
    const labels = camps.map(c => c.name.replace('Relief Center', '').replace('Higher Secondary', 'HSS'));
    const occupancyData = camps.map(c => c.occupancy);
    const capacityData  = camps.map(c => c.capacity);

    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Current Occupancy',
            data: occupancyData,
            backgroundColor: '#2563EB',
            borderRadius: 4,
            barPercentage: 0.6
          },
          {
            label: 'Total Capacity',
            data: capacityData,
            backgroundColor: '#E2E8F0',
            borderRadius: 4,
            barPercentage: 0.6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: {
              font: { family: 'Inter', size: 12 },
              usePointStyle: true,
              boxWidth: 8
            }
          },
          tooltip: {
            mode: 'index',
            intersect: false
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { font: { family: 'Inter', size: 11 } }
          },
          y: {
            grid: { color: '#F1F5F9' },
            ticks: { font: { family: 'Inter', size: 11 } },
            beginAtZero: true
          }
        }
      }
    });
  },

  /**
   * Render Critical Alerts Feed
   */
  renderAlerts: function() {
    const container = document.getElementById('alertsFeedList');
    if (!container) return;

    let html = '';
    window.Relief360Data.alerts.forEach(alert => {
      const badgeClass = alert.priority === 'CRITICAL' ? 'danger' : alert.priority === 'WARNING' ? 'warning' : 'info';
      html += `
        <div class="p-3 mb-2 rounded border border-light-subtle bg-white shadow-sm">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="status-badge ${badgeClass}">${alert.priority}</span>
            <small class="text-muted"><i class="far fa-clock me-1"></i>${alert.time}</small>
          </div>
          <h6 class="mb-1 text-dark font-semibold" style="font-size: 0.88rem;">${alert.title}</h6>
          <p class="mb-0 text-muted" style="font-size: 0.8rem;">${alert.message}</p>
        </div>
      `;
    });

    container.innerHTML = html;
  },

  /**
   * Render Resource Stock Progress Bars
   */
  renderResources: function() {
    const container = document.getElementById('resourceStockList');
    if (!container) return;

    let html = '';
    window.Relief360Data.resourceStock.forEach(item => {
      const barColor = item.percent > 75 ? 'bg-success' : item.percent > 50 ? 'bg-warning' : 'bg-danger';
      html += `
        <div class="mb-3">
          <div class="d-flex justify-content-between align-items-center mb-1" style="font-size: 0.82rem;">
            <span class="fw-semibold text-dark">${item.item}</span>
            <span class="text-muted">${item.available.toLocaleString()} ${item.unit} (${item.percent}%)</span>
          </div>
          <div class="progress" style="height: 6px; background-color: #E2E8F0;">
            <div class="progress-bar ${barColor}" role="progressbar" style="width: ${item.percent}%;" aria-valuenow="${item.percent}" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  },

  /**
   * Render Activity Feed
   */
  renderActivityFeed: function() {
    const container = document.getElementById('recentActivityFeed');
    if (!container) return;

    let html = '';
    window.Relief360Data.recentActivity.forEach(act => {
      html += `
        <li class="activity-item">
          <div class="activity-icon bg-${act.color}-subtle text-${act.color}">
            <i class="fas ${act.icon}"></i>
          </div>
          <div class="activity-details">
            <p class="activity-text">${act.title}</p>
            <span class="activity-time">${act.time}</span>
          </div>
        </li>
      `;
    });

    container.innerHTML = html;
  }
};
