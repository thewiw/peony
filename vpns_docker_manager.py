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
        
    def check_for_vpns(self, caddy_name: str) -> tuple[bool, list]:
        vpns = set()
        for container in self.client.containers.list(all=True):
            name = container.name
            if name.endswith("-ui") and name != f"{caddy_name}-ui":
                vpns.add(name[:-3])
        return bool(vpns), sorted(list(vpns))

