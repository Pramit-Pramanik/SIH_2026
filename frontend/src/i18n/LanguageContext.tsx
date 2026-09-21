import React, { createContext, useContext, useState, ReactNode } from 'react';
import { translations } from './translations';

export type SupportedLanguage = 'en' | 'hi';

interface LanguageContextType {
  language: SupportedLanguage;
  setLanguage: (lang: SupportedLanguage) => void;
  t: (path: string, params?: Record<string, string | number>) => string;
  getMandiName: (canonicalName: string) => string;
  getCropName: (canonicalName: string) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const MANDI_TRANSLATIONS: Record<string, { en: string; hi: string }> = {
  'Sehore APMC Mandi': { en: 'Sehore APMC Mandi', hi: 'सीहोर एपीएमसी मंडी' },
  'Sehore Krishi Upaj Mandi': { en: 'Sehore Krishi Upaj Mandi', hi: 'सीहोर कृषि उपज मंडी' },
  'Karnal Grain Mandi': { en: 'Karnal Grain Mandi', hi: 'करनाल अनाज मंडी' },
  'Khanna Grain Mandi': { en: 'Khanna Grain Mandi', hi: 'खन्ना अनाज मंडी' },
  'Ujjain APMC Mandi': { en: 'Ujjain APMC Mandi', hi: 'उज्जैन एपीएमसी मंडी' },
  'Dewas APMC Mandi': { en: 'Dewas APMC Mandi', hi: 'देवास एपीएमसी मंडी' },
  'Bhopal Grain Mandi': { en: 'Bhopal Grain Mandi', hi: 'भोपाल अनाज मंडी' },
  'Indore APMC Mandi': { en: 'Indore APMC Mandi', hi: 'इंदौर एपीएमसी मंडी' },
  'Central APMC Mandi': { en: 'Central APMC Mandi', hi: 'केंद्रीय एपीएमसी मंडी' },
  'Closed Mandi': { en: 'Closed Mandi', hi: 'बंद मंडी' },
  'Test Mandi': { en: 'Test Mandi', hi: 'परीक्षण मंडी' },
};

export const CROP_TRANSLATIONS: Record<string, { en: string; hi: string }> = {
  'Wheat': { en: 'Wheat', hi: 'गेहूं' },
  'Wheat (HD-2967)': { en: 'Wheat (HD-2967)', hi: 'गेहूं (HD-2967)' },
  'Wheat (Sharbati)': { en: 'Wheat (Sharbati)', hi: 'गेहूँ (शरबती)' },
  'Paddy': { en: 'Paddy', hi: 'धान' },
  'Paddy (Basmati)': { en: 'Paddy (Basmati)', hi: 'धान (बासमती)' },
  'Mustard': { en: 'Mustard', hi: 'सरसों' },
  'Mustard (Pusa Bold)': { en: 'Mustard (Pusa Bold)', hi: 'सरसों (पूसा बोल्ड)' },
  'Chana (Gram)': { en: 'Chana (Gram)', hi: 'चना' },
  'Chana': { en: 'Chana', hi: 'चना' },
  'Gram': { en: 'Gram', hi: 'चना' },
  'Soybean': { en: 'Soybean', hi: 'सोयाबीन' },
  'Soybean (Yellow)': { en: 'Soybean (Yellow)', hi: 'सोयाबीन (पीला)' },
  'Cotton': { en: 'Cotton', hi: 'कपास' },
  'Cotton (Hybrid)': { en: 'Cotton (Hybrid)', hi: 'कपास (हाइब्रिड)' },
  'Maize': { en: 'Maize', hi: 'मक्का' },
  'Corn': { en: 'Corn', hi: 'मक्का' },
  'Barley': { en: 'Barley', hi: 'जौ' },
  'Bajra': { en: 'Bajra', hi: 'बाजरा' },
  'Jowar': { en: 'Jowar', hi: 'ज्वार' },
  'Moong': { en: 'Moong', hi: 'मूंग' },
  'Urad': { en: 'Urad', hi: 'उड़द' },
  'Tur': { en: 'Tur', hi: 'अरहर' },
  'Arhar': { en: 'Arhar', hi: 'अरहर' },
};

/**
 * Vocabulary map for standard APMC and geographical words
 */
const MANDI_VOCABULARY: Record<string, string> = {
  'sehore': 'सीहोर',
  'karnal': 'करनाल',
  'khanna': 'खन्ना',
  'ujjain': 'उज्जैन',
  'dewas': 'देवास',
  'bhopal': 'भोपाल',
  'indore': 'इंदौर',
  'jabalpur': 'जबलपुर',
  'gwalior': 'ग्वालियर',
  'vidisha': 'विदिशा',
  'hoshangabad': 'होशंगाबाद',
  'narmadapuram': 'नर्मदापुरम',
  'harda': 'हरदा',
  'raisen': 'रायसेन',
  'amritsar': 'अमृतसर',
  'ludhiana': 'लुधियाना',
  'kota': 'कोटा',
  'jaipur': 'जयपुर',
  'nagpur': 'नागपुर',
  'pune': 'पुणे',
  'nashik': 'नासिक',
  'rajkot': 'राजकोट',
  'ahmedabad': 'अहमदाबाद',
  'surat': 'सूरत',
  'central': 'केंद्रीय',
  'closed': 'बंद',
  'test': 'परीक्षण',
  'demo': 'डेमो',
  'apmc': 'एपीएमसी',
  'mandi': 'मंडी',
  'krishi': 'कृषि',
  'upaj': 'उपज',
  'grain': 'अनाज',
  'sub-yard': 'उप-यार्ड',
  'yard': 'यार्ड',
  'terminal': 'टर्मिनल',
  'market': 'बाजार',
  'main': 'मुख्य',
  'north': 'उत्तर',
  'south': 'दक्षिण',
  'east': 'पूर्व',
  'west': 'पश्चिम',
  'district': 'ज़िला',
  'state': 'राज्य',
};

/**
 * Vocabulary map for standard crops and attributes
 */
const CROP_VOCABULARY: Record<string, string> = {
  'wheat': 'गेहूं',
  'paddy': 'धान',
  'rice': 'चावल',
  'mustard': 'सरसों',
  'chana': 'चना',
  'gram': 'चना',
  'soybean': 'सोयाबीन',
  'cotton': 'कपास',
  'maize': 'मक्का',
  'corn': 'मक्का',
  'barley': 'जौ',
  'bajra': 'बाजरा',
  'jowar': 'ज्वार',
  'moong': 'मूंग',
  'urad': 'उड़द',
  'tur': 'अरहर',
  'arhar': 'अरहर',
  'lentil': 'मसूर',
  'masoor': 'मसूर',
  'groundnut': 'मूंगफली',
  'peanut': 'मूंगफली',
  'sunflower': 'सूरजमुखी',
  'sesame': 'तिल',
  'sugarcane': 'गन्ना',
  'onion': 'प्याज',
  'potato': 'आलू',
  'tomato': 'टमाटर',
  'garlic': 'लहसुन',
  'ginger': 'अदरक',
  'coriander': 'धनिया',
  'cumin': 'जीरा',
  'fenugreek': 'मेथी',
  'yellow': 'पीला',
  'black': 'काला',
  'white': 'सफेद',
  'red': 'लाल',
  'green': 'हरा',
  'desi': 'देसी',
  'hybrid': 'हाइब्रिड',
  'composite': 'मिश्रित',
  'bold': 'बोल्ड',
  'sharbati': 'शरबती',
  'basmati': 'बासमती',
  'pusa': 'पूसा',
  'grade': 'ग्रेड',
};

/**
 * Phonetic transliteration engine for proper nouns and unknown place names.
 * Ensures zero raw Latin text leaks into Hindi mode.
 */
export function transliterateToHindi(input: string): string {
  if (!input) return '';
  // If already contains Devanagari or is a pure number, return as-is
  if (/[\u0900-\u097F]/.test(input) || /^\d+$/.test(input)) {
    return input;
  }

  // Preserve technical identifiers (e.g. HD-2967, TXN-1001, SCALE-01)
  if (/^[A-Z0-9]+-[A-Z0-9]+$/.test(input.trim())) {
    return input;
  }

  const consonantMap: [string, string][] = [
    ['ksha', 'क्ष'], ['ksh', 'क्ष'], ['gya', 'ज्ञ'], ['tra', 'त्र'],
    ['shh', 'ष'], ['chh', 'छ'], ['kh', 'ख'], ['gh', 'घ'], ['ch', 'च'],
    ['jh', 'झ'], ['th', 'थ'], ['dh', 'ध'], ['ph', 'फ'], ['bh', 'भ'],
    ['sh', 'श'], ['k', 'क'], ['g', 'ग'], ['c', 'क'], ['j', 'ज'],
    ['t', 'त'], ['d', 'द'], ['n', 'न'], ['p', 'प'], ['b', 'ब'],
    ['m', 'म'], ['y', 'य'], ['r', 'र'], ['l', 'ल'], ['v', 'व'],
    ['w', 'व'], ['s', 'स'], ['h', 'ह'], ['z', 'ज़'], ['f', 'फ़'],
    ['q', 'क'], ['x', 'क्स']
  ];

  const vowelStandalone: [string, string][] = [
    ['aa', 'आ'], ['ee', 'ई'], ['oo', 'ऊ'], ['ai', 'ऐ'], ['au', 'औ'],
    ['a', 'अ'], ['e', 'ए'], ['i', 'इ'], ['o', 'ओ'], ['u', 'उ']
  ];

  const vowelMatra: [string, string][] = [
    ['aa', 'ा'], ['ee', 'ी'], ['oo', 'ू'], ['ai', 'ै'], ['au', 'ौ'],
    ['a', ''], ['e', 'े'], ['i', 'ि'], ['o', 'ो'], ['u', 'ु']
  ];

  let str = input.toLowerCase();
  let result = '';
  let i = 0;

  while (i < str.length) {
    // Check if character is not a letter
    const ch = str[i];
    if (!/[a-z]/.test(ch)) {
      result += ch;
      i++;
      continue;
    }

    // Check standalone vowel at word start or after non-letter
    const isStart = i === 0 || !/[a-z]/.test(str[i - 1]);
    if (isStart) {
      let matchedVowel = false;
      for (const [vText, vDev] of vowelStandalone) {
        if (str.startsWith(vText, i)) {
          result += vDev;
          i += vText.length;
          matchedVowel = true;
          break;
        }
      }
      if (matchedVowel) continue;
    }

    // Match consonant
    let matchedConsonant = false;
    for (const [cText, cDev] of consonantMap) {
      if (str.startsWith(cText, i)) {
        result += cDev;
        i += cText.length;
        matchedConsonant = true;

        // Check if immediately followed by vowel matra
        for (const [vText, vMatra] of vowelMatra) {
          if (str.startsWith(vText, i)) {
            result += vMatra;
            i += vText.length;
            break;
          }
        }
        break;
      }
    }

    if (!matchedConsonant) {
      // Fallback: advance single char
      result += str[i];
      i++;
    }
  }

  return result;
}

export const LanguageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<SupportedLanguage>(() => {
    try {
      const stored = localStorage.getItem('mandiq_lang');
      if (stored === 'hi' || stored === 'en') return stored;
    } catch {
      // Storage unavailable
    }
    return 'en';
  });

