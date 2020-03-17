import collections
import html
import pathlib
import json
import logging
import re
import requests
import sys
import urllib

logger = logging.getLogger('rom.patchwork')

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
    return bool(self.filename) and self.filename != '/dev/null'

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

class PatchworkSeries(object):
  def __init__(self, url):
    self.url = url

  def get_patch_subjects(self):
    patch = requests.get(self.url.geturl()).text.replace('\n','')
    pattern = '<a'
    pattern += '\s+'
    pattern += 'href='
    pattern += '"/patch/([0-9]+)/.*?"'
    pattern += '\s*>\s*'
    pattern += '\[\S*\] (.*?)'
    pattern += '</a>'
    regex = re.compile(pattern, flags=(re.I | re.MULTILINE | re.DOTALL))
    m = regex.findall(patch)
    if not m or not len(m):
      return None
    ret = []
    for s in m:
      ret.append(html.unescape(s[1]))
    return ret


class PatchworkPatch(object):
  def __init__(self, whitelist, url):
    parsed = urllib.parse.urlparse(url)

    m = re.match('/([a-z/]*)/([0-9]*)/?', parsed.path)
    if not m or not m.group(2):
      logger.error('Malformed patchwork URL "%s"'.format(url))
      raise ValueError('Invalid url')

    found = False
    for i in whitelist:
      if parsed.netloc == i.host:
        self.path_prefix = i.path
        self.comments_supported = i.has_comments
        found = True
        break
    if not found:
      logger.error('Patchwork host not whitelisted "%s"'.format(url))
      raise ValueError('Invalid host')

    self.url = parsed
    self.id = int(m.group(2))
    self.patch = None
    self.comments = []

  def get_series(self):
    patch = requests.get(self.url.geturl()).text
    m = re.findall('a href="/series/([0-9]+)/"', patch)
    if not m or not len(m):
      return None
    return PatchworkSeries(self.url._replace(path='/series/{}/'.format(m[0])))

  def get_patch(self):
    if not self.patch:
      raw_path = pathlib.PurePath(self.url.path, 'raw')
      raw_url = self.url._replace(path=str(raw_path))
      self.patch = requests.get(raw_url.geturl()).text
    return self.patch

  def get_comments(self):
    if self.comments or not self.comments_supported:
        return self.comments

    comments_path = pathlib.PurePath(self.path_prefix,
                                     'api/patches/{}/comments/'.format(self.id))
    comments_url = self.url._replace(path=str(comments_path))
    resp = requests.get(comments_url.geturl())

    rest = resp.json()
    for c in rest:
      comment = PatchworkComment(c)
      self.comments.append(comment)

    return self.comments
