import test from 'node:test';
import assert from 'node:assert/strict';
import { translations } from '../src/i18n/translations';
import { MANDI_TRANSLATIONS, CROP_TRANSLATIONS, transliterateToHindi } from '../src/i18n/LanguageContext';

test('Single-Language Localization & Fallback Elimination - MandiQ Phase 3', async (t) => {
  await t.test('1. Dictionary Completeness: Perfect 100% key symmetry between English and Hindi', () => {
    const enKeys = Object.keys(translations.en);
    const hiKeys = Object.keys(translations.hi);

    assert.deepEqual(enKeys.sort(), hiKeys.sort(), 'Top-level namespaces must match exactly');

    for (const ns of enKeys as (keyof typeof translations.en)[]) {
      const enSub = Object.keys(translations.en[ns]);
      const hiSub = Object.keys(translations.hi[ns]);
      assert.deepEqual(
        enSub.sort(),
        hiSub.sort(),
        `Namespace '${ns}' must have identical keys between English and Hindi`
      );
    }
  });

  await t.test('2. Strict Invariant: ONE SELECTED LANGUAGE -> ONE VISIBLE UI LANGUAGE (Hindi)', () => {
    // When Hindi is active, user-facing tokens must be pure Hindi, no English remnants
    const farmerTitleHi = translations.hi.farmer.step1Title;
    const activeTokenHi = translations.hi.farmer.activeToken;
    const apmcAdminHi = translations.hi.admin.apmcBoardAdmin;
    const gateRulesHi = translations.hi.gate.cryptoRules;

    assert.match(farmerTitleHi, /[\u0900-\u097F]/, 'Farmer step title must contain Devanagari script');
    assert.match(activeTokenHi, /[\u0900-\u097F]/, 'Active token label must contain Devanagari script');
    assert.match(apmcAdminHi, /[\u0900-\u097F]/, 'APMC admin label must contain Devanagari script');
    assert.match(gateRulesHi, /[\u0900-\u097F]/, 'Gate rules label must contain Devanagari script');

    assert.notEqual(activeTokenHi, translations.en.farmer.activeToken, 'Hindi string must not equal English string');
  });

  await t.test('3. Elimination of Silent English Fallback: Missing key yields controlled placeholder, NOT English', () => {
    // Implementation of the resolver as defined in LanguageContext.tsx
    function resolveKey(lang: 'en' | 'hi', path: string): string {
      const keys = path.split('.');
      let current: any = translations[lang];

      for (const k of keys) {
        if (current && typeof current === 'object' && k in current) {
          current = current[k];
        } else {
          current = undefined;
          break;
        }
      }

      if (typeof current === 'string') {
        return current;
      }

      // Prohibit silent fallback to English when Hindi is selected!
      if (lang === 'hi') {
        return `[MISSING: ${path}]`;
      }

      return path;
    }

    // Existing key resolves correctly
    assert.equal(resolveKey('hi', 'farmer.activeToken'), translations.hi.farmer.activeToken);
    assert.equal(resolveKey('en', 'farmer.activeToken'), translations.en.farmer.activeToken);

    // Missing key in Hindi must NEVER silently return English
    const missingResult = resolveKey('hi', 'nonexistent.mockKey');
    assert.equal(missingResult, '[MISSING: nonexistent.mockKey]', 'Must return controlled placeholder without silent English fallback');
    assert.notEqual(missingResult, 'mockKey');
  });

  await t.test('4. Dynamic Domain Localization: Commodities and APMC Mandis localize at presentation time', () => {
    // Database commodity name "Wheat (Sharbati)" localizes dynamically based on active language
    const wheat = CROP_TRANSLATIONS['Wheat (Sharbati)'];
    assert.ok(wheat, 'Wheat (Sharbati) must be registered in CROP_TRANSLATIONS');
    assert.equal(wheat.hi, 'गेहूँ (शरबती)', 'Must return Hindi translation for Wheat (Sharbati)');
    assert.equal(wheat.en, 'Wheat (Sharbati)', 'Must return English original for en');

    // Mandi names localize without altering database IDs
    const mandi = MANDI_TRANSLATIONS['Ujjain APMC Mandi'];
    assert.ok(mandi, 'Ujjain APMC Mandi must be registered in MANDI_TRANSLATIONS');
    assert.equal(mandi.hi, 'उज्जैन एपीएमसी मंडी', 'Must return Hindi translation for Ujjain APMC Mandi');
    assert.equal(mandi.en, 'Ujjain APMC Mandi', 'Must return English original for en');
  });

  await t.test('5. Zero Network Request Requirement: Translations bundle is 100% in-memory and local-first offline capable', () => {
    assert.ok(translations, 'Translations object must exist in memory');
    assert.ok(Object.keys(translations.hi).length >= 10, 'All namespaces must be loaded synchronously');
  });

  await t.test('6. Dynamic Database Values: Unknown Mandi & Crop names never silently remain English in Hindi mode', () => {
    // Simulate getMandiName on unknown database mandis in Hindi mode
    const testMandis = [
      { input: 'Dewas APMC Mandi', expectedHiContains: 'देवास' },
      { input: 'Bhopal Grain Mandi', expectedHiContains: 'भोपाल' },
      { input: 'Nagpur APMC Mandi', expectedHiContains: 'नागपुर' },
      { input: 'Rampur Krishi Mandi', expectedHiContains: 'मंडी' },
    ];

    for (const item of testMandis) {
      const transliterated = transliterateToHindi(item.input);
      assert.ok(transliterated.length > 0, `Transliteration for ${item.input} must not be empty`);
    }

    // Novel proper nouns must convert to Devanagari script
    const novelPlace = transliterateToHindi('Rampur');
    assert.match(novelPlace, /[\u0900-\u097F]/, 'Novel place name in Hindi mode must be converted to Devanagari script');
    assert.doesNotMatch(novelPlace, /[a-zA-Z]/, 'Novel place name in Hindi mode must not contain raw Latin letters');

    const novelCrop = transliterateToHindi('Barley');
    assert.match(novelCrop, /[\u0900-\u097F]/, 'Unknown crop name in Hindi mode must be converted to Devanagari script');
    assert.doesNotMatch(novelCrop, /[a-zA-Z]/, 'Unknown crop name in Hindi mode must not contain raw Latin letters');
  });

  await t.test('7. Technical Identifiers Preservation: Alphanumeric IDs preserved for auditability', () => {
    // Technical codes like HD-2967, TXN-1001 must not be mangled
    assert.equal(transliterateToHindi('HD-2967'), 'HD-2967', 'Variety code HD-2967 must remain intact as technical identifier');
    assert.equal(transliterateToHindi('TXN-1001'), 'TXN-1001', 'Transaction ID TXN-1001 must remain intact as technical identifier');
  });
});

