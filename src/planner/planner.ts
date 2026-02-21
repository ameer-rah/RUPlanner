import type {
  Course,
  CourseId,
  PlanResult,
  PlanTerm,
  PrereqExpr,
  RequirementEval,
  Term,
  TermSeason,
} from "../types";

type PlannerOptions = {
  startTerm: Term;
  targetTerm: Term;
  minCredits: number;
  maxCredits: number;
  targetCredits: number;
};

export type PlannerInput = {
  courses: Course[];
  completedCourses: CourseId[];
  prerequisites: Map<CourseId, PrereqExpr>;
  requirementEval: RequirementEval;
  options?: Partial<PlannerOptions>;
};

const DEFAULT_OPTIONS: PlannerOptions = {
  startTerm: { year: new Date().getFullYear(), season: "Fall" },
  targetTerm: { year: new Date().getFullYear() + 4, season: "Spring" },
  minCredits: 12,
  maxCredits: 18,
  targetCredits: 15,
};

export function generatePlan(input: PlannerInput): PlanResult {
  const options = { ...DEFAULT_OPTIONS, ...input.options };
  const coursesById = new Map(input.courses.map((course) => [course.id, course]));
  const remaining = new Set<CourseId>(input.requirementEval.remainingCourses);

  const electiveSelections = pickElectives(input.requirementEval, input, coursesById);
  for (const courseId of electiveSelections) {
    remaining.add(courseId);
  }

  const scheduled = new Set<CourseId>();
  const completed = new Set<CourseId>(input.completedCourses);
  const warnings: string[] = [];
  const terms: PlanTerm[] = [];

  for (const term of iterateTerms(options.startTerm, options.targetTerm)) {
    const eligible = Array.from(remaining).filter((courseId) =>
      isEligible(courseId, input, completed, scheduled, term, coursesById)
    );

    const prioritized = prioritizeCourses(eligible, input, term, coursesById);
    const picked = pickCoursesForTerm(prioritized, coursesById, options);

    for (const courseId of picked) {
      scheduled.add(courseId);
      remaining.delete(courseId);
    }

    const credits = picked.reduce((sum, courseId) => sum + (coursesById.get(courseId)?.credits ?? 0), 0);
    terms.push({ term, courses: picked, credits });

    for (const courseId of picked) {
      completed.add(courseId);
    }

    if (remaining.size === 0) {
      break;
    }

    if (picked.length === 0) {
      warnings.push(
        `No eligible courses found for ${term.season} ${term.year}. Check prereqs or offerings.`
      );
    }
  }

  return {
    terms,
    remainingCourses: Array.from(remaining),
    warnings,
  };
}

function pickElectives(
  requirementEval: RequirementEval,
  input: PlannerInput,
  coursesById: Map<CourseId, Course>
): CourseId[] {
  const picks: CourseId[] = [];
  for (const choice of requirementEval.choices) {
    const ranked = prioritizeCourses(choice.options, input, input.options?.startTerm ?? DEFAULT_OPTIONS.startTerm, coursesById);
    picks.push(...ranked.slice(0, choice.count));
  }
  return picks;
}

function isEligible(
  courseId: CourseId,
  input: PlannerInput,
  completed: Set<CourseId>,
  scheduled: Set<CourseId>,
  term: Term,
  coursesById: Map<CourseId, Course>
): boolean {
  if (completed.has(courseId) || scheduled.has(courseId)) {
    return false;
  }

  if (!isOffered(courseId, term.season, coursesById)) {
    return false;
  }

  const prereq = input.prerequisites.get(courseId);
  return prereq ? evalPrereq(prereq, completed) : true;
}

function evalPrereq(expr: PrereqExpr, completed: Set<CourseId>): boolean {
  switch (expr.type) {
    case "course":
      return completed.has(expr.courseId);
    case "and":
      return expr.items.every((item) => evalPrereq(item, completed));
    case "or":
      return expr.items.some((item) => evalPrereq(item, completed));
    case "placement":
      return false;
    default:
      return false;
  }
}

