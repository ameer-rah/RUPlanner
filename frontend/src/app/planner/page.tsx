"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import CompletedCoursesInput from "../CompletedCoursesInput";
import TranscriptUpload from "../TranscriptUpload";
import ProgramSelectInput from "../ProgramSelectInput";
import PlanEditor, { PlanTerm } from "../PlanEditor";

type ProgramInfo = {
  school: string;
  degree_level: string;
  major_name: string;
  catalog_year: string;
  display_name: string;
  tracks: string[];
  track_labels: Record<string, string>;
  track_dimensions: { id: string; label: string; options: Record<string, { display_name: string }> }[];
};

type CoreCurriculumBlock = {
  title: string;
  total_courses: number | null;
  courses: string[];
  is_elective: boolean;
  completed: string[];
  needed: number;
  available_courses: string[];
  goal_slots?: string[][];
  completed_goal_tags?: string[];
};

type CourseStatus = {
  code: string;
  status: "completed" | "in_progress" | "planned" | "not_scheduled";
};

type ProgramSummary = {
  name: string;
  type: "major" | "minor";
  required: CourseStatus[];
  electives_needed: number;
  electives_completed: string[];
  electives_planned: string[];
  elective_options: string[];
  elective_min_300_plus: number;
  elective_min_400_plus: number;
  science_completed: string[];
  science_options: string[][];
  stats_completed: string[];
  stats_options: string[];
  science_statuses?: CourseStatus[];
  stats_statuses?: CourseStatus[];
  requirement_groups: { label: string; count: number; options: string[]; open_pool?: string; statuses?: CourseStatus[] }[];
};

type PlanResponse = {
  terms: PlanTerm[];
  remaining_courses: string[];
  warnings: string[];
  completion_term: string | null;
  completed_credits: number;
  total_credits: number;
  core_curriculum_name?: string;
  core_curriculum_blocks: CoreCurriculumBlock[];
  completed_course_map?: Record<string, string>;
  programs_summary?: ProgramSummary[];
};

const ALL_SEASONS = ["Spring", "Summer", "Fall", "Winter"];
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "https://api.ruplanner.com");

function defaultAcademicStart(now = new Date()): string {
  const season = now.getMonth() <= 4 ? "Spring" : "Fall";
  return `${season} ${now.getFullYear()}`;
}

function fourYearGraduation(term: string): string {
  const [season, yearText] = term.trim().split(/\s+/);
  const year = Number(yearText);
  if (!Number.isInteger(year)) return "";
  return season === "Spring" ? `Fall ${year + 3}` : `Spring ${year + 4}`;
}

function safeRemoveStorage(key: string) {
  try { localStorage.removeItem(key); } catch {}
}

