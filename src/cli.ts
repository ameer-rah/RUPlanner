import { evaluateRequirements } from "./requirements/engine";
import { generatePlan } from "./planner/planner";
import { courses, csRequirements, prerequisites } from "./data/sample";

const completedCourses = ["01:198:111"];

const requirementEval = evaluateRequirements(csRequirements, completedCourses, courses);

const plan = generatePlan({
  courses,
  completedCourses,
  prerequisites,
  requirementEval,
  options: {
    startTerm: { year: 2026, season: "Spring" },
    targetTerm: { year: 2028, season: "Spring" },
  },
});

const output = {
  completedCourses,
  remainingRequirements: Array.from(requirementEval.remainingCourses),
  choices: requirementEval.choices,
  notes: requirementEval.notes,
  plan,
};

console.log(JSON.stringify(output, null, 2));
