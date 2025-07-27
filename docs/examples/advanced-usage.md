# Advanced Usage Examples

This document provides advanced examples and patterns for using the MCP Firms API effectively.

## Table of Contents
- [Batch Processing](#batch-processing)
- [Cross-Source Data Enrichment](#cross-source-data-enrichment)
- [Financial Analysis](#financial-analysis)
- [IP Portfolio Analysis](#ip-portfolio-analysis)
- [Competitive Intelligence](#competitive-intelligence)
- [Performance Optimization](#performance-optimization)

## Batch Processing

### Processing Multiple Companies

```javascript
// Example: Analyze multiple competitors
const competitors = [
  "383474814", // Airbus
  "552100554", // Dassault Aviation
  "338368992", // Thales
  "562082909", // Safran
];

const results = [];

for (const siren of competitors) {
  try {
    const response = await mcpClient.call({
      tool: "get_enterprise_details",
      params: {
        siren: siren,
        source: "all",
        includeFinancials: true,
        includeIntellectualProperty: true
      }
    });
    
    if (response.success) {
      results.push(response);
    }
  } catch (error) {
    console.error(`Failed to fetch ${siren}:`, error);
  }
  
  // Add delay to respect rate limits
  await new Promise(resolve => setTimeout(resolve, 100));
}
```

### Parallel Processing with Rate Limit Management

```javascript
// Process in batches with concurrency control
async function batchProcess(sirens, batchSize = 5) {
  const results = [];
  
  for (let i = 0; i < sirens.length; i += batchSize) {
    const batch = sirens.slice(i, i + batchSize);
    
    const batchPromises = batch.map(siren => 
      mcpClient.call({
        tool: "get_enterprise_details",
        params: { siren, source: "insee" }
      }).catch(error => ({ error, siren }))
    );
    
    const batchResults = await Promise.all(batchPromises);
    results.push(...batchResults);
    
    // Rate limit pause between batches
    if (i + batchSize < sirens.length) {
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
  
  return results;
}
```

## Cross-Source Data Enrichment

### Complete Company Profile

```javascript
async function getCompleteCompanyProfile(siren) {
  // Step 1: Get basic information from INSEE
  const inseeData = await mcpClient.call({
    tool: "get_enterprise_details",
    params: {
      siren: siren,
      source: "insee"
    }
  });

  // Step 2: Get financial data from Banque de France
  const financialData = await mcpClient.call({
    tool: "get_enterprise_details",
    params: {
      siren: siren,
      source: "banque-france",
      includeFinancials: true
    }
  });

  // Step 3: Get IP data from INPI
  const ipData = await mcpClient.call({
    tool: "get_enterprise_details",
    params: {
      siren: siren,
      source: "inpi",
      includeIntellectualProperty: true
    }
  });

  // Combine all data
  return {
    siren: siren,
    identification: inseeData.details.insee.identification,
    establishments: inseeData.details.insee.establishments,
    financials: financialData.details['banque-france'].financials,
    rating: financialData.details['banque-france'].rating,
    intellectualProperty: ipData.details.inpi,
    lastUpdated: new Date().toISOString()
  };
}
```

### Data Validation Across Sources

```javascript
async function validateCompanyData(siren) {
  const sources = ['insee', 'banque-france', 'inpi'];
  const data = {};
  
  // Fetch from all sources
  for (const source of sources) {
    try {
      const response = await mcpClient.call({
        tool: "get_enterprise_details",
        params: { siren, source }
      });
      
      if (response.success) {
        data[source] = response.details[source];
      }
    } catch (error) {
      data[source] = { error: error.message };
    }
  }
  
  // Cross-validate data
  const validation = {
    siren: siren,
    nameConsistency: validateNames(data),
    addressConsistency: validateAddresses(data),
    activityConsistency: validateActivities(data),
    dataCompleteness: calculateCompleteness(data)
  };
  
  return validation;
}
```

## Financial Analysis

### Multi-Year Financial Trend Analysis

```javascript
async function analyzeFinancialTrends(siren) {
  const response = await mcpClient.call({
    tool: "get_enterprise_details",
    params: {
      siren: siren,
      source: "banque-france",
      includeFinancials: true
    }
  });

  if (!response.success) {
    throw new Error(response.error);
  }

  const financials = response.details['banque-france'].financials;
  
  // Calculate key metrics
  const analysis = {
    siren: siren,
    revenueGrowth: calculateCAGR(financials, 'revenue'),
    profitability: financials.map(f => ({
      year: f.year,
      margin: (f.netIncome / f.revenue) * 100
    })),
    leverage: financials.map(f => ({
      year: f.year,
      debtToEquity: f.debt / f.equity
    })),
    efficiency: financials.map(f => ({
      year: f.year,
      assetTurnover: f.revenue / f.totalAssets
    }))
  };
  
  return analysis;
}

function calculateCAGR(financials, metric) {
  const sorted = financials.sort((a, b) => a.year - b.year);
  const firstYear = sorted[0];
  const lastYear = sorted[sorted.length - 1];
  const years = lastYear.year - firstYear.year;
  
  return Math.pow(lastYear[metric] / firstYear[metric], 1/years) - 1;
}
```

### Peer Comparison

```javascript
async function comparePeers(sirens) {
  const peerData = await Promise.all(
    sirens.map(siren => 
      mcpClient.call({
        tool: "get_enterprise_details",
        params: {
          siren,
          source: "all",
          includeFinancials: true
        }
      })
    )
  );

  // Extract latest financial data
  const comparison = peerData
    .filter(r => r.success)
    .map(r => {
      const latestFinancials = r.details['banque-france']?.financials?.[0];
      return {
        siren: r.siren,
        name: r.details.insee?.identification?.name,
        revenue: latestFinancials?.revenue,
        profitMargin: (latestFinancials?.netIncome / latestFinancials?.revenue) * 100,
        rating: r.details['banque-france']?.rating?.score,
        employees: latestFinancials?.employees
      };
    });

  // Rank by various metrics
  return {
    byRevenue: [...comparison].sort((a, b) => b.revenue - a.revenue),
    byProfitability: [...comparison].sort((a, b) => b.profitMargin - a.profitMargin),
    byEmployees: [...comparison].sort((a, b) => b.employees - a.employees)
  };
}
```

## IP Portfolio Analysis

### Comprehensive IP Assessment

```javascript
async function analyzeIPPortfolio(siren) {
  const response = await mcpClient.call({
    tool: "get_enterprise_details",
    params: {
      siren: siren,
      source: "inpi",
      includeIntellectualProperty: true
    }
  });

  if (!response.success) {
    throw new Error(response.error);
  }

  const ip = response.details.inpi;
  
  return {
    siren: siren,
    portfolio: {
      trademarks: {
        total: ip.trademarks?.length || 0,
        active: ip.trademarks?.filter(t => t.status === 'active').length || 0,
        byClass: groupTrademarksByClass(ip.trademarks || [])
      },
      patents: {
        total: ip.patents?.length || 0,
        granted: ip.patents?.filter(p => p.status === 'granted').length || 0,
        pending: ip.patents?.filter(p => p.status === 'pending').length || 0,
        recentApplications: ip.patents?.filter(p => 
          new Date(p.applicationDate) > new Date(Date.now() - 365*24*60*60*1000)
        ).length || 0
      },
      designs: {
        total: ip.designs?.length || 0,
        active: ip.designs?.filter(d => d.status === 'active').length || 0
      }
    },
    valuation: estimateIPValue(ip)
  };
}

function groupTrademarksByClass(trademarks) {
  const byClass = {};
  trademarks.forEach(tm => {
    tm.classes.forEach(cls => {
      byClass[cls] = (byClass[cls] || 0) + 1;
    });
  });
  return byClass;
}
```

## Competitive Intelligence

### Industry Analysis

```javascript
async function analyzeIndustry(activityCode, maxCompanies = 50) {
  // Search for companies in the same industry
  const searchResponse = await mcpClient.call({
    tool: "search_enterprises",
    params: {
      query: activityCode,
      maxResults: maxCompanies,
      source: "insee"
    }
  });

  if (!searchResponse.success) {
    throw new Error(searchResponse.error);
  }

  const companies = searchResponse.results[0].data;
  
  // Get detailed data for top companies
  const detailedData = await Promise.all(
    companies.slice(0, 10).map(company =>
      mcpClient.call({
        tool: "get_enterprise_details",
        params: {
          siren: company.siren,
          source: "banque-france",
          includeFinancials: true
        }
      })
    )
  );

  // Analyze industry metrics
  const industryMetrics = {
    activityCode: activityCode,
    totalCompanies: companies.length,
    averageSize: calculateAverageSize(companies),
    topPlayers: detailedData
      .filter(r => r.success)
      .map(r => ({
        siren: r.siren,
        name: companies.find(c => c.siren === r.siren)?.name,
        revenue: r.details['banque-france']?.financials?.[0]?.revenue,
        marketShare: null // To be calculated
      }))
      .sort((a, b) => (b.revenue || 0) - (a.revenue || 0))
  };

  // Calculate market shares
  const totalRevenue = industryMetrics.topPlayers
    .reduce((sum, company) => sum + (company.revenue || 0), 0);
  
  industryMetrics.topPlayers.forEach(company => {
    if (company.revenue) {
      company.marketShare = (company.revenue / totalRevenue) * 100;
    }
  });

  return industryMetrics;
}
```

## Performance Optimization

### Caching Strategy

```javascript
class MCPFirmsClient {
  constructor() {
    this.cache = new Map();
    this.cacheTimeout = 3600000; // 1 hour
  }

  async cachedCall(params) {
    const cacheKey = JSON.stringify(params);
    const cached = this.cache.get(cacheKey);
    
    if (cached && cached.timestamp > Date.now() - this.cacheTimeout) {
      return cached.data;
    }
    
    const response = await mcpClient.call(params);
    
    if (response.success) {
      this.cache.set(cacheKey, {
        data: response,
        timestamp: Date.now()
      });
    }
    
    return response;
  }
  
  clearCache() {
    this.cache.clear();
  }
}
```

### Rate Limit Management

```javascript
class RateLimitManager {
  constructor() {
    this.limits = {
      insee: { max: 5000, current: 0, reset: Date.now() + 3600000 },
      'banque-france': { max: 1000, current: 0, reset: Date.now() + 3600000 },
      inpi: { max: 2000, current: 0, reset: Date.now() + 3600000 }
    };
  }

  async checkAndWait(source) {
    const limit = this.limits[source];
    
    // Reset if hour has passed
    if (Date.now() > limit.reset) {
      limit.current = 0;
      limit.reset = Date.now() + 3600000;
    }
    
    // Check if limit reached
    if (limit.current >= limit.max * 0.9) { // 90% threshold
      const waitTime = limit.reset - Date.now();
      console.log(`Rate limit approaching for ${source}, waiting ${waitTime}ms`);
      await new Promise(resolve => setTimeout(resolve, waitTime));
      limit.current = 0;
      limit.reset = Date.now() + 3600000;
    }
    
    limit.current++;
  }

  async callWithRateLimit(params) {
    const source = params.params.source || 'all';
    
    if (source === 'all') {
      // Check all sources
      await Promise.all([
        this.checkAndWait('insee'),
        this.checkAndWait('banque-france'),
        this.checkAndWait('inpi')
      ]);
    } else {
      await this.checkAndWait(source);
    }
    
    return mcpClient.call(params);
  }
}
```

### Error Recovery

```javascript
async function callWithRetry(params, maxRetries = 3) {
  let lastError;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await mcpClient.call(params);
      
      if (response.success) {
        return response;
      }
      
      // Handle specific errors
      if (response.error === 'RATE_LIMIT_EXCEEDED') {
        const waitTime = response.details.retryAfter * 1000;
        console.log(`Rate limit hit, waiting ${waitTime}ms`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
        continue;
      }
      
      if (response.error === 'SERVICE_UNAVAILABLE' && attempt < maxRetries) {
        const backoff = Math.pow(2, attempt) * 1000;
        console.log(`Service unavailable, retrying in ${backoff}ms`);
        await new Promise(resolve => setTimeout(resolve, backoff));
        continue;
      }
      
      // Non-retryable error
      return response;
      
    } catch (error) {
      lastError = error;
      if (attempt < maxRetries) {
        const backoff = Math.pow(2, attempt) * 1000;
        console.log(`Error occurred, retrying in ${backoff}ms`);
        await new Promise(resolve => setTimeout(resolve, backoff));
      }
    }
  }
  
  throw lastError || new Error('Max retries exceeded');
}
```

## Best Practices Summary

1. **Batch Operations**: Process multiple requests together
2. **Cache Results**: Implement local caching for frequently accessed data
3. **Handle Rate Limits**: Implement backoff and retry strategies
4. **Cross-Validate**: Use multiple sources to ensure data accuracy
5. **Monitor Performance**: Track API response times and adjust strategies
6. **Error Recovery**: Implement robust error handling and retry logic
7. **Data Enrichment**: Combine data from multiple sources for comprehensive insights