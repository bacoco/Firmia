import { INSEEAdapter } from "./insee.js";
import { BanqueFranceAdapter } from "./banque-france.js";
import { INPIAdapter } from "./inpi.js";
import type { RateLimiter } from "../rate-limiter/index.js";
import type { Cache } from "../cache/index.js";

export interface AdapterConfig {
  rateLimiter: RateLimiter;
  cache: Cache;
}

export interface BaseAdapter {
  search(query: string, options: SearchOptions): Promise<SearchResult[]>;
  getDetails(siren: string, options: DetailsOptions): Promise<EnterpriseDetails>;
  getStatus(): Promise<AdapterStatus>;
}

export interface SearchOptions {
  includeHistory?: boolean;
  maxResults?: number;
}

export interface DetailsOptions {
  includeFinancials?: boolean;
  includeIntellectualProperty?: boolean;
}

export interface SearchResult {
  siren: string;
  siret?: string;
  name: string;
  legalForm?: string;
  address?: string;
  activity?: string;
  creationDate?: string;
  status?: string;
}

export interface EnterpriseDetails {
  basicInfo: {
    siren: string;
    name: string;
    legalForm?: string;
    address?: string;
    activity?: string;
    creationDate?: string;
    status?: string;
  };
  financials?: {
    revenue?: number;
    employees?: number;
    lastUpdate?: string;
  };
  intellectualProperty?: {
    trademarks?: number;
    patents?: number;
    designs?: number;
  };
}

export interface AdapterStatus {
  available: boolean;
  rateLimit?: {
    remaining: number;
    reset: Date;
  };
  lastCheck?: Date;
}

export function setupAdapters(config: AdapterConfig): Record<string, BaseAdapter> {
  return {
    insee: new INSEEAdapter(config),
    "banque-france": new BanqueFranceAdapter(config),
    inpi: new INPIAdapter(config)
  };
}