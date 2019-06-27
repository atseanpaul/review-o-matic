from configchecker import KernelConfigChecker
from trollreview import ReviewResult
from trollreview import ReviewType
from trollreviewer import ChangeReviewer
from trollstrings import ReviewStrings

class ChromiumReviewStrings(ReviewStrings):
  CONFIG_DIFFS='''
Just thought you might like to know the kernel configs have changed in the
following way:
'''

class ChromiumChangeReviewer(ChangeReviewer):
  def __init__(self, reviewer, change, dry_run, verbose):
    super().__init__(reviewer, change, dry_run)
    self.strings = ChromiumReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)
    self.review_backports = False
    self.verbose = verbose
    self.config_diff = None

  @staticmethod
  def can_review_change(change, days_since_last_review):
    return days_since_last_review == None and 'CHROMIUM' in change.subject

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
