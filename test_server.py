#!/usr/bin/env python3
"""Test the deployed system-chat stream and verify DB writes."""
import sys
import io
import paramiko

# Ensure UTF-8 output on Windows to handle emoji/Chinese in remote logs
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HOST = "182.92.84.206"
USER = "root"
PASSWORD = "sunwenke!@#123"

def run_remote(ssh, command, timeout=180):
    print(f"[REMOTE] {command[:220]}...")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    print(f"[REMOTE] rc={rc}\nSTDOUT:\n{out}\nSTDERR:\n{err}\n{'='*40}")
    return rc, out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST} ...")
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    print("Connected.")

    ts = run_remote(ssh, "date +%s%N")[1].strip().splitlines()[-1]
    user_id = f"test_user_{ts}"
    conversation_id = f"test_conv_{ts}"

    script = f"""set -e
USER_ID="{user_id}"
CONV_ID="{conversation_id}"

echo "=== Pre-test DB counts ==="
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c "SELECT COUNT(*) AS content_exports_count FROM content_exports;"
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c "SELECT COUNT(*) AS account_profiles_count FROM account_profiles;"

echo "=== Calling system-chat stream ==="
curl -sS -N --max-time 120 -X POST "http://localhost:8080/api/v1/services/system-chat/stream" \\
  -H "Content-Type: application/json" \\
  -d '{{"user_id":"'$USER_ID'","conversation_id":"'$CONV_ID'","message":"帮我写一篇小红书种草笔记","platform":"xiaohongshu"}}' \\
  | tee /tmp/stream_test.log | tail -n 20

echo "=== Stream done, waiting 5s for async writes ==="
sleep 5

echo "=== Post-test DB counts ==="
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c "SELECT COUNT(*) AS content_exports_count FROM content_exports;"
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c "SELECT COUNT(*) AS account_profiles_count FROM account_profiles;"

echo "=== Latest content_exports for this user ==="
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c "SELECT id, user_id, conversation_id, request_id, export_type, article_title, file_path, created_at FROM content_exports WHERE user_id = '$USER_ID' ORDER BY id DESC LIMIT 3;"

echo "=== Latest account_profiles for this user ==="
PGPASSWORD=lumina123 psql -h 172.29.146.189 -U lumina -d lumina -c "SELECT id, user_id, platform, positioning_statement, updated_at FROM account_profiles WHERE user_id = '$USER_ID' ORDER BY id DESC LIMIT 3;"

echo "=== Relevant app logs (last 50 lines) ==="
docker logs --tail 50 lumina51 2>&1 | tail -n 50 || true
"""
    rc, out, err = run_remote(ssh, script, timeout=240)
    ssh.close()
    if rc != 0:
        print("Test script failed.")
        sys.exit(1)
    print("Test script finished.")

if __name__ == "__main__":
    main()
