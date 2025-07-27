# API Adapter Documentation

This document provides detailed information about the API adapters used in MCP Firms, including data field mappings, authentication requirements, and implementation details.

## Table of Contents
- [Overview](#overview)
- [Adapter Architecture](#adapter-architecture)
- [INSEE Adapter](#insee-adapter)
- [Banque de France Adapter](#banque-de-france-adapter)
- [INPI Adapter](#inpi-adapter)
- [Creating Custom Adapters](#creating-custom-adapters)
- [Error Handling](#error-handling)
- [Testing Adapters](#testing-adapters)

## Overview

MCP Firms uses a modular adapter architecture to integrate with different French enterprise data APIs. Each adapter implements a common interface while handling the specific requirements of its API.

### Base Adapter Interface

```typescript
interface BaseAdapter {
  search(query: string, options: SearchOptions): Promise<SearchResult[]>;
  getDetails(siren: string, options: DetailsOptions): Promise<EnterpriseDetails>;
  getStatus(): Promise<AdapterStatus>;
}
```

## Adapter Architecture

### Common Components

All adapters share these common components:

1. **Rate Limiter**: Prevents exceeding API quotas
2. **Cache**: Reduces API calls and improves response times
3. **Error Handler**: Standardizes error responses
4. **Type Transformer**: Converts API responses to standard format

### Adapter Configuration

```typescript
interface AdapterConfig {
  rateLimiter: RateLimiter;
  cache: Cache;
  credentials?: APICredentials;
  options?: AdapterOptions;
}
```

## INSEE Adapter

### Overview
The INSEE adapter integrates with the French National Institute of Statistics API (SIRENE V3).

### Authentication
- **Type**: OAuth 2.0 / API Key
- **Required Credentials**:
  - Consumer Key (API Key)
  - Consumer Secret (optional for enhanced security)

### Endpoints Used
- `/siren/{siren}` - Get enterprise by SIREN
- `/siret/{siret}` - Get establishment by SIRET
- `/siren` - Search enterprises

### Data Field Mappings

#### Search Results
| INSEE Field | MCP Field | Type | Description |
|------------|-----------|------|-------------|
| siren | siren | string | 9-digit enterprise identifier |
| denominationUniteLegale | name | string | Legal name |
| denominationUsuelle | tradeName | string | Trade name |
| categorieJuridiqueUniteLegale | legalForm | string | Legal form code |
| activitePrincipaleUniteLegale | activity.code | string | NAF/APE code |
| libelleActivitePrincipaleUniteLegale | activity.description | string | Activity description |
| trancheEffectifsUniteLegale | employeeRange | string | Employee range code |
| dateCreationUniteLegale | creationDate | string | Creation date |

#### Enterprise Details
| INSEE Field | MCP Field | Type | Description |
|------------|-----------|------|-------------|
| siren | identification.siren | string | Enterprise identifier |
| denominationUniteLegale | identification.name | string | Legal name |
| sigleUniteLegale | identification.acronym | string | Acronym |
| categorieJuridiqueUniteLegale | identification.legalFormCode | string | Legal form code |
| dateCreationUniteLegale | identification.registrationDate | string | Registration date |
| capitalSocial | identification.capital | number | Share capital |
| etablissements | establishments | array | List of establishments |

### Rate Limits
- **Default**: 5,000 requests/hour
- **Burst**: 50 requests/minute
- **Headers**: `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### Example Request/Response

```typescript
// Request
const adapter = new INSEEAdapter(config);
const results = await adapter.search("Airbus", { maxResults: 5 });

// Response
[
  {
    siren: "383474814",
    name: "AIRBUS",
    legalForm: "Société européenne",
    address: {
      street: "2 ROND POINT EMILE DEWOITINE",
      postalCode: "31700",
      city: "BLAGNAC"
    },
    activity: {
      code: "30.30Z",
      description: "Construction aéronautique et spatiale"
    },
    employees: 5000,
    creationDate: "1970-01-01"
  }
]
```

## Banque de France Adapter

### Overview
The Banque de France adapter provides access to financial data and credit ratings for French enterprises.

### Authentication
- **Type**: Basic Auth + API Key
- **Required Credentials**:
  - API Key
  - Username
  - Password

### Endpoints Used
- `/entreprises/{siren}/financials` - Financial statements
- `/entreprises/{siren}/rating` - Credit rating
- `/entreprises/{siren}/banking` - Banking relationships

### Data Field Mappings

#### Financial Data
| BdF Field | MCP Field | Type | Description |
|-----------|-----------|------|-------------|
| exercice | year | number | Financial year |
| chiffreAffaires | revenue | number | Annual revenue |
| resultatNet | netIncome | number | Net income |
| totalBilan | totalAssets | number | Total assets |
| capitauxPropres | equity | number | Shareholders' equity |
| dettes | debt | number | Total debt |
| effectif | employees | number | Number of employees |

#### Credit Rating
| BdF Field | MCP Field | Type | Description |
|-----------|-----------|------|-------------|
| cotation | score | string | Credit rating (AAA to D) |
| tendance | outlook | string | Rating outlook |
| dateEvaluation | lastUpdate | string | Last evaluation date |
| scoreDefaillance | defaultProbability | number | Default probability (%) |

### Rate Limits
- **Default**: 1,000 requests/hour
- **Burst**: 20 requests/minute
- **Headers**: `X-BdF-Quota-Remaining`

### Example Request/Response

```typescript
// Request
const adapter = new BanqueFranceAdapter(config);
const details = await adapter.getDetails("383474814", { includeFinancials: true });

// Response
{
  financials: [
    {
      year: 2023,
      revenue: 65446000000,
      netIncome: 3789000000,
      totalAssets: 138503000000,
      equity: 61242000000,
      debt: 45123000000,
      employees: 134267,
      currency: "EUR"
    }
  ],
  rating: {
    score: "AAA",
    outlook: "Stable",
    lastUpdate: "2024-01-15",
    defaultProbability: 0.01
  }
}
```

## INPI Adapter

### Overview
The INPI adapter provides access to intellectual property data including trademarks, patents, and industrial designs.

### Authentication
- **Type**: OAuth 2.0
- **Required Credentials**:
  - API Key
  - Client ID
  - Client Secret

### Endpoints Used
- `/marques/search` - Search trademarks
- `/brevets/search` - Search patents
- `/dessins-modeles/search` - Search designs
- `/entreprises/{siren}/ip` - Get all IP for enterprise

### Data Field Mappings

#### Trademarks
| INPI Field | MCP Field | Type | Description |
|------------|-----------|------|-------------|
| numeroMarque | id | string | Trademark number |
| nomMarque | name | string | Trademark name |
| classesNice | classes | number[] | Nice classification |
| dateDepot | applicationDate | string | Application date |
| dateEnregistrement | registrationDate | string | Registration date |
| dateExpiration | expirationDate | string | Expiration date |
| statutMarque | status | string | Status |

#### Patents
| INPI Field | MCP Field | Type | Description |
|------------|-----------|------|-------------|
| numeroBrevet | id | string | Patent number |
| titreBrevet | title | string | Patent title |
| dateDepot | applicationDate | string | Application date |
| dateDelivrance | grantDate | string | Grant date |
| inventeurs | inventors | string[] | List of inventors |
| statutBrevet | status | string | Status |

### Rate Limits
- **Default**: 2,000 requests/hour
- **Burst**: 30 requests/minute
- **Headers**: `X-INPI-Requests-Remaining`

### Example Request/Response

```typescript
// Request
const adapter = new INPIAdapter(config);
const details = await adapter.getDetails("383474814", { includeIntellectualProperty: true });

// Response
{
  trademarks: [
    {
      id: "4234567",
      name: "AIRBUS",
      classes: [12, 39, 42],
      applicationDate: "2010-01-15",
      registrationDate: "2010-03-15",
      expirationDate: "2030-03-15",
      status: "active"
    }
  ],
  patents: [
    {
      id: "EP2234567",
      title: "Aircraft wing optimization system",
      applicationDate: "2019-06-20",
      grantDate: "2021-03-10",
      inventors: ["John Doe", "Jane Smith"],
      status: "granted"
    }
  ]
}
```

## Creating Custom Adapters

### Step 1: Implement the Base Interface

```typescript
import { BaseAdapter, AdapterConfig } from './index.js';

export class CustomAdapter implements BaseAdapter {
  constructor(private config: AdapterConfig) {
    // Initialize adapter
  }

  async search(query: string, options: SearchOptions): Promise<SearchResult[]> {
    // Implement search logic
  }

  async getDetails(siren: string, options: DetailsOptions): Promise<EnterpriseDetails> {
    // Implement details retrieval
  }

  async getStatus(): Promise<AdapterStatus> {
    // Implement status check
  }
}
```

### Step 2: Register the Adapter

```typescript
// In adapters/index.ts
export function setupAdapters(config: AdapterConfig): Record<string, BaseAdapter> {
  return {
    insee: new INSEEAdapter(config),
    'banque-france': new BanqueFranceAdapter(config),
    inpi: new INPIAdapter(config),
    custom: new CustomAdapter(config), // Add your adapter
  };
}
```

### Step 3: Add Configuration

```env
# In .env
CUSTOM_API_KEY=your_api_key
CUSTOM_API_URL=https://api.custom.com
RATE_LIMIT_CUSTOM=1000
```

## Error Handling

### Common Error Codes

All adapters use standardized error codes:

```typescript
enum APIErrorCode {
  AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED",
  RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED",
  ENTERPRISE_NOT_FOUND = "ENTERPRISE_NOT_FOUND",
  INVALID_SIREN = "INVALID_SIREN",
  SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE",
  NO_DATA_AVAILABLE = "NO_DATA_AVAILABLE"
}
```

### Error Response Format

```typescript
interface ErrorResponse {
  success: false;
  error: string;
  code?: APIErrorCode;
  details?: {
    message: string;
    originalError?: unknown;
    suggestions?: string[];
  };
}
```

### Handling API-Specific Errors

```typescript
try {
  const response = await apiCall();
} catch (error) {
  if (isRateLimitError(error)) {
    throw new APIError(
      APIErrorCode.RATE_LIMIT_EXCEEDED,
      'Rate limit exceeded',
      { resetTime: error.resetTime }
    );
  }
  // Handle other errors...
}
```

## Testing Adapters

### Unit Testing

```typescript
describe('INSEEAdapter', () => {
  let adapter: INSEEAdapter;
  let mockCache: jest.Mocked<Cache>;
  let mockRateLimiter: jest.Mocked<RateLimiter>;

  beforeEach(() => {
    mockCache = createMockCache();
    mockRateLimiter = createMockRateLimiter();
    adapter = new INSEEAdapter({ cache: mockCache, rateLimiter: mockRateLimiter });
  });

  describe('search', () => {
    it('should return cached results when available', async () => {
      mockCache.get.mockResolvedValue(cachedResults);
      const results = await adapter.search('test');
      expect(mockCache.get).toHaveBeenCalledWith('insee:search:test:{}');
      expect(results).toEqual(cachedResults);
    });
  });
});
```

### Integration Testing

```typescript
describe('INSEE API Integration', () => {
  it('should search for real enterprises', async () => {
    const adapter = new INSEEAdapter(realConfig);
    const results = await adapter.search('Airbus');
    
    expect(results).toHaveLength(greaterThan(0));
    expect(results[0]).toHaveProperty('siren');
    expect(results[0]).toHaveProperty('name');
  });
});
```

### Mocking External APIs

```typescript
// Mock INSEE API responses
nock('https://api.insee.fr')
  .get('/entreprises/sirene/V3/siren/383474814')
  .reply(200, mockINSEEResponse);

// Test with mocked API
const results = await adapter.getDetails('383474814');
expect(results).toMatchSnapshot();
```

## Best Practices

1. **Always use rate limiting** to respect API quotas
2. **Implement caching** to reduce API calls
3. **Transform data consistently** to standard format
4. **Handle errors gracefully** with meaningful messages
5. **Log API interactions** for debugging
6. **Test with mock data** to avoid hitting real APIs
7. **Document field mappings** thoroughly
8. **Version your adapters** for backward compatibility

## Resources

- [INSEE API Documentation](https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3&provider=insee)
- [Banque de France API Portal](https://developer.banque-france.fr)
- [INPI Data Portal](https://data.inpi.fr/docs)
- [MCP Protocol Specification](https://modelcontextprotocol.io)