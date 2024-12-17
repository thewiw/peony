#!/usr/bin/env python3

import os
import argparse
import secrets
import random
import string
import shutil
from datetime import datetime

try:
    from peony.docker_manager import DockerManager
    from peony.utils import (
        get_backup_path,
        get_caddy_path,
        load_template_with_update,
        read_settings,
        find_caddy_server,
    )
except (ImportError, ModuleNotFoundError):
    from docker_manager import DockerManager
    from utils import (
        get_backup_path,
        get_caddy_path,
        load_template_with_update,
        read_settings,
        find_caddy_server,
    )


def list_vpns(docker: DockerManager, caddy_name: str) -> None:
    vpns = []
    caddy_dir = get_caddy_path(caddy_name)
    vpn_select_path = os.path.join(caddy_dir, "static/vpn-select.html")

    with open(vpn_select_path, "r") as f:
        content = f.read()
        start = content.find("const vpns = [")
        end = content.find("];", start)
        vpns_str = content[start:end].replace("const vpns = [", "").strip()
        vpns = [v.strip(' "') for v in vpns_str.split(",") if v.strip()]

    if not vpns:
        print("No VPNs configured")
        return

    print("\n======= Configured VPNs =======")
    for vpn in vpns:
        container = docker.get_container(vpn)
        status = container.status.capitalize() if container else "Not found"
        port = docker.get_container_port(vpn) or "N/A"
        print(f"- {vpn} (Status: {status}, Port: {port})")


def _validate_vpn_settings(config: dict) -> None:
    is_wiw = os.path.exists("/opt/wiw")
    errors = []

    key_size = config.get("easyrsa_key_size")
    if key_size:
        if key_size not in ["1024", "2048", "4096"]:
            errors.append(
                f"Invalid easyrsa_key_size: {key_size} (should be 1024 not recommanded, 2048 or 4096"
            )
        elif key_size == "1024":
            print(
                "\n⚠️  Warning: Using 1024 bit keys is not recommended for security reasons"
            )

    if expire := config.get("easyrsa_ca_expire"):
        if not expire.isdigit() or int(expire) <= 0:
            errors.append(
                f"Invalid easyrsa_ca_expire: {expire} (should be a positive number)"
            )

    if expire := config.get("easyrsa_cert_expire"):
        if not expire.isdigit() or int(expire) <= 0:
            errors.append(
                f"Invalid easyrsa_cert_expire: {expire} (should be a positive number)"
            )

    if renew := config.get("easyrsa_cert_renew"):
        if not renew.isdigit() or int(expire) <= 0:
            errors.append(
                f"Invalid easyrsa_cert_renew: {renew} (should be a positive number)"
            )

    if days := config.get("easyrsa_crl_days"):
        if not days.isdigit() or int(expire) <= 0:
            errors.append(
                f"Invalid easyrsa_crl_days: {days} (should be a positive number)"
            )

    if country := config.get("easyrsa_req_country"):
        if not (len(country) == 2 and country.isalpha()):
            errors.append(
                f"Invalid easyrsa_req_country: {country} (should be 2 letters country code, e.g. FR)"
            )

    if email := config.get("easyrsa_req_email"):
        if "@" not in email or "." not in email.split("@")[1]:
            errors.append(f"Invalid easyrsa_req_email: {email}")

    if proto := config.get("openvpn_prot"):
        if proto.lower() not in ["udp", "tcp"]:
            errors.append(f"Invalid openvpn_prot: {proto} should be udp or tcp")

    for bool_setting in ["openvpn_gateway", "openvpn_dns"]:
        if value := config.get(bool_setting):
            if value.lower() not in ["true", "false"]:
                errors.append(
                    f"Invalid {bool_setting}: {value} should be a boolean (true or false)"
                )

    if not is_wiw:
        required_fields = [
            "easyrsa_key_size",
            "easyrsa_ca_expire",
            "easyrsa_cert_expire",
            "easyrsa_cert_renew",
            "easyrsa_crl_days",
            "easyrsa_req_country",
            "easyrsa_req_province",
            "easyrsa_req_city",
            "easyrsa_req_org",
            "easyrsa_req_email",
            "openvpn_prot",
        ]
        for field in required_fields:
            if not config.get(field):
                errors.append(f"Missing required field: {field}")

    if errors:
        raise ValueError("\n".join(errors))


def get_config_path(name: str = None) -> str:
    wiw_path = "/opt/wiw/config"
    vpn_path = "/opt/vpn/config"
    base_path = wiw_path if os.path.exists(wiw_path) else vpn_path
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    return os.path.join(base_path, name) if name else base_path


