#!/usr/bin/env python3
"""Upload the lumina image tar and deploy it to the remote server."""
import os
import sys
import io
import time
import paramiko

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HOST = "182.92.84.206"
USER = "root"
PASSWORD = "sunwenke!@#123"
LOCAL_TAR = "D:/project/lumina/lumina728-1.9.tar"
REMOTE_TAR = "/root/lumina728-1.9.tar"
COMPOSE_FILE = "/root/lumina-prod/docker-compose.prod.yml"
ENV_FILE = "/root/lumina-prod/.env.prod"
IMAGE_TAG = "lumina728:1.9"

def run_remote(ssh, command, timeout=300):
    print(f"[REMOTE] {command[:200]}...")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    print(f"[REMOTE] rc={rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}\n{'='*40}")
    return rc, out, err

def main():
    if not os.path.exists(LOCAL_TAR):
        print(f"Local tar not found: {LOCAL_TAR}")
        sys.exit(1)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST} ...")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    print("Connected.")

    # Upload tar
    print(f"Uploading {LOCAL_TAR} ({os.path.getsize(LOCAL_TAR)} bytes) to {REMOTE_TAR} ...")
    sftp = ssh.open_sftp()
    sftp.put(LOCAL_TAR, REMOTE_TAR)
    sftp.close()
    print("Upload complete.")

    # Run deployment and verification steps
    script = f"""set -e
export COMPOSE_FILE={COMPOSE_FILE}
export ENV_FILE={ENV_FILE}

echo "=== Stopping legacy docker-run container if present ==="
if docker ps -aq --filter name=lumina51 | grep -q .; then
    docker stop lumina51 || true
    docker rm lumina51 || true
fi

echo "=== Loading image ==="
docker load -i {REMOTE_TAR}

echo "=== Updating compose image tag ==="
if [ -f "$COMPOSE_FILE" ]; then
    sed -i 's|lumina[0-9]*:[0-9.]*|{IMAGE_TAG}|g' "$COMPOSE_FILE"
    grep -n "image:" "$COMPOSE_FILE" || true
else
    echo "WARNING: compose file not found: $COMPOSE_FILE"
fi

if [ -f "$ENV_FILE" ]; then
    sed -i 's|LUMINA_IMAGE=.*|LUMINA_IMAGE={IMAGE_TAG}|g' "$ENV_FILE" || true
    grep -n "LUMINA_IMAGE" "$ENV_FILE" || true
fi

echo "=== Recreating containers ==="
cd /root/lumina-prod
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --force-recreate

echo "=== Waiting for API health ==="
for i in $(seq 1 30); do
    if curl -sS -o /dev/null -w "%{{http_code}}" http://localhost:8080/health | grep -qE '^2'; then
        echo "Health OK"
        break
    fi
    echo "Attempt $i/30 not healthy yet..."
    sleep 2
done

echo "=== Container status ==="
docker ps --format "table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}"

echo "=== db_pool check ==="
curl -sS http://localhost:8080/health || true
echo ""

echo "=== DB connectivity check ==="
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c "SELECT COUNT(*) AS content_exports_count FROM content_exports;"
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c "SELECT COUNT(*) AS account_profiles_count FROM account_profiles;"
"""
    rc, out, err = run_remote(ssh, script, timeout=600)
    ssh.close()
    if rc != 0:
        print("Deployment script failed.")
        sys.exit(1)
    print("Deployment script finished.")

if __name__ == "__main__":
    main()
