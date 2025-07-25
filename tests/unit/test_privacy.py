"""Unit tests for privacy filtering."""

import pytest
from datetime import datetime

from src.privacy.filters import PrivacyFilter, apply_privacy_filters
from src.models.company import Company, Address, Executive


class TestPrivacyFilter:
    """Test privacy filtering functionality."""
    
    @pytest.fixture
    def privacy_filter(self):
        """Create privacy filter instance."""
        return PrivacyFilter()
    
    def test_filter_protected_company_address(self, privacy_filter):
        """Test filtering of protected company addresses."""
        company_data = {
            "siren": "123456789",
            "denomination": "TEST COMPANY",
            "privacy_status": "P",  # Protected
            "address": {
                "street": "123 Secret Street",
                "postal_code": "75001",
                "city": "Paris",
                "latitude": 48.8566,
                "longitude": 2.3522
            }
        }
        
        filtered = privacy_filter.filter_company(company_data)
        
        # Address should only have postal code and city
        assert filtered["address"]["postal_code"] == "75001"
        assert filtered["address"]["city"] == "Paris"
        assert "street" not in filtered["address"]
        assert "latitude" not in filtered["address"]
        assert "longitude" not in filtered["address"]
    
    def test_filter_executive_birth_details(self, privacy_filter):
        """Test filtering of executive birth information."""
        executive_data = {
            "role": "CEO",
            "name": "Dupont",
            "first_name": "Jean",
            "birth_date": "1970-05-15",
            "person_type": "PHYSIQUE",
            "date_naissance_complete": "1970-05-15",
            "lieu_naissance": "Paris"
        }
        
        filtered = privacy_filter.apply_filters(executive_data, "Executive")
        
        # Birth date should be masked to YYYY-MM
        assert filtered["birth_date"] == "1970-05"
        assert "date_naissance_complete" not in filtered
        assert "lieu_naissance" not in filtered
    
    def test_no_filtering_for_open_company(self, privacy_filter):
        """Test that open companies are not filtered."""
        company_data = {
            "siren": "123456789",
            "denomination": "OPEN COMPANY",
            "privacy_status": "O",  # Open
            "address": {
                "street": "123 Public Street",
                "postal_code": "75001",
                "city": "Paris",
                "latitude": 48.8566,
                "longitude": 2.3522
            }
        }
        
        filtered = privacy_filter.filter_company(company_data)
        
        # All address fields should be present
        assert filtered["address"]["street"] == "123 Public Street"
        assert filtered["address"]["latitude"] == 48.8566
        assert filtered["address"]["longitude"] == 2.3522
    
    def test_insee_diffusion_protection(self, privacy_filter):
        """Test INSEE diffusion protection status."""
        company_data = {
            "siren": "123456789",
            "denomination": "PROTECTED COMPANY",
            "statut_diffusion": "P",  # INSEE protection
            "voie": "123 Secret Street",
            "numVoie": "123",
            "latitude": 48.8566,
            "longitude": 2.3522,
            "codePostal": "75001",
            "commune": "Paris"
        }
        
        # Apply filters with Company model type
        filtered = privacy_filter.apply_filters(company_data, "Company")
        
        # Protected fields should be removed
        assert "voie" not in filtered
        assert "numVoie" not in filtered
        assert "latitude" not in filtered
        assert "longitude" not in filtered
        # Public fields should remain
        assert filtered["codePostal"] == "75001"
        assert filtered["commune"] == "Paris"
    
    def test_recursive_filtering(self, privacy_filter):
        """Test that filtering is applied recursively."""
        company_data = {
            "siren": "123456789",
            "denomination": "TEST COMPANY",
            "privacy_status": "P",
            "executives": [
                {
                    "role": "CEO",
                    "name": "Dupont",
                    "birth_date": "1970-05-15",
                    "person_type": "PHYSIQUE"
                }
            ],
            "establishments": [
                {
                    "siret": "12345678900001",
                    "privacy_status": "P",
                    "address": {
                        "street": "Secret",
                        "postal_code": "75001",
                        "city": "Paris"
                    }
                }
            ]
        }
        
        filtered = privacy_filter.filter_company(company_data)
        
        # Check executive filtering
        assert filtered["executives"][0]["birth_date"] == "1970-05"
        
        # Check establishment address filtering
        assert "street" not in filtered["establishments"][0]["address"]
        assert filtered["establishments"][0]["address"]["postal_code"] == "75001"
    
    def test_privacy_notice(self, privacy_filter):
        """Test privacy notice generation."""
        protected_data = {"privacy_status": "P"}
        notice = privacy_filter.get_privacy_notice(protected_data)
        assert notice == "Certaines informations ont été masquées conformément au RGPD"
        
        open_data = {"privacy_status": "O"}
        notice = privacy_filter.get_privacy_notice(open_data)
        assert notice is None


class TestPrivacyHelpers:
    """Test privacy helper functions."""
    
    def test_apply_privacy_filters_function(self):
        """Test the convenience function."""
        data = {
            "siren": "123456789",
            "privacy_status": "P",
            "address": {
                "street": "Secret",
                "postal_code": "75001",
                "city": "Paris"
            }
        }
        
        filtered = apply_privacy_filters(data, "Company")
        
        assert "street" not in filtered["address"]
        assert filtered["address"]["postal_code"] == "75001"