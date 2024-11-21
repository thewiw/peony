#!/usr/bin/env python3

import os
import argparse
import secrets
import string
from datetime import datetime
from vpns_docker_manager import DockerManager
from vpns_utils import (
    get_backup_path,
    get_caddy_path,
    load_template_with_update,
    read_settings,
    find_caddy_server,
)

def get_config_path(name: str = None) -> str:
    wiw_path = "/opt/wiw/config"
    vpn_path = "/opt/vpn/config"
    base_path = wiw_path if os.path.exists(wiw_path) else vpn_path
    if not os.path.exists(base_path):
        os.system(f"sudo mkdir -p {base_path}")
        os.system(f"sudo chown -R $USER:$USER {os.path.dirname(base_path)}")

    return os.path.join(base_path, name) if name else base_path


def _create_vpn_directories(output_dir: str) -> None:
    directories = ["config", "pki", "clients", "db", "staticclients", "log"]
    for dir in directories:
        os.makedirs(os.path.join(output_dir, dir), exist_ok=True)


def _generate_password() -> str:
    characts = string.ascii_letters + string.digits + "@#$%"
    return "".join(secrets.choice(characts) for _ in range(12))


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
        while subnet_num in used_subnets or subnet_num+1 in used_subnets or subnet_num+2 in used_subnets:
            subnet_num += 3

    return {
        "docker_subnet": f"172.28.{subnet_num}.0/24",
        "trust_subnet": f"10.0.{subnet_num}.0",
        "guest_subnet": f"10.0.{subnet_num+1}.0",
        "home_subnet": f"10.0.{subnet_num+2}.0",
    }

def backup_vpn(docker: DockerManager, caddy_name: str, vpn_name: str) -> None:
    backup_dir = get_backup_path()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_file = os.path.join(
        backup_dir, f"{caddy_name}-{vpn_name}-{timestamp}-remove.tgz"
    )

    backup_cmd = f"sudo tar czf {backup_file} -C / opt/docker/volumes/{caddy_name} opt/vpn/config/{vpn_name}"
    os.system(backup_cmd)


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

    # Mise à jour Caddyfile
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
        # os.system(f"sudo chown -R $USER:$USER {output_dir}")
        _create_vpn_directories(output_dir)

        subnets = calculate_subnets(name)
        vpn_port = docker.get_free_port()
        admin_password = _generate_password()

        context = {
            "container_name": name,
            "container_name_ui": f"{name}-ui",
            "volume_path": output_dir,
            "vpn_port": vpn_port,
            "protocol": config.get("openvpn_prot", "udp"),
            "admin_password": admin_password,
            "hostname": config["caddy_hostname"],
            **subnets,
            "EASYRSA_DN": config.get("EASYRSA_DN", "org"),
            "EASYRSA_REQ_COUNTRY": config.get("easyrsa_req_country", "FR"),
            "EASYRSA_REQ_PROVINCE": config.get("easyrsa_req_province", "GE"),
            "EASYRSA_REQ_CITY": config.get("easyrsa_req_city", "Nancy"),
            "EASYRSA_REQ_ORG": config.get("easyrsa_req_org", "TheWiw"),
            "EASYRSA_REQ_EMAIL": config.get("easyrsa_req_email", "willy@thewiw.com"),
        }

        os.system(f"docker network rm {name}-net 2>/dev/null")
        docker.create_network(name=f"{name}-net", subnet=subnets["docker_subnet"])

        if os.system("docker network inspect vpn-proxy >/dev/null 2>&1") != 0:
            raise Exception("vpn-proxy network not found. Create Caddy first.")

        templates = [
            ("docker-compose.yaml", ""),
            ("server.conf", ""),
            ("client.conf", "config/"),
            ("easy-rsa.vars", "config/"),
        ]

        for template, subdir in templates:
            content = load_template_with_update(f"templates/vpns/{template}", context)
            target_dir = os.path.join(output_dir, subdir)
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, template)
            with open(target_path, "w") as f:
                f.write(content)

        _update_caddy_config(docker, caddy_name, name, config["caddy_hostname"])

        container = docker.get_container(caddy_name)
        if container:
            container.restart()

        docker.start_compose(os.path.join(output_dir, "docker-compose.yaml"))

        return admin_password

    except Exception as e:
        if os.path.exists(output_dir):
            os.system(f"sudo rm -rf {output_dir}")
        try:
            os.system(f"docker network rm {name}-net")
        except:
            pass
        raise e


def remove_vpn(docker: DockerManager, name: str, caddy_name: str) -> None:
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

    config_path = get_config_path(name)
    if os.path.exists(config_path):
        os.system(f"sudo rm -rf {config_path}")


def main():
    parser = argparse.ArgumentParser(description="Manage OpenVPN servers")
    parser.add_argument("action", choices=["create", "remove"])
    parser.add_argument("name", help="VPN name")
    parser.add_argument("--caddy", help="Caddy container name")
    args = parser.parse_args()

    try:
        docker = DockerManager()
        caddy_name = args.caddy or find_caddy_server()
        if not caddy_name:
            raise Exception(
                "No Caddy server found. Create one first with vpns-caddy.py"
            )

        config = read_settings("vpn_settings", {"openvpn_prot": "udp"})

        if not config.get("caddy_hostname"):
            raise ValueError("CADDY_HOSTNAME is mandatory in vpn_settings")

        if args.action == "create":
            admin_password = create_vpn(docker, args.name, caddy_name, config)
            print(f"Created VPN {args.name}")
            print(f"UI Admin credentials:")
            print(f"Username: admin")
            print(f"Password: {admin_password}")
            print(
                f"Access the VPN Select page at https://{config['caddy_hostname']}/vpn-select.html"
            )
        else:
            remove_vpn(docker, args.name, caddy_name)
            print(f"Removed VPN {args.name}")

    except Exception as err:
        print(f"Error: {err}")
        exit(1)


if __name__ == "__main__":
    main()
