from trollreview import ReviewType

import random
import re

class ChangeReviewer(object):
  def __init__(self, project, reviewer, change, msg_limit, dry_run):
    self.project = project
    self.reviewer = reviewer
    self.is_backport = 'BACKPORT' in change.subject
    self.is_fixup = 'FIXUP' in change.subject
    self.is_revert = change.subject.startswith('Revert ')
    self.change = change
    self.msg_limit = msg_limit
    self.dry_run = dry_run
    self.gerrit_patch = None
    self.upstream_patch = None
    self.review_result = None
    self.strings = None
    self.diff = None

  @staticmethod
  def can_review_change(project, change, days_since_last_review):
    raise NotImplementedError()

  def format_diff(self):
    # Leave room for boilerplate and other review feedback, 2k chars for now
    max_size = self.msg_limit - 2048
    msg = ''
    for l in self.diff:
      msg += '  {}\n'.format(l)

    if len(msg) > max_size:
      trunc_msg = '\n\n  !!!! Diff truncated !!!!'
      msg = msg[:(max_size - len(trunc_msg))]
      msg += trunc_msg

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
                                  self.project.gerrit_remote_name,
                                  self.change.current_revision.ref)
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
