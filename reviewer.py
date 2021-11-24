import difflib
import enum
import logging
import re
import subprocess
import sys

logger = logging.getLogger('rom.reviewer')

class LineType(enum.Enum):
  GITDIFF = 'diff --git '
  INDEX = 'index '
  DELETED = 'deleted '
  ADDED = 'new file mode '
  FILE_OLD = '--- (?:a/)?(.*)'
  FILE_NEW = '\+\+\+ (?:b/)?(.*)'
  CHUNK = '@@ -?([0-9]+),?([0-9]+)? \+?([0-9]+),?([0-9]+)? @@(.*)'
  DIFF = '[+-]'
  SIMILARITY = 'similarity index ([0-9]+)%'
  RENAME = 'rename (from|to) (.*)'
  CONTEXT = ' '
  EMPTY = ''

class CallType(enum.Enum):
  CHECK_OUTPUT = 0
  CHECK_CALL = 1
  CALL = 2

class CommitRef(object):
  def __init__(self, sha, remote=None, branch=None, tag=None):
    self.sha = sha
    self.set_remote(remote)
    self.branch = branch
    self.tag = tag

  def set_remote(self, remote):
    self.remote = remote
    if self.remote:
      self.remote_name = re.sub('([a-z]*\://)|\W', '', self.remote, flags=re.I)
    else:
      self.remote_name = None

  def refs(self, use_remote=False):
    if use_remote and self.remote_name and self.branch:
      return '{}/{}'.format(self.remote_name, self.branch)
    if self.branch:
      return 'refs/heads/{}'.format(self.branch)
    if self.tag:
      return 'refs/tags/{}'.format(self.tag)
    return None

  def __str__(self):
    ret = 'sha={}'.format(self.sha[:12])
    if self.branch:
      ret += ' branch={}'.format(self.branch)
    if self.tag:
      ret += ' tag={}'.format(self.tag)
    if self.remote:
      ret += ' remote={}'.format(self.remote)
    return ret

  def __repr__(self):
    return self.__str__()

  @staticmethod
  def refs_from_patch(patch):
    # Helper pattern to match any character that isn't whitespace or )
    non_ws = '[^\)^\s]'

    # This has pattern has gotten a bit hard to parse, so i'll do my best.

    # Start with an opening paren and allow for whitespace
    pattern = '\((?:\s*)'

    # This is pretty easy, look the "cherry picked from commit" string taking
    # into account space or dash between cherry and picked, and allowing for
    # multiple spaces after commit.
    pattern += 'cherry.picked from commit\s*'

    # Then we grab the hexidecimal hash string. Everything after this is
    # optional.
    pattern += '([0-9a-f]*)'

    # Wrap the optional group in parens
    pattern += '('

    # Optionally gobble up everything (including newlines) until we hit the next
    # group. This allows for extra fluff in between the hash and URL (like an
    # extra 'from' as seen in http://crosreview.com/1537900). Instead of just .*
    # explicitly forbid matching ) since it could go looking through the source
    # for a URL (like in http://crosreview.com/1544916). Finally, use a
    # non-greedy algorithm to avoid gobbling the URL.
    pattern += '[^\)]*?'

    # This will match the remote url. It's pretty simple, just matches any
    # protocol (git://, http://, https://, madeup://) and then match all
    # non-whitespace characters, this is our remote.
    pattern += '([a-z]*\://{nws}*)'.format(nws=non_ws)

    # Now that we have the URL, eat any whitespace again
    pattern += '\s*'

    # The next run of non-whitespace characters could either be 'tag' or the
    # remote branch. Make it optional in case they want to use the default
    # remote branch
    pattern += '({nws}*)?'.format(nws=non_ws)

    # Eat more whitespace, yum!
    pattern += '\s*'

    # Finally, if this is a tag, parse the tag name
    pattern += '({nws}*)?'.format(nws=non_ws)

    # Close the optional paren around remote/branch
    pattern += ')?'

    # Finally, account for any trailing whitespace
    pattern += '\s*'

    # Close the paren
    pattern += '\)'

    regex = re.compile(pattern, flags=(re.I | re.MULTILINE | re.DOTALL))
    m = regex.findall(patch)
    if not m or not len(m):
      return None

    ret = []
    for s in m:
      if s[3] == 'tag' and s[4]:
        ret.append(CommitRef(sha=s[0], remote=s[2], tag=s[4]))
      else:
        ret.append(CommitRef(sha=s[0], remote=s[2], branch=s[3]))

    return ret

  @staticmethod
  def links_from_patch(patch):
    pattern = '\s*Link:\s+(\S+)'
    regex = re.compile(pattern)
    m = regex.findall(patch)
    if not m or not len(m):
      return None

    ret = []
    for s in m:
      ret.append(s)
    return ret

