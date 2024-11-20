#!/usr/bin/env python3

import os
import argparse
from datetime import datetime
from vpns_docker_manager import DockerManager


def backup_all(
    docker: DockerManager, caddy_name: str, backup_dir: str = None, filename: str = None) -> None:
    if not backup_dir:
        backup_dir = docker.get_backup_path()
    else:
        if not os.path.exists(backup_dir):
            os.system(f"sudo mkdir -p {backup_dir}")
            os.system(f"sudo chown -R $USER:$USER {os.path.dirname(backup_dir)}")

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{caddy_name}-{timestamp}.tgz"

    backup_file = os.path.join(backup_dir, filename)

    has_vpns, vpns = check_for_vpns(docker, caddy_name)

    backup_cmd = f"sudo tar czf {backup_file} -C / opt/docker/volumes/{caddy_name}"

    if has_vpns:
        for vpn in vpns:
            backup_cmd += f" opt/vpn/config/{vpn}"

    os.system(backup_cmd)
    print(f"Backup created: {backup_file}")
    if has_vpns:
        print(f"VPNs included in backup: {', '.join(vpns)}")


def check_for_vpns(docker: DockerManager, caddy_name: str) -> tuple[bool, list]:
    vpns = set()

    for container in docker.client.containers.list(all=True):
        name = container.name
        if name.endswith("-ui") and name != f"{caddy_name}-ui":
            vpns.add(name[:-3])

    return bool(vpns), sorted(list(vpns))


def main():
    parser = argparse.ArgumentParser(description="Backup Caddy and VPN(s) config")
    parser.add_argument("--dest", help="Dest directory for backup")
    parser.add_argument("--file", help="Backup file name")
    parser.add_argument("--caddy", default="caddy", help="Caddy container name")
    args = parser.parse_args()

    try:
        docker = DockerManager()
        caddy_dir = f"/opt/docker/volumes/{args.caddy}"
        if not os.path.exists(caddy_dir):
            raise Exception(f"Caddy server directory {caddy_dir} not found")
        backup_all(docker, args.caddy, args.dest, args.file)
        print("Backup completed !")

    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
