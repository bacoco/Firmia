import axios from "axios";
import type { 
  BaseAdapter, 
  AdapterConfig, 
  SearchOptions, 
  DetailsOptions, 
  SearchResult, 
  EnterpriseDetails, 
  AdapterStatus 
} from "./index.js";

interface INSEETokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export class INSEEAdapter implements BaseAdapter {
  // Support both old and new API URLs
  private readonly legacyBaseUrl = "https://api.insee.fr/entreprises/sirene/V3";
  private readonly newBaseUrl = "https://api.insee.fr/api-sirene/3.11";
  private readonly tokenUrl = "https://api.insee.fr/token";
  
  // Authentication configuration
  private readonly legacyApiKey: string;
  private readonly newApiKey: string;
  private readonly clientId: string;
  private readonly clientSecret: string;
  
  // Token management
  private accessToken: string | null = null;
  private tokenExpiry: Date | null = null;
  
  private readonly rateLimiter: AdapterConfig["rateLimiter"];
  private readonly cache: AdapterConfig["cache"];
  private readonly useNewApi: boolean;

  constructor(config: AdapterConfig) {
    this.rateLimiter = config.rateLimiter;
    this.cache = config.cache;
    
    // Legacy API key (for backwards compatibility)
    this.legacyApiKey = process.env['INSEE_API_KEY'] || "";
    
    // New API configuration (OAuth2)
    this.newApiKey = process.env['INSEE_API_KEY_INTEGRATION'] || "";
    this.clientId = process.env['INSEE_CLIENT_ID'] || "";
    this.clientSecret = process.env['INSEE_CLIENT_SECRET'] || "";
    
    // Determine which API to use
    this.useNewApi = !!(this.newApiKey || (this.clientId && this.clientSecret));
    
    if (!this.useNewApi && !this.legacyApiKey) {
      console.warn("INSEE API credentials not found. Please configure either legacy API key or new OAuth2 credentials.");
    }
    
    // API selection completed during initialization
  }

