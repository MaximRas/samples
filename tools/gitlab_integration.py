import logging
import re

from gitlab import Gitlab
from gitlab.v4.objects.issues import ProjectIssue
import pytest
from requests.exceptions import ConnectionError

from tools import config
from tools.retry import retry

log = logging.getLogger(__name__)
_gl = None

_cache = {}

project_path_to_id = {
    'client/metapix-frontend-app': 58,
    'engine/http-api/auth-manager': 39,
    'engine/http-api/layout-manager': 37,
    'engine/http-api/notification-manager': 38,
    'engine/http-api/object-management/object-manager': 36,
    'whole-project-tasks': 72,
    'engine/http-api/device-manager': 28,
    'engine/meta-receiver': 24,
    'license-server/web-app': 43,
}


class GitlabIssueException(Exception):
    pass


@retry(ConnectionError)
def get_gitlab_handler() -> Gitlab:
    global _gl

    if _gl is None:
        _gl = Gitlab(
            config.user_config["gitlab"]["host"],
            private_token=config.user_config["gitlab"]["private_token"],
        )
        _gl.auth()
    return _gl


def get_issue_by_path(path: str) -> ProjectIssue:
    """
    Path is the part of url which after "metapix-cloud/"
    For example: client/metapix-frontend-app/-/issues/705
    """
    if path in _cache:
        return _cache[path]

    gl = get_gitlab_handler()
    project_path, issue_id = re.findall(r"(.*)/-/issues/(\d+)", path)[0]
    proj = gl.projects.get(id=project_path_to_id[project_path])
    issue = proj.issues.get(id=int(issue_id))
    log.info(f"{path} is {issue.state}. Labels: {issue.labels}")

    # check issue state
    if issue.state == "closed" and "Status::Duplicate" in issue.labels:
        raise GitlabIssueException(f"{path} is duplicate. Please fix this link")
    if issue.state == "closed" and issue.moved_to_id:
        raise GitlabIssueException(f"{path} was moved")

    _cache[path] = issue
    return issue


def url_to_path(url: str) -> str:
    BASE_URL = config.user_config["gitlab"]["host"] + "metapix-cloud/"
    assert url.startswith(BASE_URL)
    path = url[len(BASE_URL):]
    return path


def raise_if_fixed(path):
    issue = get_issue_by_path(path)
    if issue.state == "closed":
        raise GitlabIssueException(f"{path} has been fixed")


def is_fixed(*args, **kwargs):
    try:
        raise_if_fixed(*args, **kwargs)
    except GitlabIssueException:
        return True
    else:
        return False


def skip_if_opened(path, warn_if_not_opened=True):
    issue = get_issue_by_path(path)
    if issue.state == "opened":
        if "Status::QA" in issue.labels:
            # consider issue is closed
            log.info(f"{path} is in QA")
            return
        pytest.skip(f"Issue {path} is {issue.state}")
    if warn_if_not_opened:
        log.warning(f'Is not opened any more: {path}')
