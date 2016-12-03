from __future__ import absolute_import
from __future__ import unicode_literals

import contextlib
import io
import os.path

from aspy.yaml import ordered_dump
from aspy.yaml import ordered_load

import pre_commit.constants as C
from pre_commit.clientlib.validate_config import CONFIG_JSON_SCHEMA
from pre_commit.clientlib.validate_config import validate_config_extra
from pre_commit.clientlib.validate_manifest import load_manifest
from pre_commit.jsonschema_extensions import apply_defaults
from pre_commit.ordereddict import OrderedDict
from pre_commit.util import cmd_output
from pre_commit.util import cwd
from testing.util import copy_tree_to_path
from testing.util import get_head_sha
from testing.util import get_resource_path


def git_dir(tempdir_factory):
    path = tempdir_factory.get()
    with cwd(path):
        cmd_output('git', 'init')
    return path


def make_repo(tempdir_factory, repo_source):
    path = git_dir(tempdir_factory)
    copy_tree_to_path(get_resource_path(repo_source), path)
    with cwd(path):
        cmd_output('git', 'add', '.')
        cmd_output('git', 'commit', '-m', 'Add hooks')
    return path


@contextlib.contextmanager
def modify_manifest(path):
    """Modify the manifest yielded by this context to write to hooks.yaml."""
    manifest_path = os.path.join(path, C.MANIFEST_FILE)
    manifest = ordered_load(io.open(manifest_path).read())
    yield manifest
    with io.open(manifest_path, 'w') as manifest_file:
        manifest_file.write(ordered_dump(manifest, **C.YAML_DUMP_KWARGS))
    cmd_output('git', 'commit', '-am', 'update hooks.yaml', cwd=path)


@contextlib.contextmanager
def modify_config(path='.', commit=True):
    """Modify the config yielded by this context to write to
    .pre-commit-config.yaml
    """
    config_path = os.path.join(path, C.CONFIG_FILE)
    config = ordered_load(io.open(config_path).read())
    yield config
    with io.open(config_path, 'w', encoding='UTF-8') as config_file:
        config_file.write(ordered_dump(config, **C.YAML_DUMP_KWARGS))
    if commit:
        cmd_output('git', 'commit', '-am', 'update config', cwd=path)


def config_with_local_hooks():
    return OrderedDict((
        ('repo', 'local'),
        ('hooks', [OrderedDict((
            ('id', 'do_not_commit'),
            ('name', 'Block if "DO NOT COMMIT" is found'),
            ('entry', 'DO NOT COMMIT'),
            ('language', 'pcre'),
            ('files', '^(.*)$'),
        ))])
    ))


def make_config_from_repo(repo_path, sha=None, hooks=None, check=True):
    manifest = load_manifest(os.path.join(repo_path, C.MANIFEST_FILE))
    config = OrderedDict((
        ('repo', repo_path),
        ('sha', sha or get_head_sha(repo_path)),
        (
            'hooks',
            hooks or [OrderedDict((('id', hook['id']),)) for hook in manifest],
        ),
    ))

    if check:
        wrapped_config = apply_defaults([config], CONFIG_JSON_SCHEMA)
        validate_config_extra(wrapped_config)
        return wrapped_config[0]
    else:
        return config


def read_config(directory, config_file=C.CONFIG_FILE):
    config_path = os.path.join(directory, config_file)
    config = ordered_load(io.open(config_path).read())
    return config


def write_config(directory, config, config_file=C.CONFIG_FILE):
    if type(config) is not list:
        assert type(config) is OrderedDict
        config = [config]
    with io.open(os.path.join(directory, config_file), 'w') as outfile:
        outfile.write(ordered_dump(config, **C.YAML_DUMP_KWARGS))


def add_config_to_repo(git_path, config, config_file=C.CONFIG_FILE):
    write_config(git_path, config, config_file=config_file)
    with cwd(git_path):
        cmd_output('git', 'add', config_file)
        cmd_output('git', 'commit', '-m', 'Add hooks config')
    return git_path


def make_consuming_repo(tempdir_factory, repo_source):
    path = make_repo(tempdir_factory, repo_source)
    config = make_config_from_repo(path)
    git_path = git_dir(tempdir_factory)
    return add_config_to_repo(git_path, config)
