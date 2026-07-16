import numpy as np
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

np.random.seed(42)
n = 10000

# 1. Feature Generation
data = pd.DataFrame({
    'user_history_rto_rate': np.random.beta(2, 5, n),        
    'user_total_orders':     np.random.poisson(8, n),         
    'orders_in_last_7days':  np.random.poisson(1.5, n),       
    'payment_mode':          np.random.choice(['COD', 'Prepaid'], n, p=[0.70, 0.30]),  
    'order_value':           np.random.lognormal(6, 0.8, n).clip(99, 4999).round(0),   
    'address_length':        np.random.normal(55, 20, n).clip(8, 150).astype(int),     
    'pincode_rto_rate':      np.random.beta(2, 8, n),         
})

# 2. Target Generation (is_rto)
# Realistic calculation mimicking real-world risk factors
base_risk = (
    0.50 * data['user_history_rto_rate'] +                    # High past RTO -> High Risk
    0.20 * (data['payment_mode'] == 'COD').astype(float) +    # COD -> Less commitment
    0.15 * data['pincode_rto_rate'] +                         # Risky area
    0.15 * (1 - data['address_length'] / 150)                 # Short address -> Vague -> High Risk
)

# Scale base_risk so the average RTO rate is exactly 25%
target_mean = 0.25
scaled_risk = base_risk * (target_mean / base_risk.mean())
scaled_risk = scaled_risk.clip(0.01, 0.95)

# Generate labels probabilistically based on the risk score (adds realistic noise!)
# This ensures XGBoost outputs smooth probabilities (0.1 to 0.9) instead of just 0.001 or 0.999
data['is_rto'] = np.random.binomial(1, scaled_risk)

# 3. Validation output
print(f"Generated {n} rows of synthetic data.")
print(f"Realistic RTO rate achieved: {data['is_rto'].mean():.1%}")

# Save for training step
csv_path = os.path.join(BASE_DIR, 'synthetic_data.csv')
data.to_csv(csv_path, index=False)
print(f"Data saved successfully to {csv_path}")
