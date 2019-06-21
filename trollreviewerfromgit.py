from trollreview import ReviewResult
from trollreviewergit import GitChangeReviewer
from trollstrings import ReviewStrings

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

class FromgitChangeReviewer(GitChangeReviewer):
  def __init__(self, reviewer, change, dry_run):
    super().__init__(reviewer, change, dry_run)
    self.strings = FromgitReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)

  @staticmethod
  def can_review_change(change):
    return 'FROMGIT' in change.subject