def _create_vpn_directories(output_dir: str) -> None:
    directories = ["config", "pki", "clients", "db", "staticclients", "log"]
    for dir in directories:
        os.makedirs(os.path.join(output_dir, dir), exist_ok=True)


def _generate_password() -> str:
    characts = string.ascii_letters + string.digits + "()!?,.;#{}[]_-+/*"
    return "".join(secrets.choice(characts) for _ in range(random.randint(27, 32)))


def calculate_subnets(name: str) -> dict:
    if any(c.isdigit() for c in name):
        vpn_num = int("".join(filter(str.isdigit, name)))
        subnet_num = vpn_num * 3 - 2
    else:
        used_subnets = {0}
        for net in os.popen("docker network ls --format '{{.Name}}'").read().split():
            if net.endswith("-net"):
                inspect = os.popen(f"docker network inspect {net}").read()
                if "Subnet" in inspect and "172.28." in inspect:
                    subnet = inspect.split("172.28.")[1].split(".")[0]
                    try:
                        used_subnets.add(int(subnet))
                    except ValueError:
                        continue
        subnet_num = 1
        while (
            subnet_num in used_subnets
            or subnet_num + 1 in used_subnets
            or subnet_num + 2 in used_subnets
        ):
            subnet_num += 3

    return {
        "docker_subnet": f"172.28.{subnet_num}.0/24",
        "trust_subnet": f"10.0.{subnet_num}.0",
        "guest_subnet": f"10.0.{subnet_num+1}.0",
        "home_subnet": f"10.0.{subnet_num+2}.0",
    }


def backup_vpn(docker: DockerManager, caddy_name: str, vpn_name: str) -> None:
    backup_dir = get_backup_path()
    vpn_path = get_config_path(vpn_name)

    if not os.path.exists(vpn_path):
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(
        backup_dir, f"{caddy_name}-{vpn_name}-{timestamp}-remove.tgz"
    )
    backup_cmd = (
        f"sudo tar czf {backup_file} -C / opt/docker/volumes/{caddy_name} {vpn_path}"
    )
    os.system(backup_cmd)


def _generate_vpn_context(
    docker: DockerManager,
    name: str,
    config: dict,
    output_dir: str,
    admin_password: str = None,
) -> dict:
    subnets = calculate_subnets(name)

    if not admin_password:
        current_port = docker.get_container_port(name)
        vpn_port = (
            current_port if current_port else docker.get_free_port(start_port=15000)
        )
    else:
        vpn_port = docker.get_free_port(start_port=15000)

    caddy_config = read_settings("caddy_settings")
    hostname = caddy_config.get("hostname")
    if not hostname:
        raise ValueError("HOSTNAME is mandatory in caddy_settings")

    return {
        "container_name": name,
        "container_name_ui": f"{name}-ui",
        "volume_path": output_dir,
        "vpn_port": vpn_port,
        "protocol": config.get("openvpn_prot", "udp"),
        "admin_password": admin_password,
        "hostname": hostname,
        **subnets,
        "EASYRSA_DN": "org",
        "EASYRSA_REQ_COUNTRY": config.get("easyrsa_req_country", "FR"),
        "EASYRSA_REQ_PROVINCE": config.get("easyrsa_req_province", "GE"),
        "EASYRSA_REQ_CITY": config.get("easyrsa_req_city", "Nancy"),
        "EASYRSA_REQ_ORG": config.get("easyrsa_req_org", "TheWiw"),
        "EASYRSA_REQ_EMAIL": config.get("easyrsa_req_email", "willy@thewiw.com"),
        "EASYRSA_REQ_OU": config.get("easyrsa_req_ou", ""),
        "EASYRSA_KEY_SIZE": config.get("easyrsa_key_size", "4096"),
        "EASYRSA_CA_EXPIRE": config.get("easyrsa_ca_expire", "10958"),
        "EASYRSA_CERT_EXPIRE": config.get("easyrsa_cert_expire", "5478"),
        "EASYRSA_CERT_RENEW": config.get("easyrsa_cert_renew", "365"),
        "EASYRSA_CRL_DAYS": config.get("easyrsa_crl_days", "730"),
        "openvpn_gateway_bool_comment": (
            "" if config.get("openvpn_gateway", "false").lower() == "true" else "#"
        ),
        "openvpn_dns_bool_comment": (
            "" if config.get("openvpn_dns", "false").lower() == "true" else "#"
        ),
    }


def _update_vpn_configs(output_dir: str, context: dict) -> None:
    templates = [
        ("server.conf", ""),
        ("client.conf", "config/"),
        ("easy-rsa.vars", "config/"),
        ("docker-compose.yml", ""),
    ]

    for template, subdir in templates:
        content = load_template_with_update(f"templates/vpns/{template}", context)
        target_dir = os.path.join(output_dir, subdir)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, template)
        with open(target_path, "w") as f:
            f.write(content)


