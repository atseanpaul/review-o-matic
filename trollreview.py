import enum
import random

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
  IN_MAINLINE = 'in_mainline'
  UPSTREAM_COMMENTS = 'upstream_comments'
  NOT_IN_MAINLINE = 'not_in_mainline'

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
    self.inline_comments = {}

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

  def add_inline_comment(self, new_file, line, comment):
    if not self.inline_comments.get(new_file):
      self.inline_comments[new_file] = []
    self.inline_comments[new_file].append({"line": line, "message": comment})

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
