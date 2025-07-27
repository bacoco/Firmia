/**
 * Enhanced mock data fixtures for comprehensive testing
 * Includes realistic French company data, error scenarios, and edge cases
 */

export interface MockCompanyProfile {
  siren: string;
  siret: string;
  name: string;
  legalForm: string;
  address: string;
  activity: string;
  creationDate: string;
  status: string;
  employees: string;
  capital: number;
  industry: string;
  region: string;
  characteristics: string[];
}

export const enhancedMockCompanies: Record<string, MockCompanyProfile> = {
  // Large multinational corporation
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
    capital: 166786720,
    industry: "Agroalimentaire",
    region: "Île-de-France",
    characteristics: ["multinational", "listed", "large", "food_industry"]
  },

  // Aerospace leader
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
    capital: 3217113851,
    industry: "Aéronautique",
    region: "Occitanie",
    characteristics: ["multinational", "listed", "large", "aerospace", "defense"]
  },

  // Retail giant
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
    capital: 1929696016,
    industry: "Commerce",
    region: "Île-de-France",
    characteristics: ["multinational", "listed", "large", "retail", "hypermarkets"]
  },

  // Tech startup
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
    capital: 10000,
    industry: "Technologies",
    region: "Île-de-France",
    characteristics: ["startup", "tech", "small", "innovation"]
  },

  // SME in manufacturing
  sme_manufacturing: {
    siren: "445123789",
    siret: "44512378900012",
    name: "PRECISION MECANIQUE LYON",
    legalForm: "5710",
    address: "15 RUE DE L'INDUSTRIE 69100 VILLEURBANNE",
    activity: "25.73Z", // Fabrication d'outillage
    creationDate: "1998-06-15",
    status: "A",
    employees: "50 à 99 salariés",
    capital: 150000,
    industry: "Métallurgie",
    region: "Auvergne-Rhône-Alpes",
    characteristics: ["sme", "manufacturing", "medium", "regional"]
  },

  // Service company
  consulting: {
    siren: "528456123",
    siret: "52845612300019",
    name: "CONSEIL & STRATEGIES",
    legalForm: "5710",
    address: "10 AVENUE DES CHAMPS-ELYSEES 75008 PARIS",
    activity: "70.22Z", // Conseil pour les affaires et autres conseils de gestion
    creationDate: "2005-03-20",
    status: "A",
    employees: "20 à 49 salariés",
    capital: 50000,
    industry: "Services",
    region: "Île-de-France",
    characteristics: ["services", "consulting", "medium", "business"]
  },

  // Inactive company
  inactive: {
    siren: "123456789",
    siret: "12345678900001",
    name: "ANCIENNE SOCIETE",
    legalForm: "5710",
    address: "1 RUE DU PASSE 75000 PARIS",
    activity: "70.10Z",
    creationDate: "1990-01-01",
    status: "C", // Cessée
    employees: "0 salarié",
    capital: 0,
    industry: "Inconnue",
    region: "Île-de-France",
    characteristics: ["inactive", "closed", "historical"]
  },

  // Edge case: Special characters in name
  special_chars: {
    siren: "999888777",
    siret: "99988877700001",
    name: "L'ENTREPRISE À CARACTÈRES SPÉCIAUX & CIE",
    legalForm: "5710",
    address: "123 RUE DE L'ÉTOILE 75017 PARIS",
    activity: "70.10Z",
    creationDate: "2010-12-31",
    status: "A",
    employees: "10 à 19 salariés",
    capital: 25000,
    industry: "Divers",
    region: "Île-de-France",
    characteristics: ["special_chars", "small", "edge_case"]
  }
};