def _update_caddy_config(
    docker: DockerManager,
    caddy_name: str,
    vpn_name: str,
    hostname: str,
    remove: bool = False,
) -> None:
    caddy_dir = get_caddy_path(caddy_name)
    vpn_select_path = os.path.join(caddy_dir, "static/vpn-select.html")
    caddyfile_path = os.path.join(caddy_dir, "Caddyfile")

    with open(vpn_select_path, "r") as f:
        content = f.read()

    start = content.find("const vpns = [")
    end = content.find("];", start)
    vpns_str = content[start:end].replace("const vpns = [", "").strip()
    vpns = [v.strip(' "') for v in vpns_str.split(",") if v.strip()]

    if remove and vpn_name in vpns:
        vpns.remove(vpn_name)
    elif not remove and vpn_name not in vpns:
        vpns.append(vpn_name)

    if vpns:
        new_vpns = f'const vpns = ["{"\", \"".join(vpns)}"];'
    else:
        new_vpns = "const vpns = [];"
    content = content[:start] + new_vpns + content[end + 2 :]

    with open(vpn_select_path, "w") as f:
        f.write(content)

    with open(caddyfile_path, "r") as f:
        caddy_content = f.read().strip()

    if not remove:
        if caddy_content.endswith("}"):
            caddy_content = caddy_content[:-1]

        vpn_config = f"""
    @has{vpn_name}Cookie {{
        header Cookie *use_vpn={vpn_name}*
    }}
    handle @has{vpn_name}Cookie {{
        reverse_proxy {vpn_name}-ui:8080 {{
            header_up X-Forwarded-Host "{hostname}"
            header_up X-Forwarded-Proto "https"
            header_down Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"
            header_down Pragma "no-cache"
            header_down Expires "0"
            header_down X-Backend-Server "{vpn_name}-backend"
        }}
    }}
}}"""
        caddy_content += vpn_config
    else:
        lines = caddy_content.split("\n")
        new_lines = []
        brace_count = 0
        skip = False

        for line in lines:
            if f"@has{vpn_name}Cookie" in line:
                skip = True
                continue

            if skip:
                if "{" in line:
                    brace_count += 1
                if "}" in line:
                    brace_count -= 1
                    if brace_count < 0:
                        skip = False
                        brace_count = 0
                continue

            new_lines.append(line)

        caddy_content = "\n".join(new_lines).strip()
        if not caddy_content.endswith("}"):
            caddy_content += "\n}"

    with open(caddyfile_path, "w") as f:
        f.write(caddy_content)


def create_vpn(docker: DockerManager, name: str, caddy_name: str, config: dict) -> str:
    caddy_dir = get_caddy_path(caddy_name)
    if not os.path.exists(caddy_dir):
        raise Exception(f"Caddy server {caddy_name} not found")

    output_dir = get_config_path(name)
    if os.path.exists(output_dir):
        raise Exception(f"VPN directory {output_dir} already exists")

    try:
        os.system(
            f"git clone https://github.com/d3vilh/openvpn-server.git {output_dir}"
        )
        git_dir = os.path.join(output_dir, ".git")
        github_dir = os.path.join(output_dir, ".github")

        if os.path.exists(git_dir):
            shutil.rmtree(git_dir)

        if os.path.exists(github_dir):
            shutil.rmtree(github_dir)
        _create_vpn_directories(output_dir)

        admin_password = _generate_password()
        context = _generate_vpn_context(
            docker, name, config, output_dir, admin_password
        )

        os.system(f"docker network rm {name}-net 2>/dev/null")
        docker.create_network(name=f"{name}-net", subnet=context["docker_subnet"])

        if os.system("docker network inspect vpn-proxy >/dev/null 2>&1") != 0:
            raise Exception("vpn-proxy network not found. Create Caddy first.")

        _update_vpn_configs(output_dir, context)
        _update_caddy_config(docker, caddy_name, name, context["hostname"])

        container = docker.get_container(caddy_name)
        if container:
            container.restart()

        docker.start_compose(os.path.join(output_dir, "docker-compose.yml"))
        print("\nInitializing VPN server (this might take few minutes)...")
        print("============================")

        log_cmd = f"docker logs -f {name} & while ! docker logs {name} 2>&1 | grep -q 'Start openvpn process'; do sleep 1; done && kill $!"
        os.system(log_cmd)

        print("\n✓ VPN server initialized successfully!")

        return admin_password

    except Exception as e:
        if os.path.exists(output_dir):
            os.system(f"sudo rm -rf {output_dir}")
        try:
            os.system(f"docker network rm {name}-net")
        except:
            pass
        raise e


