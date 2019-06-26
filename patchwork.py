import pathlib
import re
import requests
import sys
import urllib

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

  def get_patch(self):
    raw_path = str(pathlib.PurePath(self.url.path, 'raw'))
    raw_url = self.url._replace(path=raw_path)
    return requests.get(raw_url.geturl()).text
