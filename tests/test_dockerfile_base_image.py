import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"


def _dockerfile_text() -> str:
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def test_python_base_image_uses_mirror_by_default():
    """云端构建匿名拉取 docker.io 会 429，默认必须走镜像加速地址。"""
    text = _dockerfile_text()

    arg_match = re.search(r"^ARG\s+PYTHON_IMAGE=(\S+)\s*$", text, re.MULTILINE)
    assert arg_match, "Dockerfile 需声明 ARG PYTHON_IMAGE 以便切换基础镜像源"

    default_image = arg_match.group(1)
    assert default_image.startswith("docker.m.daocloud.io/library/python:"), default_image


def test_all_from_lines_use_python_image_arg():
    text = _dockerfile_text()

    from_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("FROM ")]
    assert from_lines, "Dockerfile 缺少 FROM 指令"
    for line in from_lines:
        assert "${PYTHON_IMAGE}" in line, line
        assert "docker.io" not in line, line
