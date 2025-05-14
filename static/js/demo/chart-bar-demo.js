// Set new default font family and font color to mimic Bootstrap's default styling
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

// Bar Chart Example
var ctx = document.getElementById("myBarChart");
var myBarChart = new Chart(ctx, {
  type: 'bar',
  data: {
    labels: [],
    datasets: [
      {
        label: "Food",
        backgroundColor: "#4e73df",
        hoverBackgroundColor: "#2e59d9",
        borderColor: "#4e73df",
        data: [],
      },
      {
        label: "Leisure",
        backgroundColor: "#1cc88a",
        hoverBackgroundColor: "#17a673",
        borderColor: "#1cc88a",
        data: [],
      },
      {
        label: "Utilities",
        backgroundColor: "#36b9cc",
        hoverBackgroundColor: "#2c9faf",
        borderColor: "#36b9cc",
        data: [],
      },
      {
        label: "Automatic Withdrawals",
        backgroundColor: "#f6c23e",
        hoverBackgroundColor: "#f4b619",
        borderColor: "#f6c23e",
        data: [],
      },
      {
        label: "SMBC Payments",
        backgroundColor: "#e74a3b",
        hoverBackgroundColor: "#d52c1e",
        borderColor: "#e74a3b",
        data: [],
      },
      {
        label: "Stuff",
        backgroundColor: "#858796",
        hoverBackgroundColor: "#6b7280",
        borderColor: "#858796",
        data: [],
      }
    ],
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
          unit: 'month'
        },
        stacked: true, // Stack bars to group them by month
        gridLines: {
          display: false,
          drawBorder: false
        },
        ticks: {
          maxTicksLimit: 6
        },
        maxBarThickness: 25,
      }],
      yAxes: [{
        stacked: true, // Stack values to show total expenses
        ticks: {
          min: 0,
          max: 15000,
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
      display: true
    },
    tooltips: {
      titleMarginBottom: 10,
      titleFontColor: '#6e707e',
      titleFontSize: 14,
      backgroundColor: "rgb(255,255,255)",
      bodyFontColor: "#858796",
      borderColor: '#dddfeb',
      borderWidth: 1,
      xPadding: 15,
      yPadding: 15,
      displayColors: true,
      caretPadding: 10,
      callbacks: {
        label: function(tooltipItem, chart) {
          var datasetLabel = chart.datasets[tooltipItem.datasetIndex].label || '';
          return datasetLabel + ': ¥' + number_format(tooltipItem.yLabel);
        }
      }
    },
  }
});
document.addEventListener("DOMContentLoaded", function () {
  const sheetSelector = document.getElementById("sheetSelector");
  const chartCanvas = document.getElementById("myBarChart");
  let myBarChart; // Assume this is already initialized elsewhere

  function loadSheets() {
    fetch("/dashboard/get_sheets/")
        .then(response => response.json())
        .then(data => {
            sheetSelector.innerHTML = '<option value="" disabled>Select a Google Sheet</option>';
            
            data.sheets.forEach(sheet => {
                const option = document.createElement("option");
                option.value = sheet.value;  
                option.textContent = sheet.name;
                sheetSelector.appendChild(option);
            });

            // ✅ Auto-select the latest sheet (which is at the top)
            if (data.sheets.length > 0) {
                const latestSheet = data.sheets[0].value; // Get the first sheet (latest one)
                sheetSelector.value = latestSheet; // Set it as selected

                console.log("Latest sheet selected:", latestSheet);

                // ✅ Fetch chart data and update progress bars
                fetchChartData(latestSheet);
            }
        })
        .catch(error => console.error("Error fetching sheets:", error));
}


  // Fetch chart data based on sheet name
  async function fetchChartData(sheetName) {
    try {
        // Use the query parameter key "sheet_name" for both endpoints
        const response = await fetch(`/dashboard/get_sheet_data/?sheet_name=${sheetName}`);
        const data = await response.json();

        const monthlyResponse = await fetch(`/dashboard/get_monthly_expenses/?sheet_name=${sheetName}`);
        const monthlyData = await monthlyResponse.json();

        // Merge the detailed sheet data with the monthly breakdown
        const mergedData = { ...data, monthly_expenses: monthlyData };

        // Update the progress bar spans with the percentage values
        updateProgressBars(mergedData.monthly_expenses);
        // Update the chart (assuming your chart uses detailed data arrays)
        updateChart(mergedData);
    } catch (error) {
        console.error("Error fetching chart data:", error);
    }
  }

  function updateProgressBars(monthlyExpenses) {
    // Example: monthlyExpenses might be { Food: 34.18, Leisure: 0, Utility: 0, Automatic_withdrawal: 62.76, SMBC_payments: 7.05, Stuff: 3.06 }
    document.getElementById("food-percent").innerText = Math.round(monthlyExpenses.Food) + "%";
    document.querySelector('[data-category="food"]').style.width = Math.round(monthlyExpenses.Food) + "%";
  
    document.getElementById("leisure-percent").innerText = Math.round(monthlyExpenses.Leisure) + "%";
    document.querySelector('[data-category="leisure"]').style.width = Math.round(monthlyExpenses.Leisure) + "%";
  
    document.getElementById("utilities-percent").innerText = Math.round(monthlyExpenses.Utility) + "%";
    document.querySelector('[data-category="utilities"]').style.width = Math.round(monthlyExpenses.Utility) + "%";
  
    document.getElementById("auto-percent").innerText = Math.round(monthlyExpenses.Automatic_withdrawal) + "%";
    document.querySelector('[data-category="automatic"]').style.width = Math.round(monthlyExpenses.Automatic_withdrawal) + "%";
  
    document.getElementById("smbc-percent").innerText = Math.round(monthlyExpenses.SMBC_payments) + "%";
    document.querySelector('[data-category="smbc"]').style.width = Math.round(monthlyExpenses.SMBC_payments) + "%";
  
    document.getElementById("stuff-percent").innerText = Math.round(monthlyExpenses.Stuff) + "%";
    document.querySelector('[data-category="stuff"]').style.width = Math.round(monthlyExpenses.Stuff) + "%";
  }
  

  // Update the bar chart with detailed data (assumes myBarChart has been initialized)
  function updateChart(data) {
      // Here, data contains your detailed arrays (e.g., "dates", "food", etc.)
      // Adjust according to your actual chart data structure.
      myBarChart.data.labels = data.dates || []; // Or data.months if that’s what you're using
      myBarChart.data.datasets[0].data = data.food || [];
      myBarChart.data.datasets[1].data = data.leisure || [];
      myBarChart.data.datasets[2].data = data.utility || [];
      myBarChart.data.datasets[3].data = data.automatic_withdrawals || [];
      myBarChart.data.datasets[4].data = data.smbc_payments || [];
      myBarChart.data.datasets[5].data = data.stuff || [];
      myBarChart.update();
  }

  // Call loadSheets() on page load
  loadSheets();

  // Attach fetch call to the dropdown selection
  sheetSelector.addEventListener("change", function () {
      fetchChartData(this.value);
  });
});