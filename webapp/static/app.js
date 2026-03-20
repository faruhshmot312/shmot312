// Telegram WebApp init
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
}

// State
let currentPeriod = 'all';
let chartInstances = {};

// Format numbers
function fmt(n) {
    if (n === null || n === undefined) return '—';
    return Math.round(n).toLocaleString('ru-RU');
}

function fmtShort(n) {
    if (n === null || n === undefined) return '—';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return Math.round(n / 1_000) + 'K';
    return fmt(n);
}

// Chart.js defaults
Chart.defaults.color = getComputedStyle(document.body).getPropertyValue('--text-sub').trim() || '#8a8a9a';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.display = false;

// Destroy chart before re-creating
function destroyChart(id) {
    if (chartInstances[id]) {
        chartInstances[id].destroy();
        delete chartInstances[id];
    }
}

function createChart(id, config) {
    destroyChart(id);
    chartInstances[id] = new Chart(document.getElementById(id), config);
}

// Tab navigation
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    });
});

// Period filter
document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentPeriod = btn.dataset.period;
        loadDashboard();
    });
});

// Refresh button
document.getElementById('refresh-btn').addEventListener('click', async () => {
    const btn = document.getElementById('refresh-btn');
    btn.classList.add('spinning');
    btn.disabled = true;
    try {
        await fetch('/api/refresh', { method: 'POST' });
        await loadDashboard();
    } catch (e) {
        console.error(e);
    }
    btn.classList.remove('spinning');
    btn.disabled = false;
});

// Load data
async function loadDashboard() {
    try {
        const resp = await fetch('/api/dashboard?period=' + currentPeriod);
        const data = await resp.json();
        render(data);
    } catch (e) {
        document.getElementById('loader').innerHTML = '<p style="color:var(--red)">Ошибка загрузки данных</p>';
    }
}

function render(d) {
    document.getElementById('loader').style.display = 'none';
    document.getElementById('content').style.display = 'block';

    const now = new Date();
    document.getElementById('update-time').textContent =
        now.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

    // === Plan-Fact ===
    renderPlanFact(d.plan_fact);

    // === KPI ===
    const profit = d.profit.net_profit_ytd;
    const kpiProfit = document.getElementById('kpi-profit');
    kpiProfit.textContent = fmtShort(profit);
    kpiProfit.className = 'kpi-value ' + (profit >= 0 ? 'color-green' : 'color-red');
    document.getElementById('kpi-margin').textContent = `маржа ${d.profit.gross_margin}%`;

    document.getElementById('kpi-balance').textContent = fmtShort(d.finance.total);
    document.getElementById('kpi-days-left').textContent = `запас ${Math.round(d.finance.days_left)} дн.`;

    document.getElementById('kpi-active-amount').textContent = fmtShort(d.deals.active_amount);
    document.getElementById('kpi-active-count').textContent = `${d.deals.active} сделок`;

    document.getElementById('kpi-debt').textContent = fmtShort(d.debitors.total);
    document.getElementById('kpi-debt-count').textContent = `${d.debitors.count} должников`;

    // Mini stats
    document.getElementById('mini-deals').textContent = d.deals.total;
    document.getElementById('mini-conv').textContent = d.deals.conversion + '%';
    document.getElementById('mini-avg').textContent = fmtShort(d.deals.avg_check);
    document.getElementById('mini-cycle').textContent = d.analytics.deal_cycle.avg + ' дн.';

    // Funnel & Overdue
    renderFunnel(d.funnel);
    renderOverdue(d.overdue);

    // === Finance tab ===
    document.getElementById('profit-revenue').textContent = fmt(d.profit.total_paid) + ' сом';
    document.getElementById('profit-purchases').textContent = '−' + fmt(d.profit.total_purchases) + ' сом';
    document.getElementById('monthly-costs').textContent = fmt(d.profit.fixed_costs_monthly) + ' сом/мес';
    document.getElementById('profit-unpaid').textContent = fmt(d.profit.total_unpaid) + ' сом';
    const netEl = document.getElementById('profit-net');
    netEl.textContent = fmt(d.profit.net_profit_ytd) + ' сом';
    netEl.className = 'stat-val ' + (d.profit.net_profit_ytd >= 0 ? 'color-green' : 'color-red');
    document.getElementById('days-reserve').textContent = Math.round(d.finance.days_left) + ' дней';

    renderProfitChart(d.profit.monthly_profit);
    renderMonthsChart(d.finance.months_data);
    renderPurchasesChart(d.profit.monthly_purchases);

    // === Deals tab ===
    renderAgingChart(d.analytics.debt_aging.buckets);
    renderManagers(d.managers);
    renderRejectionsChart(d.rejections);
    renderDebitors(d.debitors.list);

    // === Team tab ===
    renderManagerRanking(d.manager_ranking);
    renderSeamstressesChart(d.managers_sheets);
    renderSeamstressDetails(d.managers_sheets);

    // === Analytics tab ===
    renderProductsChart(d.analytics.products);
    renderPrintMethods(d.analytics.print_methods);
    renderRepeatClients(d.analytics.repeat_clients);
    renderSourcesChart(d.analytics.sources);
    renderMonthlyDealsChart(d.analytics.monthly_deals);
}

