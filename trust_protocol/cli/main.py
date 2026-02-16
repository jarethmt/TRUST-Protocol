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
    trust-protocol skill sign     # Sign a skill manifest locally
    trust-protocol skill publish  # Publish signed manifest to registry
    trust-protocol skill verify   # Verify a signed manifest
    trust-protocol setup          # Interactive setup wizard
    trust-protocol emergency      # Emergency controls
"""

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


# --- Unseal ---

@app.command("unseal")
def unseal_cmd(
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Unseal the vault on a running server.

    Prompts for the master password interactively.  The password is sent
    to the server once and held only in server process memory -- never
    written to disk.
    """
    import getpass
    import httpx

    # Check current seal status
    try:
        r = httpx.get(f"{url}/v1/seal-status", timeout=5)
        status = r.json()
        if not status["sealed"]:
            console.print("[yellow]Server is already unsealed.[/yellow]")
            raise typer.Exit(0)
    except httpx.ConnectError:
        console.print("[bold red]Cannot reach server at {url}[/bold red]")
        raise typer.Exit(1)

    password = getpass.getpass("Vault master password: ")
    if not password:
        console.print("[red]Password cannot be empty.[/red]")
        raise typer.Exit(1)

    try:
        r = httpx.post(
            f"{url}/v1/unseal",
            headers={"X-Admin-Key": admin_key},
            json={"password": password},
            timeout=10,
        )
        if r.status_code == 200:
            console.print("[bold green]Vault unsealed successfully.[/bold green]")
        else:
            detail = r.json().get("detail", r.text)
            console.print(f"[bold red]Unseal failed:[/bold red] {detail}")
            raise typer.Exit(1)
    except httpx.ConnectError:
        console.print("[bold red]Cannot reach server.[/bold red]")
        raise typer.Exit(1)


# --- Seal ---

