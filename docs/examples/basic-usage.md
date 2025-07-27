# Basic Usage Examples

This document provides basic examples of using the MCP Firms API.

## Table of Contents
- [Setup](#setup)
- [Simple Enterprise Search](#simple-enterprise-search)
- [Get Enterprise Details](#get-enterprise-details)
- [Check API Status](#check-api-status)
- [Error Handling](#error-handling)

## Setup

First, ensure your MCP client is configured to use the mcp-firms server:

```json
{
  "mcpServers": {
    "mcp-firms": {
      "command": "node",
      "args": ["/path/to/mcp-firms/dist/index.js"],
      "env": {
        "NODE_ENV": "production"
      }
    }
  }
}
```

## Simple Enterprise Search

### Search by Company Name

```json
{
  "tool": "search_enterprises",
  "params": {
    "query": "Airbus"
  }
}
```

**Response:**
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
    }
  ]
}
```

### Search by SIREN Number

```json
{
  "tool": "search_enterprises",
  "params": {
    "query": "383474814"
  }
}
```

### Search with Options

```json
{
  "tool": "search_enterprises",
  "params": {
    "query": "technology",
    "maxResults": 20,
    "source": "insee",
    "includeHistory": true
  }
}
```

## Get Enterprise Details

### Basic Details Request

```json
{
  "tool": "get_enterprise_details",
  "params": {
    "siren": "383474814"
  }
}
```

**Response:**
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
    }
  }
}
```

### Details from Specific Source

```json
{
  "tool": "get_enterprise_details",
  "params": {
    "siren": "383474814",
    "source": "banque-france",
    "includeFinancials": true,
    "includeIntellectualProperty": false
  }
}
```

### Complete Details from All Sources

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

## Check API Status

### Basic Status Check

```json
{
  "tool": "get_api_status",
  "params": {}
}
```

**Response:**
```json
{
  "success": true,
  "status": {
    "insee": {
      "available": true,
      "rateLimit": {
        "remaining": 4523,
        "total": 5000,
        "reset": "2024-01-20T15:00:00Z"
      },
      "responseTime": 234,
      "lastCheck": "2024-01-20T14:30:00Z"
    },
    "banque-france": {
      "available": true,
      "rateLimit": {
        "remaining": 876,
        "total": 1000,
        "reset": "2024-01-20T15:00:00Z"
      },
      "responseTime": 456,
      "lastCheck": "2024-01-20T14:30:00Z"
    },
    "inpi": {
      "available": true,
      "rateLimit": {
        "remaining": 1654,
        "total": 2000,
        "reset": "2024-01-20T15:00:00Z"
      },
      "responseTime": 567,
      "lastCheck": "2024-01-20T14:30:00Z"
    }
  }
}
```

## Error Handling

### Invalid SIREN Format

```json
{
  "tool": "get_enterprise_details",
  "params": {
    "siren": "12345"  // Invalid: must be 9 digits
  }
}
```

**Response:**
```json
{
  "success": false,
  "error": "INVALID_SIREN",
  "details": {
    "message": "SIREN must be exactly 9 digits",
    "provided": "12345",
    "expected": "9-digit string"
  }
}
```

### Enterprise Not Found

```json
{
  "tool": "get_enterprise_details",
  "params": {
    "siren": "999999999"
  }
}
```

**Response:**
```json
{
  "success": false,
  "error": "ENTERPRISE_NOT_FOUND",
  "details": {
    "message": "No enterprise found with SIREN: 999999999",
    "suggestions": []
  }
}
```

### Rate Limit Exceeded

```json
{
  "tool": "search_enterprises",
  "params": {
    "query": "test"
  }
}
```

**Response (when rate limited):**
```json
{
  "success": false,
  "error": "RATE_LIMIT_EXCEEDED",
  "details": {
    "message": "Rate limit exceeded for INSEE API",
    "resetTime": "2024-01-20T15:00:00Z",
    "retryAfter": 1800
  }
}
```

## Best Practices

1. **Always check API status** before making multiple requests
2. **Use specific sources** when you only need data from one API
3. **Enable caching** by reusing the same query parameters
4. **Handle errors gracefully** - check for success: false
5. **Respect rate limits** - implement backoff when limits are reached