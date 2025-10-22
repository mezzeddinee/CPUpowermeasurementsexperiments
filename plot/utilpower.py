import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

# CPU utilization (%)
cpu_util = np.array([64, 20.2, 30, 37, 49, 56.9, 91, 100, 82, 74, 10.1]).reshape(-1, 1)

# Power (Watts)
power = np.array([17.2, 10.3, 11.7, 12.1, 12.5, 12.7, 14.17, 14.31, 13.7, 12.7, 8.2])

# Create and train the model
model = LinearRegression()
model.fit(cpu_util, power)

# Predict line
cpu_range = np.linspace(0, 110, 200).reshape(-1, 1)
predicted_power = model.predict(cpu_range)

# Print regression equation
print(f"Regression equation: Power = {model.coef_[0]:.3f} * CPU_util + {model.intercept_:.3f}")
print(f"R² score: {model.score(cpu_util, power):.3f}")

# Plot
plt.scatter(cpu_util, power, color='blue', label='Observed Data')
plt.plot(cpu_range, predicted_power, color='red', label='Linear Fit')
plt.xlabel('CPU Utilization (%)')
plt.ylabel('Power (Watts)')
plt.title('Linear Regression: CPU Utilization vs Power')
plt.legend()
plt.grid(True)
plt.show()