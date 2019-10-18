#!/usr/bin/python3

import argparse
import logging
import re
import subprocess
import sys

from reviewer import Reviewer

logger = logging.basicConfig(stream=sys.stdout, level=logging.WARNING)

def review_change(reviewer, local_sha):
  upstream_sha = reviewer.get_cherry_pick_sha_from_local_sha(local_sha)
  upstream_patch = reviewer.get_commit_from_sha(upstream_sha)
  local_patch = reviewer.get_commit_from_sha(local_sha)
  result = reviewer.compare_diffs(upstream_patch, local_patch)

  if reviewer.verbose or reviewer.chatty or len(result):
    logger.info('Reviewing %s (rmt=%s)' % (local_sha, upstream_sha[:11]))

  for l in result:
    logger.info(l)

  if len(result):
    logger.info('')

  return len(result)


def main():
  parser = argparse.ArgumentParser(description='Auto review UPSTREAM patches')
  parser.add_argument('--start', help='commit hash to start from',
                      required=True)
  parser.add_argument('--prefix', default='UPSTREAM', help='subject prefix')
  parser.add_argument('--verbose', help='print commits', action='store_true')
  parser.add_argument('--chatty', help='print diffs', action='store_true')
  args = parser.parse_args()

  if args.verbose or args.chatty:
    logger.setLevel(logging.DEBUG)

  proc = subprocess.check_output(
          ['git', 'log', '--oneline', '%s^..' % args.start])

  regex = re.compile('([0-9a-f]*) (%s): ' % (args.prefix), flags=re.I)
  ret = 0
  reviewer = Reviewer(args.verbose, args.chatty)
  for l in reversed(proc.decode('UTF-8').split('\n')):
    this_ret = 0
    m = regex.match(l)
    if m:
      this_ret = review_change(reviewer, m.group(1))
    ret += this_ret

  return ret

if __name__ == '__main__':
  sys.exit(main())
