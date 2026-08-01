// Set new default font family and font color
Chart.defaults.global.defaultFontFamily = 'Nunito', '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#858796';

function number_format(number, decimals, dec_point, thousands_sep) {
  number = (number + '').replace(',', '').replace(' ', '');
  var n = !isFinite(+number) ? 0 : +number,
    prec = !isFinite(+decimals) ? 0 : Math.abs(decimals),
    sep = (typeof thousands_sep === 'undefined') ? ',' : thousands_sep,
    dec = (typeof dec_point === 'undefined') ? '.' : dec_point,
    s = '',
    toFixedFix = function(n, prec) {
      var k = Math.pow(10, prec);
      return '' + Math.round(n * k) / k;
    };
  s = (prec ? toFixedFix(n, prec) : '' + Math.round(n)).split('.');
  if (s[0].length > 3) {
    s[0] = s[0].replace(/\B(?=(?:\d{3})+(?!\d))/g, sep);
  }
  if ((s[1] || '').length < prec) {
    s[1] = s[1] || '';
    s[1] += new Array(prec - s[1].length + 1).join('0');
  }
  return s.join(dec);
}

// Check if canvas element exists before creating chart
var ctx = document.getElementById("myAreaChart");
if (!ctx) {
    console.error('Canvas element #myAreaChart not found!');
}

var myLineChart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: [],
    datasets: [{
      label: "Expenses",
      lineTension: 0.3,
      backgroundColor: "rgba(78, 115, 223, 0.05)",
      borderColor: "rgba(78, 115, 223, 1)",
      pointRadius: 3,
      pointBackgroundColor: "rgba(78, 115, 223, 1)",
      pointBorderColor: "rgba(78, 115, 223, 1)",
      pointHoverRadius: 3,
      pointHoverBackgroundColor: "rgba(78, 115, 223, 1)",
      pointHoverBorderColor: "rgba(78, 115, 223, 1)",
      pointHitRadius: 10,
      pointBorderWidth: 2,
      data: [],
    }],
  },
  options: {
    maintainAspectRatio: false,
    layout: {
      padding: {
        left: 10,
        right: 25,
        top: 25,
        bottom: 0
      }
    },
    scales: {
      xAxes: [{
        time: {
          unit: 'date'
        },
        gridLines: {
          display: false,
          drawBorder: false
        },
        ticks: {
          maxTicksLimit: 7
        }
      }],
      yAxes: [{
        ticks: {
          maxTicksLimit: 5,
          padding: 10,
          callback: function(value, index, values) {
            return '¥' + number_format(value);
          }
        },
        gridLines: {
          color: "rgb(234, 236, 244)",
          zeroLineColor: "rgb(234, 236, 244)",
          drawBorder: false,
          borderDash: [2],
          zeroLineBorderDash: [2]
        }
      }],
    },
    legend: {
      display: false
    },
    tooltips: {
      backgroundColor: "rgb(255,255,255)",
      bodyFontColor: "#858796",
      titleMarginBottom: 10,
      titleFontColor: '#6e707e',
      titleFontSize: 14,
      borderColor: '#dddfeb',
      borderWidth: 1,
      xPadding: 15,
      yPadding: 15,
      displayColors: false,
      intersect: false,
      mode: 'index',
      caretPadding: 10,
      callbacks: {
        label: function(tooltipItem, chart) {
          var datasetLabel = chart.datasets[tooltipItem.datasetIndex].label || '';
          return datasetLabel + ': ¥' + number_format(tooltipItem.yLabel);
        }
      }
    }
  }
});

// Current view state
let currentView = 'monthly';
let selectedMonth = null;

