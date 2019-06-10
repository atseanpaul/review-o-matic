#!/usr/bin/env python3

from reviewer import Reviewer
from gerrit import Gerrit, GerritRevision, GerritMessage
from configchecker import KernelConfigChecker

import argparse
import datetime
import enum
import json
import random
import re
import requests
import sys
import time
import urllib

class ReviewStrings(object):
  HEADER='''
-- Automated message --
'''
  FOUND_ISSUES_HEADER_SINGLE='''
The following issue was found with your patch:
'''
  FOUND_ISSUES_HEADER_MULTIPLE='''
The following issues were found with your patch:
'''
  SUCCESS='''
No changes have been detected between this change and its upstream source!
'''
  POSITIVE_VOTE='''
This patch is certified {} by review-o-matic!
'''
  CLEAN_BACKPORT_HEADER='''
This change has a BACKPORT prefix, however it does not differ from its upstream
source. The BACKPORT prefix should be primarily used for patches which were
altered during the cherry-pick (due to conflicts or downstream inconsistencies).
'''
  MISSING_FIELDS='''
Your commit message is missing the following required field(s):
    {}
'''
  FEEDBACK_AFTER_ISSUES='''
Enough with the bad news! Here's some more feedback on your patch:
'''
  MISSING_HASH_HEADER='''
Your commit message is missing the upstream commit hash. It should be in the
form:
'''
  MISSING_HASH_FOOTER='''
Hint: Use the '-x' argument of git cherry-pick to add this automagically
'''
  INVALID_HASH_HEADER='''
The commit hash(es) you've provided in your commit message could not be found
upstream. The following hash/remote/branch tuple(s) were tried:
'''
  INVALID_HASH_LINE='''
  {}
    from remote {}
'''
  MISSING_AM='''
Your commit message is missing the patchwork URL. It should be in the
form:
    (am from https://patchwork.kernel.org/.../)
'''
  DIFFERS_HEADER='''
This patch differs from the source commit.
'''
  ALTERED_UPSTREAM='''
Since this is not labeled as BACKPORT, it shouldn't. Either this reviewing
script is incorrect (totally possible, pls send patches!), or something changed
when this was backported. If the backport required changes, please consider
using the BACKPORT label with a description of your downstream changes in your
commit message

Below is a diff of the upstream patch referenced in this commit message, vs this
patch.

'''
  ALTERED_FROMLIST='''
Changes have been detected between the patch on the list and this backport.
Since the diff algorithm used by the developer to generate this patch may
differ from the one used to review, this could be a false negative.

If the backport required changes to the FROMLIST patch, please consider adding
a BACKPORT label to your subject.

Below is the generated diff of the fromlist patch referenced in this commit
message vs this patch.

'''
  BACKPORT_FROMLIST='''
Below is the generated diff of the fromlist patch referenced in this commit
message vs this patch. This message is posted to make reviewing backports
easier.

Since the diff algorithm used by the developer to generate this patch may
differ from the one used to review, there is a higher chance that this diff is
incorrect. So take this with a grain of salt.

'''
  CLEAR_VOTES='''
Changes were detected between this patch and the upstream version referenced in
the commit message.

Comparing FROMLIST backports is less reliable than UPSTREAM/FROMGIT patches
since the diff algorithms can differ between developer machine and this
review script. As such, it's usually not worthwhile posting the diff. Looks like
you'll have to do this review the old fashioned way!
'''
  BACKPORT_DIFF='''
This is expected, and this message is posted to make reviewing backports easier.
'''
  FOUND_FIXES_REF_HEADER='''
 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
 !! NOTE: This patch has been referenced in the Fixes: tag of another commit. If
 !!       you haven't already, consider backporting the following patch[es]:'''
  FIXES_REF_LINE='''
 !!  {}'''
  FIXES_REF_FOOTER='''
 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
'''
  FOOTER='''
To learn more about backporting kernel patches to Chromium OS, check out:
https://chromium.googlesource.com/chromiumos/docs/+/master/kernel_faq.md#UPSTREAM_BACKPORT_FROMLIST_and-you

If you're curious about how this message was generated, head over to:
https://github.com/atseanpaul/review-o-matic

This link is not useful:
https://thats.poorly.run/
'''
  ISSUE_SEPARATOR='''
>>>>>>> Issue {}
'''
  FEEDBACK_SEPARATOR='''
>>>>>> Feedback {}
'''
  REVIEW_SEPARATOR='''
------------------
'''
  WEB_LINK='''
If you would like to view the upstream patch on the web, follow this link:
{}
'''

  SWAG = ['Frrrresh', 'Crisper Than Cabbage', 'Awesome', 'Ahhhmazing',
          'Cool As A Cucumber', 'Most Excellent', 'Eximious', 'Prestantious',
          'Supernacular', 'Bodacious', 'Blue Chip', 'Blue Ribbon', 'Cracking',
          'Dandy', 'Dynamite', 'Fab', 'Fabulous', 'Fantabulous',
          'Scrumtrulescent', 'First Class', 'First Rate', 'First String',
          'Five Star', 'Gangbusters', 'Grand', 'Groovy', 'HYPE', 'Jim-Dandy',
          'Snazzy', 'Marvelous', 'Nifty', 'Par Excellence', 'Peachy Keen',
          'PHAT', 'Prime', 'Prizewinning', 'Quality', 'Radical', 'Righteous',
          'Sensational', 'Slick', 'Splendid', 'Lovely', 'Stellar', 'Sterling',
          'Superb', 'Superior', 'Superlative', 'Supernal', 'Swell', 'Terrific',
          'Tip-Top', 'Top Notch', 'Top Shelf', 'Unsurpassed', 'Wonderful']

