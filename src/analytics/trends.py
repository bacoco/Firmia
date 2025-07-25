"""Trend analysis module for identifying business patterns."""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import statistics

from structlog import get_logger

from ..cache import get_cache_manager

logger = get_logger(__name__)


class TrendDirection(str, Enum):
    """Trend direction indicators."""
    STRONG_UP = "strong_up"
    UP = "up"
    STABLE = "stable"
    DOWN = "down"
    STRONG_DOWN = "strong_down"
    VOLATILE = "volatile"


@dataclass
class TrendPoint:
    """Single point in a trend series."""
    timestamp: datetime
    value: float
    label: Optional[str] = None


@dataclass
class TrendAnalysis:
    """Complete trend analysis result."""
    metric: str
    direction: TrendDirection
    change_percent: float
    volatility: float
    data_points: List[TrendPoint]
    forecast: Optional[Dict[str, Any]] = None
    seasonality: Optional[Dict[str, Any]] = None
    anomalies: List[Dict[str, Any]] = None


class TrendAnalyzer:
    """Analyzes trends in business data."""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.logger = logger.bind(component="trend_analyzer")
    
    async def analyze_sector_trends(
        self,
        naf_code: str,
        metrics: List[str] = ["company_count", "avg_revenue", "avg_employees"],
        period_months: int = 24
    ) -> Dict[str, TrendAnalysis]:
        """Analyze multiple metrics for a sector over time."""
        results = {}
        
        for metric in metrics:
            analysis = await self._analyze_single_metric(
                naf_code=naf_code,
                metric=metric,
                period_months=period_months
            )
            results[metric] = analysis
        
        return results
    
    async def _analyze_single_metric(
        self,
        naf_code: str,
        metric: str,
        period_months: int
    ) -> TrendAnalysis:
        """Analyze a single metric over time."""
        # Get historical data
        query = self._build_trend_query(metric, period_months)
        params = [naf_code, period_months]
        
        data = await self.cache_manager.query_analytics(query, params)
        
        if not data:
            return TrendAnalysis(
                metric=metric,
                direction=TrendDirection.STABLE,
                change_percent=0.0,
                volatility=0.0,
                data_points=[]
            )
        
        # Convert to TrendPoints
        data_points = [
            TrendPoint(
                timestamp=datetime.fromisoformat(row["period"]),
                value=float(row[metric]),
                label=row.get("label")
            )
            for row in data
        ]
        
        # Calculate trend metrics
        direction = self._calculate_direction(data_points)
        change_percent = self._calculate_change_percent(data_points)
        volatility = self._calculate_volatility(data_points)
        
        # Detect anomalies
        anomalies = self._detect_anomalies(data_points)
        
        # Simple forecast
        forecast = self._generate_forecast(data_points) if len(data_points) >= 6 else None
        
        # Detect seasonality
        seasonality = self._detect_seasonality(data_points) if len(data_points) >= 12 else None
        
        return TrendAnalysis(
            metric=metric,
            direction=direction,
            change_percent=change_percent,
            volatility=volatility,
            data_points=data_points,
            forecast=forecast,
            seasonality=seasonality,
            anomalies=anomalies
        )
    
    def _build_trend_query(self, metric: str, period_months: int) -> str:
        """Build SQL query for trend data."""
        if metric == "company_count":
            return """
            SELECT 
                DATE_TRUNC('month', creation_date) as period,
                COUNT(*) as company_count
            FROM companies
            WHERE naf_code = ?
                AND creation_date >= CURRENT_DATE - INTERVAL '? months'
            GROUP BY DATE_TRUNC('month', creation_date)
            ORDER BY period
            """
        
        elif metric == "avg_revenue":
            return """
            SELECT 
                DATE_TRUNC('month', last_update) as period,
                AVG(revenue) as avg_revenue
            FROM companies
            WHERE naf_code = ?
                AND last_update >= CURRENT_DATE - INTERVAL '? months'
                AND revenue > 0
            GROUP BY DATE_TRUNC('month', last_update)
            ORDER BY period
            """
        
        elif metric == "avg_employees":
            return """
            SELECT 
                DATE_TRUNC('month', last_update) as period,
                AVG(CAST(employee_count AS INTEGER)) as avg_employees
            FROM companies
            WHERE naf_code = ?
                AND last_update >= CURRENT_DATE - INTERVAL '? months'
                AND employee_count IS NOT NULL
            GROUP BY DATE_TRUNC('month', last_update)
            ORDER BY period
            """
        
        else:
            raise ValueError(f"Unknown metric: {metric}")
    
    def _calculate_direction(self, data_points: List[TrendPoint]) -> TrendDirection:
        """Calculate overall trend direction."""
        if len(data_points) < 2:
            return TrendDirection.STABLE
        
        # Simple linear regression
        x_values = list(range(len(data_points)))
        y_values = [p.value for p in data_points]
        
        # Calculate slope
        n = len(x_values)
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            return TrendDirection.STABLE
        
        slope = numerator / denominator
        
        # Normalize slope by average value
        normalized_slope = slope / (y_mean if y_mean != 0 else 1) * 100
        
        # Check volatility
        volatility = self._calculate_volatility(data_points)
        
        if volatility > 50:  # High volatility
            return TrendDirection.VOLATILE
        
        # Determine direction based on normalized slope
        if normalized_slope > 10:
            return TrendDirection.STRONG_UP
        elif normalized_slope > 2:
            return TrendDirection.UP
        elif normalized_slope < -10:
            return TrendDirection.STRONG_DOWN
        elif normalized_slope < -2:
            return TrendDirection.DOWN
        else:
            return TrendDirection.STABLE
    
    def _calculate_change_percent(self, data_points: List[TrendPoint]) -> float:
        """Calculate percentage change from start to end."""
        if len(data_points) < 2:
            return 0.0
        
        start_value = data_points[0].value
        end_value = data_points[-1].value
        
        if start_value == 0:
            return 0.0
        
        return ((end_value - start_value) / start_value) * 100
    
    def _calculate_volatility(self, data_points: List[TrendPoint]) -> float:
        """Calculate volatility as coefficient of variation."""
        if len(data_points) < 2:
            return 0.0
        
        values = [p.value for p in data_points]
        mean = statistics.mean(values)
        
        if mean == 0:
            return 0.0
        
        stdev = statistics.stdev(values)
        return (stdev / mean) * 100
    
    def _detect_anomalies(self, data_points: List[TrendPoint]) -> List[Dict[str, Any]]:
        """Detect anomalous values using z-score method."""
        if len(data_points) < 3:
            return []
        
        values = [p.value for p in data_points]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        
        anomalies = []
        
        if stdev > 0:
            for i, point in enumerate(data_points):
                z_score = abs((point.value - mean) / stdev)
                if z_score > 2:  # More than 2 standard deviations
                    anomalies.append({
                        "index": i,
                        "timestamp": point.timestamp,
                        "value": point.value,
                        "z_score": z_score,
                        "severity": "high" if z_score > 3 else "medium"
                    })
        
        return anomalies
    
    def _generate_forecast(self, data_points: List[TrendPoint]) -> Dict[str, Any]:
        """Generate simple linear forecast."""
        if len(data_points) < 3:
            return None
        
        # Use last 6 points for forecast
        recent_points = data_points[-6:]
        
        # Simple linear extrapolation
        x_values = list(range(len(recent_points)))
        y_values = [p.value for p in recent_points]
        
        # Calculate trend line
        n = len(x_values)
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        intercept = y_mean - slope * x_mean
        
        # Forecast next 3 periods
        forecast_values = []
        last_timestamp = recent_points[-1].timestamp
        
        for i in range(1, 4):
            forecast_x = len(recent_points) + i - 1
            forecast_y = slope * forecast_x + intercept
            forecast_timestamp = last_timestamp + timedelta(days=30 * i)  # Approximate monthly
            
            forecast_values.append({
                "timestamp": forecast_timestamp,
                "value": max(0, forecast_y),  # Ensure non-negative
                "confidence": 0.7 - (i * 0.1)  # Decreasing confidence
            })
        
        return {
            "method": "linear_extrapolation",
            "forecasts": forecast_values,
            "trend_slope": slope,
            "r_squared": self._calculate_r_squared(x_values, y_values, slope, intercept)
        }
    
    def _calculate_r_squared(
        self,
        x_values: List[float],
        y_values: List[float],
        slope: float,
        intercept: float
    ) -> float:
        """Calculate R-squared for trend line fit."""
        y_mean = sum(y_values) / len(y_values)
        
        # Total sum of squares
        ss_tot = sum((y - y_mean) ** 2 for y in y_values)
        
        # Residual sum of squares
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))
        
        if ss_tot == 0:
            return 0.0
        
        return 1 - (ss_res / ss_tot)
    
    def _detect_seasonality(self, data_points: List[TrendPoint]) -> Dict[str, Any]:
        """Detect seasonal patterns in data."""
        if len(data_points) < 12:
            return None
        
        # Group by month
        monthly_values = {}
        for point in data_points:
            month = point.timestamp.month
            if month not in monthly_values:
                monthly_values[month] = []
            monthly_values[month].append(point.value)
        
        # Calculate average for each month
        monthly_averages = {}
        for month, values in monthly_values.items():
            monthly_averages[month] = statistics.mean(values)
        
        # Calculate seasonal indices
        overall_mean = statistics.mean([p.value for p in data_points])
        seasonal_indices = {}
        
        if overall_mean > 0:
            for month, avg in monthly_averages.items():
                seasonal_indices[month] = (avg / overall_mean) * 100
        
        # Detect if there's significant seasonality
        index_values = list(seasonal_indices.values())
        seasonality_strength = max(index_values) - min(index_values) if index_values else 0
        
        return {
            "has_seasonality": seasonality_strength > 20,  # 20% variation threshold
            "strength": seasonality_strength,
            "seasonal_indices": seasonal_indices,
            "peak_months": [m for m, idx in seasonal_indices.items() if idx > 110],
            "low_months": [m for m, idx in seasonal_indices.items() if idx < 90]
        }
    
    async def identify_emerging_sectors(
        self,
        min_growth_rate: float = 20.0,
        min_companies: int = 10
    ) -> List[Dict[str, Any]]:
        """Identify rapidly growing sectors."""
        query = """
        WITH sector_growth AS (
            SELECT 
                naf_code,
                COUNT(*) as total_companies,
                SUM(CASE WHEN creation_date > CURRENT_DATE - INTERVAL '1 year' THEN 1 ELSE 0 END) as new_companies,
                SUM(CASE WHEN creation_date > CURRENT_DATE - INTERVAL '2 years' 
                         AND creation_date <= CURRENT_DATE - INTERVAL '1 year' THEN 1 ELSE 0 END) as prev_year_companies
            FROM companies
            WHERE is_active = true
            GROUP BY naf_code
            HAVING COUNT(*) >= ?
        )
        SELECT 
            naf_code,
            total_companies,
            new_companies,
            CASE 
                WHEN prev_year_companies > 0 
                THEN ((new_companies::FLOAT - prev_year_companies) / prev_year_companies) * 100
                ELSE 100.0
            END as growth_rate
        FROM sector_growth
        WHERE new_companies > prev_year_companies
        ORDER BY growth_rate DESC
        LIMIT 20
        """
        
        results = await self.cache_manager.query_analytics(query, [min_companies])
        
        # Filter by minimum growth rate
        emerging_sectors = [
            r for r in results 
            if r["growth_rate"] >= min_growth_rate
        ]
        
        return emerging_sectors