// Function to update the top stats cards
// Function to update the top stats cards
function updateStatsCards(sheetName) {
    if (!sheetName) {
        console.warn('No sheet name provided to updateStatsCards');
        return;
    }
    
    console.log('Updating stats for:', sheetName);
    
    fetch(`/dashboard/get_month_stats/?sheet_name=${sheetName}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('HTTP error! status: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('Stats data received:', data);
            
            // Update monthly spending
            const monthlySpendingEl = document.getElementById('monthly-spending');
            if (monthlySpendingEl) {
                monthlySpendingEl.textContent = '¥' + number_format(data.total_spend);
            }
            
            // Update budget percentage
            const budgetPercentage = Math.min(data.budget_percentage, 100);
            const budgetPercentageEl = document.getElementById('budget-percentage');
            if (budgetPercentageEl) {
                budgetPercentageEl.textContent = Math.round(budgetPercentage) + '%';
            }
            
            // Update progress bar
            const progressBar = document.getElementById('budget-progress-bar');
            if (progressBar) {
                progressBar.style.width = budgetPercentage + '%';
                progressBar.setAttribute('aria-valuenow', budgetPercentage);
                
                // Change progress bar color based on usage
                progressBar.classList.remove('bg-info', 'bg-warning', 'bg-danger');
                if (budgetPercentage < 75) {
                    progressBar.classList.add('bg-info');
                } else if (budgetPercentage < 90) {
                    progressBar.classList.add('bg-warning');
                } else {
                    progressBar.classList.add('bg-danger');
                }
            }
            
            // Update budget amount text
            const budgetAmountEl = document.getElementById('budget-amount');
            if (budgetAmountEl) {
                budgetAmountEl.textContent = '¥' + number_format(data.total_spend) + ' / ¥200,000';
            }
            
            // Update average daily spending
            const avgDailySpendingEl = document.getElementById('avg-daily-spending');
            if (avgDailySpendingEl) {
                avgDailySpendingEl.textContent = '¥' + number_format(data.avg_daily_spending);
            }
            
            // Update days tracked
            const daysTrackedEl = document.getElementById('days-tracked');
            if (daysTrackedEl) {
                daysTrackedEl.textContent = data.days_with_expenses + ' days tracked';
            }
        })
        .catch(error => console.error('Error updating stats cards:', error));
}

// Function to load available months into the dropdown
function loadMonthSelector() {
    console.log('Loading month selector...');
    
    fetch('/dashboard/get_sheets/')
        .then(response => {
            if (!response.ok) {
                throw new Error('HTTP error! status: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('Sheets data received:', data);
            
            const monthSelector = document.getElementById('monthSelector');
            if (!monthSelector) {
                console.error('Month selector element not found!');
                return;
            }
            
            monthSelector.innerHTML = '<option value="" disabled>Select a month</option>';
            
            if (!data.sheets || data.sheets.length === 0) {
                console.warn('No sheets returned from API');
                monthSelector.innerHTML = '<option value="" disabled>No sheets available</option>';
                return;
            }
            
            data.sheets.forEach(sheet => {
                const option = document.createElement('option');
                option.value = sheet.value;
                option.textContent = sheet.name;
                monthSelector.appendChild(option);
            });
            
            // Auto-select the latest month (first in the list)
            if (data.sheets.length > 0) {
                selectedMonth = data.sheets[0].value;
                monthSelector.value = selectedMonth;
                
                console.log('Auto-selected month:', selectedMonth);
                
                // Update stats cards with latest month
                updateStatsCards(selectedMonth);
                
                // Load initial chart
                updateChartView(currentView);
            }
        })
        .catch(error => {
            console.error('Error loading months:', error);
            const monthSelector = document.getElementById('monthSelector');
            if (monthSelector) {
                monthSelector.innerHTML = '<option value="" disabled>Error loading sheets</option>';
            }
        });
}

// Function to fetch and update chart based on view type and selected month
function updateChartView(viewType) {
    let endpoint = '';
    let params = '';
    
    // Add sheet_name parameter for daily and weekly views
    if (selectedMonth && (viewType === 'daily' || viewType === 'weekly')) {
        params = `?sheet_name=${selectedMonth}`;
    }
    
    switch(viewType) {
        case 'daily':
            endpoint = '/dashboard/get_daily_expenses/' + params;
            break;
        case 'weekly':
            endpoint = '/dashboard/get_weekly_expenses/' + params;
            break;
        case 'monthly':
        default:
            endpoint = '/dashboard/get_monthly_overview/';
            break;
    }
    
    console.log('Fetching chart data from:', endpoint);
    
    fetch(endpoint)
        .then(response => {
            if (!response.ok) {
                throw new Error('HTTP error! status: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('Chart data received:', data);
            
            if (!data.labels || !data.values) {
                console.error('Invalid data format:', data);
                return;
            }
            
            myLineChart.data.labels = data.labels;
            myLineChart.data.datasets[0].data = data.values;
            myLineChart.update();
            currentView = viewType;
            
            console.log('Chart updated successfully');
        })
        .catch(error => console.error("Error fetching chart data:", error));
}

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing...');
    
    // Load month selector and initial data
    loadMonthSelector();
    
    // View type dropdown click handlers
    const viewOptions = document.querySelectorAll('.view-option');
    console.log('Found view options:', viewOptions.length);
    
    viewOptions.forEach(option => {
        option.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all options
            viewOptions.forEach(opt => opt.classList.remove('active'));
            
            // Add active class to clicked option
            this.classList.add('active');
            
            // Get the view type and update chart
            const viewType = this.getAttribute('data-view');
            console.log('View changed to:', viewType);
            updateChartView(viewType);
        });
    });
    
    // Month selector change handler
    const monthSelector = document.getElementById('monthSelector');
    if (monthSelector) {
        console.log('Month selector found, attaching listener');
        monthSelector.addEventListener('change', function() {
            selectedMonth = this.value;
            console.log('Month changed to:', selectedMonth);
            
            // Update stats cards with new month
            updateStatsCards(selectedMonth);
            
            // If currently viewing daily or weekly, update the chart
            if (currentView === 'daily' || currentView === 'weekly') {
                updateChartView(currentView);
            }
        });
    } else {
        console.error('Month selector not found in DOM!');
    }
});