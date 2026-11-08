import tomllib

from django.conf import settings
from django.test import SimpleTestCase


def requirement_lines(path):
    with open(path, encoding="utf-8") as handle:
        return [
            line.strip()
            for line in handle
            if line.strip() and not line.lstrip().startswith(("#", "-"))
        ]


class DependencyManifestTests(SimpleTestCase):
    def test_pyproject_and_requirements_list_the_same_runtime_packages(self):
        with open(settings.BASE_DIR / "pyproject.toml", "rb") as handle:
            declared = tomllib.load(handle)["project"]["dependencies"]
        pinned = requirement_lines(settings.BASE_DIR / "requirements.txt")
        self.assertEqual(sorted(declared), sorted(pinned))

    def test_python_version_matches_the_docker_image(self):
        pinned = (settings.BASE_DIR / ".python-version").read_text().strip()
        dockerfile = (settings.BASE_DIR / "Dockerfile").read_text()
        self.assertIn("FROM python:%s-slim" % pinned, dockerfile)
