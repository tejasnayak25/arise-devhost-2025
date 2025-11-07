
"""
Carbon footprint calculation engine
Implements GHG Protocol standards and uses region-specific emission factors
"""

import yaml
import logging
from typing import Dict, List, Optional
from datetime import date, datetime
from pathlib import Path

from models.emission_data import (
    EmissionDataPoint,
    EmissionSummary,
    ActivityType,
    EmissionScope,
    ComplianceStatus
)

logger = logging.getLogger(__name__)


class EmissionFactorDatabase:
    """
    Database of emission factors for different activities and regions
    Based on IPCC, EPA, and European Environment Agency data
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.emission_factors = self._load_default_factors()
        
        if config_path and Path(config_path).exists():
            self._load_custom_factors(config_path)
    
    def _load_default_factors(self) -> Dict:
        """Load default emission factors"""
        
        return {
            'electricity': {
                # kg CO2e per kWh
                'SE': 0.013,  # Sweden - very low (nuclear + hydro)
                'NO': 0.018,  # Norway - mostly hydro
                'DK': 0.167,  # Denmark - mixed
                'FI': 0.093,  # Finland - nuclear + renewable
                'default': 0.500  # EU average
            },
            'natural_gas': {
                # kg CO2e per m³
                'default': 2.03
            },
            'diesel': {
                # kg CO2e per liter
                'default': 2.68
            },
            'petrol': {
                # kg CO2e per liter
                'default': 2.31
            },
            'heating_oil': {
                # kg CO2e per liter
                'default': 2.96
            },
            'lpg': {
                # kg CO2e per kg
                'default': 3.00
            },
            'transport_freight': {
                # kg CO2e per ton-km
                'truck': 0.097,
                'rail': 0.022,
                'ship': 0.011,
                'air': 0.602,
                'default': 0.097
            },
            'transport_business_travel': {
                # kg CO2e per passenger-km
                'car': 0.171,
                'bus': 0.089,
                'train': 0.041,
                'flight_domestic': 0.255,
                'flight_international': 0.195,
                'default': 0.171
            },
            'waste_disposal': {
                # kg CO2e per kg
                'landfill': 0.500,
                'incineration': 0.020,
                'recycling': -0.150,  # Carbon credit
                'composting': 0.010,
                'default': 0.500
            },
            'water_consumption': {
                # kg CO2e per m³
                'default': 0.344
            },
            'refrigerants': {
                # kg CO2e per kg leaked
                'R-134a': 1430,
                'R-410A': 2088,
                'R-32': 675,
                'default': 1430
            }
        }
    
    def _load_custom_factors(self, config_path: str):
        """Load custom emission factors from config"""
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if 'emission_factors' in config:
                # Merge custom factors with defaults
                for activity, factors in config['emission_factors'].items():
                    if activity in self.emission_factors:
                        self.emission_factors[activity].update(factors)
                    else:
                        self.emission_factors[activity] = factors
            
            logger.info(f"Loaded custom emission factors from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load custom factors: {e}")
    
    def get_emission_factor(
        self,
        activity_type: ActivityType,
        country_code: str = 'default',
        sub_type: Optional[str] = None
    ) -> float:
        """
        Get emission factor for an activity
        
        Args:
            activity_type: Type of activity
            country_code: ISO country code
            sub_type: Sub-type for specific activities (e.g., 'truck' for freight)
            
        Returns:
            Emission factor in kg CO2e per unit
        """
        
        activity_key = activity_type.value if isinstance(activity_type, ActivityType) else activity_type
        
        if activity_key not in self.emission_factors:
            logger.warning(f"No emission factor for {activity_type}, using default")
            return 1.0  # Default fallback
        
        factors = self.emission_factors[activity_key]
        
        # Handle sub-types
        if sub_type and sub_type in factors:
            return factors[sub_type]
        
        # Handle country-specific factors
        if country_code in factors:
            return factors[country_code]
        
        # Return default
        if 'default' in factors:
            return factors['default']
        
        return 1.0


class CarbonCalculator:
    """
    Main carbon footprint calculator
    Implements GHG Protocol calculation methodology
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.emission_db = EmissionFactorDatabase(config_path)
        self.thresholds = self._load_thresholds(config_path)
    
    def _load_thresholds(self, config_path: Optional[str]) -> Dict:
        """Load compliance thresholds"""
        
        default_thresholds = {
            'scope_1_warning': 100000,  # kg CO2e per year
            'scope_2_warning': 50000,
            'scope_3_warning': 200000
        }
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                if 'compliance' in config and 'thresholds' in config['compliance']:
                    return config['compliance']['thresholds']
            except Exception as e:
                logger.warning(f"Failed to load thresholds: {e}")
        
        return default_thresholds
    
    def calculate_emissions(
        self,
        activity_type: ActivityType,
        amount: float,
        unit: str,
        country_code: str = 'SE',
        sub_type: Optional[str] = None
    ) -> float:
        """
        Calculate CO2 emissions for an activity
        
        Args:
            activity_type: Type of activity
            amount: Amount of activity
            unit: Unit of measurement
            country_code: ISO country code
            sub_type: Sub-type for specific activities
            
        Returns:
            CO2 emissions in kg CO2e
        """
        
        emission_factor = self.emission_db.get_emission_factor(
            activity_type,
            country_code,
            sub_type
        )
        
        # Unit conversion if needed
        converted_amount = self._convert_units(amount, unit, activity_type)
        
        # Calculate emissions
        emissions = converted_amount * emission_factor
        
        activity_name = activity_type.value if isinstance(activity_type, ActivityType) else activity_type
        logger.debug(
            f"Calculated {emissions:.2f} kg CO2e for {amount} {unit} "
            f"of {activity_name} (factor: {emission_factor})"
        )
        
        return emissions
    
    def _convert_units(
        self,
        amount: float,
        unit: str,
        activity_type: ActivityType
    ) -> float:
        """Convert units to standard format for emission calculation"""
        
        unit_lower = unit.lower()
        
        # Energy conversions
        if unit_lower in ['kwh', 'kilowatt-hour']:
            return amount
        elif unit_lower in ['mwh', 'megawatt-hour']:
            return amount * 1000
        elif unit_lower in ['gwh', 'gigawatt-hour']:
            return amount * 1000000
        
        # Volume conversions
        elif unit_lower in ['m3', 'm³', 'cubic meter']:
            return amount
        elif unit_lower in ['l', 'liter', 'litre']:
            return amount / 1000  # Convert to m³ where applicable
        
        # Mass conversions
        elif unit_lower in ['kg', 'kilogram']:
            return amount
        elif unit_lower in ['t', 'ton', 'tonne']:
            return amount * 1000
        
        # Distance conversions
        elif unit_lower in ['km', 'kilometer']:
            return amount
        elif unit_lower in ['m', 'meter']:
            return amount / 1000
        
        # If no conversion needed or unknown unit, return as is
        return amount
    
    def calculate_for_data_point(
        self,
        data_point: EmissionDataPoint
    ) -> EmissionDataPoint:
        """
        Calculate emissions for a data point and update it
        
        Args:
            data_point: Emission data point
            
        Returns:
            Updated data point with calculated emissions
        """
        
        # Get emission factor if not already set
        if not data_point.emission_factor:
            data_point.emission_factor = self.emission_db.get_emission_factor(
                data_point.activity_type,
                data_point.country_code
            )
        
        # Calculate emissions if not already calculated
        if not data_point.co2_emissions:
            data_point.co2_emissions = self.calculate_emissions(
                data_point.activity_type,
                data_point.amount,
                data_point.unit,
                data_point.country_code
            )
        
        return data_point
    
    def calculate_bulk(
        self,
        data_points: List[EmissionDataPoint]
    ) -> List[EmissionDataPoint]:
        """
        Calculate emissions for multiple data points
        
        Args:
            data_points: List of emission data points
            
        Returns:
            List of updated data points with calculated emissions
        """
        
        for dp in data_points:
            self.calculate_for_data_point(dp)
        
        logger.info(f"Calculated emissions for {len(data_points)} data points")
        return data_points
    
    def generate_summary(
        self,
        data_points: List[EmissionDataPoint],
        company_id: str,
        period_start: date,
        period_end: date,
        previous_period_total: Optional[float] = None
    ) -> EmissionSummary:
        """
        Generate emission summary for a period
        
        Args:
            data_points: List of emission data points
            company_id: Company identifier
            period_start: Start date of period
            period_end: End date of period
            previous_period_total: Total emissions from previous period
            
        Returns:
            EmissionSummary object
        """
        
        # Filter data points for the period and company
        filtered_points = [
            dp for dp in data_points
            if dp.company_id == company_id
            and period_start <= dp.date <= period_end
        ]
        
        # Calculate emissions if not already done
        self.calculate_bulk(filtered_points)
        
        # Aggregate by scope
        scope_1_total = sum(
            dp.co2_emissions for dp in filtered_points
            if dp.scope == EmissionScope.SCOPE_1 and dp.co2_emissions
        )
        
        scope_2_total = sum(
            dp.co2_emissions for dp in filtered_points
            if dp.scope == EmissionScope.SCOPE_2 and dp.co2_emissions
        )
        
        scope_3_total = sum(
            dp.co2_emissions for dp in filtered_points
            if dp.scope == EmissionScope.SCOPE_3 and dp.co2_emissions
        )
        
        total_emissions = scope_1_total + scope_2_total + scope_3_total
        
        # Aggregate by activity type
        emissions_by_activity = {}
        for dp in filtered_points:
            if dp.co2_emissions:
                activity = dp.activity_type if isinstance(dp.activity_type, str) else dp.activity_type.value
                emissions_by_activity[activity] = emissions_by_activity.get(activity, 0) + dp.co2_emissions
        
        # Calculate change percentage
        change_percentage = None
        if previous_period_total and previous_period_total > 0:
            change_percentage = ((total_emissions - previous_period_total) / previous_period_total) * 100
        
        # Determine compliance status
        compliance_status = self._check_compliance_status(
            scope_1_total,
            scope_2_total,
            scope_3_total
        )
        
        # Validation statistics
        verified_count = sum(1 for dp in filtered_points if dp.verified)
        verified_percentage = (verified_count / len(filtered_points) * 100) if filtered_points else 0
        
        return EmissionSummary(
            company_id=company_id,
            period_start=period_start,
            period_end=period_end,
            scope_1_total=scope_1_total,
            scope_2_total=scope_2_total,
            scope_3_total=scope_3_total,
            total_emissions=total_emissions,
            emissions_by_activity=emissions_by_activity,
            previous_period_total=previous_period_total,
            change_percentage=change_percentage,
            compliance_status=compliance_status,
            data_points_count=len(filtered_points),
            verified_data_percentage=verified_percentage
        )
    
    def _check_compliance_status(
        self,
        scope_1: float,
        scope_2: float,
        scope_3: float
    ) -> ComplianceStatus:
        """Check compliance status based on thresholds"""
        
        if (scope_1 > self.thresholds['scope_1_warning'] or
            scope_2 > self.thresholds['scope_2_warning'] or
            scope_3 > self.thresholds['scope_3_warning']):
            return ComplianceStatus.WARNING
        
        return ComplianceStatus.COMPLIANT
    
    def calculate_intensity_metrics(
        self,
        total_emissions: float,
        revenue: Optional[float] = None,
        employees: Optional[int] = None,
        production_volume: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate emission intensity metrics
        
        Args:
            total_emissions: Total CO2 emissions in kg
            revenue: Annual revenue
            employees: Number of employees
            production_volume: Production volume in relevant units
            
        Returns:
            Dictionary of intensity metrics
        """
        
        metrics = {}
        
        if revenue and revenue > 0:
            metrics['emissions_per_revenue'] = total_emissions / revenue
        
        if employees and employees > 0:
            metrics['emissions_per_employee'] = total_emissions / employees
        
        if production_volume and production_volume > 0:
            metrics['emissions_per_unit'] = total_emissions / production_volume
        
        return metrics
