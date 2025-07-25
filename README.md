# Firmia

French Company Intelligence MCP Server - Democratizing access to French business data.

## 🚀 Overview

Firmia is a production-grade MCP (Model Context Protocol) server that provides comprehensive French company and association intelligence by orchestrating 8+ public APIs and static datasets. It offers a unified interface to French business data that is currently locked behind expensive proprietary solutions.

## 🛠️ Tech Stack

- **Python 3.12**: Modern async Python with full type hints
- **FastMCP**: MCP protocol implementation
- **Redis**: High-performance caching layer
- **DuckDB**: Analytics and static data processing
- **HTTPx**: Async HTTP client with HTTP/2 support
- **Pydantic**: Data validation and serialization
- **OpenTelemetry**: Distributed tracing and monitoring

## ✨ Features

### Core Features (Phase 1-2)
- ✅ **Multi-Source Company Search**: Search across INSEE, INPI, Recherche Entreprises, and RNA
- ✅ **Unified Company Profiles**: Complete data fusion from multiple sources with precedence rules
- ✅ **Official Document Downloads**: Access to KBIS, bilans, actes, statuts, attestations
- ✅ **RGPD Compliance**: Privacy filters, audit logging, and data protection
- ✅ **Multi-Provider Authentication**: OAuth2 (INSEE, DGFIP), JWT (INPI, API Entreprise)

### Advanced Features (Phase 2 Extended)
- ✅ **Legal Announcements (BODACC)**: Track bankruptcy, sales, procedures, corrections
- ✅ **Association Search (RNA)**: Find and analyze French associations
- ✅ **Environmental Certifications (RGE)**: Verify RGE, QUALIBAT, QUALIT'ENR certifications
- ✅ **Mixed Search**: Combined company and association search results
- ✅ **Financial Health Check**: Risk assessment based on collective procedures

### Analytics & Intelligence (Phase 3)
- ✅ **Company Health Scoring**: AI-driven health scores with risk factors and recommendations
- ✅ **Market Analytics**: Sector statistics, geographic distribution, concentration analysis
- ✅ **Trend Analysis**: Business trends with forecasting and seasonality detection
- ✅ **Peer Comparison**: Compare companies with industry peers
- ✅ **Batch Operations**: Execute bulk searches, health scores, and analytics
- ✅ **Data Export**: Export results in JSON, CSV, or Excel formats
- ✅ **Static Data Pipeline**: Automated ETL for SIRENE stock, BODACC, and public contracts

### Pending Features
- 🔧 **Bank Account Verification**: FICOBA integration (requires special authorization)
- 📋 **Performance Optimization**: Query optimization and caching improvements

## 📚 Available MCP Tools

The server exposes 23 MCP tools organized by category:

### Search & Discovery
- `search_companies` - Multi-source company and association search
- `search_legal_announcements` - Search BODACC announcements
- `search_associations` - Search RNA for associations
- `search_certified_companies` - Find RGE certified companies

### Company Information
- `get_company_profile` - Unified company profile with data fusion
- `get_company_analytics` - Timeline, financial evolution, peer comparison
- `get_company_health_score` - AI-driven health score with recommendations
- `get_association_details` - Detailed association information
- `check_if_association` - Verify if SIREN is an association
- `check_certifications` - Verify environmental certifications

### Documents & Legal
- `download_document` - Download official documents (KBIS, bilans, etc.)
- `list_documents` - List available documents for a company
- `get_announcement_timeline` - Chronological BODACC timeline
- `check_financial_health` - Financial risk assessment

### Analytics & Market Intelligence
- `get_market_analytics` - Sector stats, geographic distribution, concentration
- `get_trend_analysis` - Business trends with forecasting
- `get_certification_domains` - Available RGE domains and types

### Data Operations
- `export_data` - Export search results, profiles, or analytics
- `batch_operation` - Execute batch operations in parallel
- `update_static_data` - Manually trigger data pipeline updates
- `get_pipeline_status` - Check ETL pipeline status

### System
- `health_check` - Server health and authentication status

## 🏃‍♂️ Quick Start

### Prerequisites

- Python 3.12+
- uv (recommended) or pip
- Redis server (optional - server runs without it)
- Docker (optional)

### Installation

```bash
# Clone the repository
git clone https://github.com/bacoco/Firmia.git
cd Firmia

# Create virtual environment (using uv is recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install MCP SDK (already included in repo)
uv pip install -e ./mcp-python-sdk

# Install dependencies
uv pip install -r requirements_dev.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API credentials (optional - public APIs work without auth)

# Run the server
python -m src.server_new
```

### Environment Variables

API credentials in `.env` (optional - many APIs work without authentication):