class UpstreamReviewStrings(ReviewStrings):
  HASH_EXAMPLE='''
    (cherry picked from commit <commit SHA>)
'''
  INVALID_HASH_FOOTER='''
Please double check your commit hash is valid in the upstream tree and the hash
is formatted properly in your commit message (see below):
'''
  CLEAN_BACKPORT_FOOTER='''
Consider changing your subject prefix to UPSTREAM to better reflect the
contents of this patch.
'''

class FromgitReviewStrings(ReviewStrings):
  HASH_EXAMPLE='''
    (cherry picked from commit <commit SHA>
     <remote git url> <remote git branch>)
'''
  INVALID_HASH_FOOTER='''
Please double check your commit hash is valid in the upstream tree, and please
fully specify the remote tree and branch for FROMGIT changes (see below):
'''
  CLEAN_BACKPORT_FOOTER='''
Consider changing your subject prefix to FROMGIT to better reflect the
contents of this patch.
'''

class FromlistReviewStrings(ReviewStrings):
  CLEAN_BACKPORT_FOOTER='''
Consider changing your subject prefix to FROMLIST to better reflect the
contents of this patch.
'''

class ChromiumReviewStrings(ReviewStrings):
  CONFIG_DIFFS='''
Just thought you might like to know the kernel configs have changed in the
following way:
'''

class ReviewType(enum.Enum):
  FIXES_REF = 'fixes_ref'
  MISSING_FIELDS = 'missing_fields'
  MISSING_HASH = 'missing_hash'
  MISSING_AM = 'missing_am'
  INVALID_HASH = 'invalid_hash'
  INCORRECT_PREFIX = 'incorrect_prefix'
  ALTERED_UPSTREAM = 'altered_upstream'
  BACKPORT = 'backport'
  SUCCESS = 'success'
  CLEAR_VOTES = 'clear_votes'
  KCONFIG_CHANGE = 'kconfig_change'

  def __str__(self):
    return self.value
  def __repr__(self):
    return str(self)


