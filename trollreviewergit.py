from trollreview import ReviewType
from trollreviewer import ChangeReviewer

import logging
import requests
import sys
import urllib

logger = logging.getLogger(__name__)

class GitChangeReviewer(ChangeReviewer):
  DEFAULT_REMOTE='git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git'
  DEFAULT_BRANCH='master'

  def __init__(self, reviewer, change, dry_run):
    super().__init__(reviewer, change, dry_run)
    self.upstream_sha = None

  @staticmethod
  def can_review_change(change, days_since_last_review):
    raise NotImplementedError()

  def get_cgit_web_link_path(self):
    return '/commit/?head={}&id={}'.format(self.upstream_sha['branch'],
                                           self.upstream_sha['sha'])

  def get_upstream_web_link(self):
    remote = self.upstream_sha['remote']
    parsed = urllib.parse.urlparse(remote)
    l = 'https://'

    if parsed.netloc == 'git.kernel.org':
      l += parsed.netloc
      l += parsed.path
      l += self.get_cgit_web_link_path()
    elif 'github.com' in parsed.netloc:
      l += parsed.netloc
      l += parsed.path
      l += '/commit/{}'.format(self.upstream_sha['sha'])
    elif 'anongit' in parsed.netloc:
      l += parsed.netloc.replace('anongit', 'cgit')
      l += parsed.path
      l += self.get_cgit_web_link_path()
    elif 'git.infradead.org' in parsed.netloc:
      l = 'http://' # whomp whomp
      l += parsed.netloc
      l += parsed.path
      l += '/commit/{}'.format(self.upstream_sha['sha'])
    elif 'linuxtv.org' in parsed.netloc:
      l += 'git.linuxtv.org'
      l += parsed.path
      l += self.get_cgit_web_link_path()
    else:
      logger.error('Could not parse web link for {}'.format(remote))
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

  def add_invalid_hash_review(self, hashes):
    msg = self.strings.INVALID_HASH_HEADER
    for h in hashes:
      remote_str = h['remote']
      if h['branch']:
        remote_str += ' branch {}'.format(h['branch'])
      msg += self.strings.INVALID_HASH_LINE.format(h['sha'], remote_str)
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
    upstream_shas = self.reviewer.get_cherry_pick_shas_from_patch(
                                    self.gerrit_patch)
    if not upstream_shas:
      self.add_missing_hash_review()
      return

    upstream_sha = None
    for s in reversed(upstream_shas):
      if not s['remote']:
        s['remote'] = self.DEFAULT_REMOTE
      if not s['branch']:
        s['branch'] = self.DEFAULT_BRANCH
      s['remote_name'] = self.reviewer.generate_remote_name(s['remote'])

      self.reviewer.fetch_remote(s['remote_name'], s['remote'], s['branch'])

      if not self.reviewer.is_sha_in_branch(s['sha'], s['remote_name'],
                                            s['branch']):
        continue

      self.upstream_patch = self.reviewer.get_commit_from_sha(s['sha'])
      self.upstream_sha = s

    if not self.upstream_patch:
      self.add_invalid_hash_review(upstream_shas)
      return

  def is_sha_in_mainline(self):
    if not self.upstream_sha:
      return False

    remote_name = self.reviewer.generate_remote_name(self.DEFAULT_REMOTE)
    if remote_name != self.upstream_sha['remote_name']:
        self.reviewer.fetch_remote(remote_name, self.DEFAULT_REMOTE,
                                   self.DEFAULT_BRANCH)
    return self.reviewer.is_sha_in_branch(self.upstream_sha['sha'], remote_name,
                                          self.DEFAULT_BRANCH)

  def get_patches(self):
    super().get_patches()

    if self.upstream_patch and self.upstream_sha:
      fixes_ref = self.reviewer.find_fixes_reference(
                                  self.upstream_sha['sha'],
                                  self.upstream_sha['remote_name'],
                                  self.upstream_sha['branch'])
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
