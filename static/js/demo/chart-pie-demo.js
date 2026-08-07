// Set new default font family and font color to mimic Bootstrap's default styling
Chart.defaults.global.defaultFontFamily = 'Nunito', '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.global.defaultFontColor = '#858796';

// Expense breakdown chart. It is updated from the same API response as the
// Breakdown Expenses progress bars in chart-bar-demo.js.
var ctx = document.getElementById("myPieChart");
var myPieChart = new Chart(ctx, {
  type: 'doughnut',
  data: {
    labels: [
      "Food",
      "Leisure",
      "Utilities",
      "Automatic Withdrawal",
      "SMBC Payments",
      "Stuff"
    ],
    datasets: [{
      data: [0, 0, 0, 0, 0, 0],
      backgroundColor: [
        '#e74a3b', '#f6c23e', '#1cc88a',
        '#4e73df', '#36b9cc', '#858796'
      ],
      hoverBackgroundColor: [
        '#c83b2f', '#dda20a', '#17a673',
        '#2e59d9', '#2c9faf', '#6c757d'
      ],
      hoverBorderColor: "rgba(234, 236, 244, 1)",
    }],
  },
  options: {
    maintainAspectRatio: false,
    tooltips: {
      backgroundColor: "rgb(255,255,255)",
      bodyFontColor: "#858796",
      borderColor: '#dddfeb',
      borderWidth: 1,
      xPadding: 15,
      yPadding: 15,
      displayColors: false,
      caretPadding: 10,
    },
    legend: {
      display: true,
      position: 'bottom'
    },
    cutoutPercentage: 80,
  },
});

window.updateExpensePie = function(monthlyExpenses) {
  const values = [
    monthlyExpenses.Food,
    monthlyExpenses.Leisure,
    monthlyExpenses.Utility,
    monthlyExpenses.Automatic_withdrawal,
    monthlyExpenses.SMBC_payments,
    monthlyExpenses.Stuff
  ].map(value => {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : 0;
  });

  myPieChart.data.datasets[0].data = values;
  myPieChart.update();
};
