// Maps course prefix abbreviations to Rutgers registrar subject numbers.
// Full registrar code format: campus:subject:number (e.g. CS111 -> 01:198:111)
const DEPT_SUBJECT: Record<string, string> = {
  ACCT: "010", ACE: "007", AFRS: "016", AGECO: "007", AMES: "098",
  AMESALL: "098", AMST: "050", ANSC: "340", ANTH: "070", ARAB: "074",
  ARCH: "080", ART: "081", ARTH: "082", ASTRO: "750", BCHEM: "115",
  BIO: "119", BIOTECH: "137", BLAW: "140", BME: "125", BSYSE: "116",
  BUSS: "135", CBN: "148", CEE: "180", CHE: "155", CHEM: "160",
  CHN: "165", CINE: "175", CLAS: "190", CLASS: "190", COGS: "185",
  COMM: "192", COMMUN: "192", COMPLIT: "195", CRP: "762", CS: "198",
  CSA: "198", DANC: "214", DISAB: "216", DISA: "216", DSTU: "216",
  DNP: "705", ECE: "332", ECON: "220", EDUC: "300", EADM: "300",
  EDLT: "300", EDPD: "300", EDPY: "300", ENG: "355", ENGL: "350",
  ENGLA: "350", ENVSCI: "375", ENVST: "375", ENT: "370", ENVE: "180",
  EENR: "375", ESME: "885", EXPOS: "355", EXSC: "572", FIN: "390",
  FREN: "420", FS: "400", GENET: "447", GEOG: "450", GEOSC: "460",
  GERM: "470", GLHUM: "554", GREK: "490", GRE: "490", HEBR: "500",
  HINDI: "504", HIST: "510", HLAD: "501", HA: "501", HIED: "507",
  HRM: "545", IGS: "554", IRHR: "545", ISE: "540", ITAL: "560",
  ITI: "194", JWST: "563", JMS: "563", JOUR: "567", JPN: "217",
  KOR: "574", LA: "550", LAS: "590", LAT: "595", LATIN: "595",
  LCS: "600", LER: "545", LSER: "545", LING: "615", MAE: "650",
  MAP: "642", MAED: "640", MARINE: "712", MATH: "640", MCB: "695",
  MCHM: "663", MEDST: "667", MES: "625", METEOR: "107", MICROB: "681",
  MGMT: "660", MKTG: "630", MHRM: "545", MLER: "545", MSE: "635",
  MSN: "705", MSW: "910", MUS: "700", MUSA: "700", MUSC: "700",
  NURS: "705", NUTRSCI: "709", PADM: "762", PBIO: "765", PCHM: "160",
  PCOL: "718", PERS: "726", PHAR: "720", PHRC: "720", PHIL: "730",
  PHSL: "761", PHYS: "750", PLSC: "765", POLS: "790", PORT: "810",
  PPOL: "762", PPP: "762", PSYC: "830", PUBH: "832", PUBP: "762",
  RELGS: "840", RUSS: "859", SAAS: "098", SCM: "799", SCED: "300",
  SLAV: "859", SOC: "920", SOCW: "910", SPAN: "940", SPED: "300",
  SPMD: "475", SPSY: "300", SSED: "300", STAT: "960", SW: "910",
  SWAH: "016", THEA: "965", THTA: "965", THTR: "965", TLED: "300",
  TURF: "976", TURK: "975", UPD: "762", URST: "762", WGSS: "988",
  EURO: "360", FILM: "175", HUNG: "508", LANE: "615", LCD: "300",
  MODGK: "500", READ: "300", SPFE: "300",
  GACCT: "010", GACCNB: "010", GBLAW: "140", GECON: "220",
  GFIN: "390", GFINA: "390", GMATH: "640", GMGT: "660",
  GMKT: "630", GQF: "643", GSCM: "799", GSTAT: "960",
};

// Reverse map: subject number -> preferred short prefix
// When multiple prefixes share a subject, the first (shorter/canonical) one wins.
const SUBJECT_TO_PREFIX: Record<string, string> = {};
for (const [prefix, subject] of Object.entries(DEPT_SUBJECT)) {
  if (!SUBJECT_TO_PREFIX[subject]) {
    SUBJECT_TO_PREFIX[subject] = prefix;
  }
}
// Override ambiguous ones to the most common prefix
SUBJECT_TO_PREFIX["198"] = "CS";
SUBJECT_TO_PREFIX["640"] = "MATH";
SUBJECT_TO_PREFIX["750"] = "PHYS";
SUBJECT_TO_PREFIX["160"] = "CHEM";
SUBJECT_TO_PREFIX["960"] = "STAT";
SUBJECT_TO_PREFIX["920"] = "SOC";
SUBJECT_TO_PREFIX["910"] = "SOC";  // social work uses SW
SUBJECT_TO_PREFIX["300"] = "EDUC";
SUBJECT_TO_PREFIX["762"] = "CRP";
SUBJECT_TO_PREFIX["545"] = "IRHR";
SUBJECT_TO_PREFIX["700"] = "MUS";
SUBJECT_TO_PREFIX["350"] = "ENGL";
SUBJECT_TO_PREFIX["965"] = "THEA";

/**
 * Converts a Rutgers registrar code (e.g. "01:198:111") back to the short
 * course code (e.g. "CS111"). Returns null if the subject is unknown.
 */
export function registrarToShortCode(registrar: string): string | null {
  const match = registrar.match(/^\d{2}:(\d{3}):(\d+.*)$/);
  if (!match) return null;
  const [, subject, number] = match;
  const prefix = SUBJECT_TO_PREFIX[subject];
  if (!prefix) return null;
  return `${prefix}${number}`;
}

/** Parse a course code like "CS111" into prefix and number */
function parseCourseCode(code: string): { prefix: string; number: string } | null {
  const match = code.match(/^([A-Z]+)(\d+.*)$/);
  if (!match) return null;
  return { prefix: match[1], number: match[2] };
}

/** Returns the full Rutgers registrar code, e.g. "01:198:111", or null if unknown */
export function getRegistrarCode(courseCode: string): string | null {
  const parsed = parseCourseCode(courseCode);
  if (!parsed) return null;
  const subject = DEPT_SUBJECT[parsed.prefix];
  if (!subject) return null;
  return `01:${subject}:${parsed.number}`;
}

/** Returns a link to the Rutgers Schedule of Classes for the course's subject */
export function getRutgersSOCUrl(courseCode: string): string | null {
  const parsed = parseCourseCode(courseCode);
  if (!parsed) return null;
  const subject = DEPT_SUBJECT[parsed.prefix];
  if (!subject) return null;
  // Links to the SOC subject search (NB campus, current year)
  return `https://sis.rutgers.edu/soc/api/courses.json?year=2026&term=9&campus=NB&subject=${subject}`;
}

/** Returns a Coursicle link for the specific course — student-friendly */
export function getCoursiclUrl(courseCode: string): string | null {
  const parsed = parseCourseCode(courseCode);
  if (!parsed) return null;
  if (!DEPT_SUBJECT[parsed.prefix]) return null;
  return `https://www.coursicle.com/rutgers/courses/${parsed.prefix}/${parsed.number}/`;
}
