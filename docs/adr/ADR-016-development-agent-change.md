# ADR-016: Change of development agent to Claude Code
Status: Accepted
Date: 2026-11-24

## Context
IBM Bob's budget ran out on 2026-11-23 with BOB-P3-01 code and tests complete (705 passing) and docs pending.
The schedule requires continuing.

## Options
A. Wait for Bob's budget to reset or be topped up.
B. Mixed: Bob for AI-integration phases (P5–P7), another agent for the rest.
C. Claude Code (VS Code) as the development agent from P3-01 closure onward.

## Decision
C. Claude Code executes the architect's prompts from P3-01 closure onward, with the same prompt format, gates and
review process. A repo CLAUDE.md holds the standing rules. If Bob's budget returns, Bob is preferred for P5–P7.

## Consequences
+ Schedule continues; process and quality gates unchanged.
- Less IBM Bob evidence for competency 4. Mitigation: Bob's P0–P3-01 work (8 prompts, corrective cycles, reports)
  stays as evidence, and the evidence register states honestly which agent built each phase.

## Affected artifacts
CLAUDE.md; docs/bob/PROMPT_REGISTER.md (Notes column); docs/evidence/EVIDENCE_REGISTER.md; commit trailers.
