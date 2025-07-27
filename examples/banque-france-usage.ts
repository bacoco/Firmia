import { BanqueFranceAdapter } from "../src/adapters/banque-france.js";
import { createRateLimiter } from "../src/rate-limiter/index.js";
import { createCache } from "../src/cache/index.js";

// Example usage of the Banque de France adapter
async function main() {
  // Initialize the adapter with rate limiter and cache
  const rateLimiter = createRateLimiter({
    "banque-france": {
      maxRequests: 100,
      perMilliseconds: 60000 // 100 requests per minute
    }
  });

  const cache = createCache({
    ttl: 3600, // 1 hour default TTL
    maxSize: 1000
  });

  const adapter = new BanqueFranceAdapter({
    rateLimiter,
    cache
  });

  try {
    // Example 1: Search by SIREN (9-digit company identifier)
    console.log("=== Example 1: Search by SIREN ===");
    const searchResults = await adapter.search("123456789", {
      maxResults: 5
    });
    
    if (searchResults.length > 0) {
      console.log("Found company:", searchResults[0]);
    } else {
      console.log("No financial data found for this SIREN");
    }

    // Example 2: Get detailed financial information
    console.log("\n=== Example 2: Get Company Details ===");
    const details = await adapter.getDetails("123456789", {
      includeFinancials: true
    });

    console.log("Basic Info:", details.basicInfo);
    
    if (details.financials) {
      console.log("Financial Summary:", details.financials);
    }

    // Access extended financial data (type assertion needed)
    const extendedDetails = details as any;
    if (extendedDetails.extendedFinancials) {
      const { statements, creditRating, paymentIncidents } = extendedDetails.extendedFinancials;
      
      console.log("\n=== Financial Statements (Last 3 Years) ===");
      statements.forEach((statement: any) => {
        console.log(`Year ${statement.year}:`, {
          revenue: statement.revenue,
          employees: statement.employees,
          totalAssets: statement.totalAssets,
          equity: statement.equity
        });
      });

      if (creditRating) {
        console.log("\n=== Credit Rating ===");
        console.log(`Rating: ${creditRating.rating} (${creditRating.riskLevel})`);
        console.log(`Date: ${creditRating.date}`);
        console.log(`Score: ${creditRating.score}`);
      }

      console.log("\n=== Payment Incidents ===");
      if (paymentIncidents.length > 0) {
        paymentIncidents.forEach((incident: any) => {
          console.log(`- ${incident.date}: €${incident.amount} (${incident.type}) - ${incident.status}`);
        });
      } else {
        console.log("No payment incidents recorded");
      }
    }

    // Example 3: Check API status
    console.log("\n=== Example 3: API Status ===");
    const status = await adapter.getStatus();
    console.log("API Available:", status.available);
    if (status.rateLimit) {
      console.log("Rate Limit Remaining:", status.rateLimit.remaining);
      console.log("Rate Limit Reset:", status.rateLimit.reset);
    }

    // Example 4: Batch processing multiple companies
    console.log("\n=== Example 4: Batch Processing ===");
    const sirens = ["123456789", "987654321", "456789123"];
    
    for (const siren of sirens) {
      try {
        const result = await adapter.getDetails(siren, {
          includeFinancials: true
        });
        console.log(`${siren}: ${result.basicInfo.name || "Not found"}`);
      } catch (error) {
        console.error(`Error processing ${siren}:`, error);
      }
    }

  } catch (error) {
    console.error("Error:", error);
  }
}

// Run the example
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(console.error);
}

export { main };