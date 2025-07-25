"""Privacy filters for RGPD compliance."""

from typing import Any, Dict, List, Optional, Union
from copy import deepcopy
from datetime import datetime

from pydantic import BaseModel
from structlog import get_logger

from ..models.company import Company, CompanySearchResult, Executive, Address

logger = get_logger(__name__)


class PrivacyRule(BaseModel):
    """Privacy filtering rule definition."""
    name: str
    condition: str  # Field to check (e.g., "privacy_status", "statut_diffusion")
    condition_value: Any  # Value that triggers the rule
    fields_to_remove: List[str] = []
    fields_to_mask: Dict[str, str] = {}  # field: masked_value
    applies_to: List[str] = []  # Model types this rule applies to


class PrivacyFilter:
    """Applies RGPD-compliant privacy filtering to data."""
    
    def __init__(self):
        self.logger = logger.bind(component="privacy_filter")
        self.rules = self._initialize_rules()
    
    def _initialize_rules(self) -> List[PrivacyRule]:
        """Initialize privacy filtering rules."""
        return [
            # Protected company addresses
            PrivacyRule(
                name="mask_protected_addresses",
                condition="privacy_status",
                condition_value="P",
                fields_to_remove=["street", "latitude", "longitude"],
                fields_to_mask={},
                applies_to=["Company", "CompanySearchResult", "Establishment"]
            ),
            
            # Individual birth details
            PrivacyRule(
                name="remove_birth_details",
                condition="is_individual",
                condition_value=True,
                fields_to_remove=["birth_date", "birth_place"],
                fields_to_mask={"birth_date": "YYYY-MM"},  # Keep only year-month
                applies_to=["Executive", "BeneficialOwner"]
            ),
            
            # Diffusion status from INSEE
            PrivacyRule(
                name="insee_diffusion_protected",
                condition="statut_diffusion",
                condition_value="P",
                fields_to_remove=["voie", "numVoie", "latitude", "longitude"],
                fields_to_mask={},
                applies_to=["Company", "Establishment"]
            ),
            
            # Executive privacy for individuals
            PrivacyRule(
                name="executive_privacy",
                condition="person_type",
                condition_value="PHYSIQUE",
                fields_to_remove=["date_naissance_complete", "lieu_naissance"],
                fields_to_mask={"date_naissance": "YYYY-MM"},
                applies_to=["Executive", "Representative"]
            )
        ]
    
    def apply_filters(self, data: Any, model_type: str = None) -> Any:
        """Apply privacy filters to data based on rules."""
        if data is None:
            return None
        
        # Determine model type if not provided
        if model_type is None:
            model_type = type(data).__name__
        
        # Work with a copy to avoid modifying original
        filtered_data = deepcopy(data)
        
        # Apply rules
        for rule in self.rules:
            if model_type in rule.applies_to:
                filtered_data = self._apply_rule(filtered_data, rule)
        
        return filtered_data
    
    def _apply_rule(self, data: Any, rule: PrivacyRule) -> Any:
        """Apply a single privacy rule to data."""
        # Handle different data types
        if isinstance(data, dict):
            return self._apply_rule_to_dict(data, rule)
        elif isinstance(data, list):
            return [self._apply_rule(item, rule) for item in data]
        elif hasattr(data, "__dict__"):
            # Pydantic model or class instance
            dict_data = data.dict() if hasattr(data, "dict") else vars(data)
            filtered_dict = self._apply_rule_to_dict(dict_data, rule)
            
            # Reconstruct object if it's a Pydantic model
            if hasattr(data, "parse_obj"):
                return type(data).parse_obj(filtered_dict)
            return filtered_dict
        
        return data
    
    def _apply_rule_to_dict(self, data: Dict[str, Any], rule: PrivacyRule) -> Dict[str, Any]:
        """Apply rule to dictionary data."""
        # Check if rule condition is met
        condition_met = False
        
        if rule.condition in data:
            if callable(rule.condition_value):
                condition_met = rule.condition_value(data)
            else:
                condition_met = data.get(rule.condition) == rule.condition_value
        
        if not condition_met:
            return data
        
        # Apply field removal
        for field in rule.fields_to_remove:
            if field in data:
                data.pop(field, None)
                self.logger.debug("field_removed", 
                                field=field, 
                                rule=rule.name)
        
        # Apply field masking
        for field, masked_value in rule.fields_to_mask.items():
            if field in data and data[field]:
                original_value = data[field]
                
                # Handle date masking
                if masked_value == "YYYY-MM" and original_value:
                    if isinstance(original_value, str) and len(original_value) >= 7:
                        data[field] = original_value[:7]  # Keep YYYY-MM
                    elif isinstance(original_value, datetime):
                        data[field] = original_value.strftime("%Y-%m")
                else:
                    data[field] = masked_value
                
                self.logger.debug("field_masked", 
                                field=field, 
                                rule=rule.name)
        
        # Recursively apply to nested objects
        for key, value in data.items():
            if isinstance(value, dict):
                data[key] = self._apply_rule_to_dict(value, rule)
            elif isinstance(value, list):
                data[key] = [self._apply_rule(item, rule) for item in value]
        
        return data
    
    def filter_company(self, company: Union[Company, Dict[str, Any]]) -> Union[Company, Dict[str, Any]]:
        """Apply privacy filters specifically to company data."""
        filtered = self.apply_filters(company, "Company")
        
        # Additional company-specific filtering
        if isinstance(filtered, dict):
            # Filter executives
            if "executives" in filtered:
                filtered["executives"] = [
                    self.apply_filters(exec, "Executive") 
                    for exec in filtered["executives"]
                ]
            
            # Filter establishments
            if "establishments" in filtered:
                filtered["establishments"] = [
                    self.apply_filters(est, "Establishment") 
                    for est in filtered["establishments"]
                ]
            
            # Filter address
            if "address" in filtered and filtered.get("privacy_status") == "P":
                filtered["address"] = self._filter_address(filtered["address"])
        
        return filtered
    
    def _filter_address(self, address: Union[Address, Dict[str, Any]]) -> Union[Address, Dict[str, Any]]:
        """Filter address data for protected entities."""
        if address is None:
            return None
        
        # For protected addresses, only keep postal code and city
        if isinstance(address, dict):
            return {
                "postal_code": address.get("postal_code"),
                "city": address.get("city")
            }
        elif isinstance(address, Address):
            return Address(
                postal_code=address.postal_code,
                city=address.city
            )
        
        return address
    
    def filter_search_results(
        self, 
        results: List[CompanySearchResult]
    ) -> List[CompanySearchResult]:
        """Apply privacy filters to search results."""
        filtered_results = []
        
        for result in results:
            # Check if company is diffusion-protected
            if hasattr(result, "privacy_status") and result.privacy_status == "P":
                # Filter address information
                if result.address:
                    result.address = self._filter_address(result.address)
            
            filtered_results.append(result)
        
        return filtered_results
    
    def should_hide_entity(self, data: Dict[str, Any]) -> bool:
        """Check if entity should be completely hidden from results."""
        # Some entities might be completely hidden based on specific criteria
        # For now, we show all entities but filter their data
        return False
    
    def get_privacy_notice(self, data: Dict[str, Any]) -> Optional[str]:
        """Get privacy notice for filtered data."""
        if data.get("privacy_status") == "P" or data.get("statut_diffusion") == "P":
            return "Certaines informations ont été masquées conformément au RGPD"
        return None


# Convenience function
def apply_privacy_filters(
    data: Any, 
    model_type: str = None
) -> Any:
    """Apply privacy filters to data."""
    filter = PrivacyFilter()
    return filter.apply_filters(data, model_type)