"""Company health score calculation module."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from structlog import get_logger

from ..api import BODACCAPI, APIEntrepriseAPI
from ..models.company import Company

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Overall health status categories."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthMetric:
    """Individual health metric."""
    name: str
    value: float  # 0-100
    weight: float  # Weight in overall score
    status: HealthStatus
    details: Dict[str, Any]
    last_updated: datetime


@dataclass
class HealthScore:
    """Company health score result."""
    siren: str
    overall_score: float  # 0-100
    overall_status: HealthStatus
    metrics: List[HealthMetric]
    risk_factors: List[str]
    positive_factors: List[str]
    recommendations: List[str]
    calculated_at: datetime
    data_sources: List[str]


class HealthScoreCalculator:
    """Calculates comprehensive company health scores."""
    
    def __init__(self):
        self.bodacc_api = BODACCAPI()
        self.api_entreprise = APIEntrepriseAPI()
        self.logger = logger.bind(component="health_score")
        
        # Metric weights (must sum to 1.0)
        self.weights = {
            "financial_stability": 0.30,
            "legal_status": 0.25,
            "activity_level": 0.20,
            "growth_trend": 0.15,
            "compliance": 0.10
        }
    
    async def calculate_health_score(
        self,
        company: Company,
        include_predictions: bool = False
    ) -> HealthScore:
        """Calculate comprehensive health score for a company."""
        self.logger.info("calculating_health_score", siren=company.siren)
        
        metrics = []
        risk_factors = []
        positive_factors = []
        recommendations = []
        data_sources = ["company_profile"]
        
        # 1. Financial Stability
        financial_metric = await self._assess_financial_stability(company)
        metrics.append(financial_metric)
        
        # 2. Legal Status
        legal_metric = await self._assess_legal_status(company)
        metrics.append(legal_metric)
        data_sources.append("bodacc")
        
        # 3. Activity Level
        activity_metric = self._assess_activity_level(company)
        metrics.append(activity_metric)
        
        # 4. Growth Trend
        growth_metric = self._assess_growth_trend(company)
        metrics.append(growth_metric)
        
        # 5. Compliance
        compliance_metric = self._assess_compliance(company)
        metrics.append(compliance_metric)
        
        # Calculate overall score
        overall_score = sum(
            metric.value * self.weights[metric.name]
            for metric in metrics
        )
        
        # Determine overall status
        overall_status = self._get_status_from_score(overall_score)
        
        # Analyze risk and positive factors
        for metric in metrics:
            if metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                risk_factors.extend(metric.details.get("risks", []))
            if metric.status in [HealthStatus.EXCELLENT, HealthStatus.GOOD]:
                positive_factors.extend(metric.details.get("strengths", []))
        
        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, company)
        
        # Add predictions if requested
        if include_predictions:
            predictions = await self._generate_predictions(company, metrics)
            if predictions:
                recommendations.append(f"Predicted trend: {predictions}")
        
        return HealthScore(
            siren=company.siren,
            overall_score=round(overall_score, 1),
            overall_status=overall_status,
            metrics=metrics,
            risk_factors=risk_factors,
            positive_factors=positive_factors,
            recommendations=recommendations,
            calculated_at=datetime.utcnow(),
            data_sources=data_sources
        )
    
    async def _assess_financial_stability(self, company: Company) -> HealthMetric:
        """Assess financial stability based on available data."""
        score = 50.0  # Base score
        details = {"risks": [], "strengths": []}
        
        # Check capital
        if company.financials and company.financials.capital:
            capital = company.financials.capital
            if capital > 100000:
                score += 20
                details["strengths"].append(f"Strong capital: {capital:,.0f}€")
            elif capital > 10000:
                score += 10
                details["strengths"].append(f"Adequate capital: {capital:,.0f}€")
            elif capital < 1000:
                score -= 20
                details["risks"].append(f"Low capital: {capital:,.0f}€")
        
        # Check for recent financial difficulties (BODACC)
        financial_health = await self.bodacc_api.check_financial_health(company.siren)
        
        if financial_health["has_collective_procedures"]:
            score -= 30
            details["risks"].append("Has collective procedures")
            
            if financial_health["recent_collective_procedures"]:
                score -= 20
                details["risks"].append("Recent bankruptcy/liquidation procedures")
        
        # Check employee count (proxy for size/stability)
        if company.employee_range:
            if "50" in company.employee_range or "100" in company.employee_range:
                score += 10
                details["strengths"].append(f"Significant workforce: {company.employee_range}")
            elif "0" in company.employee_range or "aucun" in company.employee_range.lower():
                score -= 10
                details["risks"].append("No employees reported")
        
        # Ensure score is within bounds
        score = max(0, min(100, score))
        
        return HealthMetric(
            name="financial_stability",
            value=score,
            weight=self.weights["financial_stability"],
            status=self._get_status_from_score(score),
            details=details,
            last_updated=datetime.utcnow()
        )
    
    async def _assess_legal_status(self, company: Company) -> HealthMetric:
        """Assess legal status and compliance."""
        score = 80.0  # Start with good score
        details = {"risks": [], "strengths": []}
        
        # Check if company is active
        if company.is_active:
            details["strengths"].append("Company is active")
        else:
            score -= 50
            details["risks"].append("Company is inactive/ceased")
        
        # Check age of company
        if company.creation_date:
            company_age = (datetime.utcnow() - company.creation_date).days / 365
            if company_age > 10:
                score += 10
                details["strengths"].append(f"Established company: {company_age:.1f} years")
            elif company_age > 3:
                score += 5
                details["strengths"].append(f"Mature company: {company_age:.1f} years")
            elif company_age < 1:
                score -= 10
                details["risks"].append(f"Young company: {company_age:.1f} years")
        
        # Check for legal form stability
        if company.legal_form and company.legal_form.get("code"):
            legal_code = company.legal_form["code"]
            # Stable legal forms (SA, SAS, SARL)
            if legal_code in ["5710", "5499", "5498"]:
                score += 5
                details["strengths"].append(f"Stable legal form: {company.legal_form.get('label', legal_code)}")
        
        score = max(0, min(100, score))
        
        return HealthMetric(
            name="legal_status",
            value=score,
            weight=self.weights["legal_status"],
            status=self._get_status_from_score(score),
            details=details,
            last_updated=datetime.utcnow()
        )
    
    def _assess_activity_level(self, company: Company) -> HealthMetric:
        """Assess business activity level."""
        score = 50.0
        details = {"risks": [], "strengths": []}
        
        # Check if headquarters exists
        if company.is_headquarters:
            score += 10
            details["strengths"].append("Has headquarters")
        
        # Check number of establishments
        if company.establishments:
            establishment_count = len(company.establishments)
            if establishment_count > 5:
                score += 20
                details["strengths"].append(f"Multiple establishments: {establishment_count}")
            elif establishment_count > 1:
                score += 10
                details["strengths"].append(f"Has {establishment_count} establishments")
        
        # Check for executives
        if company.executives:
            exec_count = len(company.executives)
            if exec_count > 3:
                score += 10
                details["strengths"].append(f"Strong leadership: {exec_count} executives")
            elif exec_count > 0:
                score += 5
                details["strengths"].append(f"Has {exec_count} executive(s)")
        else:
            score -= 10
            details["risks"].append("No executives listed")
        
        # Check certifications
        if company.certifications:
            cert_count = sum(1 for _, v in company.certifications.dict().items() if v)
            if cert_count > 0:
                score += 10
                details["strengths"].append(f"Has {cert_count} certification(s)")
        
        score = max(0, min(100, score))
        
        return HealthMetric(
            name="activity_level",
            value=score,
            weight=self.weights["activity_level"],
            status=self._get_status_from_score(score),
            details=details,
            last_updated=datetime.utcnow()
        )
    
    def _assess_growth_trend(self, company: Company) -> HealthMetric:
        """Assess growth trends."""
        score = 50.0  # Neutral starting point
        details = {"risks": [], "strengths": [], "neutral": []}
        
        # Without historical data, we use proxies
        
        # Recent creation can indicate growth
        if company.creation_date:
            company_age = (datetime.utcnow() - company.creation_date).days / 365
            if 1 < company_age < 5:
                score += 10
                details["strengths"].append("Growing startup phase")
        
        # Multiple establishments indicate expansion
        if company.establishments and len(company.establishments) > 1:
            score += 15
            details["strengths"].append("Geographic expansion")
        
        # High employee count for age indicates growth
        if company.employee_range and company.creation_date:
            company_age = (datetime.utcnow() - company.creation_date).days / 365
            if company_age < 5 and ("20" in company.employee_range or "50" in company.employee_range):
                score += 20
                details["strengths"].append("Rapid team growth")
        
        # No real trend data available
        if not details["strengths"] and not details["risks"]:
            details["neutral"].append("Limited growth data available")
        
        score = max(0, min(100, score))
        
        return HealthMetric(
            name="growth_trend",
            value=score,
            weight=self.weights["growth_trend"],
            status=self._get_status_from_score(score),
            details=details,
            last_updated=datetime.utcnow()
        )
    
    def _assess_compliance(self, company: Company) -> HealthMetric:
        """Assess regulatory compliance."""
        score = 70.0  # Start with good compliance assumption
        details = {"risks": [], "strengths": []}
        
        # Check if company data is complete
        if company.denomination and company.siren and company.address:
            score += 10
            details["strengths"].append("Complete registration data")
        else:
            score -= 10
            details["risks"].append("Incomplete registration data")
        
        # Check for certifications (indicates compliance awareness)
        if company.certifications:
            if company.certifications.rge:
                score += 10
                details["strengths"].append("RGE certified")
            if company.certifications.qualiopi:
                score += 10
                details["strengths"].append("Qualiopi certified")
        
        # Privacy compliance
        if company.privacy_status == "P":
            # Company has opted for privacy protection - neutral
            details["neutral"] = ["Privacy protection enabled"]
        
        score = max(0, min(100, score))
        
        return HealthMetric(
            name="compliance",
            value=score,
            weight=self.weights["compliance"],
            status=self._get_status_from_score(score),
            details=details,
            last_updated=datetime.utcnow()
        )
    
    def _get_status_from_score(self, score: float) -> HealthStatus:
        """Convert numeric score to status category."""
        if score >= 85:
            return HealthStatus.EXCELLENT
        elif score >= 70:
            return HealthStatus.GOOD
        elif score >= 50:
            return HealthStatus.FAIR
        elif score >= 30:
            return HealthStatus.WARNING
        elif score > 0:
            return HealthStatus.CRITICAL
        else:
            return HealthStatus.UNKNOWN
    
    def _generate_recommendations(
        self,
        metrics: List[HealthMetric],
        company: Company
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Financial recommendations
        financial = next((m for m in metrics if m.name == "financial_stability"), None)
        if financial and financial.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
            if "Low capital" in str(financial.details.get("risks", [])):
                recommendations.append("Consider capital increase to strengthen financial position")
            if "Recent bankruptcy" in str(financial.details.get("risks", [])):
                recommendations.append("Monitor closely - recent financial difficulties detected")
        
        # Growth recommendations
        growth = next((m for m in metrics if m.name == "growth_trend"), None)
        if growth and growth.value < 50:
            recommendations.append("Explore growth opportunities through new markets or partnerships")
        
        # Compliance recommendations
        compliance = next((m for m in metrics if m.name == "compliance"), None)
        if compliance and compliance.value < 70:
            if not company.certifications or not company.certifications.rge:
                recommendations.append("Consider RGE certification for environmental credibility")
        
        # Activity recommendations
        activity = next((m for m in metrics if m.name == "activity_level"), None)
        if activity and "No executives listed" in str(activity.details.get("risks", [])):
            recommendations.append("Update company records with current executive information")
        
        if not recommendations:
            recommendations.append("Maintain current positive trajectory")
        
        return recommendations
    
    async def _generate_predictions(
        self,
        company: Company,
        metrics: List[HealthMetric]
    ) -> Optional[str]:
        """Generate future predictions based on current metrics."""
        overall_score = sum(m.value * m.weight for m in metrics)
        
        if overall_score >= 70:
            return "Stable to positive outlook over next 12 months"
        elif overall_score >= 50:
            return "Moderate risk - monitor key indicators quarterly"
        else:
            return "High risk - immediate attention recommended"
    
    async def close(self) -> None:
        """Close API clients."""
        await self.bodacc_api.close()
        await self.api_entreprise.close()