class Reviewer(object):
  MAX_CONTEXT = 5

  def __init__(self, verbose=False, chatty=False, git_dir=None):
    self.verbose = verbose
    self.chatty = chatty
    self.git_dir = git_dir
    if git_dir:
      self.git_cmd = ['git', '-C', git_dir ]
    else:
      self.git_cmd = ['git']

  def __strip_commit_msg(self, patch):
    regex = re.compile('diff --git ')
    for i, l in enumerate(patch):
      if regex.match(l):
        return patch[i:]

  def classify_line(self, line):
    for t in LineType:
      m = re.match(t.value, line)
      if m:
        return (t,m)
    return None

  def __strip_kruft(self, diff, context):
    ret = []
    ignore = [LineType.CHUNK, LineType.GITDIFF, LineType.INDEX,
              LineType.DELETED, LineType.ADDED, LineType.SIMILARITY,
              LineType.RENAME, LineType.EMPTY]
    include = [LineType.FILE_NEW, LineType.FILE_OLD, LineType.DIFF]
    ctx_buffer = []
    for l in diff:
      if not l:
        continue

      l_type,_ = self.classify_line(l)

      if self.chatty:
        logger.debug('%s- "%s"' % (l_type, l))

      if not l_type:
        logger.error('Could not classify line "{}"'.format(l))
        ctx_buffer = []
        continue

      if l_type == LineType.CONTEXT:
        ctx_buffer.append(l)
        continue

      # If we want to include context in the diffs, include the last N lines of
      # context we've collected
      if ctx_buffer and context:
        ret.extend(ctx_buffer[-context:])

      ctx_buffer = []

      if l_type in ignore:
        continue
      elif l_type in include:
        ret.append(l)
      else:
        logger.error('line_type not handled {}: {}'.format(l_type, l))

    if ctx_buffer and context:
      ret.extend(ctx_buffer[-context:])

    return ret

  def git(self, cmd, call_type, stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL, skip_err=False):
    run_cmd = self.git_cmd + cmd
    logger.debug('GIT: {}'.format(' '.join(run_cmd)))
    if call_type == CallType.CHECK_OUTPUT:
      return subprocess.check_output(run_cmd, stderr=stderr).decode('UTF-8')
    elif call_type == CallType.CHECK_CALL:
      try:
        subprocess.check_call(run_cmd, stdout=stdout, stderr=stderr)
        return 0
      except subprocess.CalledProcessError as e:
        if not skip_err:
          logger.exception('Exception running git: {}'.format(e))
          logger.error('FAIL: {}'.format(' '.join(run_cmd)))
          raise
        return e.returncode
    elif call_type == CallType.CALL:
      subprocess.call(run_cmd, stdout=stdout, stderr=stderr)
    else:
      raise ValueError('Invalid call type {}'.format(call_type))
    return None

  def find_fixes_reference(self, ref):
    cmd = ['log', '--format=oneline', '--abbrev-commit', '-i', '--grep',
           'Fixes:.*{}'.format(ref.sha[:8]), '{}..{}'.format(ref.sha,
                                                             ref.refs(True))]
    return self.git(cmd, CallType.CHECK_OUTPUT)

  def get_am_from_from_patch(self, patch):
    regex = re.compile('\(am from (http.*)\)', flags=re.I)
    m = regex.findall(patch)
    if not m or not len(m):
      return None
    return m

  def add_or_update_remote(self, ref):
    cmd = ['remote', 'set-url', ref.remote_name, ref.remote]
    ret = self.git(cmd, CallType.CHECK_CALL, skip_err=True)
    if ret == 0:
      return

    cmd = ['remote', 'add', ref.remote_name, ref.remote]
    ret = self.git(cmd, CallType.CHECK_CALL)
    if ret != 0:
      logger.error('Failed to add remote {} ({})', str(ref), ret)

  def fetch_remote(self, ref):
    logger.debug('Fetching {}'.format(str(ref)))

    self.add_or_update_remote(ref)

    cmd = ['fetch', '--prune', '--tags', ref.remote_name, ref.refs()]
    ret = self.git(cmd, CallType.CHECK_CALL, skip_err=True)
    if ret != 0:
      logger.error('Fetch remote ({}) failed: ({})'.format(str(ref), ret))

  def checkout(self, ref):
    cmd = ['checkout', ref]
    logger.debug("Running {}".format(" ".join(cmd)))

    self.git(cmd, CallType.CALL)

  def checkout_reset(self, path):
    cmd = ['checkout', '--', path]
    logger.debug('Running {}'.format(' '.join(cmd)))

    self.git(cmd, CallType.CALL)

  def get_commit_msg_from_sha(self, sha):
    cmd = ['log', '-1', sha]
    return self.git(cmd, CallType.CHECK_OUTPUT, stderr=None)

  def get_cherry_pick_sha_from_local_sha(self, local_sha):
    commit_message = self.get_commit_msg_from_sha(local_sha)

    # Use the last SHA found in the patch, since it's (probably) most recent,
    # and only return the SHA, not the remote/branch
    return CommitRef.refs_from_patch(commit_message)[-1].sha

  def get_links_from_local_sha(self, local_sha):
    commit_message = self.get_commit_msg_from_sha(local_sha)

    # Use the last SHA found in the patch, since it's (probably) most recent,
    # and only return the SHA, not the remote/branch
    return CommitRef.links_from_patch(commit_message)

  def get_commit_from_subject(self, subject, surrounding_commit=None):
    cmd = ['log', '-F', '--grep', subject, r'--format=%h %s']
    if surrounding_commit:
      cmd.append('{}~100..'.format(surrounding_commit))
    ret = self.git(cmd, CallType.CHECK_OUTPUT, stderr=None).strip()
    return ret.splitlines()

  def is_sha_in_branch(self, ref, skip_err=False):
    cmd = ['merge-base', '--is-ancestor', ref.sha, ref.refs(True)]
    try:
      ret = self.git(cmd, CallType.CHECK_CALL, skip_err=True)
      return ret == 0
    except Exception as e:
      if not skip_err:
        logger.error('git merge-base failed {}: ({})'.format(str(ref), str(e)))
        logger.exception('Exception checking sha: {}'.format(e))
        raise

  def get_commit_from_sha(self, ref):
    cmd = ['show', '--minimal', '-U{}'.format(self.MAX_CONTEXT), r'--format=%B',
           ref.sha]
    ret = self.git(cmd, CallType.CHECK_OUTPUT, stderr=None)
    return ret

  def strip_special(self, string):
    return re.sub('([a-z]*\://)|\W', '', string, flags=re.I)

  def fetch_to_tmp_ref(self, remote, ref):
    stripped = '{}_{}'.format(self.strip_special(remote),
                              self.strip_special(ref))
    tmp_ref = 'refs/branches/{}'.format(stripped)
    cmd = ['fetch', '--prune', remote, '{}:{}'.format(ref, tmp_ref)]
    self.git(cmd, CallType.CHECK_CALL)
    return tmp_ref

  def delete_ref(self, ref):
    cmd = ['update-ref', '-d', ref]
    self.git(cmd, CallType.CHECK_CALL)

  def get_commit_from_remote(self, remote, ref):
    tmp_ref = self.fetch_to_tmp_ref(remote, ref)

    ret = self.get_commit_from_sha(CommitRef(sha=tmp_ref))

    self.delete_ref(tmp_ref)
    return ret

  def compare_diffs(self, a, b, context=0):
    if context > self.MAX_CONTEXT:
      raise ValueError('Invalid context given')

    a = a.split('\n')
    b = b.split('\n')

    # strip the commit messages
    a = self.__strip_commit_msg(a) or []
    b = self.__strip_commit_msg(b) or []
    a = self.__strip_kruft(a, context)
    b = self.__strip_kruft(b, context)

    files = {'new': '', 'old': ''}
    printed_files = False

    ret = []
    differ = difflib.Differ()
    for l in differ.compare(a, b):
      # strip the differ margin for analyzing the line
      line = l[2:]

      # if this is a file line, save the file for later printing
      l_type,_ = self.classify_line(line)
      if l_type == LineType.FILE_OLD:
        files['old'] = line
        continue # old always comes before new, so loop around to pick up new
      elif l_type == LineType.FILE_NEW:
        files['new'] = line
        printed_files = False

      # discard the differ '?' helper and unchanged lines
      if l[0] == '?' or not l[:2].strip():
        continue

      if not printed_files:
        ret.append(files['old'])
        ret.append(files['new'])
        printed_files = True

      # don't double print files
      if l_type == LineType.FILE_NEW or l_type == LineType.FILE_OLD:
        continue

      # add the change to the diff
      ret.append(l)

    return ret
