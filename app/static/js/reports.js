/**
 * SpendSense — Reports & Analytics Visualization
 * Responsive Chart.js configuration supporting Light and Dark themes dynamically.
 */

(function () {
    let categoryChart = null;
    let trendChart = null;
    let cachedChartData = null;

    // Harmonious, high-contrast palette accessible in both light and dark modes
    const palette = [
        '#2563eb', // Royal Blue
        '#10b981', // Emerald
        '#f59e0b', // Amber
        '#ef4444', // Red / Crimson
        '#8b5cf6', // Violet
        '#06b6d4', // Cyan
        '#ec4899', // Pink
        '#14b8a6', // Teal
        '#f97316', // Orange
        '#64748b'  // Slate
    ];

    function getThemeStyles() {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        return {
            textColor: isDark ? '#e2e8f0' : '#1e293b',       /* Bright Slate 200 in dark mode, Deep Slate 800 in light mode */
            gridColor: isDark ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.08)',
            tooltipBg: isDark ? '#1e293b' : '#ffffff',
            tooltipText: isDark ? '#f8fafc' : '#0f172a',
            tooltipBorder: isDark ? '#475569' : '#cbd5e1',
            sliceBorder: isDark ? '#131b2e' : '#ffffff',
            incomeColor: isDark ? '#4ade80' : '#15803d',
            expenseColor: isDark ? '#f87171' : '#b91c1c'
        };
    }

    function renderChartsWithData(data) {
        if (!data) return;
        const styles = getThemeStyles();

        // 1. Spending by Category (Doughnut Chart)
        const pieCtx = document.getElementById('categoryPieChart');
        if (pieCtx) {
            const catLabels = data.expense_categories ? data.expense_categories.labels : [];
            const catValues = data.expense_categories ? data.expense_categories.data : [];

            if (categoryChart) {
                categoryChart.destroy();
                categoryChart = null;
            }

            if (catLabels && catLabels.length > 0) {
                pieCtx.style.display = 'block';
                const alertEl = document.getElementById('noExpenseAlert');
                if (alertEl) alertEl.classList.add('d-none');

                categoryChart = new Chart(pieCtx, {
                    type: 'doughnut',
                    data: {
                        labels: catLabels,
                        datasets: [{
                            data: catValues,
                            backgroundColor: palette.slice(0, catLabels.length),
                            borderWidth: 2,
                            borderColor: styles.sliceBorder,
                            hoverOffset: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: {
                                    boxWidth: 12,
                                    boxHeight: 12,
                                    borderRadius: 3,
                                    useBorderRadius: true,
                                    padding: 12,
                                    color: styles.textColor,
                                    font: {
                                        size: 12,
                                        family: 'Plus Jakarta Sans',
                                        weight: '500'
                                    }
                                }
                            },
                            tooltip: {
                                backgroundColor: styles.tooltipBg,
                                borderColor: styles.tooltipBorder,
                                borderWidth: 1,
                                titleColor: styles.tooltipText,
                                bodyColor: styles.tooltipText,
                                padding: 10,
                                cornerRadius: 6,
                                callbacks: {
                                    label: function (context) {
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        return ` ${label}: ₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                                    }
                                }
                            }
                        },
                        cutout: '68%'
                    }
                });
            } else {
                pieCtx.style.display = 'none';
                const alertEl = document.getElementById('noExpenseAlert');
                if (alertEl) alertEl.classList.remove('d-none');
            }
        }

        // 2. Income vs. Spending Trend (Bar Chart)
        const barCtx = document.getElementById('trendBarChart');
        if (barCtx && data.monthly_trends) {
            if (trendChart) {
                trendChart.destroy();
                trendChart = null;
            }

            trendChart = new Chart(barCtx, {
                type: 'bar',
                data: {
                    labels: data.monthly_trends.labels,
                    datasets: [
                        {
                            label: 'Income',
                            data: data.monthly_trends.income,
                            backgroundColor: styles.incomeColor,
                            borderRadius: 4,
                            maxBarThickness: 28
                        },
                        {
                            label: 'Expense',
                            data: data.monthly_trends.expense,
                            backgroundColor: styles.expenseColor,
                            borderRadius: 4,
                            maxBarThickness: 28
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            align: 'end',
                            labels: {
                                boxWidth: 12,
                                boxHeight: 12,
                                borderRadius: 3,
                                useBorderRadius: true,
                                color: styles.textColor,
                                font: { family: 'Plus Jakarta Sans', size: 12, weight: '500' }
                            }
                        },
                        tooltip: {
                            backgroundColor: styles.tooltipBg,
                            borderColor: styles.tooltipBorder,
                            borderWidth: 1,
                            titleColor: styles.tooltipText,
                            bodyColor: styles.tooltipText,
                            padding: 10,
                            cornerRadius: 6,
                            callbacks: {
                                label: function (context) {
                                    const val = context.parsed.y || 0;
                                    return ` ${context.dataset.label}: ₹${val.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: styles.textColor,
                                font: { family: 'Plus Jakarta Sans', size: 11 }
                            }
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: styles.gridColor },
                            ticks: {
                                color: styles.textColor,
                                font: { family: 'Plus Jakarta Sans', size: 11, weight: '600' },
                                callback: function (val) {
                                    return '₹' + (val >= 1000 ? (val / 1000).toLocaleString('en-IN') + 'k' : val);
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    // Expose chart re-render hook globally for theme toggler in base.html
    window.renderCharts = function () {
        if (cachedChartData) {
            renderChartsWithData(cachedChartData);
        }
    };

    document.addEventListener('DOMContentLoaded', function () {
        const monthSelect = document.getElementById('reportMonth');
        const yearSelect = document.getElementById('reportYear');

        const selectedMonth = monthSelect ? monthSelect.value : (new Date().getMonth() + 1);
        const selectedYear = yearSelect ? yearSelect.value : new Date().getFullYear();

        fetch(`/reports/api/chart-data?month=${selectedMonth}&year=${selectedYear}`)
            .then(res => res.json())
            .then(data => {
                cachedChartData = data;
                renderChartsWithData(data);
            })
            .catch(err => {
                console.error('Failed to load chart telemetry:', err);
            });
    });
})();
