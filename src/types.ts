export type CourseId = string;

export type TermSeason = "Fall" | "Spring" | "Summer";

export type Term = {
  year: number;
  season: TermSeason;
};

export type Course = {
  id: CourseId;
  subject: string;
  number: string;
  title: string;
  credits: number;
  offered?: TermSeason[];
  categories?: string[];
};

export type PrereqExpr =
  | { type: "course"; courseId: CourseId }
  | { type: "and"; items: PrereqExpr[] }
  | { type: "or"; items: PrereqExpr[] }
  | { type: "placement"; code: string };

export type RequirementNode =
  | { type: "allOf"; items: RequirementNode[] }
  | { type: "oneOf"; items: RequirementNode[] }
  | { type: "nOf"; count: number; items: RequirementNode[] }
  | { type: "course"; courseId: CourseId }
  | { type: "category"; category: string; minCourses?: number }
  | { type: "creditsAtLevel"; subject: string; minCredits: number; minLevel: number }
  | { type: "creditsTotal"; minCredits: number };

export type RequirementEval = {
  satisfied: boolean;
  remainingCourses: Set<CourseId>;
  choices: Array<{ count: number; options: CourseId[] }>;
  notes: string[];
};

export type StudentProfile = {
  school: string;
  majors: string[];
  minors: string[];
  catalogYear: string;
  gradTarget: Term;
};

export type StudentRecord = {
  profile: StudentProfile;
  completedCourses: CourseId[];
};

export type PlanTerm = {
  term: Term;
  courses: CourseId[];
  credits: number;
};

export type PlanResult = {
  terms: PlanTerm[];
  remainingCourses: CourseId[];
  warnings: string[];
};
