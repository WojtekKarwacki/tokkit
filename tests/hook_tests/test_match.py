"""Tests for command-to-hint pattern matching."""

import pytest
from tokkit_hook.match import match_command


class TestGitCommands:
    def test_git_diff(self):
        assert match_command("git diff") == "git-diff"

    def test_git_diff_with_args(self):
        assert match_command("git diff HEAD~1") == "git-diff"

    def test_git_status(self):
        assert match_command("git status") == "git-status"

    def test_git_log(self):
        assert match_command("git log --oneline") == "git-log"

    def test_git_show(self):
        assert match_command("git show HEAD") == "git-show"

    def test_git_blame(self):
        assert match_command("git blame src/main.py") == "git-blame"

    def test_git_branch(self):
        assert match_command("git branch -a") == "git-branch"

    def test_git_stash_list(self):
        assert match_command("git stash list") == "git-stash"


class TestPythonCommands:
    def test_pytest(self):
        assert match_command("pytest") == "pytest"

    def test_pytest_with_args(self):
        assert match_command("pytest tests/ -v") == "pytest"

    def test_python_m_pytest(self):
        assert match_command("python -m pytest") == "pytest"

    def test_python3_m_pytest(self):
        assert match_command("python3 -m pytest tests/") == "pytest"

    def test_ruff_check(self):
        assert match_command("ruff check .") == "ruff"

    def test_ruff_dot(self):
        assert match_command("ruff .") == "ruff"

    def test_mypy(self):
        assert match_command("mypy src/") == "mypy"

    def test_pip_list(self):
        assert match_command("pip list") == "pip-list"

    def test_pip_freeze(self):
        assert match_command("pip freeze") == "pip-freeze"

    def test_pip_install(self):
        assert match_command("pip install requests") == "pip"


class TestJSCommands:
    def test_npx_jest(self):
        assert match_command("npx jest") == "jest"

    def test_yarn_jest(self):
        assert match_command("yarn jest --watch") == "jest"

    def test_eslint(self):
        assert match_command("eslint src/") == "eslint"

    def test_npx_eslint(self):
        assert match_command("npx eslint .") == "eslint"

    def test_tsc(self):
        assert match_command("tsc --noEmit") == "tsc"

    def test_npm_test(self):
        assert match_command("npm test") == "npm"

    def test_npm_run(self):
        assert match_command("npm run build") == "npm"


class TestDockerCommands:
    def test_docker_compose(self):
        assert match_command("docker compose up") == "docker-compose"

    def test_docker_compose_hyphen(self):
        assert match_command("docker-compose ps") == "docker-compose"

    def test_docker_ps(self):
        assert match_command("docker ps") == "docker-ps"

    def test_docker_images(self):
        assert match_command("docker images") == "docker-images"

    def test_docker_logs(self):
        assert match_command("docker logs mycontainer") == "docker-logs"


class TestKubernetes:
    def test_kubectl_get(self):
        assert match_command("kubectl get pods") == "kubectl"

    def test_kubectl_describe(self):
        assert match_command("kubectl describe pod mypod") == "kubectl"

    def test_kubectl_logs(self):
        assert match_command("kubectl logs mypod") == "kubectl"


class TestShellCommands:
    def test_grep_r(self):
        assert match_command("grep -r 'foo' .") == "grep"

    def test_grep_rn(self):
        assert match_command("grep -rn pattern src/") == "grep"

    def test_rg(self):
        assert match_command("rg foo src/") == "rg"

    def test_ls(self):
        assert match_command("ls") == "ls"

    def test_ls_with_args(self):
        assert match_command("ls -la") == "ls"

    def test_tree(self):
        assert match_command("tree") == "tree"

    def test_find(self):
        assert match_command("find . -name '*.py'") == "find"

    def test_gh_pr(self):
        assert match_command("gh pr list") == "gh"

    def test_gh_issue(self):
        assert match_command("gh issue view 42") == "gh"

    def test_gh_run(self):
        assert match_command("gh run list") == "gh"

    def test_env(self):
        assert match_command("env") == "env"

    def test_printenv(self):
        assert match_command("printenv PATH") == "env"


class TestExclusions:
    def test_cat_source_py(self):
        assert match_command("cat src/main.py") is None

    def test_cat_source_js(self):
        assert match_command("cat app/index.js") is None

    def test_cat_source_ts(self):
        assert match_command("cat lib/types.ts") is None

    def test_bat_passthrough(self):
        assert match_command("bat src/main.py") is None

    def test_vim_passthrough(self):
        assert match_command("vim foo.txt") is None

    def test_nvim_passthrough(self):
        assert match_command("nvim .")is None

    def test_pipe_passthrough(self):
        assert match_command("git diff | head -20") is None

    def test_redirect_passthrough(self):
        assert match_command("git log > out.txt") is None

    def test_unknown_command(self):
        assert match_command("some-custom-tool --flag") is None
