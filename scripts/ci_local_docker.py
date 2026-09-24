"""Disposable CI containers only: no Compose, host ports or real-store mounts."""

import json
import subprocess
import tarfile
import time
import uuid

from ci_local import sha, step, pytest_metrics


def run_docker(runner, identity, required):
    probe = runner.run(
        "docker_probe",
        ["docker", "info", "--format", "{{.ServerVersion}}"],
        required,
        timeout=15,
    )
    if probe["status"] != "PASS":
        probe["status"] = "BLOCKED"
        return "BLOCKED"
    if identity["dirty_state"]:
        runner.steps.append(
            step(
                "docker_source",
                "BLOCKED",
                {"reason": "Docker archive requires clean committed source"},
                required,
            )
        )
        return "BLOCKED"
    start_index = len(runner.steps)
    suffix = uuid.uuid4().hex[:12]
    network, database, application = [
        "sapi-ci-" + label + "-" + suffix for label in ("net", "db", "test")
    ]
    image = "sapi-ci-local:" + identity["tree_sha"][:12]
    context = runner.output / "docker-context"
    context.mkdir()
    archive = runner.output / "source.tar"
    archive_step = runner.run(
        "docker_archive",
        [
            "git",
            "archive",
            "--format=tar",
            "--output=" + str(archive),
            identity["code_sha"],
        ],
        required,
    )
    if archive_step["status"] != "PASS":
        return "BLOCKED"
    with tarfile.open(archive) as bundle:
        if any(not (m.isfile() or m.isdir()) for m in bundle.getmembers()):
            runner.steps.append(
                step(
                    "docker_source",
                    "BLOCKED",
                    {"reason": "Archive contains links or special files"},
                    required,
                )
            )
            return "BLOCKED"
        bundle.extractall(context, filter="data")
    archive_step["evidence"]["archive_sha256"] = sha(archive)
    # CI image uses the repository analytics dependency build, never its daily-loop CMD.
    dockerfile = (context / "Dockerfile.analytics").read_text(encoding="utf-8")
    dockerfile += (
        "\nRUN apt-get update && apt-get install -y --no-install-recommends git "
        "&& rm -rf /var/lib/apt/lists/*\n"
        'ENTRYPOINT ["python"]\nCMD ["-c", "import time; time.sleep(1800)"]\n'
    )
    (context / "Dockerfile.ci-local").write_text(dockerfile, encoding="utf-8")
    build = runner.run(
        "docker_build",
        [
            "docker",
            "build",
            "-f",
            str(context / "Dockerfile.ci-local"),
            "-t",
            image,
            str(context),
        ],
        required,
        timeout=1200,
    )
    if build["status"] != "PASS":
        return "FAIL" if build["status"] == "FAIL" else "BLOCKED"
    resources = []
    try:
        for name, command, resource in (
            (
                "docker_network",
                ["docker", "network", "create", "--internal", network],
                ("network", network),
            ),
            (
                "docker_database",
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    database,
                    "--network",
                    network,
                    "--network-alias",
                    "db",
                    "--tmpfs",
                    "/var/lib/postgresql/data",
                    "-e",
                    "POSTGRES_HOST_AUTH_METHOD=trust",
                    "-e",
                    "POSTGRES_USER=sapi",
                    "-e",
                    "POSTGRES_DB=sapi_db",
                    "postgis/postgis:15-3.4",
                ],
                ("container", database),
            ),
        ):
            # Record name before launch so a timeout cannot leak an owned container.
            resources.append(resource)
            if runner.run(name, command, required)["status"] != "PASS":
                return "BLOCKED"
        ready = False
        for _ in range(30):
            check = subprocess.run(
                [
                    "docker",
                    "exec",
                    database,
                    "pg_isready",
                    "-U",
                    "sapi",
                    "-d",
                    "sapi_db",
                ],
                capture_output=True,
                env=runner.env,
                timeout=10,
            )
            if check.returncode == 0:
                ready = True
                break
            time.sleep(1)
        runner.steps.append(
            step(
                "docker_database_ready",
                "PASS" if ready else "BLOCKED",
                required=required,
            )
        )
        if not ready:
            return "BLOCKED"
        if (
            runner.run(
                "docker_copy_schema",
                [
                    "docker",
                    "cp",
                    str(context / "docker/initdb"),
                    database + ":/tmp/ci-initdb",
                ],
                required,
            )["status"]
            != "PASS"
        ):
            return "BLOCKED"
        # Preserve CI's psql options/order. Its lack of ON_ERROR_STOP is documented.
        runner.run(
            "docker_schema",
            [
                "docker",
                "exec",
                database,
                "sh",
                "-c",
                'for f in /tmp/ci-initdb/*.sql; do psql -U sapi -d sapi_db -f "$f"; done',
            ],
            required,
        )
        resources.append(("container", application))
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            application,
            "--network",
            network,
            "-e",
            "PYTHON_DOTENV_DISABLED=1",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "DATABASE_URL=postgresql://sapi@db:5432/sapi_db",
            "-e",
            "DATABASE_URL_DIRECT=postgresql://sapi@db:5432/sapi_db",
            "--entrypoint",
            "python",
            image,
            "-c",
            "import time; time.sleep(1800)",
        ]
        if runner.run("docker_test_container", command, required)["status"] != "PASS":
            return "BLOCKED"
        prefix = ["docker", "exec", application]
        runner.run(
            "docker_format",
            prefix + ["black", "--check", "src", "app", "tests"],
            required,
        )
        runner.run(
            "docker_lint",
            prefix
            + [
                "flake8",
                "src",
                "app",
                "tests",
                "--max-line-length=100",
                "--extend-ignore=E203,W503",
            ],
            required,
        )
        runner.run(
            "docker_tests",
            prefix
            + [
                "pytest",
                "--junitxml=/tmp/ci-junit.xml",
                "--cov-report=json:/tmp/ci-coverage.json",
            ],
            required,
        )
        for remote, local in (
            ("/tmp/ci-junit.xml", "docker-junit.xml"),
            ("/tmp/ci-coverage.json", "docker-coverage.json"),
        ):
            runner.run(
                "copy_" + local.replace(".", "_"),
                [
                    "docker",
                    "cp",
                    application + ":" + remote,
                    str(runner.output / local),
                ],
                required,
            )
        try:
            metrics = pytest_metrics(
                runner.output / "docker-junit.xml",
                runner.output / "docker-coverage.json",
            )
            (runner.output / "docker-metrics.json").write_text(
                json.dumps(metrics, indent=2), encoding="utf-8"
            )
            runner.steps.append(step("docker_metrics", "PASS", metrics, required))
        except (OSError, ValueError, KeyError):
            runner.steps.append(step("docker_metrics", "BLOCKED", required=required))
    finally:
        for kind, name in reversed(resources):
            command = (
                ["docker", "rm", "-f", "-v", name]
                if kind == "container"
                else ["docker", "network", "rm", name]
            )
            # -v only removes anonymous volumes of this uniquely owned test container.
            runner.run("cleanup_" + name, command, required=True, timeout=30)
    statuses = [s["status"] for s in runner.steps[start_index:]]
    return (
        "FAIL" if "FAIL" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS"
    )