  async search(query: string, options: SearchOptions): Promise<SearchResult[]> {
    const cacheKey = `insee:search:${query}:${JSON.stringify(options)}`;
    
    // Check cache first
    const cached = await this.cache.get(cacheKey);
    if (cached) {
      return cached as SearchResult[];
    }

    // Apply rate limiting
    await this.rateLimiter.acquire("insee");

    try {
      // Get appropriate headers for authentication
      const headers = await this.getAuthHeaders();
      const baseUrl = this.useNewApi ? this.newBaseUrl : this.legacyBaseUrl;
      
      // Check if query is a SIREN/SIRET number
      const isSiren = /^\d{9}$/.test(query);
      const isSiret = /^\d{14}$/.test(query);
      
      let endpoint: string;
      let params: Record<string, any> = {};

      if (isSiren) {
        endpoint = `${baseUrl}/siren/${query}`;
      } else if (isSiret) {
        endpoint = `${baseUrl}/siret/${query}`;
      } else {
        // Text search - use proper query format for INSEE API
        endpoint = `${baseUrl}/siren`;
        params['nombre'] = options.maxResults || 10;
        
        if (this.useNewApi) {
          // For new API, get all results and filter locally (temporary workaround)
          // Note: This is less efficient but works around query syntax issues
          params['nombre'] = Math.min((options.maxResults || 10) * 10, 100); // Get more to filter
        } else {
          // Legacy format with field qualifier  
          params['q'] = `denominationUniteLegale:*${query}*`;
        }
      }


      const response = await axios.get(endpoint, {
        headers: {
          ...headers,
          "Accept": "application/json"
        },
        params
      });

      let results = this.transformSearchResults(response.data);
      
      // For new API, filter results locally by company name
      if (this.useNewApi && !isSiren && !isSiret) {
        const searchTerm = query.toLowerCase();
        
        // First try exact match filtering
        let filteredResults = results.filter(result => 
          result.name.toLowerCase().includes(searchTerm)
        );
        
        // If no exact matches found, try partial matching with looser criteria
        if (filteredResults.length === 0 && searchTerm.length >= 3) {
          filteredResults = results.filter(result => {
            const name = result.name.toLowerCase();
            // Try matching any part of the search term
            return searchTerm.split('').some(char => name.includes(char)) ||
                   name.split(' ').some(word => word.startsWith(searchTerm.substring(0, 3)));
          });
        }
        
        // If still no results, return first few results as suggestions
        if (filteredResults.length === 0 && results.length > 0) {
          filteredResults = results.slice(0, Math.min(5, options.maxResults || 5));
        }
        
        results = filteredResults.slice(0, options.maxResults || 10);
      }
      
      // Cache the results
      await this.cache.set(cacheKey, results, 3600); // Cache for 1 hour
      
      return results;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error('INSEE API Search Error Details:', {
          status: error.response?.status,
          statusText: error.response?.statusText,
          data: error.response?.data,
          url: error.config?.url,
          params: error.config?.params
        });
        throw new Error(`INSEE API error: ${error.response?.data?.message || error.response?.data || error.message}`);
      }
      throw error;
    }
  }

  async getDetails(siren: string, options: DetailsOptions): Promise<EnterpriseDetails> {
    const cacheKey = `insee:details:${siren}:${JSON.stringify(options)}`;
    
    // Check cache first
    const cached = await this.cache.get(cacheKey);
    if (cached) {
      return cached as EnterpriseDetails;
    }

    // Apply rate limiting
    await this.rateLimiter.acquire("insee");

    try {
      const headers = await this.getAuthHeaders();
      const baseUrl = this.useNewApi ? this.newBaseUrl : this.legacyBaseUrl;
      
      const response = await axios.get(`${baseUrl}/siren/${siren}`, {
        headers: {
          ...headers,
          "Accept": "application/json"
        }
      });

      const details = this.transformEnterpriseDetails(response.data);
      
      // Cache the results
      await this.cache.set(cacheKey, details, 3600); // Cache for 1 hour
      
      return details;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`INSEE API error: ${error.response?.data?.message || error.message}`);
      }
      throw error;
    }
  }

  async getStatus(): Promise<AdapterStatus> {
    try {
      const headers = await this.getAuthHeaders();
      const baseUrl = this.useNewApi ? this.newBaseUrl : this.legacyBaseUrl;
      
      // Make a simple request to check API availability
      await axios.get(`${baseUrl}/informations`, {
        headers: {
          ...headers,
          "Accept": "application/json"
        }
      });

      return {
        available: true,
        rateLimit: await this.rateLimiter.getStatus("insee"),
        lastCheck: new Date()
      };
    } catch (error) {
      return {
        available: false,
        lastCheck: new Date()
      };
    }
  }

  /**
   * Get authentication headers based on the configured authentication method
   */
  private async getAuthHeaders(): Promise<Record<string, string>> {
    if (this.useNewApi) {
      if (this.newApiKey) {
        // Use API key header method
        return {
          "X-INSEE-Api-Key-Integration": this.newApiKey
        };
      } else if (this.clientId && this.clientSecret) {
        // Use OAuth2 access token
        const token = await this.getAccessToken();
        return {
          "Authorization": `Bearer ${token}`
        };
      }
    }
    
    // Fallback to legacy Bearer token
    return {
      "Authorization": `Bearer ${this.legacyApiKey}`
    };
  }

  /**
   * Get or refresh OAuth2 access token
   */
  private async getAccessToken(): Promise<string> {
    // Check if we have a valid token
    if (this.accessToken && this.tokenExpiry && new Date() < this.tokenExpiry) {
      return this.accessToken;
    }

    // Get new token
    try {
      const credentials = Buffer.from(`${this.clientId}:${this.clientSecret}`).toString('base64');
      
      const response = await axios.post(this.tokenUrl, 
        "grant_type=client_credentials",
        {
          headers: {
            "Authorization": `Basic ${credentials}`,
            "Content-Type": "application/x-www-form-urlencoded"
          }
        }
      );

      const tokenData: INSEETokenResponse = response.data;
      this.accessToken = tokenData.access_token;
      
      // Set expiry time (subtract 5 minutes for safety)
      this.tokenExpiry = new Date(Date.now() + (tokenData.expires_in - 300) * 1000);
      
      return this.accessToken;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`INSEE OAuth2 token error: ${error.response?.data?.error_description || error.message}`);
      }
      throw error;
    }
  }

  private transformSearchResults(data: any): SearchResult[] {
    if (!data || !data.unitesLegales) {
      return [];
    }

    if (data.unitesLegales.length === 0) {
      return [];
    }

    return data.unitesLegales.map((unit: any) => {
      // Get the current period (usually the first one with dateFin: null)
      const currentPeriod = unit.periodesUniteLegale?.find((p: any) => p.dateFin === null) || 
                           unit.periodesUniteLegale?.[0] || {};
      
      return {
        siren: unit.siren,
        siret: `${unit.siren}${currentPeriod.nicSiegeUniteLegale || ''}`,
        name: currentPeriod.denominationUniteLegale || 
              currentPeriod.denominationUsuelle1UniteLegale || 
              currentPeriod.nomUniteLegale || "",
        legalForm: currentPeriod.categorieJuridiqueUniteLegale,
        address: "", // Address requires separate SIRET lookup
        activity: currentPeriod.activitePrincipaleUniteLegale,
        creationDate: unit.dateCreationUniteLegale,
        status: currentPeriod.etatAdministratifUniteLegale
      };
    });
  }

  private transformEnterpriseDetails(data: any): EnterpriseDetails {
    const unit = data.uniteLegale || {};
    
    return {
      basicInfo: {
        siren: unit.siren,
        name: unit.denominationUniteLegale || unit.denominationUsuelle1UniteLegale || "",
        legalForm: unit.categorieJuridiqueUniteLegale,
        address: this.formatAddress(unit.adresseSiegeUniteLegale),
        activity: unit.activitePrincipaleUniteLegale,
        creationDate: unit.dateCreationUniteLegale,
        status: unit.etatAdministratifUniteLegale
      },
      financials: {
        employees: unit.trancheEffectifsUniteLegale,
        lastUpdate: unit.dateDernierTraitementUniteLegale
      }
    };
  }

  private formatAddress(address: any): string {
    if (!address) return "";
    
    const parts = [
      address.numeroVoieEtablissement,
      address.typeVoieEtablissement,
      address.libelleVoieEtablissement,
      address.codePostalEtablissement,
      address.libelleCommuneEtablissement
    ].filter(Boolean);
    
    return parts.join(" ");
  }
}