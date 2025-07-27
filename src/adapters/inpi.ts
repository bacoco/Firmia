import axios, { AxiosInstance } from "axios";
import type { 
  BaseAdapter, 
  AdapterConfig, 
  SearchOptions, 
  DetailsOptions, 
  SearchResult, 
  EnterpriseDetails, 
  AdapterStatus 
} from "./index.js";

interface INPIAuthResponse {
  token: string;
  user: {
    id: number;
    email: string;
    firstname: string;
    lastname: string;
    roles: string[];
  };
}

interface INPICompany {
  siren: string;
  denomination?: string;
  sigle?: string;
  adresse?: string;
  codePostal?: string;
  ville?: string;
  formeJuridique?: string;
  codeCategory?: string;
  activitySector?: string;
  dateCreation?: string;
  capitalSocial?: number;
  effectif?: number;
  dateRadiation?: string;
  statut?: string;
  dateImmatriculation?: string;
  numeroRCS?: string;
  nationalite?: string;
  dateClotureExercice?: string;
  representants?: Array<{
    role: string;
    nom: string;
    prenoms?: string[];
    dateNaissance?: string;
    entreprise?: {
      siren: string;
      denomination: string;
    };
  }>;
}

interface INPIAttachment {
  id: string;
  type: 'BILAN' | 'ACTE' | 'AUTRE';
  dateDepot: string;
  confidentiel: boolean;
  url: string;
  nomDocument?: string;
  typeDocument?: string;
}

export class INPIAdapter implements BaseAdapter {
  private readonly baseUrl: string;
  private readonly username: string;
  private readonly password: string;
  private readonly rateLimiter: AdapterConfig["rateLimiter"];
  private readonly cache: AdapterConfig["cache"];
  private axiosInstance: AxiosInstance;
  private authToken?: string;
  private tokenExpiry?: Date;