function isLocalPreview(): boolean {
  if (typeof window === "undefined") return false;
  const hostname = window.location.hostname.toLowerCase();
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function getAuthHeaders(): Record<string, string> {
  try {
    const token = localStorage.getItem("ru_planner_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch { return {}; }
}

function getSeasonBtnClass(season: string, active: boolean) {
  if (!active) return "season-btn";
  if (season === "Fall") return "season-btn active-fall";
  if (season === "Spring") return "season-btn active-spring";
  if (season === "Summer") return "season-btn active-summer";
  return "season-btn active-winter";
}

function getUserInitials(email: string | null): string {
  if (!email) return "?";
  return email.charAt(0).toUpperCase();
}

function courseLevel(code: string): number {
  const match = code.match(/\d+/);
  return match ? Math.floor(Number(match[0]) / 100) * 100 : 0;
}

function liveCourseStatus(code: string, completed: Set<string>, inProgress: Set<string>, planned: Set<string>): CourseStatus["status"] {
  if (completed.has(code)) return "completed";
  if (inProgress.has(code)) return "in_progress";
  if (planned.has(code)) return "planned";
  return "not_scheduled";
}

function evaluateProgram(prog: ProgramSummary, completed: Set<string>, inProgress: Set<string>, planned: Set<string>): ProgramSummary {
  const covered = new Set([...completed, ...inProgress, ...planned]);
  const electiveMatches = [...new Set((prog.elective_options ?? []).filter((code) => covered.has(code)))];
  const electiveCompleted = electiveMatches.filter((code) => completed.has(code) || inProgress.has(code));
  const electivePlanned = electiveMatches.filter((code) => planned.has(code) && !completed.has(code) && !inProgress.has(code));

  const sciencePaths = prog.science_options ?? [];
  const selectedSciencePath = sciencePaths.reduce<string[]>((best, path) => {
    const bestCovered = best.filter((code) => covered.has(code)).length;
    const pathCovered = path.filter((code) => covered.has(code)).length;
    return pathCovered > bestCovered ? path : best;
  }, sciencePaths[0] ?? []);

  return {
    ...prog,
    required: prog.required.map(({ code }) => ({ code, status: liveCourseStatus(code, completed, inProgress, planned) })),
    electives_completed: electiveCompleted,
    electives_planned: electivePlanned,
    science_statuses: selectedSciencePath.map((code) => ({ code, status: liveCourseStatus(code, completed, inProgress, planned) })),
    stats_statuses: (prog.stats_options ?? []).map((code) => ({ code, status: liveCourseStatus(code, completed, inProgress, planned) })),
    requirement_groups: (prog.requirement_groups ?? []).map((group) => ({
      ...group,
      statuses: group.options.map((code) => ({ code, status: liveCourseStatus(code, completed, inProgress, planned) })),
    })),
  };
}

function programCoverage(prog: ProgramSummary) {
  const isCovered = (item: CourseStatus) => item.status !== "not_scheduled";
  const requiredCovered = prog.required.filter(isCovered).length;
  const electiveCodes = [...prog.electives_completed, ...prog.electives_planned];
  const electiveCovered = Math.min(prog.electives_needed, electiveCodes.length);
  const high300 = electiveCodes.filter((code) => courseLevel(code) >= 300).length;
  const high400 = electiveCodes.filter((code) => courseLevel(code) >= 400).length;
  const electiveLevelsMet = high300 >= (prog.elective_min_300_plus ?? 0) && high400 >= (prog.elective_min_400_plus ?? 0);
  const science = prog.science_statuses ?? [];
  const stats = prog.stats_statuses ?? [];
  const scienceCovered = science.filter(isCovered).length;
  const statsCovered = stats.length ? (stats.some(isCovered) ? 1 : 0) : 0;
  const consumedGroupCodes = new Set<string>();
  const groupCovered = (prog.requirement_groups ?? []).reduce((sum, group) => {
    const matches = (group.statuses ?? []).filter((item) => isCovered(item) && !consumedGroupCodes.has(item.code));
    matches.slice(0, group.count).forEach((item) => consumedGroupCodes.add(item.code));
    return sum + Math.min(group.count, matches.length);
  }, 0);
  const groupTotal = (prog.requirement_groups ?? []).reduce((sum, group) => sum + group.count, 0);
  const covered = requiredCovered + electiveCovered + scienceCovered + statsCovered + groupCovered;
  const total = prog.required.length + prog.electives_needed + science.length + (stats.length ? 1 : 0) + groupTotal;
  return { covered, total, complete: covered === total && electiveLevelsMet };
}

function UserMenu({ email, onSignOut }: { email: string | null; onSignOut: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button
        className="topbar-avatar"
        onClick={() => setOpen((v) => !v)}
        title={email ?? ""}
      >
        {getUserInitials(email)}
      </button>
      {open && (
        <>
          <div
            style={{ position: "fixed", inset: 0, zIndex: 199 }}
            onClick={() => setOpen(false)}
          />
          <div style={{
            position: "absolute", top: "calc(100% + 8px)", right: 0,
            background: "var(--surface)", border: "1.5px solid var(--border-2)",
            borderRadius: 12, boxShadow: "var(--shadow-lg)",
            minWidth: 200, zIndex: 200, overflow: "hidden",
          }}>
            <div style={{
              padding: "12px 16px 10px",
              borderBottom: "1px solid var(--border)",
            }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--text)" }}>
                {email ?? ""}
              </div>
              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>
                Signed in
              </div>
            </div>
            <button
              onClick={() => { setOpen(false); onSignOut(); }}
              style={{
                width: "100%", padding: "10px 16px", background: "none", border: "none",
                textAlign: "left", fontSize: 13, color: "var(--ru-red)", cursor: "pointer",
                fontFamily: "inherit", fontWeight: 500,
                transition: "background var(--transition-fast)",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--ru-red-light)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
            >
              Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}


function blockShortTitle(title: string): string {
  // Strip leading "R# : " prefix and keep the rest
  return title.replace(/^R\d+\s*:\s*/, "");
}

function evaluateCoreBlocks(blocks: CoreCurriculumBlock[], terms: PlanTerm[]): CoreCurriculumBlock[] {
  const plannedCourses = terms.flatMap((term) => term.courses);
  return blocks.map((block) => {
    if (block.total_courses == null) return block;
    const validCodes = new Set([...(block.courses ?? []), ...(block.available_courses ?? [])]);
    const satisfied = new Set(block.completed);
    const remainingSlots = (block.goal_slots ?? []).map((slot) => new Set(slot));
    const usedGoalTags = new Set(block.completed_goal_tags ?? []);
    const distinctInterchangeableGoals = remainingSlots.some((slot) => slot.size > 1);
    for (const completedTag of block.completed_goal_tags ?? []) {
      const slotIndex = remainingSlots.findIndex((slot) => slot.has(completedTag));
      if (slotIndex >= 0) remainingSlots.splice(slotIndex, 1);
    }
    for (const course of plannedCourses) {
      if (satisfied.has(course.code) || remainingSlots.length === 0) continue;
      const courseTags = course.core_tags ?? [];
      const slotIndex = remainingSlots.findIndex((slot) =>
        slot.size === 0
          ? validCodes.has(course.code)
          : courseTags.some((tag) => slot.has(tag) && (!distinctInterchangeableGoals || !usedGoalTags.has(tag))),
      );
      if (slotIndex < 0) continue;
      const matchedTag = courseTags.find((tag) => remainingSlots[slotIndex].has(tag)
        && (!distinctInterchangeableGoals || !usedGoalTags.has(tag)));
      if (matchedTag) usedGoalTags.add(matchedTag);
      remainingSlots.splice(slotIndex, 1);
      satisfied.add(course.code);
    }
    return {
      ...block,
      completed: [...satisfied],
      needed: remainingSlots.length,
    };
  });
}

function CollapsiblePanel({ title, badge, defaultOpen = false, children }: {
  title: string;
  badge?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{
      background: "var(--surface)",
      border: "1.5px solid var(--border-2)",
      borderRadius: 14,
      marginBottom: 16,
      overflow: "hidden",
    }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 20px",
          background: "none",
          border: "none",
          cursor: "pointer",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>{title}</span>
          {badge && (
            <span style={{ fontSize: 11, background: "var(--border-2)", color: "var(--text-3)", borderRadius: 99, padding: "1px 8px", fontWeight: 600 }}>
              {badge}
            </span>
          )}
        </div>
        <span style={{ fontSize: 11, color: "var(--text-3)", transform: open ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>▼</span>
      </button>
      {open && (
        <div style={{ padding: "0 20px 16px" }}>
          {children}
        </div>
      )}
    </div>
  );
}

function CoreBlockRow({ block }: { block: CoreCurriculumBlock }) {
  const [expanded, setExpanded] = useState(false);
  const short = blockShortTitle(block.title);
  const isComplete = block.needed === 0;
  const isPartial = !isComplete && block.completed.length > 0;
  const isOpenBlock = !isComplete && block.courses.length === 0;

  const badgeStyle = isComplete
    ? { background: "rgba(34,197,94,0.12)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.2)" }
    : isPartial
    ? { background: "rgba(245,158,11,0.12)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.2)" }
    : { background: "var(--surface-2)", color: "var(--text-3)", border: "1px solid var(--border-2)" };

  const badgeText = isComplete ? "Complete" : isPartial ? "Partial" : "Not Started";

  return (
    <div style={{
      background: isComplete ? "rgba(34,197,94,0.03)" : "var(--surface-2)",
      border: `1px solid ${isComplete ? "rgba(34,197,94,0.15)" : "var(--border)"}`,
      borderRadius: 10,
      overflow: "hidden",
      transition: "border-color 150ms",
    }}>
      <button
        onClick={() => !isComplete && setExpanded((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          background: "none",
          border: "none",
          cursor: isComplete ? "default" : "pointer",
          gap: 10,
          textAlign: "left",
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", flex: 1 }}>{short}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 99, letterSpacing: "0.04em", textTransform: "uppercase" as const, ...badgeStyle }}>
            {badgeText}
          </span>
          {!isComplete && (
            <span style={{ fontSize: 10, color: "var(--text-3)", display: "inline-block", transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}>▼</span>
          )}
        </div>
      </button>

      {!isComplete && expanded && (
        <div style={{ padding: "0 14px 12px" }}>
          {block.completed.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 8 }}>
              {block.completed.map((code) => (
                <span key={code} style={{ fontSize: 11, fontWeight: 600, padding: "2px 7px", borderRadius: 4, background: "rgba(34,197,94,0.12)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.2)" }}>
                  {code}
                </span>
              ))}
            </div>
          )}
          <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 8 }}>
            {isOpenBlock
              ? `Need ${block.needed} more — select from Degree Navigator`
              : `Need ${block.needed} more course${block.needed !== 1 ? "s" : ""}`}
          </div>
          {!isOpenBlock && (block.available_courses ?? []).length > 0 && (
            <>
              <div style={{ fontSize: 10, color: "var(--text-3)", marginBottom: 5, textTransform: "uppercase" as const, letterSpacing: "0.05em", fontWeight: 600 }}>
                Courses that satisfy this
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {(block.available_courses ?? []).slice(0, 30).map((code) => (
                  <span key={code} style={{ fontSize: 11, fontWeight: 500, padding: "2px 7px", borderRadius: 4, background: "var(--surface-3)", color: "var(--text-2)", border: "1px solid var(--border-2)" }}>
                    {code}
                  </span>
                ))}
                {(block.available_courses ?? []).length > 30 && (
                  <span style={{ fontSize: 11, color: "var(--text-3)", alignSelf: "center" }}>
                    +{(block.available_courses ?? []).length - 30} more
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {isComplete && block.completed.length > 0 && (
        <div style={{ padding: "0 14px 10px", display: "flex", flexWrap: "wrap", gap: 4 }}>
          {block.completed.map((code) => (
            <span key={code} style={{ fontSize: 11, fontWeight: 600, padding: "2px 7px", borderRadius: 4, background: "rgba(34,197,94,0.12)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.2)" }}>
              {code}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function CoreCurriculumPanel({ name, blocks, terms }: { name: string; blocks: CoreCurriculumBlock[]; terms: PlanTerm[] }) {
  if (!blocks.length) return null;

  const liveBlocks = evaluateCoreBlocks(blocks, terms);

  const doneCount = liveBlocks.filter((b) => b.needed === 0).length;
  const pct = Math.round((doneCount / liveBlocks.length) * 100);
  const badge = `${doneCount}/${liveBlocks.length} complete`;
  return (
    <CollapsiblePanel title={name} badge={badge}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-3)", marginBottom: 5 }}>
          <span>Overall completion</span>
          <span>{pct}%</span>
        </div>
        <div style={{ height: 4, background: "var(--surface-3)", borderRadius: 99, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: "var(--ru-red)", borderRadius: 99, transition: "width 0.4s cubic-bezier(0.4,0,0.2,1)" }} />
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {liveBlocks.map((blk, i) => (
          <CoreBlockRow key={i} block={blk} />
        ))}
      </div>
    </CollapsiblePanel>
  );
}

function CourseChip({ code, status }: { code: string; status: "completed" | "in_progress" | "planned" | "not_scheduled" }) {
  const style =
    status === "completed"     ? { background: "#dcfce7", color: "#166534", borderColor: "#bbf7d0" } :
    status === "in_progress"   ? { background: "#fef3c7", color: "#92400e", borderColor: "#fde68a" } :
    status === "planned"       ? { background: "var(--surface-2,#f3f4f6)", color: "var(--text-2)", borderColor: "var(--border-2)" } :
                                 { background: "#fff1f2", color: "#9f1239", borderColor: "#fecdd3" };
  return <span className="plan-completed-chip" style={style}>{code}</span>;
}

function ReqRow({ label, items }: { label: string; items: CourseStatus[] }) {
  if (!items.length) return null;
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
      <span style={{ fontSize: 10, fontWeight: 600, color: "var(--text-3)", minWidth: 120, flexShrink: 0, textTransform: "uppercase", letterSpacing: "0.05em", paddingTop: 3 }}>
        {label}
      </span>
      <div className="plan-completed-chips" style={{ margin: 0, flexWrap: "wrap" }}>
        {items.map((cs) => <CourseChip key={cs.code} code={cs.code} status={cs.status} />)}
      </div>
    </div>
  );
}

function ProgramRequirementsPanel({ prog }: { prog: ProgramSummary }) {
  const doneCount = prog.required.filter((c) => c.status !== "not_scheduled").length;
  const totalReq = prog.required.length;
  const elecDone = prog.electives_completed.length + prog.electives_planned.length;
  const elecNeeded = prog.electives_needed;
  const coverage = programCoverage(prog);
  const allDone = coverage.complete;
  const badge = allDone ? "Complete" : `${doneCount}/${totalReq} req · ${elecDone}/${elecNeeded} elec`;

  const typeLabel = prog.type === "major" ? "Major" : prog.type === "minor" ? "Minor" : "Concentration";

  return (
    <CollapsiblePanel title={`${typeLabel}: ${prog.name}`} badge={badge} defaultOpen>
      <div style={{ marginBottom: 4 }}>
        <div style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 6 }}>
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#dcfce7", border: "1px solid #bbf7d0", marginRight: 4 }} />completed&nbsp;
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#fef3c7", border: "1px solid #fde68a", marginRight: 4, marginLeft: 8 }} />in progress&nbsp;
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "var(--surface-2,#f3f4f6)", border: "1px solid var(--border-2)", marginRight: 4, marginLeft: 8 }} />planned&nbsp;
          <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "#fff1f2", border: "1px solid #fecdd3", marginRight: 4, marginLeft: 8 }} />not scheduled
        </div>
      </div>

      <ReqRow label="Required" items={prog.required} />

      {(prog.science_statuses ?? []).length > 0 && (
        <ReqRow label="Science Req" items={prog.science_statuses ?? []} />
      )}
      {(prog.stats_statuses ?? []).length > 0 && (
        <ReqRow label="Stats Req (choose one)" items={prog.stats_statuses ?? []} />
      )}

      {elecNeeded > 0 && (
        <ReqRow
          label={`Electives (${elecDone}/${elecNeeded})`}
          items={[
            ...prog.electives_completed.map((c) => ({ code: c, status: "completed" as const })),
            ...prog.electives_planned.map((c) => ({ code: c, status: "planned" as const })),
          ]}
        />
      )}
      {(prog.requirement_groups ?? []).map((group) => (
        <ReqRow
          key={group.label}
          label={`${group.label} (${group.count})`}
          items={group.statuses ?? group.options.map((code) => ({ code, status: "not_scheduled" as const }))}
        />
      ))}
      {(prog.requirement_groups ?? []).filter((group) => group.open_pool).map((group) => (
        <div key={`${group.label}-note`} style={{ marginTop: 8, fontSize: 11, color: "var(--amber)" }}>
          {group.label}: {group.open_pool}
        </div>
      ))}
      {!allDone && elecDone >= elecNeeded && (
        <div style={{ marginTop: 8, fontSize: 11, color: "var(--amber)" }}>
          Check the highlighted required, science, statistics, and upper-level elective constraints before graduating.
        </div>
      )}
    </CollapsiblePanel>
  );
}

const WIZARD_STEPS = ["Degree", "Program", "Start", "Schedule", "Transcript", "Generate"];

type WizardProps = {
  step: number; onStepChange: (s: number) => void;
  degreeFilter: string; setDegreeFilter: (v: string) => void;
  majorPrograms: ProgramInfo[]; minorPrograms: ProgramInfo[];
  selectedMajors: string[]; setSelectedMajors: (v: string[]) => void;
  selectedMajorTracks: Record<string, string>; setSelectedMajorTracks: (v: (prev: Record<string, string>) => Record<string, string>) => void;
  selectedMinors: string[]; setSelectedMinors: (v: string[]) => void;
  selectedMinorTracks: Record<string, string>; setSelectedMinorTracks: (v: (prev: Record<string, string>) => Record<string, string>) => void;
  startTerm: string; setStartTerm: (v: string) => void;
  targetGradTerm: string; setTargetGradTerm: (v: string) => void;
  maxCredits: number; setMaxCredits: (v: number) => void;
  preferredSeasons: string[]; toggleSeason: (s: string) => void;
  completedCourses: string[]; setCompletedCourses: (v: string[]) => void;
  setInProgressCourses: (fn: (prev: string[]) => string[]) => void;
  onSubmit: (e: { preventDefault(): void }) => void;
  status: string;
};

function WizardPreviewPanel({ step, degreeFilter, selectedMajors }: { step: number; degreeFilter: string; selectedMajors: string[] }) {
  const previewData = [
    {
      term: "Fall 2025", delay: "0s", anim: "wizard-float-a 3.2s ease-in-out infinite",
      courses: [{ code: "CS111", cr: 3 }, { code: "MATH151", cr: 4 }, { code: "EXPOS101", cr: 3 }, { code: "PHYS201", cr: 3 }],
    },
    {
      term: "Spring 2026", delay: "0.4s", anim: "wizard-float-b 2.8s ease-in-out infinite",
      courses: [{ code: "CS112", cr: 4 }, { code: "MATH152", cr: 4 }, { code: "CS205", cr: 3 }, { code: "ECE211", cr: 3 }],
    },
    {
      term: "Fall 2026", delay: "0.8s", anim: "wizard-float-c 3.6s ease-in-out infinite",
      courses: [{ code: "CS344", cr: 3 }, { code: "CS211", cr: 4 }, { code: "STAT355", cr: 3 }],
    },
  ];

  const label = step === 0
    ? (degreeFilter === "master" ? "Graduate programs" : "Undergraduate programs")
    : step === 1 && selectedMajors[0]
    ? selectedMajors[0].split("(")[0].trim()
    : step === 5
    ? "Your plan is ready to generate"
    : "Your degree plan";

  return (
    <div style={{ width: "100%", minHeight: "100%", padding: "32px 40px 48px", display: "flex", flexDirection: "column", gap: 0 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>Preview</div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text)", letterSpacing: "-0.02em" }}>{label}</div>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 14 }}>
        {previewData.map((sem) => (
          <div
            key={sem.term}
            style={{
              background: "var(--surface-2)",
              border: "1.5px solid var(--border-2)",
              borderRadius: 14,
              padding: "14px 16px",
              animation: sem.anim,
              animationDelay: sem.delay,
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-3)", letterSpacing: "0.04em", textTransform: "uppercase", marginBottom: 10 }}>
              {sem.term}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {sem.courses.map((c) => (
                <div
                  key={c.code}
                  style={{
                    fontSize: 11, padding: "4px 10px", borderRadius: 8,
                    background: "var(--surface-3)", border: "1px solid var(--border-2)",
                    color: "var(--text-2)", fontWeight: 600,
                    display: "flex", alignItems: "center", gap: 5,
                  }}
                >
                  {c.code}
                  <span style={{ color: "var(--text-3)", fontWeight: 400 }}>{c.cr}cr</span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 10, fontSize: 11, color: "var(--text-3)" }}>
              {sem.courses.reduce((s, c) => s + c.cr, 0)} credits
            </div>
          </div>
        ))}
      </div>
      <div style={{
        marginTop: 20, padding: "14px 16px", background: "rgba(204,17,51,0.06)",
        border: "1.5px solid rgba(204,17,51,0.2)", borderRadius: 12,
      }}>
        <div style={{ fontSize: 11, color: "var(--ru-red)", fontWeight: 700, marginBottom: 3 }}>Degree progress</div>
        <div style={{ background: "var(--border-2)", borderRadius: 99, height: 4, overflow: "hidden" }}>
          <div style={{ width: "34%", height: "100%", background: "var(--ru-red)", borderRadius: 99, transition: "width 0.6s ease" }} />
        </div>
        <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 5 }}>42 / 120 credits completed</div>
      </div>
    </div>
  );
}

function WizardStepContent({
  step = 0,
  degreeFilter, setDegreeFilter,
  majorPrograms, minorPrograms,
  selectedMajors, setSelectedMajors,
  selectedMajorTracks, setSelectedMajorTracks,
  selectedMinors, setSelectedMinors,
  selectedMinorTracks, setSelectedMinorTracks,
  startTerm, setStartTerm,
  targetGradTerm, setTargetGradTerm,
  maxCredits, setMaxCredits,
  preferredSeasons, toggleSeason,
  completedCourses, setCompletedCourses, setInProgressCourses,
}: Omit<WizardProps, "onStepChange" | "onSubmit" | "status">) {
  const updateStartTerm = (next: string) => {
    const currentAutoTarget = fourYearGraduation(startTerm);
    const nextAutoTarget = fourYearGraduation(next);
    if (targetGradTerm === currentAutoTarget && nextAutoTarget) setTargetGradTerm(nextAutoTarget);
    setStartTerm(next);
  };
  if (step === 0) return (
    <div>
      <p style={{ fontSize: 26, fontWeight: 700, color: "var(--text)", marginBottom: 8, letterSpacing: "-0.03em", lineHeight: 1.2 }}>
        What degree are you pursuing?
      </p>
      <p style={{ fontSize: 14, color: "var(--text-3)", marginBottom: 28, lineHeight: 1.5 }}>
        Select your degree level to see available Rutgers programs.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {[
          { key: "bachelor", label: "Bachelor's", desc: "BA, BS, BFA, and other undergraduate degrees" },
          { key: "master",   label: "Master's",   desc: "MS, MA, MEng, and other graduate degrees" },
        ].map((opt) => (
          <button
            key={opt.key}
            type="button"
            onClick={() => setDegreeFilter(opt.key)}
            style={{
              width: "100%", textAlign: "left", padding: "18px 20px",
              borderRadius: 14, cursor: "pointer", fontFamily: "inherit",
              background: degreeFilter === opt.key ? "rgba(204,17,51,0.07)" : "var(--surface-2)",
              border: degreeFilter === opt.key ? "1.5px solid var(--ru-red)" : "1.5px solid var(--border-2)",
              transition: "all 0.15s",
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 700, color: degreeFilter === opt.key ? "var(--ru-red)" : "var(--text)", marginBottom: 3 }}>
              {opt.label}
            </div>
            <div style={{ fontSize: 13, color: "var(--text-3)" }}>{opt.desc}</div>
          </button>
        ))}
      </div>
    </div>
  );

  if (step === 1) return (
    <div>
      <p style={{ fontSize: 26, fontWeight: 700, color: "var(--text)", marginBottom: 8, letterSpacing: "-0.03em", lineHeight: 1.2 }}>
        What&apos;s your major?
      </p>
      <p style={{ fontSize: 14, color: "var(--text-3)", marginBottom: 28, lineHeight: 1.5 }}>
        Search and select your major program. You can add minors too.
      </p>
      <div style={{ marginBottom: 20 }}>
        <label className="label" style={{ marginBottom: 8, display: "block" }}>Major(s)</label>
        <ProgramSelectInput programs={majorPrograms} value={selectedMajors} onChange={setSelectedMajors} placeholder="Search by name or school…" />
        {selectedMajors.map((majorName) => {
          const prog = majorPrograms.find((p) => p.display_name === majorName);
          if (!prog?.tracks?.length) return null;
          return (
            <div key={majorName} style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 11, color: "var(--text-3)", flexShrink: 0 }}>{prog.major_name} track:</span>
              <select
                value={selectedMajorTracks[majorName] ?? ""}
                onChange={(e) => setSelectedMajorTracks((prev) => ({ ...prev, [majorName]: e.target.value }))}
                style={{ fontSize: 12, padding: "3px 6px", borderRadius: 6, border: "1px solid var(--border-2)", background: "var(--surface)", color: "var(--text)", flex: 1 }}
              >
                <option value="">Select track…</option>
                {prog.tracks.map((track) => <option key={track} value={track}>{track.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}</option>)}
              </select>
            </div>
          );
        })}
      </div>
      <div>
        <label className="label" style={{ marginBottom: 8, display: "block" }}>
          Minor(s) <span className="label-optional">optional</span>
        </label>
        <ProgramSelectInput programs={minorPrograms} value={selectedMinors} onChange={setSelectedMinors} placeholder="Search minors…" />
        {selectedMinors.filter((minor) => selectedMinorTracks[minor]).map((minor) => (
          <div key={minor} style={{ marginTop: 8, fontSize: 11, color: "var(--text-3)" }}>
            Track: {selectedMinorTracks[minor].replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}
          </div>
        ))}
      </div>
    </div>
  );

  if (step === 2) return (
    <div>
      <p style={{ fontSize: 26, fontWeight: 700, color: "var(--text)", marginBottom: 8, letterSpacing: "-0.03em", lineHeight: 1.2 }}>
        When do you start?
      </p>
      <p style={{ fontSize: 14, color: "var(--text-3)", marginBottom: 28, lineHeight: 1.5 }}>
        Select the semester you are currently in or starting next.
      </p>
      <label className="label" style={{ marginBottom: 10, display: "block" }}>Starting term</label>
      <div className="start-term-row" style={{ marginBottom: 0 }}>
        {["Fall", "Spring", "Summer", "Winter"].map((s) => (
          <button key={s} type="button"
            className={`season-btn${startTerm.startsWith(s) ? ` active-${s.toLowerCase()}` : ""}`}
            onClick={() => updateStartTerm(`${s} ${startTerm.split(" ")[1] ?? new Date().getFullYear()}`)}
          >{s}</button>
        ))}
        <input
          className="input start-term-year"
          value={startTerm.split(" ")[1] ?? ""}
          onChange={(e) => updateStartTerm(`${startTerm.split(" ")[0]} ${e.target.value}`)}
          placeholder={String(new Date().getFullYear())} maxLength={4}
        />
      </div>
    </div>
  );

  if (step === 3) return (
    <div>
      <p style={{ fontSize: 26, fontWeight: 700, color: "var(--text)", marginBottom: 8, letterSpacing: "-0.03em", lineHeight: 1.2 }}>
        When do you want to graduate?
      </p>
      <p style={{ fontSize: 14, color: "var(--text-3)", marginBottom: 28, lineHeight: 1.5 }}>
        Set your target graduation date and schedule preferences.
      </p>
      <div style={{ marginBottom: 20 }}>
        <label className="label" style={{ marginBottom: 8, display: "block" }}>Target graduation</label>
        <input className="input" value={targetGradTerm} onChange={(e) => setTargetGradTerm(e.target.value)} placeholder={`e.g. ${fourYearGraduation(defaultAcademicStart())}`} />
      </div>
      <div style={{ marginBottom: 20 }}>
        <label className="label" style={{ marginBottom: 8, display: "block" }}>Max credits per term</label>
        <div className="credit-slider-row">
          <input type="range" min={6} max={21} value={maxCredits} onChange={(e) => setMaxCredits(Number(e.target.value))} className="credit-slider" />
          <span className="credit-value">{maxCredits}</span>
        </div>
      </div>
      <div>
        <label className="label" style={{ marginBottom: 10, display: "block" }}>Semesters to enroll in</label>
        <div className="season-toggles">
          {["Spring", "Summer", "Fall", "Winter"].map((season) => (
            <button key={season} type="button" className={getSeasonBtnClass(season, preferredSeasons.includes(season))} onClick={() => toggleSeason(season)}>
              {season}
            </button>
          ))}
        </div>
        {preferredSeasons.length === 0 && <p style={{ fontSize: 12, color: "var(--ru-red)", marginTop: 8, marginBottom: 0 }}>Select at least one semester.</p>}
        {preferredSeasons.includes("Summer") && <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 6, marginBottom: 0, lineHeight: 1.4 }}>Summer: max 12 credits total.</p>}
        {preferredSeasons.includes("Winter") && <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 6, marginBottom: 0, lineHeight: 1.4 }}>Winter: max 4 credits. Not for first-years or GPA &lt; 2.0.</p>}
      </div>
    </div>
  );

  // step 4 — Transcript
  if (step === 4) return (
    <div>
      <p style={{ fontSize: 26, fontWeight: 700, color: "var(--text)", marginBottom: 8, letterSpacing: "-0.03em", lineHeight: 1.2 }}>
        What have you completed?
      </p>
      <p style={{ fontSize: 14, color: "var(--text-3)", marginBottom: 28, lineHeight: 1.5 }}>
        Upload your transcript or add courses manually. You can skip this step.
      </p>
      <TranscriptUpload
        onCoursesDetected={(codes) => setCompletedCourses([...new Set([...completedCourses, ...codes])])}
        onInProgressDetected={(codes) => setInProgressCourses((prev) => [...new Set([...prev, ...codes])])}
      />
      <CompletedCoursesInput value={completedCourses} onChange={setCompletedCourses} />
    </div>
  );

  // step 5 — Generate (review + submit)
  const rows: { label: string; value: string }[] = [
    { label: "Degree", value: degreeFilter === "master" ? "Master's" : "Bachelor's" },
    { label: "Major", value: selectedMajors.join(", ") || "—" },
    { label: "Start", value: startTerm || "—" },
    { label: "Graduation", value: targetGradTerm || "—" },
    { label: "Max credits / term", value: String(maxCredits) },
    { label: "Semesters", value: preferredSeasons.join(", ") || "—" },
    { label: "Completed courses", value: completedCourses.length > 0 ? `${completedCourses.length} courses` : "None added" },
  ];
  return (
    <div>
      <p style={{ fontSize: 26, fontWeight: 700, color: "var(--text)", marginBottom: 8, letterSpacing: "-0.03em", lineHeight: 1.2 }}>
        Ready to generate your plan.
      </p>
      <p style={{ fontSize: 14, color: "var(--text-3)", marginBottom: 28, lineHeight: 1.5 }}>
        Review your selections below, then hit generate.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 1, borderRadius: 12, overflow: "hidden", border: "1.5px solid var(--border-2)" }}>
        {rows.map((row) => (
          <div key={row.label} style={{ display: "flex", justifyContent: "space-between", padding: "11px 16px", background: "var(--surface-2)", gap: 12 }}>
            <span style={{ fontSize: 13, color: "var(--text-3)", flexShrink: 0 }}>{row.label}</span>
            <span style={{ fontSize: 13, color: "var(--text)", fontWeight: 600, textAlign: "right" }}>{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function FullPageWizard(props: WizardProps & { compact?: boolean }) {
  const { step, onStepChange, onSubmit, status, compact } = props;
  const total = WIZARD_STEPS.length;

  function canAdvance() {
    if (step === 1) return props.selectedMajors.length > 0;
    if (step === 3) return props.preferredSeasons.length > 0 && !!props.targetGradTerm.trim();
    return true;
  }

  if (compact) return (
    <form onSubmit={onSubmit} className="form" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <span style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase" }}>Step {step + 1} of {total}</span>
          <span style={{ fontSize: 11, color: "var(--text-3)" }}>{WIZARD_STEPS[step]}</span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {WIZARD_STEPS.map((_, i) => (
            <div key={i} onClick={() => i < step && onStepChange(i)}
              style={{ flex: 1, height: 3, borderRadius: 99, background: i <= step ? "var(--ru-red)" : "var(--border-2)", cursor: i < step ? "pointer" : "default", transition: "background 0.2s" }}
            />
          ))}
        </div>
      </div>
      <div key={step} className="wizard-step-anim" style={{ flex: 1, overflowY: "auto" }}>
        <WizardStepContent {...props} step={step} />
      </div>
      <div style={{ paddingTop: 14, borderTop: "1px solid var(--border-2)", marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
        {step < total - 1 ? (
          <button type="button" className="primary-button" disabled={!canAdvance()} onClick={() => onStepChange(step + 1)}>Next →</button>
        ) : (
          <button type="button" className="primary-button" onClick={() => onSubmit({ preventDefault: () => {} })}>Generate my plan</button>
        )}
        {step > 0 && (
          <button type="button" onClick={() => onStepChange(step - 1)} style={{ width: "100%", padding: "10px 0", borderRadius: 10, border: "1px solid var(--border-2)", background: "transparent", color: "var(--text-2)", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
            ← Back
          </button>
        )}
        {status && <p className="status-msg" style={{ margin: 0 }}>{status}</p>}
      </div>
    </form>
  );

  return (
    <form onSubmit={onSubmit} className="wizard-fullpage">
      {/* Left panel */}
      <div className="wizard-left">
        {/* Step indicator */}
        <div style={{ marginBottom: 40 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 12, color: "var(--text-3)", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
              Step {step + 1} of {total}
            </span>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>{WIZARD_STEPS[step]}</span>
          </div>
          <div style={{ display: "flex", gap: 5 }}>
            {WIZARD_STEPS.map((_, i) => (
              <div
                key={i}
                onClick={() => i < step && onStepChange(i)}
                style={{
                  flex: 1, height: 3, borderRadius: 99,
                  background: i <= step ? "var(--ru-red)" : "var(--border-2)",
                  cursor: i < step ? "pointer" : "default",
                  transition: "background 0.25s",
                }}
              />
            ))}
          </div>
        </div>

        {/* Animated step content */}
        <div key={step} className="wizard-step-anim" style={{ flex: 1, overflowY: "auto", paddingBottom: 8 }}>
          <WizardStepContent {...props} step={step} />
        </div>

        {/* Navigation */}
        <div style={{ paddingTop: 20, borderTop: "1px solid var(--border)", marginTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
          {step < total - 1 ? (
            <button
              type="button"
              className="primary-button"
              disabled={!canAdvance()}
              onClick={() => onStepChange(step + 1)}
            >
              Next →
            </button>
          ) : (
            <button
              type="button"
              className="primary-button"
              onClick={() => onSubmit({ preventDefault: () => {} })}
            >
              Generate my plan
            </button>
          )}
          {step > 0 && (
            <button
              type="button"
              onClick={() => onStepChange(step - 1)}
              style={{
                width: "100%", padding: "11px 0", borderRadius: 10,
                border: "1px solid var(--border-2)", background: "transparent",
                color: "var(--text-2)", fontSize: 13, fontWeight: 600,
                cursor: "pointer", fontFamily: "inherit", transition: "background 0.15s",
              }}
            >
              ← Back
            </button>
          )}
          {status && <p className="status-msg" style={{ margin: 0, textAlign: "center" }}>{status}</p>}
        </div>
      </div>

      {/* Right panel — decorative preview */}
      <div className="wizard-right">
        <WizardPreviewPanel step={step} degreeFilter={props.degreeFilter} selectedMajors={props.selectedMajors} />
      </div>
    </form>
  );
}

function TrackSelectionModal({ program, onSelect, onRemove }: { program: ProgramInfo; onSelect: (track: string) => void; onRemove: () => void }) {
  const [dimensionIndex, setDimensionIndex] = useState(0);
  const [dimensionSelections, setDimensionSelections] = useState<string[]>([]);
  const dimension = program.track_dimensions?.[dimensionIndex];
  const choices = dimension ? Object.keys(dimension.options) : program.tracks;
  const choose = (choice: string) => {
    if (!dimension) return onSelect(choice);
    const next = [...dimensionSelections, choice];
    if (dimensionIndex + 1 < program.track_dimensions.length) {
      setDimensionSelections(next);
      setDimensionIndex((value) => value + 1);
    } else onSelect(next.join("/"));
  };
  return (
    <div className="modal-overlay">
      <div className="elective-modal" role="dialog" aria-modal="true" aria-labelledby="track-modal-title" style={{ maxWidth: 480 }}>
        <div className="elective-modal-header">
          <div>
            <div id="track-modal-title" className="elective-modal-title">Choose {dimension?.label?.toLowerCase() ?? "a track"}</div>
            <div className="elective-modal-sub">{program.major_name} requires this selection before RU Planner can build an accurate schedule.</div>
          </div>
        </div>
        <div className="elective-options-list" style={{ padding: 12 }}>
          {choices.map((track, index) => (
            <button key={track} className="elective-option-row" onClick={() => choose(track)} autoFocus={index === 0}>
              <div className="elective-option-code">{dimension?.options[track]?.display_name ?? program.track_labels?.[track] ?? track.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}</div>
            </button>
          ))}
          <button className="elective-option-row" onClick={onRemove} style={{ marginTop: 8, color: "var(--ru-red)" }}>
            Remove {program.degree_level === "minor" ? "minor" : "program"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PlannerPage() {
  const router = useRouter();
  const [selectedMajors, setSelectedMajors] = useState<string[]>([]);
  const [selectedMajorTracks, setSelectedMajorTracks] = useState<Record<string, string>>({});
  const [selectedMinors, setSelectedMinors] = useState<string[]>([]);
  // Maps minor display_name → chosen track (only for minors that have tracks)
  const [selectedMinorTracks, setSelectedMinorTracks] = useState<Record<string, string>>({});
  const [completedCourses, setCompletedCourses] = useState<string[]>([]);
  const [inProgressCourses, setInProgressCourses] = useState<string[]>([]);
  const [startTerm, setStartTerm] = useState(defaultAcademicStart);
  const [targetGradTerm, setTargetGradTerm] = useState(() => fourYearGraduation(defaultAcademicStart()));
  const [maxCredits, setMaxCredits] = useState(18);
  const [preferredSeasons, setPreferredSeasons] = useState<string[]>(["Spring", "Fall"]);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [planKey, setPlanKey] = useState(0);
  const [status, setStatus] = useState("");
  const [programs, setPrograms] = useState<ProgramInfo[]>([]);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState("");
  const [degreeFilter, setDegreeFilter] = useState<string>("bachelor");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);

  const editedTermsRef = useRef<PlanTerm[]>([]);
  const [editedTerms, setEditedTerms] = useState<PlanTerm[]>([]);

  const handleTermsChange = useCallback((terms: PlanTerm[]) => {
    editedTermsRef.current = terms;
    setEditedTerms(terms);
  }, []);

  useEffect(() => {
    router.prefetch("/schedules");
    async function checkAuthAndLoadPrograms() {
      try {
        const localBypass = isLocalPreview();
        if (localBypass) {
          setUserEmail("local-preview@ruplanner.dev");
          const programsRes = await fetch(`${apiBase}/programs`);
          if (programsRes.ok) setPrograms(await programsRes.json());
          return;
        }
        const meRes = await fetch(`${apiBase}/auth/me`, { credentials: 'include', headers: getAuthHeaders() });
        if (!meRes.ok) {
          router.push("/");
          return;
        }
        const me = await meRes.json();
        setUserEmail(me.email);

        if (me.onboarding_completed) {
          const profileRes = await fetch(`${apiBase}/profile`, {
            credentials: "include",
            headers: getAuthHeaders(),
          });
          if (profileRes.ok) {
            const saved = await profileRes.json();
            const profile = saved.planner_profile;
            const lastPlan = saved.last_plan as PlanResponse | null;
            if (profile) {
              setDegreeFilter(profile.degree_level ?? "bachelor");
              setSelectedMajors(profile.majors ?? []);
              setSelectedMinors(profile.minors ?? []);
              setCompletedCourses(profile.completed_courses ?? []);
              setInProgressCourses(profile.in_progress_courses ?? []);
              const savedStart = profile.start_term ?? defaultAcademicStart();
              const savedGraduation = profile.target_grad_term ?? fourYearGraduation(savedStart);
              setStartTerm(savedStart);
              // Migrate the old two-year default that made nearly every fresh
              // plan appear impossible. Explicitly chosen dates are preserved.
              const legacyTwoYearDefault = savedStart === "Fall 2026" && savedGraduation === "Spring 2028";
              setTargetGradTerm(legacyTwoYearDefault ? fourYearGraduation(savedStart) : savedGraduation);
              setMaxCredits(profile.max_credits_per_term ?? 18);
              setPreferredSeasons(profile.preferred_seasons ?? ["Spring", "Fall"]);
              if (lastPlan && !legacyTwoYearDefault) {
                setPlan(lastPlan);
                setEditedTerms(lastPlan.terms);
                editedTermsRef.current = lastPlan.terms;
                setPlanKey((key) => key + 1);
              }
            }
          }
        }

        const programsRes = await fetch(`${apiBase}/programs`, { credentials: 'include', headers: getAuthHeaders() });
        if (programsRes.ok) {
          const data = await programsRes.json();
          setPrograms(data);
        }
      } catch {
        router.push("/");
      }
    }
    checkAuthAndLoadPrograms();
  }, [router]);

  const DEGREE_FILTERS = [
    { key: "bachelor", label: "Bachelor's", levels: new Set(["bachelor_ba","bachelor_bs","bachelor_bfa","bachelor_bm","bachelor_bsba","bachelor_bsla"]) },
    { key: "master",   label: "Master's",   levels: new Set(["master","master_ms","master_ma","master_mat","master_meng"]) },
  ];
  const activeFilter = DEGREE_FILTERS.find((f) => f.key === degreeFilter)!;
  const majorPrograms = programs.filter(
    (p) => p.degree_level !== "minor" && p.degree_level !== "concentration" && activeFilter.levels.has(p.degree_level)
  );
  const minorPrograms = programs.filter((p) => p.degree_level === "minor");
  const hasTrackChoices = (program?: ProgramInfo) => Boolean(program && (program.tracks.length || program.track_dimensions?.length));
  const pendingTrackProgram = useMemo(() => {
    for (const selected of selectedMajors) {
      const program = majorPrograms.find((candidate) => candidate.display_name === selected);
      if (hasTrackChoices(program) && !selectedMajorTracks[selected]) return program;
    }
    for (const selected of selectedMinors) {
      const program = minorPrograms.find((candidate) => candidate.display_name === selected);
      if (hasTrackChoices(program) && !selectedMinorTracks[selected]) return program;
    }
    return null;
  }, [selectedMajors, selectedMinors, selectedMajorTracks, selectedMinorTracks, majorPrograms, minorPrograms]);

  function selectPendingTrack(track: string) {
    if (!pendingTrackProgram) return;
    const selected = pendingTrackProgram.display_name;
    if (pendingTrackProgram.degree_level === "minor") setSelectedMinorTracks((previous) => ({ ...previous, [selected]: track }));
    else setSelectedMajorTracks((previous) => ({ ...previous, [selected]: track }));
  }

  function removePendingTrackProgram() {
    if (!pendingTrackProgram) return;
    if (pendingTrackProgram.degree_level === "minor") setSelectedMinors((current) => current.filter((selected) => selected !== pendingTrackProgram.display_name));
    else setSelectedMajors((current) => current.filter((selected) => selected !== pendingTrackProgram.display_name));
  }

  function toggleSeason(season: string) {
    setPreferredSeasons((prev) =>
      prev.includes(season) ? prev.filter((s) => s !== season) : [...prev, season]
    );
  }

  async function handleSignOut() {
    safeRemoveStorage("ru_planner_token");
    safeRemoveStorage("ru_planner_email");
    try {
      await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" });
    } catch {}
    router.push("/");
  }

  async function handleSubmit(event: { preventDefault(): void }) {
    event.preventDefault();

    if (preferredSeasons.length === 0) {
      setStatus("Select at least one semester to enroll in.");
      return;
    }

    const minorMissingTrack = selectedMinors.find((minor) => {
      const program = minorPrograms.find((candidate) => candidate.display_name === minor);
      return hasTrackChoices(program) && !selectedMinorTracks[minor];
    });
    const majorMissingTrack = selectedMajors.find((major) => {
      const program = majorPrograms.find((candidate) => candidate.display_name === major);
      return hasTrackChoices(program) && !selectedMajorTracks[major];
    });
    const programMissingTrack = majorMissingTrack ?? minorMissingTrack;
    if (programMissingTrack) {
      setStatus(`Select a track for ${programMissingTrack.split("(")[0].trim()}.`);
      setWizardStep(1);
      return;
    }

    setStatus("Generating plan…");
    setSaveStatus("");
    const payload = {
      degree_level: degreeFilter,
      majors: selectedMajors.map((major) => {
        const track = selectedMajorTracks[major];
        const program = majorPrograms.find((candidate) => candidate.display_name === major);
        return track && program ? major.replace(program.major_name, `${program.major_name} — ${track}`) : major;
      }),
      minors: selectedMinors.map((m) => {
        const track = selectedMinorTracks[m];
        const prog = minorPrograms.find((p) => p.display_name === m);
        if (track && prog) {
          // "Statistics (Minor, SAS)" → "Statistics — Data Science (Minor, SAS)"
          return m.replace(prog.major_name, `${prog.major_name} — ${track}`);
        }
        return m;
      }),
      concentrations: [],
      completed_courses: [...new Set(completedCourses)],
      in_progress_courses: [...new Set(inProgressCourses)],
      start_term: startTerm.trim() || undefined,
      target_grad_term: targetGradTerm,
      max_credits_per_term: maxCredits,
      summer_max_credits: 12,
      winter_max_credits: 4,
      preferred_seasons: preferredSeasons,
    };

    let res: Response;
    try {
      const planEndpoint = isLocalPreview() ? "/dev/plan" : "/plan";
      res = await fetch(`${apiBase}${planEndpoint}`, {
        method: "POST",
        headers: { "content-type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(payload),
        credentials: "include",
      });
    } catch {
      setStatus("Error: Could not reach the local planner API. Make sure the backend is running on port 8000.");
      return;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown error" }));
      const detail = typeof err.detail === "string"
        ? err.detail
        : Array.isArray(err.detail)
        ? err.detail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join("; ")
        : "Failed to generate plan.";
      setStatus(`Error: ${detail}`);
      return;
    }

    const data = (await res.json()) as PlanResponse;
    editedTermsRef.current = data.terms;
    setEditedTerms(data.terms);
    setPlan(data);
    setPlanKey((k) => k + 1);
    setStatus("");
    setSidebarOpen(false);
  }

  async function handleSave() {
    if (!plan) return;

    setSaveStatus("Saving…");
    const name = `${selectedMajors[0] ?? "My"} — ${targetGradTerm}`;

    const plan_data = {
      ...plan,
      terms: editedTermsRef.current,
    };

    const res = await fetch(`${apiBase}/schedules`, {
      method: "POST",
      headers: { "content-type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ name, plan_data }),
      credentials: 'include',
    });

    if (res.status === 401) {
      safeRemoveStorage("ru_planner_token");
      safeRemoveStorage("ru_planner_email");
      router.push("/");
      return;
    }

    if (!res.ok) {
      setSaveStatus("Failed to save. Please try again.");
      return;
    }

    setSaveStatus("Schedule saved!");
  }

  const totalPlanCredits = editedTerms.reduce((sum, term) => sum + term.total_credits, 0);
  const livePrograms = useMemo(() => {
    if (!plan) return [];
    const completed = new Set(completedCourses.map((code) => code.trim().toUpperCase()));
    const inProgress = new Set(inProgressCourses.map((code) => code.trim().toUpperCase()));
    const planned = new Set(editedTerms.flatMap((term) => term.courses.map((course) => course.code.trim().toUpperCase())));
    return (plan.programs_summary ?? []).map((program) => evaluateProgram(program, completed, inProgress, planned));
  }, [plan, completedCourses, inProgressCourses, editedTerms]);
  const liveCoverage = useMemo(() => {
    const programTotals = livePrograms.reduce((sum, program) => {
      const result = programCoverage(program);
      return { covered: sum.covered + result.covered, total: sum.total + result.total, complete: sum.complete && result.complete };
    },
    { covered: 0, total: 0, complete: true });
    const coreBlocks = evaluateCoreBlocks(plan?.core_curriculum_blocks ?? [], editedTerms).filter((block) => block.total_courses != null);
    const coreCovered = coreBlocks.reduce((sum, block) => sum + Math.min(block.total_courses ?? 0, (block.total_courses ?? 0) - block.needed), 0);
    const coreTotal = coreBlocks.reduce((sum, block) => sum + (block.total_courses ?? 0), 0);
    return {
      covered: programTotals.covered + coreCovered,
      total: programTotals.total + coreTotal,
      complete: programTotals.complete && coreBlocks.every((block) => block.needed === 0),
    };
  }, [livePrograms, plan, editedTerms]);
  const coveragePercent = liveCoverage.total > 0 ? Math.round((liveCoverage.covered / liveCoverage.total) * 100) : 0;

  const wizardProps: WizardProps = {
    step: wizardStep,
    onStepChange: setWizardStep,
    degreeFilter,
    setDegreeFilter: (v) => { setDegreeFilter(v); setSelectedMajors([]); },
    majorPrograms,
    minorPrograms,
    selectedMajors,
    setSelectedMajors: (next) => {
      setSelectedMajors(next);
      setSelectedMajorTracks((previous) => Object.fromEntries(next.filter((major) => previous[major]).map((major) => [major, previous[major]])));
    },
    selectedMajorTracks,
    setSelectedMajorTracks,
    selectedMinors,
    setSelectedMinors: (next) => {
      setSelectedMinors(next);
      setSelectedMinorTracks((prev) => {
        const kept: Record<string, string> = {};
        for (const m of next) if (prev[m]) kept[m] = prev[m];
        return kept;
      });
    },
    selectedMinorTracks,
    setSelectedMinorTracks,
    startTerm,
    setStartTerm,
    targetGradTerm,
    setTargetGradTerm,
    maxCredits,
    setMaxCredits,
    preferredSeasons,
    toggleSeason,
    completedCourses,
    setCompletedCourses,
    setInProgressCourses,
    onSubmit: handleSubmit,
    status,
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      {pendingTrackProgram && <TrackSelectionModal program={pendingTrackProgram} onSelect={selectPendingTrack} onRemove={removePendingTrackProgram} />}
      {/* ── Topbar ── */}
      <header className="topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 4, marginRight: 28 }}>
          <img src="/RUPlanner Logo.svg" alt="RU Planner" style={{ height: 36, width: "auto" }} />
        </div>
        <nav className="topbar-nav">
          <span className="topbar-nav-item active">My Planner</span>
          <Link href="/schedules" className="topbar-nav-item" prefetch>Schedules</Link>
          <Link href="/sniper" className="topbar-nav-item" prefetch>Course Sniper</Link>
        </nav>
        <div className="topbar-right">
          {plan && (
            <button
              className="mobile-sidebar-btn"
              onClick={() => setSidebarOpen((v) => !v)}
              aria-label="Plan settings"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <line x1="2" y1="4" x2="14" y2="4"/>
                <line x1="2" y1="8" x2="14" y2="8"/>
                <line x1="2" y1="12" x2="14" y2="12"/>
                <circle cx="5" cy="4" r="1.5" fill="var(--surface-2)" stroke="currentColor"/>
                <circle cx="11" cy="8" r="1.5" fill="var(--surface-2)" stroke="currentColor"/>
                <circle cx="7" cy="12" r="1.5" fill="var(--surface-2)" stroke="currentColor"/>
              </svg>
            </button>
          )}
          <UserMenu email={userEmail} onSignOut={handleSignOut} />
        </div>
      </header>

      {!plan ? (
        /* ── Full-page wizard ── */
        <FullPageWizard {...wizardProps} />
      ) : (
        /* ── App shell with plan ── */
        <>
          <div
            className={`mobile-sidebar-overlay${sidebarOpen ? " visible" : ""}`}
            onClick={() => setSidebarOpen(false)}
          />
          <div className="app-shell">
            {/* Sidebar: plan summary + actions */}
            <aside className={`sidebar${sidebarOpen ? " mobile-open" : ""}`}>
              <div className="sidebar-body">
                {/* Plan summary */}
                <div style={{ marginBottom: 20 }}>
                  <div style={{ fontSize: 11, color: "var(--text-3)", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 10 }}>Current plan</div>
                  {[
                    { label: "Degree", value: degreeFilter === "master" ? "Master's" : "Bachelor's" },
                    { label: "Major", value: selectedMajors[0]?.split("(")[0].trim() ?? "—" },
                    { label: "Graduation", value: targetGradTerm || "—" },
                    { label: "Start", value: startTerm || "—" },
                    { label: "Completed", value: completedCourses.length > 0 ? `${completedCourses.length} courses` : "None" },
                  ].map((row) => (
                    <div key={row.label} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", borderBottom: "1px solid var(--border)" }}>
                      <span style={{ fontSize: 12, color: "var(--text-3)" }}>{row.label}</span>
                      <span style={{ fontSize: 12, color: "var(--text)", fontWeight: 600, textAlign: "right", maxWidth: "60%" }}>{row.value}</span>
                    </div>
                  ))}
                </div>

                {/* Actions */}
                <button
                  type="button"
                  onClick={() => { setPlan(null); setWizardStep(0); setStatus(""); }}
                  style={{
                    width: "100%", padding: "11px 14px", borderRadius: 10, marginBottom: 8,
                    border: "none", background: "var(--ru-red)",
                    color: "#fff", fontSize: 13, fontWeight: 700,
                    cursor: "pointer", fontFamily: "inherit",
                  }}
                >
                  Build new plan
                </button>
                <button
                  type="button"
                  onClick={() => { setPlan(null); setWizardStep(4); setStatus(""); }}
                  style={{
                    width: "100%", padding: "10px 14px", borderRadius: 10,
                    border: "1px solid var(--border-2)", background: "var(--surface-2)",
                    color: "var(--text-2)", fontSize: 13, fontWeight: 600,
                    cursor: "pointer", fontFamily: "inherit",
                  }}
                >
                  Edit settings
                </button>
              </div>
            </aside>

            {/* Main panel */}
            <div className="main-panel">
              <div className="main-content">
                {/* Stats bar */}
                <div className="stats-bar">
                  <div className="stats-bar-item" style={{ paddingLeft: 4 }}>
                    <span className="stats-bar-number">{totalPlanCredits}</span>
                    <span className="stats-bar-label">total credits</span>
                  </div>
                  <div className="stats-bar-item">
                    <span className="stats-bar-number">{editedTerms.length}</span>
                    <span className="stats-bar-label">semesters</span>
                  </div>
                  <div className="stats-bar-progress">
                    <div className="stats-bar-progress-labels">
                      <span className="stats-bar-progress-title">Degree progress</span>
                      <span className="stats-bar-progress-value">
                        {liveCoverage.covered} / {liveCoverage.total} requirements ({coveragePercent}%)
                      </span>
                    </div>
                    <div className="stats-bar-progress-track">
                      <div
                        className="stats-bar-progress-fill"
                        style={{ width: `${coveragePercent}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Planner title */}
                <div className="planner-header">
                  <div className="planner-title">
                    {selectedMajors[0] ?? "My Plan"}
                    {plan.completion_term && (
                      <span className="planner-title-grad">— {plan.completion_term}</span>
                    )}
                  </div>
                  <div className="planner-subtitle">
                    {editedTerms.length} semesters · {totalPlanCredits} total credits · {liveCoverage.complete ? "all tracked requirements covered" : "requirements still missing"}
                  </div>
                </div>

                {plan.terms.length === 0 && plan.remaining_courses.length === 0 && (
                  <div className="plan-warning" style={{ marginBottom: 12 }}>
                    <strong>No course data available.</strong> This program hasn&apos;t been published yet.
                  </div>
                )}
                {!liveCoverage.complete && liveCoverage.total > 0 && (
                  <div className="plan-warning danger" style={{ marginBottom: 12 }}>
                    <strong>This edited plan does not yet cover every tracked program requirement.</strong>
                  </div>
                )}
                {livePrograms.map((prog, i) => (
                  <ProgramRequirementsPanel key={i} prog={prog} />
                ))}

                {plan.core_curriculum_blocks?.length > 0 && (
                  <CoreCurriculumPanel
                    name={plan.core_curriculum_name ?? "Core Curriculum"}
                    blocks={plan.core_curriculum_blocks}
                    terms={editedTerms}
                  />
                )}

                <PlanEditor
                  key={planKey}
                  initialTerms={plan.terms}
                  completedCourses={completedCourses}
                  onTermsChange={handleTermsChange}
                />

                <div className="save-bar">
                  <button className="save-button" onClick={handleSave}>
                    Save schedule
                  </button>
                  {saveStatus && (
                    <span className={saveStatus === "Schedule saved!" ? "save-success" : "save-hint"}>
                      {saveStatus}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
