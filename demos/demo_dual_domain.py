"""Dual-domain program-exit demo for Primer."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from capillary_actions_sdk.events import AGUIEvent
from demo_education import run_memory_roundtrip

from primer_core.eval.cases import EngagementEvalCase
from primer_core.eval.harness import format_report, run_eval_suite
from primer_core.eval.metrics import find_eval_case

DOMAINS = ["education", "coop-finance"]
REPO_ROOT = Path(__file__).resolve().parent.parent


async def run_streaming_leg(
    domain: str,
    case: EngagementEvalCase,
) -> bool:
    """Run one domain through the shared AG-UI streaming surface."""
    events = [
        event
        async for event in case.orchestrator.run_engagement_streaming(
            skill_name=case.skill_name,
            subject_id=case.subject_id,
            thread_id=case.thread_id,
            input_data=case.input_data,
        )
    ]

    passed = bool(events) and all(isinstance(event, AGUIEvent) for event in events)

    print(f"\n[{domain}] Streaming engagement")
    print("-" * 72)

    for event in events:
        print(f"  {event.event_type.value}")

    print(f"[{domain}] typed AG-UI stream: {'PASS' if passed else 'FAIL'}")

    return passed


async def run_domain_leg(domain: str) -> bool:
    """Run streaming and memory demonstrations for one DomainPack."""
    print("\n" + "=" * 88)
    print(f"DOMAIN: {domain}")
    print("=" * 88)

    case = find_eval_case(domain)

    print(f"Engine: {type(case.orchestrator).__module__}.{type(case.orchestrator).__name__}")
    print(f"Skill: {case.skill_name}")

    streaming_passed = await run_streaming_leg(domain, case)

    memory_passed = await run_memory_roundtrip(
        domain=domain,
        case=case,
    )

    passed = streaming_passed and memory_passed

    print(f"\n[{domain}] domain leg: {'PASS' if passed else 'FAIL'}")

    return passed


def run_pytest_gate() -> bool:
    """Run the packaged eval tests with a bounded subprocess timeout."""
    print("\n" + "=" * 88)
    print("PYTEST EVAL GATE")
    print("=" * 88)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/eval",
                "-q",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("pytest eval gate exceeded 120 seconds --> FAIL")
        return False

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr)

    passed = result.returncode == 0

    print(f"pytest eval gate: {'PASS' if passed else 'FAIL'}")

    return passed


async def run_demo() -> int:
    """Run the complete dual-domain program-exit demonstration."""
    print("=" * 88)
    print("PRIMER DUAL-DOMAIN EXIT DEMO")
    print("=" * 88)

    domain_results = [await run_domain_leg(domain) for domain in DOMAINS]

    print("\n" + "=" * 88)
    print("SWAP PARITY + TRANSITION METRICS")
    print("=" * 88)

    eval_report = await run_eval_suite(DOMAINS)
    print(format_report(eval_report))

    pytest_passed = run_pytest_gate()

    passed = all(domain_results) and eval_report.passed and pytest_passed

    print("\n" + "=" * 88)
    print(f"PROGRAM EXIT GATE: {'PASS' if passed else 'FAIL'}")
    print("=" * 88)

    return 0 if passed else 1


def main() -> int:
    return asyncio.run(run_demo())


if __name__ == "__main__":
    raise SystemExit(main())
