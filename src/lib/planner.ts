import { evaluateRequirements } from "../requirements/engine";
import { generatePlan } from "../planner/planner";
import { resolveProgramData } from "./programs";
import type { CourseId, StudentProfile } from "../types";

export function buildPlan(completedCourses: CourseId[], profile?: StudentProfile | null) {
  const program = resolveProgramData(profile);
  const requirementEval = evaluateRequirements(program.requirements, completedCourses, program.courses);
  const plan = generatePlan({
    courses: program.courses,
    completedCourses,
    prerequisites: program.prerequisites,
    requirementEval,
  });

  return {
    requirementEval,
    plan,
    programId: program.id,
    programWarnings: program.warnings,
  };
}
