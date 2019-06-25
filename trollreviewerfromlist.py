from trollreview import ReviewResult
from trollreview import ReviewType
from trollreviewer import ChangeReviewer
from trollstrings import ReviewStrings

import sys

class FromlistReviewStrings(ReviewStrings):
  CLEAN_BACKPORT_FOOTER='''
Consider changing your subject prefix to FROMLIST to better reflect the
contents of this patch.
'''

class FromlistChangeReviewer(ChangeReviewer):
  def __init__(self, reviewer, change, dry_run):
    super().__init__(reviewer, change, dry_run)
    self.strings = FromlistReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)
    self.review_backports = False

  @staticmethod
  def can_review_change(change, days_since_last_review):
    return days_since_last_review == None and 'FROMLIST' in change.subject

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
