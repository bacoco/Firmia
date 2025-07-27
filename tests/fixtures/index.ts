/**
 * Test fixtures for French company data
 * Based on real company information but may be modified for testing purposes
 */

export const mockCompanies = {
  danone: {
    siren: "552032534",
    siret: "55203253400041",
    name: "DANONE",
    legalForm: "5710", // SA à conseil d'administration
    address: "17 BOULEVARD HAUSSMANN 75009 PARIS",
    activity: "70.10Z", // Activités des sièges sociaux
    creationDate: "1955-01-01",
    status: "A", // Active
    employees: "10000 salariés ou plus",
    capital: 166786720
  },
  airbus: {
    siren: "383474814",
    siret: "38347481400011",
    name: "AIRBUS",
    legalForm: "5499", // Société européenne
    address: "2 ROND-POINT EMILE DEWOITINE 31700 BLAGNAC",
    activity: "30.30Z", // Construction aéronautique et spatiale
    creationDate: "1992-07-01",
    status: "A",
    employees: "10000 salariés ou plus",
    capital: 3217113851
  },
  carrefour: {
    siren: "652014051",
    siret: "65201405100031",
    name: "CARREFOUR",
    legalForm: "5710",
    address: "93 AVENUE DE PARIS 91300 MASSY",
    activity: "70.10Z",
    creationDate: "1959-07-11",
    status: "A",
    employees: "10000 salariés ou plus",
    capital: 1929696016
  },
  startup: {
    siren: "881234567",
    siret: "88123456700014",
    name: "FRENCH TECH STARTUP",
    legalForm: "5710",
    address: "42 RUE DE LA STARTUP 75001 PARIS",
    activity: "62.01Z", // Programmation informatique
    creationDate: "2020-01-15",
    status: "A",
    employees: "6 à 9 salariés",
    capital: 10000
  }
};

export const mockINSEEResponses = {
  searchByName: {
    unitesLegales: [
      {
        siren: mockCompanies.danone.siren,
        siretSiegeSocial: mockCompanies.danone.siret,
        denominationUniteLegale: mockCompanies.danone.name,
        categorieJuridiqueUniteLegale: mockCompanies.danone.legalForm,
        adresseSiegeUniteLegale: {
          numeroVoieEtablissement: "17",
          typeVoieEtablissement: "BOULEVARD",
          libelleVoieEtablissement: "HAUSSMANN",
          codePostalEtablissement: "75009",
          libelleCommuneEtablissement: "PARIS"
        },
        activitePrincipaleUniteLegale: mockCompanies.danone.activity,
        dateCreationUniteLegale: mockCompanies.danone.creationDate,
        etatAdministratifUniteLegale: mockCompanies.danone.status,
        trancheEffectifsUniteLegale: mockCompanies.danone.employees
      }
    ]
  },
  searchBySiren: {
    uniteLegale: {
      siren: mockCompanies.danone.siren,
      denominationUniteLegale: mockCompanies.danone.name,
      categorieJuridiqueUniteLegale: mockCompanies.danone.legalForm,
      adresseSiegeUniteLegale: {
        numeroVoieEtablissement: "17",
        typeVoieEtablissement: "BOULEVARD",
        libelleVoieEtablissement: "HAUSSMANN",
        codePostalEtablissement: "75009",
        libelleCommuneEtablissement: "PARIS"
      },
      activitePrincipaleUniteLegale: mockCompanies.danone.activity,
      dateCreationUniteLegale: mockCompanies.danone.creationDate,
      etatAdministratifUniteLegale: mockCompanies.danone.status,
      trancheEffectifsUniteLegale: mockCompanies.danone.employees,
      dateDernierTraitementUniteLegale: "2024-01-15"
    }
  },
  notFound: {
    fault: {
      code: "CLIENT",
      message: "Aucune unité légale ne correspond aux critères de recherche",
      description: "Not Found"
    }
  },
  unauthorized: {
    fault: {
      code: "UNAUTHORIZED",
      message: "Jeton invalide",
      description: "Invalid token"
    }
  },
  rateLimit: {
    fault: {
      code: "RATE_LIMIT",
      message: "Nombre d'appels à l'API dépassé",
      description: "Too many requests"
    }
  }
};

