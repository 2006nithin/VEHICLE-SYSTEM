// Tab Navigation
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.getAttribute('data-tab');
        switchTab(tabName);
    });
});

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active class from all nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    const selectedTab = document.getElementById(tabName);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Highlight selected nav button
    const selectedBtn = document.querySelector(`[data-tab="${tabName}"]`);
    if (selectedBtn) {
        selectedBtn.classList.add('active');
    }

    // Load dashboard data if switching to dashboard
    if (tabName === 'dashboard') {
        loadDashboardData();
    }
}

// Dashboard Data Loading
async function loadDashboardData() {
    try {
        // Fetch stats, alerts, and recent vehicles
        const [statsRes, alertsRes, vehiclesRes] = await Promise.all([
            fetch('/dashboard/stats'),
            fetch('/dashboard/alerts'),
            fetch('/dashboard/recent-vehicles')
        ]);

        if (!statsRes.ok || !alertsRes.ok || !vehiclesRes.ok) {
            throw new Error('Failed to load dashboard data');
        }

        const stats = await statsRes.json();
        const alerts = await alertsRes.json();
        const vehicles = await vehiclesRes.json();

        // Update stats cards
        document.getElementById('totalRegistrations').textContent = stats.total_registrations || 0;
        document.getElementById('activeVehicles').textContent = stats.active_vehicles || 0;
        document.getElementById('expiringLicenses').textContent = stats.expiring_licenses || 0;
        document.getElementById('expiredDocuments').textContent = stats.expired_documents || 0;

        // Update alerts
        if (alerts.alert_message) {
            const alertBox = document.getElementById('alertBox');
            document.getElementById('alertText').textContent = alerts.alert_message;
            alertBox.style.display = 'flex';
        } else {
            document.getElementById('alertBox').style.display = 'none';
        }

        // Populate recent vehicles table
        populateRecentVehiclesTable(vehicles.vehicles || []);
    } catch (error) {
        console.error('Error loading dashboard:', error);
        document.getElementById('alertBox').style.display = 'flex';
        document.getElementById('alertText').textContent = 'Error loading dashboard data. Please refresh.';
    }
}

function populateRecentVehiclesTable(vehicles) {
    const tbody = document.getElementById('recentTable');
    
    if (!vehicles || vehicles.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">No recent registrations found</td></tr>';
        return;
    }

    tbody.innerHTML = vehicles.map(v => {
        const expiryDate = new Date(v.registration_expiry);
        const today = new Date();
        let status = 'ACTIVE';
        let statusClass = 'status-active';
        
        if (expiryDate < today) {
            status = 'EXPIRED';
            statusClass = 'status-expired';
        } else if ((expiryDate - today) / (1000 * 60 * 60 * 24) < 30) {
            status = 'EXPIRING';
            statusClass = 'status-expiring';
        }

        return `
            <tr>
                <td><strong>${v.registration_number}</strong></td>
                <td>${v.owner_name}</td>
                <td>${v.model}</td>
                <td>LMV</td>
                <td>${formatDate(v.created_date || new Date().toISOString())}</td>
                <td>${formatDate(v.registration_expiry)}</td>
                <td><span class="status-badge ${statusClass}">${status}</span></td>
            </tr>
        `;
    }).join('');
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-IN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
}

// Form Handlers
const ownerForm = document.getElementById('ownerForm');
const licenseForm = document.getElementById('licenseForm');
const renewForm = document.getElementById('renewForm');
const loadReminders = document.getElementById('loadReminders');

const setResult = (element, data) => {
    element.textContent = JSON.stringify(data, null, 2);
};

const submitJson = async (url, payload, resultElement) => {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
            setResult(resultElement, { error: data.detail || data });
            return;
        }
        setResult(resultElement, data);
    } catch (error) {
        setResult(resultElement, { error: error.message });
    }
};

ownerForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(ownerForm);
    const payload = {
        name: form.get('name'),
        national_id: form.get('national_id'),
        contact_number: form.get('contact_number'),
        address: form.get('address'),
        vehicle: {
            registration_number: form.get('registration_number'),
            chassis_number: form.get('chassis_number'),
            model: form.get('model'),
            registration_expiry: form.get('registration_expiry'),
        },
    };
    await submitJson('/owners/register', payload, document.getElementById('ownerResult'));
});

licenseForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(licenseForm);
    const payload = {
        owner_id: Number(form.get('owner_id')),
        vehicle_id: Number(form.get('vehicle_id')),
        license_number: form.get('license_number'),
        license_class: form.get('license_class'),
        issue_date: form.get('issue_date'),
        expiry_date: form.get('expiry_date'),
    };
    await submitJson('/licenses/issue', payload, document.getElementById('licenseResult'));
});

renewForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(renewForm);
    const licenseId = Number(form.get('license_id'));
    const payload = {
        owner_id: Number(form.get('owner_id')),
        vehicle_id: Number(form.get('vehicle_id')),
        license_number: form.get('license_number'),
        license_class: form.get('license_class'),
        issue_date: form.get('issue_date'),
        expiry_date: form.get('expiry_date'),
    };
    await submitJson(`/licenses/${licenseId}/renew`, payload, document.getElementById('renewResult'));
});

loadReminders.addEventListener('click', async () => {
    try {
        const response = await fetch('/reminders');
        const data = await response.json();
        if (!response.ok) {
            document.getElementById('reminderResult').textContent = JSON.stringify({ error: data.detail || data }, null, 2);
            return;
        }
        document.getElementById('reminderResult').textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        document.getElementById('reminderResult').textContent = JSON.stringify({ error: error.message }, null, 2);
    }
});

// Load dashboard on page load
window.addEventListener('load', () => {
    loadDashboardData();
});