class ReviewResult(object):
  def __init__(self, change, strings, dry_run=False):
    self.change = change
    self.strings = strings
    self.vote = 0
    self.notify = False
    self.dry_run = dry_run
    self.issues = {}
    self.feedback = {}
    self.web_link = None

  def add_review(self, review_type, msg, vote=0, notify=False, dry_run=False):
    # Take the lowest negative, or the highest positive
    if vote < 0 or self.vote < 0:
      self.vote = min(self.vote, vote)
    elif vote > 0 or self.vote > 0:
      self.vote = max(self.vote, vote)
    else:
      self.vote = vote

    if vote < 0:
      self.issues[review_type] = msg
    else:
      self.feedback[review_type] = msg

    self.notify = self.notify or notify
    self.dry_run = self.dry_run or dry_run

  def add_web_link(self, link):
    self.web_link = link

  def generate_issues(self):
    num_issues = len(self.issues)
    if not num_issues:
      return ''

    if num_issues > 1:
      msg = self.strings.FOUND_ISSUES_HEADER_MULTIPLE
    else:
      msg = self.strings.FOUND_ISSUES_HEADER_SINGLE

    for j,i in enumerate(self.issues.values()):
      if num_issues > 1:
        msg += self.strings.ISSUE_SEPARATOR.format(j + 1)
      msg += i
    return msg

  def generate_feedback(self):
    num_feedback = len(self.feedback)
    if not num_feedback:
      return ''

    if len(self.issues):
      msg = self.strings.FEEDBACK_AFTER_ISSUES
    elif self.vote > 0:
      msg = self.strings.POSITIVE_VOTE.format(random.choice(self.strings.SWAG))
    else:
      msg = ''

    for j,f in enumerate(self.feedback.values()):
      if num_feedback > 1:
        msg += self.strings.FEEDBACK_SEPARATOR.format(j + 1)
      msg += f
    return msg

  def generate_review_message(self):
    msg = self.strings.HEADER
    msg += self.generate_issues()
    if len(self.issues) and len(self.feedback):
      msg += self.strings.REVIEW_SEPARATOR
    msg += self.generate_feedback()
    msg += self.strings.REVIEW_SEPARATOR
    if self.web_link:
      msg += self.strings.WEB_LINK.format(self.web_link)
    msg += self.strings.FOOTER
    return msg

class ChangeReviewer(object):
  GERRIT_REMOTE = 'cros'
  def __init__(self, reviewer, change, dry_run):
    self.reviewer = reviewer
    self.is_backport = 'BACKPORT' in change.subject
    self.is_fixup = 'FIXUP' in change.subject
    self.is_revert = change.subject.startswith('Revert ')
    self.change = change
    self.dry_run = dry_run
    self.gerrit_patch = None
    self.upstream_patch = None
    self.review_result = None
    self.strings = None
    self.diff = None

  @staticmethod
  def can_review_change(change):
    raise NotImplementedError()

  def format_diff(self):
    msg = ''
    for l in self.diff:
      msg += '  {}\n'.format(l)
    return msg

  def add_successful_review(self):
    msg = self.strings.SUCCESS.format(random.choice(self.strings.SWAG))
    self.review_result.add_review(ReviewType.SUCCESS, msg, vote=1)

  def add_clean_backport_review(self):
    msg = self.strings.CLEAN_BACKPORT_HEADER
    msg += self.strings.CLEAN_BACKPORT_FOOTER
    self.review_result.add_review(ReviewType.INCORRECT_PREFIX, msg, vote=-1,
                                  notify=True)

  def add_missing_fields_review(self, fields):
    missing = []
    if not fields['bug']:
      missing.append('BUG=')
    if not fields['test']:
      missing.append('TEST=')
    if not fields['sob']:
      cur_rev = self.change.current_revision
      missing.append('Signed-off-by: {} <{}>'.format(cur_rev.uploader_name,
                                                     cur_rev.uploader_email))

    msg = self.strings.MISSING_FIELDS.format(', '.join(missing))
    self.review_result.add_review(ReviewType.MISSING_FIELDS, msg, vote=-1,
                                  notify=True)

  def get_gerrit_patch(self):
    for i in range(0, 4):
      try:
        self.gerrit_patch = self.reviewer.get_commit_from_remote(
                                  self.GERRIT_REMOTE, self.change.current_revision.ref)
        return True
      except:
        continue
    raise ValueError('ERROR: Could not get gerrit patch {}\n'.format(
                                                      self.change))

  def get_upstream_patch(self):
    raise NotImplementedError()

  def get_upstream_web_link(self):
    return None

  def get_patches(self):
    self.get_gerrit_patch()
    self.get_upstream_patch()

  def validate_commit_message(self):
    cur_rev = self.change.current_revision
    fields={'sob':False, 'bug':False, 'test':False}
    sob_name_re = re.compile('Signed-off-by:\s+{}'.format(
                                cur_rev.uploader_name))
    sob_email_re = re.compile('Signed-off-by:.*?<{}>'.format(
                                cur_rev.uploader_email))
    for l in cur_rev.commit_message.splitlines():
      if l.startswith('BUG='):
        fields['bug'] = True
      elif l.startswith('TEST='):
        fields['test'] = True
      elif sob_name_re.match(l):
        fields['sob'] = True
      elif sob_email_re.match(l):
        fields['sob'] = True

    if not fields['bug'] or not fields['test'] or not fields['sob']:
      self.add_missing_fields_review(fields)

  def diff_patches(self, context=0):
    self.diff = self.reviewer.compare_diffs(self.upstream_patch,
                                            self.gerrit_patch, context=context)

  def compare_patches_clean(self):
    raise NotImplementedError()

  def compare_patches_backport(self):
    raise NotImplementedError()

  def compare_patches(self):
    if self.is_backport:
      # If a BACKPORT appears to be clean, increase the context to be sure
      # before suggesting switching to UPSTREAM prefix
      if len(self.diff) == 0:
        self.diff_patches(context=3)

      self.compare_patches_backport()
    else:
      self.compare_patches_clean()

  def review_patch(self):
    # Don't review these patches (yet)
    if self.is_fixup or self.is_revert:
      return None

    self.get_patches()
    self.validate_commit_message()
    if self.gerrit_patch and self.upstream_patch:
      self.diff_patches()
      self.compare_patches()

    if self.upstream_patch:
      self.get_upstream_web_link()

    if not self.review_result.issues and not self.review_result.feedback:
      return None
    return self.review_result

