from trollreview import ReviewResult
from trollreview import ReviewType
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
  PATCH_IN_MAINLINE='''
This patch is labeled as FROMGIT, however it seems like it's already been
applied to mainline. Please revise your patch subject to replace FROMGIT with
UPSTREAM.
'''

class FromgitChangeReviewer(GitChangeReviewer):
  def __init__(self, reviewer, change, dry_run, days_since_last_review):
    super().__init__(reviewer, change, dry_run)
    self.strings = FromgitReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)
    self.days_since_last_review = days_since_last_review

  @staticmethod
  def can_review_change(change, days_since_last_review):
    return ('FROMGIT' in change.subject and
            (days_since_last_review == None or days_since_last_review >= 14))

  def add_patch_in_mainline_review(self):
    self.review_result.add_review(ReviewType.IN_MAINLINE,
                                  self.strings.PATCH_IN_MAINLINE, vote=-1,
                                  notify=True)

  def get_upstream_patch(self):
    super().get_upstream_patch()

    if self.upstream_patch and self.upstream_sha:
      remote = self.DEFAULT_REMOTE
      remote_name = self.reviewer.generate_remote_name(remote)
      self.reviewer.fetch_remote(remote_name, remote, self.DEFAULT_BRANCH)
      if self.reviewer.is_sha_in_branch(self.upstream_sha['sha'], remote_name,
                                        self.DEFAULT_BRANCH):
        self.add_patch_in_mainline_review()
        return

  def review_patch(self):
    result = super().review_patch()

    # Only re-review patches if we're adding an IN_MAINLINE review
    if (self.days_since_last_review != None and
        ReviewType.IN_MAINLINE not in result.issues):
      return None

    return result
