"""CLI entry point for GovSim Autonomous.

Usage:
    python -m simulation.main [--config path/to/config.yaml] [--seed 42] [--stub]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from simulation.config import load_config, load_config_from_yaml
from simulation.engine import Engine
from simulation.llm_interface import StubLLM, RecordingLLM
from simulation.llm_client import DeepSeekLLM


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="GovSim Autonomous — LLM-driven agent simulation"
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to YAML config file (default: config/default.yaml)",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="Use StubLLM instead of DeepSeek (for testing)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output JSON path (default: outputs/<run_id>.json)",
    )
    parser.add_argument(
        "--run-id", "-r",
        default=None,
        help="Run identifier",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print config and exit without running",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-turn progress during simulation",
    )
    parser.add_argument(
        "--record-prompts",
        action="store_true",
        help="Record full prompt text and raw LLM responses in output",
    )
    return parser


def main():
    parser = _build_arg_parser()
    args = parser.parse_args()

    # Load config
    if args.config:
        config = load_config_from_yaml(args.config)
    else:
        default_yaml = Path(__file__).parent.parent / "config" / "default.yaml"
        if default_yaml.exists():
            config = load_config_from_yaml(str(default_yaml))
        else:
            config = load_config({})  # Use all defaults

    if args.dry_run:
        import json
        print(json.dumps(config, indent=2))
        return

    # Build LLM
    if args.stub:
        print("[main] Using StubLLM (deterministic)")
        llm = StubLLM()
    else:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            print(
                "Error: DEEPSEEK_API_KEY not set. "
                "Use --stub to run with StubLLM.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"[main] Using DeepSeekLLM (model={config['llm']['model']})")
        llm = DeepSeekLLM(
            api_key=api_key,
            model=config["llm"]["model"],
            temperature=config["llm"]["temperature"],
            max_tokens=config["llm"]["max_tokens"],
        )

    # Wrap in RecordingLLM if --record-prompts
    if args.record_prompts:
        recording_llm = RecordingLLM(llm)
        llm = recording_llm
        print("[main] Prompt recording enabled")

    # Run simulation
    engine = Engine(config, llm=llm, seed=args.seed, run_id=args.run_id, verbose=args.verbose)
    print(f"[main] Running simulation ({config['simulation']['num_rounds']} rounds, "
          f"{len(config['agents']['names'])} agents)...")
    engine.run()

    # Save output (compute path first so debug prompts can reference it)
    output_path = args.output
    if not output_path:
        run_id = engine.recorder.run_id
        output_dir = Path(__file__).parent.parent / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / f"{run_id}.json")

    # Save recorded prompts to separate debug file (not in main output)
    if args.record_prompts:
        recording = getattr(engine.llm, "history", None)
        if recording:
            def _to_serializable(obj):
                if obj is None:
                    return None
                if isinstance(obj, (int, float, str, bool)):
                    return obj
                if isinstance(obj, (list, tuple)):
                    return [_to_serializable(v) for v in obj]
                if isinstance(obj, set):
                    return [_to_serializable(v) for v in obj]
                if isinstance(obj, dict):
                    return {k: _to_serializable(v) for k, v in obj.items()}
                if hasattr(obj, "__dict__"):
                    return {k: _to_serializable(v) for k, v in obj.__dict__.items()
                            if not k.startswith("_")}
                return str(obj)

            prompt_log = []
            for entry in recording:
                prompt_log.append({
                    "prompt": _to_serializable(entry["prompt"]),
                    "response": _to_serializable(entry["response"]),
                })
            debug_path = output_path.replace(".json", "_prompts.json")
            import json
            with open(debug_path, "w", encoding="utf-8") as f:
                json.dump(prompt_log, f, indent=2, ensure_ascii=False)
            print(f"[main] Prompt debug log saved to: {debug_path}")

    engine.save_output(output_path)
    print(f"[main] Output saved to: {output_path}")

    # Print summary
    output = engine.get_output()
    last_metrics = output["metrics"]["by_round"][-1] if output["metrics"]["by_round"] else {}
    print(f"[main] Done. Final round metrics: "
          f"harvest={last_metrics.get('total_harvest', 0):.1f}, "
          f"pool={last_metrics.get('pool_remaining', 0):.1f}, "
          f"gini={last_metrics.get('gini_coefficient', 0):.3f}"
    )

    if not args.stub and isinstance(llm, DeepSeekLLM):
        s = llm.stats()
        print(f"[main] LLM stats: {s['calls']} calls, "
              f"{s['total_tokens']} tokens, "
              f"{s['total_time_ms'] / 1000:.1f}s total")


if __name__ == "__main__":
    main()