```env
# INSEE OAuth2 (optional)
INSEE_CLIENT_ID=your-insee-client-id
INSEE_CLIENT_SECRET=your-insee-client-secret

# INPI JWT (optional)
INPI_USERNAME=your-inpi-username
INPI_PASSWORD=your-inpi-password

# API Entreprise (optional)
API_ENTREPRISE_TOKEN=your-api-entreprise-token

# Redis (optional - server runs without it)
REDIS_URL=redis://localhost:6379/0

# DGFIP OAuth2 (optional)
DGFIP_CLIENT_ID=your-dgfip-client-id
DGFIP_CLIENT_SECRET=your-dgfip-client-secret
```

**Note:** The following APIs work without any credentials:
- Recherche Entreprises (company search)
- BODACC (legal announcements)
- RNA (associations)
- RGE (environmental certifications)

### Available Scripts

```bash
# Run the MCP server
python -m src.server_new

# Test the server
python test_mcp_server.py

# Run tests
pytest

# Run tests with coverage
pytest --cov=src

# Type checking
mypy src

# Linting
ruff check src

# Format code
black src tests
```

### Using with Claude Desktop

To use Firmia with Claude Desktop, add to your MCP settings:

```json
{
  "servers": {
    "firmia": {
      "command": "python",
      "args": ["-m", "src.server_new"],
      "cwd": "/path/to/Firmia"
    }
  }
}
```

## 📁 Project Structure

```
firmia/
├── src/              # Source code
│   ├── api/         # External API clients (8+ integrations)
│   ├── auth/        # Authentication managers
│   ├── cache/       # Redis + DuckDB caching
│   ├── models/      # Pydantic models
│   ├── tools/       # MCP tools (23 tools)
│   ├── analytics/   # Analytics engine
│   ├── pipeline/    # ETL pipeline
│   ├── privacy/     # RGPD compliance
│   ├── resilience/  # Circuit breakers
│   └── monitoring/  # Observability
├── tests/           # Test suite
├── deployment/      # Docker & K8s configs
└── docs/           # Documentation
```

## 🧪 Testing

This project includes comprehensive test coverage:

```bash
# Run all tests
pytest

# Run specific test module
pytest tests/unit/test_auth.py

# Run integration tests
pytest tests/integration/

# Run analytics tests
pytest tests/integration/test_analytics.py

# Generate coverage report
pytest --cov=src --cov-report=html
```

## 🐳 Docker

Build and run with Docker:

```bash
# Build image
docker build -t firmia .

# Run container
docker run -p 8789:8789 --env-file .env firmia

# Use docker-compose for development
docker-compose -f deployment/docker-compose.dev.yml up

# Production deployment
docker build -f deployment/Dockerfile -t firmia:prod .
```

## ☸️ Kubernetes

Deploy to Kubernetes:

```bash
# Create namespace
kubectl create namespace firmia

# Apply configs and secrets
kubectl apply -f deployment/k8s/configmap.yaml
kubectl apply -f deployment/k8s/secrets.yaml

# Deploy application
kubectl apply -f deployment/k8s/deployment.yaml
kubectl apply -f deployment/k8s/service.yaml
```

## 📊 Example Usage

### Search Companies with Health Score

```python
# Search for software companies
results = await search_companies(
    query="logiciel",
    naf_code="62.01Z",
    department="75",
    include_associations=True
)

# Get health score for a company
health = await get_company_health_score(
    siren="123456789",
    include_predictions=True
)
```

### Export Analytics Data

```python
# Export sector analytics to CSV
export = await export_data(
    data_type="analytics_results",
    format="csv",
    analytics_query="sector_statistics",
    parameters={"naf_code": "62.01Z"}
)

# Batch health scores
batch_results = await batch_operation(
    operation="health_score",
    items=[
        {"siren": "123456789"},
        {"siren": "987654321"},
        {"siren": "555666777"}
    ],
    parallel=True
)
```

## 🔧 Configuration

Key configuration files:

- `.env` - Environment variables and API credentials
- `pyproject.toml` - Project metadata and tool configuration
- `deployment/docker-compose.yml` - Docker development setup
- `deployment/k8s/` - Kubernetes manifests
- `src/config.py` - Application settings

## 📈 Performance

- **Caching**: Multi-layer caching with Redis (hot) and DuckDB (analytics)
- **Rate Limiting**: Respects all API rate limits with circuit breakers
- **Parallel Processing**: Batch operations support up to 20 parallel workers
- **Static Data**: ETL pipeline for offline analytics on 3M+ companies

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- French government for providing open APIs
- data.gouv.fr for static datasets
- FastMCP team for the excellent framework

## 👥 Author

Loic ([@bacoco](https://github.com/bacoco))

---

*Built with ❤️ using [Claude Code](https://claude.ai/code) and [Pantheon](https://github.com/godsco/pantheon)*