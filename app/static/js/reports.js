/**
 * SpendSense - Reports Charts Script
 * Fetches JSON metrics and initializes Chart.js visualizations
 */

document.addEventListener('DOMContentLoaded', function () {
    const monthSelect = document.getElementById('reportMonth');
    const yearSelect = document.getElementById('reportYear');

    const selectedMonth = monthSelect ? monthSelect.value : new Date().getMonth() + 1;
    const selectedYear = yearSelect ? yearSelect.value : new Date().getFullYear();

    // Vibrant modern color palette for categories
    const chartColors = [
        '#4361ee', '#3a0ca3', '#7209b7', '#f72585', '#4cc9f0',
        '#ff9f1c', '#2ec4b6', '#e71d36', '#011627', '#6c757d',
        '#20c997', '#fd7e14', '#0d6efd', '#6610f2', '#6f42c1'
    ];

    fetch(`/reports/api/chart-data?month=${selectedMonth}&year=${selectedYear}`)
        .then(response => response.json())
        .then(data => {
            // 1. Render Category Doughnut Chart
            const pieCtx = document.getElementById('categoryPieChart');
            if (pieCtx) {
                const catLabels = data.expense_categories.labels;
                const catValues = data.expense_categories.data;

                if (catLabels.length > 0) {
                    new Chart(pieCtx, {
                        type: 'doughnut',
                        data: {
                            labels: catLabels,
                            datasets: [{
                                data: catValues,
                                backgroundColor: chartColors.slice(0, catLabels.length),
                                borderWidth: 2,
                                borderColor: '#ffffff',
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
                                        padding: 12,
                                        font: {
                                            size: 11,
                                            family: 'Inter'
                                        }
                                    }
                                },
                                tooltip: {
                                    callbacks: {
                                        label: function (context) {
                                            let label = context.label || '';
                                            let value = context.parsed || 0;
                                            return `${label}: ₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
                                        }
                                    }
                                }
                            },
                            cutout: '65%'
                        }
                    });
                } else {
                    pieCtx.style.display = 'none';
                    const alertEl = document.getElementById('noExpenseAlert');
                    if (alertEl) alertEl.classList.remove('d-none');
                }
            }

            // 2. Render Income vs Expense Trend Bar Chart
            const barCtx = document.getElementById('trendBarChart');
            if (barCtx) {
                new Chart(barCtx, {
                    type: 'bar',
                    data: {
                        labels: data.monthly_trends.labels,
                        datasets: [
                            {
                                label: 'Income',
                                data: data.monthly_trends.income,
                                backgroundColor: '#2ec4b6',
                                borderRadius: 6,
                                maxBarThickness: 32
                            },
                            {
                                label: 'Expenses',
                                data: data.monthly_trends.expense,
                                backgroundColor: '#e63946',
                                borderRadius: 6,
                                maxBarThickness: 32
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
                                    boxWidth: 14,
                                    font: { family: 'Inter', size: 12 }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function (context) {
                                        return `${context.dataset.label}: ₹${context.parsed.y.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { display: false }
                            },
                            y: {
                                beginAtZero: true,
                                grid: { color: '#f1f5f9' },
                                ticks: {
                                    callback: function (val) {
                                        return '₹' + (val >= 1000 ? (val / 1000) + 'k' : val);
                                    }
                                }
                            }
                        }
                    }
                });
            }
        })
        .catch(err => {
            console.error('Error loading analytics chart data:', err);
        });
});
