export interface DebateArgument {
  position: "bull" | "bear";
  round_number: number;
  argument: string;
  key_points: string[];
  rebuttal_to_previous: string | null;
}

export interface DebateRound {
  round_number: number;
  bull_argument: DebateArgument;
  bear_argument: DebateArgument;
}

export interface DebateResult {
  ticker: string;
  rounds: DebateRound[];
  bull_case_summary: string;
  bear_case_summary: string;
  key_points_of_agreement: string[];
  key_points_of_disagreement: string[];
  unresolved_uncertainties: string[];
}
