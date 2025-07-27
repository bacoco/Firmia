# INSEE API Migration Guide

## Overview

INSEE is transitioning to a new API authentication system by **September 2024**. Firmia has been updated to support both the legacy and new authentication methods for seamless transition.

## Authentication Methods

### ✅ Current Working Method: API Key Integration

The **recommended method** that works immediately:

```bash
# Environment variable
INSEE_API_KEY_INTEGRATION=c1e98007-96f9-498a-a980-0796f9a98a23

# HTTP Header
X-INSEE-Api-Key-Integration: c1e98007-96f9-498a-a980-0796f9a98a23
```

### 🔄 OAuth2 Client Credentials (In Development)

For maximum security, INSEE also provides OAuth2:

```bash
# Environment variables
INSEE_CLIENT_ID=your_client_id
INSEE_CLIENT_SECRET=your_client_secret

# Token endpoint
POST https://api.insee.fr/token
Authorization: Basic base64(client_id:client_secret)
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
```

### 🚨 Legacy Method (Deprecated September 2024)

The old method that will stop working:

```bash
# Environment variable
INSEE_API_KEY=your_legacy_key

# HTTP Header
Authorization: Bearer your_legacy_key
```

## API Endpoints

### New API Base URL
- **Production**: `https://api.insee.fr/api-sirene/3.11`
- **Test**: Same endpoint, different credentials

### Legacy API Base URL (Deprecated)
- **Production**: `https://api.insee.fr/entreprises/sirene/V3`

## Configuration in Firmia

Firmia automatically detects which authentication method to use based on available environment variables:

### Priority Order:
1. **New API Key Integration** (`INSEE_API_KEY_INTEGRATION`)
2. **OAuth2 Credentials** (`INSEE_CLIENT_ID` + `INSEE_CLIENT_SECRET`)
3. **Legacy API Key** (`INSEE_API_KEY`) - fallback

### Example .env Configuration:

```bash
# Option 1: API Key Integration (Recommended)
INSEE_API_KEY_INTEGRATION=c1e98007-96f9-498a-a980-0796f9a98a23

# Option 2: OAuth2 (Most Secure)
INSEE_CLIENT_ID=your_client_id
INSEE_CLIENT_SECRET=your_client_secret

# Option 3: Legacy (Deprecated)
INSEE_API_KEY=your_legacy_key
```

## Migration Steps

### Before September 2024:

1. **Obtain new API credentials** from INSEE:
   - Visit [INSEE Developer Portal](https://api.insee.fr)
   - Request new API integration key
   - Or setup OAuth2 client credentials

2. **Update your .env file**:
   ```bash
   # Add new credentials
   INSEE_API_KEY_INTEGRATION=your_new_key
   
   # Keep legacy for fallback (optional)
   INSEE_API_KEY=your_legacy_key
   ```

3. **Test the new authentication**:
   ```bash
   node test-insee-auth.js
   ```

4. **Verify Firmia works correctly**:
   ```bash
   npm run build
   npm start
   ```

### After September 2024:

1. **Remove legacy credentials**:
   ```bash
   # Remove from .env
   # INSEE_API_KEY=your_legacy_key
   ```

2. **Update documentation and scripts** to only reference new API

## Test Results

As of July 27, 2025:

- ✅ **API Key Integration**: WORKING
- 🔄 **OAuth2 Client Credentials**: Token generation works, API calls need scope verification
- ❌ **Legacy API**: Will stop working in September 2024

## Query Format Changes

The new API uses a slightly different query format:

### Legacy Format:
```
q=denominationUniteLegale:"Company Name"
```

### New API Format:
```
q=denominationUniteLegale:Company Name
```

Firmia handles this automatically based on the detected API version.

## Support

For INSEE API issues:
- 📧 **Email**: support@insee.fr
- 📖 **Documentation**: https://api.insee.fr/docs
- 🐛 **API Status**: https://api.insee.fr/api-sirene/3.11/informations

For Firmia issues:
- 🐛 **GitHub Issues**: https://github.com/bacoco/Firmia/issues
- 📧 **Email**: support@firmia.dev

## Summary

✅ **Firmia is ready for the INSEE API transition**
✅ **No code changes required for users**
✅ **Automatic detection of authentication method**
✅ **Backward compatibility maintained until September 2024**

Just update your environment variables with the new INSEE credentials and you're ready to go!