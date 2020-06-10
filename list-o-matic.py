#!/usr/bin/python3

import argparse
from collections import defaultdict
import json
import logging
import subprocess
import sys
import time

from gerrit import Gerrit

logging.basicConfig(stream=sys.stdout, level=logging.INFO)



def main():
  parser = argparse.ArgumentParser(description='Generate list of changes')
  parser.add_argument('--owner', required=True, help='Address of owner')
  parser.add_argument('--review-score', default=None, type=int,
    help='Desired review score')
  args = parser.parse_args()

  gerrit = Gerrit('https://chromium-review.googlesource.com',
                       use_internal=False)

  changes = gerrit.query_changes(owner=args.owner, status='open')
  output = defaultdict(list)

  for c in changes:
    add = True
    if args.review_score != None:
      for r in c.vote_code_review:
        if r == args.review_score:
          add = False
        if r < 0:
          add = False

    if add:
      output[c.subject].append(c)

  for k,v in output.items():
    print('{:78.78}'.format(k))
    for c in v:
      print('  {:34} http://crosreview.com/{}'.format(c.branch, c.number))
    print('')


if __name__ == '__main__':
  sys.exit(main())
