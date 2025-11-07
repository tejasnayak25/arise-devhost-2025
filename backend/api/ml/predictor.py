
"""
AI/ML module for emission predictions and anomaly detection
Uses time series forecasting and statistical methods
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta, datetime
from typing import List, Dict, Optional, Tuple, Any
import logging
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logging.warning("Prophet not available, using fallback prediction method")

from models.emission_data import (
    EmissionDataPoint,
    PredictionResult,
    ReductionRecommendation,
    ActivityType,
)

logger = logging.getLogger(__name__)


class EmissionPredictor:
    """
    Predicts future emissions using time series forecasting
    """
    
    def __init__(self, model_type: str = 'prophet'):
        self.model_type = model_type
        self.model = None
        self.training_data = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def prepare_data(
        self,
        data_points: List[EmissionDataPoint]
    ) -> pd.DataFrame:
        """
        Prepare emission data for ML models
        
        Args:
            data_points: List of emission data points
            
        Returns:
            DataFrame ready for training
        """
        
        # Convert to DataFrame
        records = []
        for dp in data_points:
            if dp.co2_emissions:
                records.append({
                    'ds': pd.to_datetime(dp.date),  # Prophet requires 'ds' column
                    'y': dp.co2_emissions,  # Prophet requires 'y' column
                    'scope': dp.scope,
                    'activity_type': dp.activity_type
                })
        
        df = pd.DataFrame(records)
        
        if df.empty:
            raise ValueError("No emission data available for training")
        
        # Aggregate by date
        df_agg = df.groupby('ds')['y'].sum().reset_index()
        
        return df_agg
    
    def train(
        self,
        data_points: List[EmissionDataPoint],
        **kwargs
    ):
        """
        Train the prediction model
        
        Args:
            data_points: Historical emission data points
            **kwargs: Additional parameters for the model
        """
        
        logger.info(f"Training {self.model_type} model with {len(data_points)} data points")
        
        self.training_data = self.prepare_data(data_points)
        
        if self.model_type == 'prophet' and PROPHET_AVAILABLE:
            self._train_prophet(**kwargs)
        else:
            self._train_fallback(**kwargs)
        
        self.is_trained = True
        logger.info("Model training completed")
    
    def _train_prophet(self, **kwargs):
        """Train Facebook Prophet model"""
        
        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            **kwargs
        )
        
        self.model.fit(self.training_data)
    
    def _train_fallback(self, **kwargs):
        """Fallback training using simple moving average"""
        
        # Simple exponential smoothing
        self.model = {
            'mean': self.training_data['y'].mean(),
            'trend': self._calculate_trend(),
            'seasonal': self._calculate_seasonality()
        }
    
    def _calculate_trend(self) -> float:
        """Calculate linear trend"""
        
        if len(self.training_data) < 2:
            return 0.0
        
        x = np.arange(len(self.training_data))
        y = self.training_data['y'].values
        
        # Simple linear regression
        coeffs = np.polyfit(x, y, 1)
        return coeffs[0]  # Return slope
    
    def _calculate_seasonality(self) -> Dict[int, float]:
        """Calculate seasonal patterns by month"""
        
        self.training_data['month'] = pd.to_datetime(self.training_data['ds']).dt.month
        seasonal = self.training_data.groupby('month')['y'].mean().to_dict()
        
        return seasonal
    
    def predict_future(
        self,
        months: int = 12,
        company_id: str = "default"
    ) -> PredictionResult:
        """
        Predict future emissions
        
        Args:
            months: Number of months to forecast
            company_id: Company identifier
            
        Returns:
            PredictionResult with predictions
        """
        
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")
        
        logger.info(f"Predicting emissions for next {months} months")
        
        if self.model_type == 'prophet' and PROPHET_AVAILABLE:
            predictions = self._predict_prophet(months)
        else:
            predictions = self._predict_fallback(months)
        
        # Get forecast period
        last_date = self.training_data['ds'].max()
        forecast_start = last_date + timedelta(days=1)
        forecast_end = forecast_start + timedelta(days=30*months)
        
        # Calculate totals and confidence intervals
        total_predicted = predictions['yhat'].sum()
        confidence_lower = predictions['yhat_lower'].sum() if 'yhat_lower' in predictions else total_predicted * 0.8
        confidence_upper = predictions['yhat_upper'].sum() if 'yhat_upper' in predictions else total_predicted * 1.2
        
        # Detect trend
        trend = self._detect_trend(predictions['yhat'].values)
        
        return PredictionResult(
            company_id=company_id,
            prediction_date=date.today(),
            forecast_period_start=forecast_start.date(),
            forecast_period_end=forecast_end.date(),
            predicted_scope_1=total_predicted * 0.3,  # Assume distribution
            predicted_scope_2=total_predicted * 0.4,
            predicted_scope_3=total_predicted * 0.3,
            predicted_total=total_predicted,
            confidence_interval_lower=confidence_lower,
            confidence_interval_upper=confidence_upper,
            model_type=self.model_type,
            training_data_points=len(self.training_data),
            trend=trend,
            seasonal_patterns=self._identify_seasonal_patterns()
        )
    
    def _predict_prophet(self, months: int) -> pd.DataFrame:
        """Make predictions using Prophet"""
        
        future = self.model.make_future_dataframe(periods=months*30, freq='D')
        forecast = self.model.predict(future)
        
        # Get only future predictions
        future_forecast = forecast[forecast['ds'] > self.training_data['ds'].max()]
        
        return future_forecast
    
    def _predict_fallback(self, months: int) -> pd.DataFrame:
        """Make predictions using fallback method"""
        
        last_date = self.training_data['ds'].max()
        future_dates = pd.date_range(
            start=last_date + timedelta(days=1),
            periods=months*30,
            freq='D'
        )
        
        predictions = []
        base_value = self.model['mean']
        trend = self.model['trend']
        
        for i, date_val in enumerate(future_dates):
            month = date_val.month
            seasonal_factor = self.model['seasonal'].get(month, 1.0) / self.model['mean']
            
            predicted_value = (base_value + trend * i) * seasonal_factor
            predictions.append({
                'ds': date_val,
                'yhat': predicted_value,
                'yhat_lower': predicted_value * 0.8,
                'yhat_upper': predicted_value * 1.2
            })
        
        return pd.DataFrame(predictions)
    
    def _detect_trend(self, values: np.ndarray) -> str:
        """Detect if emissions are increasing, decreasing, or stable"""
        
        if len(values) < 2:
            return "stable"
        
        # Calculate trend using linear regression
        x = np.arange(len(values))
        coeffs = np.polyfit(x, values, 1)
        slope = coeffs[0]
        
        # Threshold is 5% change over the period
        threshold = np.mean(values) * 0.05 / len(values)
        
        if slope > threshold:
            return "increasing"
        elif slope < -threshold:
            return "decreasing"
        else:
            return "stable"
    
    def _identify_seasonal_patterns(self) -> List[str]:
        """Identify seasonal patterns in data"""
        
        patterns = []
        
        if self.training_data is not None and len(self.training_data) > 12:
            # Check for yearly patterns
            monthly_avg = self.training_data.groupby(
                pd.to_datetime(self.training_data['ds']).dt.month
            )['y'].mean()
            
            max_month = monthly_avg.idxmax()
            min_month = monthly_avg.idxmin()
            
            month_names = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }
            
            patterns.append(f"Peak emissions in {month_names.get(max_month, 'Unknown')}")
            patterns.append(f"Lowest emissions in {month_names.get(min_month, 'Unknown')}")
        
        return patterns


class AnomalyDetector:
    """
    Detects anomalies and unusual patterns in emission data
    """
    
    def __init__(self):
        self.model = IsolationForest(
            contamination=0.1,  # Expected proportion of outliers
            random_state=42
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
    
    def fit(self, data_points: List[EmissionDataPoint]):
        """
        Fit the anomaly detection model
        
        Args:
            data_points: Historical emission data points
        """
        
        features = self._extract_features(data_points)
        
        if len(features) < 10:
            logger.warning("Not enough data for anomaly detection")
            return
        
        features_scaled = self.scaler.fit_transform(features)
        self.model.fit(features_scaled)
        self.is_fitted = True
        
        logger.info("Anomaly detection model fitted")
    
    def _extract_features(
        self,
        data_points: List[EmissionDataPoint]
    ) -> np.ndarray:
        """Extract features for anomaly detection"""
        
        features = []
        for dp in data_points:
            if dp.co2_emissions:
                features.append([
                    dp.co2_emissions,
                    dp.amount,
                    dp.date.weekday(),
                    dp.date.month
                ])
        
        return np.array(features)
    
    def detect_anomalies(
        self,
        data_points: List[EmissionDataPoint]
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in emission data
        
        Args:
            data_points: Data points to check for anomalies
            
        Returns:
            List of detected anomalies with details
        """
        
        if not self.is_fitted:
            raise ValueError("Model must be fitted before detecting anomalies")
        
        features = self._extract_features(data_points)
        features_scaled = self.scaler.transform(features)
        
        # Predict anomalies (-1 for anomalies, 1 for normal)
        predictions = self.model.predict(features_scaled)
        scores = self.model.score_samples(features_scaled)
        
        anomalies = []
        for i, (dp, pred, score) in enumerate(zip(data_points, predictions, scores)):
            if pred == -1:  # Anomaly detected
                anomalies.append({
                    'date': dp.date.isoformat(),
                    'activity_type': dp.activity_type,
                    'emissions': dp.co2_emissions,
                    'anomaly_score': float(score),
                    'description': f"Unusual {dp.activity_type} emissions detected",
                    'severity': 'high' if score < -0.5 else 'medium'
                })
        
        logger.info(f"Detected {len(anomalies)} anomalies in {len(data_points)} data points")
        
        return anomalies


