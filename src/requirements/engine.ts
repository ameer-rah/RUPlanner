import type { Course, CourseId, RequirementEval, RequirementNode } from "../types";

type EvalContext = {
  completed: Set<CourseId>;
  coursesById: Map<CourseId, Course>;
};

export function evaluateRequirements(
  root: RequirementNode,
  completedCourses: CourseId[],
  courses: Course[]
): RequirementEval {
  const context: EvalContext = {
    completed: new Set(completedCourses),
    coursesById: new Map(courses.map((course) => [course.id, course])),
  };

  const remainingCourses = new Set<CourseId>();
  const choices: RequirementEval["choices"] = [];
  const notes: string[] = [];

  const satisfied = evalNode(root, context, remainingCourses, choices, notes);

  return {
    satisfied,
    remainingCourses,
    choices,
    notes,
  };
}

function evalNode(
  node: RequirementNode,
  context: EvalContext,
  remainingCourses: Set<CourseId>,
  choices: RequirementEval["choices"],
  notes: string[]
): boolean {
  switch (node.type) {
    case "course": {
      const done = context.completed.has(node.courseId);
      if (!done) {
        remainingCourses.add(node.courseId);
      }
      return done;
    }
    case "allOf": {
      let ok = true;
      for (const child of node.items) {
        ok = evalNode(child, context, remainingCourses, choices, notes) && ok;
      }
      return ok;
    }
    case "oneOf": {
      const satisfied = node.items.some((child) =>
        evalNode(child, context, remainingCourses, choices, notes)
      );
      if (!satisfied) {
        const options = collectCourseOptions(node.items);
        if (options.length > 0) {
          choices.push({ count: 1, options });
        }
      }
      return satisfied;
    }
    case "nOf": {
      const hits = node.items.filter((child) =>
        evalNode(child, context, remainingCourses, choices, notes)
      ).length;
      const satisfied = hits >= node.count;
      if (!satisfied) {
        const options = collectCourseOptions(node.items);
        if (options.length > 0) {
          choices.push({ count: node.count - hits, options });
        }
      }
      return satisfied;
    }
    case "category": {
      const minCourses = node.minCourses ?? 1;
      const completed = Array.from(context.completed).filter((courseId) => {
        const course = context.coursesById.get(courseId);
        return course?.categories?.includes(node.category);
      });
      if (completed.length < minCourses) {
        notes.push(`Need ${minCourses - completed.length} more in category ${node.category}.`);
      }
      return completed.length >= minCourses;
    }
    case "creditsAtLevel": {
      let credits = 0;
      for (const courseId of context.completed) {
        const course = context.coursesById.get(courseId);
        if (!course) {
          continue;
        }
        const level = Number.parseInt(course.number, 10);
        if (course.subject === node.subject && level >= node.minLevel) {
          credits += course.credits;
        }
      }
      if (credits < node.minCredits) {
        notes.push(
          `Need ${node.minCredits - credits} more ${node.subject} credits at ${node.minLevel}+ level.`
        );
      }
      return credits >= node.minCredits;
    }
    case "creditsTotal": {
      let credits = 0;
      for (const courseId of context.completed) {
        const course = context.coursesById.get(courseId);
        if (course) {
          credits += course.credits;
        }
      }
      if (credits < node.minCredits) {
        notes.push(`Need ${node.minCredits - credits} more total credits.`);
      }
      return credits >= node.minCredits;
    }
    default:
      return false;
  }
}

function collectCourseOptions(items: RequirementNode[]): CourseId[] {
  const options: CourseId[] = [];
  for (const item of items) {
    if (item.type === "course") {
      options.push(item.courseId);
    } else if ("items" in item) {
      options.push(...collectCourseOptions(item.items));
    }
  }
  return Array.from(new Set(options));
}
