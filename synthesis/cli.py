import os
import sys
import anthropic
import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from dotenv import load_dotenv

from synthesis.retrieval import search_arxiv, search_openalex, search_nber, deduplicate
from synthesis.extraction import extract_claims, extract_effect_sizes
from synthesis.data import FredClient, fetch_worldbank
from synthesis.alignment import score_alignment, pool_evidence
from synthesis.alignment.qqa import build_gap_matrix
from synthesis.report import generate_report, build_html

load_dotenv()

app = typer.Typer(help="Synthesis — AI economics research tool combining qualitative and quantitative analysis.")
console = Console()


@app.command()
def research(
    question: str = typer.Argument(..., help="Your economics research question"),
    output_dir: str = typer.Option("./synthesis_output", "--output", "-o", help="Output directory"),
    max_papers: int = typer.Option(24, "--papers", "-p", help="Max papers to retrieve"),
    no_fred: bool = typer.Option(False, "--no-fred", help="Skip FRED data (if no API key)"),
    no_worldbank: bool = typer.Option(False, "--no-worldbank", help="Skip World Bank data"),
):
    """
    Run a full Synthesis research analysis on any economics question.

    Example:
        synthesis "Does raising the minimum wage increase unemployment?"
    """
    console.print(Panel.fit(
        f"[bold blue]Synthesis[/bold blue] · Economics Research Brief\n"
        f"[dim]Qualitative + Quantitative + QQA Alignment[/dim]",
        border_style="blue"
    ))
    console.print(f"\n[bold]Question:[/bold] {question}\n")

    # Check API keys
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY not set.")
        console.print("Run: [bold]export ANTHROPIC_API_KEY='sk-ant-...'[/bold]")
        raise typer.Exit(1)

    client = anthropic.Anthropic()
    fred_client = None

    if not no_fred:
        fred_key = os.environ.get("FRED_API_KEY")
        if fred_key:
            fred_client = FredClient(api_key=fred_key)
        else:
            console.print("[yellow]⚠ FRED_API_KEY not set — skipping FRED data.[/yellow]")
            console.print("  Get a free key at [link]https://fred.stlouisfed.org/docs/api/api_key.html[/link]")
            console.print("  Then: [bold]export FRED_API_KEY='your-key'[/bold]\n")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Retrieve papers ───────────────────────────────────────────────
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as prog:
        task = prog.add_task("Searching arXiv economics papers...", total=None)
        arxiv_papers = search_arxiv(question, max_results=max_papers // 3)
        prog.update(task, description=f"arXiv: {len(arxiv_papers)} papers found")

        prog.update(task, description="Searching OpenAlex...")
        oa_papers = search_openalex(question, max_results=max_papers // 3)
        prog.update(task, description=f"OpenAlex: {len(oa_papers)} papers found")

        prog.update(task, description="Searching NBER working papers...")
        nber_papers = search_nber(question, max_results=max_papers // 3)
        prog.update(task, description=f"NBER: {len(nber_papers)} papers found")

    raw_papers = arxiv_papers + oa_papers + nber_papers
    all_papers = deduplicate(raw_papers)
    dupes = len(raw_papers) - len(all_papers)
    console.print(
        f"[green]✓[/green] {len(all_papers)} papers retrieved "
        f"(arXiv: {len(arxiv_papers)}, OpenAlex: {len(oa_papers)}, NBER: {len(nber_papers)}"
        + (f", [dim]{dupes} duplicates removed[/dim])" if dupes else ")")
    )

    if not all_papers:
        console.print("[red]No papers found. Try rephrasing your question.[/red]")
        raise typer.Exit(1)

    # ── Step 2: Extract claims ────────────────────────────────────────────────
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as prog:
        prog.add_task("Extracting structured claims from literature...", total=None)
        claims = extract_claims(all_papers, question, client)

    console.print(f"[green]✓[/green] {len(claims)} empirical claims extracted")

    # ── Step 2b: Extract numerical effect sizes ───────────────────────────────
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console) as prog:
        prog.add_task("Extracting numerical effect sizes from abstracts...", total=None)
        effect_sizes = extract_effect_sizes(all_papers, question, client)

    if effect_sizes:
        console.print(f"[green]✓[/green] {len(effect_sizes)} numerical effect sizes extracted")
    else:
        console.print("[dim]  No explicit numerical effect sizes found in abstracts[/dim]")

    # ── Step 3: Pull FRED data ────────────────────────────────────────────────
    fred_series = []
    if fred_client:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console) as prog:
            prog.add_task("Pulling FRED empirical data...", total=None)
            try:
                fred_series = fred_client.fetch_relevant(question, client, max_series=4)
            except Exception as e:
                console.print(f"[yellow]FRED warning:[/yellow] {e}")

        console.print(f"[green]✓[/green] {len(fred_series)} FRED series retrieved")

    # ── Step 4: Pull World Bank data ──────────────────────────────────────────
    wb_series = []
    if not no_worldbank:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console) as prog:
            prog.add_task("Pulling World Bank cross-country data...", total=None)
            try:
                wb_series = fetch_worldbank(question, client, max_indicators=2)
            except Exception as e:
                console.print(f"[yellow]World Bank warning:[/yellow] {e}")

        console.print(f"[green]✓[/green] {len(wb_series)} World Bank series retrieved")

    data_series = fred_series + wb_series

    # ── Step 5: QQA Alignment ─────────────────────────────────────────────────
    alignment = []
    if claims and data_series:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                      console=console) as prog:
            prog.add_task("Running QQA alignment scoring...", total=None)
            alignment = score_alignment(claims, data_series, client)
        console.print(f"[green]✓[/green] QQA alignment complete")
    elif claims:
        from synthesis.alignment.qqa import AlignmentResult
        alignment = [
            AlignmentResult(claim=c, support_level="insufficient_data",
                            support_score=None, data_series_used=[],
                            explanation="No empirical data available for alignment.")
            for c in claims
        ]

    # ── Step 5b: Meta-analytic pooling ───────────────────────────────────────
    pooled = pool_evidence(claims)
    console.print(
        f"[green]✓[/green] Pooled evidence: [bold]{pooled.pooled_direction.upper()}[/bold] "
        f"(score {pooled.weighted_score:+.2f}, {pooled.n_claims} claims)"
    )

    # ── Step 6: Generate report ───────────────────────────────────────────────
    console.print("\n[bold blue]Generating Synthesis Report...[/bold blue]\n")
    console.print("─" * 70)

    report_text = generate_report(question, claims, alignment, data_series, pooled, client)

    console.print("\n" + "─" * 70)

    # ── Step 7: Save outputs ──────────────────────────────────────────────────
    safe_name = "".join(c if c.isalnum() or c in " -" else "_" for c in question[:50]).strip()
    safe_name = safe_name.replace(" ", "_").lower()

    md_path = out_path / f"{safe_name}.md"
    html_path = out_path / f"{safe_name}.html"

    with open(md_path, "w") as f:
        header = f"# Synthesis Research Brief\n\n**Question:** {question}\n\n---\n\n"
        f.write(header + report_text)

    html_content = build_html(
        question, report_text, alignment, data_series, len(all_papers),
        fred_count=len(fred_series), wb_count=len(wb_series), pooled=pooled,
        effect_sizes=effect_sizes,
    )
    with open(html_path, "w") as f:
        f.write(html_content)

    console.print(f"\n[green]✓[/green] Markdown → [bold]{md_path}[/bold]")
    console.print(f"[green]✓[/green] HTML report → [bold]{html_path}[/bold]")

    # ── Summary stats ─────────────────────────────────────────────────────────
    gap_matrix = build_gap_matrix([r.claim for r in alignment])
    supported = sum(1 for r in alignment if r.support_score and r.support_score > 0)
    contested = len(gap_matrix.get("contested_claims", []))

    console.print(Panel(
        f"[bold]Papers:[/bold] {len(all_papers)}  "
        f"[bold]Claims:[/bold] {len(claims)}  "
        f"[bold green]Supported:[/bold green] {supported}  "
        f"[bold yellow]Contested:[/bold yellow] {contested}  "
        f"[bold]Gaps:[/bold] {len(gap_matrix.get('unstudied_combinations', []))}",
        title="[bold blue]Research Summary[/bold blue]",
        border_style="blue"
    ))

    import subprocess
    subprocess.Popen(["open", str(html_path)])


def main():
    app()


if __name__ == "__main__":
    main()