export const mockAPIResponses = {
  insee: {
    searchByName: (companyKey: keyof typeof enhancedMockCompanies) => {
      const company = enhancedMockCompanies[companyKey];
      return {
        unitesLegales: [{
          siren: company.siren,
          siretSiegeSocial: company.siret,
          denominationUniteLegale: company.name,
          categorieJuridiqueUniteLegale: company.legalForm,
          adresseSiegeUniteLegale: {
            numeroVoieEtablissement: company.address.split(' ')[0],
            typeVoieEtablissement: company.address.split(' ')[1],
            libelleVoieEtablissement: company.address.split(' ').slice(2, -2).join(' '),
            codePostalEtablissement: company.address.split(' ').slice(-2, -1)[0],
            libelleCommuneEtablissement: company.address.split(' ').slice(-1)[0]
          },
          activitePrincipaleUniteLegale: company.activity,
          dateCreationUniteLegale: company.creationDate,
          etatAdministratifUniteLegale: company.status,
          trancheEffectifsUniteLegale: company.employees
        }]
      };
    },

    searchBySiren: (companyKey: keyof typeof enhancedMockCompanies) => {
      const company = enhancedMockCompanies[companyKey];
      return {
        uniteLegale: {
          siren: company.siren,
          denominationUniteLegale: company.name,
          categorieJuridiqueUniteLegale: company.legalForm,
          adresseSiegeUniteLegale: {
            numeroVoieEtablissement: company.address.split(' ')[0],
            typeVoieEtablissement: company.address.split(' ')[1],
            libelleVoieEtablissement: company.address.split(' ').slice(2, -2).join(' '),
            codePostalEtablissement: company.address.split(' ').slice(-2, -1)[0],
            libelleCommuneEtablissement: company.address.split(' ').slice(-1)[0]
          },
          activitePrincipaleUniteLegale: company.activity,
          dateCreationUniteLegale: company.creationDate,
          etatAdministratifUniteLegale: company.status,
          trancheEffectifsUniteLegale: company.employees,
          dateDernierTraitementUniteLegale: "2024-01-15"
        }
      };
    },

    errors: {
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
      },
      serverError: {
        fault: {
          code: "SERVER_ERROR",
          message: "Erreur interne du serveur",
          description: "Internal server error"
        }
      }
    }
  },

  banqueFrance: {
    financialData: (companyKey: keyof typeof enhancedMockCompanies) => {
      const company = enhancedMockCompanies[companyKey];
      const baseRevenue = company.capital * 100; // Rough estimation
      
      return {
        bilans: [{
          raisonSociale: company.name,
          formeJuridique: company.legalForm,
          adresse: company.address,
          activitePrincipale: company.activity,
          dateCreation: company.creationDate,
          situation: company.status === 'A' ? 'active' : 'inactive',
          revenue: baseRevenue,
          netIncome: baseRevenue * 0.05,
          equity: company.capital,
          debt: company.capital * 0.3,
          employees: parseInt(company.employees.split(' ')[0]) || 0,
          year: 2023
        }]
      };
    },

    creditRating: (companyKey: keyof typeof enhancedMockCompanies) => {
      const company = enhancedMockCompanies[companyKey];
      const ratings = {
        large: "3++",
        medium: "4+",
        small: "5",
        startup: "5+",
        inactive: "9"
      };
      
      let ratingKey: keyof typeof ratings = "medium";
      if (company.characteristics.includes("large")) ratingKey = "large";
      else if (company.characteristics.includes("small")) ratingKey = "small";
      else if (company.characteristics.includes("startup")) ratingKey = "startup";
      else if (company.characteristics.includes("inactive")) ratingKey = "inactive";

      return {
        cotation: ratings[ratingKey],
        dateCotation: "2024-01-15",
        score: ratingKey === "large" ? 95 : ratingKey === "medium" ? 80 : 65
      };
    },

    paymentIncidents: (companyKey: keyof typeof enhancedMockCompanies) => {
      const company = enhancedMockCompanies[companyKey];
      
      if (company.characteristics.includes("inactive") || company.characteristics.includes("startup")) {
        return {
          incidents: [{
            date: "2023-06-15",
            amount: 5000,
            type: "Retard de paiement",
            status: "Résolu"
          }]
        };
      }
      
      return { incidents: [] };
    }
  },

  inpi: {
    authToken: {
      access_token: "mock-inpi-token-12345",
      token_type: "Bearer",
      expires_in: 3600
    },

    companyData: (companyKey: keyof typeof enhancedMockCompanies) => {
      const company = enhancedMockCompanies[companyKey];
      
      return {
        companies: [{
          siren: company.siren,
          denomination: company.name,
          sigle: company.name.split(' ')[0],
          adresse: company.address.split(' ').slice(0, -2).join(' '),
          codePostal: company.address.split(' ').slice(-2, -1)[0],
          ville: company.address.split(' ').slice(-1)[0],
          formeJuridique: company.legalForm,
          codeCategory: company.activity,
          activitySector: company.industry,
          dateCreation: company.creationDate,
          capitalSocial: company.capital,
          effectif: parseInt(company.employees.split(' ')[0]) || 0,
          statut: company.status === 'A' ? 'actif' : 'radié',
          dateImmatriculation: company.creationDate
        }]
      };
    },

    intellectualProperty: (companyKey: keyof typeof enhancedMockCompanies) => {
      const company = enhancedMockCompanies[companyKey];
      let trademarks = 0, patents = 0, designs = 0;

      if (company.characteristics.includes("large")) {
        trademarks = Math.floor(Math.random() * 200) + 50;
        patents = Math.floor(Math.random() * 100) + 20;
        designs = Math.floor(Math.random() * 50) + 10;
      } else if (company.characteristics.includes("medium")) {
        trademarks = Math.floor(Math.random() * 50) + 10;
        patents = Math.floor(Math.random() * 20) + 5;
        designs = Math.floor(Math.random() * 15) + 3;
      } else if (company.characteristics.includes("small") || company.characteristics.includes("startup")) {
        trademarks = Math.floor(Math.random() * 10) + 1;
        patents = Math.floor(Math.random() * 5) + 1;
        designs = Math.floor(Math.random() * 3);
      }

      return {
        attachments: [
          ...Array(trademarks).fill(null).map((_, i) => ({
            id: `tm-${i}`,
            type: 'MARQUE',
            dateDepot: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(),
            confidentiel: false,
            nomDocument: `Marque ${company.name} ${i + 1}`,
            typeDocument: 'marque'
          })),
          ...Array(patents).fill(null).map((_, i) => ({
            id: `pt-${i}`,
            type: 'BREVET',
            dateDepot: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(),
            confidentiel: Math.random() > 0.8,
            nomDocument: `Brevet ${company.name} ${i + 1}`,
            typeDocument: 'brevet'
          })),
          ...Array(designs).fill(null).map((_, i) => ({
            id: `dg-${i}`,
            type: 'DESSIN',
            dateDepot: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(),
            confidentiel: false,
            nomDocument: `Dessin ${company.name} ${i + 1}`,
            typeDocument: 'dessin'
          }))
        ]
      };
    }
  }
};

