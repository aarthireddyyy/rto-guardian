import os
import pandas as pd
import numpy as np
# pyrefly: ignore [missing-import]
import xgboost as xgb 
# pyrefly: ignore [missing-import]
import joblib
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
# pyrefly: ignore [missing-import]
import matplotlib.pyplot as plt
# pyrefly: ignore [missing-import]
import shap

# 1. Load Data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(BASE_DIR, 'synthetic_data.csv')
data = pd.read_csv(csv_path)

# 2. Preprocess
# Encode payment_mode: COD -> 1, Prepaid -> 0 (Usually LabelEncoder does alphabetical COD=0, Prepaid=1)
le = LabelEncoder()
data['payment_mode'] = le.fit_transform(data['payment_mode'])

X = data.drop('is_rto', axis=1)
y = data['is_rto']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Scale numerical features (important for FastAPI endpoint consistency)
scaler = StandardScaler()
feature_cols = X.columns.tolist()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# 3. Train XGBoost
model = xgb.XGBClassifier(
    n_estimators=150,          # 150 trees
    max_depth=5,               # shallow to prevent overfitting
    learning_rate=0.1,         
    reg_alpha=0.1,             # L1 (Lasso) - feature selection
    reg_lambda=1.0,            # L2 (Ridge) - prevents dominating features
    scale_pos_weight=1.5,      # Gentle upweight for RTO class
    eval_metric='logloss',
    random_state=42
)

model.fit(X_train_scaled, y_train)

# 4. Evaluate
y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]

# Use our API's 0.3 threshold instead of the default 0.5
y_pred_custom = (y_pred_proba >= 0.3).astype(int)

print("=== Classification Report (Threshold = 0.3) ===")
print(classification_report(y_test, y_pred_custom, target_names=['Delivered', 'RTO']))

cm = confusion_matrix(y_test, y_pred_custom)
print("=== Confusion Matrix ===")
print(f"  TN={cm[0][0]}  FP={cm[0][1]}")
print(f"  FN={cm[1][0]}  TP={cm[1][1]}")

auc = roc_auc_score(y_test, y_pred_proba)
print(f"\nAUC-ROC: {auc:.4f}")

# 5. SHAP Explainability (Saved to image)
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test_scaled)
plt.figure()
shap.summary_plot(shap_values, X_test_scaled, feature_names=feature_cols, show=False)
shap_path = os.path.join(BASE_DIR, 'shap_summary.png')
plt.savefig(shap_path, bbox_inches='tight')
print(f"\nSHAP summary plot saved to {shap_path}")

# 6. Save Model Bundle
artifact = {
    'model': model,
    'scaler': scaler,
    'feature_columns': feature_cols,
    'label_encoder': le,
    'version': '1.0.0'
}

model_dir = os.path.join(BASE_DIR, 'models')
os.makedirs(model_dir, exist_ok=True)
model_path = os.path.join(model_dir, 'rto_risk_model.pkl')
joblib.dump(artifact, model_path)
print(f"Model bundle saved: {os.path.getsize(model_path) / 1024:.1f} KB")
