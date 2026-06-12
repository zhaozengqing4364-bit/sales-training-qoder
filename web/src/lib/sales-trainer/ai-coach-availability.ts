import type { SalesTrainerPath, SalesTrainerPathLevel } from "@/lib/api/types";

const BUSINESS_SKILLS_MODULE_KEY = "business_skills";

function isBusinessSkillsLevel(level: SalesTrainerPathLevel): boolean {
    return level.module_key === BUSINESS_SKILLS_MODULE_KEY
        || (level.ai_coach_availability !== null && level.ai_coach_availability !== undefined);
}

function coachHrefFromLevel(level: SalesTrainerPathLevel): string | null {
    const availability = level.ai_coach_availability;
    return availability?.available && availability.coach_path
        ? availability.coach_path
        : null;
}

export function findBusinessSkillsCoachHref(
    paths: readonly SalesTrainerPath[],
    unitId?: string | null,
): string | null {
    for (const path of paths) {
        for (const level of path.levels) {
            if (unitId && level.unit_id !== unitId) {
                continue;
            }
            if (!isBusinessSkillsLevel(level)) {
                continue;
            }
            const coachHref = coachHrefFromLevel(level);
            if (coachHref) {
                return coachHref;
            }
        }
    }
    return null;
}
