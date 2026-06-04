#!/usr/bin/env python3
"""部署脚本"""
import os
import io
import tarfile
import yaml
import paramiko

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

with open(os.path.join(SCRIPT_DIR, "config.yaml")) as f:
    cfg = yaml.safe_load(f)

HOST = cfg["host"]
PORT = cfg.get("port", 22)
USER = cfg.get("user", "root")
PASS = cfg["password"]
REMOTE_DIR = cfg["remote_dir"]

EXCLUDE = {".venv", "__pycache__", ".git", "deploy/config.yaml", "app.log", "app.pid"}


def should_exclude(path):
    for part in path.split("/"):
        if part in EXCLUDE:
            return True
    return path.endswith(".pyc")


def create_tar():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(PROJECT_DIR):
            rel_root = os.path.relpath(root, PROJECT_DIR)
            dirs[:] = [d for d in dirs if not should_exclude(os.path.join(rel_root, d))]
            for f in files:
                fpath = os.path.join(rel_root, f)
                if should_exclude(fpath):
                    continue
                tar.add(os.path.join(root, f), arcname=fpath)
    buf.seek(0)
    return buf


def run(ssh, cmd):
    print(f"  > {cmd}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"    {out}")
    if err:
        print(f"    [err] {err}")


def main():
    print(f"=== 连接 {HOST} ===")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)

    print(f"=== 上传文件到 {REMOTE_DIR} ===")
    sftp = ssh.open_sftp()
    tar_data = create_tar()
    remote_tar = "/tmp/order_v1_deploy.tar.gz"
    with sftp.open(remote_tar, "wb") as f:
        f.write(tar_data.read())
    sftp.close()

    run(ssh, f"mkdir -p {REMOTE_DIR}")
    run(ssh, f"tar xzf {remote_tar} -C {REMOTE_DIR}")
    run(ssh, f"rm -f {remote_tar}")
    run(ssh, f"test -d {REMOTE_DIR}/.venv || python3 -m venv {REMOTE_DIR}/.venv")
    run(ssh, f"{REMOTE_DIR}/.venv/bin/pip install -r {REMOTE_DIR}/requirements.txt -q")
    run(ssh, f"cd {REMOTE_DIR} && bash deploy/service.sh restart")

    ssh.close()
    print("=== 部署完成 ===")


if __name__ == "__main__":
    main()
