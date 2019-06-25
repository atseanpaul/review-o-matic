from trollreview import ReviewResult
from trollreviewergit import GitChangeReviewer
from trollstrings import ReviewStrings

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

class UpstreamChangeReviewer(GitChangeReviewer):
  def __init__(self, reviewer, change, dry_run):
    super().__init__(reviewer, change, dry_run)
    self.strings = UpstreamReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)

  @staticmethod
  def can_review_change(change, days_since_last_review):
    # labeled UPSTREAM or labeled BACKPORT
    return (days_since_last_review == None and
            ('UPSTREAM' in change.subject or
             ('BACKPORT' in change.subject and
              'FROMGIT' not in change.subject and
              'FROMLIST' not in change.subject)))
