import os
import docker
from typing import Dict, Set, Optional, Tuple
from docker.errors import NotFound


class DockerManager:
    def __init__(self):
        self.client = docker.from_env()

    def get_container(self, name: str) -> Optional[docker.models.containers.Container]:
        try:
            return self.client.containers.get(name)
        except NotFound:
            return None

    def create_network(self, name: str, subnet: str) -> docker.models.networks.Network:
        try:
            return self.client.networks.create(
                name=name, driver="bridge", ipam={"Config": [{"Subnet": subnet}]}
            )
        except docker.errors.APIError as e:
            raise Exception(f"Failed to create network: {e}")

    def remove_container(self, name: str) -> None:
        container = self.get_container(name)
        if container:
            container.stop(timeout=10)
            container.remove(force=True)

    def get_used_ports(self) -> Set[int]:
        used_ports = set()
        for container in self.client.containers.list(all=True):
            ports = container.attrs["HostConfig"].get("PortBindings", {})
            for mappings in ports.values():
                if mappings:
                    used_ports.update(
                        int(m["HostPort"]) for m in mappings if "HostPort" in m
                    )
        return used_ports

    def get_free_port(self, start_port: int = 1194) -> int:
        used_ports = self.get_used_ports()
        port = start_port
        while port in used_ports:
            port += 1
        return port

    def start_compose(self, compose_file: str) -> None:
        if os.system(f"docker compose -f {compose_file} up -d") != 0:
            raise Exception("Failed to start docker-compose")

    def read_settings(self, file_path: str, defaults: dict = None) -> dict:
        settings = defaults or {}
        try:
            with open(file_path) as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        settings[key.strip().lower()] = value.strip()
            return settings
        except FileNotFoundError:
            raise Exception(f"Settings file {file_path} not found")

    def load_template_with_update(self, template_path: str, context: dict) -> str:
        try:
            with open(template_path) as f:
                content = f.read()
                for key, value in context.items():
                    content = content.replace(f"${{{key}}}", str(value))
            return content
        except FileNotFoundError:
            raise Exception(f"Template {template_path} not found")

    def get_backup_path(self) -> str:
        wiw_path = "/opt/wiw/backup"
        vpn_path = "/opt/vpn/backup"
        base_path = wiw_path if os.path.exists(wiw_path) else vpn_path
        if not os.path.exists(base_path):
            os.system(f"sudo mkdir -p {base_path}")
            os.system(f"sudo chown -R $USER:$USER {os.path.dirname(base_path)}")
        return base_path