class GitChangeReviewer(ChangeReviewer):
  DEFAULT_REMOTE='git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git'
  def __init__(self, reviewer, change, dry_run):
    super().__init__(reviewer, change, dry_run)
    self.upstream_sha = None

  @staticmethod
  def can_review_change(change):
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
      sys.stderr.write(
            'ERROR: Could not parse web link for {}\n'.format(remote))
      return

    r = requests.get(l)
    if r.status_code == 200:
      self.review_result.add_web_link(l)
    else:
      sys.stderr.write('ERROR: Got {} status for {}\n'.format(r.status_code, l))
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
        s['branch'] = 'master'
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


class UpstreamChangeReviewer(GitChangeReviewer):
  def __init__(self, reviewer, change, dry_run):
    super().__init__(reviewer, change, dry_run)
    self.strings = UpstreamReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)

  @staticmethod
  def can_review_change(change):
    # labeled UPSTREAM or labeled BACKPORT
    return ('UPSTREAM' in change.subject or
            ('BACKPORT' in change.subject and
             'FROMGIT' not in change.subject and
             'FROMLIST' not in change.subject))


class FromgitChangeReviewer(GitChangeReviewer):
  def __init__(self, reviewer, change, dry_run):
    super().__init__(reviewer, change, dry_run)
    self.strings = FromgitReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)

  @staticmethod
  def can_review_change(change):
    return 'FROMGIT' in change.subject