export const mockBanqueFranceResponses = {
  searchResult: {
    enterprises: [
      {
        siren: mockCompanies.danone.siren,
        name: mockCompanies.danone.name,
        financials: {
          turnover: 27661000000,
          netIncome: 1851000000,
          equity: 15821000000,
          debt: 11840000000,
          year: 2023
        },
        rating: {
          score: "3++",
          trend: "stable",
          lastUpdate: "2024-01-15"
        }
      }
    ]
  },
  detailsResult: {
    siren: mockCompanies.danone.siren,
    name: mockCompanies.danone.name,
    financials: {
      current: {
        turnover: 27661000000,
        netIncome: 1851000000,
        equity: 15821000000,
        debt: 11840000000,
        ebitda: 4338000000,
        employees: 95947,
        year: 2023
      },
      history: [
        {
          year: 2022,
          turnover: 27661000000,
          netIncome: 950000000,
          equity: 14942000000
        },
        {
          year: 2021,
          turnover: 24281000000,
          netIncome: 1922000000,
          equity: 13982000000
        }
      ]
    },
    rating: {
      score: "3++",
      trend: "stable",
      methodology: "Banque de France FIBEN",
      factors: {
        profitability: "A",
        liquidity: "A",
        solvency: "B"
      },
      lastUpdate: "2024-01-15"
    }
  }
};

export const mockINPIResponses = {
  searchResult: {
    trademarks: [
      {
        number: "4512345",
        name: "DANONE",
        owner: mockCompanies.danone.name,
        siren: mockCompanies.danone.siren,
        classes: ["29", "30", "32"],
        status: "Enregistrée",
        filingDate: "2019-01-15",
        registrationDate: "2019-07-15",
        expiryDate: "2029-01-15"
      },
      {
        number: "4567890",
        name: "ACTIVIA",
        owner: mockCompanies.danone.name,
        siren: mockCompanies.danone.siren,
        classes: ["29"],
        status: "Enregistrée",
        filingDate: "2020-03-20",
        registrationDate: "2020-09-20",
        expiryDate: "2030-03-20"
      }
    ],
    patents: [
      {
        number: "FR3012345",
        title: "Procédé de fermentation lactique amélioré",
        owner: mockCompanies.danone.name,
        siren: mockCompanies.danone.siren,
        inventors: ["Jean Dupont", "Marie Martin"],
        filingDate: "2021-06-15",
        publicationDate: "2023-01-15",
        status: "Délivré"
      }
    ]
  },
  detailsResult: {
    siren: mockCompanies.danone.siren,
    intellectualProperty: {
      trademarks: {
        total: 245,
        active: 198,
        pending: 12,
        expired: 35
      },
      patents: {
        total: 89,
        active: 67,
        pending: 8,
        expired: 14
      },
      designs: {
        total: 34,
        active: 28,
        pending: 2,
        expired: 4
      }
    },
    portfolio: {
      mainBrands: ["DANONE", "ACTIVIA", "EVIAN", "ACTIMEL", "ALPRO"],
      technologicalDomains: ["Fermentation", "Nutrition", "Packaging", "Probiotics"],
      geographicalCoverage: ["France", "EU", "USA", "China", "Brazil"]
    }
  }
};

export const mockApiErrors = {
  networkError: new Error("Network error: Unable to reach API"),
  timeoutError: new Error("Request timeout after 30000ms"),
  invalidApiKey: new Error("Invalid API key"),
  serverError: new Error("Internal server error (500)"),
  parseError: new Error("Failed to parse API response")
};

export const createMockCache = () => {
  const storage = new Map<string, { value: any; expires: number }>();
  
  return {
    get: jest.fn(async (key: string) => {
      const item = storage.get(key);
      if (!item) return undefined;
      if (Date.now() > item.expires) {
        storage.delete(key);
        return undefined;
      }
      return item.value;
    }),
    set: jest.fn(async (key: string, value: any, ttl: number = 3600) => {
      storage.set(key, {
        value,
        expires: Date.now() + (ttl * 1000)
      });
    }),
    delete: jest.fn(async (key: string) => {
      storage.delete(key);
    }),
    flush: jest.fn(async () => {
      storage.clear();
    }),
    getStats: jest.fn(() => ({
      hits: 0,
      misses: 0,
      keys: storage.size,
      ksize: 0,
      vsize: 0
    }))
  };
};

export const createMockRateLimiter = () => {
  const counters = new Map<string, number>();
  
  return {
    acquire: jest.fn(async (source: string) => {
      const count = counters.get(source) || 0;
      counters.set(source, count + 1);
      // Simulate rate limiting
      if (count > 10) {
        throw new Error("Rate limit exceeded");
      }
    }),
    getStatus: jest.fn(async (source: string) => ({
      remaining: Math.max(0, 10 - (counters.get(source) || 0)),
      reset: new Date(Date.now() + 3600000)
    })),
    reset: jest.fn((source: string) => {
      counters.delete(source);
    })
  };
};