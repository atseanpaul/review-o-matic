from reviewer import CommitRef
from trollreview import ReviewType
from trollreviewer import ChangeReviewer

import logging
import re
import requests
import sys
import urllib

logger = logging.getLogger('rom.troll.reviewer.git')

class GitChangeReviewer(ChangeReviewer):
  def __init__(self, project, reviewer, change, msg_limit, dry_run):
    super().__init__(project, reviewer, change, msg_limit, dry_run)
    self.upstream_ref = None

  @staticmethod
  def can_review_change(project, change, days_since_last_review):
    raise NotImplementedError()

  def get_cgit_web_link_path(self):
    ret = '/commit/?id={}'.format(self.upstream_ref.sha)
    if self.upstream_ref.branch:
      return ret + '&head={}'.format(self.upstream_ref.branch)
    if self.upstream_ref.tag:
      return ret + '&tag={}'.format(self.upstream_ref.tag)
    return ret

  def get_upstream_web_link(self):
    remote = self.upstream_ref.remote
    parsed = urllib.parse.urlparse(remote)
    l = 'https://'

    if parsed.netloc == 'git.kernel.org':
      l += parsed.netloc
      l += parsed.path
      l += self.get_cgit_web_link_path()
    elif 'github.com' in parsed.netloc:
      l += parsed.netloc
      l += re.sub('\.git$', '', parsed.path)
      l += '/commit/{}'.format(self.upstream_ref.sha)
    elif 'anongit' in parsed.netloc:
      l += parsed.netloc.replace('anongit', 'cgit')
      l += parsed.path
      l += self.get_cgit_web_link_path()
    elif 'git.infradead.org' in parsed.netloc:
      l = 'http://' # whomp whomp
      l += parsed.netloc
      l += parsed.path
      l += '/commit/{}'.format(self.upstream_ref.sha)
    elif 'linuxtv.org' in parsed.netloc:
      l += 'git.linuxtv.org'
      l += parsed.path
      l += self.get_cgit_web_link_path()
    elif 'w1.fi' in parsed.netloc:
      tree = re.match('/srv/git/(.*)\.git$', parsed.path)
      if not tree:
        logger.warning('Unexpected w1.fi remote {}'.format(remote))
        return
      l += 'w1.fi'
      l += '/cgit/{}'.format(tree.group(1))
      l += self.get_cgit_web_link_path()
    else:
      logger.warning('Could not parse web link for {}'.format(remote))
      return

    r = requests.get(l)
    if r.status_code == 200:
      self.review_result.add_web_link(l)
    else:
      logger.error('Got {} status for {}'.format(r.status_code, l))
      return


  def add_missing_hash_review(self):
      msg = self.strings.MISSING_HASH_HEADER
      msg += self.strings.HASH_EXAMPLE
      msg += self.strings.MISSING_HASH_FOOTER
      self.review_result.add_review(ReviewType.MISSING_HASH, msg, vote=-1,
                                    notify=True)

  def add_invalid_hash_review(self, refs):
    msg = self.strings.INVALID_HASH_HEADER
    for r in refs:
      msg += self.strings.INVALID_HASH_LINE.format(str(r))
    msg += self.strings.INVALID_HASH_FOOTER
    msg += self.strings.HASH_EXAMPLE
    self.review_result.add_review(ReviewType.INVALID_HASH, msg, vote=-1,
                                  notify=True)

  def add_fixes_ref_review(self, fixes_ref):
    msg = self.strings.FOUND_FIXES_REF_HEADER
    for l in fixes_ref.splitlines():
      msg += self.strings.FIXES_REF_LINE.format(l)
    msg += self.strings.FIXES_REF_FOOTER
    self.review_result.add_review(ReviewType.FIXES_REF, msg, notify=True)

  def add_altered_upstream_review(self):
    msg = self.strings.DIFFERS_HEADER
    msg += self.strings.ALTERED_UPSTREAM
    msg += self.format_diff()
    self.review_result.add_review(ReviewType.ALTERED_UPSTREAM,
                                  msg, vote=-1, notify=True)

  def add_backport_diff_review(self):
    msg = self.strings.DIFFERS_HEADER
    msg += self.strings.BACKPORT_DIFF
    msg += self.format_diff()
    self.review_result.add_review(ReviewType.BACKPORT, msg)

  def get_upstream_patch(self):
    upstream_refs = CommitRef.refs_from_patch(self.gerrit_patch)
    if not upstream_refs:
      self.add_missing_hash_review()
      # TODO: Remove me when Issue #19 is fixed
      logger.error('Adding missing hash review for change {}, patch="{}"'.format(self.change, self.gerrit_patch))
      return

    for r in reversed(upstream_refs):
      if not r.remote:
        r.set_remote(self.project.mainline_repo)
      if not r.branch and not r.tag:
        r.branch = self.project.mainline_branch

      self.reviewer.fetch_remote(r)
      if not self.reviewer.is_sha_in_branch(r):
        continue

      self.upstream_patch = self.reviewer.get_commit_from_sha(r)
      self.upstream_ref = r

    if not self.upstream_patch:
      self.add_invalid_hash_review(upstream_refs)
      return

  def is_sha_in_mainline(self):
    if not self.upstream_ref:
      return False

    mainline_ref = CommitRef(sha=self.upstream_ref.sha,
                             remote=self.project.mainline_repo,
                             branch=self.project.mainline_branch)

    if mainline_ref.remote_name != self.upstream_ref.remote_name:
        self.reviewer.fetch_remote(mainline_ref)

    return self.reviewer.is_sha_in_branch(mainline_ref, skip_err=True)

  def get_patches(self):
    super().get_patches()

    if self.upstream_patch and self.upstream_ref:
      fixes_ref = self.reviewer.find_fixes_reference(self.upstream_ref)
      if fixes_ref:
        self.add_fixes_ref_review(fixes_ref)

  def compare_patches_backport(self):
    if len(self.diff) == 0:
      self.add_clean_backport_review()
    else:
      self.add_backport_diff_review()

  def compare_patches_clean(self):
    if len(self.diff):
      self.add_altered_upstream_review()
    else:
      self.add_successful_review()