  constructor(config: AdapterConfig) {
    this.rateLimiter = config.rateLimiter;
    this.cache = config.cache;
    this.username = process.env['INPI_USERNAME'] || "";
    this.password = process.env['INPI_PASSWORD'] || "";
    this.baseUrl = process.env['NEXT_PUBLIC_INPI_API_URL'] || "https://registre-national-entreprises.inpi.fr/api";
    
    if (!this.username || !this.password) {
      console.warn("INPI credentials not found in environment variables");
    }

    this.axiosInstance = axios.create({
      baseURL: this.baseUrl,
      timeout: parseInt(process.env['NEXT_PUBLIC_API_TIMEOUT'] || '30000'),
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json"
      }
    });
  }

  private async authenticate(): Promise<void> {
    // Check if we have a valid token
    if (this.authToken && this.tokenExpiry && new Date() < this.tokenExpiry) {
      return;
    }

    const cacheKey = "inpi:auth:token";
    const cachedAuth = await this.cache.get(cacheKey);
    
    if (cachedAuth) {
      const { token, expiry } = cachedAuth as { token: string; expiry: string };
      const expiryDate = new Date(expiry);
      if (new Date() < expiryDate) {
        this.authToken = token;
        this.tokenExpiry = expiryDate;
        return;
      }
    }

    try {
      const response = await axios.post<INPIAuthResponse>(
        `${this.baseUrl}/sso/login`,
        {
          username: this.username,
          password: this.password
        }
      );

      this.authToken = response.data.token;
      
      // Handle expiry time - default to 1 hour (86400 seconds as seen in JWT)
      const expiresIn = 86400; // 24 hours as per INPI JWT
      const safetyMargin = Math.min(300, expiresIn / 2); // Use 5 min or half the duration
      
      this.tokenExpiry = new Date(Date.now() + (expiresIn - safetyMargin) * 1000);

      // Cache the token
      await this.cache.set(cacheKey, {
        token: this.authToken,
        expiry: this.tokenExpiry.toISOString()
      }, expiresIn - safetyMargin);

    } catch (error) {
      if (axios.isAxiosError(error)) {
        console.error('INPI Auth Error Details:', {
          status: error.response?.status,
          statusText: error.response?.statusText,
          data: error.response?.data,
          url: error.config?.url
        });
        throw new Error(`INPI authentication failed: ${error.response?.data?.message || error.response?.data || error.message}`);
      }
      console.error('INPI Auth Error (non-axios):', error);
      throw error;
    }
  }

  private async makeAuthenticatedRequest<T>(url: string, params?: Record<string, any>): Promise<T> {
    await this.authenticate();
    
    const response = await this.axiosInstance.get<T>(url, {
      headers: {
        "Authorization": `Bearer ${this.authToken}`
      },
      params
    });

    return response.data;
  }

  async search(query: string, options: SearchOptions): Promise<SearchResult[]> {
    const cacheKey = `inpi:search:${query}:${JSON.stringify(options)}`;
    
    // Check cache first
    const cached = await this.cache.get(cacheKey);
    if (cached) {
      return cached as SearchResult[];
    }

    // Apply rate limiting
    await this.rateLimiter.acquire("inpi");

    try {
      // Check if query is a SIREN number
      const isSiren = /^\d{9}$/.test(query);
      
      let companies: INPICompany[] = [];
      
      if (isSiren) {
        // Direct SIREN search
        const response = await this.makeAuthenticatedRequest<INPICompany[] | { companies: INPICompany[] }>(
          "/companies",
          {
            "siren[]": query,
            pageSize: Math.min(options.maxResults || 5, 5) // Limit to 5 to avoid memory issues
          }
        );
        // Handle different response formats
        if (Array.isArray(response)) {
          companies = response;
        } else {
          companies = (response as { companies: INPICompany[] }).companies || [];
        }
      } else {
        // Company name search
        const response = await this.makeAuthenticatedRequest<INPICompany[] | { companies: INPICompany[] }>(
          "/companies",
          {
            companyName: query,
            pageSize: Math.min(options.maxResults || 5, 5) // Limit to 5 to avoid memory issues
          }
        );
        // Handle different response formats
        if (Array.isArray(response)) {
          companies = response;
        } else {
          companies = (response as { companies: INPICompany[] }).companies || [];
        }
      }

      const results = companies.map(company => this.transformToSearchResult(company));
      
      // Cache the results
      await this.cache.set(cacheKey, results, 3600); // Cache for 1 hour
      
      return results;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 429) {
          throw new Error("INPI API rate limit exceeded. Please try again later.");
        }
        throw new Error(`INPI API error: ${error.response?.data?.message || error.message}`);
      }
      throw error;
    }
  }

  async getDetails(siren: string, options: DetailsOptions): Promise<EnterpriseDetails> {
    const cacheKey = `inpi:details:${siren}:${JSON.stringify(options)}`;
    
    // Check cache first
    const cached = await this.cache.get(cacheKey);
    if (cached) {
      return cached as EnterpriseDetails;
    }

    // Apply rate limiting
    await this.rateLimiter.acquire("inpi");

    try {
      // Get company details
      const company = await this.makeAuthenticatedRequest<INPICompany>(
        `/companies/${siren}`
      );

      let intellectualProperty = undefined;
      
      if (options.includeIntellectualProperty) {
        // Get attachments to count intellectual property documents
        try {
          const attachments = await this.makeAuthenticatedRequest<{ attachments: INPIAttachment[] }>(
            `/companies/${siren}/attachments`
          );
          
          intellectualProperty = this.countIntellectualProperty(attachments.attachments || []);
        } catch (error) {
          console.warn(`Failed to fetch attachments for ${siren}:`, error);
        }
      }

      const details = this.transformToEnterpriseDetails(company, intellectualProperty);
      
      // Cache the results
      await this.cache.set(cacheKey, details, 3600); // Cache for 1 hour
      
      return details;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        if (error.response?.status === 429) {
          throw new Error("INPI API rate limit exceeded. Please try again later.");
        }
        throw new Error(`INPI API error: ${error.response?.data?.message || error.message}`);
      }
      throw error;
    }
  }

  async getStatus(): Promise<AdapterStatus> {
    try {
      // Authenticate to check API availability
      await this.authenticate();
      
      // Make a simple request to check API status
      await this.makeAuthenticatedRequest("/api/companies", { pageSize: 1 });

      const rateLimit = await this.rateLimiter.getStatus("inpi");

      return {
        available: true,
        rateLimit,
        lastCheck: new Date()
      };
    } catch (error) {
      return {
        available: false,
        lastCheck: new Date()
      };
    }
  }

  private transformToSearchResult(company: any): SearchResult {
    // Handle the actual INPI API response structure
    const siren = company.siren || company.formality?.siren || "";
    const formality = company.formality || {};
    const content = formality.content || {};
    const personneMorale = content.personneMorale || {};
    
    // Extract company name from the correct nested structure
    const identite = personneMorale.identite || {};
    const entreprise = identite.entreprise || {};
    const denomination = entreprise.denomination || "";
    
    // Extract address from the correct structure
    const adresseEntreprise = personneMorale.adresseEntreprise || {};
    const address = this.formatAddressFromINPI(adresseEntreprise, personneMorale, company);
    
    // Extract activity from entreprise data
    const activite = entreprise.codeApe || company.activitySector || "";
    
    // Extract legal form
    const formeJuridique = entreprise.formeJuridique || formality.formeJuridique || company.formeJuridique || "";
    
    // Extract creation date
    const creationDate = entreprise.dateImmat || personneMorale.dateImmatriculation || company.dateCreation || "";
    
    return {
      siren: siren,
      name: denomination,
      legalForm: formeJuridique,
      address: address,
      activity: activite,
      creationDate: creationDate,
      status: this.determineINPIStatus(company)
    };
  }

  private transformToEnterpriseDetails(
    company: INPICompany, 
    intellectualProperty?: { trademarks: number; patents: number; designs: number }
  ): EnterpriseDetails {
    const basicInfo = {
      siren: company.siren,
      name: company.denomination || company.sigle || "",
      legalForm: company.formeJuridique,
      address: this.formatAddress(company),
      activity: company.codeCategory || company.activitySector,
      creationDate: company.dateCreation || company.dateImmatriculation,
      status: this.determineStatus(company)
    };

    const financials = company.capitalSocial || company.effectif ? {
      revenue: company.capitalSocial,
      employees: company.effectif,
      lastUpdate: new Date().toISOString() // INPI doesn't provide this directly
    } : undefined;

    return {
      basicInfo,
      financials,
      intellectualProperty
    };
  }

  private formatAddress(company: INPICompany): string {
    const parts = [
      company.adresse,
      company.codePostal,
      company.ville
    ].filter(Boolean);
    
    return parts.join(" ");
  }

  private formatAddressFromINPI(adresseEntreprise: any, personneMorale: any, company: any): string {
    // Try to extract address from the nested INPI structure
    
    // Check if address is in adresseEntreprise.adresse
    let adresse = adresseEntreprise.adresse;
    
    // Fallback to other possible locations
    if (!adresse || Object.keys(adresse).length === 0) {
      adresse = adresseEntreprise || personneMorale.adresse || personneMorale.adresseSiege || company.adresse;
    }
    
    if (adresse && Object.keys(adresse).length > 0) {
      const parts = [
        adresse.numVoie || adresse.numero || adresse.numeroVoie,
        adresse.typeVoie,
        adresse.voie || adresse.nomVoie,
        adresse.codePostal,
        adresse.commune || adresse.ville || adresse.localite
      ].filter(Boolean);
      return parts.join(" ");
    }
    return "";
  }

  private determineStatus(company: INPICompany): string {
    if (company.dateRadiation) {
      return "radié";
    }
    if (company.statut) {
      return company.statut.toLowerCase();
    }
    return "actif";
  }

  private determineINPIStatus(company: any): string {
    // Handle actual INPI response structure
    const formality = company.formality || {};
    const content = formality.content || {};
    
    if (content.cessationActivite || content.dissolution) {
      return "cessé";
    }
    if (content.radiation) {
      return "radié";
    }
    if (company.nombreEtablissementsOuverts > 0) {
      return "actif";
    }
    return "actif"; // Default status
  }

  private countIntellectualProperty(attachments: INPIAttachment[]): {
    trademarks: number;
    patents: number;
    designs: number;
  } {
    let trademarks = 0;
    let patents = 0;
    let designs = 0;

    for (const attachment of attachments) {
      const docName = attachment.nomDocument?.toLowerCase() || "";
      const docType = attachment.typeDocument?.toLowerCase() || "";
      
      if (docName.includes("marque") || docType.includes("marque")) {
        trademarks++;
      } else if (docName.includes("brevet") || docType.includes("brevet")) {
        patents++;
      } else if (docName.includes("dessin") || docName.includes("modele") || 
                 docType.includes("dessin") || docType.includes("modele")) {
        designs++;
      }
    }

    return { trademarks, patents, designs };
  }

  /**
   * Get beneficial ownership information from company representatives
   */
  async getBeneficialOwners(siren: string): Promise<Array<{
    name: string;
    role: string;
    birthDate?: string;
    isCompany: boolean;
    companySiren?: string;
  }>> {
    const cacheKey = `inpi:beneficial-owners:${siren}`;
    
    // Check cache first
    const cached = await this.cache.get(cacheKey);
    if (cached) {
      return cached as Array<any>;
    }

    // Apply rate limiting
    await this.rateLimiter.acquire("inpi");

    try {
      const company = await this.makeAuthenticatedRequest<INPICompany>(
        `/api/companies/${siren}`
      );

      const beneficialOwners = (company.representants || []).map(rep => ({
        name: rep.nom,
        role: rep.role,
        birthDate: rep.dateNaissance,
        isCompany: !!rep.entreprise,
        companySiren: rep.entreprise?.siren
      }));

      // Cache the results
      await this.cache.set(cacheKey, beneficialOwners, 3600); // Cache for 1 hour

      return beneficialOwners;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Failed to fetch beneficial owners: ${error.response?.data?.message || error.message}`);
      }
      throw error;
    }
  }

  /**
   * Get company publications (acts and financial documents)
   */
  async getCompanyPublications(siren: string, options?: {
    type?: 'ACTE' | 'BILAN' | 'ALL';
    from?: Date;
    to?: Date;
    includeConfidential?: boolean;
  }): Promise<Array<{
    id: string;
    type: string;
    name: string;
    date: string;
    confidential: boolean;
    downloadUrl?: string;
  }>> {
    const cacheKey = `inpi:publications:${siren}:${JSON.stringify(options || {})}`;
    
    // Check cache first
    const cached = await this.cache.get(cacheKey);
    if (cached) {
      return cached as Array<any>;
    }

    // Apply rate limiting
    await this.rateLimiter.acquire("inpi");

    try {
      const attachments = await this.makeAuthenticatedRequest<{ attachments: INPIAttachment[] }>(
        `/api/companies/${siren}/attachments`
      );

      let publications = (attachments.attachments || [])
        .filter(att => {
          // Filter by type if specified
          if (options?.type && options.type !== 'ALL' && att.type !== options.type) {
            return false;
          }
          
          // Filter by confidentiality
          if (!options?.includeConfidential && att.confidentiel) {
            return false;
          }

          // Filter by date range
          const attDate = new Date(att.dateDepot);
          if (options?.from && attDate < options.from) {
            return false;
          }
          if (options?.to && attDate > options.to) {
            return false;
          }

          return true;
        })
        .map(att => ({
          id: att.id,
          type: att.type,
          name: att.nomDocument || `${att.type} ${att.id}`,
          date: att.dateDepot,
          confidential: att.confidentiel,
          downloadUrl: att.confidentiel ? undefined : `${this.baseUrl}${att.url}`
        }));

      // Sort by date descending
      publications.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

      // Cache the results
      await this.cache.set(cacheKey, publications, 3600); // Cache for 1 hour

      return publications;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Failed to fetch company publications: ${error.response?.data?.message || error.message}`);
      }
      throw error;
    }
  }

  /**
   * Get differential updates for companies (recent changes)
   */
  async getDifferentialUpdates(options: {
    from: Date;
    to?: Date;
    pageSize?: number;
    searchAfter?: string;
  }): Promise<{
    companies: Array<{
      siren: string;
      name: string;
      updateType: string;
      updateDate: string;
    }>;
    nextCursor?: string;
  }> {
    // Apply rate limiting
    await this.rateLimiter.acquire("inpi");

    try {
      const params: Record<string, any> = {
        from: options.from.toISOString().split('T')[0],
        to: (options.to || new Date()).toISOString().split('T')[0],
        pageSize: options.pageSize || 100
      };

      if (options.searchAfter) {
        params.searchAfter = options.searchAfter;
      }

      const response = await this.makeAuthenticatedRequest<{
        companies: INPICompany[];
        searchAfter?: string;
      }>("/api/companies/diff", params);

      const companies = (response.companies || []).map(company => ({
        siren: company.siren,
        name: company.denomination || company.sigle || "",
        updateType: this.determineUpdateType(company),
        updateDate: company.dateImmatriculation || new Date().toISOString()
      }));

      return {
        companies,
        nextCursor: response['searchAfter']
      };
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Failed to fetch differential updates: ${error.response?.data?.message || error.message}`);
      }
      throw error;
    }
  }

  private determineUpdateType(company: INPICompany): string {
    if (company.dateRadiation) {
      return "RADIATION";
    }
    if (company.dateImmatriculation && 
        new Date(company.dateImmatriculation) > new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)) {
      return "CREATION";
    }
    return "MODIFICATION";
  }
}