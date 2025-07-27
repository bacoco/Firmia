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

export class INSEEAdapter implements BaseAdapter {
  private readonly baseUrl = "https://api.insee.fr/entreprises/sirene/V3";
  private readonly apiKey: string;
  private readonly rateLimiter: AdapterConfig["rateLimiter"];
  private readonly cache: AdapterConfig["cache"];

  constructor(config: AdapterConfig) {
    this.rateLimiter = config.rateLimiter;
    this.cache = config.cache;
    this.apiKey = process.env['INSEE_API_KEY'] || "";
    
    if (!this.apiKey) {
      console.warn("INSEE API key not found in environment variables");
    }
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
      // Check if query is a SIREN/SIRET number
      const isSiren = /^\d{9}$/.test(query);
      const isSiret = /^\d{14}$/.test(query);
      
      let endpoint: string;
      let params: Record<string, any> = {
        nombre: options.maxResults || 10
      };

      if (isSiren) {
        endpoint = `${this.baseUrl}/siren/${query}`;
      } else if (isSiret) {
        endpoint = `${this.baseUrl}/siret/${query}`;
      } else {
        // Text search
        endpoint = `${this.baseUrl}/siren`;
        params['q'] = `denominationUniteLegale:"${query}"`;
      }

      const response = await axios.get(endpoint, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Accept": "application/json"
        },
        params
      });

      const results = this.transformSearchResults(response.data);
      
      // Cache the results
      await this.cache.set(cacheKey, results, 3600); // Cache for 1 hour
      
      return results;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`INSEE API error: ${error.response?.data?.message || error.message}`);
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
      const response = await axios.get(`${this.baseUrl}/siren/${siren}`, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
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
      // Make a simple request to check API availability
      await axios.get(`${this.baseUrl}/informations`, {
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
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

  private transformSearchResults(data: any): SearchResult[] {
    if (!data || !data.unitesLegales) {
      return [];
    }

    return data.unitesLegales.map((unit: any) => ({
      siren: unit.siren,
      siret: unit.siretSiegeSocial,
      name: unit.denominationUniteLegale || unit.denominationUsuelle1UniteLegale || "",
      legalForm: unit.categorieJuridiqueUniteLegale,
      address: this.formatAddress(unit.adresseSiegeUniteLegale),
      activity: unit.activitePrincipaleUniteLegale,
      creationDate: unit.dateCreationUniteLegale,
      status: unit.etatAdministratifUniteLegale
    }));
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