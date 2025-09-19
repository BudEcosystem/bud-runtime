"""ClickHouse migration management CLI."""

import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from budeval.commons.logging import logging
from budeval.evals.storage.clickhouse import ClickHouseStorage


logger = logging.getLogger(__name__)
console = Console()


@click.group()
def cli():
    """ClickHouse migration management commands."""
    pass


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
async def status(dry_run: bool):
    """Show migration status."""
    storage = ClickHouseStorage()

    try:
        await storage.initialize()

        # Get applied migrations
        applied = await storage._get_applied_migrations()

        # Get all migration files
        migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))

        # Create status table
        table = Table(title="Migration Status")
        table.add_column("Migration", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Checksum", style="yellow")

        for migration_file in migration_files:
            migration_name = migration_file.stem

            # Calculate checksum
            with open(migration_file, "rb") as f:
                checksum = hashlib.sha256(f.read()).hexdigest()[:8] + "..."

            if migration_name in applied:
                status_text = "✓ Applied"
                style = "green"
            else:
                status_text = "⨯ Pending"
                style = "yellow"

            table.add_row(migration_name, f"[{style}]{status_text}[/{style}]", checksum)

        console.print(table)
        console.print(f"\nTotal: {len(migration_files)} migrations")
        console.print(f"Applied: {len(applied)} migrations")
        console.print(f"Pending: {len(migration_files) - len(applied)} migrations")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        await storage.close()


@cli.command()
@click.option("--force", is_flag=True, help="Force run even if already applied")
@click.option("--migration", help="Run specific migration by name")
async def up(force: bool, migration: Optional[str]):
    """Apply pending migrations."""
    storage = ClickHouseStorage()

    try:
        await storage.initialize()

        if migration:
            # Run specific migration
            migrations_dir = Path(__file__).parent.parent.parent / "migrations"
            migration_file = migrations_dir / f"{migration}.sql"

            if not migration_file.exists():
                console.print(f"[red]Migration {migration} not found[/red]")
                sys.exit(1)

            applied = await storage._get_applied_migrations()

            if migration in applied and not force:
                console.print(f"[yellow]Migration {migration} already applied. Use --force to rerun.[/yellow]")
                return

            console.print(f"[cyan]Applying migration: {migration}[/cyan]")
            checksum = storage._calculate_checksum(migration_file)
            success = await storage._apply_migration(migration_file, migration, checksum)

            if success:
                console.print(f"[green]✓ Migration {migration} applied successfully[/green]")
            else:
                console.print(f"[red]✗ Migration {migration} failed[/red]")
                sys.exit(1)
        else:
            # Run all pending migrations
            console.print("[cyan]Running pending migrations...[/cyan]")
            await storage._run_migrations()
            console.print("[green]✓ All migrations applied successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        await storage.close()


@cli.command()
async def validate():
    """Validate migration checksums."""
    storage = ClickHouseStorage()

    try:
        await storage.initialize()

        # Get migration records with checksums
        async with storage.get_connection() as conn, conn.cursor() as cursor:
            query = """
            SELECT version, checksum
            FROM budeval.schema_migrations
            WHERE success = 1
            ORDER BY version
            """
            await cursor.execute(query)
            rows = await cursor.fetchall()

        migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        errors = []

        table = Table(title="Migration Checksum Validation")
        table.add_column("Migration", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details")

        for version, stored_checksum in rows:
            migration_file = migrations_dir / f"{version}.sql"

            if not migration_file.exists():
                table.add_row(version, "[red]✗ Missing[/red]", "Migration file not found")
                errors.append(f"{version}: file not found")
                continue

            current_checksum = storage._calculate_checksum(migration_file)

            if stored_checksum == "bootstrap":
                # Skip bootstrap entry
                table.add_row(
                    version,
                    "[cyan]⊘ Bootstrap[/cyan]",
                    "Initial tracking record",
                )
            elif current_checksum == stored_checksum:
                table.add_row(
                    version,
                    "[green]✓ Valid[/green]",
                    f"Checksum: {current_checksum[:8]}...",
                )
            else:
                table.add_row(
                    version,
                    "[red]✗ Modified[/red]",
                    f"Expected: {stored_checksum[:8]}..., Got: {current_checksum[:8]}...",
                )
                errors.append(f"{version}: checksum mismatch")

        console.print(table)

        if errors:
            console.print(f"\n[red]Validation failed with {len(errors)} error(s):[/red]")
            for error in errors:
                console.print(f"  - {error}")
            sys.exit(1)
        else:
            console.print("\n[green]✓ All migrations validated successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        await storage.close()


@cli.command()
@click.confirmation_option(prompt="This will reset all migration tracking. Are you sure?")
async def reset():
    """Reset migration tracking (development only)."""
    storage = ClickHouseStorage()

    try:
        await storage.initialize()

        console.print("[yellow]Resetting migration tracking...[/yellow]")

        async with storage.get_connection() as conn, conn.cursor() as cursor:
            # Clear migration tracking table
            await cursor.execute("TRUNCATE TABLE budeval.schema_migrations")

        console.print("[green]✓ Migration tracking reset successfully[/green]")
        console.print("[cyan]Run 'migrate up' to reapply all migrations[/cyan]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        await storage.close()


def main():
    """Run the CLI main entry point."""
    # Handle async commands
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command in ["status", "up", "validate", "reset"]:
            # Get the command function
            cmd_func = cli.commands[command].callback
            # Run it in an event loop
            asyncio.run(cmd_func(*sys.argv[2:]))
            return

    # Otherwise run normally
    cli()


if __name__ == "__main__":
    main()