export const mockErrorScenarios = {
  network: {
    timeout: { code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' },
    refused: { code: 'ECONNREFUSED', message: 'connect ECONNREFUSED 127.0.0.1:80' },
    hostNotFound: { code: 'ENOTFOUND', message: 'getaddrinfo ENOTFOUND api.example.com' },
    networkUnreachable: { code: 'ENETUNREACH', message: 'network is unreachable' }
  },

  http: {
    badRequest: { status: 400, data: { message: 'Bad Request', error: 'Invalid parameters' } },
    unauthorized: { status: 401, data: { message: 'Unauthorized', error: 'Invalid API key' } },
    forbidden: { status: 403, data: { message: 'Forbidden', error: 'Access denied' } },
    notFound: { status: 404, data: { message: 'Not Found', error: 'Resource not found' } },
    tooManyRequests: { status: 429, data: { message: 'Too Many Requests', error: 'Rate limit exceeded' } },
    internalError: { status: 500, data: { message: 'Internal Server Error', error: 'Server error' } },
    badGateway: { status: 502, data: { message: 'Bad Gateway', error: 'Upstream error' } },
    serviceUnavailable: { status: 503, data: { message: 'Service Unavailable', error: 'Maintenance mode' } }
  },

  data: {
    malformedJson: '{"invalid": json}',
    unexpectedStructure: { unexpected: 'structure', missing: 'expected_fields' },
    emptyResponse: '',
    nullResponse: null,
    arrayInsteadOfObject: ['this', 'should', 'be', 'object'],
    stringInsteadOfObject: 'this should be an object'
  }
};

export const mockPerformanceData = {
  latencySimulation: {
    fast: 10,    // 10ms
    normal: 100, // 100ms
    slow: 1000,  // 1s
    timeout: 30000 // 30s
  },

  loadTestScenarios: [
    { name: 'light', concurrent: 10, requests: 100, duration: 30000 },
    { name: 'moderate', concurrent: 50, requests: 500, duration: 60000 },
    { name: 'heavy', concurrent: 100, requests: 1000, duration: 120000 },
    { name: 'stress', concurrent: 200, requests: 2000, duration: 300000 }
  ]
};

export const generateRandomCompany = (): MockCompanyProfile => {
  const industries = ['Technologies', 'Commerce', 'Industrie', 'Services', 'Santé', 'Education'];
  const regions = ['Île-de-France', 'Auvergne-Rhône-Alpes', 'Nouvelle-Aquitaine', 'Occitanie', 'Hauts-de-France'];
  const legalForms = ['5710', '5499', '5307', '5408'];
  const activities = ['62.01Z', '47.11F', '70.10Z', '25.73Z', '70.22Z'];

  const randomSiren = Math.floor(Math.random() * 900000000) + 100000000;
  const randomSiret = randomSiren.toString() + String(Math.floor(Math.random() * 100000)).padStart(5, '0');

  return {
    siren: randomSiren.toString(),
    siret: randomSiret,
    name: `SOCIETE ALEATOIRE ${randomSiren}`,
    legalForm: legalForms[Math.floor(Math.random() * legalForms.length)],
    address: `${Math.floor(Math.random() * 999) + 1} RUE ALEATOIRE ${Math.floor(Math.random() * 90000) + 10000} VILLE`,
    activity: activities[Math.floor(Math.random() * activities.length)],
    creationDate: new Date(Date.now() - Math.random() * 20 * 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    status: Math.random() > 0.1 ? 'A' : 'C',
    employees: ['0 salarié', '1 ou 2 salariés', '3 à 5 salariés', '6 à 9 salariés', '10 à 19 salariés'][Math.floor(Math.random() * 5)],
    capital: Math.floor(Math.random() * 1000000) + 1000,
    industry: industries[Math.floor(Math.random() * industries.length)],
    region: regions[Math.floor(Math.random() * regions.length)],
    characteristics: ['random', 'generated']
  };
};

export const createMockDataSet = (count: number): MockCompanyProfile[] => {
  return Array.from({ length: count }, () => generateRandomCompany());
};