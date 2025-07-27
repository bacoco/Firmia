# Firmia - French Enterprise Data Integration

Firmia is an MCP (Model Context Protocol) server that provides unified access to French enterprise data from multiple official sources including INSEE, Banque de France, and INPI. Firmia streamlines business intelligence by consolidating French company data into a single, powerful interface.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Available Tools](#available-tools)
- [API Response Examples](#api-response-examples)
- [Architecture](#architecture)
- [Data Sources](#data-sources)
- [Performance](#performance)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

- 🏢 **Multi-Source Integration**: Access data from INSEE, Banque de France, and INPI through a single interface
- 🔍 **Enterprise Search**: Search by name, SIREN, or SIRET across all data sources
- 📊 **Comprehensive Data**: Get company information, financials, and intellectual property data
- ⚡ **Performance Optimized**: Built-in caching and rate limiting for optimal performance
- 🔒 **Type-Safe**: Full TypeScript support with strict type checking
- 🛡️ **Error Handling**: Robust error handling with detailed error messages
- 🔄 **Automatic Retries**: Smart retry logic for transient failures
- 📈 **Rate Limit Management**: Intelligent quota management across APIs

## Installation

### Prerequisites
- Node.js 18.0.0 or higher
- npm 8.0.0 or higher
- MCP client (Claude Desktop, VS Code extension, or other MCP-compatible client)

### Step-by-Step Installation

1. **Clone the repository**
```bash
git clone https://github.com/bacoco/Firmia.git
cd Firmia
```

2. **Install dependencies**
```bash
npm install
```

3. **Configure environment variables**
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API credentials
# See Configuration section for details
```

4. **Build the project**
```bash
npm run build
```

5. **Add to your MCP client configuration**

For Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "firmia": {
      "command": "node",
      "args": ["/path/to/Firmia/dist/index.js"],
      "env": {
        "NODE_ENV": "production"
      }
    }
  }
}
```

## Configuration

### Obtaining API Keys

#### 1. INSEE API
1. Visit [INSEE Developer Portal](https://api.insee.fr)
2. Create an account (free)
3. Create a new application
4. Subscribe to the "Sirene - V3" API
5. Copy your Consumer Key and Consumer Secret

#### 2. Banque de France API
1. Contact Banque de France at [webstat@banque-france.fr](mailto:webstat@banque-france.fr)
2. Request access to their enterprise data API
3. You'll receive credentials via secure email

#### 3. INPI API
1. Visit [INPI Data Portal](https://data.inpi.fr)
2. Create a developer account
3. Request API access for:
   - Trademark database
   - Patent database
   - Design database
4. Note your API key and client credentials

### Environment Variables

Create a `.env` file with the following configuration:

```env
# INSEE API Configuration
INSEE_API_KEY=your_insee_api_key
INSEE_API_URL=https://api.insee.fr/entreprises/sirene/V3

# Banque de France API Configuration
BANQUE_FRANCE_API_KEY=your_api_key
BANQUE_FRANCE_USERNAME=your_username
BANQUE_FRANCE_PASSWORD=your_password
BANQUE_FRANCE_API_URL=https://api.banque-france.fr

# INPI API Configuration
INPI_API_KEY=your_api_key
INPI_CLIENT_ID=your_client_id
INPI_CLIENT_SECRET=your_client_secret
INPI_API_URL=https://api.inpi.fr

# Cache Configuration
CACHE_TTL=3600                    # Cache time-to-live in seconds (default: 1 hour)
CACHE_CHECK_PERIOD=600            # Cache cleanup interval in seconds

# Rate Limiting Configuration (requests per hour)
RATE_LIMIT_INSEE=5000             # INSEE API rate limit
RATE_LIMIT_BANQUE_FRANCE=1000    # Banque de France API rate limit
RATE_LIMIT_INPI=2000              # INPI API rate limit

# MCP Server Configuration
MCP_SERVER_NAME=firmia
MCP_SERVER_VERSION=1.0.0
MCP_LOG_LEVEL=info                # Options: debug, info, warn, error

# Development Settings
NODE_ENV=development              # Options: development, production
DEBUG=firmia:*                    # Enable debug logging
```

## Usage

### Starting the Server

```bash
# Development mode with hot reload
npm run dev

# Production mode
npm run build
npm start

# With custom environment file
NODE_ENV=production npm start
```

### Testing the Connection

Once the server is running, you can test it using the MCP client:

```json
{
  "tool": "get_api_status",
  "params": {}
}
```

## Available Tools

### 1. search_enterprises

Search for French enterprises across multiple data sources.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | Yes | - | Enterprise name or SIREN/SIRET number |
| source | enum | No | "all" | Data source: "all", "insee", "banque-france", "inpi" |
| includeHistory | boolean | No | false | Include historical data |
| maxResults | number | No | 10 | Maximum results (1-100) |

**Example Request:**
```json
{
  "tool": "search_enterprises",
  "params": {
    "query": "Airbus",
    "source": "all",
    "includeHistory": false,
    "maxResults": 5
  }
}
```

### 2. get_enterprise_details

Get detailed information about a specific enterprise by SIREN.

**Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| siren | string | Yes | - | 9-digit SIREN number |
| source | enum | No | "all" | Data source: "all", "insee", "banque-france", "inpi" |
| includeFinancials | boolean | No | true | Include financial data |
| includeIntellectualProperty | boolean | No | true | Include IP data |

**Example Request:**
```json
{
  "tool": "get_enterprise_details",
  "params": {
    "siren": "383474814",
    "source": "all",
    "includeFinancials": true,
    "includeIntellectualProperty": true
  }
}
```

### 3. get_api_status

Check the status and rate limits of connected APIs.

**Example Request:**
```json
{
  "tool": "get_api_status",
  "params": {}
}
```

## API Response Examples

### Search Response
```json
{
  "success": true,
  "results": [
    {
      "source": "insee",
      "data": [
        {
          "siren": "383474814",
          "name": "AIRBUS",
          "legalForm": "Société européenne",
          "address": {
            "street": "2 ROND POINT EMILE DEWOITINE",
            "postalCode": "31700",
            "city": "BLAGNAC"
          },
          "activity": {
            "code": "30.30Z",
            "description": "Construction aéronautique et spatiale"
          },
          "employees": 5000,
          "creationDate": "1970-01-01"
        }
      ]
    },
    {
      "source": "banque-france",
      "data": [
        {
          "siren": "383474814",
          "name": "AIRBUS",
          "rating": "AAA",
          "lastFinancialYear": 2023
        }
      ]
    }
  ]
}
```

### Enterprise Details Response
```json
{
  "success": true,
  "siren": "383474814",
  "details": {
    "insee": {
      "identification": {
        "siren": "383474814",
        "name": "AIRBUS",
        "tradeName": "AIRBUS COMMERCIAL AIRCRAFT",
        "legalForm": "Société européenne",
        "registrationDate": "1970-01-01",
        "capital": 2704000
      },
      "establishments": [
        {
          "siret": "38347481400048",
          "isHeadOffice": true,
          "address": {
            "street": "2 ROND POINT EMILE DEWOITINE",
            "postalCode": "31700",
            "city": "BLAGNAC"
          }
        }
      ]
    },
    "banque-france": {
      "financials": [
        {
          "year": 2023,
          "revenue": 65446000000,
          "netIncome": 3789000000,
          "totalAssets": 138503000000,
          "employees": 134267
        }
      ],
      "rating": {
        "score": "AAA",
        "outlook": "Stable",
        "lastUpdate": "2024-01-15"
      }
    },
    "inpi": {
      "trademarks": [
        {
          "id": "4234567",
          "name": "AIRBUS",
          "classes": [12, 39, 42],
          "registrationDate": "2010-03-15",
          "status": "active"
        }
      ],
      "patents": [
        {
          "id": "EP2234567",
          "title": "Aircraft wing optimization system",
          "applicationDate": "2019-06-20",
          "status": "granted"
        }
      ]
    }
  }
}
```

### Error Response Example
```json
{
  "success": false,
  "error": "ENTERPRISE_NOT_FOUND",
  "details": {
    "message": "No enterprise found with SIREN: 123456789",
    "suggestions": ["Did you mean: 123456788?"]
  }
}
```

## Architecture

```
mcp-firms/
├── src/
│   ├── index.ts              # MCP server entry point
│   ├── adapters/             # API adapters for each data source
│   │   ├── index.ts          # Adapter factory and interfaces
│   │   ├── insee.ts          # INSEE API adapter
│   │   ├── banque-france.ts  # Banque de France adapter
│   │   └── inpi.ts           # INPI adapter
│   ├── cache/                # Caching layer
│   │   └── index.ts          # Cache implementation
│   ├── rate-limiter/         # Rate limiting implementation
│   │   └── index.ts          # Rate limiter with per-API quotas
│   ├── types/                # TypeScript type definitions
│   │   └── index.ts          # Shared types and interfaces
│   └── utils/                # Utility functions
│       └── index.ts          # Helper functions
├── tests/                    # Test suite
│   ├── adapters/            # Adapter tests
│   ├── integration/         # Integration tests
│   └── utils.test.ts        # Utility tests
├── docs/                     # Documentation
│   ├── API.md               # API adapter documentation
│   ├── CONTRIBUTING.md      # Contribution guidelines
│   └── examples/            # Usage examples
└── dist/                    # Compiled JavaScript (generated)
```

## Data Sources

### INSEE (Institut National de la Statistique et des Études Économiques)
- **Data Coverage**: All French enterprises and establishments
- **Update Frequency**: Daily
- **Key Data Points**:
  - Company identification (SIREN/SIRET)
  - Legal information and structure
  - Business classification (NAF/APE codes)
  - Establishment locations and employees
  - Administrative status and changes

### Banque de France
- **Data Coverage**: Companies with significant economic activity
- **Update Frequency**: Quarterly
- **Key Data Points**:
  - Financial statements (3-5 years history)
  - Credit ratings and risk assessment
  - Banking relationships
  - Economic indicators
  - Payment behavior

### INPI (Institut National de la Propriété Industrielle)
- **Data Coverage**: All IP registrations in France
- **Update Frequency**: Weekly
- **Key Data Points**:
  - Trademarks (national and EU)
  - Patents (French and European)
  - Industrial designs
  - Company registrations
  - IP litigation history

## Performance

### Caching Strategy
- **In-memory cache** with configurable TTL
- **Cache key format**: `source:operation:params`
- **Default TTL**: 1 hour (configurable)
- **Cache invalidation**: Automatic based on TTL

### Rate Limiting
- **Per-API rate limits** with configurable quotas
- **Token bucket algorithm** for smooth rate limiting
- **Automatic retry** with exponential backoff
- **Rate limit headers** passed to response

### Response Times
- **Cached responses**: < 10ms
- **INSEE API**: 200-500ms
- **Banque de France API**: 300-800ms
- **INPI API**: 400-1000ms
- **Multi-source queries**: Parallel execution

## Development

### Prerequisites
- Node.js 18+ with TypeScript support
- Git for version control
- API keys for testing

### Setup Development Environment
```bash
# Clone the repository
git clone https://github.com/bacoco/Firmia.git
cd Firmia

# Install dependencies
npm install

# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Lint code
npm run lint

# Type checking
npm run typecheck

# Run in development mode
npm run dev
```

### Project Scripts
- `npm run build` - Build TypeScript to JavaScript
- `npm run dev` - Run with hot reload
- `npm test` - Run test suite
- `npm run test:watch` - Run tests in watch mode
- `npm run test:coverage` - Generate coverage report
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix linting issues
- `npm run typecheck` - Run TypeScript compiler check

## Troubleshooting

### Common Issues

#### 1. Authentication Errors
**Problem**: `AUTHENTICATION_FAILED` error
**Solution**: 
- Verify API keys in `.env` file
- Check API key permissions
- Ensure keys are not expired

#### 2. Rate Limit Exceeded
**Problem**: `RATE_LIMIT_EXCEEDED` error
**Solution**:
- Wait for rate limit reset (shown in response)
- Reduce request frequency
- Increase cache TTL
- Configure lower rate limits in `.env`

#### 3. Enterprise Not Found
**Problem**: `ENTERPRISE_NOT_FOUND` error
**Solution**:
- Verify SIREN format (9 digits)
- Check if company is registered in France
- Try searching by name instead

#### 4. Connection Issues
**Problem**: `SERVICE_UNAVAILABLE` error
**Solution**:
- Check internet connection
- Verify API endpoints are accessible
- Check if APIs are under maintenance

#### 5. Cache Issues
**Problem**: Stale or incorrect data
**Solution**:
- Restart the server to clear cache
- Reduce cache TTL for frequently updated data
- Check cache configuration

### Debug Mode

Enable debug logging for troubleshooting:
```bash
DEBUG=firmia:* npm run dev
```

This will show:
- API request/response details
- Cache hit/miss information
- Rate limiting decisions
- Error stack traces

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for details on:
- Setting up development environment
- Code style guidelines
- Adding new API adapters
- Submitting pull requests
- Reporting issues

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- INSEE for providing the SIRENE API
- Banque de France for financial data access
- INPI for intellectual property data
- The MCP community for the protocol specification
- Contributors and maintainers

## Support

- 📧 Email: support@firmia.dev
- 💬 Discord: [Join our server](https://discord.gg/firmia)
- 🐛 Issues: [GitHub Issues](https://github.com/bacoco/Firmia/issues)
- 📖 Wiki: [Documentation Wiki](https://github.com/bacoco/Firmia/wiki)