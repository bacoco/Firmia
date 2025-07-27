# INPI Adapter Documentation

The INPI (Institut National de la Propriété Industrielle) adapter provides access to the French national business registry data, including company information, beneficial ownership, intellectual property records, and official publications.

## Features

- **JWT Authentication**: Secure token-based authentication with automatic renewal
- **Company Search**: Search by SIREN number or company name
- **Detailed Company Information**: Comprehensive business data including legal form, address, and status
- **Beneficial Ownership**: Access to company representatives and shareholders
- **Company Publications**: Legal acts (ACTE) and financial statements (BILAN)
- **Intellectual Property**: Track trademarks, patents, and designs
- **Differential Updates**: Monitor recent company changes
- **Rate Limiting**: Built-in rate limit management (10,000 daily API calls)
- **Caching**: Aggressive caching to minimize API calls

## Configuration

### Environment Variables

Add the following to your `.env` file:

```env
INPI_USERNAME=your_email@example.com
INPI_PASSWORD=your_inpi_password
```

### Rate Limits

- **Daily Limit**: 10,000 API calls
- **Max Page Size**: 200 results per request
- Configure in `.env`: `RATE_LIMIT_INPI=2000` (requests per hour)

## Usage Examples

### Basic Search

```typescript
import { INPIAdapter } from './adapters/inpi.js';

const adapter = new INPIAdapter(config);

// Search by SIREN
const results = await adapter.search('123456789', {
  maxResults: 10
});

// Search by company name
const results = await adapter.search('Société Example', {
  maxResults: 20
});
```

### Company Details

```typescript
// Get basic company information
const details = await adapter.getDetails('123456789', {
  includeFinancials: true,
  includeIntellectualProperty: true
});

console.log(details.basicInfo);
// {
//   siren: '123456789',
//   name: 'SOCIETE EXAMPLE',
//   legalForm: 'SAS',
//   address: '123 RUE EXAMPLE 75001 PARIS',
//   activity: '6201Z',
//   creationDate: '2020-01-15',
//   status: 'actif'
// }

console.log(details.intellectualProperty);
// {
//   trademarks: 3,
//   patents: 1,
//   designs: 2
// }
```

### Beneficial Ownership

```typescript
const owners = await adapter.getBeneficialOwners('123456789');

console.log(owners);
// [
//   {
//     name: 'Jean DUPONT',
//     role: 'Président',
//     birthDate: '1970-05-15',
//     isCompany: false
//   },
//   {
//     name: 'HOLDING EXAMPLE',
//     role: 'Actionnaire principal',
//     isCompany: true,
//     companySiren: '987654321'
//   }
// ]
```

### Company Publications

```typescript
// Get all public financial statements from 2023
const publications = await adapter.getCompanyPublications('123456789', {
  type: 'BILAN',
  from: new Date('2023-01-01'),
  to: new Date('2023-12-31'),
  includeConfidential: false
});

console.log(publications);
// [
//   {
//     id: 'doc123',
//     type: 'BILAN',
//     name: 'Comptes annuels 2023',
//     date: '2024-03-15',
//     confidential: false,
//     downloadUrl: 'https://registre-national-entreprises.inpi.fr/api/bilans/doc123/download'
//   }
// ]
```

### Differential Updates

```typescript
// Monitor recent company changes
const updates = await adapter.getDifferentialUpdates({
  from: new Date('2024-01-01'),
  to: new Date('2024-01-31'),
  pageSize: 100
});

console.log(updates.companies);
// [
//   {
//     siren: '123456789',
//     name: 'NEW COMPANY SAS',
//     updateType: 'CREATION',
//     updateDate: '2024-01-15'
//   },
//   {
//     siren: '987654321',
//     name: 'OLD COMPANY SARL',
//     updateType: 'RADIATION',
//     updateDate: '2024-01-20'
//   }
// ]

// Continue with pagination
if (updates.nextCursor) {
  const nextPage = await adapter.getDifferentialUpdates({
    from: new Date('2024-01-01'),
    searchAfter: updates.nextCursor
  });
}
```

## Error Handling

The adapter provides detailed error messages:

```typescript
try {
  const results = await adapter.search('test');
} catch (error) {
  if (error.message.includes('rate limit exceeded')) {
    // Wait and retry later
    console.log('Daily quota reached, retry tomorrow');
  } else if (error.message.includes('authentication failed')) {
    // Check credentials
    console.log('Invalid INPI credentials');
  }
}
```

## API Status Check

```typescript
const status = await adapter.getStatus();

console.log(status);
// {
//   available: true,
//   rateLimit: {
//     remaining: 8543,
//     reset: Date('2024-01-15T00:00:00Z')
//   },
//   lastCheck: Date('2024-01-14T15:30:00Z')
// }
```

## Data Types

### SearchResult
- `siren`: Company SIREN number
- `name`: Company name
- `legalForm`: Legal structure (SAS, SARL, etc.)
- `address`: Registered address
- `activity`: Activity code (APE/NAF)
- `creationDate`: Registration date
- `status`: Current status (actif, radié, etc.)

### EnterpriseDetails
- `basicInfo`: Core company information
- `financials`: Capital and employee count
- `intellectualProperty`: IP asset counts

### Document Types
- `BILAN`: Financial statements
- `ACTE`: Legal acts and updates
- `AUTRE`: Other documents

## Best Practices

1. **Cache Effectively**: Results are cached for 1 hour by default
2. **Batch Requests**: Use the search function with multiple SIRENs when possible
3. **Monitor Rate Limits**: Check status regularly to avoid hitting limits
4. **Handle Confidential Data**: Some documents may be marked as confidential
5. **Use Differential Updates**: For monitoring changes, use the differential API

## Limitations

- Maximum 10,000 API calls per day
- Some documents require additional permissions
- Historical data may be limited
- Real-time updates have a slight delay

## Support

For API access and technical support:
- INPI Developer Portal: https://data.inpi.fr
- API Documentation: https://registre-national-entreprises.inpi.fr/api
- Support Email: api-support@inpi.fr