@app.command("seal")
def seal_cmd(
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Re-seal the vault on a running server.

    Clears the master password from server memory.  Credential operations
    will return 503 until the server is unsealed again.
    """
    import httpx

    try:
        r = httpx.post(
            f"{url}/v1/seal",
            headers={"X-Admin-Key": admin_key},
            timeout=10,
        )
        if r.status_code == 200:
            console.print("[bold green]Server sealed. Credential operations disabled.[/bold green]")
        else:
            detail = r.json().get("detail", r.text)
            console.print(f"[bold red]Seal failed:[/bold red] {detail}")
            raise typer.Exit(1)
    except httpx.ConnectError:
        console.print("[bold red]Cannot reach server.[/bold red]")
        raise typer.Exit(1)


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
    code_path: Path = typer.Option(..., help="Path to skill code file or directory"),
    private_key: Path = typer.Option(..., help="Path to private key PEM file"),
    output: Path = typer.Option("signed-manifest.json", help="Output file"),
    capabilities: Optional[str] = typer.Option(None, help="Comma-separated capabilities"),
    credentials: Optional[str] = typer.Option(None, help="Comma-separated required credentials"),
    description: str = typer.Option("", help="Skill description"),
):
    """Sign a skill manifest locally. The private key never leaves your machine."""
    from trust_protocol.core.skill_signer import hash_code
    from trust_protocol.sdk import TrustProtocolClient

    code = code_path.read_bytes()
    code_hash = hash_code(code)
    priv_pem = private_key.read_bytes()

    caps = [c.strip() for c in capabilities.split(",")] if capabilities else []
    creds = [c.strip() for c in credentials.split(",")] if credentials else []

    result = TrustProtocolClient.sign_locally(
        name=name,
        version=version,
        publisher_id=publisher_id,
        code_hash=code_hash,
        private_key_pem=priv_pem,
        capabilities=caps,
        credentials_required=creds,
        description=description,
    )

    output.write_text(json.dumps(result, indent=2))
    console.print(f"[bold green]Skill signed locally:[/bold green] {name} v{version}")
    console.print(f"  Code hash:  {code_hash}")
    console.print(f"  Output:     {output}")
    console.print(f"[dim]Private key was used locally and never transmitted.[/dim]")


@skill_app.command("publish")
def skill_publish(
    manifest_path: Path = typer.Argument(..., help="Path to signed manifest JSON"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Publish a signed manifest to the registry. Sign locally first with 'skill sign'."""
    from trust_protocol.sdk import TrustProtocolClient

    manifest = json.loads(manifest_path.read_text())

    with TrustProtocolClient(url, admin_key=admin_key) as client:
        result = client.publish_skill(manifest)

    if result.get("published"):
        console.print(f"[bold green]Skill published:[/bold green] {result['manifest']['manifest']['name']}")
        console.print(f"  Publisher: {result['publisher_name']}")
        console.print(f"  Tier:      {result['publisher_trust_tier']}")
    else:
        console.print(f"[bold red]Publication failed[/bold red]")
        raise typer.Exit(1)


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


# --- Setup Wizard ---

TRUST_HOME = Path.home() / ".trust-protocol"


@app.command("setup")
def setup(
    registry_url: str = typer.Option("http://localhost:9500", help="TRUST Protocol registry URL"),
    admin_key: Optional[str] = typer.Option(None, envvar="TRUST_ADMIN_KEY", help="Admin key (for self-hosted registries)"),
    name: Optional[str] = typer.Option(None, help="Publisher name (skip interactive prompt)"),
    organization: Optional[str] = typer.Option(None, help="Organization name"),
):
    """Set up TRUST Protocol for skill publishing in one step.

    Generates an Ed25519 keypair, registers you as a publisher, and saves
    your config to ~/.trust-protocol/. After this, you can sign and
    publish skills immediately.
    """
    from trust_protocol.core.skill_signer import generate_keypair

    console.print()
    console.print("[bold]TRUST Protocol Setup[/bold]")
    console.print("[dim]Setting up local signing and publisher registration.[/dim]")
    console.print()

    # --- Create config directory ---
    TRUST_HOME.mkdir(parents=True, exist_ok=True)

    config_path = TRUST_HOME / "config.json"
    priv_path = TRUST_HOME / "publisher.key"
    pub_path = TRUST_HOME / "publisher.pub"

    # Check for existing setup
    if config_path.exists():
        existing = json.loads(config_path.read_text())
        console.print(f"[yellow]Existing setup found:[/yellow]")
        console.print(f"  Publisher: {existing.get('publisher_name', 'unknown')}")
        console.print(f"  ID:        {existing.get('publisher_id', 'unknown')}")
        console.print(f"  Registry:  {existing.get('registry_url', 'unknown')}")
        console.print()
        if not typer.confirm("Overwrite existing setup?", default=False):
            console.print("[dim]Setup cancelled.[/dim]")
            raise typer.Exit(0)

    # --- Collect info ---
    if name is None:
        name = typer.prompt("Publisher name (your name or org)")
    if organization is None:
        organization = typer.prompt("Organization (leave empty if personal)", default="")

    console.print()
    console.print("[bold]Generating Ed25519 keypair...[/bold]")
    private_pem, public_pem = generate_keypair()

    priv_path.write_bytes(private_pem)
    priv_path.chmod(0o600)
    pub_path.write_bytes(public_pem)

    console.print(f"  Private key: {priv_path} [dim](chmod 600)[/dim]")
    console.print(f"  Public key:  {pub_path}")

    # --- Register with registry ---
    publisher_id = None
    trust_tier = None

    console.print()
    console.print(f"[bold]Registering with registry at {registry_url}...[/bold]")

    try:
        import httpx

        headers = {}
        if admin_key:
            headers["X-Admin-Key"] = admin_key

        r = httpx.post(
            f"{registry_url}/v1/publishers",
            headers=headers,
            json={
                "name": name,
                "organization": organization,
                "public_key_pem": public_pem.decode(),
            },
            timeout=10,
        )

        if r.status_code == 201:
            data = r.json()
            publisher_id = data["publisher_id"]
            trust_tier = data.get("trust_tier", "NOVICE")
            console.print(f"  [green]Registered![/green]")
            console.print(f"  Publisher ID: {publisher_id}")
            console.print(f"  Trust tier:   {trust_tier}")
        elif r.status_code == 409:
            console.print(f"  [yellow]Publisher name '{name}' already exists.[/yellow]")
            console.print(f"  [dim]You may need to choose a different name.[/dim]")
        else:
            console.print(f"  [yellow]Registration returned {r.status_code}[/yellow]")
            console.print(f"  [dim]{r.text}[/dim]")
            console.print(f"  [dim]Keys were saved locally. You can register manually later.[/dim]")
    except Exception as e:
        console.print(f"  [yellow]Could not reach registry:[/yellow] {e}")
        console.print(f"  [dim]Keys were saved locally. Register when the registry is available.[/dim]")

    # --- Save config ---
    config = {
        "publisher_name": name,
        "publisher_id": publisher_id,
        "organization": organization,
        "trust_tier": trust_tier,
        "registry_url": registry_url,
        "private_key_path": str(priv_path),
        "public_key_path": str(pub_path),
    }
    config_path.write_text(json.dumps(config, indent=2))

    console.print()
    console.print(f"[bold green]Setup complete![/bold green]")
    console.print(f"  Config saved to: {config_path}")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  1. Sign a skill:   trust-protocol skill sign my-skill 1.0.0 --publisher-id {publisher_id or 'YOUR_ID'} --code-path ./skill.py --private-key {priv_path}")
    console.print(f"  2. Publish it:     trust-protocol skill publish signed-manifest.json")
    console.print(f"  3. Anyone verifies: trust-protocol skill verify signed-manifest.json")


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
