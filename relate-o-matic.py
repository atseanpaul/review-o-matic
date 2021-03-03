#!/usr/bin/python3

from patchwork import PatchworkPatch
from reviewer import Reviewer
from trollconfig import TrollConfigPatchwork

import argparse
import logging
from logging import handlers
import re
import sys
import urllib

logger = logging.getLogger('rom')
logger.setLevel(logging.DEBUG) # leave this to handlers

def setup_logging(args):
  info_handler = logging.StreamHandler(sys.stdout)
  info_handler.setFormatter(logging.Formatter('%(levelname)6s - %(name)s - %(message)s'))
  if args.verbose:
    info_handler.setLevel(logging.DEBUG)
  else:
    info_handler.setLevel(logging.INFO)
  logger.addHandler(info_handler)


def main():
  parser = argparse.ArgumentParser(description='Get related patches')
  parser.add_argument('--git-dir', default=None, help='Path to git directory')
  parser.add_argument('--verbose', help='print commits', action='store_true')
  parser.add_argument('--chatty', help='print diffs', action='store_true')
  parser.add_argument('--commit', help='commit hash to find related patches',
                      required=True)
  args = parser.parse_args()

  setup_logging(args)

  reviewer = Reviewer(args.verbose, args.chatty, git_dir=args.git_dir)
  links = reviewer.get_links_from_local_sha(args.commit)

  series = None
  for l in reversed(links):
    logger.debug('Trying patchwork link {}'.format(l))
    parsed = urllib.parse.urlparse(l)

    m = re.match('(.*?)/patch/([^/]*)/?', parsed.path)
    if not m:
      continue
    pw = TrollConfigPatchwork('generated', parsed.netloc, m.group(1), False)

    logger.debug('Trying parsed patchwork link {}'.format(pw))
    p = PatchworkPatch([pw], l)
    series = p.get_series()
    if series:
      break

  if not series:
      logger.error('Could not find series for patch')
      return 1

  logger.info('Found series: {}'.format(series.url.geturl()))
  patches = series.get_patch_subjects()
  for p in patches:
    logger.info(' Find commits for: {}'.format(p))
    commit = reviewer.get_commit_from_subject(p, surrounding_commit=args.commit)
    if not commit:
      logger.warning('Could not find commit for {}'.format(p))
    for c in commit:
      logger.info('   Found: {}'.format(c))
  

if __name__ == '__main__':
  sys.exit(main())
