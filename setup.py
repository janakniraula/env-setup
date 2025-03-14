import os
import subprocess
import time
import sys
from pathlib import Path

# Function to run shell commands with improved output and error handling
def run_command(command, description, ignore_errors=False):
    print(f"\n{description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=not ignore_errors
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.returncode == 0:
            print("✅ Success!")
        elif ignore_errors:
            print("ℹ️ Ignored non-critical error.")
        else:
            print(f"❌ Error: {result.stderr.strip()}")
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        if not ignore_errors:
            print(f"❌ Failed: {e.stderr.strip()}")
            sys.exit(1)

# Check if script is run with sudo privileges
if os.geteuid() != 0:
    print("❌ This script requires sudo privileges. Please run with 'sudo python3 script.py'.")
    sys.exit(1)

# User confirmation
print("Starting DevOps environment setup for Jenkins (in Docker), Docker, and GitHub CLI...")
print("⚠️ This script will modify your system. Ensure you have an Ubuntu server ready.")
input("Press Enter to continue or Ctrl+C to abort...")

# Update and upgrade the system
run_command("apt update && apt upgrade -y", "Updating and upgrading the system")

# Install OpenJDK 21 for Jenkins
run_command("apt install -y openjdk-21-jdk", "Installing OpenJDK 21")
run_command("java -version", "Verifying Java installation")

# Install GitHub CLI (without authentication)
run_command("apt install -y gh", "Installing GitHub CLI")
run_command("gh --version", "Verifying GitHub CLI installation")

# Install Docker and Docker Compose on the host
run_command("apt install -y docker.io docker-compose", "Installing Docker and Docker Compose on host")
run_command("docker --version", "Verifying Docker installation")
run_command("docker-compose --version", "Verifying Docker Compose installation")

# Enable and start Docker service
run_command("systemctl enable docker", "Enabling Docker service")
run_command("systemctl start docker", "Starting Docker service")
run_command("systemctl status docker --no-pager | head -n 3", "Checking Docker status")

# Add current user to Docker group
current_user = os.getenv("SUDO_USER") or os.getenv("USER")
if current_user:
    run_command(f"usermod -aG docker {current_user}", f"Adding {current_user} to Docker group")
else:
    print("❌ Could not determine current user. Skipping Docker group addition.")

# Apply group changes without requiring logout
run_command(f"sg docker -c 'echo Group refreshed'", "Refreshing group membership for Docker", ignore_errors=True)

# Check for port 8080 conflict and free it if needed
port_check = subprocess.run("netstat -tulnp | grep 8080", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
if port_check.returncode == 0:
    print("❌ Port 8080 is in use. Attempting to free it...")
    run_command("systemctl stop jenkins || true", "Stopping native Jenkins (if running)", ignore_errors=True)
    run_command("pkill -f 'java.*8080' || true", "Killing any process on port 8080", ignore_errors=True)

# Check if jenkins-docker container exists and start or create it
jenkins_home = Path("/var/jenkins_home")
jenkins_home.mkdir(exist_ok=True, mode=0o700)

container_check = subprocess.run("docker ps -a | grep -q jenkins-docker", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
if container_check.returncode == 0:
    print("\nExisting jenkins-docker container found...")
    run_command("docker start jenkins-docker", "Starting existing jenkins-docker container")
else:
    print("\nNo jenkins-docker container found. Creating a new one...")
    run_command(
        """
        docker run -d --name jenkins-docker \
        --restart unless-stopped \
        -p 8080:8080 -p 50000:50000 \
        -v /var/jenkins_home:/var/jenkins_home \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v $(which docker):/usr/bin/docker \
        -u root \
        -e DOCKER_GID=$(getent group docker | cut -d: -f3) \
        jenkins/jenkins:lts
        """,
        "Creating and starting new jenkins-docker container"
    )

# Wait for Jenkins to initialize and fetch initial admin password
print("\nWaiting for Jenkins to start...")
time.sleep(20)  # Increased wait time for stability
run_command(
    "docker exec jenkins-docker cat /var/jenkins_home/secrets/initialAdminPassword",
    "Fetching Jenkins initial admin password"
)

# Final instructions
print("\n✅ Setup completed successfully!")
print("⚠️ Jenkins is running at http://<your_server_ip>:8080")
print("⚠️ Use the password displayed above to unlock Jenkins.")
print("ℹ️ To enable docker-compose in Jenkins, manually install it inside the container:")
print("  1. docker exec -it jenkins-docker bash")
print("  2. curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose")
print("  3. chmod +x /usr/local/bin/docker-compose")
print("  4. exit")
print("ℹ️ If Docker commands fail, log out and back in, or reboot the server with 'sudo reboot'.")
print("ℹ️ Next steps: Configure Jenkins, set up your Django pipeline, and deploy!")
