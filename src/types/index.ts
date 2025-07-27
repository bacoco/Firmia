// Common types used across the MCP firms server

export interface APICredentials {
  insee?: {
    apiKey: string;
    baseUrl?: string;
  };
  banqueFrance?: {
    apiKey: string;
    username?: string;
    password?: string;
    baseUrl?: string;
  };
  inpi?: {
    apiKey: string;
    clientId?: string;
    clientSecret?: string;
    baseUrl?: string;
  };
}

export interface ErrorResponse {
  success: false;
  error: string;
  code?: string;
  details?: unknown;
}

export interface SuccessResponse<T> {
  success: true;
  data: T;
  metadata?: ResponseMetadata;
}

export interface ResponseMetadata {
  source: string;
  timestamp: string;
  cached: boolean;
  rateLimit?: {
    remaining: number;
    reset: string;
  };
}

export type APIResponse<T> = SuccessResponse<T> | ErrorResponse;

// Enterprise-specific types
export interface Address {
  street?: string;
  postalCode?: string;
  city?: string;
  country?: string;
  coordinates?: {
    latitude: number;
    longitude: number;
  };
}

export interface LegalRepresentative {
  name: string;
  role: string;
  startDate?: string;
}

export interface Establishment {
  siret: string;
  name?: string;
  address?: Address;
  isHeadOffice: boolean;
  activity?: string;
  employees?: number;
  creationDate?: string;
  status?: string;
}

// Financial data types
export interface FinancialStatement {
  year: number;
  revenue?: number;
  netIncome?: number;
  totalAssets?: number;
  equity?: number;
  debt?: number;
  employees?: number;
  currency: string;
}

export interface BankingRelationship {
  bankName: string;
  type: "main" | "secondary";
  since?: string;
}

// Intellectual property types
export interface Trademark {
  id: string;
  name: string;
  classes: number[];
  registrationDate: string;
  expirationDate?: string;
  status: "active" | "expired" | "pending";
}

export interface Patent {
  id: string;
  title: string;
  applicationDate: string;
  grantDate?: string;
  inventors?: string[];
  status: "granted" | "pending" | "expired";
}

export interface Design {
  id: string;
  title: string;
  registrationDate: string;
  expirationDate?: string;
  status: "active" | "expired";
}

// API-specific error codes
export enum APIErrorCode {
  // General errors
  UNKNOWN_ERROR = "UNKNOWN_ERROR",
  INVALID_REQUEST = "INVALID_REQUEST",
  AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED",
  RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED",
  SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE",
  
  // Business errors
  ENTERPRISE_NOT_FOUND = "ENTERPRISE_NOT_FOUND",
  INVALID_SIREN = "INVALID_SIREN",
  INVALID_SIRET = "INVALID_SIRET",
  ACCESS_DENIED = "ACCESS_DENIED",
  
  // Data errors
  NO_DATA_AVAILABLE = "NO_DATA_AVAILABLE",
  INCOMPLETE_DATA = "INCOMPLETE_DATA",
  OUTDATED_DATA = "OUTDATED_DATA"
}