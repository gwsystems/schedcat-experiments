"""A "hackish" git interface.

Intended to encode the software version in experiment output.
"""

import re
import os

from subprocess import Popen, PIPE

def path_to_repository():
    "Assumes this file is part of a git repository."
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def get_head(repo_dir=None):
    if repo_dir is None:
        repo_dir = path_to_repository()
    try:
        head_file = open(repo_dir + '/.git/HEAD')
        ref_str = head_file.readline()
        head_file.close()
    except IOError, msg:
        return None
    parsed = re.match('ref: ([^\n]*)\n', ref_str)
    if not parsed:
        return None
    try:
        ref_file = open(repo_dir + '/.git/' + parsed.group(1))
        sha      = ref_file.readline()
        ref_file.close()
    except IOError, msg:
        return None
    return sha.strip()

def modified_files(repo_dir=None):
    if repo_dir is None:
        repo_dir = path_to_repository() + '/.git'
    try:
        env = dict(os.environ)
        env['GIT_DIR'] = repo_dir
        git = Popen(['git', 'diff', '--name-only'],
                    env=env, stdout=PIPE)
        (out, err) = git.communicate()
    except OSError, msg:
        print 'modified_files(): ', msg
        return None
    files = out.strip()
    return files.split('\n') if files else []

def get_version_string(repo_dir=None):
    head     = get_head(repo_dir)
    modified = modified_files(repo_dir)
    return ("%s+" if modified else "%s") % head