// === RENDER FUNCTIONS ===

function renderPlanFact(pf) {
    if (!pf) return;
    const pct = Math.min(pf.pct, 100);
    document.getElementById('plan-pct').textContent = pf.pct + '%';
    document.getElementById('plan-pct').className = 'plan-pct ' + (pf.pct >= 100 ? 'color-green' : pf.pct >= 70 ? 'color-orange' : 'color-red');
    document.getElementById('plan-bar').style.width = pct + '%';
    document.getElementById('plan-bar').className = 'progress-bar ' + (pf.pct >= 100 ? 'bar-green' : pf.pct >= 70 ? 'bar-orange' : 'bar-red');
    document.getElementById('plan-current').textContent = fmtShort(pf.current) + ' сом';
    document.getElementById('plan-target').textContent = 'из ' + fmtShort(pf.target);
    if (pf.pct < 100 && pf.days_remaining > 0) {
        document.getElementById('plan-daily').textContent =
            `${pf.deals_won} выиграно | осталось ${pf.days_remaining} дн. | нужно ${fmtShort(pf.daily_needed)}/день`;
    } else if (pf.pct >= 100) {
        document.getElementById('plan-daily').textContent = 'План выполнен!';
    }
}

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

function renderManagerRanking(ranking) {
    const el = document.getElementById('manager-ranking');
    if (!ranking || !ranking.length) { el.innerHTML = '<p>Нет данных</p>'; return; }
    const active = ranking.filter(m => m.revenue > 0 || m.deals_total > 0);
    if (!active.length) { el.innerHTML = '<p>Нет данных</p>'; return; }
    const maxRev = Math.max(...active.map(m => m.revenue));
    el.innerHTML = '<div class="ranking-table">' +
        '<div class="ranking-header"><span>Менеджер</span><span>Выручка</span><span>Конв</span><span>Ср.чек</span></div>' +
        active.map((m, i) => {
            const barW = maxRev > 0 ? (m.revenue / maxRev * 100) : 0;
            const medal = i === 0 ? '1' : i === 1 ? '2' : i === 2 ? '3' : '';
            return `<div class="ranking-row">
                <div class="ranking-info">
                    <span class="ranking-pos ${i < 3 ? 'top' + (i+1) : ''}">${medal || (i+1)}</span>
                    <span class="ranking-name">${m.name}</span>
                </div>
                <div class="ranking-bar-bg"><div class="ranking-bar" style="width:${barW}%"></div></div>
                <div class="ranking-stats">
                    <span>${fmtShort(m.revenue)}</span>
                    <span>${m.conversion}%</span>
                    <span>${fmtShort(m.avg_check)}</span>
                </div>
            </div>`;
        }).join('') +
    '</div>';
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

function renderPrintMethods(methods) {
    const el = document.getElementById('print-methods');
    if (!methods.length) { el.innerHTML = '<p>Нет данных</p>'; return; }
    const total = methods.reduce((s, m) => s + m.count, 0);
    el.innerHTML = methods.map(m => {
        const pct = total ? Math.round(m.count / total * 100) : 0;
        const color = m.name === 'Вышивка' ? 'var(--blue)' : 'var(--orange)';
        return `<div class="method-row">
            <div class="method-header">
                <span class="method-name" style="color:${color}">${m.name}</span>
                <span class="method-pct">${pct}% (${m.count} шт.)</span>
            </div>
            <div class="method-bar-bg"><div class="method-bar" style="width:${pct}%;background:${color}"></div></div>
            <div class="method-revenue">Выручка: ${fmtShort(m.revenue)} сом</div>
        </div>`;
    }).join('');
}

function renderRepeatClients(data) {
    document.getElementById('clients-unique').textContent = data.unique;
    document.getElementById('clients-repeat').textContent = data.repeat;
    document.getElementById('clients-pct').textContent = data.repeat_pct + '%';

    const el = document.getElementById('top-clients');
    if (!data.top.length) return;
    el.innerHTML = '<div class="top-label">Топ повторных клиентов:</div>' +
        data.top.map(c =>
            `<div class="debt-row">
                <span class="debt-title">${c.title} (${c.orders}x)</span>
                <span class="stat-val">${fmtShort(c.revenue)}</span>
            </div>`
        ).join('');
}

// === CHARTS ===

function renderProfitChart(monthly) {
    if (!monthly.length) return;
    createChart('chart-profit', {
        type: 'bar',
        data: {
            labels: monthly.map(m => m.month),
            datasets: [{
                label: 'Прибыль',
                data: monthly.map(m => m.profit),
                backgroundColor: monthly.map(m => m.profit >= 0 ? '#2ec4b6' : '#e63946'),
                borderRadius: 6, barPercentage: 0.6,
            }]
        },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: v => fmtShort(v) } } } }
    });
}