  const setLanguage = (lang: SupportedLanguage) => {
    setLanguageState(lang);
    try {
      localStorage.setItem('mandiq_lang', lang);
    } catch {
      // Storage unavailable
    }
  };

  const t = (path: string, params?: Record<string, string | number>): string => {
    const dict = translations[language] as unknown as Record<string, unknown>;
    const keys = path.split('.');
    let current: unknown = dict;

    for (const key of keys) {
      if (current && typeof current === 'object' && key in (current as Record<string, unknown>)) {
        current = (current as Record<string, unknown>)[key];
      } else {
        // Strict Single-Language Enforcement: No silent English fallback
        console.warn(`[i18n] Missing translation for key: "${path}" in language: "${language}"`);
        return `[MISSING: ${path}]`;
      }
    }

    if (typeof current !== 'string') {
      console.warn(`[i18n] Translation path does not resolve to string: "${path}" in language: "${language}"`);
      return `[MISSING: ${path}]`;
    }

    let result = current;
    if (params) {
      for (const [pKey, pVal] of Object.entries(params)) {
        result = result.replace(new RegExp(`{${pKey}}`, 'g'), String(pVal));
      }
    }
    return result;
  };

  const getMandiName = (canonicalName: string): string => {
    if (!canonicalName) return '';
    const trimmed = canonicalName.trim();
    const match = MANDI_TRANSLATIONS[trimmed];
    if (match) return match[language];

    if (language === 'en') {
      return trimmed;
    }

    // Hindi mode: Explicit multi-tier dynamic localization strategy
    // 1. Check known full name
    if (MANDI_TRANSLATIONS[trimmed]) {
      return MANDI_TRANSLATIONS[trimmed].hi;
    }

    // 2. Tokenize and map compound tokens
    const tokens = trimmed.split(/(\s+|[(),\-/])/);
    const localized = tokens.map((token) => {
      const lower = token.toLowerCase();
      if (MANDI_VOCABULARY[lower]) {
        return MANDI_VOCABULARY[lower];
      }
      if (/^[A-Za-z]+$/.test(token)) {
        return transliterateToHindi(token);
      }
      return token;
    });

    return localized.join('');
  };

  const getCropName = (canonicalName: string): string => {
    if (!canonicalName) return '';
    const trimmed = canonicalName.trim();
    const match = CROP_TRANSLATIONS[trimmed];
    if (match) return match[language];

    if (language === 'en') {
      return trimmed;
    }

    // Hindi mode: Explicit multi-tier dynamic localization strategy
    // 1. Check known full name
    if (CROP_TRANSLATIONS[trimmed]) {
      return CROP_TRANSLATIONS[trimmed].hi;
    }

    // 2. Tokenize and map compound tokens
    const tokens = trimmed.split(/(\s+|[(),\-/])/);
    const localized = tokens.map((token) => {
      const lower = token.toLowerCase();
      if (CROP_VOCABULARY[lower]) {
        return CROP_VOCABULARY[lower];
      }
      // Preserve technical crop variety codes (e.g. HD-2967)
      if (/^[A-Z0-9]+-[A-Z0-9]+$/.test(token)) {
        return token;
      }
      if (/^[A-Za-z]+$/.test(token)) {
        return transliterateToHindi(token);
      }
      return token;
    });

    return localized.join('');
  };

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, getMandiName, getCropName }}>
      {children}
    </LanguageContext.Provider>
  );
};

export function useLanguage(): LanguageContextType {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