class FromlistChangeReviewer(ChangeReviewer):
  def __init__(self, reviewer, change, dry_run):
    super().__init__(reviewer, change, dry_run)
    self.strings = FromlistReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)
    self.review_backports = False

  @staticmethod
  def can_review_change(change):
    return 'FROMLIST' in change.subject

  def add_missing_am_review(self, change):
    self.review_result.add_review(ReviewType.MISSING_AM,
                                  self.strings.MISSING_AM, vote=-1, notify=True)

  def add_altered_fromlist_review(self):
    msg = self.strings.ALTERED_FROMLIST
    msg += self.format_diff()
    self.review_result.add_review(ReviewType.ALTERED_UPSTREAM, msg)

  def add_fromlist_backport_review(self):
    msg = self.strings.BACKPORT_FROMLIST
    msg += self.format_diff()
    self.review_result.add_review(ReviewType.BACKPORT, msg)

  def add_clear_votes_review(self):
    msg = self.strings.CLEAR_VOTES
    self.review_result.add_review(ReviewType.CLEAR_VOTES, msg)

  def get_upstream_patch(self):
    patchwork_url = self.reviewer.get_am_from_from_patch(self.gerrit_patch)
    if not patchwork_url:
      self.add_missing_am_review(self.change)
      return

    for u in reversed(patchwork_url):
      try:
        self.upstream_patch = self.reviewer.get_commit_from_patchwork(u)
        break
      except:
        continue

    if not self.upstream_patch:
      sys.stderr.write(
        'ERROR: patch missing from patchwork, or patchwork host '
        'not whitelisted for {} ({})\n'.format(self.change,
                                               patchwork_url))
      return

  def compare_patches_clean(self):
    if len(self.diff) == 0:
      self.add_successful_review()
    elif self.review_backports:
      self.add_altered_fromlist_review()
    else:
      self.add_clear_votes_review()

  def compare_patches_backport(self):
    if len(self.diff) == 0:
      self.add_clean_backport_review()
    elif self.review_backports:
      self.add_fromlist_backport_review()
    else:
      self.add_clear_votes_review()

class ChromiumChangeReviewer(ChangeReviewer):
  def __init__(self, reviewer, change, dry_run, verbose):
    super().__init__(reviewer, change, dry_run)
    self.strings = ChromiumReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)
    self.review_backports = False
    self.verbose = verbose
    self.config_diff = None

  @staticmethod
  def can_review_change(change):
    return 'CHROMIUM' in change.subject

  def get_gerrit_patch(self):
    super().get_gerrit_patch()
    kconfigchecker = KernelConfigChecker(reviewer=self.reviewer,
                                         verbose=self.verbose)

    if kconfigchecker.is_config_change(self.gerrit_patch):
      self.config_diff = kconfigchecker.get_kernel_configs(self.GERRIT_REMOTE,
                                      self.change.current_revision.ref)

    if self.config_diff:
      self.add_config_change_review()

    return None

  def get_upstream_patch(self):
    return None

  def add_config_change_review(self):
    msg = self.strings.CONFIG_DIFFS
    msg += self.config_diff
    self.review_result.add_review(ReviewType.KCONFIG_CHANGE, msg)

