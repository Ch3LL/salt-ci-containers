"""
Generate the mirrors layout.
"""
from __future__ import annotations

import jinja2.sandbox
import yaml
from invoke import task

from . import utils


def _sort_containers(data):
    name, details = data
    print(1234, data)
    if "name" in data:
        return 1
    return -1


@task
def generate(ctx, ghcr_org="s0undt3ch-salt-ci"):
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
        if line == "## Included Containers":
            main_readme_contents.append(line)
            break
        else:
            main_readme_contents.append(line)

    for name, details in list(sorted(custom_containers.items())) + list(
        sorted(mirror_containers.items())
    ):
        if "name" in details:
            is_mirror = False
        else:
            is_mirror = True

        if is_mirror:
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
                header = header = f"# {name} mirrored containers\n"
                readme_contents.append(
                    f"- [{container}:{version}](https://hub.docker.com/r/{org}/{container_name}"
                    f"/tags?name={source_tag or version}) - `ghcr.io/{ghcr_org}/{container_name}:{version}`"
                )
                with dockerfile.open("w") as wfh:
                    wfh.write(f"FROM {container}:{source_tag or version}\n")
            else:
                header = f"# {name} containers\n"
                readme_contents.append(
                    f"- {container_name} - `ghcr.io/{ghcr_org}/{container_name}:{version}`"
                )

        with readme.open("w") as wfh:
            main_readme_contents.append("\n")
            main_readme_contents.append(f"##{header}")
            main_readme_contents.extend(readme_contents)
            wfh.write(f"{header}\n")
            wfh.write("\n".join(readme_contents))
            wfh.write("\n")

        utils.info(f"  Generating Github workflow for {name} mirror...")
        env = jinja2.sandbox.SandboxedEnvironment()
        workflow_tpl = utils.REPO_ROOT / ".github" / "workflows" / ".mirror.template.j2"
        template = env.from_string(workflow_tpl.read_text())
        jinja_context = {
            "name": name,
            "dockerfiles_path": dockerfile.relative_to(utils.REPO_ROOT),
            "repository_owner": ghcr_org,
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

    ctx.run("git add mirrors/ .github/workflows/*.yml")
