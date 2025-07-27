# Banque de France Adapter

## Overview

The Banque de France adapter provides integration with the Banque de France Webstat API to access financial data about French companies. This includes financial statements, credit ratings, and payment incident information.

## Features

- **Financial Statements**: Access to the last 3 annual financial statements for companies
- **Credit Ratings**: Retrieve Banque de France credit ratings and risk assessments
- **Payment Incidents**: Check for any recorded payment incidents
- **Caching**: Intelligent caching of API responses to minimize API calls
- **Rate Limiting**: Built-in rate limiting to respect API quotas

## Configuration

### Environment Variables

```bash
BANQUE_FRANCE_API_KEY=your_api_key_here
```

To obtain an API key:
1. Register at https://developer.webstat.banque-france.fr/
2. Create an account and verify your email
3. Access your dashboard to generate API credentials

## Usage

### Search by SIREN

The adapter primarily works with SIREN numbers (9-digit company identifiers):

```typescript
const results = await adapter.search("123456789", {
  maxResults: 10
});
```

**Note**: Text-based searches are not supported as the Banque de France API is designed for lookup by SIREN only.

### Get Company Details

Retrieve detailed financial information for a company:

```typescript
const details = await adapter.getDetails("123456789", {
  includeFinancials: true
});
```

This returns:
- Basic company information
- Latest financial data (revenue, employees)
- Extended financial data (when includeFinancials is true):
  - Last 3 annual financial statements
  - Credit rating and risk assessment
  - Payment incidents history

## API Endpoints Used

The adapter integrates with the following Banque de France API endpoints:

1. **Financial Statements**: `/entreprises/bilans/{siren}/derniers`
   - Returns the last 3 annual financial statements
   - Includes revenue, assets, equity, debt, and employee count

2. **Credit Rating**: `/entreprises/cotation/{siren}`
   - Provides the Banque de France credit rating
   - Ratings range from 3++ (excellent) to 9 (payment incidents)
   - Includes risk level assessment

3. **Payment Incidents**: `/entreprises/incidents-paiement/{siren}`
   - Lists any recorded payment incidents
   - Includes date, amount, type, and status

4. **Health Check**: `/health`
   - Used to verify API availability

## Data Structures

### Credit Rating Scale

The Banque de France uses the following rating scale:

- **3++**: Excellent
- **3+**: Very Good
- **3**: Good
- **4+**: Satisfactory
- **4**: Fair
- **5+**: Weak
- **5**: Poor
- **6**: Very Poor
- **7**: Major Risk
- **8**: Threatened
- **9**: Payment Incidents

### Extended Financial Data

When `includeFinancials` is true, the response includes an `extendedFinancials` object:

```typescript
{
  statements: [
    {
      year: 2023,
      revenue: 1000000,
      netIncome: 100000,
      totalAssets: 2000000,
      equity: 500000,
      debt: 300000,
      employees: 50
    }
    // ... more years
  ],
  creditRating: {
    rating: "4+",
    date: "2024-01-15",
    score: 75,
    riskLevel: "Satisfactory"
  },
  paymentIncidents: [
    {
      date: "2023-06-01",
      amount: 5000,
      type: "late_payment",
      status: "resolved"
    }
  ]
}
```

## Error Handling

The adapter handles the following error scenarios:

- **404 Not Found**: Returns empty results/data when a company is not found
- **401 Unauthorized**: Throws error indicating invalid API key
- **429 Rate Limit**: Handled by the rate limiter before making requests
- **Network Errors**: Propagated with descriptive error messages

## Rate Limits

The exact rate limits are determined by your Banque de France API subscription tier. The adapter uses the configured rate limiter to ensure compliance with these limits.

## Caching

All responses are cached for 1 hour (3600 seconds) to:
- Reduce API calls for repeated queries
- Improve response times
- Stay within rate limits

Cache keys include the query parameters to ensure proper cache invalidation when options change.

## Integration with MCP

The adapter follows the BaseAdapter interface and integrates seamlessly with the MCP connector system:

```typescript
const adapters = setupAdapters({
  rateLimiter: rateLimiterInstance,
  cache: cacheInstance
});

const banqueFranceAdapter = adapters["banque-france"];
```

## Security Considerations

- API keys should never be hardcoded
- Always use environment variables for sensitive credentials
- The adapter warns if the API key is not configured
- All API calls use HTTPS with proper authorization headers

## Limitations

1. **SIREN-only Search**: The API only supports lookup by SIREN, not by company name
2. **French Companies Only**: Limited to companies registered in France
3. **Data Availability**: Not all companies have financial data in the Banque de France system
4. **Historical Data**: Limited to the last 3 annual statements

## Future Enhancements

Potential improvements for the adapter:

1. Support for statistical series endpoints
2. Regional economic data integration
3. Batch SIREN lookup capabilities
4. Webhook support for data updates
5. Integration with other Banque de France APIs