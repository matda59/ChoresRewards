document.addEventListener('DOMContentLoaded', function() {
    // Parse chart data from JSON script tag
    const chartDataScript = document.getElementById('chart-data');
    let chartData = {};
    if (chartDataScript) {
        try {
            chartData = JSON.parse(chartDataScript.textContent);
        } catch (e) {
            console.error('Failed to parse chart data JSON:', e);
        }
    }

    let personPieChart = null;
    let monthlyBarChart = null;
    let topTasksTrendChart = null;

    function createPersonPieChart(ctx, data) {
        return new Chart(ctx, {
            type: 'pie',
            data: data,
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        labels: {
                            color: getTextColor()
                        }
                    }
                }
            }
        });
    }

    function createMonthlyBarChart(ctx, data) {
        return new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                scales: {
                    x: {
                        ticks: {
                            color: getTextColor()
                        }
                    },
                    y: {
                        ticks: {
                            color: getTextColor()
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: getTextColor()
                        }
                    }
                }
            }
        });
    }

    function createTopTasksTrendChart(ctx, data) {
        return new Chart(ctx, {
            type: 'line',
            data: data,
            options: {
                responsive: true,
                scales: {
                    x: {
                        ticks: {
                            color: getTextColor()
                        }
                    },
                    y: {
                        ticks: {
                            color: getTextColor()
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: getTextColor()
                        }
                    }
                }
            }
        });
    }

    function getTextColor() {
        return document.body.getAttribute('data-theme') === 'dark' ? '#fff' : '#000';
    }

    window.updateChartsForTheme = function(theme) {
        const textColor = theme === 'dark' ? '#fff' : '#000';

        if (personPieChart) {
            personPieChart.options.plugins.legend.labels.color = textColor;
            personPieChart.update();
        }
        if (monthlyBarChart) {
            monthlyBarChart.options.scales.x.ticks.color = textColor;
            monthlyBarChart.options.scales.y.ticks.color = textColor;
            monthlyBarChart.options.plugins.legend.labels.color = textColor;
            monthlyBarChart.update();
        }
        if (topTasksTrendChart) {
            topTasksTrendChart.options.scales.x.ticks.color = textColor;
            topTasksTrendChart.options.scales.y.ticks.color = textColor;
            topTasksTrendChart.options.plugins.legend.labels.color = textColor;
            topTasksTrendChart.update();
        }
    };

    const personPieCtx = document.getElementById('personPie')?.getContext('2d');
    const monthlyBarCtx = document.getElementById('monthlyBar')?.getContext('2d');
    const topTasksTrendCtx = document.getElementById('topTasksTrend')?.getContext('2d');

    if (personPieCtx && chartData.personPieData) {
        personPieChart = createPersonPieChart(personPieCtx, chartData.personPieData);
    }
    if (monthlyBarCtx && chartData.monthlyBarData) {
        monthlyBarChart = createMonthlyBarChart(monthlyBarCtx, chartData.monthlyBarData);
    }
    if (topTasksTrendCtx && chartData.topTasksTrendData) {
        topTasksTrendChart = createTopTasksTrendChart(topTasksTrendCtx, chartData.topTasksTrendData);
    }
});
