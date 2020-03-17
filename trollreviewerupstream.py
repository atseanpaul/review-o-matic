from trollreview import ReviewResult
from trollreview import ReviewType
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
  PATCH_NOT_IN_MAINLINE='''
This patch is labeled as {}, however it seems like it has not
been applied to mainline. If your patch is in a maintainer tree, please use the
{}FROMGIT subject prefix.
'''

class UpstreamChangeReviewer(GitChangeReviewer):
  def __init__(self, project, reviewer, change, dry_run):
    super().__init__(project, reviewer, change, dry_run)
    self.strings = UpstreamReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)

  @staticmethod
  def can_review_change(project, change, days_since_last_review):
    # No timed re-review on upstream patches
    if days_since_last_review != None:
      return False

    if 'UPSTREAM' in project.prefixes and 'UPSTREAM' in change.subject:
      return True

    if ('BACKPORT' in project.prefixes and
        'BACKPORT' in change.subject and
        'FROMGIT' not in change.subject and
        'FROMLIST' not in change.subject):
      return True

    return False

  def add_patch_not_in_mainline_review(self):
    msg = self.strings.PATCH_NOT_IN_MAINLINE.format(
            'BACKPORT' if self.is_backport else 'UPSTREAM',
            'BACKPORT: ' if self.is_backport else '')
    self.review_result.add_review(ReviewType.NOT_IN_MAINLINE, msg, vote=-1,
                                  notify=True)

  def get_upstream_patch(self):
    super().get_upstream_patch()

    if not self.is_sha_in_mainline():
      self.add_patch_not_in_mainline_review()
