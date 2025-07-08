"""
Virtualization command for CAI cli.
This module provides commands for setting up and managing Docker virtualization
environments.
"""
import os
import json
import subprocess
import datetime
import time
from typing import List, Optional, Dict, Any, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
import rich.box

from cai.repl.commands.base import Command, register_command

console = Console()

# Default Docker images for CAI
DEFAULT_IMAGES = {
    "kalilinux/kali-rolling": {
        "image": "kalilinux/kali-rolling",
        "description": "Official Kali Linux distribution for penetration testing and security audits",
        "category": "Offensive Pentesting",
        "id": "pen1"
    },
    "parrotsec/security": {
        "image": "parrotsec/security",
        "description": "Official Parrot Security OS image, popular for penetration testing and forensic analysis",
        "category": "Offensive Pentesting",
        "id": "pen2"
    },
}

# --- Helper function for image name normalization ---
def normalize_image_name(image_name: str) -> str:
    """
    Ensure the image name always includes a tag (default to ':latest' if missing).
    Args:
        image_name: The Docker image name, possibly without a tag.
    Returns:
        The image name with a tag (':latest' if not specified).
    """
    if not image_name:
        return image_name
    if ":" not in image_name:
        return f"{image_name}:latest"
    return image_name


class DockerManager:
    """Manager for Docker operations."""

    @staticmethod
    def is_docker_installed() -> bool:
        """Check if Docker is installed.

        Returns:
            bool: True if Docker is installed, False otherwise
        """
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    @staticmethod
    def is_docker_running() -> bool:
        """Check if Docker daemon is running.

        Returns:
            bool: True if Docker daemon is running, False otherwise
        """
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    @staticmethod
    def get_container_list() -> List[Dict[str, Any]]:
        """Get a list of running Docker containers.

        Returns:
            List[Dict[str, Any]]: List of container information dictionaries
        """
        try:
            result = subprocess.run(
                [
                    "docker", "ps", "--all",
                    "--format", "{{json .}}"
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        containers.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            
            return containers
        except (subprocess.SubprocessError, FileNotFoundError):
            return []

    @staticmethod
    def get_images_list() -> List[Dict[str, Any]]:
        """Get a list of Docker images.

        Returns:
            List[Dict[str, Any]]: List of image information dictionaries
        """
        try:
            result = subprocess.run(
                [
                    "docker", "images",
                    "--format", "{{json .}}"
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            images = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        images.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            
            return images
        except (subprocess.SubprocessError, FileNotFoundError):
            return []

    @staticmethod
    def pull_image(image_name: str) -> Tuple[bool, str]:
        """Pull a Docker image.

        Args:
            image_name: Name of the image to pull

        Returns:
            Tuple[bool, str]: Success status and output message
        """
        try:
            # Use Popen to stream pull progress line by line.
            pull_proc = subprocess.Popen(
                ["docker", "pull", image_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Stream output in real time to the console.
            if pull_proc.stdout is not None:
                for line in pull_proc.stdout:
                    console.print(line.rstrip())

            pull_proc.wait()

            if pull_proc.returncode == 0:
                return True, (
                    f"Successfully pulled image: {image_name}"
                )
            return False, (
                f"Failed to pull image: {image_name} "
                f"(code {pull_proc.returncode})"
            )
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            return False, f"Error pulling image: {str(e)}"

    @staticmethod
    def run_container(
        image_name: str,
        container_name: str = None
    ) -> Tuple[bool, str]:
        """Run a Docker container.

        Args:
            image_name: Name of the image to run
            container_name: Optional name for the container

        Returns:
            Tuple[bool, str]: Success status and output message
        """
        try:
            # Normalize image name for all comparisons
            normalized_image_name = normalize_image_name(image_name)
            # Get the workspace directory for mounting
            workspace_dir = os.getenv("CAI_WORKSPACE_DIR", os.getcwd())
            if not os.path.exists(workspace_dir):
                workspace_dir = os.path.expanduser("~")
            
            # On macOS and Windows, Docker has specific mounting requirements
            # Convert to absolute path to ensure proper mounting
            workspace_dir = os.path.abspath(workspace_dir)
            
            # Identify problematic images that need special handling
            problematic_images = {
                # Image name: [needs_entrypoint_override, no_mount]
                "parrotsec/security": [True, True],
                "remnux/remnux-distro": [True, True],
                "lauriewired/linux-malware-analysis-container": [True, True]
            }
            
            # Get flags for this image
            image_flags = problematic_images.get(image_name, [False, False])
            needs_entrypoint_override = image_flags[0]
            no_mount = image_flags[1]
            
            # Start command
            cmd = ["docker", "run", "-d"]
            
            # Override entrypoint for problematic images
            if needs_entrypoint_override:
                cmd.extend(["--entrypoint", "/bin/bash"])
            
            # Add container name if provided
            if container_name:
                cmd.extend(["--name", container_name])
            
            # IMPORTANT: Always use host networking for all containers
            # This ensures that the container has the same network connectivity as the host
            cmd.extend(["--network=host"])
            
            # Mount the workspace directory to /workspace in the container
            # Use current directory if all else fails
            target_mount = "/workspace"
            try_mount = not no_mount
            
            if try_mount:
                cmd.extend([
                    "-v", f"{workspace_dir}:{target_mount}",
                    "--workdir", target_mount
                ])
            
            # Add specific flags based on container type
            if image_name == "kalilinux/kali-rolling":
                # For Kali, add additional flags for security tools
                cmd.extend([
                    "--cap-add=NET_ADMIN",  # Allow network admin capabilities
                ])
            elif image_name == "cai-container":
                # For CAI container, add any specific flags needed
                # Like extra volume mounts or environment variables
                home_dir = os.path.expanduser("~")
                if os.path.exists(home_dir):
                    cmd.extend([
                        "-v", f"{home_dir}/.ssh:/root/.ssh:ro",  # Mount ssh keys as read-only
                        "-e", "DISPLAY=host.docker.internal:0"   # X11 forwarding
                    ])
            
            # For all containers, add these capabilities and privileges
            cmd.extend([
                "--cap-add=NET_ADMIN",       # Network administration (for nmap, etc.)
                "--cap-add=NET_RAW",         # Raw network access (for packet capture)
                "--security-opt=seccomp=unconfined"  # Disable seccomp for better tool compatibility
            ])
            
            # Add the image name
            cmd.append(image_name)
            
            # Add command to keep container running
            # For containers with override entrypoint, we use -c "command"
            if needs_entrypoint_override:
                cmd.extend(["-c", "tail -f /dev/null"])
            else:
                cmd.extend(["tail", "-f", "/dev/null"])
            
            # Print the command for debugging
            console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if process.returncode == 0:
                container_id = process.stdout.strip()
                
                # Verify the container is actually running
                time.sleep(0.5)  # Brief pause to give it time to fully start
                verify_cmd = ["docker", "ps", "--filter", f"id={container_id}", "--format", "{{.ID}}"]
                verify_result = subprocess.run(
                    verify_cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if not verify_result.stdout.strip():
                    return False, f"Container created but exited immediately. Check image compatibility."
                
                return True, (
                    f"Successfully started container with ID: {container_id}"
                )
            else:
                error_msg = process.stderr
                
                # If mount fails, try again without mounts
                if "Mounts denied" in error_msg or try_mount:
                    console.print(
                        f"[yellow]Mount failed. Trying without workspace mount...[/yellow]"
                    )
                    # Remove any mount-related options
                    new_cmd = ["docker", "run", "-d"]
                    
                    # Override entrypoint for problematic images
                    if needs_entrypoint_override:
                        new_cmd.extend(["--entrypoint", "/bin/bash"])
                    
                    # Add container name if provided
                    if container_name:
                        new_cmd.extend(["--name", container_name])
                    
                    # IMPORTANT: Always use host networking
                    new_cmd.extend(["--network=host"])
                    
                    # For all containers, add these capabilities and privileges
                    new_cmd.extend([
                        "--cap-add=NET_ADMIN",
                        "--cap-add=NET_RAW",
                        "--security-opt=seccomp=unconfined"
                    ])
                    
                    # Add the image name
                    new_cmd.append(image_name)
                    
                    # Add command to keep container running
                    if needs_entrypoint_override:
                        new_cmd.extend(["-c", "tail -f /dev/null"])
                    else:
                        new_cmd.extend(["tail", "-f", "/dev/null"])
                    
                    console.print(f"[dim]Retry: {' '.join(new_cmd)}[/dim]")
                    
                    # Try again
                    retry_process = subprocess.run(
                        new_cmd,
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if retry_process.returncode == 0:
                        container_id = retry_process.stdout.strip()
                        
                        # Verify the container is actually running
                        time.sleep(0.5)
                        verify_cmd = ["docker", "ps", "--filter", f"id={container_id}", "--format", "{{.ID}}"]
                        verify_result = subprocess.run(
                            verify_cmd,
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        if not verify_result.stdout.strip():
                            return False, f"Container created but exited immediately despite retry."
                        
                        return True, (
                            f"Successfully started container with ID: {container_id} "
                            f"(without workspace mount)"
                        )
                    else:
                        error_msg = retry_process.stderr
                
                # --- Robust handling for 'already exists' error ---
                if "already exists" in error_msg and container_name:
                    # Find the container by name
                    for container in DockerManager.get_container_list():
                        # Docker prepends '/' to container names in 'Names' field
                        if container.get("Names", "") == f"/{container_name}":
                            # Normalize both image names for comparison
                            container_image = normalize_image_name(container.get("Image", ""))
                            if container_image == normalized_image_name:
                                container_id = container.get("ID", "")
                                container_status = container.get("Status", "").lower()
                                # If running, just reuse it
                                if "up" in container_status:
                                    return True, (
                                        f"Successfully started existing container: {container_id}"
                                    )
                                # If stopped, start it
                                elif "exited" in container_status or "created" in container_status:
                                    start_cmd = ["docker", "start", container_id]
                                    start_process = subprocess.run(
                                        start_cmd,
                                        capture_output=True,
                                        text=True,
                                        check=False
                                    )
                                    if start_process.returncode == 0:
                                        return True, (
                                            f"Successfully started existing container: {container_id}"
                                        )
                                    else:
                                        # If start fails, try to remove and recreate
                                        subprocess.run(
                                            ["docker", "rm", "-f", container_id],
                                            capture_output=True,
                                            text=True,
                                            check=False
                                        )
                                        # Try again with a new name
                                        new_name = f"{container_name}-new"
                                        return DockerManager.run_container(image_name, new_name)
                            else:
                                # If the image does not match, remove and recreate
                                subprocess.run(
                                    ["docker", "rm", "-f", container.get("ID", "")],
                                    capture_output=True,
                                    text=True,
                                    check=False
                                )
                                # Try again with the same name
                                return DockerManager.run_container(image_name, container_name)
                # If still fails, check for common issues
                if "already exists" in error_msg and container_name:
                    # Container with this name already exists
                    # Try to find its ID and use it if its image matches
                    for container in DockerManager.get_container_list():
                        if container.get("Names", "") == f"/{container_name}":
                            if container.get("Image", "") == image_name:
                                container_id = container.get("ID", "")
                                
                                # Start it if needed
                                start_cmd = ["docker", "start", container_id]
                                start_process = subprocess.run(
                                    start_cmd,
                                    capture_output=True,
                                    text=True,
                                    check=False
                                )
                                
                                if start_process.returncode == 0:
                                    # Verify it's actually running
                                    time.sleep(0.5)
                                    verify_cmd = ["docker", "ps", "--filter", f"id={container_id}", "--format", "{{.ID}}"]
                                    verify_result = subprocess.run(
                                        verify_cmd,
                                        capture_output=True,
                                        text=True,
                                        check=False
                                    )
                                    
                                    if not verify_result.stdout.strip():
                                        # If it's not running, try to commit it to a new image and create a fixed container
                                        console.print(
                                            f"[yellow]Container exits immediately. "
                                            f"Attempting to create fixed version...[/yellow]"
                                        )
                                        
                                        # First, start the container in detached mode (it may exit immediately)
                                        subprocess.run(
                                            ["docker", "start", container_id],
                                            capture_output=True,
                                            text=True,
                                            check=False
                                        )
                                        
                                        # Try to commit the container to a new image
                                        fixed_image = f"fixed-{image_name.replace('/', '-')}"
                                        commit_result = subprocess.run(
                                            ["docker", "commit", container_id, fixed_image],
                                            capture_output=True,
                                            text=True,
                                            check=False
                                        )
                                        
                                        if commit_result.returncode == 0:
                                            # Remove the old container
                                            subprocess.run(
                                                ["docker", "rm", "-f", container_id],
                                                capture_output=True,
                                                text=True,
                                                check=False
                                            )
                                            
                                            # Create a new container with the fixed image
                                            fixed_cmd = [
                                                "docker", "run", "-d",
                                                "--entrypoint", "/bin/bash",
                                                "--name", f"{container_name}-fixed",
                                                "--network=host",
                                                "--cap-add=NET_ADMIN",
                                                "--cap-add=NET_RAW",
                                                "--security-opt=seccomp=unconfined",
                                                fixed_image,
                                                "-c", "tail -f /dev/null"
                                            ]
                                            
                                            fixed_result = subprocess.run(
                                                fixed_cmd,
                                                capture_output=True,
                                                text=True,
                                                check=False
                                            )
                                            
                                            if fixed_result.returncode == 0:
                                                return True, (
                                                    f"Successfully started fixed container: {fixed_result.stdout.strip()}"
                                                )
                                    else:
                                        # Container is running
                                        return True, (
                                            f"Successfully started existing container: {container_id}"
                                        )
                                else:
                                    # If start fails, try with entrypoint override
                                    if needs_entrypoint_override:
                                        # Remove the existing container and create a new one
                                        console.print(
                                            f"[yellow]Cannot start container. Removing and creating a new one with fixed entrypoint.[/yellow]"
                                        )
                                        
                                        # Remove the old container
                                        subprocess.run(
                                            ["docker", "rm", "-f", container_id],
                                            capture_output=True,
                                            text=True,
                                            check=False
                                        )
                                        
                                        # Create new name to avoid conflicts
                                        new_name = f"{container_name}-fixed"
                                        
                                        # Create a new container with fixed entrypoint
                                        fixed_cmd = [
                                            "docker", "run", "-d",
                                            "--entrypoint", "/bin/bash",
                                            "--name", new_name,
                                            "--network=host",
                                            "--cap-add=NET_ADMIN",
                                            "--cap-add=NET_RAW",
                                            "--security-opt=seccomp=unconfined",
                                            image_name,
                                            "-c", "tail -f /dev/null"
                                        ]
                                        
                                        fixed_result = subprocess.run(
                                            fixed_cmd,
                                            capture_output=True,
                                            text=True,
                                            check=False
                                        )
                                        
                                        if fixed_result.returncode == 0:
                                            container_id = fixed_result.stdout.strip()
                                            # Verify it's running
                                            time.sleep(0.5)
                                            if subprocess.run(
                                                ["docker", "ps", "--filter", f"id={container_id}", "--format", "{{.ID}}"],
                                                capture_output=True, text=True, check=False
                                            ).stdout.strip():
                                                return True, (
                                                    f"Successfully started fixed container: {container_id}"
                                                )
                            
                            # If it doesn't match our image but has the same name, 
                            # remove it and try again with a different name
                            console.print(
                                f"[yellow]Container name conflict. "
                                f"Removing container {container_name} and creating a new one...[/yellow]"
                            )
                            
                            rm_cmd = ["docker", "rm", "-f", container.get("ID", "")]
                            subprocess.run(
                                rm_cmd,
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            
                            # Try again with a slightly different name
                            new_name = f"{container_name}-new"
                            return DockerManager.run_container(image_name, new_name)
                
                # If still fails, return detailed error
                return False, f"Failed to start container: {error_msg}"
                
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            return False, f"Error starting container: {str(e)}"

    @staticmethod
    def set_active_container(container_id: str) -> None:
        """Set the active container for CAI.

        Args:
            container_id: ID of the container to set as active
        """
        # Check if the container is actually running
        try:
            check_process = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", container_id],
                capture_output=True,
                text=True,
                check=False
            )
            
            # If container exists but is not running, try to start it
            if check_process.returncode == 0 and "false" in check_process.stdout.lower():
                console.print(
                    f"[yellow]Container {container_id[:12]} exists but is not running. "
                    f"Attempting to start it...[/yellow]"
                )
                
                # First try with standard start
                start_process = subprocess.run(
                    ["docker", "start", container_id],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                # Check if start was successful
                if start_process.returncode != 0:
                    console.print(
                        f"[yellow]Normal start failed. Trying with custom keep-alive...[/yellow]"
                    )
                    
                    # Some containers exit immediately. Force remove and recreate with keep-alive
                    try:
                        # Get the image of the container
                        image_info = subprocess.run(
                            ["docker", "inspect", "--format", "{{.Config.Image}}", container_id],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        if image_info.returncode == 0:
                            image_name = image_info.stdout.strip()
                            
                            # Remove the old container
                            subprocess.run(
                                ["docker", "rm", "-f", container_id],
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            
                            # Create a new container with the same ID (hopefully)
                            # Using explicit keep-alive command
                            new_container = subprocess.run(
                                [
                                    "docker", "run", "-d", 
                                    "--name", f"cai-{image_name.replace('/', '-')}",
                                    image_name,
                                    "/bin/sh", "-c", "while true; do sleep 1000; done"
                                ],
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            
                            if new_container.returncode == 0:
                                # Update container_id to the new one
                                container_id = new_container.stdout.strip()
                                console.print(
                                    f"[green]Created and started new container {container_id[:12]}[/green]"
                                )
                            else:
                                console.print(
                                    f"[red]Failed to create new container: {new_container.stderr}[/red]"
                                )
                    except Exception as e:
                        console.print(f"[red]Error creating replacement container: {str(e)}[/red]")
                else:
                    # Normal start succeeded, now verify it's really running
                    verify = subprocess.run(
                        ["docker", "ps", "--filter", f"id={container_id}", "--format", "{{.ID}}"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if not verify.stdout.strip():
                        console.print(
                            f"[yellow]Container started but exited immediately. "
                            f"Recreating with keep-alive...[/yellow]"
                        )
                        
                        # Get the image of the container
                        image_info = subprocess.run(
                            ["docker", "inspect", "--format", "{{.Config.Image}}", container_id],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        if image_info.returncode == 0:
                            image_name = image_info.stdout.strip()
                            
                            # Remove the old container
                            subprocess.run(
                                ["docker", "rm", "-f", container_id],
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            
                            # Create a new container with persistent command
                            new_container = subprocess.run(
                                [
                                    "docker", "run", "-d", 
                                    "--name", f"cai-{image_name.replace('/', '-')}",
                                    image_name,
                                    "/bin/sh", "-c", "while true; do sleep 1000; done"
                                ],
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            
                            if new_container.returncode == 0:
                                # Update container_id to the new one
                                container_id = new_container.stdout.strip()
                                console.print(
                                    f"[green]Created persistent container {container_id[:12]}[/green]"
                                )
                            else:
                                console.print(
                                    f"[red]Failed to create persistent container: {new_container.stderr}[/red]"
                                )
        except Exception as e:
            # If there's an error, just log and continue
            console.print(f"[yellow]Warning during container activation: {str(e)}[/yellow]")
        
        # Set the container as active
        os.environ["CAI_ACTIVE_CONTAINER"] = container_id
        
        # Create workspace directory in container if needed
        try:
            # Get current workspace name
            workspace_name = os.getenv("CAI_WORKSPACE", None)            
            # Make sure workspace name is valid
            if not all(c.isalnum() or c in ['_', '-'] for c in workspace_name):
                workspace_name = "cai_default"
            
            # Create workspace directory path inside container
            container_workspace_path = f"/workspace/workspaces/{workspace_name}"
            
            # Check if container is running before attempting to create directory
            check_running = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", container_id],
                capture_output=True,
                text=True,
                check=False
            )
            
            if check_running.returncode == 0 and "true" in check_running.stdout.lower():
                # Create the workspace directory in the container
                mkdir_cmd = ["docker", "exec", container_id, "mkdir", "-p", container_workspace_path]
                mkdir_result = subprocess.run(
                    mkdir_cmd,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if mkdir_result.returncode == 0:
                    console.print(
                        f"[dim]Created workspace directory in container: {container_workspace_path}[/dim]"
                    )
                else:
                    console.print(
                        f"[yellow]Warning: Could not create workspace directory in container: {mkdir_result.stderr}[/yellow]"
                    )
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to setup workspace in container: {str(e)}[/yellow]")


class VirtualizationCommand(Command):
    """Command for Docker-based virtualization environments."""

    def __init__(self):
        """Initialize the virtualization command."""
        super().__init__(
            name="/virtualization",
            description=(
                "Set up and manage Docker virtualization environments"
            ),
            aliases=["/virt"]
        )
        
        # Cache for Docker information
        self.cached_containers = []
        self.cached_images = []
        self.last_docker_fetch = (
            datetime.datetime.now() - datetime.timedelta(minutes=10)
        )

        # Create mapping from ID to image name
        self.id_to_image = {}
        for image_name, image_info in DEFAULT_IMAGES.items():
            if "id" in image_info:
                self.id_to_image[image_info["id"]] = image_name
        
        # Add subcommands
        self.add_subcommand(
            "pull",
            "Pull a Docker image",
            self.handle_pull_subcommand
        )
        self.add_subcommand(
            "run",
            "Run a Docker container",
            self.handle_run_subcommand
        )

    def handle(self, args: Optional[List[str]] = None) -> bool:
        """Handle the virtualization command.

        Args:
            args: Optional list of command arguments

        Returns:
            True if the command was handled successfully, False otherwise
        """
        if not args:
            return self.show_virtualization_status()
            
        # Check if the first argument is a subcommand
        if args[0] in self.subcommands:
            return super().handle(args)
            
        # If not a subcommand, treat as image name to activate
        return self.handle_activate_image(args[0])
    
    def handle_no_args(self) -> bool:
        """Override default behavior to show status instead of error.

        Returns:
            True if the command was handled successfully, False otherwise
        """
        return self.show_virtualization_status()

    def show_virtualization_status(self) -> bool:
        """Show the current virtualization status.

        Returns:
            True if the command was handled successfully, False otherwise
        """
        docker_manager = DockerManager()
        
        # Check if Docker is installed
        if not docker_manager.is_docker_installed():
            console.print(
                Panel(
                    "Docker is not installed on your system.\n"
                    "Please install Docker to use virtualization features.",
                    title="Docker Not Found",
                    border_style="red"
                )
            )
            return True
            
        # Check if Docker daemon is running
        if not docker_manager.is_docker_running():
            console.print(
                Panel(
                    "Docker is not running.\n"
                    "Please start the Docker service to use virtualization.",
                    title="Docker Not Running",
                    border_style="yellow"
                )
            )
            return True
            
        # Get current active container
        active_container = os.getenv("CAI_ACTIVE_CONTAINER", "")
        
        # Refresh container and image cache
        self.refresh_docker_info()
        
        # Display active environment panel with more prominent styling
        self.show_active_environment(active_container)
        
        # Display only essential images by default
        self.show_useful_images_table(show_all=False)
        
        # Display usage information
        self.show_usage_info()
        
        return True

    def show_active_environment(self, active_container: str) -> None:
        """Display the active environment information.

        Args:
            active_container: ID of the active container, if any
        """
        # Get container details if active
        container_details = ""
        image_name = ""
        container_short_id = ""
        
        if active_container:
            for container in self.cached_containers:
                if container.get("ID", "").startswith(active_container):
                    container_short_id = container.get("ID", "")[:12]
                    image_name = container.get("Image", "")
                    container_details = f"Container: {container_short_id} ({image_name})"
                    break
        
        # Determine environment name and info
        if active_container:
            env_name = "Docker Container"
            env_info = container_details
            
            # Find the security category if this is one of our images
            if image_name in DEFAULT_IMAGES:
                category = DEFAULT_IMAGES[image_name].get("category", "")
                image_id = DEFAULT_IMAGES[image_name].get("id", "")
                if category:
                    env_name = f"{category} Environment"
                    if image_id:
                        env_info = f"{container_details} [ID: {image_id}]"
                    
            # Add icon based on environment
            icon = "🐳"  # Default Docker icon
            if "kali" in image_name.lower():
                icon = "🔒"  # Security icon for Kali
            elif "parrot" in image_name.lower():
                icon = "🔒"  # Security icon for Parrot
            elif "cai" in image_name.lower():
                icon = "⭐"  # Star for CAI container
            
            title = f"Active Environment: {icon} {env_name}"
            border_style = "green"
        else:
            env_name = "Host System"
            env_info = "Commands are executing directly on the host where CAI is running"
            title = "Active Environment: 💻 Host System"
            border_style = "blue"
        
        # Show the panel with environment information
        panel_content = [
            f"[bold cyan]Current active environment:[/bold cyan] [bold green]{env_name}[/bold green]",
            f"[cyan]Details:[/cyan] {env_info}",
            "",
            "[bold yellow]Select an environment from below to switch:[/bold yellow]"
        ]
        
        console.print(
            Panel(
                "\n".join(panel_content),
                border_style=border_style,
                title=title,
                title_align="left",
                padding=(1, 2)
            )
        )

    def refresh_docker_info(self) -> None:
        """Refresh Docker container and image information."""
        now = datetime.datetime.now()
        
        # Only refresh if the cache is older than 60 seconds
        if (now - self.last_docker_fetch).total_seconds() >= 60:
            docker_manager = DockerManager()
            self.cached_containers = docker_manager.get_container_list()
            self.cached_images = docker_manager.get_images_list()
            self.last_docker_fetch = now
            
    def show_useful_images_table(self, show_all: bool = False) -> None:
        """Display a table of useful Docker images.

        Args:
            show_all: Whether to show all available images (default: False)
        """
        # Get active container for highlighting
        active_container = os.getenv("CAI_ACTIVE_CONTAINER", "")
        active_image = ""
        
        # Find the active image if there's an active container
        if active_container:
            for container in self.cached_containers:
                if container.get("ID", "").startswith(active_container):
                    active_image = container.get("Image", "")
                    break
        
        # Process information about available images
        available_images = {
            img.get("Repository", ""): img
            for img in self.cached_images
        }
        
        # Define essential images to always show
        essential_images = [
            "kalilinux/kali-rolling", 
            "parrotsec/security"
        ]
        
        # Create main images table
        image_table = Table(
            title="Available Security Environments",
            show_header=True,
            header_style="bold yellow",
            title_style="bold cyan",
            box=rich.box.SQUARE
        )
        
        image_table.add_column("ID", style="bold blue", justify="center", width=6)
        image_table.add_column("Environment", style="bold cyan", width=30)
        image_table.add_column("Description", style="white")
        image_table.add_column("Status", style="green", justify="center", width=20)
        
        # Add Host System as the first option
        is_host_active = not active_container
        host_status = "[bold green]CURRENT ENVIRONMENT[/bold green]" if is_host_active else "[dim]Available[/dim]"
        display_host = "💻 [bold green]Host System ⭐ ACTIVE[/bold green]" if is_host_active else "💻 Host System"
        
        image_table.add_row(
            "[bold]host[/bold]",
            display_host,
            "Execute commands directly on the host operating system",
            host_status
        )
        
        # Add essential images 
        for image_name in essential_images:
            if image_name in DEFAULT_IMAGES:
                info = DEFAULT_IMAGES[image_name]
                
                # Get image ID
                image_id = info.get("id", "")
                
                # Check image status
                status = "[dim]Not pulled[/dim]"
                container_id = ""
                
                # Check for container using this image
                for container in self.cached_containers:
                    if container.get("Image", "") == image_name:
                        container_id = container.get("ID", "")[:12]
                        container_status = container.get("Status", "").lower()
                        
                        if "up" in container_status:
                            status = f"[bold green]RUNNING[/bold green] (ID: {container_id})"
                        elif "exited" in container_status or "created" in container_status:
                            status = f"[yellow]STOPPED[/yellow] (ID: {container_id})"
                        else:
                            status = f"[blue]CONTAINER[/blue] (ID: {container_id})"
                        break
                        
                # If no container but image is available
                if not container_id:
                    if image_name in available_images:
                        img = available_images[image_name]
                        image_id_short = img.get("ID", "")[:12]
                        status = f"[green]Available[/green] (ID: {image_id_short})"
                
                # Add special icon based on image type
                icon = "🔷"  # Default
                if image_name == "kalilinux/kali-rolling":
                    icon = "🔒"
                elif image_name == "parrotsec/security":
                    icon = "🔒"
                    
                # Display name with category
                category = info.get("category", "")
                display_name = f"{icon} {image_name} [ID: {image_id}]" if image_id else f"{icon} {image_name}"
                
                # Highlight active image
                if image_name == active_image:
                    display_name = f"[bold green]{icon} {image_name} ⭐ ACTIVE[/bold green]"
                    status = "[bold green]CURRENT ENVIRONMENT[/bold green]"
                
                # Add row to table
                image_table.add_row(
                    f"[bold]{image_id}[/bold]",
                    display_name,
                    info["description"],
                    status
                )
        
        # Print the essential images table
        console.print(image_table)
        
        # If show_all flag is True, show all available images by category
        if show_all:
            self._show_all_images_by_category(available_images, active_image)
            
        # If not showing all, add a note about additional images
        else:
            console.print("\n[dim]Only showing essential environments.[/dim]")

    def _show_all_images_by_category(self, available_images, active_image):
        """Show all images organized by category.
        
        Args:
            available_images: Dictionary of available Docker images
            active_image: Name of the currently active image, if any
        """
        # Group images by category
        images_by_category = {}
        for name, info in DEFAULT_IMAGES.items():
            category = info.get("category", "Other")
            if category not in images_by_category:
                images_by_category[category] = []
            images_by_category[category].append((name, info))
        
        # Define the preferred order of categories
        category_order = [
            "Offensive Pentesting",
            "CAI Official",
            "Forensic Analysis",
            "Malware Analysis",
            "Reverse Engineering",
            "Container Security"
        ]
        
        # Display tables in the preferred order
        console.print("\n[bold cyan]All Available Security Environments:[/bold cyan]\n")
        
        for category in category_order:
            # Skip if no images in this category
            if category not in images_by_category:
                continue
                
            images = images_by_category[category]
            
            image_table = Table(
                title=f"{category} Environments",
                show_header=True,
                header_style="bold yellow",
                title_style="bold cyan",
                box=rich.box.SIMPLE
            )
            
            image_table.add_column("ID", style="bold blue", justify="center", width=6)
            image_table.add_column("Environment", style="bold cyan", width=30)
            image_table.add_column("Description", style="white")
            image_table.add_column("Status", style="green", justify="center", width=20)
            
            # Add rows for the images in this category
            for name, info in images:
                # Check if image is available locally
                status = "[dim]Not pulled[/dim]"
                container_id = ""
                container_status = ""
                
                # First check if there's a container using this image
                for container in self.cached_containers:
                    if container.get("Image", "") == name:
                        container_id = container.get("ID", "")[:12]
                        container_status = container.get("Status", "").lower()
                        
                        if "up" in container_status:
                            status = f"[bold green]RUNNING[/bold green] (ID: {container_id})"
                        elif "exited" in container_status or "created" in container_status:
                            status = f"[yellow]STOPPED[/yellow] (ID: {container_id})"
                        else:
                            status = f"[blue]CONTAINER[/blue] (ID: {container_id})"
                        break
                        
                # If no container but image is available
                if not container_id:
                    if name in available_images:
                        img = available_images[name]
                        image_id = img.get("ID", "")[:12]
                        status = f"[green]Available[/green] (ID: {image_id})"
                
                # Add special icon for different category
                icon = "🔷"  # Default icon
                if category == "CAI Official":
                    icon = "⭐"
                elif category == "Offensive Pentesting":
                    icon = "🔒"
                elif category == "Forensic Analysis":
                    icon = "🔍"
                elif category == "Malware Analysis":
                    icon = "🦠"
                elif category == "Reverse Engineering":
                    icon = "⚙️"
                elif category == "Container Security":
                    icon = "🛡️"
                    
                # Get the ID from the image info
                image_id = info.get("id", "")
                    
                # Display name with ID if available
                image_name_display = f"{icon} {name} [ID: {image_id}]" if image_id else f"{icon} {name}"
                description_display = info["description"]
                
                # Highlight active image
                if name == active_image:
                    image_name_display = f"[bold green]{icon} {name} ⭐ ACTIVE[/bold green]"
                    description_display = f"[green]{info['description']}[/green]"
                    status = "[bold green]CURRENT ENVIRONMENT[/bold green]"
                
                image_table.add_row(
                    f"[bold]{image_id}[/bold]",
                    image_name_display,
                    description_display,
                    status
                )
                
            console.print(image_table)

    def show_usage_info(self) -> None:
        """Display usage information for the virtualization command with category examples."""
        console.print("\n[bold cyan]Available Commands:[/bold cyan]")
        console.print(
            "  [bold]/virtualization[/bold]                      - "
            "Show environment selection menu")
        console.print(
            "  [bold]/virtualization <image_name>[/bold]         - "
            "Switch to environment by name")
        console.print(
            "  [bold]/virtualization <image_id>[/bold]           - "
            "Switch by ID (e.g.: sec1, pen1)")
        
        # Common commands with examples
        console.print("\n[bold yellow]Common Commands:[/bold yellow]")
        console.print(
            "  [bold]/virtualization kalilinux/kali-rolling[/bold] - "
            "Kali Linux with security tools [ID: pen1]")
        console.print(
            "  [bold]/virtualization parrotsec/security[/bold]   - "
            "Parrot Security OS with tools [ID: pen2]")
        console.print(
            "  [bold]/virtualization host[/bold]                 - "
            "Return to host system")
        
        # General note
        console.print("\n[bold red]Important:[/bold red]")
        console.print("[dim]When a container is active, all shell commands will execute inside that container. LLM commands will also be executed in this environment.[/dim]")
    
    def handle_pull_subcommand(self, args: Optional[List[str]] = None) -> bool:
        """Handle the pull subcommand.
        
        Args:
            args: Optional list of subcommand arguments
            
        Returns:
            True if the subcommand was handled successfully, False otherwise
        """
        if not args:
            console.print(
                "[yellow]Please specify an image to pull.[/yellow]"
            )
            return False
            
        image_name = args[0]
        docker_manager = DockerManager()
        
        # Check Docker status
        if not docker_manager.is_docker_installed():
            console.print(
                "[red]Docker is not installed on your system.[/red]"
            )
            return False
            
        if not docker_manager.is_docker_running():
            console.print(
                "[yellow]Docker daemon is not running.[/yellow]"
            )
            return False
            
        # Show progress message
        with console.status(f"Pulling Docker image: {image_name}..."):
            success, message = docker_manager.pull_image(image_name)
            
        # Show result
        if success:
            console.print(f"[green]{message}[/green]")
            
            # Refresh Docker info
            self.refresh_docker_info()
        else:
            console.print(f"[red]{message}[/red]")
            
        return success
    
    def handle_run_subcommand(self, args: Optional[List[str]] = None) -> bool:
        """Handle the run subcommand.
        
        Args:
            args: Optional list of subcommand arguments
            
        Returns:
            True if the subcommand was handled successfully, False otherwise
        """
        if not args:
            console.print(
                "[yellow]Please specify an image to run.[/yellow]"
            )
            return False
            
        image_name = args[0]
        container_name = None
        
        # Check if a container name was provided
        if len(args) > 1:
            container_name = args[1]
            
        docker_manager = DockerManager()
        
        # Check Docker status
        if not docker_manager.is_docker_installed():
            console.print(
                "[red]Docker is not installed on your system.[/red]"
            )
            return False
            
        if not docker_manager.is_docker_running():
            console.print(
                "[yellow]Docker daemon is not running.[/yellow]"
            )
            return False
            
        # Show progress message
        status_message = f"Running Docker container from image: {image_name}..."
        with console.status(status_message):
            success, message = docker_manager.run_container(
                image_name, container_name)
            
        # Show result
        if success:
            console.print(f"[green]{message}[/green]")
            
            # Extract container ID from message
            container_id = message.split(":")[-1].strip()
            
            # Set as active container
            docker_manager.set_active_container(container_id)
            console.print(
                f"[green]Container {container_id[:12]} set as active environment.[/green]"
            )
            
            # Refresh Docker info
            self.refresh_docker_info()
        else:
            console.print(f"[red]{message}[/red]")
            
        return success
        
    def handle_activate_image(self, image_identifier: str) -> bool:
        """Handle activating a Docker image by name or ID.
        
        Args:
            image_identifier: Name or ID of the image to activate
            
        Returns:
            True if the image was activated successfully, False otherwise
        """
        # Normalize image name for all comparisons
        normalized_image_identifier = normalize_image_name(image_identifier)
        # Special case for returning to host system
        if image_identifier.lower() in ["host", "system", "none"]:
            if "CAI_ACTIVE_CONTAINER" in os.environ:
                # Clear the active container
                previous = os.environ.pop("CAI_ACTIVE_CONTAINER")
                console.print(
                    f"[green]Switched back to host system environment. "
                    f"Previous container {previous[:12]} is no longer active.[/green]"
                )
                return True
            else:
                console.print(
                    "[yellow]Already using host system environment.[/yellow]"
                )
                return True
        
        docker_manager = DockerManager()
        
        # Check Docker status
        if not docker_manager.is_docker_installed():
            console.print(
                "[red]Docker is not installed on your system.[/red]"
            )
            return False
            
        if not docker_manager.is_docker_running():
            console.print(
                "[yellow]Docker daemon is not running.[/yellow]"
            )
            return False
        
        # Refresh container and image cache
        self.refresh_docker_info()
        
        # NEW: Check if the image_identifier is an existing container ID
        for container in self.cached_containers:
            container_id = container.get("ID", "")
            if container_id.startswith(image_identifier):
                # Found a container with matching ID (or starting with the provided ID)
                console.print(
                    f"[yellow]Found container with ID: {container_id[:12]}[/yellow]"
                )
                
                # Get container status
                container_status = container.get("Status", "").lower()
                
                # Check if the container is stopped and start it if needed
                if "exited" in container_status or "created" in container_status:
                    console.print(
                        f"[yellow]Container {container_id[:12]} exists but is stopped. "
                        f"Attempting to start it...[/yellow]"
                    )
                    
                    # Try to start the container
                    try:
                        start_process = subprocess.run(
                            ["docker", "start", container_id],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        if start_process.returncode != 0:
                            console.print(
                                f"[yellow]Warning: Failed to start container: {start_process.stderr}[/yellow]"
                            )
                    except Exception as e:
                        console.print(f"[yellow]Warning: {str(e)}[/yellow]")
                
                # Set this container as active
                docker_manager.set_active_container(container_id)
                
                # Get the image name for display
                image_name = container.get("Image", "unknown")
                
                # Find the category information if available
                category = "Docker Container"
                if image_name in DEFAULT_IMAGES:
                    category = DEFAULT_IMAGES[image_name].get("category", "Docker Container")
                
                console.print(
                    f"[green]Switched to container {container_id[:12]} "
                    f"({image_name}).[/green]\n"
                    f"[dim]All commands will now execute in this {category} container.[/dim]"
                )
                
                # Show environment status after switching
                self.show_active_environment(container_id)
                return True
        
        # Check if we're using an ID, and convert it to image name if needed
        image_name = image_identifier
        if image_identifier in self.id_to_image:
            image_name = self.id_to_image[image_identifier]
            console.print(
                f"[dim]Using image '{image_name}' for ID '{image_identifier}'[/dim]"
            )
        
        # SPECIAL HANDLING FOR PARROTSEC
        # ==============================
        if image_name == "parrotsec/security":
            return self._handle_parrotsec()
        
        # Generate a container name based on the image (needed for later)
        container_name = None
        if image_name == "kalilinux/kali-rolling":
            container_name = "kali-security"
        else:
            # For other images, use a name based on the ID if available
            for img_name, img_info in DEFAULT_IMAGES.items():
                if img_name == image_name and "id" in img_info:
                    container_name = f"cai-{img_info['id']}"
                    break
        
        # First, check if there's an existing container using the requested image
        for container in self.cached_containers:
            # Normalize both image names for comparison
            container_image = normalize_image_name(container.get("Image", ""))
            if container_image == normalize_image_name(image_name):
                container_id = container.get("ID", "")
                container_status = container.get("Status", "").lower()
                
                # Check if the container is stopped and start it if needed
                if "exited" in container_status or "created" in container_status:
                    # Start the container if it's stopped
                    console.print(
                        f"[yellow]Container {container_id[:12]} exists but is stopped. "
                        f"Attempting to activate it...[/yellow]"
                    )
                    
                    try:
                        # First try with standard start
                        start_process = subprocess.run(
                            ["docker", "start", container_id],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        # Check if start was successful
                        if start_process.returncode != 0:
                            console.print(
                                f"[yellow]Normal start failed: {start_process.stderr.strip()}[/yellow]"
                            )
                            console.print(
                                f"[yellow]Setting container as active anyway - commands will fall back to host.[/yellow]"
                            )
                            
                            # Set container as active even though it's not running
                            # The run_command function will handle fallback to host
                            docker_manager.set_active_container(container_id)
                            
                            # Find the category information
                            category = "Docker Container"
                            if image_name in DEFAULT_IMAGES:
                                category = DEFAULT_IMAGES[image_name].get("category", "Docker Container")
                            
                            console.print(
                                f"[yellow]Container {container_id[:12]} is not running, but it's now the active environment.[/yellow]\n"
                                f"[dim]Commands will be executed on the host until the container is fixed.[/dim]"
                            )
                            
                            # Show environment status after switching
                            self.show_active_environment(container_id)
                            return True
                    except Exception as e:
                        console.print(f"[red]Error starting container: {str(e)}[/red]")
                        # Continue to set it as active anyway
                        docker_manager.set_active_container(container_id)
                        return True
                
                # Set this container as active
                docker_manager.set_active_container(container_id)
                
                # Find the category information
                category = "Docker Container"
                if image_name in DEFAULT_IMAGES:
                    category = DEFAULT_IMAGES[image_name].get("category", "Docker Container")
                
                console.print(
                    f"[green]Switched to {category} environment.[/green]\n"
                    f"[dim]Using existing container {container_id[:12]}.[/dim]"
                )
                
                # Show environment status after switching
                self.show_active_environment(container_id)
                return True
        
        # No existing container or container couldn't be started - check if image is available locally
        image_available = False
        for image in self.cached_images:
            # Normalize both image names for comparison
            if normalize_image_name(image.get("Repository", "")) == normalize_image_name(image_name):
                image_available = True
                break
                
        # If not available, pull it
        if not image_available:
            console.print(
                f"[yellow]Image {image_name} not found locally. "
                f"Pulling from Docker Hub...[/yellow]"
            )
            
            with console.status(f"Pulling Docker image: {image_name}..."):
                success, message = docker_manager.pull_image(image_name)
                
            if not success:
                console.print(f"[red]{message}[/red]")
                # Don't fallback here - just report the error
                return False
                
            console.print(f"[green]{message}[/green]")
        
        # Run a container from the image
        with console.status(
            f"Starting {image_name} environment..."
        ):
            success, message = docker_manager.run_container(image_name, container_name)
            
        if not success:
            console.print(f"[red]{message}[/red]")
            
            # For problematic images, we might still want to set them as active
            # so commands can fall back to host
            # is_problematic = image_name in problematic_images # This variable is not defined in the original code
            # if is_problematic:
            #     console.print(
            #         f"[yellow]Unable to start {image_name} container. "
            #         f"Setting it as active anyway to enable fallback to host execution.[/yellow]"
            #     )
                
                # Create a dummy ID that will be treated as the active container
                # dummy_id = f"dummy-{image_name.replace('/', '-')}"
                # os.environ["CAI_ACTIVE_CONTAINER"] = dummy_id
                
                # console.print(
                #     f"[yellow]Set '{dummy_id}' as active environment.[/yellow]\n"
                #     f"[dim]Commands will execute on host, but environment name will show as {image_name}.[/dim]"
                # )
                # return True
                
            return False
            
        console.print(f"[green]{message}[/green]")
        
        # Extract container ID from message
        container_id = message.split(":")[-1].strip()
        
        # Set as active container
        docker_manager.set_active_container(container_id)
        
        # Find the category information
        category = "Docker Container"
        if image_name in DEFAULT_IMAGES:
            category = DEFAULT_IMAGES[image_name].get("category", "Docker Container")
            
        console.print(
            f"[green]Switched to {category} environment ({image_name}).[/green]\n"
            f"[dim]All commands will now execute in container {container_id[:12]}.[/dim]"
        )
        
        # Show environment status after switching
        self.show_active_environment(container_id)
        
        return True

    def _handle_parrotsec(self) -> bool:
        """Special handler for Parrot Security which is particularly problematic.
        
        Returns:
            True if the image was activated successfully, False otherwise
        """
        image_name = "parrotsec/security"
        fixed_image_name = "cai-fixed-parrotsec"
        container_name = "cai-parrotsec"
        
        console.print(
            f"[yellow]Using special handling for {image_name}.[/yellow]"
        )
        
        # Step 1: Check if we already have the fixed image
        fixed_image_exists = False
        for image in self.cached_images:
            if image.get("Repository", "") == fixed_image_name:
                fixed_image_exists = True
                break
                
        # Step 2: If we don't have a fixed image, create one
        if not fixed_image_exists:
            console.print(
                f"[yellow]Creating a fixed Parrot Security image...[/yellow]"
            )
            
            # 2.1: First pull the original image if needed
            original_exists = False
            for image in self.cached_images:
                if image.get("Repository", "") == image_name:
                    original_exists = True
                    break
                    
            if not original_exists:
                console.print(
                    f"[yellow]Pulling {image_name} image...[/yellow]"
                )
                with console.status(f"Pulling {image_name}..."):
                    result = subprocess.run(
                        ["docker", "pull", image_name],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if result.returncode != 0:
                        console.print(
                            f"[red]Failed to pull {image_name}: {result.stderr}[/red]"
                        )
                        return False
            
            # 2.2: Create a temporary container and export a fixed Dockerfile
            temp_name = f"temp-parrot-{int(time.time())}"
            
            # Create temp container using the original image
            with console.status("Creating temporary container..."):
                create_result = subprocess.run(
                    [
                        "docker", "create",
                        "--name", temp_name,
                        image_name
                    ],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if create_result.returncode != 0:
                    console.print(
                        f"[red]Failed to create temporary container: {create_result.stderr}[/red]"
                    )
                    return False
            
            # 2.3: Create a custom Dockerfile to fix the entry point
            dockerfile_content = f"""FROM {image_name}
ENTRYPOINT ["/bin/bash"]
CMD ["-c", "tail -f /dev/null"]
"""
            
            # Write Dockerfile to a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".dockerfile") as f:
                f.write(dockerfile_content)
                f.flush()
                
                # 2.4: Build the fixed image
                with console.status(f"Building fixed {fixed_image_name}..."):
                    build_result = subprocess.run(
                        [
                            "docker", "build",
                            "-f", f.name,
                            "-t", fixed_image_name,
                            "."
                        ],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if build_result.returncode != 0:
                        console.print(
                            f"[red]Failed to build fixed image: {build_result.stderr}[/red]"
                        )
                        return False
            
            # 2.5: Clean up the temporary container
            subprocess.run(
                ["docker", "rm", temp_name],
                capture_output=True,
                text=True,
                check=False
            )
            
            console.print(
                f"[green]Successfully created fixed Parrot Security image: {fixed_image_name}[/green]"
            )
            
            # Refresh images to include the new one
            self.cached_images = DockerManager.get_images_list()
        
        # Step 3: Check if a container with our fixed image is already running
        existing_container_id = None
        for container in self.cached_containers:
            if container.get("Image", "") == fixed_image_name:
                existing_container_id = container.get("ID", "")
                break
        
        # Step 4: If container exists, try to start it if needed
        if existing_container_id:
            console.print(
                f"[yellow]Found existing fixed container. Starting if needed...[/yellow]"
            )
            
            # Check if it's running
            check_result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", existing_container_id],
                capture_output=True,
                text=True,
                check=False
            )
            
            if check_result.returncode == 0 and "true" in check_result.stdout.lower():
                # It's already running, use it
                console.print(
                    f"[green]Container {existing_container_id[:12]} is already running.[/green]"
                )
            else:
                # Start it
                start_result = subprocess.run(
                    ["docker", "start", existing_container_id],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if start_result.returncode != 0:
                    # Failed to start, remove and create a new one
                    console.print(
                        f"[yellow]Failed to start container. Removing and creating a new one.[/yellow]"
                    )
                    
                    subprocess.run(
                        ["docker", "rm", "-f", existing_container_id],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    existing_container_id = None
                else:
                    console.print(
                        f"[green]Successfully started container {existing_container_id[:12]}.[/green]"
                    )
        
        # Step 5: If no running container, create a new one
        if not existing_container_id:
            console.print(
                f"[yellow]Creating new container from fixed image...[/yellow]"
            )
            
            # Remove any existing container with the same name
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                text=True,
                check=False
            )
            
            # Create a new container
            with console.status("Creating container..."):
                create_result = subprocess.run(
                    [
                        "docker", "run", "-d",
                        "--name", container_name,
                        "--network=host",
                        "--cap-add=NET_ADMIN",
                        "--cap-add=NET_RAW",
                        "--security-opt=seccomp=unconfined",
                        fixed_image_name
                        # No command needed - using CMD from the fixed image
                    ],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if create_result.returncode != 0:
                    console.print(
                        f"[red]Failed to create container: {create_result.stderr}[/red]"
                    )
                    return False
                
                existing_container_id = create_result.stdout.strip()
                
                # Verify it's running
                time.sleep(1)
                check_result = subprocess.run(
                    ["docker", "ps", "--filter", f"id={existing_container_id}", "--format", "{{.ID}}"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if not check_result.stdout.strip():
                    console.print(
                        f"[red]Container created but not running. Setting with fallback handling.[/red]"
                    )
                else:
                    console.print(
                        f"[green]Container {existing_container_id[:12]} created and running.[/green]"
                    )
        
        # Step 6: Set the container as active
        DockerManager.set_active_container(existing_container_id)
        
        # Step 7: Show success message
        category = "Offensive Pentesting"
        console.print(
            f"[green]Switched to {category} environment ({image_name}).[/green]\n"
            f"[dim]All commands will now execute in container {existing_container_id[:12]}.[/dim]"
        )
        
        # Show environment status after switching
        self.show_active_environment(existing_container_id)
        
        return True

    def _fallback_to_best_environment(self) -> bool:
        """Attempt to fallback to the best available environment.
        
        Returns:
            True if fallback was successful, False otherwise
        """
        # Check for existing containers with our default images
        for container in self.cached_containers:
            image = container.get("Image", "")
            if image in DEFAULT_IMAGES:
                container_id = container.get("ID", "")
                # Set this container as active
                DockerManager.set_active_container(container_id)
                console.print(
                    f"[yellow]Falling back to existing container {container_id[:12]} "
                    f"from image {image}.[/yellow]"
                )
                # Refresh Docker info
                self.refresh_docker_info()
                
                # Show current environment status
                self.show_active_environment(container_id)
                return True
            
        # Then try kalilinux/kali-rolling
        if "kalilinux/kali-rolling" in [img.get("Repository", "") for img in self.cached_images]:
            console.print(
                "[yellow]Falling back to kalilinux/kali-rolling image...[/yellow]"
            )
            return self.handle_activate_image("kalilinux/kali-rolling")
        return self.handle_activate_image("kalilinux/kali-rolling")

# Register the commands
register_command(VirtualizationCommand())