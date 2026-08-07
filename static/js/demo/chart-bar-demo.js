document.addEventListener("DOMContentLoaded", function () {
  const sheetSelector = document.getElementById("sheetSelector");

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

            // Auto-select the latest sheet (which is at the top)
            if (data.sheets.length > 0) {
                const latestSheet = data.sheets[0].value; // Get the first sheet (latest one)
                sheetSelector.value = latestSheet; // Set it as selected

                console.log("Latest sheet selected:", latestSheet);

                // Fetch chart data and update progress bars
                fetchChartData(latestSheet);
            }
        })
        .catch(error => console.error("Error fetching sheets:", error));
  }

  // Fetch chart data based on sheet name
  async function fetchChartData(sheetName) {
    try {
        const monthlyResponse = await fetch(`/dashboard/get_monthly_expenses/?sheet_name=${sheetName}`);
        const monthlyData = await monthlyResponse.json();

        if (!monthlyResponse.ok || monthlyData.error) {
            throw new Error(monthlyData.error || `HTTP ${monthlyResponse.status}`);
        }

        // The progress bars and pie chart intentionally share this response.
        updateProgressBars(monthlyData);
        if (typeof window.updateExpensePie === "function") {
            window.updateExpensePie(monthlyData);
        }
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

  // Call loadSheets() on page load
  loadSheets();

  // Attach fetch call to the dropdown selection
  sheetSelector.addEventListener("change", function () {
      fetchChartData(this.value);
  });
});
