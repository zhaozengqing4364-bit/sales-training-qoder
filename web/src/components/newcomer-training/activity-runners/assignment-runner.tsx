import type { ActivityRunnerProps } from "./types";
import { AudioAssessmentRunner } from "./audio-assessment-runner";

export function AssignmentRunner(props: ActivityRunnerProps) {
    return <AudioAssessmentRunner {...props} />;
}