function isOffered(courseId: CourseId, season: TermSeason, coursesById: Map<CourseId, Course>): boolean {
  const course = coursesById.get(courseId);
  if (!course) {
    return false;
  }
  if (!course.offered || course.offered.length === 0) {
    return true;
  }
  return course.offered.includes(season);
}

function prioritizeCourses(
  courseIds: CourseId[],
  input: PlannerInput,
  term: Term,
  coursesById: Map<CourseId, Course>
): CourseId[] {
  const unlockDepth = computeUnlockDepth(input.prerequisites);
  return courseIds
    .slice()
    .sort((a, b) => {
      const aDepth = unlockDepth.get(a) ?? 0;
      const bDepth = unlockDepth.get(b) ?? 0;
      const aOffered = offeringWeight(a, term.season, coursesById);
      const bOffered = offeringWeight(b, term.season, coursesById);
      return bDepth - aDepth || bOffered - aOffered;
    });
}

function offeringWeight(courseId: CourseId, season: TermSeason, coursesById: Map<CourseId, Course>): number {
  const course = coursesById.get(courseId);
  if (!course?.offered || course.offered.length === 0) {
    return 0;
  }
  return course.offered.length === 1 && course.offered[0] === season ? 2 : 1;
}

function pickCoursesForTerm(
  prioritized: CourseId[],
  coursesById: Map<CourseId, Course>,
  options: PlannerOptions
): CourseId[] {
  const picked: CourseId[] = [];
  let credits = 0;
  for (const courseId of prioritized) {
    const course = coursesById.get(courseId);
    if (!course) {
      continue;
    }
    if (credits + course.credits > options.maxCredits) {
      continue;
    }
    picked.push(courseId);
    credits += course.credits;
    if (credits >= options.targetCredits) {
      break;
    }
  }
  if (credits < options.minCredits && picked.length > 0) {
    return picked;
  }
  return picked;
}

function iterateTerms(start: Term, end: Term): Term[] {
  const seasons: TermSeason[] = ["Spring", "Summer", "Fall"];
  const result: Term[] = [];
  let year = start.year;
  let seasonIndex = seasons.indexOf(start.season);

  while (year < end.year || (year === end.year && seasonIndex <= seasons.indexOf(end.season))) {
    result.push({ year, season: seasons[seasonIndex] });
    seasonIndex += 1;
    if (seasonIndex >= seasons.length) {
      seasonIndex = 0;
      year += 1;
    }
  }

  return result;
}

function computeUnlockDepth(prerequisites: Map<CourseId, PrereqExpr>): Map<CourseId, number> {
  const graph = new Map<CourseId, CourseId[]>();
  for (const [courseId, prereq] of prerequisites.entries()) {
    const deps = extractCourses(prereq);
    for (const dep of deps) {
      if (!graph.has(dep)) {
        graph.set(dep, []);
      }
      graph.get(dep)?.push(courseId);
    }
  }

  const memo = new Map<CourseId, number>();
  const dfs = (courseId: CourseId, visiting: Set<CourseId>): number => {
    if (memo.has(courseId)) {
      return memo.get(courseId) ?? 0;
    }
    if (visiting.has(courseId)) {
      return 0;
    }
    visiting.add(courseId);
    const children = graph.get(courseId) ?? [];
    let depth = 0;
    for (const child of children) {
      depth = Math.max(depth, 1 + dfs(child, visiting));
    }
    visiting.delete(courseId);
    memo.set(courseId, depth);
    return depth;
  };

  const result = new Map<CourseId, number>();
  for (const courseId of graph.keys()) {
    result.set(courseId, dfs(courseId, new Set()));
  }
  return result;
}

function extractCourses(expr: PrereqExpr): CourseId[] {
  switch (expr.type) {
    case "course":
      return [expr.courseId];
    case "and":
    case "or":
      return expr.items.flatMap(extractCourses);
    case "placement":
      return [];
    default:
      return [];
  }
}
