/**
 * Minimal internal i18n (no dependency yet).
 *
 * Dictionaries are flat and dot-keyed (see src/i18n/en.ts). Phase 2+ may swap
 * this for react-i18next if pluralisation/formatting needs grow — the
 * dictionary shape stays behind this one function.
 */
import { en, type TranslationKey } from "../i18n/en";
import { hi } from "../i18n/hi";

export type Language = "en" | "hi";

const dictionaries: Record<Language, Partial<Record<TranslationKey, string>>> = {
  en,
  hi,
};

export function t(lang: Language, key: TranslationKey): string {
  return dictionaries[lang][key] ?? en[key];
}

export function isSupportedLanguage(value: string): value is Language {
  return value === "en" || value === "hi";
}