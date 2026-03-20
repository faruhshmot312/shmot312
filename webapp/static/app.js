// Telegram WebApp init
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
}

// Format numbers
function fmt(n, decimals = 0) {
    if (n === null || n === undefined) return '—';
    return Math.round(n).toLocaleString('ru-RU');
}

function fmtShort(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return Math.round(n / 1_000) + 'K';
    return fmt(n);
}

// Chart.js defaults
Chart.defaults.color = getComputedStyle(document.body).getPropertyValue('--text-sub').trim() || '#8a8a9a';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.display = false;

// Tab navigation
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    });
});

// Load data
async function loadDashboard() {
    try {
        const resp = await fetch('/api/dashboard');
        const data = await resp.json();
        render(data);
    } catch (e) {
        document.getElementById('loader').innerHTML = '<p style="color:var(--red)">Ошибка загрузки данных</p>';
    }
}

function render(d) {
    // Hide loader, show content
    document.getElementById('loader').style.display = 'none';
    document.getElementById('content').style.display = 'block';

    const now = new Date();
    document.getElementById('update-time').textContent =
        now.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

    // KPI
    document.getElementById('kpi-balance').textContent = fmtShort(d.finance.total);
    document.getElementById('kpi-days-left').textContent = `запас ${Math.round(d.finance.days_left)} дн.`;

    document.getElementById('kpi-won-amount').textContent = fmtShort(d.deals.won_amount);
    document.getElementById('kpi-won-count').textContent = `${d.deals.won} сделок, ср.чек ${fmtShort(d.deals.avg_check)}`;

    document.getElementById('kpi-active-amount').textContent = fmtShort(d.deals.active_amount);
    document.getElementById('kpi-active-count').textContent = `${d.deals.active} сделок`;

    document.getElementById('kpi-debt').textContent = fmtShort(d.debitors.total);
    document.getElementById('kpi-debt-count').textContent = `${d.debitors.count} должников`;

    // Funnel
    renderFunnel(d.funnel);

    // Overdue
    renderOverdue(d.overdue);

    // Finance tab
    document.getElementById('monthly-costs').textContent = fmt(d.finance.monthly_costs) + ' сом/мес';
    document.getElementById('days-reserve').textContent = Math.round(d.finance.days_left) + ' дней';
    renderMonthsChart(d.finance.months_data);

    // Deals tab
    renderManagers(d.managers);
    renderRejectionsChart(d.rejections);
    renderDebitors(d.debitors.list);

    // Managers (sheets) tab
    renderSeamstressesChart(d.managers_sheets);
    renderSeamstressDetails(d.managers_sheets);
}

// --- RENDER FUNCTIONS ---

function renderFunnel(funnel) {
    const el = document.getElementById('funnel');
    if (!funnel.length) { el.innerHTML = '<p>Нет данных</p>'; return; }
    const max = Math.max(...funnel.map(f => f.count));
    el.innerHTML = funnel.map(f => {
        const pct = (f.count / max * 100).toFixed(0);
        return `<div class="funnel-row">
            <span class="funnel-name">${f.stage}</span>
            <span class="funnel-count">${f.count}</span>
            <span class="funnel-amount">${fmtShort(f.amount)}</span>
        </div>
        <div style="padding:0 10px;"><div class="funnel-bar" style="width:${pct}%"></div></div>`;
    }).join('');
}

function renderOverdue(overdue) {
    const card = document.getElementById('overdue-card');
    const el = document.getElementById('overdue-list');
    if (!overdue.length) { card.style.display = 'none'; return; }
    card.style.display = 'block';
    el.innerHTML = overdue.map(o =>
        `<div class="overdue-row">
            <span class="overdue-title">${o.title}</span>
            <span class="overdue-days">${o.days_late} дн.</span>
        </div>`
    ).join('');
}

function renderManagers(managers) {
    const el = document.getElementById('managers-list');
    el.innerHTML = managers.map(m =>
        `<div class="manager-card">
            <div class="manager-name">${m.name}</div>
            <div class="manager-stats">
                <div class="manager-stat">Выручка: <span>${fmtShort(m.revenue)}</span></div>
                <div class="manager-stat">Сделок: <span>${m.won}/${m.total}</span></div>
                <div class="manager-stat">Конв: <span>${m.conversion}%</span></div>
                <div class="manager-stat">Ср.чек: <span>${fmtShort(m.avg_check)}</span></div>
            </div>
        </div>`
    ).join('');
}

function renderDebitors(list) {
    const el = document.getElementById('debitors-list');
    if (!list.length) { el.innerHTML = '<p>Нет должников</p>'; return; }
    el.innerHTML = list.map(d =>
        `<div class="debt-row">
            <span class="debt-title">${d.title}</span>
            <span class="debt-amount">${fmtShort(d.debt)}</span>
        </div>`
    ).join('');
}

function renderSeamstressDetails(seamstresses) {
    const el = document.getElementById('seamstress-details');
    el.innerHTML = seamstresses.map(s =>
        `<div class="seamstress-card">
            <div class="seamstress-name">${s.name}</div>
            <div class="seamstress-stats">
                <div class="seamstress-stat">Сумма: <span>${fmtShort(s.total)}</span></div>
                <div class="seamstress-stat">Оплачено: <span>${fmtShort(s.paid)}</span></div>
                <div class="seamstress-stat">Записей: <span>${s.orders}</span></div>
            </div>
        </div>`
    ).join('');
}

// --- CHARTS ---

function renderMonthsChart(months) {
    if (!months.length) return;
    new Chart(document.getElementById('chart-months'), {
        type: 'bar',
        data: {
            labels: months.map(m => m.month),
            datasets: [
                { label: 'Приход', data: months.map(m => m.income), backgroundColor: '#2ec4b6', borderRadius: 6, barPercentage: 0.6 },
                { label: 'Расход', data: months.map(m => m.expense), backgroundColor: '#e63946', borderRadius: 6, barPercentage: 0.6 },
            ]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } },
            scales: { y: { ticks: { callback: v => fmtShort(v) } } }
        }
    });
}

function renderRejectionsChart(rejections) {
    const labels = Object.keys(rejections);
    const values = Object.values(rejections);
    if (!labels.length) return;

    new Chart(document.getElementById('chart-rejections'), {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data: values, backgroundColor: ['#e63946', '#ff9f1c', '#4361ee', '#2ec4b6', '#8a8a9a'], borderWidth: 0 }]
        },
        options: {
            responsive: true,
            cutout: '60%',
            plugins: {
                legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 11 }, padding: 12 } }
            }
        }
    });
}

function renderSeamstressesChart(seamstresses) {
    if (!seamstresses.length) return;
    new Chart(document.getElementById('chart-seamstresses'), {
        type: 'bar',
        data: {
            labels: seamstresses.map(s => s.name),
            datasets: [{
                label: 'Сумма заказов',
                data: seamstresses.map(s => s.total),
                backgroundColor: ['#4361ee', '#2ec4b6', '#ff9f1c', '#e63946'],
                borderRadius: 8, barPercentage: 0.6,
            }]
        },
        options: {
            responsive: true,
            indexAxis: 'y',
            scales: { x: { ticks: { callback: v => fmtShort(v) } } }
        }
    });
}

// Start
loadDashboard();
