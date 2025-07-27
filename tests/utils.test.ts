import {
  validateSIREN,
  validateSIRET,
  formatSIREN,
  formatSIRET,
  extractSIREN,
  normalizeEnterpriseName,
  parseFrenchDate,
  formatCurrency,
  chunk
} from '../src/utils/index.js';

describe('SIREN/SIRET Validation', () => {
  describe('validateSIREN', () => {
    it('should validate correct SIREN numbers', () => {
      expect(validateSIREN('552032534')).toBe(true); // Danone
      expect(validateSIREN('383474814')).toBe(true); // Airbus
    });

    it('should reject invalid SIREN numbers', () => {
      expect(validateSIREN('123456789')).toBe(false); // Invalid checksum
      expect(validateSIREN('12345678')).toBe(false); // Too short
      expect(validateSIREN('1234567890')).toBe(false); // Too long
      expect(validateSIREN('12345678a')).toBe(false); // Contains letter
    });
  });

  describe('validateSIRET', () => {
    it('should validate correct SIRET numbers', () => {
      expect(validateSIRET('55203253400041')).toBe(true); // Danone HQ
      expect(validateSIRET('38347481400011')).toBe(true); // Airbus HQ
    });

    it('should reject invalid SIRET numbers', () => {
      expect(validateSIRET('12345678901234')).toBe(false); // Invalid checksum
      expect(validateSIRET('1234567890123')).toBe(false); // Too short
      expect(validateSIRET('123456789012345')).toBe(false); // Too long
    });
  });
});

describe('Formatting Functions', () => {
  describe('formatSIREN', () => {
    it('should format valid SIREN with spaces', () => {
      expect(formatSIREN('552032534')).toBe('552 032 534');
      expect(formatSIREN('383474814')).toBe('383 474 814');
    });

    it('should return original string for invalid SIREN', () => {
      expect(formatSIREN('123456789')).toBe('123456789');
    });
  });

  describe('formatSIRET', () => {
    it('should format valid SIRET with spaces', () => {
      expect(formatSIRET('55203253400041')).toBe('552 032 534 00041');
      expect(formatSIRET('38347481400011')).toBe('383 474 814 00011');
    });
  });

  describe('extractSIREN', () => {
    it('should extract SIREN from SIRET', () => {
      expect(extractSIREN('55203253400041')).toBe('552032534');
      expect(extractSIREN('38347481400011')).toBe('383474814');
    });
  });
});

describe('Enterprise Name Normalization', () => {
  it('should normalize enterprise names', () => {
    expect(normalizeEnterpriseName('Société Générale')).toBe('SOCIETE GENERALE');
    expect(normalizeEnterpriseName('L\'Oréal S.A.')).toBe('L OREAL S A');
    expect(normalizeEnterpriseName('  Multiple   Spaces  ')).toBe('MULTIPLE SPACES');
    expect(normalizeEnterpriseName('Café & Co.')).toBe('CAFE CO');
  });
});

describe('Date Parsing', () => {
  it('should parse French date formats', () => {
    const date1 = parseFrenchDate('15/03/2024');
    expect(date1?.toISOString().substring(0, 10)).toBe('2024-03-15');

    const date2 = parseFrenchDate('01-12-2023');
    expect(date2?.toISOString().substring(0, 10)).toBe('2023-12-01');

    const date3 = parseFrenchDate('2024-03-15');
    expect(date3?.toISOString().substring(0, 10)).toBe('2024-03-15');
  });

  it('should return null for invalid dates', () => {
    expect(parseFrenchDate('')).toBeNull();
    expect(parseFrenchDate('invalid')).toBeNull();
    expect(parseFrenchDate('32/13/2024')).toBeNull();
  });
});

describe('Currency Formatting', () => {
  it('should format currency in EUR', () => {
    expect(formatCurrency(1234.56)).toContain('1');
    expect(formatCurrency(1234.56)).toContain('234');
    expect(formatCurrency(1000000)).toContain('000');
  });
});

describe('Array Chunking', () => {
  it('should chunk arrays correctly', () => {
    const array = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    const chunks = chunk(array, 3);
    
    expect(chunks).toHaveLength(4);
    expect(chunks[0]).toEqual([1, 2, 3]);
    expect(chunks[1]).toEqual([4, 5, 6]);
    expect(chunks[2]).toEqual([7, 8, 9]);
    expect(chunks[3]).toEqual([10]);
  });

  it('should handle empty arrays', () => {
    expect(chunk([], 3)).toEqual([]);
  });

  it('should handle chunk size larger than array', () => {
    expect(chunk([1, 2, 3], 10)).toEqual([[1, 2, 3]]);
  });
});