def update_vpn(docker: DockerManager, name: str, caddy_name: str, config: dict) -> None:
    output_dir = get_config_path(name)
    if not os.path.exists(output_dir):
        raise Exception(f"VPN {name} not found")

    try:
        backup_vpn(docker, caddy_name, name)
        docker_compose_path = os.path.join(output_dir, "docker-compose.yml")
        with open(docker_compose_path) as f:
            for line in f:
                if "OPENVPN_ADMIN_PASSWORD=" in line:
                    admin_password = line.split("=")[1].strip()
                    break
        context = _generate_vpn_context(
            docker, name, config, output_dir, admin_password
        )
        _update_vpn_configs(output_dir, context)

        docker.stop_container(name)
        docker.stop_container(f"{name}-ui")

        _update_caddy_config(docker, caddy_name, name, "", remove=True)
        _update_caddy_config(docker, caddy_name, name, context["hostname"])

        docker.start_compose(os.path.join(output_dir, "docker-compose.yml"))
        caddy = docker.get_container(caddy_name)
        if caddy:
            caddy.restart()

        print(f"Successfully updated VPN {name}")

    except Exception as e:
        print(f"Error updating VPN {name}: {str(e)}")
        raise e


def remove_vpn(docker: DockerManager, name: str, caddy_name: str) -> None:
    vpn_path = get_config_path(name)
    container = docker.get_container(name)

    print("\nRemoving VPN server (this might take few minutes)...")

    if not os.path.exists(vpn_path) and not container:
        print(f"No VPN configuration found in {vpn_path}")
        raise Exception(f"VPN {name} does not exist. Nothing to remove.")

    try:
        if os.path.exists(vpn_path):
            backup_vpn(docker, caddy_name, name)

        for container_name in [name, f"{name}-ui"]:
            docker.remove_container(container_name)

        _update_caddy_config(docker, caddy_name, name, "", remove=True)
        caddy = docker.get_container(caddy_name)
        if caddy:
            caddy.restart()

        try:
            network = docker.client.networks.get(f"{name}-net")
            network.remove()
        except docker.errors.NotFound:
            print(f"Network {name}-net already removed")

        if os.path.exists(vpn_path):
            os.system(f"sudo rm -rf {vpn_path}")

    except Exception as e:
        raise Exception(f"Failed to remove VPN {name}: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="Manage OpenVPN servers")
    parser.add_argument("action", choices=["create", "update", "remove", "list"])
    parser.add_argument("name", help="VPN name", nargs="?")
    parser.add_argument("--caddy", help="Caddy container name")
    args = parser.parse_args()

    try:
        docker = DockerManager()
        caddy_name = args.caddy or find_caddy_server()

        if not caddy_name:
            raise Exception(
                "No Caddy server found. Create one first with vpns-caddy.py"
            )

        if args.action == "list":
            list_vpns(docker, caddy_name)
            return

        if not args.name:
            raise ValueError("VPN name is required for create/update/remove actions")

        vpn_path = get_config_path(args.name)

        config = read_settings(
            "vpn_settings",
            {"openvpn_prot": "udp", "openvpn_gateway": "false", "openvpn_dns": "false"},
        )

        _validate_vpn_settings(config)

        if args.action == "create":
            admin_password = create_vpn(docker, args.name, caddy_name, config)
            vpn_port = docker.get_container_port(args.name)
            subnets = calculate_subnets(args.name)
            caddy_config = read_settings("caddy_settings")

            print("\n======= VPN Summary =======")
            print(f"VPN Name: {args.name}")
            print("\n=== UI Credentials ===")
            print(f"Username: admin")
            print(f"Password: {admin_password}")
            print("\n⚠️ Please store this password in a secure location.\n")
            print(
                f"VPN Select page: https://{caddy_config['hostname']}/vpn-select.html"
            )
            print("\n=== Network Details ===")
            print(f"VPN IP Range: {subnets['trust_subnet']}/24")
            print(f"Docker UI Network: {subnets['docker_subnet']}")
            print(f"Host: {caddy_config['hostname']} (Port: {vpn_port})")
            print("\n============================")
        elif args.action == "update":
            update_vpn(docker, args.name, caddy_name, config)
            print(f"Updated VPN {args.name} in {vpn_path}")
        else:
            remove_vpn(docker, args.name, caddy_name)
            print(f"\n✓Removed VPN {args.name} from {vpn_path} !")

    except Exception as err:
        print(f"Error: {err}")
        exit(1)


if __name__ == "__main__":
    main()