class RecommendationEngine:
    """
    Generates AI-powered recommendations for emission reduction
    """
    
    def __init__(self):
        self.recommendations_db = self._load_recommendations_database()
    
    def _load_recommendations_database(self) -> Dict:
        """Load database of reduction recommendations"""
        
        return {
            ActivityType.ELECTRICITY: [
                {
                    'title': 'Switch to Renewable Energy Contract',
                    'description': 'Switch to a 100% renewable energy contract from your electricity provider',
                    'reduction_percentage': 90,
                    'cost_impact': 'low',
                    'difficulty': 'easy',
                    'implementation_weeks': 2
                },
                {
                    'title': 'Install Solar Panels',
                    'description': 'Install rooftop solar panels to generate renewable electricity on-site',
                    'reduction_percentage': 60,
                    'cost_impact': 'high',
                    'difficulty': 'hard',
                    'implementation_weeks': 12
                },
                {
                    'title': 'Upgrade to LED Lighting',
                    'description': 'Replace all traditional lighting with energy-efficient LED lights',
                    'reduction_percentage': 10,
                    'cost_impact': 'medium',
                    'difficulty': 'easy',
                    'implementation_weeks': 4
                }
            ],
            ActivityType.NATURAL_GAS: [
                {
                    'title': 'Improve Building Insulation',
                    'description': 'Upgrade building insulation to reduce heating requirements',
                    'reduction_percentage': 30,
                    'cost_impact': 'medium',
                    'difficulty': 'medium',
                    'implementation_weeks': 8
                },
                {
                    'title': 'Install Heat Pump',
                    'description': 'Replace gas heating with electric heat pump system',
                    'reduction_percentage': 70,
                    'cost_impact': 'high',
                    'difficulty': 'hard',
                    'implementation_weeks': 10
                }
            ],
            ActivityType.TRANSPORT_FREIGHT: [
                {
                    'title': 'Optimize Delivery Routes',
                    'description': 'Use route optimization software to minimize travel distances',
                    'reduction_percentage': 15,
                    'cost_impact': 'low',
                    'difficulty': 'easy',
                    'implementation_weeks': 2
                },
                {
                    'title': 'Switch to Electric Vehicles',
                    'description': 'Replace diesel vehicles with electric alternatives',
                    'reduction_percentage': 80,
                    'cost_impact': 'high',
                    'difficulty': 'medium',
                    'implementation_weeks': 24
                }
            ]
        }
    
    def generate_recommendations(
        self,
        emissions_summary: Dict[str, float],
        company_id: str,
        budget: Optional[float] = None
    ) -> List[ReductionRecommendation]:
        """
        Generate personalized reduction recommendations
        
        Args:
            emissions_summary: Dictionary of emissions by activity type
            company_id: Company identifier
            budget: Available budget for implementations
            
        Returns:
            List of ReductionRecommendation objects
        """
        
        recommendations = []
        
        # Sort activities by emission amount
        sorted_activities = sorted(
            emissions_summary.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for activity_str, current_emissions in sorted_activities[:5]:  # Top 5 activities
            try:
                activity_type = ActivityType(activity_str)
            except ValueError:
                continue
            
            if activity_type not in self.recommendations_db:
                continue
            
            for rec_template in self.recommendations_db[activity_type]:
                reduction_amount = current_emissions * (rec_template['reduction_percentage'] / 100)
                
                recommendation = ReductionRecommendation(
                    company_id=company_id,
                    recommendation_id=f"{company_id}_{activity_str}_{rec_template['title'][:20]}",
                    activity_type=activity_type,
                    current_emissions=current_emissions,
                    title=rec_template['title'],
                    description=rec_template['description'],
                    implementation_steps=self._generate_implementation_steps(rec_template),
                    estimated_reduction=reduction_amount,
                    reduction_percentage=rec_template['reduction_percentage'],
                    difficulty_level=rec_template['difficulty'],
                    priority='high' if reduction_amount > 10000 else 'medium' if reduction_amount > 1000 else 'low',
                    implementation_time_weeks=rec_template['implementation_weeks']
                )
                
                recommendations.append(recommendation)
        
        # Sort by impact (high reduction first)
        recommendations.sort(key=lambda x: x.estimated_reduction, reverse=True)
        
        logger.info(f"Generated {len(recommendations)} recommendations")
        
        return recommendations
    
    def _generate_implementation_steps(self, template: Dict) -> List[str]:
        """Generate implementation steps based on template"""
        
        if template['difficulty'] == 'easy':
            return [
                "Contact relevant service providers for quotes",
                "Review and approve implementation plan",
                "Schedule implementation",
                "Monitor results and verify impact"
            ]
        elif template['difficulty'] == 'medium':
            return [
                "Conduct feasibility study",
                "Obtain multiple quotes from vendors",
                "Secure budget approval",
                "Plan implementation timeline",
                "Execute implementation",
                "Measure and report results"
            ]
        else:  # hard
            return [
                "Commission detailed technical assessment",
                "Develop comprehensive business case",
                "Secure executive and board approval",
                "Run competitive tender process",
                "Appoint project management team",
                "Execute phased implementation",
                "Conduct ongoing monitoring and optimization"
            ]
