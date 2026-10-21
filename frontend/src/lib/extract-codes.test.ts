import { describe, it, expect } from 'vitest';
import { extractCodes } from './extract-codes';
describe('conservative code detection', () => {
  it('does not join expiry prose', () => {
    expect(extractCodes('Este código vence en 15 minutos')).toEqual([]);
    expect(extractCodes('Your code expires in 15 minutes')).toEqual([]);
  });
  it('recognizes explicit codes without joining words', () => {
    expect(extractCodes('Tu código es: 123456')).toEqual(['123456']);
    expect(extractCodes('Verification code: AB12CD')).toEqual(['AB12CD']);
    expect(extractCodes('Código de acceso\n784512')).toEqual(['784512']);
  });
  it('deduplicates and rejects dates, units and partial long tokens', () => {
    expect(extractCodes('código: 123456\ncódigo: 123456')).toEqual(['123456']);
    expect(extractCodes('código: 2026')).toEqual([]);
    expect(extractCodes('code: 1234 minutes')).toEqual([]);
    expect(extractCodes('code: ABC123456789012')).toEqual([]);
  });
});
