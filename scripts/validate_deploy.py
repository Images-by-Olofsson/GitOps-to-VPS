
import sys
import json
import subprocess
import os
import datetime
import argparse
from typing import Any, Dict, List

# --- Visual Styling ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {msg} ==={Colors.ENDC}")

def print_check(msg, status="ok"):
    if status == "ok":
        print(f"  {Colors.OKGREEN}✓{Colors.ENDC} {msg}")
    elif status == "fail":
        print(f"  {Colors.FAIL}✗{Colors.ENDC} {msg}")
    elif status == "warn":
        print(f"  {Colors.WARNING}!{Colors.ENDC} {msg}")
    else:
        print(f"  • {msg}")

def print_service_header(service_name):
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}Service: {service_name}{Colors.ENDC}")

# --- Helper Functions ---

def parse_labels(labels_list_or_dict):
    """Normalize labels to a dictionary."""
    if isinstance(labels_list_or_dict, dict):
        return labels_list_or_dict
    
    label_dict = {}
    if isinstance(labels_list_or_dict, list):
        for l in labels_list_or_dict:
            if '=' in l:
                k, v = l.split('=', 1)
                label_dict[k] = v
            else:
                label_dict[l] = ""
    return label_dict

def get_router_middlewares(labels, router_name):
    """
    Get the list of middlewares applied to a specific router.
    Looks for label: traefik.http.routers.<router_name>.middlewares
    """
    key = f"traefik.http.routers.{router_name}.middlewares"
    if key in labels:
        return [m.strip() for m in labels[key].split(',')]
    return []

def get_middleware_definitions(labels):
    """
    Parse middleware definitions from labels.
    Returns a dict: {middleware_name: [list of underlying middlewares or config]}
    Handles chains transparently by just storing the value.
    Specific case: traefik.http.middlewares.<name>.chain.middlewares=mw1,mw2
    """
    defs = {}
    for k, v in labels.items():
        # Check for chain definition
        # Format: traefik.http.middlewares.<name>.chain.middlewares
        if k.startswith("traefik.http.middlewares.") and ".chain.middlewares" in k:
            parts = k.split('.')
            # traefik.http.middlewares.<name>.chain.middlewares -> name is at index 3
            if len(parts) >= 4:
                mw_name = parts[3]
                defs[mw_name] = [m.strip() for m in v.split(',')]
    return defs

def resolve_middlewares(middleware_list, definitions, depth=0):
    """
    Recursively resolve a list of middlewares against definitions to find
    effective middlewares (e.g. expanding chains).
    Returns a set of all effective middleware names/types.
    """
    resolved = set()
    if depth > 5: # prevent infinite recursion
        return resolved

    for mw in middleware_list:
        clean_mw = mw.split('@')[0] # remove @docker, @file etc for matching definitions logic if needed, 
                                    # but definitions usually match the name used.
        
        # If it's a chain we know about, expand it
        if clean_mw in definitions:
            resolved.update(resolve_middlewares(definitions[clean_mw], definitions, depth+1))
        else:
            resolved.add(mw)
    
    return resolved

def get_container_runtime_status(paths_to_check):
    """
    Fetch runtime status of containers using 'docker compose ps --format json'.
    Returns a dict mapping service name (or container name) to status info.
    """
    containers = {}
    for path in paths_to_check:
        if not os.path.exists(path):
            continue
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", path, "ps", "--format", "json", "-a"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            output = result.stdout.strip()
            if not output:
                 continue
            
            try:
                data = json.loads(output)
                if isinstance(data, dict):
                    data = [data]
            except json.JSONDecodeError:
                data = []
                for line in output.split('\n'):
                    if line.strip():
                        try:
                            data.append(json.loads(line))
                        except:
                            pass
            
            for c in data:
                service = c.get('Service', c.get('Name', 'unknown'))
                containers[service] = {
                    'state': c.get('State', 'unknown'),
                    'status': c.get('Status', 'unknown'),
                    'health': c.get('Health', ''),
                    'name': c.get('Name', '')
                }

        except Exception as e:
            print(f"{Colors.WARNING}Warning: Could not fetch runtime status for {path}: {e}{Colors.ENDC}")
    return containers


