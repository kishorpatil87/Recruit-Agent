"""
Recruitment Agent — Entry point.
"""
from __future__ import annotations

import sys
import uvicorn
from config.settings import get_settings


def main():
    import argparse
    settings = get_settings()

    parser = argparse.ArgumentParser(
        prog="recruitment-agent",
        description="AI Recruitment Agent — Ollama + LangGraph (100% local)",
    )
    parser.add_argument("--host", default=settings.api_host)
    parser.add_argument("--port", type=int, default=settings.api_port)
    parser.add_argument("--reload", action="store_true", help="Dev mode auto-reload")
    args = parser.parse_args()

    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console()
        console.print(Panel.fit(
            f"[bold purple]🎯 RecruitAI — AI Recruitment Agent[/bold purple]\n"
            f"[dim]Ollama Local — {settings.ollama_model}[/dim]\n\n"
            f"[bold]Web UI:[/bold]   [cyan]http://localhost:{args.port}[/cyan]\n"
            f"[bold]API Docs:[/bold]  [cyan]http://localhost:{args.port}/api/docs[/cyan]\n\n"
            + (
                f"[bold green]✓ Ollama connected ({settings.ollama_model})[/bold green]"
                if settings.has_llm else
                "[bold red]⚠  Ollama not reachable![/bold red]\n"
                "[dim]1. Install Ollama: https://ollama.com/download\n"
                f"2. Pull model: ollama pull {settings.ollama_model}\n"
                "3. Start server: ollama serve[/dim]"
            ),
            border_style="purple",
        ))
    except ImportError:
        print(f"\n🎯 RecruitAI starting at http://localhost:{args.port}\n")

    uvicorn.run(
        "api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
