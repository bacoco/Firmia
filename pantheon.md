---
version: 1.0
project_type: "MCP Server / REST API"
author: "Loic"
created_at: "2025-01-20"
workflow:
  git_enabled: true
  auto_commit: true
  test_before_commit: true
  generate_tests: true
  commit_style: detailed
  feature_branch: false
  create_github_immediately: true
  continuous_push: true
  auto_push_github: true
  generate_readme: true
  docker_enabled: true
  docker_compose: true
  docker_dev_config: true
  kubernetes_manifests: true
  cicd_workflows: false
---

## FEATURE: Multi-Source Company Search

[HIGH PRIORITY] Implement comprehensive search functionality across multiple government APIs with intelligent result fusion. Search by company name, SIREN/SIRET, executive names with advanced filters (NAF code, postal code, department, employee range, legal status). Must handle both companies and associations, with pagination and sub-second response times for cached queries.

Dependencies: None

## FEATURE: Unified Company Profile API

[HIGH PRIORITY] Create a single endpoint that orchestrates calls to INSEE Sirene, INPI RNE, API Entreprise, and other sources to build a complete company profile. Implement intelligent data fusion with precedence rules (RNE > Sirene current > Sirene historical), privacy filtering for protected entities, and selective data inclusion based on user permissions.

Dependencies: Multi-Source Company Search

## FEATURE: Official Document Download Service

[HIGH PRIORITY] Enable secure downloading of official documents (bilans, actes, statuts, KBIS, attestations) from INPI and API Entreprise. Implement rate limiting for PDF downloads (50/min), audit logging for compliance, and support for both direct PDF streaming and URL generation with expiration.

Dependencies: Unified Company Profile API

## FEATURE: Business Events Timeline

[HIGH PRIORITY] Integrate BODACC API to provide chronological timeline of all business events (creation, modification, bankruptcy procedures, sales). Include advanced filtering by event type and date range, with enriched event details and tribunal information.

Dependencies: Multi-Source Company Search

## FEATURE: RGPD-Compliant Privacy Filtering

[HIGH PRIORITY] Implement comprehensive privacy protection system that automatically masks personal addresses for diffusion-protected entities, removes birth details for individuals, and maintains full audit trail for regulatory compliance. Must be applied consistently across all API responses.

Dependencies: None

## FEATURE: Multi-Provider Authentication Manager

[HIGH PRIORITY] Build robust authentication system supporting 7 different mechanisms: OAuth2 (INSEE, DGFIP), JWT with login (INPI), long-lived JWT (API Entreprise), and no-auth APIs. Include automatic token refresh, secure storage in AWS Secrets Manager, and graceful fallback on auth failures.

Dependencies: None

## FEATURE: Association Search Integration

[MEDIUM PRIORITY] Integrate RNA (Répertoire National des Associations) API to enable searching for French associations. Include mixed search results combining companies and associations, with specific association metadata (utility public status, agreements, regime).

Dependencies: Multi-Source Company Search

## FEATURE: RGE Certification Verification

[MEDIUM PRIORITY] Integrate ADEME's RGE (Reconnu Garant de l'Environnement) database to verify environmental certifications for construction/renovation professionals. Include certification domains, validity dates, and qualifying organization information.

Dependencies: Unified Company Profile API

## FEATURE: Bank Account Verification (FICOBA)

[MEDIUM PRIORITY] Implement FICOBA integration for authorized users to verify bank account ownership. Strict access control with comprehensive audit logging, IBAN/BIC validation, and account type information. Requires special authorization.

Dependencies: Multi-Provider Authentication Manager

## FEATURE: Company Health Score Analytics

[MEDIUM PRIORITY] Develop analytics engine using DuckDB to calculate company health scores based on public contracts, business events, employee count, and bankruptcy procedures. Include materialized views for performance and trend analysis capabilities.

Dependencies: Business Events Timeline, Static Data Pipeline

## FEATURE: Static Data Pipeline

[HIGH PRIORITY] Build ETL pipeline for processing large static datasets (Sirene stock, BODACC archives, DECP contracts) in Parquet format. Implement scheduled downloads, incremental updates, atomic table swaps, and automatic cache invalidation.

Dependencies: None

## FEATURE: Intelligent Caching Layer

[HIGH PRIORITY] Implement multi-tier caching with Redis for hot data and DuckDB for analytics. Include cache key patterns by query type, TTL management, automatic invalidation on data updates, and 60%+ cache hit ratio target.

Dependencies: None

## FEATURE: Circuit Breaker & Resilience

[HIGH PRIORITY] Build resilience layer with circuit breakers per API, configurable failure thresholds, exponential backoff retry logic, and graceful degradation on upstream failures. Essential for maintaining 99.5% availability SLO.

Dependencies: Multi-Provider Authentication Manager

## FEATURE: OpenTelemetry Instrumentation

[MEDIUM PRIORITY] Comprehensive observability with OpenTelemetry tracing, Prometheus metrics, structured JSON logging, and performance monitoring. Track API call latencies, cache hit ratios, error rates by type, and authentication token status.

Dependencies: None

## EXAMPLES:

- `firmia-PRD.md`: Complete 1600+ line PRD with detailed API specifications, schemas, and implementation requirements
- Each API section includes full request/response examples with actual field names and data structures
- Privacy filtering rules with specific conditions and field removal logic
- Complete Kubernetes deployment manifests and Dockerfile specifications

## DOCUMENTATION:

- `https://recherche-entreprises.api.gouv.fr`: Main search API (no auth required)
- `https://portail-api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene`: INSEE Sirene V3.11 API
- `https://registre-national-entreprises.inpi.fr/api`: INPI RNE API documentation
- `https://entreprise.api.gouv.fr/v3`: API Entreprise for official documents
- `https://bodacc-datadila.opendatasoft.com/api/v2`: BODACC business announcements
- `https://api-asso.djepva.fr/api/v2`: RNA associations API
- MCP Protocol: https://modelcontextprotocol.io/docs

## CONSTRAINTS:

- **Performance**: 95% of queries must respond in < 2 seconds, 99% in < 5 seconds
- **Availability**: 99.5% uptime SLO with comprehensive monitoring
- **RGPD Compliance**: All personal data must be filtered according to French privacy laws
- **Rate Limits**: Must respect all upstream API limits (varying from 10 req/min to 250 req/min)
- **Authentication**: Support 7 different auth mechanisms across APIs
- **Data Volume**: Handle 20M+ companies and associations
- **Docker Image**: Must be < 500MB using distroless base
- **Resource Limits**: Max 4Gi memory, 2 CPU cores per pod
- **French Only**: Limited to French entities (no international support in V1)
- **Read-Only**: No data modification capabilities
- **No ML/AI**: No predictive models or ML features in V1

## OTHER CONSIDERATIONS:

- **Data Fusion Precedence**: RNE data always takes precedence over Sirene for conflicts
- **Privacy by Design**: When in doubt about privacy, always err on the side of caution
- **Partial Data Strategy**: Return partial data rather than failing completely
- **Source Transparency**: Always indicate which APIs provided which data
- **Error Mapping**: Consistent error codes regardless of upstream API
- **Token Management**: Proactive refresh before expiration
- **Testing Requirements**: Minimum 80% code coverage with extensive fusion logic tests
- **Deployment**: Kubernetes-ready with autoscaling (3-20 replicas)
- **Security**: All tokens in AWS Secrets Manager, TLS 1.3 for external calls
- **Timeline**: 12-week implementation split into 3 phases