def get_container_resource_stats():
    """
    Fetch CPU and memory usage per container using 'docker stats --no-stream'.
    Returns a dict: {service_name: {cpu_percent, mem_usage, mem_limit, mem_percent}}
    """
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             '{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        stats = {}
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) >= 4:
                name = parts[0].strip()
                cpu = parts[1].strip().rstrip('%')
                mem_parts = parts[2].strip().split(' / ')
                mem_usage = mem_parts[0] if len(mem_parts) >= 1 else 'N/A'
                mem_limit = mem_parts[1] if len(mem_parts) >= 2 else 'N/A'
                mem_pct = parts[3].strip().rstrip('%')
                stats[name] = {
                    'cpu_percent': float(cpu) if cpu else 0.0,
                    'mem_usage': mem_usage,
                    'mem_limit': mem_limit,
                    'mem_percent': float(mem_pct) if mem_pct else 0.0
                }
        return stats
    except Exception as e:
        print(f"{Colors.WARNING}Warning: Could not fetch resource stats: {e}{Colors.ENDC}")
        return {}


def get_certificate_info():
    """
    Read certificate data from Traefik's acme.json file.
    Tries common paths: /opt/traefik/certs/acme.json, /etc/traefik/acme.json
    Returns a list of {domain, expiry, days_left, issuer}
    """
    import ssl
    import base64

    acme_paths = [
        '/opt/traefik/certs/acme.json',
        '/opt/traefik/acme.json',
        '/etc/traefik/acme.json',
        './acme.json'
    ]

    acme_data = None
    for path in acme_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    acme_data = json.load(f)
                print_check(f"Certificate data loaded from {path}", "ok")
                break
            except Exception as e:
                print_check(f"Failed to read {path}: {e}", "warn")

    if not acme_data or not isinstance(acme_data, dict):
        print_check("No acme.json found (cert monitoring unavailable)", "warn")
        return []

    certs = []
    try:
        # acme.json structure varies by resolver name
        for resolver_name, resolver_data in acme_data.items():
            if not isinstance(resolver_data, dict):
                continue
            certificates = resolver_data.get('Certificates', [])
            if not certificates:
                # Try nested Account structure
                certificates = resolver_data.get('Account', {}).get('Certificates', [])

            for cert_entry in certificates:
                domain_info = cert_entry.get('domain', {})
                main_domain = domain_info.get('main', 'unknown')
                sans = domain_info.get('sans', [])

                # Try to parse certificate for expiry
                cert_pem = cert_entry.get('certificate', '')
                if cert_pem:
                    try:
                        cert_bytes = base64.b64decode(cert_pem)
                        # Use openssl to get expiry
                        result = subprocess.run(
                            ['openssl', 'x509', '-noout', '-enddate'],
                            input=cert_bytes,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        if result.returncode == 0:
                            date_str = result.stdout.decode().strip().replace('notAfter=', '')
                            # Parse: "Mar 14 12:00:00 2026 GMT"
                            expiry = datetime.datetime.strptime(date_str, '%b %d %H:%M:%S %Y %Z')
                            days_left = (expiry - datetime.datetime.utcnow()).days
                        else:
                            expiry = None
                            days_left = -1
                    except Exception:
                        expiry = None
                        days_left = -1
                else:
                    expiry = None
                    days_left = -1

                all_domains = [main_domain] + (sans or [])
                for d in all_domains:
                    certs.append({
                        'domain': d,
                        'expiry': expiry.isoformat() if expiry else 'unknown',  # type: ignore
                        'days_left': days_left,
                        'resolver': resolver_name
                    })
    except Exception as e:
        print_check(f"Error parsing certificate data: {e}", "warn")

    return certs


def get_deploy_history(deploy_path=None):
    """
    Read deployment history from deploy.log.
    Returns last 10 entries as a list of {timestamp, action, status}.
    """
    log_paths = [
        deploy_path + '/deploy.log' if deploy_path else None,
        './deploy.log',
        '/opt/gitops/deploy.log'
    ]

    for path in [p for p in log_paths if p]:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    lines: List[str] = f.readlines()
                entries = []
                for line in lines[-10:]:  # type: ignore
                    parts = line.strip().split(' | ')
                    if len(parts) >= 3:
                        entries.append({
                            'timestamp': parts[0].strip(),
                            'action': parts[1].strip(),
                            'status': parts[2].strip()
                        })
                return entries
            except Exception:
                pass
    return []


# --- Validation Logic ---

def validate_docker_compose(export_json_path=None, ci_mode=False):
    # Attempt to locate docker-compose.yml
    if not os.path.exists('docker-compose.yml'):
        if os.path.exists('../docker-compose.yml'):
            os.chdir('..')

    print_header("Docker Compose Validation")
    print(f"{Colors.OKBLUE}Running 'docker compose config' to resolve configuration...{Colors.ENDC}")

    compose_data = {'services': {}}
    paths_to_check = ['docker-compose.yml', 'infrastructure/docker-compose.yml']
    if os.path.exists('apps'):
        for item in os.listdir('apps'):
            app_path = os.path.join('apps', item, 'docker-compose.yml')
            if os.path.isfile(app_path):
                paths_to_check.append(app_path)

    for path in paths_to_check:
        if not os.path.exists(path):
            continue
        try:
            # Run docker compose config
            result = subprocess.run(
                ["docker", "compose", "-f", path, "config", "--format", "json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            data = json.loads(result.stdout)
            if 'services' in data:
                compose_data['services'].update(data['services'])
        except subprocess.CalledProcessError as e:
            print(f"\n{Colors.FAIL}Error running docker compose config on {path}:{Colors.ENDC}\n{e.stderr}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"\n{Colors.FAIL}Error parsing JSON output from {path}:{Colors.ENDC} {e}")
            sys.exit(1)
        except FileNotFoundError:
            print(f"\n{Colors.FAIL}Error: 'docker' command not found.{Colors.ENDC}")
            sys.exit(1)

    if not compose_data or 'services' not in compose_data:
        print(f"\n{Colors.FAIL}Error: No services found in configuration.{Colors.ENDC}")
        sys.exit(1)

    # Fetch Runtime Status (skip in CI mode - no containers running)
    if ci_mode:
        print(f"{Colors.WARNING}CI Mode: Skipping runtime status checks{Colors.ENDC}")
        runtime_status = {}
    else:
        runtime_status = get_container_runtime_status(paths_to_check)

    all_errors = {}
    services = compose_data.get('services', {})
    
    # Data for JSON export
    services_data: Dict[str, Any] = {}
    dashboard_data: Dict[str, Any] = {
        "timestamp": datetime.datetime.now().isoformat(),
        "services": services_data,
        "certificates": [],
        "resources": {},
        "deploys": [],
        "summary": "ok"
    }
    
    print(f"{Colors.OKGREEN}[OK] Configuration loaded successfully.{Colors.ENDC}")
    print(f"Found {len(services)} services to validate.")

    for service_name, service_config in services.items():
        print_service_header(service_name)
        service_errors = []
        
        # Runtime Info
        rt_info = runtime_status.get(service_name, {})
        state = rt_info.get('state', 'Not Running')
        status_text = rt_info.get('status', '-')
        
        print_check(f"Runtime State: {state} ({status_text})", "ok" if state.lower() == "running" else "warn")
        
        labels = parse_labels(service_config.get('labels', {}))
        
        # Identify Routers
        routers = []
        for k in labels.keys():
            if k.startswith("traefik.http.routers.") and ".rule" in k:
                # traefik.http.routers.<name>.rule -> extract name
                parts = k.split('.')
                if len(parts) >= 4:
                    routers.append(parts[3])
        
        # Get Definitions (Locally defined chains)
        mw_defs = get_middleware_definitions(labels)

        networks = service_config.get('networks', {})
        service_networks = list(networks.keys()) if isinstance(networks, dict) else networks
        deploy = service_config.get('deploy', {})
        resources = deploy.get('resources', {})
        limits = resources.get('limits', {})

        # --- 1. Domain Validation ---
        primary_domain = None
        if routers:
            print_check(f"Routers found: {', '.join(routers)}")
            has_domain = True 
            for r in routers:
                rule = labels.get(f"traefik.http.routers.{r}.rule", "")
                if "Host(" in rule:
                    try:
                        # Extract domain: Host(`domain`) or Host("domain")
                        start = rule.find("Host(") + 5
                        end = rule.find(")", start)
                        domain_val = rule[start:end].strip("`\"' ")
                        if not primary_domain:
                            primary_domain = domain_val
                    except Exception:
                        pass
                else:
                    has_domain = False
                    print_check(f"Router '{r}' missing 'Host()' in rule", "fail")
                    service_errors.append(f"Router '{r}' missing 'Host()' rule.")
            
            if has_domain:
                print_check("Domain rules check", "ok")

        else:
             if labels.get("traefik.enable") == "true":
                 print_check("Service enabled for Traefik but no routers defined", "warn")
             else:
                 print_check("Internal service (no routers)", "ok")


        # --- 2. Auth Policy & IP Security ---
        is_public = labels.get('custom.public') == 'true'
        
        if routers:
            for r in routers:
                applied_mws = get_router_middlewares(labels, r)
                effective_mws = resolve_middlewares(applied_mws, mw_defs)
                has_authelia = any('authelia@docker' in m for m in effective_mws)
                has_cf = any('cloudflare-headers' in m for m in effective_mws)

                if is_public:
                    print_check(f"Router '{r}': Public access allowed", "warn")
                else:
                    if has_authelia:
                        print_check(f"Router '{r}': Protected by Authelia", "ok")
                    else:
                        print_check(f"Router '{r}': NOT protected by Authelia (and not public)", "fail")
                        service_errors.append(f"Router '{r}' is missing Authelia middleware and passed 'custom.public=true' is not set.")

                if has_cf:
                     print_check(f"Router '{r}': IP Security active (cloudflare-headers)", "ok")
                else:
                     print_check(f"Router '{r}': Missing Cloudflare headers", "fail")
                     service_errors.append(f"Router '{r}' missing 'cloudflare-headers' middleware.")

        # --- 3. Network Requirements ---
        allowed_networks = ['traefik_traefik-network', 'soc-network']
        
        if not service_networks:
             print_check("No networks defined", "fail")
             service_errors.append("Network Error: No networks defined.")
        else:
            attached_ok = any(net in allowed_networks for net in service_networks)
            if attached_ok:
                print_check(f"Network ok: {service_networks}", "ok")
            else:
                 print_check(f"Invalid network: {service_networks}", "fail")
                 service_errors.append(f"Network Error: Must be attached to one of {allowed_networks}. Found: {service_networks}")


        # --- 4. Certificate Settings ---
        if routers:
            for r in routers:
                resolver = labels.get(f"traefik.http.routers.{r}.tls.certresolver")
                if resolver == "letsencrypt":
                    print_check(f"Router '{r}': TLS (letsencrypt)", "ok")
                else:
                    print_check(f"Router '{r}': Missing/Invalid certresolver", "fail")
                    service_errors.append(f"Router '{r}' must set 'tls.certresolver=letsencrypt'.")


        # --- 5. Resource Limits ---
        if not limits.get('cpus') or not limits.get('memory'):
            print_check("Resource limits missing", "fail")
            service_errors.append("Resource Limits: Missing 'deploy.resources.limits.cpus' or 'memory'.")
        else:
            print_check(f"Limits: CPU {limits.get('cpus')}, Mem {limits.get('memory')}", "ok")


        if service_errors:
            all_errors[service_name] = service_errors
            
        # Add to dashboard data
        services_data[service_name] = {  # type: ignore
            "status": "error" if service_errors else "healthy",
            "runtime_state": state,
            "runtime_status": status_text,
            "issues": service_errors,
            "config": {
                "cpu": limits.get('cpus', 'N/A'),
                "memory": limits.get('memory', 'N/A'),
                "public": is_public,
                "routers": len(routers),
                "domain": primary_domain
            }
        }

    # --- Collect Additional Data (skip in CI) ---
    if not ci_mode:
        # Certificate info
        print_header("Certificate Monitor")
        certs = get_certificate_info()
        dashboard_data['certificates'] = certs
        if certs:
            for cert in certs:
                days = int(cert.get('days_left', -1))
                domain = str(cert.get('domain', 'unknown'))
                status = 'ok' if days > 30 else ('warn' if days > 7 else 'fail')
                print_check(f"{domain}: {days} days left", status)
        else:
            print_check("No certificate data available", "warn")

        # Resource stats
        print_header("Resource Usage")
        resource_stats = get_container_resource_stats()
        dashboard_data['resources'] = resource_stats
        for name, stats in resource_stats.items():
            cpu_pct = float(stats.get('cpu_percent', 0.0))
            mem_u = str(stats.get('mem_usage', ''))
            mem_l = str(stats.get('mem_limit', ''))
            mem_p = float(stats.get('mem_percent', 0.0))
            cpu_status = 'ok' if cpu_pct < 80.0 else ('warn' if cpu_pct < 95.0 else 'fail')
            print_check(f"{name}: CPU {cpu_pct}% | MEM {mem_u}/{mem_l} ({mem_p}%)", cpu_status)

        # Deploy history
        print_header("Deploy History")
        deploys = get_deploy_history()
        dashboard_data['deploys'] = deploys
        if deploys:
            for d in deploys[-5:]:  # type: ignore
                action = str(d.get('action', ''))
                d_status = str(d.get('status', ''))
                d_time = str(d.get('timestamp', ''))
                status = 'ok' if d_status == 'SUCCESS' else 'fail'
                print_check(f"{d_time} | {action} | {d_status}", status)
        else:
            print_check("No deploy history found", "warn")

    # --- Summary & Export ---
    print_header("Validation Summary")
    
    # --- Check Logic: Real Status vs Config ---
    # User feedback: "don't use fake data" -> If it's configured correctly but NOT running, 
    # the summary should reflect that it is DOWN, not OK.
    
    any_service_down = False
    # Ensure we iterate over values() of the nested dict 'services'
    service_metrics = dashboard_data.get("services", {})
    if isinstance(service_metrics, dict):
        for srv_metrics in service_metrics.values():
            if not isinstance(srv_metrics, dict):
                continue
            state = srv_metrics.get("runtime_state", "").lower()
            # Consider 'running' or 'restarting' as somewhat active. 
            if state not in ["running", "restarting"]:
                 # Exception: dashboard-updater is a one-off loop in heavy load? No it should be running.
                 # Allow clean exits only if status says Exited (0)
                 status_text = srv_metrics.get("runtime_status", "")
                 if "Exited (0)" not in status_text: 
                     any_service_down = True

    if all_errors:
        dashboard_data["summary"] = "failed"
        print(f"{Colors.FAIL}{Colors.BOLD}[FAIL] Validation FAILED{Colors.ENDC}")
        for srv, errs in all_errors.items():
            print(f"\n{Colors.FAIL}Service '{srv}':{Colors.ENDC}")
            for e in errs:
                print(f"  - {e}")
    elif any_service_down:
        dashboard_data["summary"] = "degraded"
        print(f"{Colors.WARNING}{Colors.BOLD}[WARN] Configuration Valid, but Services are NOT RUNNING.{Colors.ENDC}")
    else:
        print(f"{Colors.OKGREEN}{Colors.BOLD}[OK] Validation PASSED! All agents look happy.{Colors.ENDC}")
    
    if export_json_path:
        try:
            with open(export_json_path, 'w') as f:
                json.dump(dashboard_data, f, indent=2)
            print(f"\n{Colors.OKBLUE}Dashboard data exported to {export_json_path}{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.FAIL}Failed to export JSON: {e}{Colors.ENDC}")

    if all_errors:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Validate docker-compose configuration')
    parser.add_argument('target', nargs='?', default=None,
                        help='Path to docker-compose.yml or JSON export path')
    parser.add_argument('--ci', action='store_true',
                        help='CI mode: skip runtime status checks')
    args = parser.parse_args()

    export_path = None
    if args.target and args.target.endswith('.json'):
        export_path = args.target

    validate_docker_compose(export_path, ci_mode=args.ci)
