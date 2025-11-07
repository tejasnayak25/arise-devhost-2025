
"""
Data models for emission tracking and ESG reporting
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class DataSource(str, Enum):
    """Types of data sources for emission data"""
    ERP = "erp"
    UTILITY_BILL = "utility_bill"
    ENERGY_METER = "energy_meter"
    INVOICE = "invoice"
    MANUAL_ENTRY = "manual_entry"
    IOT_SENSOR = "iot_sensor"


class EmissionScope(str, Enum):
    """GHG Protocol emission scopes"""
    SCOPE_1 = "scope_1"  # Direct emissions from owned/controlled sources
    SCOPE_2 = "scope_2"  # Indirect emissions from purchased energy
    SCOPE_3 = "scope_3"  # All other indirect emissions in value chain


class ActivityType(str, Enum):
    """Types of activities that generate emissions"""
    ELECTRICITY = "electricity"
    NATURAL_GAS = "natural_gas"
    HEATING_OIL = "heating_oil"
    DIESEL = "diesel"
    PETROL = "petrol"
    TRANSPORT_FREIGHT = "transport_freight"
    TRANSPORT_BUSINESS_TRAVEL = "transport_business_travel"
    WASTE_DISPOSAL = "waste_disposal"
    WATER_CONSUMPTION = "water_consumption"
    REFRIGERANTS = "refrigerants"
    OTHER = "other"


class ComplianceStatus(str, Enum):
    """Compliance status levels"""
    COMPLIANT = "compliant"
    WARNING = "warning"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"


class EmissionDataPoint(BaseModel):
    """Individual emission data point"""
    
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    date: date
    company_id: str
    facility_id: Optional[str] = None
    
    # Activity information
    activity_type: ActivityType
    activity_description: Optional[str] = None
    scope: EmissionScope
    
    # Measurement data
    amount: float = Field(gt=0, description="Amount of activity (e.g., kWh, liters, kg)")
    unit: str = Field(description="Unit of measurement")
    
    # Emission calculation
    emission_factor: Optional[float] = Field(None, description="kg CO2e per unit")
    co2_emissions: Optional[float] = Field(None, description="Total CO2 equivalent emissions in kg")
    
    # Data source
    source_type: DataSource
    source_reference: Optional[str] = Field(None, description="Reference to original document/system")
    
    # Geographic info
    country_code: str = Field(default="SE", description="ISO country code")
    region: Optional[str] = None
    
    # Metadata
    verified: bool = False
    verification_date: Optional[date] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


class CompanyProfile(BaseModel):
    """Company profile for ESG reporting"""
    
    company_id: str
    company_name: str
    org_number: str
    
    # Industry classification
    industry_sector: str
    sub_sector: Optional[str] = None
    
    # Location
    country: str
    address: str
    
    # Company size
    employee_count: Optional[int] = None
    annual_revenue: Optional[float] = None
    
    # ESG settings
    reporting_frequency: str = "quarterly"
    fiscal_year_start: date
    
    # Compliance requirements
    csrd_applicable: bool = True
    eu_taxonomy_applicable: bool = True
    
    # Contact
    contact_person: str
    contact_email: str
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class EmissionSummary(BaseModel):
    """Summary of emissions for a period"""
    
    company_id: str
    period_start: date
    period_end: date
    
    # Scope totals (kg CO2e)
    scope_1_total: float = 0.0
    scope_2_total: float = 0.0
    scope_3_total: float = 0.0
    total_emissions: float = 0.0
    
    # Activity breakdown
    emissions_by_activity: Dict[str, float] = Field(default_factory=dict)
    
    # Comparison
    previous_period_total: Optional[float] = None
    change_percentage: Optional[float] = None
    
    # Compliance
    compliance_status: ComplianceStatus
    compliance_notes: List[str] = Field(default_factory=list)
    
    # Statistics
    data_points_count: int = 0
    verified_data_percentage: float = 0.0
    
    generated_at: datetime = Field(default_factory=datetime.now)


class ComplianceCheck(BaseModel):
    """Results of a compliance check"""
    
    company_id: str
    check_date: date
    reporting_period_start: date
    reporting_period_end: date
    
    # CSRD Compliance
    csrd_compliant: bool
    csrd_issues: List[str] = Field(default_factory=list)
    
    # EU Taxonomy Compliance
    taxonomy_compliant: bool
    taxonomy_issues: List[str] = Field(default_factory=list)
    
    # Emission thresholds
    scope_1_within_limits: bool
    scope_2_within_limits: bool
    scope_3_within_limits: bool
    
    # Overall status
    overall_status: ComplianceStatus
    risk_level: str  # low, medium, high, critical
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list)
    action_required: bool = False
    deadline: Optional[date] = None
    
    # Audit trail
    checked_by: str
    verification_method: str


class PredictionResult(BaseModel):
    """ML prediction results for emissions"""
    
    company_id: str
    prediction_date: date
    forecast_period_start: date
    forecast_period_end: date
    
    # Predictions
    predicted_scope_1: float
    predicted_scope_2: float
    predicted_scope_3: float
    predicted_total: float
    
    # Confidence intervals
    confidence_interval_lower: float
    confidence_interval_upper: float
    confidence_level: float = 0.95
    
    # Model info
    model_type: str
    model_accuracy: Optional[float] = None
    training_data_points: int
    
    # Anomalies detected
    anomalies_detected: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Insights
    trend: str  # increasing, decreasing, stable
    seasonal_patterns: List[str] = Field(default_factory=list)
    
    generated_at: datetime = Field(default_factory=datetime.now)


class ReductionRecommendation(BaseModel):
    """AI-generated recommendation for emission reduction"""
    
    company_id: str
    recommendation_id: str
    
    # Target
    activity_type: ActivityType
    current_emissions: float  # kg CO2e
    
    # Recommendation
    title: str
    description: str
    implementation_steps: List[str]
    
    # Impact
    estimated_reduction: float  # kg CO2e
    reduction_percentage: float
    
    # Implementation
    cost_estimate: Optional[float] = None
    payback_period_months: Optional[int] = None
    difficulty_level: str  # easy, medium, hard
    priority: str  # low, medium, high
    
    # Timeline
    implementation_time_weeks: Optional[int] = None
    
    # Status
    status: str = "pending"  # pending, in_progress, completed, rejected
    
    created_at: datetime = Field(default_factory=datetime.now)
