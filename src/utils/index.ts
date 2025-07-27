/**
 * Utility functions for SIREN/SIRET validation and data formatting
 */

/**
 * Validates a SIREN number (9 digits)
 */
export function validateSIREN(siren: string): boolean {
  if (!siren || typeof siren !== 'string') {
    return false;
  }
  
  // Remove spaces and check if it's exactly 9 digits
  const cleanSiren = siren.replace(/\s/g, '');
  return /^\d{9}$/.test(cleanSiren);
}

/**
 * Validates a SIRET number (14 digits)
 */
export function validateSIRET(siret: string): boolean {
  if (!siret || typeof siret !== 'string') {
    return false;
  }
  
  // Remove spaces and check if it's exactly 14 digits
  const cleanSiret = siret.replace(/\s/g, '');
  if (!/^\d{14}$/.test(cleanSiret)) {
    return false;
  }
  
  // Check if the first 9 digits form a valid SIREN
  const siren = cleanSiret.substring(0, 9);
  return validateSIREN(siren);
}

/**
 * Formats a SIREN number with spaces for readability
 */
export function formatSIREN(siren: string): string {
  if (!validateSIREN(siren)) {
    return siren;
  }
  
  const cleanSiren = siren.replace(/\s/g, '');
  return `${cleanSiren.substring(0, 3)} ${cleanSiren.substring(3, 6)} ${cleanSiren.substring(6, 9)}`;
}

/**
 * Formats a SIRET number with spaces for readability
 */
export function formatSIRET(siret: string): string {
  if (!validateSIRET(siret)) {
    return siret;
  }
  
  const cleanSiret = siret.replace(/\s/g, '');
  return `${cleanSiret.substring(0, 3)} ${cleanSiret.substring(3, 6)} ${cleanSiret.substring(6, 9)} ${cleanSiret.substring(9, 14)}`;
}

/**
 * Parses French date formats (DD/MM/YYYY or DD-MM-YYYY) to Date object
 */
export function parseFrenchDate(dateString: string): Date | null {
  if (!dateString || typeof dateString !== 'string') {
    return null;
  }
  
  // Try DD/MM/YYYY format
  let match = dateString.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (match) {
    const day = parseInt(match[1], 10);
    const month = parseInt(match[2], 10);
    const year = parseInt(match[3], 10);
    
    // Validate ranges
    if (day < 1 || day > 31 || month < 1 || month > 12 || year < 1900 || year > 2100) {
      return null;
    }
    
    const date = new Date(year, month - 1, day);
    
    // Check if the date is valid (e.g., not February 30th)
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
      return null;
    }
    
    return date;
  }
  
  // Try DD-MM-YYYY format
  match = dateString.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
  if (match) {
    const day = parseInt(match[1], 10);
    const month = parseInt(match[2], 10);
    const year = parseInt(match[3], 10);
    
    // Validate ranges
    if (day < 1 || day > 31 || month < 1 || month > 12 || year < 1900 || year > 2100) {
      return null;
    }
    
    const date = new Date(year, month - 1, day);
    
    // Check if the date is valid
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
      return null;
    }
    
    return date;
  }
  
  return null;
}

/**
 * Formats a date to French format (DD/MM/YYYY)
 */
export function formatFrenchDate(date: Date): string {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) {
    return '';
  }
  
  const day = date.getDate().toString().padStart(2, '0');
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const year = date.getFullYear();
  
  return `${day}/${month}/${year}`;
}

/**
 * Normalizes company names for comparison
 */
export function normalizeCompanyName(name: string): string {
  if (!name || typeof name !== 'string') {
    return '';
  }
  
  return name
    .toUpperCase()
    .replace(/\s+/g, ' ')
    .replace(/[^\w\s]/g, '')
    .trim();
}

/**
 * Extracts numeric value from employee count strings
 */
export function parseEmployeeCount(employeeString: string): number | null {
  if (!employeeString || typeof employeeString !== 'string') {
    return null;
  }
  
  // Handle ranges like "10 à 19 salariés"
  const rangeMatch = employeeString.match(/(\d+)\s*à\s*(\d+)/);
  if (rangeMatch) {
    const min = parseInt(rangeMatch[1], 10);
    const max = parseInt(rangeMatch[2], 10);
    return Math.floor((min + max) / 2); // Return average
  }
  
  // Handle "X salariés ou plus"
  const plusMatch = employeeString.match(/(\d+)\s+salariés?\s+ou\s+plus/);
  if (plusMatch) {
    return parseInt(plusMatch[1], 10);
  }
  
  // Handle simple numbers
  const numberMatch = employeeString.match(/(\d+)/);
  if (numberMatch) {
    return parseInt(numberMatch[1], 10);
  }
  
  return null;
}

/**
 * Formats currency amounts with French formatting
 */
export function formatCurrency(amount: number, currency = 'EUR'): string {
  if (typeof amount !== 'number' || isNaN(amount)) {
    return '';
  }
  
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2
  }).format(amount);
}

/**
 * Checks if a string is a valid email address
 */
export function isValidEmail(email: string): boolean {
  if (!email || typeof email !== 'string') {
    return false;
  }
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Sanitizes input strings to prevent XSS
 */
export function sanitizeInput(input: string): string {
  if (!input || typeof input !== 'string') {
    return '';
  }
  
  return input
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
}

/**
 * Validates and normalizes postal codes
 */
export function validatePostalCode(postalCode: string): boolean {
  if (!postalCode || typeof postalCode !== 'string') {
    return false;
  }
  
  // French postal codes are 5 digits
  return /^\d{5}$/.test(postalCode.replace(/\s/g, ''));
}

/**
 * Extracts SIREN from SIRET
 */
export function siretToSiren(siret: string): string | null {
  if (!validateSIRET(siret)) {
    return null;
  }
  
  return siret.replace(/\s/g, '').substring(0, 9);
}