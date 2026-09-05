"""Board of Directors entrypoint.

Application code now lives under app/, agents/, models/, tools/, utils/ and
reports/. This module intentionally remains as the stable public entrypoint so
existing commands and imports such as `import main` keep working.
"""

from app.api import app
from app.pipeline import initialize_state, node_output, run_board_meeting, run_formal_board, run_full_pipeline, run_panel

__all__ = [
    "app", "initialize_state", "node_output", "run_board_meeting",
    "run_formal_board", "run_full_pipeline", "run_panel",
]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        demo_brief = {
            "idea": "AI sales assistant for Nigerian SMEs that turns WhatsApp inquiries into qualified customers",
            "target_market": "Nigerian small and medium businesses selling through WhatsApp",
            "budget": "$10000",
            "founder_background": "Technical founder building AI products",
            "timeline": "MVP in 12 weeks",
            "constraints": "Bootstrapped; reach first revenue within 6 months",
        }
        result = run_board_meeting(demo_brief)
        print(result["final_report"])
        if result["errors"]:
            print("\nRuntime errors:")
            for error in result["errors"]:
                print(f"- {error['stage']}: {error['message']}")
