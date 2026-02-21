import type { Course, PrereqExpr, RequirementNode } from "../types";

export const courses: Course[] = [
  { id: "01:198:111", subject: "CS", number: "111", title: "Intro CS", credits: 4, offered: ["Fall", "Spring"] },
  { id: "01:198:112", subject: "CS", number: "112", title: "Data Structures", credits: 4, offered: ["Fall", "Spring"] },
  { id: "01:198:205", subject: "CS", number: "205", title: "Intro Discrete", credits: 4, offered: ["Fall", "Spring"] },
  { id: "01:198:214", subject: "CS", number: "214", title: "Systems Programming", credits: 4, offered: ["Spring"] },
  { id: "01:198:211", subject: "CS", number: "211", title: "Computer Architecture", credits: 4, offered: ["Fall"] },
  { id: "01:198:314", subject: "CS", number: "314", title: "Algorithms", credits: 4, offered: ["Fall", "Spring"] },
  { id: "01:198:336", subject: "CS", number: "336", title: "Principles of Info", credits: 3, offered: ["Fall", "Spring"] },
  { id: "01:198:344", subject: "CS", number: "344", title: "Design & Analysis", credits: 4, offered: ["Spring"] },
  { id: "01:640:151", subject: "MATH", number: "151", title: "Calc I", credits: 4, offered: ["Fall", "Spring"] },
  { id: "01:640:152", subject: "MATH", number: "152", title: "Calc II", credits: 4, offered: ["Fall", "Spring"] },
  { id: "01:960:171", subject: "PHYS", number: "171", title: "Physics I", credits: 4, offered: ["Fall", "Spring"] },
  { id: "01:960:172", subject: "PHYS", number: "172", title: "Physics II", credits: 4, offered: ["Fall", "Spring"] },
  { id: "01:355:101", subject: "ECON", number: "101", title: "Intro Micro", credits: 3, offered: ["Fall", "Spring"] },
  { id: "01:355:102", subject: "ECON", number: "102", title: "Intro Macro", credits: 3, offered: ["Fall", "Spring"] },
];

export const prerequisites: Map<string, PrereqExpr> = new Map([
  ["01:198:112", { type: "course", courseId: "01:198:111" }],
  ["01:198:214", { type: "course", courseId: "01:198:112" }],
  ["01:198:211", { type: "course", courseId: "01:198:112" }],
  ["01:198:314", { type: "and", items: [{ type: "course", courseId: "01:198:112" }, { type: "course", courseId: "01:198:205" }] }],
  ["01:198:344", { type: "course", courseId: "01:198:314" }],
  ["01:640:152", { type: "course", courseId: "01:640:151" }],
  ["01:960:172", { type: "course", courseId: "01:960:171" }],
]);

export const csRequirements: RequirementNode = {
  type: "allOf",
  items: [
    { type: "course", courseId: "01:198:111" },
    { type: "course", courseId: "01:198:112" },
    { type: "course", courseId: "01:198:205" },
    { type: "course", courseId: "01:198:214" },
    { type: "course", courseId: "01:198:211" },
    { type: "course", courseId: "01:198:314" },
    { type: "oneOf", items: [{ type: "course", courseId: "01:198:336" }, { type: "course", courseId: "01:198:344" }] },
    { type: "course", courseId: "01:640:151" },
    { type: "course", courseId: "01:640:152" },
    { type: "course", courseId: "01:960:171" },
    { type: "course", courseId: "01:960:172" },
    { type: "oneOf", items: [{ type: "course", courseId: "01:355:101" }, { type: "course", courseId: "01:355:102" }] }
  ],
};
