"""
Generate the mirrors layout.
"""
from __future__ import annotations

import json
import sys

import jinja2.sandbox
import yaml
from invoke import task

from . import utils


@task
def generate(ctx, ghcr_org="saltstack/salt-ci-containers"):
    """
    Generate the container mirrors.
    """
    ctx.cd(utils.REPO_ROOT)
    containers_path = utils.REPO_ROOT / "containers.yml"
    if containers_path.exists():
        with containers_path.open("r") as rfh:
            loaded_containers = yaml.safe_load(rfh.read())
    else:
        loaded_containers = {}

    custom_containers = {}
    mirror_containers = {}
    for name, details in loaded_containers.items():
        if "name" in details:
            custom_containers[name] = details
        else:
            mirror_containers[name] = details

    main_readme = utils.REPO_ROOT / "README.md"
    main_readme_contents = []

    for line in main_readme.read_text().splitlines():
        if line == "<!-- included-containers -->":
            main_readme_contents.append(line)
            main_readme_contents.append("\n## Custom")
            break
        else:
            main_readme_contents.append(line)

    ctx.run("git rm -f mirrors/*/*.Dockerfile .github/workflows/*.yml", warn=True, hide=True)
    for path in utils.REPO_ROOT.joinpath("mirrors").glob("*"):
        if list(path.glob("*")) == [path / "README.md"]:
            ctx.run(f"git rm -rf {path}", warn=True, hide=True)

    containers = list(sorted(custom_containers.items())) + list(sorted(mirror_containers.items()))
    mirrors_header_included = False
    for name, details in containers:
        if "name" in details:
            is_mirror = False
        else:
            is_mirror = True

        if is_mirror:
            if not mirrors_header_included:
                main_readme_contents.append("\n\n## Mirrors")
                mirrors_header_included = True

            utils.info(f"Generating {name} mirror...")
            container = details["container"]
            if "/" in container:
                org, container_name = container.rsplit("/", 1)
            else:
                org = "_"
                container_name = container

            source_tag = details.get("source_tag")
            container_dir = utils.REPO_ROOT / "mirrors" / container_name
            container_dir.mkdir(parents=True, exist_ok=True)
        else:
            org = ghcr_org
            container_name = details["name"]
            container_dir = utils.REPO_ROOT / "custom" / container_name

        readme = container_dir / "README.md"
        readme_contents = []
        for version in sorted(details["versions"]):
            utils.info(f"  Generating docker file for version {version}...")
            dockerfile = container_dir / f"{version}.Dockerfile"
            if is_mirror:
                readme_contents.append(
                    f"- [{container}:{version}](https://hub.docker.com/r/{org}/{container_name}"
                    f"/tags?name={source_tag or version}) - `ghcr.io/{ghcr_org}/{container_name}:{version}`"
                )
                with dockerfile.open("w") as wfh:
                    wfh.write(f"FROM {container}:{source_tag or version}\n")
            else:
                readme_contents.append(
                    f"- {container_name}:{version} - `ghcr.io/{ghcr_org}/{container_name}:{version}`"
                )

        with readme.open("w") as wfh:
            header = (
                f"# [![{name}]"
                f"(https://github.com/{ghcr_org}/actions/workflows/{container_name}.yml/badge.svg)]"
                f"(https://github.com/{ghcr_org}/actions/workflows/{container_name}.yml)\n"
            )
            main_readme_contents.append("\n")
            main_readme_contents.append(f"##{header}")
            main_readme_contents.extend(readme_contents)
            wfh.write(f"{header}\n")
            wfh.write("\n".join(readme_contents))
            wfh.write("\n")

        utils.info(f"  Generating Github workflow for {name} mirror...")
        env = jinja2.sandbox.SandboxedEnvironment()
        workflow_tpl = utils.REPO_ROOT / ".github" / "workflows" / ".container.template.j2"
        template = env.from_string(workflow_tpl.read_text())
        jinja_context = {
            "name": name,
            "repository_path": container_dir.relative_to(utils.REPO_ROOT),
            "is_mirror": is_mirror,
        }
        workflows_dir = utils.REPO_ROOT / ".github" / "workflows"
        workflow_path = workflows_dir / f"{container_name}.yml"
        workflow_path.write_text(template.render(**jinja_context).rstrip() + "\n")

    main_readme_contents[-1] = main_readme_contents[-1].rstrip()
    main_readme_contents.append("\n")

    with main_readme.open("w") as wfh:
        contents = "\n".join(main_readme_contents).rstrip()
        wfh.write(f"{contents}\n")

    ctx.run("git add mirrors/")
    ctx.run("git add .github/workflows/*.yml")


@task
def matrix(ctx, image, from_workflow=False):
    """
    Generate the container mirrors.
    """
    ctx.cd(utils.REPO_ROOT)
    mirrors_path = utils.REPO_ROOT / image

    output = []
    for fpath in mirrors_path.glob("*.Dockerfile"):
        output.append(
            {
                "name": f"{mirrors_path.name}:{fpath.stem}",
                "file": str(fpath.relative_to(utils.REPO_ROOT)),
            }
        )

    if from_workflow:
        print(f"::set-output name=dockerinfo::{json.dumps(output)}", flush=True, file=sys.stdout)
    else:
        print(json.dumps(output), flush=True, file=sys.stdout)
