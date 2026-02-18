"""TRUST Protocol CLI.

Usage:
    trust-protocol serve              # Start the API server
    trust-protocol status             # Check server health
    trust-protocol unseal             # Unseal the vault
    trust-protocol seal               # Re-seal the vault
    trust-protocol keygen             # Generate Ed25519 keypair
    trust-protocol setup              # Interactive setup wizard
    trust-protocol emergency          # Emergency controls

    trust-protocol agent register     # Register a new agent
    trust-protocol agent list         # List agents
    trust-protocol agent get          # Get agent details
    trust-protocol agent promote      # Promote agent trust tier
    trust-protocol agent suspend      # Suspend an agent
    trust-protocol agent revoke       # Revoke an agent

    trust-protocol cred store         # Store a credential
    trust-protocol cred list          # List credentials
    trust-protocol cred delete        # Delete a credential
    trust-protocol cred proxy-execute # Execute through the credential proxy

    trust-protocol token issue        # Issue a token for an agent
    trust-protocol token list         # List tokens
    trust-protocol token validate     # Validate a token
    trust-protocol token renew        # Renew a token
    trust-protocol token revoke       # Revoke a token

    trust-protocol audit list         # List audit entries
    trust-protocol audit verify       # Verify audit chain integrity

    trust-protocol behavior score     # Get agent behavior score
    trust-protocol behavior submit    # Submit behavior metrics

    trust-protocol pub register       # Register a publisher
    trust-protocol pub list           # List publishers
    trust-protocol pub revoke         # Revoke a publisher

    trust-protocol skill sign         # Sign a skill manifest locally
    trust-protocol skill publish      # Publish signed manifest to registry
    trust-protocol skill verify       # Verify a signed manifest
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


# ---------------------------------------------------------------------------
# Helper: connect or die
# ---------------------------------------------------------------------------

def _client(url: str, admin_key: str = None, agent_key: str = None):
    """Return a TrustProtocolClient context manager."""
    from trust_protocol.sdk import TrustProtocolClient
    return TrustProtocolClient(url, admin_key=admin_key, agent_key=agent_key)


def _handle_error(e):
    """Print a TrustProtocolError nicely."""
    from trust_protocol.sdk import TrustProtocolError
    if isinstance(e, TrustProtocolError):
        console.print(f"[bold red]Error {e.status_code}:[/bold red] {e.detail}")
    else:
        console.print(f"[bold red]Error:[/bold red] {e}")
    raise typer.Exit(1)


# ===================================================================
# Top-level commands
# ===================================================================

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

    try:
        r = httpx.get(f"{url}/v1/seal-status", timeout=5)
        status = r.json()
        if not status["sealed"]:
            console.print("[yellow]Server is already unsealed.[/yellow]")
            raise typer.Exit(0)
    except httpx.ConnectError:
        console.print(f"[bold red]Cannot reach server at {url}[/bold red]")
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


# ===================================================================
# Agent commands
# ===================================================================

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
    creds = [c.strip() for c in credentials.split(",")] if credentials else []
    caps = [c.strip() for c in capabilities.split(",")] if capabilities else []

    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.register_agent(
                name=name, agent_type=agent_type, description=description,
                required_credentials=creds, capabilities=caps,
            )
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Agent registered:[/bold green]")
    console.print(f"  Agent ID:   {result['agent_id']}")
    console.print(f"  Trust Tier: {result['trust_tier']}")
    console.print(f"  API Key:    {result['api_key']}")
    console.print(f"[bold yellow]Save the API key! It cannot be recovered.[/bold yellow]")


@agent_app.command("list")
def agent_list(
    status_filter: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """List all registered agents."""
    try:
        with _client(url, admin_key=admin_key) as c:
            agents = c.list_agents(status=status_filter)
    except Exception as e:
        _handle_error(e)

    table = Table(title="Registered Agents")
    table.add_column("Agent ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Tier", style="green")
    table.add_column("Status")

    for a in agents:
        table.add_row(a["agent_id"], a["name"], a["agent_type"], a["trust_tier"], a["status"])

    console.print(table)


@agent_app.command("get")
def agent_get(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Get details for a specific agent."""
    try:
        with _client(url, admin_key=admin_key) as c:
            agent = c.get_agent(agent_id)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold]Agent:[/bold] {agent['name']}")
    console.print(f"  ID:          {agent['agent_id']}")
    console.print(f"  Type:        {agent['agent_type']}")
    console.print(f"  Trust Tier:  [green]{agent['trust_tier']}[/green]")
    console.print(f"  Status:      {agent['status']}")
    console.print(f"  Description: {agent.get('description', '')}")
    if agent.get("required_credentials"):
        console.print(f"  Credentials: {', '.join(agent['required_credentials'])}")
    if agent.get("capabilities"):
        console.print(f"  Capabilities: {', '.join(agent['capabilities'])}")
    console.print(f"  Registered:  {agent.get('registered', '')}")


