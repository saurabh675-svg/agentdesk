export const en = {
  newChat: "New chat",
  send: "Send",
  stop: "Stop",
  copy: "Copy",
  export: "Export",
  settings: "Settings",
  filterFiles: "Filter files…",
  searchSettings: "Search settings…",
  askAnything: "Ask anything…",
  rubricSatisfied: "Rubric satisfied",
  rubricRevising: "Rubric: revising",
} as const

export const es = {
  ...en,
  newChat: "Nuevo chat",
  send: "Enviar",
  stop: "Detener",
  copy: "Copiar",
  export: "Exportar",
  settings: "Ajustes",
  filterFiles: "Filtrar archivos…",
  searchSettings: "Buscar ajustes…",
  askAnything: "Pregunta lo que sea…",
  rubricSatisfied: "Rúbrica satisfecha",
  rubricRevising: "Rúbrica: revisando",
} as const

export const hi = {
  ...en,
  newChat: "नई चैट",
  send: "भेजें",
  stop: "रोकें",
  copy: "प्रतिलिपि",
  export: "निर्यात",
  settings: "सेटिंग्स",
  filterFiles: "फ़ाइलें फ़िल्टर करें…",
  searchSettings: "सेटिंग्स खोजें…",
  askAnything: "कुछ भी पूछें…",
  rubricSatisfied: "रूब्रिक संतुष्ट",
  rubricRevising: "रूब्रिक: संशोधन",
} as const

export type Locale = "en" | "es" | "hi"
export type Strings = Record<keyof typeof en, string>

const LOCALES: Record<Locale, Strings> = { en, es, hi }
let current: Locale = "en"

export function setLocale(locale: Locale): void { current = locale }
export function getLocale(): Locale { return current }
export function t(key: keyof Strings): string { return LOCALES[current][key] ?? en[key] }
export function useT(): (key: keyof Strings) => string { return t }
