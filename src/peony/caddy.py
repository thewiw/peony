#!/usr/bin/env python3
import os
import argparse
from datetime import datetime
try:
    from peony.docker_manager import DockerManager
    from peony.utils import (
        get_caddy_path, 
        load_template_with_update, 
        read_settings, 
        get_backup_path, 
        init_config
    )
except (ImportError, ModuleNotFoundError):
    from docker_manager import DockerManager
    from utils import (
        get_caddy_path, 
        load_template_with_update, 
        read_settings, 
        get_backup_path, 
        init_config
    )


def backup_caddy(docker: DockerManager, name: str) -> None:
    backup_dir = get_backup_path()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"{name}-{timestamp}-remove.tgz")

    backup_cmd = f"sudo tar czf {backup_file} -C / opt/docker/volumes/{name}"
    os.system(backup_cmd)


# def update_hosts_file(hostname: str) -> None:
#     with open('/etc/hosts', 'r') as f:
#         content = f.read()
#         if hostname not in content:
#             os.system(f'sudo sh -c \'echo "127.0.0.1 {hostname}" >> /etc/hosts\'')


def check_for_vpns(docker: DockerManager, caddy_name: str) -> tuple[bool, list]:
    vpns = set()
    for container in docker.client.containers.list(all=True):
        name = container.name
        if name.endswith("-ui") and name != f"{caddy_name}-ui":
            vpns.add(name[:-3])
    return bool(vpns), sorted(list(vpns))


def create_directory(output_dir: str) -> None:
    os.makedirs(os.path.join(output_dir, "static"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "config"), exist_ok=True)


def generate_caddy_templates(
    docker: DockerManager, output_dir: str, name: str, config: dict
) -> None:
    context = {
        "hostname": config["hostname"],
        "container_name": name,
        "network": "vpn-proxy",
    }

    templates = [
        ("Caddyfile", ""),
        ("docker-compose.yaml", ""),
        ("vpn-select.html", "static/"),
    ]

    for template, subdir in templates:
        content = load_template_with_update(
            f"templates/caddy/{template}", context
        )
        with open(os.path.join(output_dir, subdir, template), "w") as f:
            f.write(content)


def create_caddy(docker: DockerManager, name: str, config: dict) -> None:
    output_dir = get_caddy_path(name)
    if os.path.exists(output_dir):
        raise Exception(f"Directory {output_dir} already exist")
    try:
        # update_hosts_file(config["hostname"])
        create_directory(output_dir)
        generate_caddy_templates(docker, output_dir, name, config)
        docker.start_compose(os.path.join(output_dir, "docker-compose.yaml"))
    except Exception as e:
        if os.path.exists(output_dir):
            os.system(f"rm -rf {output_dir}")
        raise e


def remove_caddy(docker: DockerManager, name: str) -> None:
    output_dir = get_caddy_path(name)
    if not os.path.exists(output_dir):
        raise Exception(f"Caddy directory {output_dir} not found")

    has_vpns, vpns = check_for_vpns(docker, name)
    if has_vpns:
        raise Exception(
            f"Cannot remove Caddy while VPNs exist.\nActive VPNs container: {', '.join(vpns)}"
        )

    backup_caddy(docker, name)
    docker.remove_container(name)
    os.system(f"sudo rm -rf {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Manage Caddy server for OpenVPN")
    parser.add_argument("action", choices=["create", "remove", 'init'])
    parser.add_argument(
        "name", nargs="?", default="caddy", help="Name for the Caddy container"
    )
    args = parser.parse_args()

    try:
        if args.action == "init":
            init_config()
            print("Configuration files created in ~/.config/peony/ ready to be edited")
            return
        docker = DockerManager()
        
        if args.action == "create":
            config = read_settings("caddy_settings", {"hostname": None})
            if not config.get("hostname"):
                raise ValueError("HOSTNAME is mandatory in caddy_settings")
            create_caddy(docker, args.name, config)
            print(f"Created Caddy server {args.name}")
            print(
                f"\nAccess the VPN Select page at https://{config['hostname']}/vpn-select.html"
            )
        else:
            remove_caddy(docker, args.name)
            print(f"✓Removed Caddy server {args.name}")
            print()

    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
