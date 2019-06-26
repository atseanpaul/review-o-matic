import collections
import pathlib
import json
import re
import requests
import sys
import urllib

class PatchworkInlineComment(object):
  def __init__(self):
    self.context = collections.deque(maxlen=3)
    self.comment = []
    self.filename = None
    self.line = None

  def add_context(self, line):
    self.context.append(line)

  def has_context(self):
    return bool(self.context)

  def add_comment(self, line):
    self.comment.append(line)

  def has_comments(self):
    return bool(self.comment)

  def set_filename(self, filename):
    self.filename = filename

  def has_filename(self):
    return bool(self.filename)

  def set_line(self, line):
    self.line = line

  def has_line(self):
    return self.line != None

  def __str__(self):
    ret = 'CONTEXT:\n--\n'
    ret += '\n'.join(self.context)
    ret += '\n'
    ret += 'COMMENT:\n--\n'
    ret += '\n'.join(self.comment)
    ret += '\n'
    return ret

  def __repr__(self):
    return self.__str__()


class PatchworkComment(object):
  def __init__(self, rest):
    self.id = rest['id']
    self.url = rest['web_url']
    self.name = rest['submitter']['name']
    self.email = rest['submitter']['email']
    self.inline_comments = []
    self.__parse_comment(rest['content'])

  def __parse_comment(self, content):
    pat = re.compile('>[\s>]*(.*)')
    lines = content.split('\n')

    cur = PatchworkInlineComment()
    for l in lines:
      m = re.match(pat, l)

      # skip empty lines
      if not l or (m and not m.group(1)):
        continue

      # Found the end of a comment, save it and start cur over
      if m and cur.has_comments():
        # Only save comments with context, throw away top-posts
        if cur.has_context():
          self.inline_comments.append(cur)
        cur = PatchworkInlineComment()

      if m:
        cur.add_context(m.group(1))
      elif l.strip():
        cur.add_comment(l)

    if cur.has_context() and cur.has_comments():
      self.inline_comments.append(cur)

  def __str__(self):
    ret = 'Comment:\n'
    ret += ' ID: {}\n'.format(self.id)
    ret += ' Author: {} <{}>\n'.format(self.name, self.email)
    ret += ' Inline Comments:\n'
    for c in self.inline_comments:
      ret += str(c)
      ret += '\n'
    ret += '---\n'
    return ret

  def __repr__(self):
    return self.__str__()


class PatchworkPatch(object):
  # Whitelisted patchwork hosts
  PATCHWORK_WHITELIST = [
    'lore.kernel.org',
    'patchwork.freedesktop.org',
    'patchwork.kernel.org',
    'patchwork.linuxtv.org',
    'patchwork.ozlabs.org'
  ]

  def __init__(self, url):
    parsed = urllib.parse.urlparse(url)

    m = re.match('/([a-z/]*)/([0-9]*)/?', parsed.path)
    if not m or not m.group(2):
      sys.stderr.write('ERROR: Malformed patchwork URL "%s"\n' % url)
      raise ValueError('Invalid url')

    if parsed.netloc not in self.PATCHWORK_WHITELIST:
      sys.stderr.write('ERROR: Patchwork host not whitelisted "%s"\n' % url)
      raise ValueError('Invalid host')

    self.url = parsed
    self.id = int(m.group(2))
    self.patch = None
    self.comments = []

  def get_patch(self):
    if not self.patch:
      raw_path = str(pathlib.PurePath(self.url.path, 'raw'))
      raw_url = self.url._replace(path=raw_path)
      self.patch = requests.get(raw_url.geturl()).text
    return self.patch

  def get_comments(self):
    if not self.comments:
      comments_path = '/api/patches/{}/comments/'.format(self.id)
      comments_url = self.url._replace(path=comments_path)
      rest = requests.get(comments_url.geturl()).json()
      for c in rest:
        comment = PatchworkComment(c)
        self.comments.append(comment)

    return self.comments
