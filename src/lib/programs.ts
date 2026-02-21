import { courses, csRequirements, prerequisites } from "../data/sample";
import type { Course, CourseId, PrereqExpr, RequirementNode, StudentProfile } from "../types";

export type ProgramData = {
  id: string;
  courses: Course[];
  prerequisites: Map<CourseId, PrereqExpr>;
  requirements: RequirementNode;
  warnings: string[];
};

const csAliases = new Set([
  "computer science",
  "cs",
  "cs (ba)",
  "cs (bs)",
  "computer science (ba)",
  "computer science (bs)",
]);

export function resolveProgramData(profile?: StudentProfile | null): ProgramData {
  const majors = profile?.majors ?? [];
  const majorMatch = majors.find((major) => csAliases.has(major.trim().toLowerCase()));
  if (majorMatch) {
    return {
      id: "SAS-CS",
      courses,
      prerequisites,
      requirements: csRequirements,
      warnings: [],
    };
  }

  return {
    id: "SAS-CS",
    courses,
    prerequisites,
    requirements: csRequirements,
    warnings: [
      "No recognized major found; using the Computer Science sample requirements.",
    ],
  };
}
