from patchwork import PatchworkPatch
from reviewer import LineType
from trollreview import ReviewResult
from trollreview import ReviewType
from trollreviewer import ChangeReviewer
from trollstrings import ReviewStrings

from fuzzywuzzy import fuzz
import logging
import sys

logger = logging.getLogger('rom.troll.reviewer.fromlist')

class FromlistReviewStrings(ReviewStrings):
  CLEAN_BACKPORT_FOOTER='''
Consider changing your subject prefix to FROMLIST to better reflect the
contents of this patch.
'''
  UPSTREAM_INLINE_COMMENT='''
-- Upstream comment by {} <{}> --
{}
--
src: {}
'''
  UPSTREAM_COMMENT_HEADER='''
This patch has comments upstream. Wherever possible, those comments have been
duplicated on this review, but there may be some that could not be. To view the
comments, follow the patchwork link in the commit message or click on the links
below.
'''
  UPSTREAM_COMMENT_LINE='''
  From {} <{}>: {}'''

class FromlistChangeReviewer(ChangeReviewer):
  def __init__(self, project, reviewer, change, msg_limit, dry_run):
    super().__init__(project, reviewer, change, msg_limit, dry_run)
    self.strings = FromlistReviewStrings()
    self.review_result = ReviewResult(self.change, self.strings, self.dry_run)
    self.review_backports = True
    self.patchwork_patch = None
    self.patchwork_comments = None

  @staticmethod
  def can_review_change(project, change, days_since_last_review):
    # No timed re-review on fromlist patches
    if days_since_last_review != None:
      return False

    return 'FROMLIST' in project.prefixes and 'FROMLIST' in change.subject

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

  def add_inline_comment_review(self, comment, inline_msg):
    formatted_msg = ''
    for l in inline_msg.comment:
      formatted_msg += '> {}\n'.format(l)

    msg = self.strings.UPSTREAM_INLINE_COMMENT.format(comment.name,
                    comment.email, formatted_msg, comment.url)
    self.review_result.add_inline_comment(inline_msg.filename, inline_msg.line,
                                          msg)

  def add_upstream_comment_review(self):
    msg = self.strings.UPSTREAM_COMMENT_HEADER
    for c in self.patchwork_comments:
      msg += self.strings.UPSTREAM_COMMENT_LINE.format(c.name, c.email, c.url)
    self.review_result.add_review(ReviewType.UPSTREAM_COMMENTS, msg)

  def get_upstream_patch(self):
    patchwork_url = self.reviewer.get_am_from_from_patch(self.gerrit_patch)
    if not patchwork_url:
      self.add_missing_am_review(self.change)
      return

    for u in reversed(patchwork_url):
      try:
        patchwork_patch = PatchworkPatch(self.project.patchworks, u)
        self.upstream_patch = patchwork_patch.get_patch()
        self.patchwork_patch = patchwork_patch
        break
      except:
        continue

    if not self.upstream_patch:
      logger.warning('patch missing from patchwork, or patchwork host not '
                     'allowed for {} ({})'.format(self.change,
                     patchwork_url))
      return

    try:
      self.patchwork_comments = self.patchwork_patch.get_comments()
    except Exception as e:
      logger.exception('Exception fetching comments: {}'.format(e))
      pass

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

  def find_line_for_inline_msg(self, diff, msg):
    cur_file = '/COMMIT_MSG'
    cur_line = 6 # The COMMIT_MSG "file" has a 6 line header
    ctx_counter = 0

    for l in diff:
      t,m = self.reviewer.classify_line(l)
      # If a file is being deleted, the file below will be /dev/null. Gerrit
      # (rightfully) doesn't know what to do with a comment on the file
      # /dev/null, so it will throw a 400-BAD_REQUEST if we try.
      #
      # TODO: We should store FILE_OLD as cur_file and then update cur_file to
      #       FILE_NEW if it is not /dev/null. I _think_ it's that easy, but
      #       don't have time to actually test the edge cases. So for now we'll
      #       store /dev/null and then discard the comment because
      #       msg.has_filename() will fail. All this work for nothing :(
      if t == LineType.FILE_NEW:
        cur_file = m.group(1)
        cur_line = 0
      elif t == LineType.CHUNK:
        cur_line = int(m.group(3)) - 1 # Take away one since we add it back

      # Increment the line count if we're counting up from a chunk or parsing
      # the commit message
      elif (t == LineType.CONTEXT or
            (t == LineType.DIFF and l[0] == '+') or
            cur_file == '/COMMIT_MSG'):
        cur_line += 1

      ratio = fuzz.token_set_ratio(l, msg.context[ctx_counter])
      gerrit_line = l.strip('+- \t')
      context_line = msg.context[ctx_counter].strip('+- \t')

      #logging.debug('G: {}'.format(l.strip('+- \t')))
      #logging.debug('P: {}'.format(msg.context[ctx_counter].strip('+- \t')))

      if gerrit_line == context_line:
        # If we find any (non-empty) match, set the return values since the
        # context may not _exactly_ match
        if context_line:
          msg.set_filename(cur_file)
          msg.set_line(cur_line)
        ctx_counter += 1

      #logging.debug('R: f={} l={} cc={} ratio={}'.format(msg.filename, msg.line, ctx_counter, ratio))

      if ctx_counter and ctx_counter == len(msg.context):
        break

  def find_parent_comment(self, msg):
    msg_test = ' '.join(msg.context).lower()
    min_ratio = 90
    for c in self.patchwork_comments:
      for m in c.inline_comments:
        # This assumes that comments are processed in order. I think that
        # assumption holds true for now and I'm being lazy, so there's that.
        if msg == m or (not m.has_filename() and not m.has_line()):
          continue

        parent_test = ' '.join(m.comment).lower()
        ratio = fuzz.token_set_ratio(msg_test, parent_test)
        if ratio >= min_ratio:
          msg.set_filename(m.filename)
          msg.set_line(m.line)

  def compare_patches(self):
    super().compare_patches()

    if not self.patchwork_comments:
      return

    split_patch = self.gerrit_patch.split('\n')
    for c in self.patchwork_comments:
      for m in c.inline_comments:
        self.find_line_for_inline_msg(split_patch, m)

    for c in self.patchwork_comments:
      for m in c.inline_comments:
        if m.has_filename() and m.has_line():
          continue
        self.find_parent_comment(m)

    for c in self.patchwork_comments:
      for m in c.inline_comments:
        if m.has_filename() and m.has_line():
          self.add_inline_comment_review(c, m)
        '''
        else:
          logging.debug("FOUND ABANDONED COMMENT")
          logging.debug("--------")
          logging.debug(c)
          logging.debug("--------")
        '''
    self.add_upstream_comment_review()