@agent_app.command("promote")
def agent_promote(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    tier: str = typer.Argument(..., help="Target trust tier (COMPANION, PARTNER, GUARDIAN, SACRED)"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Promote an agent to a higher trust tier."""
    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.promote_agent(agent_id, tier.upper())
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Agent promoted:[/bold green] {result.get('name', agent_id)} → {tier.upper()}")


@agent_app.command("suspend")
def agent_suspend(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Suspend an agent (revocable)."""
    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.suspend_agent(agent_id)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold yellow]Agent suspended:[/bold yellow] {result.get('name', agent_id)}")


@agent_app.command("revoke")
def agent_revoke(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Permanently revoke an agent."""
    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.revoke_agent(agent_id)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold red]Agent revoked:[/bold red] {result.get('name', agent_id)}")


# ===================================================================
# Credential commands
# ===================================================================

cred_app = typer.Typer(help="Credential management")
app.add_typer(cred_app, name="cred")


@cred_app.command("store")
def cred_store(
    name: str = typer.Argument(..., help="Credential name"),
    value: str = typer.Option(..., help="Credential value (or JSON object)"),
    minimum_trust: str = typer.Option("COMPANION", help="Minimum trust tier"),
    allowed_domains: Optional[str] = typer.Option(
        None, "--allowed-domains",
        help="Comma-separated domain patterns (e.g. 'api.openai.com,*.github.com'). "
             "Empty means unrestricted.",
    ),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Store a credential in the vault.

    Use --allowed-domains to restrict which URLs this credential can
    be proxied to.  Supports wildcards (e.g. '*.openai.com').  If
    omitted, the credential is unrestricted.

    Example:

        trust-protocol cred store openai_key --value "sk-..." \\
          --allowed-domains "api.openai.com"
    """
    # Try to parse as JSON, fallback to simple value
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        data = {"value": value}

    domains = [d.strip() for d in allowed_domains.split(",")] if allowed_domains else []

    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.store_credential(name, data, minimum_trust.upper(), allowed_domains=domains)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Credential stored:[/bold green] {result['name']} (min trust: {result['minimum_trust']})")
    if domains:
        console.print(f"  Allowed domains: {', '.join(domains)}")
    else:
        console.print(f"  Allowed domains: [yellow]unrestricted[/yellow]")


@cred_app.command("list")
def cred_list(
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """List stored credentials (metadata only)."""
    try:
        with _client(url, admin_key=admin_key) as c:
            creds = c.list_credentials()
    except Exception as e:
        _handle_error(e)

    table = Table(title="Stored Credentials")
    table.add_column("Name", style="cyan")
    table.add_column("Min Trust", style="green")
    table.add_column("Allowed Domains")
    table.add_column("Access Count")
    table.add_column("Created")

    for cr in creds:
        domains = cr.get("allowed_domains", [])
        domain_str = ", ".join(domains) if domains else "[yellow]*[/yellow]"
        table.add_row(cr["name"], cr["minimum_trust"], domain_str, str(cr["access_count"]), cr.get("created", ""))

    console.print(table)


@cred_app.command("delete")
def cred_delete(
    name: str = typer.Argument(..., help="Credential name"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Delete a credential from the vault."""
    try:
        with _client(url, admin_key=admin_key) as c:
            c.delete_credential(name)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Credential deleted:[/bold green] {name}")


@cred_app.command("proxy-execute")
def cred_proxy_execute(
    name: str = typer.Argument(..., help="Credential name"),
    target_url: str = typer.Option(..., "--url", help="Target URL (use {{CREDENTIAL}} as placeholder)"),
    purpose: str = typer.Option(..., help="Purpose of this request"),
    method: str = typer.Option("GET", help="HTTP method"),
    header: Optional[list[str]] = typer.Option(None, help="Headers as 'Key: Value' (repeatable, use {{CREDENTIAL}} as placeholder)"),
    body: Optional[str] = typer.Option(None, help="Request body as JSON string"),
    timeout: int = typer.Option(30, help="Request timeout in seconds"),
    agent_key: str = typer.Option(..., envvar="TRUST_AGENT_KEY", help="Agent API key"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
):
    """Execute an HTTP request through the credential proxy.

    The agent sends a request template with {{CREDENTIAL}} placeholders.
    The server substitutes the real credential value and executes the
    HTTP request. Only the response is returned -- the agent never sees
    the credential.

    Example:

        trust-protocol cred proxy-execute openai_key \\
          --url "https://api.openai.com/v1/models" \\
          --header "Authorization: Bearer {{CREDENTIAL}}" \\
          --purpose "List models" \\
          --agent-key ak_xxx
    """
    headers_dict = {}
    if header:
        for h in header:
            if ":" not in h:
                console.print(f"[bold red]Invalid header format:[/bold red] {h} (expected 'Key: Value')")
                raise typer.Exit(1)
            key, val = h.split(":", 1)
            headers_dict[key.strip()] = val.strip()

    body_dict = None
    if body:
        try:
            body_dict = json.loads(body)
        except json.JSONDecodeError:
            console.print("[bold red]Invalid JSON body[/bold red]")
            raise typer.Exit(1)

    try:
        with _client(url, agent_key=agent_key) as c:
            result = c.execute_credential(
                name=name,
                purpose=purpose,
                method=method.upper(),
                url=target_url,
                headers=headers_dict,
                body=body_dict,
                timeout_seconds=timeout,
            )
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Proxy response:[/bold green] HTTP {result['status_code']}")
    console.print(f"  Time: {result.get('execution_time_ms', '?')}ms")
    console.print()

    # Pretty-print the body if it looks like JSON
    resp_body = result.get("body", "")
    try:
        parsed = json.loads(resp_body)
        console.print_json(json.dumps(parsed))
    except (json.JSONDecodeError, TypeError):
        console.print(resp_body)


# ===================================================================
# Token commands
# ===================================================================

token_app = typer.Typer(help="Token management")
app.add_typer(token_app, name="token")


@token_app.command("issue")
def token_issue(
    agent_id: str = typer.Argument(..., help="Agent ID to issue token for"),
    patterns: Optional[str] = typer.Option(None, help="Comma-separated credential patterns (default: *)"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Issue a new token for an agent."""
    cred_patterns = [p.strip() for p in patterns.split(",")] if patterns else ["*"]

    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.issue_token(agent_id, cred_patterns)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Token issued:[/bold green]")
    console.print(f"  Token ID: {result['token_id']}")
    console.print(f"  Agent:    {result.get('agent_id', agent_id)}")
    console.print(f"  Expires:  {result.get('expires', 'N/A')}")


@token_app.command("list")
def token_list(
    agent_id: Optional[str] = typer.Option(None, help="Filter by agent ID"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """List all tokens."""
    try:
        with _client(url, admin_key=admin_key) as c:
            tokens = c.list_tokens(agent_id=agent_id)
    except Exception as e:
        _handle_error(e)

    table = Table(title="Tokens")
    table.add_column("Token ID", style="cyan")
    table.add_column("Agent ID")
    table.add_column("Status", style="green")
    table.add_column("Expires")
    table.add_column("Renewals")

    for t in tokens:
        table.add_row(
            t["token_id"],
            t.get("agent_id", ""),
            t.get("status", ""),
            t.get("expires", ""),
            str(t.get("renewal_count", 0)),
        )

    console.print(table)


@token_app.command("validate")
def token_validate(
    token_id: str = typer.Argument(..., help="Token ID"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Validate a token."""
    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.validate_token(token_id)
    except Exception as e:
        _handle_error(e)

    valid = result.get("valid", False)
    if valid:
        console.print(f"[bold green]Token valid[/bold green]")
    else:
        console.print(f"[bold red]Token invalid[/bold red]")

    console.print(f"  Token ID:  {result.get('token_id', token_id)}")
    console.print(f"  Agent ID:  {result.get('agent_id', '')}")
    console.print(f"  Status:    {result.get('status', '')}")
    console.print(f"  Expires:   {result.get('expires', '')}")


@token_app.command("renew")
def token_renew(
    token_id: str = typer.Argument(..., help="Token ID"),
    score: float = typer.Option(1.0, help="Behavior score (0.0 - 1.0)"),
    agent_key: Optional[str] = typer.Option(None, envvar="TRUST_AGENT_KEY", help="Agent API key"),
    admin_key: Optional[str] = typer.Option(None, envvar="TRUST_ADMIN_KEY", help="Admin key"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
):
    """Renew a token. Works with either admin or agent key."""
    if not agent_key and not admin_key:
        console.print("[bold red]Either --agent-key or --admin-key is required[/bold red]")
        raise typer.Exit(1)

    try:
        with _client(url, admin_key=admin_key, agent_key=agent_key) as c:
            result = c.renew_token(token_id, behavior_score=score)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Token renewed:[/bold green] {result.get('token_id', token_id)}")
    console.print(f"  New expiry: {result.get('expires', 'N/A')}")
    console.print(f"  Renewals:   {result.get('renewal_count', '?')}")


@token_app.command("revoke")
def token_revoke(
    token_id: str = typer.Argument(..., help="Token ID"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Revoke a token."""
    try:
        with _client(url, admin_key=admin_key) as c:
            c.revoke_token(token_id)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Token revoked:[/bold green] {token_id}")


# ===================================================================
# Audit commands
# ===================================================================

audit_app = typer.Typer(help="Audit chain")
app.add_typer(audit_app, name="audit")


@audit_app.command("list")
def audit_list(
    event_type: Optional[str] = typer.Option(None, "--type", help="Filter by event type"),
    agent_id: Optional[str] = typer.Option(None, help="Filter by agent ID"),
    limit: int = typer.Option(20, help="Max entries to return"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """List audit log entries."""
    try:
        with _client(url, admin_key=admin_key) as c:
            entries = c.query_audit(event_type=event_type, agent_id=agent_id, limit=limit)
    except Exception as e:
        _handle_error(e)

    table = Table(title=f"Audit Log ({len(entries)} entries)")
    table.add_column("#", style="dim")
    table.add_column("Timestamp")
    table.add_column("Event", style="cyan")
    table.add_column("Agent")
    table.add_column("Details")

    for i, entry in enumerate(entries):
        details = entry.get("details", {})
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items()) if isinstance(details, dict) else str(details)
        if len(detail_str) > 60:
            detail_str = detail_str[:57] + "..."
        table.add_row(
            str(entry.get("sequence", i)),
            entry.get("timestamp", "")[:19],
            entry.get("event_type", ""),
            entry.get("agent_id", "-"),
            detail_str,
        )

    console.print(table)


@audit_app.command("verify")
def audit_verify(
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Verify the audit chain has not been tampered with."""
    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.verify_audit()
    except Exception as e:
        _handle_error(e)

    if result.get("valid"):
        console.print(f"[bold green]Audit chain verified:[/bold green] {result.get('message', 'OK')}")
    else:
        console.print(f"[bold red]Audit chain BROKEN:[/bold red] {result.get('message', 'Verification failed')}")
        raise typer.Exit(1)


# ===================================================================
# Behavior commands
# ===================================================================

behavior_app = typer.Typer(help="Behavioral monitoring")
app.add_typer(behavior_app, name="behavior")


@behavior_app.command("score")
def behavior_score(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Get the behavior score for an agent."""
    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.get_behavior_score(agent_id)
    except Exception as e:
        _handle_error(e)

    score = result.get("score", 0)
    color = "green" if score >= 0.7 else "yellow" if score >= 0.4 else "red"
    console.print(f"[bold]Agent:[/bold] {agent_id}")
    console.print(f"  Score: [{color}]{score:.2f}[/{color}]")
    if result.get("anomalies"):
        console.print(f"  [bold yellow]Anomalies:[/bold yellow]")
        for a in result["anomalies"]:
            console.print(f"    - {a}")


@behavior_app.command("submit")
def behavior_submit(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    requests: int = typer.Option(0, help="Number of requests"),
    errors: int = typer.Option(0, help="Number of errors"),
    latency_ms: float = typer.Option(0, help="Average latency in ms"),
    agent_key: str = typer.Option(..., envvar="TRUST_AGENT_KEY", help="Agent API key"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
):
    """Submit behavior metrics for an agent."""
    try:
        with _client(url, agent_key=agent_key) as c:
            result = c.submit_metrics(
                agent_id,
                request_count=requests,
                error_count=errors,
                avg_latency_ms=latency_ms,
            )
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Metrics submitted[/bold green] for {agent_id}")


# ===================================================================
# Publisher commands
# ===================================================================

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
    pub_pem = public_key.read_text()

    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.register_publisher(name, organization, pub_pem)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold green]Publisher registered:[/bold green]")
    console.print(f"  ID:   {result['publisher_id']}")
    console.print(f"  Name: {result['name']}")
    console.print(f"  Tier: {result['trust_tier']}")


@pub_app.command("list")
def pub_list(
    status_filter: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """List all publishers."""
    try:
        with _client(url, admin_key=admin_key) as c:
            publishers = c.list_publishers(status=status_filter)
    except Exception as e:
        _handle_error(e)

    table = Table(title="Publishers")
    table.add_column("Publisher ID", style="cyan")
    table.add_column("Name")
    table.add_column("Organization")
    table.add_column("Tier", style="green")
    table.add_column("Status")

    for p in publishers:
        table.add_row(
            p["publisher_id"],
            p["name"],
            p.get("organization", ""),
            p.get("trust_tier", ""),
            p.get("status", ""),
        )

    console.print(table)


@pub_app.command("revoke")
def pub_revoke(
    publisher_id: str = typer.Argument(..., help="Publisher ID"),
    reason: str = typer.Option("", help="Reason for revocation"),
    url: str = typer.Option("http://localhost:9500", help="Server URL"),
    admin_key: str = typer.Option(..., envvar="TRUST_ADMIN_KEY", help="Admin key"),
):
    """Revoke a publisher's key."""
    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.revoke_publisher(publisher_id, reason=reason)
    except Exception as e:
        _handle_error(e)

    console.print(f"[bold red]Publisher revoked:[/bold red] {result.get('name', publisher_id)}")


# ===================================================================
# Skill commands
# ===================================================================

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
    manifest = json.loads(manifest_path.read_text())

    try:
        with _client(url, admin_key=admin_key) as c:
            result = c.publish_skill(manifest)
    except Exception as e:
        _handle_error(e)

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
    manifest = json.loads(manifest_path.read_text())

    try:
        with _client(url) as c:
            result = c.verify_skill(manifest)
    except Exception as e:
        _handle_error(e)

    if result["verified"]:
        console.print(f"[bold green]VERIFIED[/bold green]")
        console.print(f"  Publisher: {result.get('publisher_name')}")
        console.print(f"  Tier:      {result.get('publisher_trust_tier')}")
        console.print(f"  Since:     {result.get('registered_since')}")
    else:
        console.print(f"[bold red]VERIFICATION FAILED[/bold red]")
        console.print(f"  Reason: {result.get('reason')}")
        raise typer.Exit(1)


# ===================================================================
# Setup Wizard
# ===================================================================

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

    TRUST_HOME.mkdir(parents=True, exist_ok=True)

    config_path = TRUST_HOME / "config.json"
    priv_path = TRUST_HOME / "publisher.key"
    pub_path = TRUST_HOME / "publisher.pub"

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


# ===================================================================
# Emergency
# ===================================================================

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
    try:
        with _client(url, admin_key=admin_key) as c:
            if action == "activate":
                result = c.activate_emergency(reason, scope, agent_id, credential_name)
                console.print(f"[bold red]Emergency brake activated[/bold red] (scope: {scope})")
            elif action == "clear":
                result = c.clear_emergency(scope, confirmation, agent_id, credential_name)
                console.print(f"[bold green]Emergency brake cleared[/bold green] (scope: {scope})")
            elif action == "status":
                result = c.emergency_status()
                console.print(f"Global active: {result['global_active']}")
                console.print(f"Blocked agents: {len(result['blocked_agents'])}")
                console.print(f"Blocked credentials: {len(result['blocked_credentials'])}")
            else:
                console.print(f"[bold red]Unknown action:[/bold red] {action}. Use activate|clear|status")
                raise typer.Exit(1)
    except Exception as e:
        if "Unknown action" not in str(e):
            _handle_error(e)


# ===================================================================
# Entry point
# ===================================================================

def main():
    app()


if __name__ == "__main__":
    main()