class Troll(object):
  def __init__(self, url, args):
    self.url = url
    self.args = args
    self.gerrit = Gerrit(url)
    self.tag = 'autogenerated:review-o-matic'
    self.blacklist = {}
    self.stats = { str(ReviewType.SUCCESS): 0, str(ReviewType.BACKPORT): 0,
                   str(ReviewType.ALTERED_UPSTREAM): 0,
                   str(ReviewType.MISSING_FIELDS): 0,
                   str(ReviewType.MISSING_HASH): 0,
                   str(ReviewType.INVALID_HASH): 0,
                   str(ReviewType.MISSING_AM): 0,
                   str(ReviewType.INCORRECT_PREFIX): 0,
                   str(ReviewType.FIXES_REF): 0 }

  def inc_stat(self, review_type):
    if self.args.dry_run:
      return
    key = str(review_type)
    if not self.stats.get(key):
      self.stats[key] = 1
    else:
      self.stats[key] += 1

  def do_review(self, change, review):
    print('Review for change: {}'.format(change.url()))
    print('  Issues: {}, Feedback: {}, Vote:{}, Notify:{}'.format(
        review.issues.keys(), review.feedback.keys(), review.vote,
        review.notify))

    if review.dry_run:
      print(review.generate_review_message())
      print('------')
      return

    for i in review.issues:
      self.inc_stat(i)
    for f in review.feedback:
      self.inc_stat(f)
    self.gerrit.review(change, self.tag, review.generate_review_message(),
                       review.notify, vote_code_review=review.vote)

  def get_changes(self, prefix):
    message = '{}:'.format(prefix)
    after = datetime.date.today() - datetime.timedelta(days=5)
    changes = self.gerrit.query_changes(status='open', message=message,
                    after=after, project='chromiumos/third_party/kernel')
    return changes

  def add_change_to_blacklist(self, change):
    self.blacklist[change.number] = change.current_revision.number

  def is_change_in_blacklist(self, change):
    return self.blacklist.get(change.number) == change.current_revision.number

  def process_changes(self, changes):
    rev = Reviewer(git_dir=self.args.git_dir, verbose=self.args.verbose,
                   chatty=self.args.chatty)
    ret = 0
    for c in changes:
      if self.args.verbose:
        print('Processing change {}'.format(c.url()))

      # Blacklist if we've already reviewed this revision
      for m in c.messages:
        if m.tag == self.tag and m.revision_num == c.current_revision.number:
          self.add_change_to_blacklist(c)

      # Find a reviewer and blacklist if not found
      reviewer = None
      if FromlistChangeReviewer.can_review_change(c):
        reviewer = FromlistChangeReviewer(rev, c, self.args.dry_run)
      elif FromgitChangeReviewer.can_review_change(c):
        reviewer = FromgitChangeReviewer(rev, c, self.args.dry_run)
      elif UpstreamChangeReviewer.can_review_change(c):
        reviewer = UpstreamChangeReviewer(rev, c, self.args.dry_run)
      elif self.args.kconfig_hound and \
          ChromiumChangeReviewer.can_review_change(c):
        reviewer = ChromiumChangeReviewer(rev, c, self.args.dry_run,
                                          self.args.verbose)
      if not reviewer:
        self.add_change_to_blacklist(c)
        continue

      force_review = self.args.force_cl or self.args.force_all
      if not force_review and self.is_change_in_blacklist(c):
        continue

      result = reviewer.review_patch()
      if result:
        self.do_review(c, result)
        ret += 1

      self.add_change_to_blacklist(c)

    return ret

  def update_stats(self):
    if not self.args.dry_run and self.args.stats_file:
      with open(self.args.stats_file, 'wt') as f:
        json.dump(self.stats, f)
    print('--')
    summary = '  Summary: '
    total = 0
    for k,v in self.stats.items():
      summary += '{}={} '.format(k,v)
      total += v
    summary += 'total={}'.format(total)
    print(summary)
    print('')

  def run(self):
    if self.args.force_cl:
      c = self.gerrit.get_change(self.args.force_cl)
      print('Force reviewing change  {}'.format(c))
      self.process_changes([c])
      return

    if self.args.stats_file:
      try:
        with open(self.args.stats_file, 'rt') as f:
          self.stats = json.load(f)
      except FileNotFoundError:
        self.update_stats()

    prefixes = ['UPSTREAM', 'BACKPORT', 'FROMGIT', 'FROMLIST']
    if self.args.kconfig_hound:
      prefixes += ['CHROMIUM']

    while True:
      try:
        did_review = 0
        for p in prefixes:
          changes = self.get_changes(p)
          if self.args.verbose:
            print('{} changes for prefix {}'.format(len(changes), p))
          did_review += self.process_changes(changes)
        if did_review > 0:
          self.update_stats()
        if not self.args.daemon:
          break
        if self.args.verbose:
          print('Finished! Going to sleep until next run')

      except (requests.exceptions.HTTPError, OSError) as e:
        sys.stderr.write('Error getting changes: ({})\n'.format(str(e)))
        time.sleep(60)

      time.sleep(120)


def main():
  parser = argparse.ArgumentParser(description='Troll gerrit reviews')
  parser.add_argument('--git-dir', default=None, help='Path to git directory')
  parser.add_argument('--verbose', help='print commits', action='store_true')
  parser.add_argument('--chatty', help='print diffs', action='store_true')
  parser.add_argument('--daemon', action='store_true',
    help='Run in daemon mode, for continuous trolling')
  parser.add_argument('--dry-run', action='store_true', default=False,
                      help='skip the review step')
  parser.add_argument('--force-cl', default=None, help='Force review a CL')
  parser.add_argument('--force-all', action='store_true', default=False,
                      help='Force review all (implies dry-run)')
  parser.add_argument('--stats-file', default=None, help='Path to stats file')
  parser.add_argument('--kconfig-hound', default=None, action='store_true',
    help='Compute and post the total difference for kconfig changes')
  args = parser.parse_args()

  if args.force_all:
    args.dry_run = True

  troll = Troll('https://chromium-review.googlesource.com', args)
  troll.run()

if __name__ == '__main__':
  sys.exit(main())
