"""TRUST Protocol CLI.

Usage:
    trust-protocol serve          # Start the API server
    trust-protocol keygen         # Generate Ed25519 keypair
    trust-protocol status         # Check server health
    trust-protocol agent register # Register a new agent
    trust-protocol agent list     # List agents
    trust-protocol cred store     # Store a credential
    trust-protocol cred list      # List credentials
    trust-protocol pub register   # Register a publisher
    trust-protocol skill sign     # Sign a skill manifest
    trust-protocol skill verify   # Verify a signed manifest
    trust-protocol emergency      # Emergency controls
"""

import base64
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(name="trust-protocol", help="TRUST Protocol - Credential broker for AI agents")


# --- Serve ---

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(9500, help="Bind port"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
):
    """Start the TRUST Protocol API server."""
    import uvicorn
    console.print(f"[bold green]Starting TRUST Protocol server on {host}:{port}[/bold green]")
    uvicorn.run(
        "trust_protocol.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


# --- Status ---

@app.command()
def status(
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
):
    """Check server health."""
    import httpx
    try:
        r = httpx.get(f"{url}/v1/health", timeout=5)
        data = r.json()
        console.print(f"[bold green]Status:[/bold green] {data['status']}")
        console.print(f"Version: {data['version']}")
        console.print(f"Uptime: {data['uptime_seconds']:.0f}s")
    except Exception as e:
        console.print(f"[bold red]Server unreachable:[/bold red] {e}")
        raise typer.Exit(1)


# --- Keygen ---

@app.command()
def keygen(
    output_dir: Path = typer.Option(".", help="Directory to write key files"),
    name: str = typer.Option("publisher", help="Key name prefix"),
):
    """Generate an Ed25519 keypair for skill signing."""
    from trust_protocol.core.skill_signer import generate_keypair

    private_pem, public_pem = generate_keypair()

    priv_path = output_dir / f"{name}.key"
    pub_path = output_dir / f"{name}.pub"

    priv_path.write_bytes(private_pem)
    priv_path.chmod(0o600)
    pub_path.write_bytes(public_pem)

    console.print(f"[bold green]Keypair generated:[/bold green]")
    console.print(f"  Private key: {priv_path}")
    console.print(f"  Public key:  {pub_path}")
    console.print(f"[dim]Private key is chmod 600. Keep it secret.[/dim]")


# --- Agent commands ---

agent_app = typer.Typer(help="Agent management")
app.add_typer(agent_app, name="agent")


@agent_app.command("register")
def agent_register(
    name: str = typer.Argument(..., help="Agent name"),
    agent_type: str = typer.Option("executor", help="Agent type"),
    description: str = typer.Option("", help="Description"),
    credentials: Optional[str] = typer.Option(None, help="Comma-separated credential names"),
    capabilities: Optional[str] = typer.Option(None, help="Comma-separated capabilities"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Register a new agent."""
    from trust_protocol.sdk import TrustProtocolClient

    creds = [c.strip() for c in credentials.split(",")] if credentials else []
    caps = [c.strip() for c in capabilities.split(",")] if capabilities else []

    with TrustProtocolClient(url, admin_key=admin_key) as client:
        result = client.register_agent(
            name=name, agent_type=agent_type, description=description,
            required_credentials=creds, capabilities=caps,
        )

    console.print(f"[bold green]Agent registered:[/bold green]")
    console.print(f"  Agent ID:   {result['agent_id']}")
    console.print(f"  Trust Tier: {result['trust_tier']}")
    console.print(f"  API Key:    {result['api_key']}")
    console.print(f"[bold yellow]Save the API key! It cannot be recovered.[/bold yellow]")


@agent_app.command("list")
def agent_list(
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """List all registered agents."""
    from trust_protocol.sdk import TrustProtocolClient

    with TrustProtocolClient(url, admin_key=admin_key) as client:
        agents = client.list_agents()

    table = Table(title="Registered Agents")
    table.add_column("Agent ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Tier", style="green")
    table.add_column("Status")

    for a in agents:
        table.add_row(a["agent_id"], a["name"], a["agent_type"], a["trust_tier"], a["status"])

    console.print(table)


# --- Credential commands ---

cred_app = typer.Typer(help="Credential management")
app.add_typer(cred_app, name="cred")


@cred_app.command("store")
def cred_store(
    name: str = typer.Argument(..., help="Credential name"),
    value: str = typer.Option(..., help="Credential value (or JSON object)"),
    minimum_trust: str = typer.Option("COMPANION", help="Minimum trust tier"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Store a credential in the vault."""
    from trust_protocol.sdk import TrustProtocolClient

    # Try to parse as JSON, fallback to simple value
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        data = {"value": value}

    with TrustProtocolClient(url, admin_key=admin_key) as client:
        result = client.store_credential(name, data, minimum_trust)

    console.print(f"[bold green]Credential stored:[/bold green] {result['name']} (min trust: {result['minimum_trust']})")


@cred_app.command("list")
def cred_list(
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """List stored credentials (metadata only)."""
    from trust_protocol.sdk import TrustProtocolClient

    with TrustProtocolClient(url, admin_key=admin_key) as client:
        creds = client.list_credentials()

    table = Table(title="Stored Credentials")
    table.add_column("Name", style="cyan")
    table.add_column("Min Trust", style="green")
    table.add_column("Access Count")
    table.add_column("Created")

    for c in creds:
        table.add_row(c["name"], c["minimum_trust"], str(c["access_count"]), c.get("created", ""))

    console.print(table)


# --- Publisher commands ---

pub_app = typer.Typer(help="Publisher management")
app.add_typer(pub_app, name="pub")


@pub_app.command("register")
def pub_register(
    name: str = typer.Argument(..., help="Publisher name"),
    organization: str = typer.Option("", help="Organization"),
    public_key: Path = typer.Option(..., help="Path to public key PEM file"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Register a skill publisher."""
    from trust_protocol.sdk import TrustProtocolClient

    pub_pem = public_key.read_text()

    with TrustProtocolClient(url, admin_key=admin_key) as client:
        result = client.register_publisher(name, organization, pub_pem)

    console.print(f"[bold green]Publisher registered:[/bold green]")
    console.print(f"  ID:   {result['publisher_id']}")
    console.print(f"  Name: {result['name']}")
    console.print(f"  Tier: {result['trust_tier']}")


# --- Skill commands ---

skill_app = typer.Typer(help="Skill signing and verification")
app.add_typer(skill_app, name="skill")


@skill_app.command("sign")
def skill_sign(
    name: str = typer.Argument(..., help="Skill name"),
    version: str = typer.Argument(..., help="Skill version"),
    publisher_id: str = typer.Option(..., help="Publisher ID"),
    code_path: Path = typer.Option(..., help="Path to skill code file"),
    private_key: Path = typer.Option(..., help="Path to private key PEM file"),
    output: Path = typer.Option("signed-manifest.json", help="Output file"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Sign a skill manifest."""
    from trust_protocol.core.skill_signer import hash_code
    from trust_protocol.sdk import TrustProtocolClient

    code = code_path.read_bytes()
    code_hash = hash_code(code)
    priv_pem = private_key.read_bytes()
    priv_b64 = base64.b64encode(priv_pem).decode()

    with TrustProtocolClient(url, admin_key=admin_key) as client:
        result = client.sign_skill(
            name=name, version=version, publisher_id=publisher_id,
            code_hash=code_hash, private_key_pem_b64=priv_b64,
        )

    output.write_text(json.dumps(result, indent=2))
    console.print(f"[bold green]Skill signed:[/bold green] {name} v{version}")
    console.print(f"  Code hash: {code_hash}")
    console.print(f"  Output:    {output}")


@skill_app.command("verify")
def skill_verify(
    manifest_path: Path = typer.Argument(..., help="Path to signed manifest JSON"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
):
    """Verify a signed skill manifest (no auth required)."""
    from trust_protocol.sdk import TrustProtocolClient

    manifest = json.loads(manifest_path.read_text())

    with TrustProtocolClient(url) as client:
        result = client.verify_skill(manifest)

    if result["verified"]:
        console.print(f"[bold green]VERIFIED[/bold green]")
        console.print(f"  Publisher: {result.get('publisher_name')}")
        console.print(f"  Tier:      {result.get('publisher_trust_tier')}")
        console.print(f"  Since:     {result.get('registered_since')}")
    else:
        console.print(f"[bold red]VERIFICATION FAILED[/bold red]")
        console.print(f"  Reason: {result.get('reason')}")
        raise typer.Exit(1)


# --- Emergency ---

@app.command("emergency")
def emergency(
    action: str = typer.Argument(..., help="activate|clear|status"),
    scope: str = typer.Option("global", help="global|agent|credential"),
    reason: str = typer.Option("", help="Reason for activation"),
    agent_id: Optional[str] = typer.Option(None, help="Agent ID (for agent scope)"),
    credential_name: Optional[str] = typer.Option(None, help="Credential name (for credential scope)"),
    confirmation: str = typer.Option("", help="Confirmation string for clearing global brake"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Emergency brake controls."""
    from trust_protocol.sdk import TrustProtocolClient

    with TrustProtocolClient(url, admin_key=admin_key) as client:
        if action == "activate":
            result = client.activate_emergency(reason, scope, agent_id, credential_name)
            console.print(f"[bold red]Emergency brake activated[/bold red] (scope: {scope})")
        elif action == "clear":
            result = client.clear_emergency(scope, confirmation, agent_id, credential_name)
            console.print(f"[bold green]Emergency brake cleared[/bold green] (scope: {scope})")
        elif action == "status":
            result = client.emergency_status()
            console.print(f"Global active: {result['global_active']}")
            console.print(f"Blocked agents: {len(result['blocked_agents'])}")
            console.print(f"Blocked credentials: {len(result['blocked_credentials'])}")
        else:
            console.print(f"[bold red]Unknown action:[/bold red] {action}. Use activate|clear|status")
            raise typer.Exit(1)


def main():
    app()


if __name__ == "__main__":
    main()