function renderPurchasesChart(purchases) {
    if (!purchases.length) return;
    createChart('chart-purchases', {
        type: 'bar',
        data: {
            labels: purchases.map(p => p.month),
            datasets: [{ label: 'Закуп', data: purchases.map(p => p.amount), backgroundColor: '#ff9f1c', borderRadius: 6, barPercentage: 0.6 }]
        },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { ticks: { callback: v => fmtShort(v) } } } }
    });
}

function renderMonthsChart(months) {
    if (!months.length) return;
    createChart('chart-months', {
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
    createChart('chart-rejections', {
        type: 'doughnut',
        data: { labels, datasets: [{ data: values, backgroundColor: ['#e63946', '#ff9f1c', '#4361ee', '#2ec4b6', '#8a8a9a'], borderWidth: 0 }] },
        options: { responsive: true, cutout: '60%', plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 11 }, padding: 12 } } } }
    });
}

function renderSeamstressesChart(seamstresses) {
    if (!seamstresses.length) return;
    createChart('chart-seamstresses', {
        type: 'bar',
        data: {
            labels: seamstresses.map(s => s.name),
            datasets: [{ label: 'Сумма заказов', data: seamstresses.map(s => s.total), backgroundColor: ['#4361ee', '#2ec4b6', '#ff9f1c', '#e63946'], borderRadius: 8, barPercentage: 0.6 }]
        },
        options: { responsive: true, indexAxis: 'y', scales: { x: { ticks: { callback: v => fmtShort(v) } } } }
    });
}

function renderAgingChart(buckets) {
    if (!buckets.length) return;
    createChart('chart-aging', {
        type: 'bar',
        data: {
            labels: buckets.map(b => b.label),
            datasets: [{
                label: 'Сумма',
                data: buckets.map(b => b.amount),
                backgroundColor: ['#2ec4b6', '#ff9f1c', '#e63946', '#8b0000'],
                borderRadius: 6, barPercentage: 0.6,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: ctx => `${fmt(ctx.raw)} сом (${buckets[ctx.dataIndex].count} шт.)` } }
            },
            scales: { y: { ticks: { callback: v => fmtShort(v) } } }
        }
    });
}

function renderProductsChart(products) {
    if (!products.length) return;
    createChart('chart-products', {
        type: 'bar',
        data: {
            labels: products.map(p => p.name),
            datasets: [{
                label: 'Количество',
                data: products.map(p => p.count),
                backgroundColor: ['#4361ee', '#2ec4b6', '#ff9f1c', '#e63946', '#8a8a9a', '#6c5ce7', '#fd79a8', '#00cec9', '#636e72', '#d63031'],
                borderRadius: 6, barPercentage: 0.6,
            }]
        },
        options: {
            responsive: true, indexAxis: 'y',
            plugins: {
                tooltip: { callbacks: { label: ctx => `${ctx.raw} шт. | ${fmtShort(products[ctx.dataIndex].revenue)} сом` } }
            },
        }
    });
}

function renderSourcesChart(sources) {
    if (!sources.length) return;
    createChart('chart-sources', {
        type: 'bar',
        data: {
            labels: sources.map(s => s.name),
            datasets: [
                { label: 'Всего', data: sources.map(s => s.total), backgroundColor: '#4361ee', borderRadius: 6, barPercentage: 0.5 },
                { label: 'Выиграно', data: sources.map(s => s.won), backgroundColor: '#2ec4b6', borderRadius: 6, barPercentage: 0.5 },
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } },
                tooltip: { callbacks: { afterLabel: ctx => `Конв: ${sources[ctx.dataIndex].conversion}% | ${fmtShort(sources[ctx.dataIndex].revenue)} сом` } }
            },
        }
    });
}

function renderMonthlyDealsChart(monthly) {
    if (!monthly.length) return;
    createChart('chart-monthly-deals', {
        type: 'bar',
        data: {
            labels: monthly.map(m => m.month),
            datasets: [
                { label: 'Выиграно', data: monthly.map(m => m.won), backgroundColor: '#2ec4b6', borderRadius: 6, barPercentage: 0.5 },
                { label: 'Всего', data: monthly.map(m => m.total), backgroundColor: '#4361ee44', borderRadius: 6, barPercentage: 0.5 },
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } },
                tooltip: { callbacks: { afterLabel: ctx => `Выручка: ${fmtShort(monthly[ctx.dataIndex].revenue)} сом` } }
            },
        }
    });
}

// Start
loadDashboard();
